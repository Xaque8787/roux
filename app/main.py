from fastapi import FastAPI, Request, HTTPException
from fastapi import Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from datetime import datetime, timedelta
import json

# Import database and models
from .database import engine
from .dependencies import get_db
from .models import Base, Task, Batch, InventoryItem

# Import routers
from .routers import (
    auth, home, employees, ingredients, recipes, batches, 
    dishes, inventory, utilities, categories, vendors, par_unit_names
)

# Import API routers
from .api import ingredients as api_ingredients, batches as api_batches, recipes as api_recipes, tasks as api_tasks

# Import dependencies
from .dependencies import get_current_user

# Import WebSocket manager
from .websocket import manager
from .auth import verify_jwt

# Import template helper functions

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Initialize FastAPI app
app = FastAPI(title="Food Cost Management System", version="1.0.0")

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
app.include_router(api_ingredients.router)
app.include_router(api_batches.router)
app.include_router(api_recipes.router)
app.include_router(api_tasks.router)

# WebSocket endpoint for real-time updates
@app.websocket("/ws/inventory/{day_id}")
async def websocket_endpoint(websocket: WebSocket, day_id: int, token: str = None):
    # Accept connection first
    await websocket.accept()
    
    try:
        # Authenticate user
        if not token:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "No authentication token provided"
            }))
            await websocket.close(code=1008)
            return
        
        # Verify JWT token
        try:
            payload = verify_jwt(token)
            username = payload.get("sub")
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "error", 
                "message": f"Authentication failed: {str(e)}"
            }))
            await websocket.close(code=1008)
            return
        
        # Get user from database
        db = next(get_db())
        try:
            from .models import User
            user = db.query(User).filter(User.username == username).first()
            if not user or not user.is_active:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "User not found or inactive"
                }))
                await websocket.close(code=1008)
                return
        finally:
            db.close()
        
        # Connection successful
        user_info = {
            "user_id": user.id,
            "username": user.full_name or user.username
        }
        
        await manager.connect(websocket, day_id, user_info)
        
        # Send connection success message
        await websocket.send_text(json.dumps({
            "type": "connection_success",
            "message": "Connected successfully",
            "user": user_info
        }))
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Echo back for heartbeat
            await websocket.send_text(json.dumps({
                "type": "heartbeat",
                "message": "pong"
            }))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Connection error: {str(e)}"
            }))
        except:
            pass
        manager.disconnect(websocket)
        try:
            await websocket.close()
        except:
            pass
        return
    
    user_info = {
        "user_id": user.id,
        "username": user.full_name or user.username
    }
    
    await manager.connect(websocket, day_id, user_info)
    
    try:
        while True:
            # Keep connection alive and handle any incoming messages
            data = await websocket.receive_text()
            # For now, we just echo back (could be used for heartbeat)
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Additional API endpoint for batch labor stats
@app.get("/api/batches/{batch_id}/labor_stats")
async def api_batch_labor_stats(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    completed_tasks = db.query(Task).filter(
        or_(
            Task.batch_id == batch_id,
            and_(
                Task.inventory_item_id.isnot(None),
                Task.inventory_item.has(InventoryItem.batch_id == batch_id)
            )
        ),
        Task.finished_at.isnot(None)
    ).order_by(Task.finished_at.desc()).all()
    
    if not completed_tasks:
        return {
            "task_count": 0,
            "most_recent_cost": batch.estimated_labor_cost,
            "average_week": batch.estimated_labor_cost,
            "average_month": batch.estimated_labor_cost,
            "average_all_time": batch.estimated_labor_cost,
            "week_task_count": 0,
            "month_task_count": 0
        }
    
    # Calculate statistics
    most_recent = completed_tasks[0]
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    week_tasks = [t for t in completed_tasks if t.finished_at >= week_ago]
    month_tasks = [t for t in completed_tasks if t.finished_at >= month_ago]
    
    return {
        "task_count": len(completed_tasks),
        "most_recent_cost": most_recent.labor_cost,
        "most_recent_date": most_recent.finished_at.strftime('%Y-%m-%d'),
        "average_week": sum(t.labor_cost for t in week_tasks) / len(week_tasks) if week_tasks else batch.estimated_labor_cost,
        "average_month": sum(t.labor_cost for t in month_tasks) / len(month_tasks) if month_tasks else batch.estimated_labor_cost,
        "average_all_time": sum(t.labor_cost for t in completed_tasks) / len(completed_tasks),
        "week_task_count": len(week_tasks),
        "month_task_count": len(month_tasks)
    }

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401 and exc.headers and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=302)
    
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": exc.status_code,
        "detail": exc.detail
    }, status_code=exc.status_code)

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 404,
        "detail": "Page not found"
    }, status_code=404)

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 500,
        "detail": "Internal server error"
    }, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)