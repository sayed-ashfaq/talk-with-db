import ChatListItem from "./ChatListItem";
import DocumentsSection from "./DocumentsSection";
import SectionSwitch from "../SectionSwitch/SectionSwitch";
import { PlusIcon, SidebarIcon, SparkleIcon } from "../common/icons";
import styles from "./Sidebar.module.css";

export default function Sidebar({
  chats,
  activeChatId,
  isLoading,
  error,
  section,
  onSelect,
  onNew,
  onRename,
  onDelete,
  onCollapse,
}) {
  // a chat's section is fixed at creation, so picking the other one here can't change the
  // current chat — it starts a fresh one instead. No-op if the already-active option is clicked,
  // so this never discards an in-progress conversation for nothing.
  const handleSectionSwitch = (value) => {
    if (value !== section) onNew(value);
  };

  return (
    <aside className={styles.root}>
      <div className={styles.brandRow}>
        <div className={styles.brandMark}>
          <SparkleIcon />
          <span>NL2SQL</span>
        </div>
        <button
          type="button"
          className={styles.collapseButton}
          onClick={onCollapse}
          aria-label="Collapse sidebar"
          title="Collapse sidebar"
        >
          <SidebarIcon />
        </button>
      </div>

      <div className={styles.sectionSwitchRow}>
        <SectionSwitch value={section} onChange={handleSectionSwitch} compact />
      </div>

      <div className={styles.top}>
        <button type="button" className={styles.newChatButton} onClick={() => onNew()}>
          <PlusIcon />
          New chat
        </button>
      </div>

      <DocumentsSection />

      <div className={styles.list}>
        {isLoading ? (
          <p className={styles.hint}>Loading…</p>
        ) : error ? (
          <p className={styles.hint}>{error}</p>
        ) : chats.length === 0 ? (
          <p className={styles.hint}>No conversations yet.</p>
        ) : (
          chats.map((chat) => (
            <ChatListItem
              key={chat.id}
              chat={chat}
              isActive={chat.id === activeChatId}
              onSelect={() => onSelect(chat.id)}
              onRename={(title) => onRename(chat.id, title)}
              onDelete={() => onDelete(chat.id)}
            />
          ))
        )}
      </div>
    </aside>
  );
}
