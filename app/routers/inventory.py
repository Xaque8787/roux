from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from datetime import datetime, date, timedelta
from ..database import get_db
from ..dependencies import require_manager_or_admin, get_current_user, require_admin
from ..models import (
    InventoryItem, InventoryDay, InventoryDayItem, Task, User, Category, 
    Batch, ParUnitName
)
from ..websocket import manager
from ..auth import create_jwt

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
        InventoryDay.date >= thirty_days_ago,
        InventoryDay.finalized == True
    ).order_by(InventoryDay.date.desc()).limit(10).all()
    
    # Get all inventory items
    inventory_items = db.query(InventoryItem).all()
    
    # Get all employees for day creation
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get categories and other data for forms
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    par_unit_names = db.query(ParUnitName).all()
    
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
        "today_date": today.isoformat(),
        "janitorial_tasks": []  # Empty list since model doesn't exist
    })

@router.post("/new_day")
async def create_inventory_day(
    request: Request,
    date: date = Form(...),
    employees_working: list = Form(...),
    global_notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if existing_day:
        return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=302)
    
    # Create new inventory day
    inventory_day = InventoryDay(
        date=date,
        employees_working=','.join(map(str, employees_working)),
        global_notes=global_notes if global_notes else None
    )
    
    db.add(inventory_day)
    db.flush()  # Get the ID
    
    # Create inventory day items for all inventory items
    inventory_items = db.query(InventoryItem).all()
    for item in inventory_items:
        day_item = InventoryDayItem(
            day_id=inventory_day.id,
            inventory_item_id=item.id,
            quantity=0.0  # Default quantity
        )
        db.add(day_item)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

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
    
    # Get inventory day items
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item)
    ).filter(InventoryDayItem.day_id == day_id).all()
    
    # Get tasks for this day
    tasks = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.batch),
        joinedload(Task.inventory_item),
        joinedload(Task.category)
    ).filter(Task.day_id == day_id).all()
    
    # Get all employees for assignment
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get categories and batches for manual task creation
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    
    # Create JWT token for WebSocket authentication
    token = create_jwt(data={"sub": current_user.username})
    
    # Calculate task summaries for completed tasks
    task_summaries = {}
    for task in tasks:
        if task.finished_at and task.inventory_item:
            # Get the day item for this inventory item
            day_item = next((di for di in inventory_day_items if di.inventory_item_id == task.inventory_item.id), None)
            if day_item:
                summary = {
                    "par_level": task.inventory_item.par_level,
                    "par_unit_name": task.inventory_item.par_unit_name.name if task.inventory_item.par_unit_name else "units",
                    "initial_inventory": day_item.quantity,
                    "made_amount": task.made_amount,
                    "made_unit": task.made_unit,
                    "final_inventory": day_item.quantity + (task.made_amount_par_units or 0),
                    "par_unit_equals": task.inventory_item.par_unit_equals_calculated,
                    "par_unit_equals_unit": task.inventory_item.par_unit_equals_unit,
                    "par_unit_equals_type": task.inventory_item.par_unit_equals_type
                }
                task_summaries[task.id] = summary
    
    return templates.TemplateResponse("inventory_day.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
        "employees": employees,
        "categories": categories,
        "batches": batches,
        "task_summaries": task_summaries,
        "websocket_token": token
    })

