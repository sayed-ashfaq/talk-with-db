"""Database page: connect to Postgres/MySQL (structured fields or a raw URL — POST /connections),
switch/remove saved connections, then chat against the Database agent (sql_agent, analytics_agent,
visualizer)."""

import streamlit as st

import chat_ui
from api_client import ApiError, activate_connection, create_connection, delete_connection, list_connections

st.title("🗄️ Database")
st.caption("SQL retrieval, pandas/numpy analytics, and charts over a connected database.")

with st.sidebar:
    st.subheader("Database connection")

    try:
        connections = list_connections()
    except ApiError as e:
        st.error(f"Could not load connections: {e}")
        connections = []

    for c in connections:
        dot = "🟢" if c["active"] else "⚪"
        cols = st.columns([3, 1])
        cols[0].write(f"{dot} **{c['name']}** ({c['db_type']}/{c['dbname']})")
        if not c["active"]:
            if cols[1].button("Use", key=f"activate-{c['id']}"):
                try:
                    activate_connection(c["id"])
                    st.rerun()
                except ApiError as e:
                    st.error(str(e))
        else:
            if cols[1].button("✕", key=f"delete-{c['id']}"):
                try:
                    delete_connection(c["id"])
                    st.rerun()
                except ApiError as e:
                    st.error(str(e))

    if not any(c["active"] for c in connections):
        st.info("No active connection yet — DB questions will fail until one is connected.")

    with st.expander("+ Add a connection", expanded=not connections):
        mode = st.radio("Connect via", ["Fields", "URL"], horizontal=True, key="db_conn_mode")

        with st.form("db_connect_form", clear_on_submit=True):
            name = st.text_input("Name")
            db_type = st.selectbox("Database type", ["postgres", "mysql"])

            host = port = user = password = dbname = url = None
            if mode == "Fields":
                host = st.text_input("Host")
                port = st.number_input("Port", value=5432 if db_type == "postgres" else 3306, step=1)
                user = st.text_input("User")
                password = st.text_input("Password", type="password")
                dbname = st.text_input("Database name")
            else:
                url = st.text_input("Connection URL", placeholder="postgresql://user:pass@host:port/dbname")

            if st.form_submit_button("🔌 Connect"):
                payload = {"name": name, "db_type": db_type}
                if mode == "Fields":
                    payload.update(
                        {"host": host, "port": int(port), "user": user, "password": password, "dbname": dbname}
                    )
                else:
                    payload["url"] = url
                try:
                    create_connection(payload)
                    st.success(f"Connected '{name}'")
                    st.rerun()
                except ApiError as e:
                    st.error(str(e))

    st.divider()
    chat_ui.render_sidebar_chats("database", "db")

chat_ui.render_chat("database", "db", "Ask a question about your data...")
