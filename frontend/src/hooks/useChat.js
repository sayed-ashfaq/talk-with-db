import { useCallback, useRef, useState } from "react";
import { sendChatMessage } from "../api/client";

let nextId = 0;
const newId = () => `msg-${Date.now()}-${nextId++}`;

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState(null);
  // last "history" the server returned — round-tripped on the next request, per the API
  // contract. The server keeps no session state, so this is the only copy of it.
  const historyRef = useRef([]);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed || isSending) return;

      setError(null);
      setMessages((prev) => [...prev, { id: newId(), role: "user", content: trimmed }]);
      setIsSending(true);

      try {
        const response = await sendChatMessage(trimmed, historyRef.current);
        historyRef.current = response.history;
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "assistant",
            content: response.reply,
            sql: response.sql,
            routedTo: response.routed_to,
          },
        ]);
      } catch (err) {
        setError(err.message || "Something went wrong. Please try again.");
      } finally {
        setIsSending(false);
      }
    },
    [isSending],
  );

  return { messages, sendMessage, isSending, error };
}
