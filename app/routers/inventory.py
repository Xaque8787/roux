from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, date, timedelta
import json
from ..database import get_db
from ..dependencies import require_manager_or_admin, get_current_user, require_admin
from ..models import (InventoryItem, InventoryDay, InventoryDayItem, Task, User, 
                     Category, Batch, ParUnitName, JanitorialTask)
from ..websocket import manager
from ..utils.helpers import get_today_date

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def inventory_page(request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    inventory_items = db.query(InventoryItem).all()
    employees = db.query(User).filter(User.is_active == True).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    par_unit_names = db.query(ParUnitName).all()
    janitorial_tasks = db.query(JanitorialTask).all()
    
    # Get current day if exists
    today = date.today()
    current_day = db.query(InventoryDay).filter(InventoryDay.date == today).first()
    
    # Get recent finalized days (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    finalized_days = db.query(InventoryDay).filter(
        InventoryDay.date >= thirty_days_ago,
        InventoryDay.finalized == True
    ).order_by(InventoryDay.date.desc()).limit(10).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "current_user": current_user,
        "inventory_items": inventory_items,
        "employees": employees,
        "categories": categories,
        "batches": batches,
        "par_unit_names": par_unit_names,
        "janitorial_tasks": janitorial_tasks,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "today_date": get_today_date()
    })

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

@router.post("/new_day")
async def create_inventory_day(
    request: Request,
    date: str = Form(...),
    employees_working: list = Form(...),
    global_notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    # Parse date
    day_date = datetime.strptime(date, "%Y-%m-%d").date()
    
    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == day_date).first()
    if existing_day:
        return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=302)
    
    # Create new inventory day
    inventory_day = InventoryDay(
        date=day_date,
        employees_working=",".join(map(str, employees_working)),
        global_notes=global_notes if global_notes else None
    )
    
    db.add(inventory_day)
    db.flush()  # Get the ID
    
    # Create inventory day items for all master items
    inventory_items = db.query(InventoryItem).all()
    for item in inventory_items:
        day_item = InventoryDayItem(
            day_id=inventory_day.id,
            inventory_item_id=item.id,
            quantity=0.0  # Default to 0, will be updated by user
        )
        db.add(day_item)
    
    # Create tasks for inventory items that have linked batches
    for item in inventory_items:
        if item.batch:
            task = Task(
                day_id=inventory_day.id,
                inventory_item_id=item.id,
                batch_id=item.batch_id,
                description=f"Make {item.name}",
                requires_made_amount=True
            )
            db.add(task)
    
    # Create tasks for daily janitorial tasks
    daily_janitorial_tasks = db.query(JanitorialTask).filter(JanitorialTask.task_type == "daily").all()
    for janitorial_task in daily_janitorial_tasks:
        task = Task(
            day_id=inventory_day.id,
            janitorial_task_id=janitorial_task.id,
            description=janitorial_task.title,
            requires_made_amount=False
        )
        db.add(task)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

@router.post("/new_janitorial_task")
async def create_janitorial_task(
    request: Request,
    title: str = Form(...),
    instructions: str = Form(""),
    task_type: str = Form("daily"),
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

@router.get("/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_page(day_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    # Get inventory day items with their master items
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item)
    ).filter(InventoryDayItem.day_id == day_id).all()
    
    # Get tasks for this day
    tasks = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.batch),
        joinedload(Task.inventory_item),
        joinedload(Task.janitorial_task)
    ).filter(Task.day_id == day_id).all()
    
    # Get employees working this day
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get categories for manual tasks
    categories = db.query(Category).filter(Category.type == "inventory").all()
    
    # Get available janitorial tasks for manual addition
    janitorial_tasks = db.query(JanitorialTask).filter(JanitorialTask.task_type == "manual").all()
    
    # Calculate summary stats
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.finished_at])
    below_par_items = len([item for item in inventory_day_items if item.quantity < item.inventory_item.par_level])
    
    return templates.TemplateResponse("inventory_day.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
        "employees": employees,
        "categories": categories,
        "janitorial_tasks": janitorial_tasks,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "below_par_items": below_par_items
    })

@router.post("/day/{day_id}/tasks/{task_id}/start")
async def start_task(
    day_id: int,
    task_id: int,
    request: Request,
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
        "id": task.id,
        "status": "in_progress",
        "assigned_to": current_user.username,
        "started_at": task.started_at.isoformat()
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/pause")
async def pause_task(
    day_id: int,
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.started_at:
        raise HTTPException(status_code=400, detail="Task not started")
    
    # Update task timing
    task.is_paused = True
    task.paused_at = datetime.utcnow()
    
    db.commit()
    
    # Broadcast update via WebSocket
    await manager.broadcast_task_update(day_id, {
        "id": task.id,
        "status": "paused",
        "paused_at": task.paused_at.isoformat()
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/resume")
async def resume_task(
    day_id: int,
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.is_paused:
        raise HTTPException(status_code=400, detail="Task not paused")
    
    # Calculate pause duration and add to total
    if task.paused_at:
        pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
        task.total_pause_time += pause_duration
    
    # Resume task
    task.is_paused = False
    task.paused_at = None
    
    db.commit()
    
    # Broadcast update via WebSocket
    await manager.broadcast_task_update(day_id, {
        "id": task.id,
        "status": "in_progress"
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/finish")
async def finish_task(
    day_id: int,
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.started_at:
        raise HTTPException(status_code=400, detail="Task not started")
    
    # Update task timing
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    task.paused_at = None
    
    db.commit()
    
    # Broadcast update via WebSocket
    await manager.broadcast_task_update(day_id, {
        "id": task.id,
        "status": "completed",
        "finished_at": task.finished_at.isoformat()
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/finalize")
async def finalize_day(
    day_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day.finalized = True
    inventory_day.finalized_at = datetime.utcnow()
    inventory_day.finalized_by_id = current_user.id
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/reports/{day_id}", status_code=302)

@router.get("/reports/{day_id}", response_class=HTMLResponse)
async def inventory_report(day_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    # Get inventory day items
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item)
    ).filter(InventoryDayItem.day_id == day_id).all()
    
    # Get tasks for this day
    tasks = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.batch),
        joinedload(Task.inventory_item),
        joinedload(Task.janitorial_task)
    ).filter(Task.day_id == day_id).all()
    
    # Get employees
    employees = db.query(User).all()
    
    # Calculate summary stats
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.finished_at])
    below_par_items = len([item for item in inventory_day_items if item.quantity < item.inventory_item.par_level])
    
    return templates.TemplateResponse("inventory_report.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
        "employees": employees,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "below_par_items": below_par_items
    })

@router.get("/items/{item_id}/edit", response_class=HTMLResponse)
async def inventory_item_edit_page(item_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(require_admin)):
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
async def delete_inventory_item(item_id: int, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    db.delete(item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@router.get("/janitorial_tasks/{task_id}/delete")
async def delete_janitorial_task(task_id: int, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    janitorial_task = db.query(JanitorialTask).filter(JanitorialTask.id == task_id).first()
    if not janitorial_task:
        raise HTTPException(status_code=404, detail="Janitorial task not found")
    
    db.delete(janitorial_task)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@router.get("/day/{day_id}/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(day_id: int, task_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    task = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.batch),
        joinedload(Task.inventory_item),
        joinedload(Task.janitorial_task)
    ).filter(Task.id == task_id, Task.day_id == day_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get employees for display
    employees = db.query(User).all()
    
    # Get task summary if available
    task_summary = None
    if hasattr(task, 'get_task_summary'):
        task_summary = task.get_task_summary(db)
    
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "task": task,
        "employees": employees,
        "task_summary": task_summary
    })