"""Client-side hybrid cryptography helpers: RSA-OAEP plus AES-256-GCM."""
from __future__ import annotations
import base64
import json
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


def _password_key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(password.encode())


def protect_private_key(private_pem: str, password: str) -> str:
    """Encrypt a private key locally with its account password for key recovery."""
    salt, nonce = os.urandom(16), os.urandom(12)
    ciphertext = AESGCM(_password_key(password, salt)).encrypt(nonce, private_pem.encode(), None)
    return base64.b64encode(json.dumps({"salt": base64.b64encode(salt).decode(), "nonce": base64.b64encode(nonce).decode(), "ciphertext": base64.b64encode(ciphertext).decode()}).encode()).decode()


def restore_private_key(envelope: str, password: str) -> str:
    data = json.loads(base64.b64decode(envelope))
    salt, nonce = base64.b64decode(data["salt"]), base64.b64decode(data["nonce"])
    return AESGCM(_password_key(password, salt)).decrypt(nonce, base64.b64decode(data["ciphertext"]), None).decode()


def generate_key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    public_pem = private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return public_pem, private_pem


def _encrypt_key(key: bytes, public_pem: str) -> str:
    public_key = serialization.load_pem_public_key(public_pem.encode())
    encrypted_key = public_key.encrypt(key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return base64.b64encode(encrypted_key).decode()


def encrypt_message(plaintext: str, recipient_public_pem: str, sender_public_pem: str | None = None) -> dict[str, str]:
    """Encrypt content once and wrap its AES key for recipient and sender."""
    key, nonce = AESGCM.generate_key(bit_length=256), os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return {
        "content": base64.b64encode(ciphertext).decode(),
        "iv": base64.b64encode(nonce).decode(),
        "encrypted_key": _encrypt_key(key, recipient_public_pem),
        "sender_encrypted_key": _encrypt_key(key, sender_public_pem or recipient_public_pem),
    }


def decrypt_message(content: str, iv: str, encrypted_key: str, private_pem: str) -> str:
    private_key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    key = private_key.decrypt(base64.b64decode(encrypted_key), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return AESGCM(key).decrypt(base64.b64decode(iv), base64.b64decode(content), None).decode()
