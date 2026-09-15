import { useRef, useState } from "react";
import styles from "./ChatInput.module.css";

const MAX_HEIGHT_PX = 160;

export default function ChatInput({ onSend, disabled, section }) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);

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

  return (
    <form
      className={styles.form}
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
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
  );
}
