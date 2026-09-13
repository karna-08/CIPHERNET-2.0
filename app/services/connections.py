"""In-memory WebSocket delivery for encrypted message envelopes."""
from collections import defaultdict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[user_id].add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        self.connections[user_id].discard(websocket)
        if not self.connections[user_id]:
            self.connections.pop(user_id, None)

    async def send_to(self, user_id: int, event: str, data: dict) -> None:
        stale: list[WebSocket] = []
        for socket in self.connections.get(user_id, set()):
            try:
                await socket.send_json({"event": event, "data": data})
            except RuntimeError:
                stale.append(socket)
        for socket in stale:
            self.disconnect(user_id, socket)


manager = ConnectionManager()

