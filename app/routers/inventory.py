from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, date, timedelta
from typing import List
from ..database import get_db
from ..dependencies import require_manager_or_admin, get_current_user, require_admin
from ..models import (
    InventoryDay, InventoryItem, InventoryDayItem, Task, User, 
    Category, Batch, JanitorialTask, ParUnitName
)
from ..auth import create_jwt
from ..websocket import manager

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def inventory_page(request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    # Get current day if exists
    today = date.today()
    current_day = db.query(InventoryDay).filter(InventoryDay.date == today).first()
    
    # Get recent finalized days (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    finalized_days = db.query(InventoryDay).filter(
        and_(
            InventoryDay.date >= thirty_days_ago,
            InventoryDay.finalized == True
        )
    ).order_by(InventoryDay.date.desc()).limit(10).all()
    
    # Get all inventory items
    inventory_items = db.query(InventoryItem).all()
    
    # Get all employees for day creation
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get categories and other data for forms
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    par_unit_names = db.query(ParUnitName).all()
    janitorial_tasks = db.query(JanitorialTask).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "current_user": current_user,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "inventory_items": inventory_items,
        "employees": employees,
        "categories": categories,
        "batches": batches,
        "par_unit_names": par_unit_names,
        "janitorial_tasks": janitorial_tasks,
        "today_date": today.isoformat()
    })

@router.post("/new_day")
async def create_inventory_day(
    request: Request,
    date: date = Form(...),
    employees_working: List[int] = Form(...),
    global_notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if existing_day:
        raise HTTPException(status_code=400, detail="Inventory day already exists for this date")
    
    # Create new inventory day
    inventory_day = InventoryDay(
        date=date,
        employees_working=",".join(map(str, employees_working)),
        global_notes=global_notes if global_notes else None
    )
    
    db.add(inventory_day)
    db.flush()  # Get the ID
    
    # Create inventory day items for all master inventory items
    inventory_items = db.query(InventoryItem).all()
    for item in inventory_items:
        day_item = InventoryDayItem(
            day_id=inventory_day.id,
            inventory_item_id=item.id,
            quantity=0.0  # Start with 0, will be updated during the day
        )
        db.add(day_item)
    
    # Create tasks for inventory items that have linked batches
    for item in inventory_items:
        if item.batch:
            task = Task(
                day_id=inventory_day.id,
                inventory_item_id=item.id,
                batch_id=item.batch.id,
                description=f"Make {item.name}",
                assigned_to_id=None
            )
            db.add(task)
    
    # Add daily janitorial tasks
    daily_janitorial_tasks = db.query(JanitorialTask).filter(JanitorialTask.task_type == "daily").all()
    for janitorial_task in daily_janitorial_tasks:
        task = Task(
            day_id=inventory_day.id,
            janitorial_task_id=janitorial_task.id,
            description=janitorial_task.title,
            assigned_to_id=None
        )
        db.add(task)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

@router.get("/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_page(
    day_id: int, 
    request: Request, 
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_user)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    # Get all tasks for this day
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    
    # Get all inventory day items
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    
    # Get all employees for assignment
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get categories for manual task creation
    categories = db.query(Category).filter(Category.type == "inventory").all()
    
    # Get janitorial tasks for manual addition
    janitorial_tasks = db.query(JanitorialTask).filter(JanitorialTask.task_type == "manual").all()
    
    # Generate WebSocket token for real-time updates
    websocket_token = create_jwt(data={"sub": current_user.username})
    
    return templates.TemplateResponse("inventory_day.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "tasks": tasks,
        "inventory_day_items": inventory_day_items,
        "employees": employees,
        "categories": categories,
        "janitorial_tasks": janitorial_tasks,
        "websocket_token": websocket_token
    })

