import { Suspense, lazy } from "react";
import SqlToggle from "./SqlToggle";
import Markdown from "./Markdown";
import { DocumentIcon } from "../common/icons";
import styles from "./Message.module.css";

// Split out because the charting library is heavy and most turns never draw one — a greeting, a
// web lookup, or any answer that is a single number. Loaded the first time a chart actually
// appears, which is a network round trip the user is already waiting through.
const ChartCard = lazy(() => import("../Chart/ChartCard"));

// What actually answered the question — worth a small label so "this came from your documents"
// reads differently than "this came from the web" or a plain reply. "respond" (the common,
// no-specialist case) and anything unrecognized get no badge at all.
const ROUTE_LABELS = {
  sql_agent: "SQL query",
  analytics_agent: "Analytics",
  rag_agent: "Your documents",
  csv_agent: "CSV data",
  websearch_agent: "Web search",
  visualizer: "Chart",
};

function attachmentSummary(message) {
  if (message.fileType === "pdf") {
    const count = message.chunkCount ?? 0;
    return `${count} chunk${count === 1 ? "" : "s"}`;
  }
  const count = message.rowCount ?? 0;
  let summary = `${count.toLocaleString()} row${count === 1 ? "" : "s"}`;
  if (message.truncated) summary += " (truncated)";
  if (message.replacedFilename) summary += ` — replaced ${message.replacedFilename}`;
  return summary;
}

export default function Message({ message }) {
  if (message.kind === "attachment") {
    return (
      <div className={styles.row}>
        <div className={styles.attachmentChip}>
          <DocumentIcon />
          <span className={styles.attachmentName}>{message.filename}</span>
          <span className={styles.attachmentMeta}>{attachmentSummary(message)}</span>
        </div>
      </div>
    );
  }

  const isUser = message.role === "user";
  const routeLabel = !isUser ? ROUTE_LABELS[message.routedTo] : null;

  return (
    <div className={`${styles.row} ${isUser ? styles.rowUser : ""}`}>
      <div className={`${styles.bubble} ${isUser ? styles.bubbleUser : styles.bubbleAssistant}`}>
        {routeLabel && <span className={styles.routeBadge}>{routeLabel}</span>}
        {isUser ? <p className={styles.text}>{message.content}</p> : <Markdown>{message.content}</Markdown>}
        {message.data?.chart && (
          <Suspense fallback={null}>
            <ChartCard data={message.data} />
          </Suspense>
        )}
        {message.sql != null && <SqlToggle sql={message.sql} />}
      </div>
    </div>
  );
}
