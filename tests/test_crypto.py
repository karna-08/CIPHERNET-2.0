from app.services.crypto import decrypt_message, encrypt_message, generate_key_pair, protect_private_key, restore_private_key


def test_hybrid_encryption_round_trip():
    recipient_public, recipient_private = generate_key_pair()
    sender_public, sender_private = generate_key_pair()
    envelope = encrypt_message("hello CipherNet 🔐", recipient_public, sender_public)
    assert decrypt_message(envelope["content"], envelope["iv"], envelope["encrypted_key"], recipient_private) == "hello CipherNet 🔐"
    assert decrypt_message(envelope["content"], envelope["iv"], envelope["sender_encrypted_key"], sender_private) == "hello CipherNet 🔐"


def test_private_key_recovery_envelope():
    _, private_key = generate_key_pair()
    assert restore_private_key(protect_private_key(private_key, "a-long-password"), "a-long-password") == private_key