@router.post("/day/{day_id}/tasks/{task_id}/start")
async def start_task(
    day_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update task timing
    task.started_at = datetime.utcnow()
    task.assigned_to_id = current_user.id
    task.is_paused = False
    task.paused_at = None
    
    db.commit()
    
    # Broadcast update via WebSocket
    await manager.broadcast_task_update(day_id, {
        "task_id": task.id,
        "status": "in_progress",
        "assigned_to": current_user.username,
        "started_at": task.started_at.isoformat()
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/pause")
async def pause_task(
    day_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.is_paused = True
    task.paused_at = datetime.utcnow()
    
    db.commit()
    
    # Broadcast update via WebSocket
    await manager.broadcast_task_update(day_id, {
        "task_id": task.id,
        "status": "paused",
        "paused_at": task.paused_at.isoformat()
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/resume")
async def resume_task(
    day_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.is_paused = False
    task.paused_at = None
    
    db.commit()
    
    # Broadcast update via WebSocket
    await manager.broadcast_task_update(day_id, {
        "task_id": task.id,
        "status": "in_progress"
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/finish")
async def finish_task(
    day_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    task.paused_at = None
    
    db.commit()
    
    # Broadcast update via WebSocket
    await manager.broadcast_task_update(day_id, {
        "task_id": task.id,
        "status": "completed",
        "finished_at": task.finished_at.isoformat()
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/new_item")
async def create_inventory_item(
    request: Request,
    name: str = Form(...),
    par_unit_name_id: int = Form(None),
    par_level: float = Form(...),
    batch_id: int = Form(None),
    par_unit_equals_type: str = Form("par_unit_itself"),
    par_unit_equals_amount: float = Form(None),
    par_unit_equals_unit: str = Form(None),
    category_id: int = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    item = InventoryItem(
        name=name,
        par_unit_name_id=par_unit_name_id if par_unit_name_id else None,
        par_level=par_level,
        batch_id=batch_id if batch_id else None,
        par_unit_equals_type=par_unit_equals_type,
        par_unit_equals_amount=par_unit_equals_amount if par_unit_equals_type == "custom" else None,
        par_unit_equals_unit=par_unit_equals_unit if par_unit_equals_type == "custom" else None,
        category_id=category_id if category_id else None
    )
    
    db.add(item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@router.post("/new_janitorial_task")
async def create_janitorial_task(
    request: Request,
    title: str = Form(...),
    instructions: str = Form(""),
    task_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    janitorial_task = JanitorialTask(
        title=title,
        instructions=instructions if instructions else None,
        task_type=task_type
    )
    
    db.add(janitorial_task)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@router.get("/items/{item_id}/edit", response_class=HTMLResponse)
async def inventory_item_edit_page(
    item_id: int, 
    request: Request, 
    db: Session = Depends(get_db), 
    current_user = Depends(require_admin)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    par_unit_names = db.query(ParUnitName).all()
    
    return templates.TemplateResponse("inventory_item_edit.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "categories": categories,
        "batches": batches,
        "par_unit_names": par_unit_names
    })

@router.post("/items/{item_id}/edit")
async def update_inventory_item(
    item_id: int,
    request: Request,
    name: str = Form(...),
    par_unit_name_id: int = Form(None),
    par_level: float = Form(...),
    batch_id: int = Form(None),
    par_unit_equals_type: str = Form("par_unit_itself"),
    par_unit_equals_amount: float = Form(None),
    par_unit_equals_unit: str = Form(None),
    category_id: int = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    item.name = name
    item.par_unit_name_id = par_unit_name_id if par_unit_name_id else None
    item.par_level = par_level
    item.batch_id = batch_id if batch_id else None
    item.par_unit_equals_type = par_unit_equals_type
    item.par_unit_equals_amount = par_unit_equals_amount if par_unit_equals_type == "custom" else None
    item.par_unit_equals_unit = par_unit_equals_unit if par_unit_equals_type == "custom" else None
    item.category_id = category_id if category_id else None
    
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@router.get("/items/{item_id}/delete")
async def delete_inventory_item(
    item_id: int, 
    db: Session = Depends(get_db), 
    current_user = Depends(require_admin)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    db.delete(item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@router.get("/janitorial_tasks/{task_id}/delete")
async def delete_janitorial_task(
    task_id: int, 
    db: Session = Depends(get_db), 
    current_user = Depends(require_admin)
):
    janitorial_task = db.query(JanitorialTask).filter(JanitorialTask.id == task_id).first()
    if not janitorial_task:
        raise HTTPException(status_code=404, detail="Janitorial task not found")
    
    db.delete(janitorial_task)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@router.get("/reports/{day_id}", response_class=HTMLResponse)
async def inventory_report(
    day_id: int, 
    request: Request, 
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_user)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    employees = db.query(User).all()
    
    # Calculate summary statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.finished_at])
    below_par_items = len([item for item in inventory_day_items if item.quantity < item.inventory_item.par_level])
    
    return templates.TemplateResponse("inventory_report.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "tasks": tasks,
        "inventory_day_items": inventory_day_items,
        "employees": employees,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "below_par_items": below_par_items
    })