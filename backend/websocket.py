from fastapi import WebSocket
from typing import List, Dict

class ConnectionManager:
    def __init__(self):
        # Active connections mapped by facebook_user_id
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, facebook_user_id: str, websocket: WebSocket):
        await websocket.accept()
        if facebook_user_id not in self.active_connections:
            self.active_connections[facebook_user_id] = []
        self.active_connections[facebook_user_id].append(websocket)
        print(f"[WebSocket] Connected client for User: {facebook_user_id}")

    def disconnect(self, facebook_user_id: str, websocket: WebSocket):
        if facebook_user_id in self.active_connections:
            if websocket in self.active_connections[facebook_user_id]:
                self.active_connections[facebook_user_id].remove(websocket)
            if not self.active_connections[facebook_user_id]:
                del self.active_connections[facebook_user_id]
        print(f"[WebSocket] Disconnected client for User: {facebook_user_id}")

    async def send_personal_message(self, message: dict, facebook_user_id: str):
        if facebook_user_id in self.active_connections:
            for connection in self.active_connections[facebook_user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"[WebSocket] Error sending message: {str(e)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all active WebSocket connections."""
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"[WebSocket] Error broadcasting: {str(e)}")

manager = ConnectionManager()