@router.post("/day/{day_id}/update")
async def update_inventory_day(
    day_id: int,
    request: Request,
    global_notes: str = Form(""),
    force_regenerate: bool = Form(False),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot update finalized day")
    
    # Update global notes
    inventory_day.global_notes = global_notes if global_notes else None
    
    # Get form data
    form_data = await request.form()
    
    # Update inventory quantities and overrides
    for key, value in form_data.items():
        if key.startswith("item_"):
            item_id = int(key.split("_")[1])
            quantity = float(value) if value else 0.0
            
            day_item = db.query(InventoryDayItem).filter(
                InventoryDayItem.day_id == day_id,
                InventoryDayItem.inventory_item_id == item_id
            ).first()
            
            if day_item:
                day_item.quantity = quantity
        
        elif key.startswith("override_create_"):
            item_id = int(key.split("_")[2])
            day_item = db.query(InventoryDayItem).filter(
                InventoryDayItem.day_id == day_id,
                InventoryDayItem.inventory_item_id == item_id
            ).first()
            if day_item:
                day_item.override_create_task = True
        
        elif key.startswith("override_no_task_"):
            item_id = int(key.split("_")[3])
            day_item = db.query(InventoryDayItem).filter(
                InventoryDayItem.day_id == day_id,
                InventoryDayItem.inventory_item_id == item_id
            ).first()
            if day_item:
                day_item.override_no_task = True
    
    # Clear overrides that weren't checked
    all_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    for day_item in all_day_items:
        override_create_key = f"override_create_{day_item.inventory_item_id}"
        override_no_task_key = f"override_no_task_{day_item.inventory_item_id}"
        
        if override_create_key not in form_data:
            day_item.override_create_task = False
        if override_no_task_key not in form_data:
            day_item.override_no_task = False
    
    db.commit()
    
    # Generate tasks based on inventory levels
    generate_inventory_tasks(db, inventory_day, force_regenerate)
    
    # Broadcast inventory update via WebSocket
    await manager.broadcast_inventory_update(day_id, {
        "action": "updated",
        "updated_by": current_user.full_name or current_user.username
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

def generate_inventory_tasks(db: Session, inventory_day: InventoryDay, force_regenerate: bool = False):
    """Generate tasks based on inventory levels and overrides"""
    
    if force_regenerate:
        # Delete existing auto-generated tasks (keep manual tasks)
        db.query(Task).filter(
            Task.day_id == inventory_day.id,
            Task.is_manual == False
        ).delete()
    
    # Get inventory day items
    day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item)
    ).filter(InventoryDayItem.day_id == inventory_day.id).all()
    
    for day_item in day_items:
        item = day_item.inventory_item
        
        # Check if task should be created
        should_create_task = False
        
        if day_item.override_no_task:
            should_create_task = False
        elif day_item.override_create_task:
            should_create_task = True
        else:
            # Auto-generate based on par level
            should_create_task = day_item.quantity < item.par_level
        
        if should_create_task:
            # Check if task already exists for this item
            existing_task = db.query(Task).filter(
                Task.day_id == inventory_day.id,
                Task.inventory_item_id == item.id
            ).first()
            
            if not existing_task:
                # Create task
                task_description = f"Make {item.name}"
                if item.batch:
                    task_description = f"Make {item.batch.recipe.name} for {item.name}"
                
                task = Task(
                    day_id=inventory_day.id,
                    description=task_description,
                    inventory_item_id=item.id,
                    batch_id=item.batch_id if item.batch_id else None,
                    requires_made_amount=bool(item.batch_id),
                    requires_scale_selection=(item.batch and item.batch.can_be_scaled),
                    is_manual=False
                )
                
                db.add(task)
    
    db.commit()

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
    inventory_day.finalized_by_id = current_user.id
    
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@router.get("/day/{day_id}/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail_page(
    day_id: int,
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    task = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.batch),
        joinedload(Task.inventory_item),
        joinedload(Task.category)
    ).filter(Task.id == task_id, Task.day_id == day_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate task summary if completed
    task_summary = None
    if task.finished_at and task.inventory_item:
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
                "made_amount_par_units": task.made_amount_par_units or 0,
                "final_inventory": day_item.quantity + (task.made_amount_par_units or 0),
                "par_unit_equals": task.inventory_item.par_unit_equals_calculated,
                "par_unit_equals_unit": task.inventory_item.par_unit_equals_unit,
                "par_unit_equals_type": task.inventory_item.par_unit_equals_type
            }
    
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "task": task,
        "employees": employees,
        "task_summary": task_summary
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
    
    if task.status != "not_started":
        raise HTTPException(status_code=400, detail="Task already started")
    
    task.status = "in_progress"
    task.started_at = datetime.utcnow()
    task.assigned_to_id = current_user.id
    
    db.commit()
    
    # Broadcast task update
    await manager.broadcast_task_update(day_id, {
        "task_id": task_id,
        "action": "started",
        "started_by": current_user.full_name or current_user.username
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
    
    if task.status != "in_progress":
        raise HTTPException(status_code=400, detail="Task is not in progress")
    
    task.status = "paused"
    task.paused_at = datetime.utcnow()
    task.is_paused = True
    
    # Calculate pause time
    if task.started_at:
        current_time = datetime.utcnow()
        if task.total_pause_time is None:
            task.total_pause_time = 0
        
        # Add time since last resume (or start if never paused)
        last_resume = task.resumed_at or task.started_at
        active_time = (current_time - last_resume).total_seconds()
        # Don't add to pause time here - we track active time
    
    db.commit()
    
    # Broadcast task update
    await manager.broadcast_task_update(day_id, {
        "task_id": task_id,
        "action": "paused",
        "paused_by": current_user.full_name or current_user.username
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
    
    if task.status != "paused":
        raise HTTPException(status_code=400, detail="Task is not paused")
    
    task.status = "in_progress"
    task.resumed_at = datetime.utcnow()
    task.is_paused = False
    
    # Calculate pause duration and add to total
    if task.paused_at:
        pause_duration = (task.resumed_at - task.paused_at).total_seconds()
        if task.total_pause_time is None:
            task.total_pause_time = 0
        task.total_pause_time += pause_duration
    
    db.commit()
    
    # Broadcast task update
    await manager.broadcast_task_update(day_id, {
        "task_id": task_id,
        "action": "resumed",
        "resumed_by": current_user.full_name or current_user.username
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
    
    if task.status not in ["in_progress", "paused"]:
        raise HTTPException(status_code=400, detail="Task cannot be finished")
    
    task.status = "completed"
    task.finished_at = datetime.utcnow()
    task.assigned_to_id = current_user.id
    
    # Calculate total time
    if task.started_at:
        total_seconds = (task.finished_at - task.started_at).total_seconds()
        if task.total_pause_time:
            total_seconds -= task.total_pause_time
        task.total_time_minutes = max(0, int(total_seconds / 60))
        
        # Calculate labor cost
        if task.assigned_to:
            task.labor_cost = (task.total_time_minutes / 60) * task.assigned_to.hourly_wage
    
    db.commit()
    
    # Broadcast task update
    await manager.broadcast_task_update(day_id, {
        "task_id": task_id,
        "action": "finished",
        "finished_by": current_user.full_name or current_user.username
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/new")
async def create_manual_task(
    day_id: int,
    request: Request,
    description: str = Form(...),
    assigned_to_ids: list = Form([]),
    inventory_item_id: int = Form(None),
    batch_id: int = Form(None),
    category_id: int = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot add tasks to finalized day")
    
    # Create manual task
    task = Task(
        day_id=day_id,
        description=description,
        inventory_item_id=inventory_item_id if inventory_item_id else None,
        batch_id=batch_id if batch_id else None,
        category_id=category_id if category_id else None,
        requires_made_amount=bool(batch_id),
        requires_scale_selection=False,  # Manual tasks don't require scale selection
        is_manual=True
    )
    
    # Handle multiple employee assignment
    if assigned_to_ids:
        if len(assigned_to_ids) == 1:
            task.assigned_to_id = assigned_to_ids[0]
        else:
            task.assigned_employee_ids = ','.join(map(str, assigned_to_ids))
    
    db.add(task)
    db.commit()
    
    # Broadcast task creation
    await manager.broadcast_task_update(day_id, {
        "task_id": task.id,
        "action": "created",
        "created_by": current_user.full_name or current_user.username
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

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
    
    # Get inventory day items
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item)
    ).filter(InventoryDayItem.day_id == day_id).all()
    
    # Get tasks
    tasks = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.batch)
    ).filter(Task.day_id == day_id).all()
    
    # Get employees
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == "completed"])
    below_par_items = len([di for di in inventory_day_items if di.quantity < di.inventory_item.par_level])
    
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
    
    # Delete related day items first
    db.query(InventoryDayItem).filter(InventoryDayItem.inventory_item_id == item_id).delete()
    
    # Delete related tasks
    db.query(Task).filter(Task.inventory_item_id == item_id).delete()
    
    db.delete(item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)