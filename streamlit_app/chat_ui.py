"""Chat rendering shared by both pages — the Database and General agents return the same message
shape from POST /chat (reply, routed_to, sql, data), so one renderer serves both; a "general" chat's
`sql`/`data` are simply always None today (no specialists exist for it yet, see the backend's Phase 1
plan), and this code already handles that without special-casing it.
"""

import streamlit as st

import charts
from api_client import ApiError, get_chat, list_chats, send_message


def _messages_from_detail(detail: dict) -> list[dict]:
    return [
        {
            "role": m["role"],
            "content": m["content"],
            "sql": m.get("sql"),
            "routed_to": m.get("routed_to"),
            "data": m.get("data"),
        }
        for m in detail["messages"]
    ]


def render_sidebar_chats(section: str, key_prefix: str) -> None:
    st.subheader("Chats")
    if st.button("+ New chat", width="stretch", key=f"{key_prefix}-new-chat"):
        st.session_state[f"{key_prefix}_chat_id"] = None
        st.session_state[f"{key_prefix}_messages"] = []
        st.rerun()

    try:
        chats = [c for c in list_chats() if c.get("section") == section]
    except ApiError as e:
        st.error(f"Could not load chats: {e}")
        return

    active_id = st.session_state.get(f"{key_prefix}_chat_id")
    for c in chats:
        label = ("● " if c["id"] == active_id else "") + (c["title"] or "New chat")
        if st.button(label, key=f"{key_prefix}-chat-{c['id']}", width="stretch"):
            st.session_state[f"{key_prefix}_chat_id"] = c["id"]
            st.session_state[f"{key_prefix}_messages"] = _messages_from_detail(get_chat(c["id"]))
            st.rerun()


def _render_assistant_extras(msg: dict) -> None:
    if msg.get("routed_to"):
        st.caption(f"routed via `{msg['routed_to']}`")
    if msg.get("sql"):
        with st.expander("Show SQL"):
            st.code(msg["sql"], language="sql")

    data = msg.get("data")
    if not data:
        return
    if data.get("chart"):
        try:
            st.plotly_chart(charts.figure(data["chart"], data["rows"]), width="stretch")
        except Exception as e:
            st.warning(f"Could not render chart: {e}")
    if data.get("rows"):
        label = f"Data ({data.get('row_count', len(data['rows']))} rows"
        label += ", sampled)" if data.get("truncated") else ")"
        with st.expander(label):
            st.dataframe(data["rows"], width="stretch")


def render_chat(section: str, key_prefix: str, placeholder: str) -> None:
    st.session_state.setdefault(f"{key_prefix}_chat_id", None)
    st.session_state.setdefault(f"{key_prefix}_messages", [])

    for msg in st.session_state[f"{key_prefix}_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                _render_assistant_extras(msg)

    prompt = st.chat_input(placeholder)
    if not prompt:
        return

    st.session_state[f"{key_prefix}_messages"].append(
        {"role": "user", "content": prompt, "sql": None, "routed_to": None, "data": None}
    )
    with st.spinner("Thinking..."):
        try:
            resp = send_message(prompt, section=section, chat_id=st.session_state[f"{key_prefix}_chat_id"])
            st.session_state[f"{key_prefix}_chat_id"] = resp["chat_id"]
            st.session_state[f"{key_prefix}_messages"].append(
                {
                    "role": "assistant",
                    "content": resp["reply"],
                    "sql": resp.get("sql"),
                    "routed_to": resp.get("routed_to"),
                    "data": resp.get("data"),
                }
            )
        except ApiError as e:
            st.session_state[f"{key_prefix}_messages"].append(
                {"role": "assistant", "content": f"⚠️ {e}", "sql": None, "routed_to": None, "data": None}
            )
    st.rerun()
