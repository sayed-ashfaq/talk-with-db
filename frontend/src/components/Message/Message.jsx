import SqlToggle from "./SqlToggle";
import { formatInlineText } from "./formatInlineText";
import styles from "./Message.module.css";

export default function Message({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`${styles.row} ${isUser ? styles.rowUser : ""}`}>
      <div className={`${styles.bubble} ${isUser ? styles.bubbleUser : styles.bubbleAssistant}`}>
        <p className={styles.text}>{isUser ? message.content : formatInlineText(message.content)}</p>
        {message.sql != null && <SqlToggle sql={message.sql} />}
      </div>
    </div>
  );
}
