"""Thin wrapper around the real backend API — every call here is a real HTTP request to a real
endpoint (POST/GET/DELETE), nothing imports backend code directly. That's deliberate: this tool is
meant to exercise the same surface a real frontend would, so a bug in the API contract shows up here
too rather than only after the React app is updated to match.

Auth is real too — there's no backend bypass. `ensure_authenticated()` logs a fixed dev/test account
in through the actual `/auth/login` + `/auth/signup` endpoints (creating it on first run), so this
tool needs no login screen while still going through the same session-cookie auth the real frontend
uses.
"""

import os

import requests
import streamlit as st

DEFAULT_BACKEND_URL = os.environ.get("NL2SQL_BACKEND_URL", "http://localhost:8080")
# .local is a reserved special-use TLD and pydantic's EmailStr (email-validator) rejects it outright
# — confirmed live against POST /auth/signup, a 422 before this even reached auth logic.
DEV_EMAIL = os.environ.get("STREAMLIT_DEV_EMAIL", "streamlit-tester@nl2sql-tester.internal")
DEV_PASSWORD = os.environ.get("STREAMLIT_DEV_PASSWORD", "streamlit-dev-only-12345")


class ApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{detail} (HTTP {status_code})")

    def __str__(self) -> str:
        return self.detail


def backend_url() -> str:
    return st.session_state.get("backend_url", DEFAULT_BACKEND_URL)


def _session() -> requests.Session:
    # one requests.Session per browser tab (Streamlit's session_state), so the auth cookie set by
    # ensure_authenticated() is reused on every subsequent call instead of re-logging in each rerun
    if "http_session" not in st.session_state:
        st.session_state.http_session = requests.Session()
    return st.session_state.http_session


def _format_error(resp: requests.Response) -> str:
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        return resp.text or f"HTTP {resp.status_code}"
    if isinstance(detail, list):  # FastAPI validation errors
        return "; ".join(f"{'.'.join(str(p) for p in e.get('loc', []))}: {e.get('msg')}" for e in detail)
    return str(detail)


def _request(method: str, path: str, timeout: int = 60, **kwargs) -> requests.Response:
    resp = _session().request(method, f"{backend_url()}{path}", timeout=timeout, **kwargs)
    if not resp.ok:
        raise ApiError(resp.status_code, _format_error(resp))
    return resp


def ensure_authenticated() -> None:
    if st.session_state.get("authed"):
        return

    sess = _session()
    base = backend_url()
    resp = sess.post(f"{base}/auth/login", json={"email": DEV_EMAIL, "password": DEV_PASSWORD}, timeout=15)
    if resp.status_code == 401:
        # first run ever against this backend — the dev account doesn't exist yet
        resp = sess.post(
            f"{base}/auth/signup",
            json={"email": DEV_EMAIL, "password": DEV_PASSWORD, "full_name": "Streamlit Tester"},
            timeout=15,
        )
        if resp.status_code == 409:
            # lost a race with another tab/process signing the same account up first
            resp = sess.post(f"{base}/auth/login", json={"email": DEV_EMAIL, "password": DEV_PASSWORD}, timeout=15)
    if not resp.ok:
        raise ApiError(resp.status_code, _format_error(resp))

    st.session_state.authed = True
    st.session_state.dev_user = resp.json()


# --- connections -----------------------------------------------------------------------------------


def list_connections() -> list[dict]:
    return _request("GET", "/connections").json()


def create_connection(payload: dict) -> dict:
    return _request("POST", "/connections", json=payload, timeout=120).json()


def activate_connection(connection_id: str) -> dict:
    return _request("POST", f"/connections/{connection_id}/activate", timeout=120).json()


def delete_connection(connection_id: str) -> dict:
    return _request("DELETE", f"/connections/{connection_id}").json()


def get_schema(schema_type: str = "plain") -> dict:
    return _request("GET", "/connections/schema", params={"schema_type": schema_type}, timeout=60).json()


# --- chats -----------------------------------------------------------------------------------------


def list_chats() -> list[dict]:
    return _request("GET", "/chats").json()


def get_chat(chat_id: str) -> dict:
    return _request("GET", f"/chats/{chat_id}").json()


def delete_chat(chat_id: str) -> dict:
    return _request("DELETE", f"/chats/{chat_id}").json()


def send_message(message: str, section: str, chat_id: str | None = None) -> dict:
    payload = {"message": message, "section": section}
    if chat_id:
        payload["chat_id"] = chat_id
    return _request("POST", "/chat", json=payload, timeout=120).json()
