import { useMemo } from "react";
import SectionSwitch from "../SectionSwitch/SectionSwitch";
import ChatInput from "../ChatInput/ChatInput";
import { SparkleIcon } from "../common/icons";
import styles from "./Landing.module.css";

const GREETINGS = [
  "Back at it, {name}",
  "Welcome back, {name}",
  "Good to see you, {name}",
  "Ready when you are, {name}",
  "What are we digging into, {name}?",
];

const SUGGESTIONS = {
  general: [
    "Help me draft a follow-up email",
    "Summarize this in plain English",
    "Brainstorm ideas for a project kickoff",
  ],
  database: [
    "What tables are in this database?",
    "Show me the top 10 rows by revenue",
    "How many records are in each table?",
  ],
};

function firstName(user) {
  const source = user?.full_name || user?.email || "";
  return source.split(/[\s@]/)[0] || "there";
}

// Random per landing visit, not per render — picked once when this mounts (a fresh "new chat"),
// not re-rolled on every keystroke in the input below.
function randomGreeting(user) {
  const template = GREETINGS[Math.floor(Math.random() * GREETINGS.length)];
  return template.replace("{name}", firstName(user));
}

export default function Landing({
  user,
  section,
  onSectionChange,
  onSend,
  disabled,
  onAttach,
  isUploading,
  uploadingFileName,
  uploadError,
}) {
  const greeting = useMemo(() => randomGreeting(user), [user]);
  const suggestions = SUGGESTIONS[section] ?? SUGGESTIONS.general;

  return (
    <div className={styles.landing}>
      <SectionSwitch value={section} onChange={onSectionChange} />

      <h2 className={styles.greeting}>
        <SparkleIcon />
        {greeting}
      </h2>

      <div className={styles.inputWrap}>
        <ChatInput
          onSend={onSend}
          disabled={disabled}
          section={section}
          onAttach={onAttach}
          isUploading={isUploading}
          uploadingFileName={uploadingFileName}
          uploadError={uploadError}
        />
      </div>

      <div className={styles.suggestions}>
        {suggestions.map((text) => (
          <button
            key={text}
            type="button"
            className={styles.suggestion}
            onClick={() => onSend(text)}
            disabled={disabled}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
