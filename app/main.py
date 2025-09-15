from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import json

from .database import engine, get_db
from .models import Base, User
from .routers import auth, home, employees, ingredients, recipes, batches, dishes, inventory, utilities, categories, vendors, par_unit_names
from .api import ingredients as ingredients_api, recipes as recipes_api, batches as batches_api, tasks as tasks_api
from .websocket import manager
from .auth import verify_jwt
from .dependencies import get_current_user

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Food Cost Management System")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(employees.router)
app.include_router(ingredients.router)
app.include_router(recipes.router)
app.include_router(batches.router)
app.include_router(dishes.router)
app.include_router(inventory.router)
app.include_router(utilities.router)
app.include_router(categories.router)
app.include_router(vendors.router)
app.include_router(par_unit_names.router)

# Include API routers
app.include_router(ingredients_api.router)
app.include_router(recipes_api.router)
app.include_router(batches_api.router)
app.include_router(tasks_api.router)

templates = Jinja2Templates(directory="templates")

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401 and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=302)
    
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": exc.status_code,
        "detail": exc.detail
    }, status_code=exc.status_code)

@app.websocket("/ws/{day_id}")
async def websocket_endpoint(websocket: WebSocket, day_id: int, db: Session = Depends(get_db)):
    # Get token from query parameters
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="No authentication token provided")
        return
    
    try:
        # Verify the token
        payload = verify_jwt(token)
        username = payload.get("sub")
        
        # Get user from database
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.is_active:
            await websocket.close(code=1008, reason="Invalid user")
            return
        
        # Connect to WebSocket manager
        user_info = {
            "user_id": user.id,
            "username": user.username
        }
        
        await manager.connect(websocket, day_id, user_info)
        
        try:
            while True:
                # Keep connection alive and handle incoming messages
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif message.get("type") == "task_update":
                    # Broadcast task updates to all connected clients
                    await manager.broadcast_task_update(day_id, message.get("data", {}))
                elif message.get("type") == "inventory_update":
                    # Broadcast inventory updates to all connected clients
                    await manager.broadcast_inventory_update(day_id, message.get("data", {}))
                
        except WebSocketDisconnect:
            manager.disconnect(websocket)
        except Exception as e:
            print(f"WebSocket error: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Connection error: {str(e)}"
            }))
            manager.disconnect(websocket)
            
    except Exception as e:
        print(f"WebSocket authentication error: {e}")
        await websocket.close(code=1008, reason="Authentication failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)