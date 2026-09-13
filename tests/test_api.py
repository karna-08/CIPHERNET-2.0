import os
import tempfile
from fastapi.testclient import TestClient


def test_registration_login_and_message_flow(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db") as database:
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.name}")
        monkeypatch.setenv("JWT_SECRET", "test-secret")
        from app.core.config import get_settings
        get_settings.cache_clear()
        from app.main import app
        with TestClient(app) as client:
            alice = client.post("/auth/register", json={"username": "alice", "password": "password123", "publicKey": "A" * 100, "privateKeyEnvelope": "X" * 100}).json()
            bob = client.post("/auth/register", json={"username": "bob", "password": "password123", "publicKey": "B" * 100, "privateKeyEnvelope": "Y" * 100}).json()
            headers = {"Authorization": f"Bearer {alice['token']}"}
            users = client.get("/users", headers=headers).json()
            assert [user["username"] for user in users] == ["bob"]
            sent = client.post("/messages", headers=headers, json={"receiverId": bob["id"], "content": "cipher", "iv": "nonce", "encryptedKey": "recipient-key", "senderEncryptedKey": "sender-key"})
            assert sent.status_code == 201
            history = client.get(f"/messages/{bob['id']}", headers=headers).json()
            assert history[0]["content"] == "cipher"
            assert history[0]["senderEncryptedKey"] == "sender-key"
            assert client.post("/auth/login", json={"username": "alice", "password": "password123"}).json()["privateKeyEnvelope"] == "X" * 100
        get_settings.cache_clear()
