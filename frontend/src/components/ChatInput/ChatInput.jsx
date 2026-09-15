import { useRef, useState } from "react";
import { DocumentIcon, PaperclipIcon } from "../common/icons";
import styles from "./ChatInput.module.css";

const MAX_HEIGHT_PX = 160;

export default function ChatInput({
  onSend,
  disabled,
  section,
  onAttach,
  stagedFile,
  onClearStaged,
  isUploading,
  uploadError,
}) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  // attaching only makes sense for the general/Chat agent — the database section has no
  // rag_agent/csv_agent to hand a file to
  const canAttach = section !== "database";

  const handleChange = (e) => {
    setValue(e.target.value);
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
    }
  };

  const submit = () => {
    if (!value.trim() || disabled) return;
    onSend(value);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // lets picking the same file twice in a row still fire onChange
    if (file) onAttach?.(file);
  };

  return (
    <div className={styles.wrap}>
      {stagedFile && (
        <div className={styles.stagedChip}>
          <DocumentIcon />
          <span className={styles.stagedName}>{stagedFile.file.name}</span>
          <span className={styles.stagedHint}>attaches once you send</span>
          <button type="button" className={styles.stagedRemove} onClick={onClearStaged} aria-label="Remove attachment">
            ×
          </button>
        </div>
      )}

      {uploadError && <p className={styles.uploadError}>{uploadError}</p>}

      <form
        className={styles.form}
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        {canAttach && (
          <>
            <button
              type="button"
              className={styles.attachButton}
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled || isUploading}
              aria-label="Attach a PDF or CSV"
              title="Attach a PDF or CSV"
            >
              <PaperclipIcon />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.csv"
              className={styles.fileInput}
              onChange={handleFileChange}
            />
          </>
        )}

        <textarea
          ref={textareaRef}
          className={styles.textarea}
          placeholder={section === "database" ? "Ask a question about your database…" : "How can I help you today?"}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={disabled}
        />
        <button type="submit" className={styles.sendButton} disabled={disabled || !value.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
