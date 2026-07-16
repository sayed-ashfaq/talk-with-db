# NL2SQL

Ask a database questions in plain English. Connect to Postgres or MySQL, ask a question, get a natural-language answer back.

## Status: Planning

We're designing this piece by piece — agree on a step, build it, test it, then move to the next. Nothing below is final until we've both signed off on it.

## Progress log

- [x] Main agent (supervisor) — routes each message to `sql_agent`, `knowledge_agent`, `python_agent`, or answers directly. Built as a LangGraph graph, exposed via `POST /chat`. Tested against all four routes.
- [x] `sql_agent`, `knowledge_agent`, `python_agent` exist as **buffer/stub nodes** — wired into the graph so routing is provable end-to-end, but they don't do real work yet.
- [x] Folder structure matches the agreed layout below (`core/`, one-folder-per-agent). Minimal logging (`app/core/logging.py`) and a base exception class (`app/core/exceptions.py`, `NL2SQLError`) are wired in — `main.py` has a handler for it, `chat.py` logs each request's message and route. More exceptions get added as each agent actually needs them, not ahead of time.
- [x] Logging reformatted to match the reference format (`asctime - name - levelname - processName - message`), writing to both console and a daily-rotating `logs/nl2sql.log` (30-day retention).
- [x] Main agent's real logic is built out — not just a router anymore:
  - `AgentState` (`agents/main_agent/state.py`) carries `chat_history` (clean user/assistant turns only), the current `question`, the LLM-refined `refined_query` handed to whichever specialist runs, `next` (routing decision), `agent_output` (the specialist's raw response), `attempts` (loop guard), and `final_answer`.
  - `supervisor_node` is one recurring node, called again after every specialist responds: it decides which specialist to use (or that no specialist is needed), refines the query for it (resolving pronouns/context via `chat_history`), and — once a specialist has answered — judges whether that answer actually resolves the question. If yes, it's returned as-is; if no, it re-routes (same or a different specialist) up to `MAX_ATTEMPTS` (3), then gives up gracefully with the last response.
  - `chat_history` persistence is **stateless**: the server doesn't keep sessions. `POST /chat` accepts an optional `history` array and returns the updated one; the caller resends it next turn. (Revisit a server-side session/checkpointer later if this gets unwieldy.)
  - Tested live: direct chit-chat, a DB-shaped question looping against the `sql_agent` stub, and a two-turn conversation where "how many rows does **it** have?" correctly resolved to the `orders` table mentioned in the prior turn.
- [x] `sql_agent` is real:
  - `agents/sql_agent/sql.py` cleans model output before anything touches the database: extract from fences → sanitize unicode → format via sqlparse → extract statement (rejects multi-statement output, doesn't just truncate to the first) → transpile via sqlglot for the target dialect (pretty-printed, not squashed to one line) → sanitize again → block destructive keywords (word-boundary match + a SELECT/WITH allow-list, not naive substring matching).
  - `agents/sql_agent/agents.py` is an internal subgraph: generate → execute → (on error) fix → execute, up to 3 fix attempts, then synthesize in a business-analyst tone (one-liner for a single value, table + a called-out insight otherwise) or give up gracefully.
  - Every step logs its own latency (`Routing decision`, `SQL generation`, `SQL execution`, `SQL fix attempt`, `Response synthesis`, `Total query completion`) plus the actual content at each stage (`Generated SQL query`, `Formatted Fixed SQL query`, `Extracted SQL query`, `Transformed SQL query SQLglot`, `Final answer`) — all multi-line/pretty, matching the reference log format.
  - `run_query` sets a 10s statement timeout (Postgres `statement_timeout` / MySQL `MAX_EXECUTION_TIME`) before running anything.
  - **Tested live against a real production database** (read-only credentials) — a single-value question and a multi-CTE failure-rate-by-station question both succeeded on the first attempt, no fix-loop needed.
- [x] Saved, switchable DB connections — no longer just one in-memory connection:
  - Credentials persist in their own dedicated Postgres (a separate local `nl2sql_meta_db` container/database, not the target DB, not SQLite) via `app/agents/sql_agent/db.py`'s `saved_connections` table, encrypted at rest (`app/core/crypto.py`, Fernet — key from `CREDENTIALS_ENCRYPTION_KEY` in `.env`). `METADATA_DATABASE_URL` in `.env` points at this metadata store.
  - `app/router/connections.py`: `POST /connections` (save+test+activate — structured host/port/user/password/dbname **or** a raw `url`), `GET /connections` (list, no secrets returned), `POST /connections/{id}/activate` (switch), `DELETE /connections/{id}`.
  - Still single-active-connection at a time (not per-session) — this is a switchable toggle, not concurrent multi-tenancy.
  - Found and fixed two real bugs during testing: (1) SQLAlchemy's `str(url)` masks the password as `***` — needed `render_as_string(hide_password=False)` instead, or the raw-`url` path would silently connect with a literal `***` password; (2) saving a duplicate connection name 500'd with a raw `IntegrityError` traceback — now a clean error message.
- [ ] `knowledge_agent` for real — Tavily + optional DB access. **Next up.**
- [ ] `python_agent` for real — matplotlib chart generation.

## The pipeline

```
User connects to Postgres or MySQL
        |
        v
User asks a question in natural language
        |
        v
Main Agent  -- reads the question, decides it needs the database, hands off to the SQL Agent
        |
        v
SQL Agent   -- gets the schema (fetched via python) + dialect-specific context (Postgres vs MySQL)
               + rules, all as a system prompt --> writes a SQL query
        |
        v
Clean + Execute -- python strips/validates the generated SQL, runs it against the DB, collects results
        |
        v
Synthesizer -- checks the results actually answer the original question, turns them into natural language
        |
        v
Main Agent  -- decides whether to hand that answer back as-is, then responds to the user
```

## Design principles

- **Build incrementally.** One component at a time, tested before moving on.
- **No OpenAI/Anthropic keys.** LLM calls go through Groq's API, with room for local models later.
- **Orchestration via LangGraph, LLM plumbing via LangChain.**
- **Dialect-aware.** Postgres and MySQL get different schema context and rules, not one generic prompt.

## Graph design (LangGraph state machine)

One shared state carries: `question`, `db_dialect`, `schema`, `generated_sql`, `execution_result` / `error`, `synthesized_answer`, `final_answer`.

```
Main Agent (router)  -- is this a DB question, or chit-chat/out-of-scope?
        | (DB question)
        v
SQL Agent  -- schema + dialect rules + question --> SQL
        |
        v
Clean + Execute (plain python)  -- strip fences, reject anything non-SELECT, run it
        |
        |<-- on error, loop back to SQL Agent with the error (max ~2 retries)
        v
Synthesizer  -- results + question --> checks it actually answers it, writes NL answer
        |
        v
Main Agent (final check)  -- guardrail: withhold/reframe if the answer doesn't hold up
        |
        v
Response to user
```

Key calls locked in so far:
- **Full schema first.** Dump the whole schema for the connected DB into the SQL Agent's context. Only add relevant-table retrieval later if a real schema is too large for context — don't build retrieval before we know we need it.
- **Read-only, twice.** Reject any non-SELECT statement in the Clean + Execute step, independent of whatever DB-level permissions the connection uses. Defense in depth, not either/or.

## Open questions (tracked as we go)

- Exact retry cap / backoff for the SQL self-correction loop
- How much schema to hand the SQL Agent as schemas grow (see "full schema first" above)
- Which specific Groq models per agent (see below — proposal, not locked)

## Tech stack

| Layer | Choice |
|---|---|
| LLM provider | Groq API only for now — local models come later, behind the same interface |
| Agent orchestration | LangGraph |
| LLM framework | LangChain |
| Database | Postgres, MySQL |
| API layer | FastAPI, from the start |
| Package manager | uv (based on current `pyproject.toml` setup) |

**Model per agent** (different models per node, not one everywhere) — locked in, set via env in `app/config.py`:
- Main Agent (routing + chit-chat) — `llama-3.3-70b-versatile`.
- SQL Agent (generation) — `openai/gpt-oss-120b`.
- Knowledge Agent, Python Agent, Synthesizer — not assigned yet, will pick when each is actually built.

## Multi-agent shape

The main agent is a **supervisor** over specialist sub-agents, not a single fixed SQL pipeline. It looks at the message and routes to exactly one of:

- `sql_agent` — NL2SQL against the connected Postgres/MySQL database. **Current build priority.**
- `knowledge_agent` — web search (Tavily) and/or the connected database for lookups that aren't a SQL query. Buffer for now.
- `python_agent` — turns data into charts (matplotlib). Buffer for now.
- direct response — greetings, meta questions, anything needing no specialist.

More specialists (e.g. a research agent) can be added later as additional routes without changing this shape. The "pipeline" diagram above describes what happens *inside* `sql_agent` once it's built for real — that's still the plan for that node specifically.

## Project layout

```
backend/
└── app/
    ├── core/
    │   ├── config.py           # settings/env
    │   ├── llm.py               # Groq client factory, one model per agent
    │   ├── logging.py           # one logger setup, used everywhere, + log_duration() timing helper
    │   ├── exceptions.py        # exception hierarchy + FastAPI error handlers
    │   └── crypto.py            # Fernet encrypt/decrypt for saved DB credentials
    ├── router/
    │   ├── chat.py               # POST /chat
    │   └── connections.py        # POST/GET /connections, activate, delete
    ├── prompts/
    │   ├── main_agent.py
    │   └── sql_agent.py          # generation / fix / synthesizer prompts, one file
    └── agents/
        ├── main_agent/
        │   ├── __init__.py
        │   ├── state.py           # top-level graph state (messages, next) — shared across all agents
        │   └── main.py             # supervisor + direct-answer nodes, AND connects sql_agent/knowledge_agent/python_agent into one graph
        ├── sql_agent/
        │   ├── __init__.py
        │   ├── state.py            # sql_agent's own internal state — attempt count, generated_sql, last error, etc.
        │   ├── agents.py            # generate → fix (x3) → synthesize, merged, incl. the retry loop
        │   ├── db.py                # credentials, connection, schema introspection, run_query()
        │   └── sql.py               # clean generated SQL, safety check, call db.run_query(), shape for synthesizer
        ├── knowledge_agent/
        │   ├── __init__.py
        │   └── agent.py             # stub node — folder now for consistency, minimal content until built for real
        └── python_agent/
            ├── __init__.py
            └── agent.py             # stub node, same story
```

Notes:
- **One agent = one folder.** Each agent owns its own state — nothing about sql_agent's retry loop leaks into the shared top-level state, and vice versa.
- **`main_agent` is the connector.** `main_agent/main.py` is the one place that imports the other agents' node functions and wires the full graph together — the "main.py for agents." It also holds the router (LLM picks a route) and the direct-answer node (chit-chat, no specialist needed).
- **Single DB connection for now**, not multi-session — `sql_agent/db.py` holds simple state, not a per-user registry.
- **`db.py` vs `sql.py`:** `db.py` is the generic DB toolkit (connect, introspect schema, run a query, return rows). `sql.py` is the NL2SQL-specific orchestration around a generated query (clean it, safety-check it, call `db.py`, shape the result for the synthesizer). Avoids duplicating execution logic.

Frontend requirements (simple React + JS UI — chat, SQL toggle, charts) are tracked separately in `frontend/REQUIREMENTS.md`.