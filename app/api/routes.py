"""HTTP and WebSocket API preserving CipherNet's encrypted-envelope contract."""
from __future__ import annotations
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPAuthorizationCredentials
from app.models.schemas import AuthResponse, EncryptedMessage, EncryptedMessageCreate, KeyResponse, LoginRequest, RegisterRequest, UserPublic
from app.services import database
from app.services.auth import authenticated_user, bearer, create_access_token, hash_password, verify_password
from app.services.connections import manager

logger = logging.getLogger(__name__)
router = APIRouter()
CurrentUser = Depends(lambda credentials=Depends(bearer): authenticated_user(credentials))


def _user(row) -> UserPublic:
    return UserPublic(id=row["id"], username=row["username"], public_key=row["public_key"])


@router.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    with database.connection() as conn:
        if conn.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (request.username,)).fetchone():
            raise HTTPException(400, "Username already taken.")
        cursor = conn.execute("INSERT INTO users (username, password_hash, public_key, private_key_envelope) VALUES (?, ?, ?, ?)",
                              (request.username, hash_password(request.password), request.public_key, request.private_key_envelope))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    token = create_access_token(row["id"], row["username"])
    await manager.send_to(row["id"], "user_status_change", {"username": row["username"], "userId": row["id"]})
    return AuthResponse(id=row["id"], user_id=row["id"], username=row["username"], public_key=row["public_key"], token=token, private_key_envelope=row["private_key_envelope"])


@router.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    with database.connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (request.username,)).fetchone()
    if row is None or not verify_password(request.password, row["password_hash"]):
        raise HTTPException(400, "Invalid credentials.")
    return AuthResponse(id=row["id"], user_id=row["id"], username=row["username"], public_key=row["public_key"], token=create_access_token(row["id"], row["username"]), private_key_envelope=row["private_key_envelope"])


@router.get("/users", response_model=list[UserPublic])
async def users(current: dict = CurrentUser):
    with database.connection() as conn:
        rows = conn.execute("SELECT id, username, public_key FROM users WHERE id != ? ORDER BY username", (current["userId"],)).fetchall()
    return [_user(row) for row in rows]


@router.get("/users/{username}/key", response_model=KeyResponse)
async def user_key(username: str, current: dict = CurrentUser):
    with database.connection() as conn:
        row = conn.execute("SELECT public_key FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
    if row is None:
        raise HTTPException(404, "User not found.")
    return KeyResponse(public_key=row["public_key"])


@router.get("/messages/{contact_id}", response_model=list[EncryptedMessage])
async def history(contact_id: int, current: dict = CurrentUser):
    with database.connection() as conn:
        rows = conn.execute("SELECT * FROM messages WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?) ORDER BY id",
                            (current["userId"], contact_id, contact_id, current["userId"])).fetchall()
    return [EncryptedMessage(**dict(row)) for row in rows]


@router.post("/messages", response_model=EncryptedMessage, status_code=status.HTTP_201_CREATED)
async def send_message(payload: EncryptedMessageCreate, current: dict = CurrentUser):
    if payload.receiver_id == current["userId"]:
        raise HTTPException(400, "Cannot message yourself.")
    with database.connection() as conn:
        if not conn.execute("SELECT id FROM users WHERE id = ?", (payload.receiver_id,)).fetchone():
            raise HTTPException(404, "Recipient not found.")
    row = database.create_message(current["userId"], payload.receiver_id, payload.content, payload.iv,
                                  payload.encrypted_key, payload.sender_encrypted_key, payload.timestamp)
    message = EncryptedMessage(**row)
    data = message.model_dump(by_alias=True, mode="json")
    await manager.send_to(payload.receiver_id, "receive_message", data)
    await manager.send_to(current["userId"], "receive_message", data)
    return message


@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    import jwt
    from app.core.config import get_settings
    try:
        user = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        await websocket.close(code=1008)
        return
    user_id = user["userId"]
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
