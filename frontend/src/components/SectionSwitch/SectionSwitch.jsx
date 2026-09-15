import styles from "./SectionSwitch.module.css";

const OPTIONS = [
  { value: "general", label: "Chat" },
  { value: "database", label: "Database" },
];

export default function SectionSwitch({ value, onChange }) {
  const activeIndex = Math.max(0, OPTIONS.findIndex((o) => o.value === value));

  return (
    <div className={styles.switch} role="radiogroup" aria-label="Conversation type">
      <div className={styles.thumb} style={{ transform: `translateX(${activeIndex * 100}%)` }} />
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          className={`${styles.option} ${option.value === value ? styles.active : ""}`}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
