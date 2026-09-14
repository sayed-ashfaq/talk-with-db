"""Entry point — dev auth (see api_client.ensure_authenticated) + the two-page navigation.

Not the real product frontend (that's the React app in ../frontend). This is a dev tool for
exercising the split Database/General agents through the real API, page by page.
"""

import streamlit as st

import api_client

st.set_page_config(page_title="NL2SQL Tester", page_icon="🧪", layout="wide")

with st.sidebar:
    st.text_input("Backend URL", value=api_client.DEFAULT_BACKEND_URL, key="backend_url")

try:
    api_client.ensure_authenticated()
except api_client.ApiError as e:
    st.error(f"Could not reach the backend / authenticate: {e}")
    st.stop()

with st.sidebar:
    user = st.session_state.get("dev_user") or {}
    st.caption(f"dev session: {user.get('email', '?')}")
    st.divider()

database_page = st.Page("views/database.py", title="Database", icon="🗄️", default=True)
general_page = st.Page("views/general.py", title="General", icon="💬")

pg = st.navigation([database_page, general_page])
pg.run()
