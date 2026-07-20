# Talk with DB — Setup & Run Guide

## Starting the app

**1. Backend** (from `backend/`):

```bash
cd backend
.venv/bin/python main.py
```

Runs on `http://localhost:8010`. Auto-reloads on code changes.

**2. Frontend** (from `frontend/`), in a separate terminal:

```bash
cd frontend
npm run dev
```

Runs on `http://localhost:5173` — open that in a browser.

That's it — two terminals, two commands. `Ctrl-C` in each to stop.

## First-time setup (already done, for reference)

- Backend: `.venv` already exists with deps installed (`uv sync` if you ever need to redo it)
- Frontend: `npm install` in `frontend/` (already run)
- Backend needs its metadata Postgres reachable (Docker container `nl2sql_meta_db` on port 5434) and `.env` with `DATABASE_URL`/`METADATA_DATABASE_URL` set — both already in place

## Notes

- No saved connection is "active" until you pick one in the app's connection dropdown (activation state doesn't persist across backend restarts — that's existing backend behavior, not something new).
- If you ever see `EADDRINUSE`, something's still bound to the port: `lsof -ti:8010 -sTCP:LISTEN | xargs kill` (swap `5173` for the frontend).
