import os
import time

import requests
import streamlit as st

DEFAULT_BACKEND_URL = os.environ.get("NL2SQL_BACKEND_URL", "http://localhost:8010")

st.set_page_config(page_title="NL2SQL · Chat with your database", page_icon="🗄️", layout="wide")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #0f1117 0%, #1a1d2e 100%);
    border-right: 1px solid #2d3250;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3, [data-testid="stSidebar"] p,
[data-testid="stSidebar"] label { color: #e2e8f0 !important; }

.hero-title {
    font-size: 2.2rem;
    font-weight: 700;
    background: linear-gradient(90deg, #818cf8, #67e8f9);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0;
}
.hero-sub { color: #94a3b8; font-size: 1rem; margin: 4px 0 20px; }

.fancy-divider {
    height: 2px;
    background: linear-gradient(90deg, #4f46e5, #7c3aed, #06b6d4);
    border: none; border-radius: 4px; margin: 12px 0 20px;
}

.badge-connected { color: #34d399; font-weight: 600; }
.badge-disconnected { color: #f87171; font-weight: 600; }

.chat-label { font-size: 0.75rem; margin: 2px 4px; }
.chat-label-user { text-align: right; color: #a5b4fc; }
.chat-label-assistant { text-align: left; color: #67e8f9; }

div[class*="st-key-user-msg-"] {
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    border-radius: 18px 18px 4px 18px;
    padding: 10px 18px;
    margin: 2px 0 10px 15%;
    box-shadow: 0 4px 12px rgba(79,70,229,0.35);
}
div[class*="st-key-user-msg-"] p { color: white !important; margin-bottom: 0; }

div[class*="st-key-assistant-msg-"] {
    background: linear-gradient(135deg, #1e2235, #252b42);
    border-radius: 18px 18px 18px 4px;
    padding: 12px 18px;
    margin: 2px 15% 10px 0;
    border: 1px solid #3d4466;
    box-shadow: 0 4px 12px rgba(0,0,0,0.25);
}
div[class*="st-key-assistant-msg-"] p,
div[class*="st-key-assistant-msg-"] li,
div[class*="st-key-assistant-msg-"] td,
div[class*="st-key-assistant-msg-"] th { color: #e2e8f0 !important; }

.stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(79,70,229,0.4) !important;
}

div[data-testid="stMetric"] {
    background: #1a1d2e;
    border: 1px solid #2d3250;
    border-radius: 12px;
    padding: 12px 16px !important;
}
</style>
""",
    unsafe_allow_html=True,
)


def init_state():
    defaults = {
        "backend_url": DEFAULT_BACKEND_URL,
        "history": [],
        "active_connection": None,
        "total_queries": 0,
        "flash": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


def flash(kind: str, message: str):
    st.session_state.flash = (kind, message)


def _format_error(resp: requests.Response) -> str:
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        return resp.text
    if isinstance(detail, list):
        return "; ".join(f"{'.'.join(str(p) for p in e.get('loc', []))}: {e.get('msg')}" for e in detail)
    return str(detail)


def api_get(path: str):
    resp = requests.get(f"{st.session_state.backend_url}{path}", timeout=15)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, payload: dict | None = None, timeout: int = 60):
    resp = requests.post(f"{st.session_state.backend_url}{path}", json=payload, timeout=timeout)
    if not resp.ok:
        raise RuntimeError(_format_error(resp))
    return resp.json()


def api_delete(path: str):
    resp = requests.delete(f"{st.session_state.backend_url}{path}", timeout=15)
    if not resp.ok:
        raise RuntimeError(_format_error(resp))
    return resp.json()


def refresh_connections() -> list[dict]:
    try:
        connections = api_get("/connections")
    except Exception:
        st.session_state.active_connection = None
        return []
    st.session_state.active_connection = next((c for c in connections if c["active"]), None)
    return connections


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗄️ NL2SQL")
    st.markdown("*Natural Language → SQL → Answer*")
    st.markdown('<hr class="fancy-divider">', unsafe_allow_html=True)

    st.markdown("### ⚙️ Backend")
    st.session_state.backend_url = st.text_input(
        "Backend URL", value=st.session_state.backend_url, label_visibility="collapsed"
    )

    st.markdown('<hr class="fancy-divider">', unsafe_allow_html=True)
    st.markdown("### 🗄️ Database connection")
    connections = refresh_connections()

    for conn in connections:
        dot = "🟢" if conn["active"] else "⚪"
        cols = st.columns([3, 1])
        cols[0].write(f"{dot} **{conn['name']}** ({conn['db_type']}/{conn['dbname']})")
        if not conn["active"]:
            if cols[1].button("Use", key=f"activate-{conn['id']}"):
                try:
                    api_post(f"/connections/{conn['id']}/activate", timeout=120)
                    st.session_state.history = []
                    flash("success", f"Switched to '{conn['name']}'")
                    st.rerun()
                except Exception as e:
                    flash("error", str(e))
                    st.rerun()
        else:
            if cols[1].button("✕", key=f"delete-{conn['id']}"):
                try:
                    api_delete(f"/connections/{conn['id']}")
                    st.session_state.history = []
                    flash("success", f"Removed '{conn['name']}'")
                    st.rerun()
                except Exception as e:
                    flash("error", str(e))
                    st.rerun()

    if st.session_state.active_connection:
        c = st.session_state.active_connection
        st.markdown(
            f'<span class="badge-connected">● Connected to `{c["name"]}`</span>', unsafe_allow_html=True
        )
    else:
        st.markdown('<span class="badge-disconnected">● Not connected</span>', unsafe_allow_html=True)

    with st.expander("➕ Add a connection", expanded=not connections):
        mode = st.radio("Connect via", ["Fields", "URL"], horizontal=True, key="conn_mode")

        with st.form("connect_form", clear_on_submit=True):
            name = st.text_input("Name", key="conn_name")
            db_type = st.selectbox("Database type", ["postgres", "mysql"], key="conn_db_type")

            host = port = user = password = dbname = url = None
            if mode == "Fields":
                host = st.text_input("Host", key="conn_host")
                port = st.number_input(
                    "Port", value=5432 if db_type == "postgres" else 3306, step=1, key="conn_port"
                )
                user = st.text_input("User", key="conn_user")
                password = st.text_input("Password", type="password", key="conn_password")
                dbname = st.text_input("Database name", key="conn_dbname")
            else:
                url = st.text_input(
                    "Connection URL",
                    placeholder="postgresql://user:pass@host:port/dbname",
                    key="conn_url",
                )

            if st.form_submit_button("🔌 Connect", key="conn_submit"):
                payload = {"name": name, "db_type": db_type}
                if mode == "Fields":
                    payload.update(
                        {"host": host, "port": int(port), "user": user, "password": password, "dbname": dbname}
                    )
                else:
                    payload["url"] = url
                try:
                    api_post("/connections", payload, timeout=120)
                    st.session_state.history = []
                    flash("success", f"✅ Connected to '{name}'")
                    st.rerun()
                except Exception as e:
                    flash("error", str(e))
                    st.rerun()

    st.markdown('<hr class="fancy-divider">', unsafe_allow_html=True)
    st.markdown("### 🔀 Node → Model")
    st.caption("Which model handles each step, by default.")
    for node, model in [("supervisor (route/evaluate)", "llama-3.3-70b-versatile"), ("sql_agent", "openai/gpt-oss-120b")]:
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;padding:3px 0;'
            f'border-bottom:1px solid #2d3250;font-size:0.8rem;">'
            f'<span style="color:#94a3b8;">{node}</span>'
            f'<span style="color:#67e8f9;font-weight:600;">{model}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<hr class="fancy-divider">', unsafe_allow_html=True)
    st.markdown("### 📊 Session")
    col1, col2 = st.columns(2)
    col1.metric("Queries", st.session_state.total_queries)
    col2.metric("Messages", len(st.session_state.history))
    latencies = [m["latency"] for m in st.session_state.history if m.get("latency")]
    if latencies:
        st.caption(f"Avg response time: {round(sum(latencies) / len(latencies), 2)}s")

    if st.session_state.history and st.button("🆕 New chat", use_container_width=True):
        st.session_state.history = []
        st.session_state.total_queries = 0
        st.rerun()


# ─────────────────────────────────────────────
# MAIN AREA
# ─────────────────────────────────────────────
if st.session_state.flash:
    kind, message = st.session_state.flash
    getattr(st, kind)(message)
    st.session_state.flash = None

st.markdown('<div class="hero-title">🗄️ NL2SQL — Ask Your Database</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Type a question in plain English. The agent writes SQL, runs it '
    'read-only, and answers in plain language.</div>',
    unsafe_allow_html=True,
)
st.markdown('<hr class="fancy-divider">', unsafe_allow_html=True)

if st.session_state.active_connection is None:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("**Step 1**\n\n🗄️ Connect a database\n\nAdd credentials in the sidebar")
    with c2:
        st.info("**Step 2**\n\n💬 Ask anything\n\nType a question in plain English")
    with c3:
        st.info("**Step 3**\n\n✨ Get an answer\n\nRead-only — never modifies your data")
else:
    conn = st.session_state.active_connection
    st.caption(f"Connected to **{conn['name']}** ({conn['db_type']} / {conn['dbname']})")

    with st.expander("📋 View schema"):
        schema_type = st.radio(
            "Representation",
            ["plain", "graph"],
            format_func=lambda x: "Plain (flat text — what SQL generation actually uses today)"
            if x == "plain"
            else "Graph (experimental — tables as nodes, FKs as edges)",
            horizontal=True,
            key="schema_type_choice",
        )

        cache_key = (conn["id"], schema_type)
        if st.session_state.get("schema_cache_key") != cache_key:
            try:
                spinner_msg = "Building schema graph (first time embeds every table)..." if schema_type == "graph" else "Loading schema..."
                with st.spinner(spinner_msg):
                    resp = api_get(f"/connections/schema?schema_type={schema_type}")
                st.session_state.schema_cache_key = cache_key
                st.session_state.schema_text = resp["schema_text"]
            except Exception as e:
                st.session_state.schema_cache_key = None
                st.error(f"Could not load schema: {e}")

        if st.session_state.get("schema_cache_key") == cache_key and st.session_state.get("schema_text"):
            st.code(st.session_state.schema_text, language=None)

    for i, msg in enumerate(st.session_state.history):
        role = msg["role"]
        label = "You" if role == "user" else "🧠 Assistant"
        with st.container(key=f"{role}-msg-{i}"):
            st.markdown(f'<div class="chat-label chat-label-{role}">{label}</div>', unsafe_allow_html=True)
            st.markdown(msg["content"])
            if msg.get("routed_to"):
                st.caption(f"routed via `{msg['routed_to']}`")

    if not st.session_state.history:
        st.markdown("#### 💡 Try asking…")
        suggestions = [
            "What tables are in this database?",
            "How many rows are in each table?",
            "Show me the 5 most recent records",
        ]
        cols = st.columns(len(suggestions))
        for col, q in zip(cols, suggestions):
            if col.button(q, use_container_width=True, key=f"sugg_{q}"):
                st.session_state["_pending_question"] = q
                st.rerun()

    pending = st.session_state.pop("_pending_question", None)
    prompt = st.chat_input("Ask a question about your data...")
    prompt = prompt or pending

    if prompt:
        payload_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.history]
        st.session_state.history.append({"role": "user", "content": prompt})
        st.session_state.total_queries += 1

        with st.spinner("Thinking..."):
            t0 = time.time()
            try:
                result = api_post("/chat", {"message": prompt, "history": payload_history}, timeout=120)
                elapsed = round(time.time() - t0, 2)
                st.session_state.history = result["history"]
                if st.session_state.history:
                    st.session_state.history[-1]["routed_to"] = result["routed_to"]
                    st.session_state.history[-1]["latency"] = elapsed
            except Exception as e:
                flash("error", f"Request failed: {e}")
        st.rerun()

st.markdown(
    '<div style="text-align:center; color:#475569; font-size:0.8rem; padding-top:24px;">'
    "NL2SQL — read-only, multi-agent, powered by Groq</div>",
    unsafe_allow_html=True,
)
