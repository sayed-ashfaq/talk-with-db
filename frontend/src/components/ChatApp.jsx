import { useState } from "react";
import ConnectionBar from "./ConnectionBar/ConnectionBar";
import ChatWindow from "./ChatWindow/ChatWindow";
import ChatInput from "./ChatInput/ChatInput";
import Landing from "./Landing/Landing";
import SchemaGraphModal from "./SchemaGraphModal/SchemaGraphModal";
import Sidebar from "./Sidebar/Sidebar";
import UserMenu from "./UserMenu/UserMenu";
import { SidebarIcon } from "./common/icons";
import { useConnections } from "../hooks/useConnections";
import { useChat } from "../hooks/useChat";
import { useChatSessions } from "../hooks/useChatSessions";
import styles from "../App.module.css";

// What the header shows in place of the static app name — always the active conversation's
// section, so it's never ambiguous which agent is answering.
const SECTION_COPY = {
  general: { title: "Chat", tagline: "Your general assistant — ask, brainstorm, write." },
  database: { title: "Database", tagline: "Talk to your data in plain English." },
};

export default function ChatApp({ auth }) {
  const connections = useConnections();
  const sessions = useChatSessions();
  const chat = useChat({ onChatCreated: sessions.addChat, onChatUpdated: sessions.touchChat });
  const [isGraphOpen, setIsGraphOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const handleDeleteChat = async (chatId) => {
    await sessions.remove(chatId);
    if (chatId === chat.chatId) chat.newChat();
  };

  // no chat id and nothing sent yet — the landing screen, not the scrolling transcript view
  const isLanding = chat.chatId === null && chat.messages.length === 0;
  const sectionCopy = SECTION_COPY[chat.section] ?? SECTION_COPY.general;

  return (
    <div className={styles.app}>
      {isSidebarOpen && (
        <Sidebar
          chats={sessions.chats}
          activeChatId={chat.chatId}
          isLoading={sessions.isLoading}
          error={sessions.error}
          section={chat.section}
          onSelect={chat.openChat}
          onNew={chat.newChat}
          onRename={sessions.rename}
          onDelete={handleDeleteChat}
          onCollapse={() => setIsSidebarOpen(false)}
        />
      )}

      <div className={styles.mainColumn}>
        <header className={styles.header}>
          <div className={styles.brand}>
            {!isSidebarOpen && (
              <button
                type="button"
                className={styles.sidebarToggle}
                onClick={() => setIsSidebarOpen(true)}
                aria-label="Open sidebar"
                title="Open sidebar"
              >
                <SidebarIcon />
              </button>
            )}
            <div className={styles.brandText}>
              <h1>{sectionCopy.title}</h1>
              <span>{sectionCopy.tagline}</span>
            </div>
          </div>
          <div className={styles.headerActions}>
            {chat.section === "database" && (
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
            )}
            <UserMenu user={auth.user} onLogout={auth.logout} />
          </div>
        </header>

        <main className={styles.main}>
          {isLanding ? (
            <Landing
              user={auth.user}
              section={chat.section}
              onSectionChange={chat.setSection}
              onSend={chat.sendMessage}
              disabled={chat.isSending}
              onAttach={chat.attachFile}
              stagedFile={chat.stagedFile}
              onClearStaged={chat.clearStagedFile}
              isUploading={chat.isUploading}
              uploadError={chat.uploadError}
            />
          ) : (
            <>
              <ChatWindow
                messages={chat.messages}
                isSending={chat.isSending}
                error={chat.error || chat.uploadError}
              />
              <ChatInput
                onSend={chat.sendMessage}
                disabled={chat.isSending}
                section={chat.section}
                onAttach={chat.attachFile}
                stagedFile={chat.stagedFile}
                onClearStaged={chat.clearStagedFile}
                isUploading={chat.isUploading}
              />
            </>
          )}
        </main>
      </div>

      {isGraphOpen && (
        <SchemaGraphModal connectionId={connections.active?.id} onClose={() => setIsGraphOpen(false)} />
      )}
    </div>
  );
}
