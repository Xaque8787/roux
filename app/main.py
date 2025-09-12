from fastapi import FastAPI, Request, HTTPException
from fastapi import Depends
from fastapi.responses import HTMLResponse, RedirectResponse
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

# Import icon utilities
from .utils.icons import get_category_icon, get_task_icon

# Create database tables
Base.metadata.create_all(bind=engine)

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

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Add template globals for icon functions
templates.env.globals['get_category_icon'] = get_category_icon
templates.env.globals['get_task_icon'] = get_task_icon

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