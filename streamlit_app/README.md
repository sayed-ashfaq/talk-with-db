# NL2SQL Streamlit Tester

A dev UI for manually testing the backend's split Database/General agents — not the real product
frontend (that's the React app in `../frontend`). Two pages, one per top-level agent, matching the
backend's `section` split (`app/agents/database_agent`, `app/agents/general_agent`).

Everything here goes through the real HTTP API (`api_client.py`) — no backend code is imported
directly, including auth: `POST /auth/login`/`/auth/signup` against a fixed dev account, so there's
no login screen but the same session-cookie auth the real frontend uses is still exercised.

## Run

Backend must already be running (`cd ../backend && uv run python main.py`, or however you normally
start it). Then:

```bash
cd streamlit_app
uv run streamlit run app.py --server.port 8510
```

Port 8501 (Streamlit's default) is often taken by an unrelated project on this machine — 8510 avoids
the clash. Open the printed local URL.

Config, all via env var or the sidebar "Backend URL" field at runtime:

| Env var | Default | What |
|---|---|---|
| `NL2SQL_BACKEND_URL` | `http://localhost:8080` | where the API is |
| `STREAMLIT_DEV_EMAIL` | `streamlit-tester@nl2sql-tester.internal` | dev account this tool logs in/signs up as |
| `STREAMLIT_DEV_PASSWORD` | `streamlit-dev-only-12345` | its password — local dev only, not a real secret |

## What it does

- **Database page** — sidebar: save a connection (structured fields or a raw URL, `POST
  /connections`), see saved connections with which is active, switch (`Use`) or remove (`✕`) one; a
  list of this section's past chats (`GET /chats`, filtered client-side on `section`). Main area: a
  normal chat (`st.chat_message`/`st.chat_input`) against `POST /chat` with `section: "database"`.
  Each assistant reply shows which specialist handled it (`routed_to`), a collapsed SQL block when
  one ran, a Plotly chart when the backend returned one (`charts.py` renders the same `ChartSpec` the
  real frontend will), and the underlying rows in an expander.
- **General page** — same chat mechanics, `section: "general"`, no connection sidebar. Chit-chat and
  drafting help today; renders whatever `sql`/`data` a turn comes back with, so it needs no changes
  once RAG/CSV analytics land as specialists there.
- Both pages persist chats server-side (`chat_id`, same as the real frontend) rather than resending a
  client-held history — reopening a past chat re-fetches it via `GET /chats/{id}`.

## Note

The active DB connection is per-signed-in-user on the backend (not global) — since this tool always
signs in as the same fixed dev account, multiple browser tabs pointed at the same backend share one
active connection and chat list, same as two tabs of any normal logged-in app would.
