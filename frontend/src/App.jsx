import { useState } from "react";
import ConnectionBar from "./components/ConnectionBar/ConnectionBar";
import ChatWindow from "./components/ChatWindow/ChatWindow";
import ChatInput from "./components/ChatInput/ChatInput";
import SchemaGraphModal from "./components/SchemaGraphModal/SchemaGraphModal";
import { useConnections } from "./hooks/useConnections";
import { useChat } from "./hooks/useChat";
import styles from "./App.module.css";

export default function App() {
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
