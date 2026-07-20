// The LLM's replies use light markdown emphasis (**bold**) — render just that, not a full
// markdown parser, since it's the only formatting the agents actually produce today.
const BOLD_PATTERN = /\*\*(.+?)\*\*/g;

export function formatInlineText(text) {
  const parts = [];
  let lastIndex = 0;
  let match;

  while ((match = BOLD_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    parts.push(<strong key={match.index}>{match[1]}</strong>);
    lastIndex = BOLD_PATTERN.lastIndex;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));

  return parts;
}
