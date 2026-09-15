import { useEffect, useRef } from "react";
import Message from "../Message/Message";
import LoadingDots from "../common/LoadingDots";
import ErrorBanner from "../common/ErrorBanner";
import styles from "./ChatWindow.module.css";

export default function ChatWindow({ messages, isSending, error }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isSending]);

  return (
    <div className={styles.window}>
      {messages.map((message) => (
        <Message key={message.id} message={message} />
      ))}

      {isSending && (
        <div className={styles.pendingRow}>
          <LoadingDots />
        </div>
      )}

      <ErrorBanner message={error} />
      <div ref={bottomRef} />
    </div>
  );
}
