"""Streamlit client for CipherNet. Cryptographic private keys remain in session memory."""
from __future__ import annotations
import os
from datetime import datetime, timezone
import httpx
import streamlit as st
from app.services.crypto import decrypt_message, encrypt_message, generate_key_pair, protect_private_key, restore_private_key

API_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
st.set_page_config(page_title="CipherNet", page_icon="🔐", layout="wide")


def api(method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    if token := st.session_state.get("token"):
        headers["Authorization"] = f"Bearer {token}"
    response = httpx.request(method, f"{API_URL}{path}", headers=headers, timeout=10, **kwargs)
    if response.is_error:
        detail = response.json().get("detail", response.text)
        raise RuntimeError(detail)
    return response.json()


def login_screen() -> None:
    st.title("🔐 CipherNet")
    st.caption("End-to-end encrypted messaging with Python, RSA-OAEP, and AES-256-GCM.")
    login_tab, register_tab = st.tabs(["Sign in", "Create identity"])
    with login_tab:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")
        if submitted:
            try:
                identity = api("POST", "/auth/login", json={"username": username, "password": password})
                st.session_state.update(identity)
                if envelope := identity.get("privateKeyEnvelope"):
                    st.session_state["private_key"] = restore_private_key(envelope, password)
                else:
                    st.session_state.pop("private_key", None)
                    st.warning("This is a legacy identity created before key recovery was added. Its original private key cannot be recovered; create a new identity to send and read persistent messages.")
                st.rerun()
            except (RuntimeError, httpx.HTTPError) as exc:
                st.error(str(exc))
    with register_tab:
        with st.form("register"):
            username = st.text_input("New username")
            password = st.text_input("New password", type="password", help="At least 8 characters")
            submitted = st.form_submit_button("Generate identity and register")
        if submitted:
            try:
                public_key, private_key = generate_key_pair()
                envelope = protect_private_key(private_key, password)
                identity = api("POST", "/auth/register", json={"username": username, "password": password, "publicKey": public_key, "privateKeyEnvelope": envelope})
                st.session_state.update(identity)
                st.session_state["private_key"] = private_key
                st.rerun()
            except (RuntimeError, ValueError, httpx.HTTPError) as exc:
                st.error(str(exc))


def show_diagnostics() -> None:
    with st.expander("System diagnostics"):
        st.success("Authenticated API connection")
        if private_key := st.session_state.get("private_key"):
            public_key = st.session_state["publicKey"]
            probe = encrypt_message("CipherNet diagnostic", public_key)
            assert decrypt_message(
                probe["content"], probe["iv"], probe["encrypted_key"], private_key
            ) == "CipherNet diagnostic"
            st.success("RSA-OAEP + AES-256-GCM round trip verified")
        else:
            st.warning("Private key unavailable in this Streamlit session")


@st.fragment(run_every=1.0)
def conversation(contact: dict) -> None:
    """Refresh the selected conversation every second for near-real-time delivery."""
    try:
        messages = api("GET", f"/messages/{contact['id']}")
    except (RuntimeError, httpx.HTTPError) as exc:
        st.error(f"Could not load messages: {exc}")
        return
    for message in messages:
        mine = message["senderId"] == st.session_state["userId"]
        with st.chat_message("user" if mine else "assistant"):
            private_key = st.session_state.get("private_key")
            key_envelope = message.get("senderEncryptedKey") if mine else message["encryptedKey"]
            if private_key and key_envelope:
                try:
                    st.write(decrypt_message(message["content"], message["iv"], key_envelope, private_key))
                except Exception:
                    st.warning("🔒 This message was encrypted with a different private key and cannot be recovered.")
            elif mine:
                st.caption("🔒 Legacy sent envelope: sender key was not stored in the original version.")
            else:
                st.caption("🔒 Legacy encrypted message: its original private key is unavailable.")
            st.caption(f"{message['timestamp']} · encrypted envelope #{message['id']}")
    if plaintext := st.chat_input("Type a secured message"):
        try:
            envelope = encrypt_message(plaintext, contact["publicKey"], st.session_state["publicKey"])
            envelope["receiverId"] = contact["id"]
            envelope["timestamp"] = datetime.now(timezone.utc).isoformat()
            api("POST", "/messages", json=envelope)
            st.rerun()
        except (RuntimeError, ValueError, httpx.HTTPError) as exc:
            st.error(f"Message was not sent: {exc}")


def app_screen() -> None:
    st.sidebar.title("🔐 CipherNet")
    st.sidebar.caption(f"Signed in as **{st.session_state['username']}**")
    if st.sidebar.button("Sign out"):
        for key in ("token", "id", "userId", "username", "publicKey", "private_key", "contact"):
            st.session_state.pop(key, None)
        st.rerun()
    try:
        users = api("GET", "/users")
    except (RuntimeError, httpx.HTTPError) as exc:
        st.error(f"Could not contact CipherNet API at {API_URL}: {exc}")
        return
    if not users:
        st.info("No other identities yet. Register another user in a separate browser session.")
        show_diagnostics()
        return
    names = {user["username"]: user for user in users}
    selected_name = st.sidebar.selectbox("Secure link", names, index=list(names).index(st.session_state.get("contact", next(iter(names)))))
    contact = names[selected_name]
    st.session_state["contact"] = selected_name
    st.title(f"Secure chat with {selected_name}")
    conversation(contact)
    show_diagnostics()


if "token" not in st.session_state:
    login_screen()
else:
    app_screen()
