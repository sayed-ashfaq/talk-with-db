import { useCallback, useRef, useState } from "react";
import * as api from "../api/client";

let nextId = 0;
const newId = () => `msg-${Date.now()}-${nextId++}`;

// generous for a text-heavy PDF or a real spreadsheet, matching the backend's own 20MB cap on
// both upload routes — checked here too so a too-large file never makes the round trip at all
const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

function classifyFile(file) {
  const name = (file.name || "").toLowerCase();
  if (name.endsWith(".pdf")) return "pdf";
  if (name.endsWith(".csv")) return "csv";
  return null;
}

// Unary on purpose: `messages.map(toMessage)` would otherwise hand the array index to a second
// parameter, which is a silent wrong answer rather than an error.
//
// `data` comes back on the message itself when a conversation is reopened, and separately on the
// response when a turn has just run — the live copy is the full result, the stored one is trimmed
// to a size bound, so the turn that ran shows everything it fetched.
const toMessage = (m) => ({
  id: m.id,
  role: m.role,
  content: m.content,
  sql: m.sql,
  routedTo: m.routed_to,
  data: m.data ?? null,
});

/**
 * A single conversation.
 *
 * The server owns the history — this holds a chat id, not a transcript, so a refresh or a second
 * tab picks up exactly where the last one left off. `onChatCreated` fires when a message starts a
 * new conversation, which is the sidebar's cue to add a row.
 */
export function useChat({ onChatCreated, onChatUpdated } = {}) {
  const [messages, setMessages] = useState([]);
  const [isSending, setIsSending] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  // which top-level agent a new conversation goes to. Only meaningful before the first message —
  // once a chat exists, its section is fixed server-side, so this is otherwise just display state.
  // "general" (the Chat agent) is the default landing experience; Database is the opt-in.
  const [section, setSection] = useState("general");
  const chatIdRef = useRef(null);

  // a file picked before the chat exists (POST /chat requires non-empty text, so a chat can never
  // be created from an attachment alone) — held here until the first message returns a chat_id
  const [stagedFile, setStagedFile] = useState(null); // { file, kind: "pdf" | "csv" } | null
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  // so a second CSV upload in the same chat can say what it replaced — csv_agent always answers
  // from the most recent one, and that's otherwise invisible to the user
  const lastCsvFilenameRef = useRef(null);

  // start a new conversation: no request needed, the chat row is created by the first message.
  // targetSection omitted keeps whatever section is currently selected (the plain "New chat"
  // button); passed explicitly, it also switches section (the sidebar's section switch, which
  // can't change an existing chat's section, so it starts a fresh one instead).
  const newChat = useCallback((targetSection) => {
    chatIdRef.current = null;
    setMessages([]);
    setError(null);
    if (targetSection) setSection(targetSection);
    setStagedFile(null);
    setUploadError(null);
    lastCsvFilenameRef.current = null;
  }, []);

  const openChat = useCallback(async (chatId) => {
    setError(null);
    setIsLoading(true);
    try {
      const chat = await api.getChat(chatId);
      chatIdRef.current = chat.id;
      setMessages(chat.messages.map(toMessage));
      setSection(chat.section);
      setStagedFile(null);
      setUploadError(null);
      lastCsvFilenameRef.current = null;
    } catch (err) {
      setError(err.message || "Couldn't open that conversation.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // shared by the staged-file flow (chat just got its id) and the direct-upload flow (chat
  // already existed) — appends a confirmation chip to the thread rather than a real chat turn
  const performUpload = useCallback(async (targetChatId, file, kind) => {
    setIsUploading(true);
    setUploadError(null);
    try {
      if (kind === "pdf") {
        const doc = await api.uploadDocument(file, targetChatId);
        setMessages((prev) => [
          ...prev,
          { id: newId(), kind: "attachment", fileType: "pdf", filename: doc.filename, chunkCount: doc.chunk_count },
        ]);
      } else {
        const previousFilename = lastCsvFilenameRef.current;
        const upload = await api.uploadCsv(targetChatId, file);
        lastCsvFilenameRef.current = upload.filename;
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            kind: "attachment",
            fileType: "csv",
            filename: upload.filename,
            rowCount: upload.row_count,
            truncated: upload.truncated,
            replacedFilename: previousFilename && previousFilename !== upload.filename ? previousFilename : null,
          },
        ]);
      }
    } catch (err) {
      setUploadError(err.message || "Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
    }
  }, []);

  const attachFile = useCallback(
    (file) => {
      const kind = classifyFile(file);
      if (!kind) {
        setUploadError("Only PDF and CSV files are supported.");
        return;
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        setUploadError("File is too large (20MB limit).");
        return;
      }
      setUploadError(null);
      if (chatIdRef.current === null) {
        setStagedFile({ file, kind });
      } else {
        performUpload(chatIdRef.current, file, kind);
      }
    },
    [performUpload],
  );

  const clearStagedFile = useCallback(() => setStagedFile(null), []);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed || isSending) return;

      setError(null);
      // shown immediately; the server's copy replaces nothing, so this keeps its temporary id
      setMessages((prev) => [...prev, { id: newId(), role: "user", content: trimmed }]);
      setIsSending(true);

      try {
        const response = await api.sendChatMessage(trimmed, chatIdRef.current, section);
        const isNew = chatIdRef.current === null;
        chatIdRef.current = response.chat_id;

        setMessages((prev) => [
          ...prev,
          { ...toMessage(response.message), data: response.data ?? null },
        ]);

        if (isNew) {
          onChatCreated?.({ id: response.chat_id, title: response.title });
          if (stagedFile) {
            const toUpload = stagedFile;
            setStagedFile(null);
            performUpload(response.chat_id, toUpload.file, toUpload.kind);
          }
        } else {
          onChatUpdated?.(response.chat_id);
        }
      } catch (err) {
        setError(err.message || "Something went wrong. Please try again.");
      } finally {
        setIsSending(false);
      }
    },
    [isSending, section, stagedFile, performUpload, onChatCreated, onChatUpdated],
  );

  return {
    chatId: chatIdRef.current,
    messages,
    sendMessage,
    newChat,
    openChat,
    isSending,
    isLoading,
    error,
    section,
    // locked once the conversation has actually started — a chat's section can't change after
    // creation, so the switcher shouldn't offer to either
    setSection: chatIdRef.current === null ? setSection : undefined,
    stagedFile,
    attachFile,
    clearStagedFile,
    isUploading,
    uploadError,
  };
}
