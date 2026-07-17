# NL2SQL Streamlit Tester

A quick Streamlit UI for manually testing the backend — not the real product frontend (that's planned as React in `../frontend`, see `frontend/REQUIREMENTS.md`). This is a dev tool.

## Run

Backend must already be running (see `../backend/dev-notes/testing-the-api.md`). Then:

```bash
cd streamlit_app
uv run streamlit run app.py --server.port 8510
```

Port 8501 (Streamlit's default) is often taken by an unrelated project on this machine — 8510 is used above to avoid the clash; pick any free port.

Open the printed local URL. If the backend isn't at `http://localhost:8010`, either set `NL2SQL_BACKEND_URL` before launching or change the "Backend URL" field in the sidebar at runtime.

## What it does

- **Sidebar** — save a new DB connection (structured fields or a raw connection URL, matching `POST /connections`), see all saved connections with which one is active, switch (`Use`) or remove (`✕`) one.
- **Main area** — gated: shows a prompt to connect until a connection is active, then a normal chat interface (`st.chat_message`/`st.chat_input`) wired to `POST /chat`. Each reply is tagged with which agent handled it (`routed_to`) — useful for debugging routing decisions.
- History round-trips through the backend exactly as the API expects (stateless server, client resends `history` each turn) — this UI is also a reference for how a real frontend should call `/chat`.

## Note

The active connection is backend-global, not per-browser-session (matches how the backend actually works — see `frontend/REQUIREMENTS.md`'s non-goals). If you and someone else both point a UI at the same backend, switching connections affects both.
