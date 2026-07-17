# NL2SQL Frontend — Requirements

A simple web UI for the NL2SQL assistant: connect to a database, ask questions in plain English, see the answer. This is a requirements doc, not a build — no frontend code exists yet.

## Tech

- React, plain JavaScript (no TypeScript) — keep the setup light, e.g. Vite + React.
- No state-management library needed yet — local component state / Context is enough for a single chat view.

## Screens / flow

1. **Connection screen/toggle** — no longer blocked, `/connections` exists:
   - A form to save a new connection: name, db type (Postgres/MySQL), and either structured fields (host/port/user/password/dbname) or a single raw connection URL — support both input modes.
   - A **toggle/dropdown listing saved connections** (`GET /connections`) showing which one is currently active. Selecting one calls `POST /connections/{id}/activate` to switch.
   - Only one connection is active at a time — this switches which database `sql_agent` queries, it's not per-conversation.
   - Support deleting a saved connection (`DELETE /connections/{id}`).
   - Never display a saved password back in the UI once submitted — the list endpoint doesn't return it either.
2. **Chat screen** — a message box + send button, scrolling history of user messages and agent replies. Calls `POST /chat`, sending back the `history` array from the previous response each time (see contract below) — the server keeps no session state itself.
3. **Per-message rendering** — each agent reply is one of three shapes, and the UI must handle all three:
   - **Plain answer only** — just render the LLM's natural-language response. This is the default/common case.
   - **Answer + generated SQL** — render the natural-language answer, plus a **collapsed-by-default toggle** ("Show SQL") that reveals the exact SQL that was generated and run. Don't show the SQL box at all if no SQL was generated for that message.
   - **Answer + chart** — render the natural-language answer, plus the chart (from python_agent). Don't reserve chart space if no chart was generated.
4. **Loading state** while waiting on a reply — LLM calls can take a few seconds, don't leave the UI looking frozen.
5. **Error state** if the request fails (network error or non-2xx) — show a readable message, don't swallow it silently.

## API contract (current — will evolve as sql_agent/knowledge_agent/python_agent become real)

```
POST /chat
  request:  { "message": string, "history"?: [{ "role": "user"|"assistant", "content": string }] }
  response: { "reply": string, "routed_to": "sql_agent" | "knowledge_agent" | "python_agent" | "respond", "history": [...] }

POST   /connections                  { "name", "db_type", "host"?, "port"?, "user"?, "password"?, "dbname"?, "url"? } -> { "id", "name", "db_type", "dbname" }
GET    /connections                  -> [{ "id", "name", "db_type", "dbname", "active" }]
POST   /connections/{id}/activate    -> { "id", "name", "db_type", "dbname" }
DELETE /connections/{id}             -> { "deleted": id }
```

Right now `reply` is always a plain string, even when `routed_to` is `sql_agent` — the specialists are stubs, so there's no SQL or chart data in the response yet. Build the message-rendering logic (point 3 above) to key off the presence of fields, not off `routed_to` alone — e.g. only show the SQL toggle when a `sql` field is actually present, only render a chart when a `chart` field is present. Expected future fields, once the backend adds them:

```
response: {
  "reply": string,
  "routed_to": string,
  "sql": string | null,     // present only when sql_agent generated a query
  "chart": object | null    // present only when python_agent generated a chart
}
```

Don't hardcode assumptions beyond what's listed here — confirm the exact `chart` shape with backend once python_agent is real, it isn't decided yet.

## Explicit non-goals right now

- No auth/login
- No multi-conversation history or persistence beyond what `/chat`'s `history` round-trip gives you (client holds it, not the server)
- No concurrent/per-user active connections — activating a connection changes it for everyone hitting this backend, it's not scoped per browser session
