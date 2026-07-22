import { useState } from "react";
import ConnectionBar from "./ConnectionBar/ConnectionBar";
import ChatWindow from "./ChatWindow/ChatWindow";
import ChatInput from "./ChatInput/ChatInput";
import SchemaGraphModal from "./SchemaGraphModal/SchemaGraphModal";
import UserMenu from "./UserMenu/UserMenu";
import { useConnections } from "../hooks/useConnections";
import { useChat } from "../hooks/useChat";
import styles from "../App.module.css";

export default function ChatApp({ auth }) {
  const connections = useConnections();
  const { messages, sendMessage, isSending, error: chatError } = useChat();
  const [isGraphOpen, setIsGraphOpen] = useState(false);

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <h1>NL2SQL</h1>
          <span>Talk with your database</span>
        </div>
        <div className={styles.headerActions}>
          <ConnectionBar
            connections={connections.connections}
            active={connections.active}
            isLoading={connections.isLoading}
            error={connections.error}
            onActivate={connections.activate}
            onCreate={connections.create}
            onDelete={connections.remove}
            onViewGraph={() => setIsGraphOpen(true)}
          />
          <UserMenu user={auth.user} onLogout={auth.logout} />
        </div>
      </header>

      <main className={styles.main}>
        <ChatWindow messages={messages} isSending={isSending} error={chatError} />
        <ChatInput onSend={sendMessage} disabled={isSending} />
      </main>

      {isGraphOpen && (
        <SchemaGraphModal connectionId={connections.active?.id} onClose={() => setIsGraphOpen(false)} />
      )}
    </div>
  );
}
