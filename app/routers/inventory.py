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
    
    # Add daily janitorial tasks only (no batch tasks until inventory is taken)
    daily_janitorial_tasks = db.query(JanitorialTask).filter(JanitorialTask.task_type == "daily").all()
    for janitorial_task in daily_janitorial_tasks:
        task = Task(
            day_id=inventory_day.id,
            janitorial_task_id=janitorial_task.id,
            description=janitorial_task.title
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
    
    # Get batches for manual task linking
    batches = db.query(Batch).all()
    
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
        "batches": batches,
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

@router.post("/day/{day_id}/update")
async def update_inventory_day(
    day_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    form_data = await request.form()
    
    # Update inventory quantities
    for key, value in form_data.items():
        if key.startswith('quantity_'):
            item_id = int(key.split('_')[1])
            quantity = float(value) if value else 0.0
            
            day_item = db.query(InventoryDayItem).filter(
                InventoryDayItem.day_id == day_id,
                InventoryDayItem.inventory_item_id == item_id
            ).first()
            
            if day_item:
                day_item.quantity = quantity
    
    # Generate tasks if requested
    if 'generate_tasks' in form_data:
        # Remove only unstarted batch tasks (preserve started/completed and janitorial tasks)
        existing_tasks = db.query(Task).filter(Task.day_id == day_id).all()
        for task in existing_tasks:
            # Remove unstarted batch tasks only
            if (task.batch_id and not task.started_at and not task.finished_at and 
                not task.janitorial_task_id):
                db.delete(task)
        
        db.flush()  # Apply deletions before creating new tasks
        
        # Create new tasks for items below par
        inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
        for day_item in inventory_day_items:
            if day_item.quantity < day_item.inventory_item.par_level and day_item.inventory_item.batch:
                # Check if task already exists for this item
                existing_task = db.query(Task).filter(
                    Task.day_id == day_id,
                    Task.inventory_item_id == day_item.inventory_item.id,
                    Task.batch_id == day_item.inventory_item.batch.id
                ).first()
                
                if not existing_task:
                    task = Task(
                        day_id=day_id,
                        inventory_item_id=day_item.inventory_item.id,
                        batch_id=day_item.inventory_item.batch.id,
                        description=f"Make {day_item.inventory_item.name}"
                    )
                    db.add(task)
    
    db.commit()
    
    # Broadcast inventory update via WebSocket
    await manager.broadcast_inventory_update(day_id, {
        "action": "inventory_updated",
        "day_id": day_id
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/assign")
async def assign_task(
    day_id: int,
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get form data to handle multiple employee assignments
    form_data = await request.form()
    assigned_employees = form_data.getlist('assigned_employees')
    
    if not assigned_employees:
        raise HTTPException(status_code=400, detail="No employees selected")
    
    # Store employee IDs as comma-separated string
    task.assigned_employee_ids = ",".join(assigned_employees)
    
    # For backward compatibility, also set assigned_to_id to first employee
    task.assigned_to_id = int(assigned_employees[0])
    
    db.commit()
    
    # Broadcast update via WebSocket
    assigned_users = db.query(User).filter(User.id.in_([int(emp_id) for emp_id in assigned_employees])).all()
    assigned_names = [user.username for user in assigned_users]
    
    await manager.broadcast_task_update(day_id, {
        "task_id": task.id,
        "action": "assigned",
        "assigned_to": ", ".join(assigned_names)
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/start_with_scale")
async def start_task_with_scale(
    day_id: int,
    task_id: int,
    selected_scale: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Parse scale factor from selected_scale
    scale_mapping = {
        "full": 1.0,
        "double": 2.0,
        "half": 0.5,
        "quarter": 0.25,
        "eighth": 0.125,
        "sixteenth": 0.0625
    }
    
    scale_factor = scale_mapping.get(selected_scale, 1.0)
    
    # Update task with scale and start it
    task.scale_factor = scale_factor
    task.started_at = datetime.utcnow()
    task.assigned_to_id = current_user.id
    task.is_paused = False
    task.paused_at = None
    
    db.commit()
    
    # Broadcast update via WebSocket
    await manager.broadcast_task_update(day_id, {
        "task_id": task.id,
        "action": "started_with_scale",
        "scale_factor": scale_factor,
        "assigned_to": current_user.username,
        "started_at": task.started_at.isoformat()
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/finish_with_amount")
async def finish_task_with_amount(
    day_id: int,
    task_id: int,
    made_amount: float = Form(...),
    made_unit: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update task with made amount and finish it
    task.made_amount = made_amount
    task.made_unit = made_unit
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    task.paused_at = None
    
    db.commit()
    
    # Broadcast update via WebSocket
    await manager.broadcast_task_update(day_id, {
        "task_id": task.id,
        "action": "finished_with_amount",
        "made_amount": made_amount,
        "made_unit": made_unit,
        "finished_at": task.finished_at.isoformat()
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/notes")
async def update_task_notes(
    day_id: int,
    task_id: int,
    notes: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.notes = notes if notes.strip() else None
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)

@router.post("/day/{day_id}/finalize")
async def finalize_inventory_day(
    day_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day.finalized = True
    inventory_day.finalized_at = datetime.utcnow()
    db.commit()
    
    # Broadcast finalization via WebSocket
    await manager.broadcast_to_day(day_id, {
        "type": "day_finalized",
        "day_id": day_id,
        "finalized_at": inventory_day.finalized_at.isoformat()
    })
    
    return RedirectResponse(url=f"/inventory/reports/{day_id}", status_code=302)

@router.post("/day/{day_id}/regenerate_tasks")
async def regenerate_tasks(
    day_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    # Remove ALL tasks completely - true regeneration
    existing_tasks = db.query(Task).filter(Task.day_id == day_id).all()
    for task in existing_tasks:
        db.delete(task)
    
    db.flush()  # Apply deletions
    
    # Recreate daily janitorial tasks
    daily_janitorial_tasks = db.query(JanitorialTask).filter(JanitorialTask.task_type == "daily").all()
    for janitorial_task in daily_janitorial_tasks:
        task = Task(
            day_id=day_id,
            janitorial_task_id=janitorial_task.id,
            description=janitorial_task.title
        )
        db.add(task)
    
    # Reset all inventory quantities to 0
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    for day_item in inventory_day_items:
        day_item.quantity = 0.0
    
    db.commit()
    
    # Broadcast update via WebSocket
    await manager.broadcast_to_day(day_id, {
        "type": "tasks_regenerated",
        "day_id": day_id
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/add_manual_task")
async def add_manual_task(
    day_id: int,
    description: str = Form(...),
    category_id: int = Form(None),
    batch_id: int = Form(None),
    janitorial_task_id: int = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    # If janitorial_task_id is provided, use the janitorial task's title as description
    if janitorial_task_id:
        janitorial_task = db.query(JanitorialTask).filter(JanitorialTask.id == janitorial_task_id).first()
        if janitorial_task:
            description = janitorial_task.title
    
    task = Task(
        day_id=day_id,
        description=description,
        category_id=category_id if category_id else None,
        batch_id=batch_id if batch_id else None,
        janitorial_task_id=janitorial_task_id if janitorial_task_id else None
    )
    
    db.add(task)
    db.commit()
    
    # Broadcast update via WebSocket
    await manager.broadcast_task_update(day_id, {
        "task_id": task.id,
        "action": "manual_task_added",
        "description": description
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.get("/day/{day_id}/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(
    day_id: int,
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate task summary if needed
    task_summary = None
    if task.inventory_item:
        # Get the day item for this inventory item
        day_item = db.query(InventoryDayItem).filter(
            InventoryDayItem.day_id == day_id,
            InventoryDayItem.inventory_item_id == task.inventory_item.id
        ).first()
        
        if day_item:
            task_summary = {
                "par_level": task.inventory_item.par_level,
                "par_unit_name": task.inventory_item.par_unit_name.name if task.inventory_item.par_unit_name else "units",
                "initial_inventory": day_item.quantity,
                "made_amount": task.made_amount,
                "made_unit": task.made_unit,
                "par_unit_equals_type": task.inventory_item.par_unit_equals_type,
                "par_unit_equals": task.inventory_item.par_unit_equals_calculated,
                "par_unit_equals_unit": task.inventory_item.par_unit_equals_unit
            }
            
            # Calculate final inventory and conversions
            if task.made_amount and task.inventory_item.par_unit_name:
                # Convert made amount to par units if possible
                made_par_units = 0
                if task.inventory_item.par_unit_equals_calculated:
                    made_par_units = task.made_amount / task.inventory_item.par_unit_equals_calculated
                
                task_summary.update({
                    "made_par_units": made_par_units,
                    "final_inventory": day_item.quantity + made_par_units,
                    "made_amount_par_units": made_par_units
                })
    
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "task": task,
        "employees": employees,
        "task_summary": task_summary
    })

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