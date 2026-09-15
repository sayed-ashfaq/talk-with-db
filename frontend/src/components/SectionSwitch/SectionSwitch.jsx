import styles from "./SectionSwitch.module.css";

const OPTIONS = [
  { value: "general", label: "Chat" },
  { value: "database", label: "Database" },
];

// `compact` fills its container (sidebar width) instead of sizing to its own content (the
// centered landing placement) — same component, two widths.
export default function SectionSwitch({ value, onChange, compact = false }) {
  const activeIndex = Math.max(0, OPTIONS.findIndex((o) => o.value === value));

  return (
    <div
      className={`${styles.switch} ${compact ? styles.compact : ""}`}
      role="radiogroup"
      aria-label="Conversation type"
    >
      <div className={styles.thumb} style={{ transform: `translateX(${activeIndex * 100}%)` }} />
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          className={`${styles.option} ${compact ? styles.optionCompact : ""} ${
            option.value === value ? styles.active : ""
          }`}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
