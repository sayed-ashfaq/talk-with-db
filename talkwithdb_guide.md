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

## Troubleshooting

**`ERROR: [Errno 98] Address already in use`**

This means something is already listening on that port — usually a backend (or frontend) you (or an assistant session) started earlier and never stopped, not a real crash. Find and kill it, then retry:

```bash
# backend (port 8010)
lsof -ti:8010 -sTCP:LISTEN | xargs kill
# frontend (port 5173)
lsof -ti:5173 -sTCP:LISTEN | xargs kill
```

Then re-run `.venv/bin/python main.py` (or `npm run dev`). If `lsof` prints nothing but the error persists, the process may be owned by another user or a container — check `ps aux | grep main.py` (or `| grep vite`) for the PID.

**Backend logs `OPTIONS /connections HTTP/1.1" 400 Bad Request`, and the frontend can't load anything**

This is a CORS preflight rejection, not a backend crash. Cause: if port 5173 is already taken (see above — usually a leftover `npm run dev` nobody killed), Vite silently starts on the next free port (5174, 5175, ...) instead of failing loudly. The backend's CORS config now allows any `localhost`/`127.0.0.1` port, so this shouldn't happen anymore — but if you ever see it:

1. Check what port Vite actually printed on startup (`➜ Local: http://localhost:XXXX/`) and make sure that's the URL you have open in the browser.
2. If you want it back on the standard 5173, find and kill whatever's squatting on it (`lsof -ti:5173 -sTCP:LISTEN | xargs kill`) and restart `npm run dev`.
