"""Pydantic request and response models."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class RegisterRequest(ApiModel):
    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=72)
    public_key: str = Field(min_length=100, alias="publicKey")
    private_key_envelope: str = Field(min_length=100, alias="privateKeyEnvelope")


class LoginRequest(ApiModel):
    username: str
    password: str


class UserPublic(ApiModel):
    id: int
    username: str
    public_key: str = Field(alias="publicKey")


class AuthResponse(UserPublic):
    user_id: int = Field(alias="userId")
    token: str
    private_key_envelope: str | None = Field(default=None, alias="privateKeyEnvelope")


class KeyResponse(ApiModel):
    public_key: str = Field(alias="publicKey")


class EncryptedMessageCreate(ApiModel):
    receiver_id: int = Field(alias="receiverId")
    content: str = Field(min_length=1)
    iv: str = Field(min_length=1)
    encrypted_key: str = Field(min_length=1, alias="encryptedKey")
    sender_encrypted_key: str = Field(min_length=1, alias="senderEncryptedKey")
    timestamp: datetime | None = None


class EncryptedMessage(ApiModel):
    id: int
    sender_id: int = Field(alias="senderId")
    receiver_id: int = Field(alias="receiverId")
    content: str
    iv: str
    encrypted_key: str = Field(alias="encryptedKey")
    sender_encrypted_key: str | None = Field(default=None, alias="senderEncryptedKey")
    timestamp: datetime
