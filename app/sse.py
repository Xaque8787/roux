import asyncio
import json
from typing import Dict, Set, Any
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import logging

logger = logging.getLogger(__name__)

class SSEManager:
    def __init__(self):
        # Store active connections by room
        self.connections: Dict[str, Set[asyncio.Queue]] = {}
        
    async def add_connection(self, room: str, queue: asyncio.Queue):
        """Add a connection to a room"""
        if room not in self.connections:
            self.connections[room] = set()
        self.connections[room].add(queue)
        logger.info(f"Added connection to room {room}. Total connections: {len(self.connections[room])}")
    
    async def remove_connection(self, room: str, queue: asyncio.Queue):
        """Remove a connection from a room"""
        if room in self.connections:
            self.connections[room].discard(queue)
            if not self.connections[room]:
                del self.connections[room]
            logger.info(f"Removed connection from room {room}")
    
    async def broadcast_to_room(self, room: str, data: Dict[str, Any]):
        """Broadcast data to all connections in a room"""
        if room not in self.connections:
            return
        
        message = {
            "timestamp": datetime.utcnow().isoformat(),
            **data
        }
        
        message_str = f"data: {json.dumps(message)}\n\n"
        
        # Send to all connections in the room
        dead_connections = set()
        for queue in self.connections[room].copy():
            try:
                await queue.put(message_str)
            except Exception as e:
                logger.error(f"Error sending message to connection: {e}")
                dead_connections.add(queue)
        
        # Remove dead connections
        for dead_queue in dead_connections:
            self.connections[room].discard(dead_queue)
        
        logger.info(f"Broadcasted to room {room}: {len(self.connections[room])} connections")

# Global SSE manager instance
sse_manager = SSEManager()

# SSE Router
router = APIRouter(prefix="/events", tags=["sse"])

@router.get("/inventory/{day_id}")
async def inventory_day_events(day_id: int):
    """SSE endpoint for inventory day real-time updates"""
    
    async def event_generator():
        queue = asyncio.Queue()
        room = f"inventory_day_{day_id}"
        
        try:
            await sse_manager.add_connection(room, queue)
            
            # Send initial connection confirmation
            initial_message = f"data: {json.dumps({'type': 'connected', 'day_id': day_id})}\n\n"
            yield initial_message
            
            while True:
                try:
                    # Wait for messages with timeout for heartbeat
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield message
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    heartbeat = f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                    yield heartbeat
                    
        except asyncio.CancelledError:
            logger.info(f"SSE connection cancelled for day {day_id}")
        except Exception as e:
            logger.error(f"SSE error for day {day_id}: {e}")
        finally:
            await sse_manager.remove_connection(room, queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        }
    )

# Helper functions for broadcasting specific events
async def broadcast_task_update(day_id: int, task_id: int, event_type: str, task_data: Dict[str, Any]):
    """Broadcast task-related updates"""
    await sse_manager.broadcast_to_room(f"inventory_day_{day_id}", {
        "type": event_type,
        "task_id": task_id,
        **task_data
    })

async def broadcast_inventory_update(day_id: int, item_id: int, event_type: str, inventory_data: Dict[str, Any]):
    """Broadcast inventory-related updates"""
    await sse_manager.broadcast_to_room(f"inventory_day_{day_id}", {
        "type": event_type,
        "item_id": item_id,
        **inventory_data
    })

async def broadcast_day_update(day_id: int, event_type: str, day_data: Dict[str, Any]):
    """Broadcast day-level updates"""
    await sse_manager.broadcast_to_room(f"inventory_day_{day_id}", {
        "type": event_type,
        "day_id": day_id,
        **day_data
    })