# How to Run

## Every time

**Terminal 1 — backend**
```bash
cd backend
uv run python main.py
```
Runs at http://localhost:8080 (already set up — `.env`, metadata Postgres, migrations are all
done from earlier).

**Terminal 2 — streamlit**
```bash
cd streamlit_app
uv run streamlit run app.py --server.port 8510
```
Open the printed URL. Two pages in the sidebar nav — Database and General.

That's it. This project's backend always runs on 8080 — port 8010, if you see it in use on this
machine, belongs to an unrelated app and has nothing to do with this one.

## First-time setup (already done — for reference only)

- `backend/.env` needs `GROQ_API_KEY`, `LLM_PROVIDER=groq`, `METADATA_DATABASE_URL`,
  `CREDENTIALS_ENCRYPTION_KEY`, `SESSION_SECRET_KEY`.
- `cd backend && uv run alembic upgrade head` — once, against that metadata database.

## If something breaks

- **Groq 404s on a chat request** — a model got deprecated on Groq's side. Check
  `curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"` and update
  the relevant `*_model` in `backend/app/core/config.py` if it's not in that list.
