# NL2SQL

Ask a database questions in plain English. Connect to Postgres or MySQL, ask a question, get a natural-language answer back.

## Status: Planning

We're designing this piece by piece — agree on a step, build it, test it, then move to the next. Nothing below is final until we've both signed off on it.

## Progress log

- [x] Main agent (supervisor) — routes each message to `sql_agent`, `knowledge_agent`, `python_agent`, or answers directly. Built as a LangGraph graph, exposed via `POST /chat`. Tested against all four routes.
- [x] `sql_agent`, `knowledge_agent`, `python_agent` exist as **buffer/stub nodes** — wired into the graph so routing is provable end-to-end, but they don't do real work yet.
- [ ] `sql_agent` for real — schema introspection + SQL generation + safe execution. **Next up.**
- [ ] `knowledge_agent` for real — Tavily + optional DB access.
- [ ] `python_agent` for real — matplotlib chart generation.
- [ ] Synthesizer step and final-answer guardrail (currently only exist on paper in the pipeline diagram below).

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

Folder structure for `app/` (router, agents, prompts, etc.) — to be finalized in a follow-up pass.
