# How to Run

This app has three moving parts in local development:

- `backend/`: FastAPI API on `http://localhost:8080`
- `streamlit_app/`: lightweight dev UI on port `8510`
- metadata Postgres: the app's own local database for users, sessions, chats, and saved connection
  credentials

The metadata Postgres is separate from the database you want to ask questions about. Target
databases are added later in the UI as saved Postgres/MySQL connections.

## Prerequisites

- Python 3.11+
- `uv`
- Docker, or a locally installed Postgres server
- A Groq API key
- A Tavily API key (optional — only needed for the General agent's web search specialist; without
  it, web search questions get a plain "not configured" answer instead of an error)

## First-Time Setup

### 1. Start the metadata Postgres

The General agent's document search (RAG) stores embeddings with `pgvector`, so the metadata
Postgres needs that extension available — plain `postgres:16` does not include it. Docker is the
simplest local setup:

```bash
docker run --name nl2sql-meta-db \
  -e POSTGRES_USER=nl2sql \
  -e POSTGRES_PASSWORD=nl2sql_dev_password \
  -e POSTGRES_DB=nl2sql_meta \
  -p 5435:5432 \
  -d pgvector/pgvector:pg16
```

If the container already exists later, start it with:

```bash
docker start nl2sql-meta-db
```

Already have a `postgres:16` container running from before this feature existed? Install the
extension package into it directly rather than recreating the container (this keeps your existing
data volume):

```bash
docker exec <container> apt-get update
docker exec <container> apt-get install -y postgresql-16-pgvector
```

If that container has no outbound network access (some sandboxed/offline environments), download
the `.deb` on a machine that does and `docker cp` it in instead:

```bash
docker run --rm -v /tmp/pgvector_debs:/out postgres:16 bash -c \
  "apt-get update -qq && cd /out && apt-get download postgresql-16-pgvector"
docker cp /tmp/pgvector_debs/postgresql-16-pgvector_*.deb <container>:/tmp/pgvector.deb
docker exec <container> dpkg -i /tmp/pgvector.deb
```

Either way, the extension itself is created by the app's own migration (`alembic upgrade head`,
step 3 below) — installing the package just makes `CREATE EXTENSION vector` available to run.

If you prefer an existing local Postgres, create the same user/database yourself (it needs
`pgvector` installed the same way — see your distro's Postgres extension packages):

```sql
CREATE USER nl2sql WITH PASSWORD 'nl2sql_dev_password';
CREATE DATABASE nl2sql_meta OWNER nl2sql;
```

### 2. Create `backend/.env`

From `backend/`, create a `.env` file like this:

```bash
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here

METADATA_DATABASE_URL=postgresql://nl2sql:nl2sql_dev_password@localhost:5435/nl2sql_meta
CREDENTIALS_ENCRYPTION_KEY=replace_with_fernet_key
SESSION_SECRET_KEY=replace_with_random_secret

FRONTEND_URL=http://localhost:5175
COOKIE_SECURE=false

# optional — the General agent's web search specialist returns a graceful "not configured"
# answer instead of results when this is unset
TAVILY_API_KEY=your_tavily_api_key_here
```

Generate the two secrets with:

```bash
cd backend
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Use the Fernet output for `CREDENTIALS_ENCRYPTION_KEY` and the random token for
`SESSION_SECRET_KEY`.

`METADATA_DATABASE_URL` can use the normal `postgresql://...` form. The backend rewrites it to the
async driver internally where needed.

### 3. Run metadata migrations

```bash
cd backend
uv run alembic upgrade head
```

This creates the app-owned tables in `nl2sql_meta`, including users, sessions, chats, and saved
database connections.

### 4. Start the backend

```bash
cd backend
uv run python main.py
```

The backend runs at `http://localhost:8080`.

### 5. Start the Streamlit dev UI

In a second terminal:

```bash
cd streamlit_app
uv run streamlit run app.py --server.port 8510
```

Open the printed Streamlit URL. The sidebar has two pages: Database and General.

## Connecting a Target Postgres Database

After the backend and Streamlit UI are running:

1. Open the Database page.
2. In the sidebar, expand "Add a connection".
3. Choose Postgres.
4. Enter either fields:
   - host
   - port, usually `5432`
   - user
   - password
   - database name
5. Or enter a full URL:

```text
postgresql://user:password@host:5432/dbname
```

For safety, use read-only credentials for target databases. The app also blocks non-SELECT SQL in
code, but database-level read-only permissions are still the best guardrail.

If the target database is on the host machine and the backend is running directly with
`uv run python main.py`, use `localhost` as the host. If the target database is another Docker
container, use the host/port that is reachable from the backend process.

## Every Time After Setup

Terminal 1:

```bash
docker start nl2sql-meta-db
cd backend
uv run python main.py
```

Terminal 2:

```bash
cd streamlit_app
uv run streamlit run app.py --server.port 8510
```

That's it. This project's backend always runs on `8080`. Port `8010`, if you see it in use on this
machine, belongs to an unrelated app.

## Optional React Frontend

The React app is in `frontend/`, but the Streamlit app is the quickest local dev UI.

To run React instead:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The Vite dev server starts at `http://localhost:5175` (fixed via `strictPort` in `vite.config.js`).

## If Something Breaks

- Backend cannot connect to metadata Postgres: check the Docker container is running and
  `METADATA_DATABASE_URL` points at the right port, usually `5435` for the Docker command above.
- Alembic cannot import settings: make sure `backend/.env` exists before running migrations.
- Groq 404s on a chat request: a model may have been deprecated on Groq's side. Check the model list
  and update the relevant `*_MODEL` value in `backend/.env` or default in
  `backend/app/core/config.py`.



## Credentials

Name: sayed
user_name: random@rand.in
password: rand@1234