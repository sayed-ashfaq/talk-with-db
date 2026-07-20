import SqlToggle from "./SqlToggle";
import Markdown from "./Markdown";
import styles from "./Message.module.css";

export default function Message({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`${styles.row} ${isUser ? styles.rowUser : ""}`}>
      <div className={`${styles.bubble} ${isUser ? styles.bubbleUser : styles.bubbleAssistant}`}>
        {isUser ? <p className={styles.text}>{message.content}</p> : <Markdown>{message.content}</Markdown>}
        {message.sql != null && <SqlToggle sql={message.sql} />}
      </div>
    </div>
  );
}
