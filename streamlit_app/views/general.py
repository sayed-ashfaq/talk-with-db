"""General page: the General agent — chit-chat, drafting help, daily-workflow questions today.
RAG (doc upload) and CSV analytics land here once Phase 2 of the backend split is built; this page
needs no changes when they do — chat_ui already renders whatever `data`/`sql` a turn comes back with.
"""

import streamlit as st

import chat_ui

st.title("💬 General")
st.caption("General-purpose assistant. RAG over uploaded docs and CSV analytics are coming soon.")

with st.sidebar:
    chat_ui.render_sidebar_chats("general", "general")

chat_ui.render_chat("general", "general", "Ask me anything...")
