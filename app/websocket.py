from fastapi import WebSocket, WebSocketDisconnect, Depends
from typing import Dict, List
import json
import asyncio
from sqlalchemy.orm import Session
from .database import get_db
from .models import Task, User
from .auth import verify_jwt

class ConnectionManager:
    def __init__(self):
        # Store connections by day_id for efficient broadcasting
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # Store user info for each connection
        self.connection_users: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, day_id: int, user_info: dict):
        await websocket.accept()
        
        if day_id not in self.active_connections:
            self.active_connections[day_id] = []
        
        self.active_connections[day_id].append(websocket)
        self.connection_users[websocket] = {
            "day_id": day_id,
            "user_id": user_info.get("user_id"),
            "username": user_info.get("username")
        }
        
        # Send current user count to all connections for this day
        await self.broadcast_user_count(day_id)

    def disconnect(self, websocket: WebSocket):
        user_info = self.connection_users.get(websocket)
        if user_info:
            day_id = user_info["day_id"]
            if day_id in self.active_connections:
                if websocket in self.active_connections[day_id]:
                    self.active_connections[day_id].remove(websocket)
                
                # Clean up empty day connections
                if not self.active_connections[day_id]:
                    del self.active_connections[day_id]
            
            del self.connection_users[websocket]
            
            # Send updated user count
            asyncio.create_task(self.broadcast_user_count(day_id))

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            # Connection might be closed
            self.disconnect(websocket)

    async def broadcast_to_day(self, day_id: int, message: dict):
        if day_id in self.active_connections:
            message_str = json.dumps(message)
            disconnected = []
            
            for connection in self.active_connections[day_id]:
                try:
                    await connection.send_text(message_str)
                except:
                    disconnected.append(connection)
            
            # Clean up disconnected connections
            for connection in disconnected:
                self.disconnect(connection)

    async def broadcast_user_count(self, day_id: int):
        if day_id in self.active_connections:
            user_count = len(self.active_connections[day_id])
            users = []
            
            for connection in self.active_connections[day_id]:
                user_info = self.connection_users.get(connection)
                if user_info:
                    users.append({
                        "username": user_info["username"],
                        "user_id": user_info["user_id"]
                    })
            
            await self.broadcast_to_day(day_id, {
                "type": "user_count_update",
                "user_count": user_count,
                "users": users
            })

    async def broadcast_task_update(self, day_id: int, task_data: dict):
        await self.broadcast_to_day(day_id, {
            "type": "task_update",
            "task": task_data
        })

    async def broadcast_inventory_update(self, day_id: int, inventory_data: dict):
        await self.broadcast_to_day(day_id, {
            "type": "inventory_update",
            "inventory": inventory_data
        })

# Global connection manager instance
manager = ConnectionManager()

async def get_websocket_user(websocket: WebSocket, token: str, db: Session):
    """Authenticate WebSocket connection"""
    try:
        payload = verify_jwt(token)
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.is_active:
            await websocket.close(code=1008, reason="Invalid user")
            return None
        return user
    except Exception:
        await websocket.close(code=1008, reason="Authentication failed")
        return None