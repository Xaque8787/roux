from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from datetime import datetime, date, timedelta
from ..database import get_db
from ..dependencies import require_manager_or_admin, get_current_user, require_admin
from ..models import (
    InventoryItem, InventoryDay, InventoryDayItem, Task, User, Batch, Category, 
    JanitorialTask, JanitorialDayItem, ParUnitName
)
from ..websocket import manager
import json

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
        InventoryDay.finalized == True,
        InventoryDay.date >= thirty_days_ago
    ).order_by(InventoryDay.date.desc()).limit(10).all()
    
    # Get all inventory items
    inventory_items = db.query(InventoryItem).all()
    
    # Get all employees for day creation
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get all batches for linking
    batches = db.query(Batch).all()
    
    # Get categories for inventory items
    categories = db.query(Category).filter(Category.type == "inventory").all()
    
    # Get par unit names
    par_unit_names = db.query(ParUnitName).all()
    
    # Get janitorial tasks
    janitorial_tasks = db.query(JanitorialTask).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "current_user": current_user,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "inventory_items": inventory_items,
        "employees": employees,
        "batches": batches,
        "categories": categories,
        "par_unit_names": par_unit_names,
        "janitorial_tasks": janitorial_tasks,
        "today_date": today.isoformat()
    })

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
        employees_working=",".join(employees_working),
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
            quantity=0.0  # Default to 0, will be updated by user
        )
        db.add(day_item)
    
    # Create janitorial day items for all janitorial tasks
    janitorial_tasks = db.query(JanitorialTask).all()
    for janitorial_task in janitorial_tasks:
        janitorial_day_item = JanitorialDayItem(
            day_id=inventory_day.id,
            janitorial_task_id=janitorial_task.id,
            include_task=(janitorial_task.task_type == 'daily')  # Auto-include daily tasks
        )
        db.add(janitorial_day_item)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

@router.get("/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_page(day_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    # Get inventory day items
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item)
    ).filter(InventoryDayItem.day_id == day_id).all()
    
    # Get janitorial day items
    janitorial_day_items = db.query(JanitorialDayItem).options(
        joinedload(JanitorialDayItem.janitorial_task)
    ).filter(JanitorialDayItem.day_id == day_id).all()
    
    # Get tasks for this day
    tasks = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.batch),
        joinedload(Task.inventory_item),
        joinedload(Task.janitorial_task),
        joinedload(Task.category)
    ).filter(Task.day_id == day_id).all()
    
    # Get all employees for assignment
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get all batches for manual task creation
    batches = db.query(Batch).all()
    
    # Get categories for manual task creation
    categories = db.query(Category).filter(Category.type == "inventory").all()
    
    # Calculate task summaries for completed tasks
    task_summaries = {}
    for task in tasks:
        if task.status == 'completed' and task.inventory_item:
            summary = task.calculate_task_summary(db)
            if summary:
                task_summaries[task.id] = summary
    
    # Get the access token for WebSocket authentication
    access_token = request.cookies.get("access_token", "")
    
    return templates.TemplateResponse("inventory_day.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "janitorial_day_items": janitorial_day_items,
        "tasks": tasks,
        "employees": employees,
        "batches": batches,
        "categories": categories,
        "task_summaries": task_summaries,
        "access_token": access_token  # Pass token to template
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
    
    # Update inventory quantities
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    for day_item in inventory_day_items:
        quantity_key = f"item_{day_item.inventory_item_id}"
        if quantity_key in form_data:
            day_item.quantity = float(form_data[quantity_key])
        
        # Handle override flags
        override_create_key = f"override_create_{day_item.inventory_item_id}"
        override_no_task_key = f"override_no_task_{day_item.inventory_item_id}"
        
        day_item.override_create_task = override_create_key in form_data
        day_item.override_no_task = override_no_task_key in form_data
    
    # Update janitorial task inclusion
    janitorial_day_items = db.query(JanitorialDayItem).filter(JanitorialDayItem.day_id == day_id).all()
    for janitorial_day_item in janitorial_day_items:
        if janitorial_day_item.janitorial_task.task_type == 'manual':
            include_key = f"janitorial_{janitorial_day_item.janitorial_task_id}"
            janitorial_day_item.include_task = include_key in form_data
    
    db.commit()
    
    # Generate or regenerate tasks
    if force_regenerate:
        # Delete existing auto-generated tasks (keep manual tasks)
        db.query(Task).filter(
            Task.day_id == day_id,
            Task.is_manual == False
        ).delete()
    
    # Generate tasks based on inventory levels and janitorial tasks
    generate_tasks_for_day(db, inventory_day)
    
    # Broadcast inventory update via WebSocket
    await manager.broadcast_inventory_update(day_id, {
        "action": "updated",
        "updated_by": current_user.full_name or current_user.username,
        "day_id": day_id
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

def generate_tasks_for_day(db: Session, inventory_day: InventoryDay):
    """Generate tasks based on inventory levels and janitorial tasks"""
    
    # Get inventory day items
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item)
    ).filter(InventoryDayItem.day_id == inventory_day.id).all()
    
    # Generate tasks for items below par or with overrides
    for day_item in inventory_day_items:
        item = day_item.inventory_item
        
        # Check if task should be created
        should_create_task = False
        
        if day_item.override_no_task:
            # Explicitly no task
            continue
        elif day_item.override_create_task:
            # Force create task
            should_create_task = True
        elif day_item.quantity < item.par_level:
            # Below par level
            should_create_task = True
        
        if should_create_task:
            # Check if task already exists for this item
            existing_task = db.query(Task).filter(
                Task.day_id == inventory_day.id,
                Task.inventory_item_id == item.id
            ).first()
            
            if not existing_task:
                # Create task description
                if item.batch:
                    description = f"Make {item.name} ({item.batch.recipe.name})"
                    requires_made_amount = True
                    requires_scale_selection = item.batch.can_be_scaled
                else:
                    description = f"Restock {item.name}"
                    requires_made_amount = False
                    requires_scale_selection = False
                
                task = Task(
                    day_id=inventory_day.id,
                    description=description,
                    inventory_item_id=item.id,
                    batch_id=item.batch_id if item.batch else None,
                    requires_made_amount=requires_made_amount,
                    requires_scale_selection=requires_scale_selection,
                    is_manual=False
                )
                
                db.add(task)
    
    # Generate janitorial tasks
    janitorial_day_items = db.query(JanitorialDayItem).options(
        joinedload(JanitorialDayItem.janitorial_task)
    ).filter(
        JanitorialDayItem.day_id == inventory_day.id,
        JanitorialDayItem.include_task == True
    ).all()
    
    for janitorial_day_item in janitorial_day_items:
        janitorial_task = janitorial_day_item.janitorial_task
        
        # Check if task already exists
        existing_task = db.query(Task).filter(
            Task.day_id == inventory_day.id,
            Task.janitorial_task_id == janitorial_task.id
        ).first()
        
        if not existing_task:
            task = Task(
                day_id=inventory_day.id,
                description=janitorial_task.title,
                janitorial_task_id=janitorial_task.id,
                requires_made_amount=False,
                requires_scale_selection=False,
                is_manual=False
            )
            
            db.add(task)
    
    db.commit()

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
    inventory_item = InventoryItem(
        name=name,
        par_unit_name_id=par_unit_name_id if par_unit_name_id else None,
        par_level=par_level,
        batch_id=batch_id if batch_id else None,
        par_unit_equals_type=par_unit_equals_type,
        par_unit_equals_amount=par_unit_equals_amount if par_unit_equals_type == "custom" else None,
        par_unit_equals_unit=par_unit_equals_unit if par_unit_equals_type == "custom" else None,
        category_id=category_id if category_id else None
    )
    
    db.add(inventory_item)
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
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

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
        joinedload(Task.janitorial_task),
        joinedload(Task.category)
    ).filter(Task.day_id == day_id).all()
    
    # Get all employees for reference
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate summary statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == 'completed'])
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

# Task management endpoints
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
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot add tasks to finalized day")
    
    # Determine if task requires made amount based on linked batch
    requires_made_amount = False
    requires_scale_selection = False
    
    if batch_id:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if batch:
            requires_made_amount = True
            requires_scale_selection = batch.can_be_scaled
    elif inventory_item_id:
        item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
        if item and item.batch:
            requires_made_amount = True
            requires_scale_selection = item.batch.can_be_scaled
    
    task = Task(
        day_id=day_id,
        description=description,
        inventory_item_id=inventory_item_id if inventory_item_id else None,
        batch_id=batch_id if batch_id else None,
        category_id=category_id if category_id else None,
        assigned_employee_ids=",".join(assigned_to_ids) if assigned_to_ids else None,
        requires_made_amount=requires_made_amount,
        requires_scale_selection=requires_scale_selection,
        is_manual=True
    )
    
    db.add(task)
    db.commit()
    
    # Broadcast task creation via WebSocket
    await manager.broadcast_task_update(day_id, {
        "action": "created",
        "task_id": task.id,
        "description": task.description,
        "created_by": current_user.full_name or current_user.username
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/assign")
async def assign_task(
    day_id: int,
    task_id: int,
    request: Request,
    assigned_to_ids: list = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot modify finalized day")
    
    task.assigned_employee_ids = ",".join(assigned_to_ids) if assigned_to_ids else None
    db.commit()
    
    # Broadcast task assignment via WebSocket
    await manager.broadcast_task_update(day_id, {
        "action": "assigned",
        "task_id": task.id,
        "description": task.description,
        "assigned_by": current_user.full_name or current_user.username,
        "assigned_to_ids": assigned_to_ids
    })
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

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
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot modify finalized day")
    
    if task.status != "not_started":
        raise HTTPException(status_code=400, detail="Task is not in 'not_started' status")
    
    task.status = "in_progress"
    task.started_at = datetime.utcnow()
    task.assigned_to_id = current_user.id
    
    # Add current user to assigned employees if not already there
    if task.assigned_employee_ids:
        employee_ids = task.assigned_employee_ids.split(',')
        if str(current_user.id) not in employee_ids:
            employee_ids.append(str(current_user.id))
            task.assigned_employee_ids = ','.join(employee_ids)
    else:
        task.assigned_employee_ids = str(current_user.id)
    
    db.commit()
    
    # Broadcast task start via WebSocket
    await manager.broadcast_task_update(day_id, {
        "action": "started",
        "task_id": task.id,
        "description": task.description,
        "started_by": current_user.full_name or current_user.username
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
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot modify finalized day")
    
    if task.status != "not_started":
        raise HTTPException(status_code=400, detail="Task is not in 'not_started' status")
    
    # Parse scale factor
    scale_factors = {
        'full': 1.0,
        'double': 2.0,
        'half': 0.5,
        'quarter': 0.25,
        'eighth': 0.125,
        'sixteenth': 0.0625
    }
    
    scale_factor = scale_factors.get(selected_scale, 1.0)
    
    task.status = "in_progress"
    task.started_at = datetime.utcnow()
    task.assigned_to_id = current_user.id
    task.selected_scale = selected_scale
    task.scale_factor = scale_factor
    
    # Add current user to assigned employees if not already there
    if task.assigned_employee_ids:
        employee_ids = task.assigned_employee_ids.split(',')
        if str(current_user.id) not in employee_ids:
            employee_ids.append(str(current_user.id))
            task.assigned_employee_ids = ','.join(employee_ids)
    else:
        task.assigned_employee_ids = str(current_user.id)
    
    db.commit()
    
    # Broadcast task start via WebSocket
    await manager.broadcast_task_update(day_id, {
        "action": "started_with_scale",
        "task_id": task.id,
        "description": task.description,
        "selected_scale": selected_scale,
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
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot modify finalized day")
    
    if task.status != "in_progress":
        raise HTTPException(status_code=400, detail="Task is not in progress")
    
    task.status = "paused"
    task.paused_at = datetime.utcnow()
    task.is_paused = True
    
    # Calculate pause time
    if task.started_at:
        pause_duration = (datetime.utcnow() - task.started_at).total_seconds()
        task.total_pause_time += pause_duration
    
    db.commit()
    
    # Broadcast task pause via WebSocket
    await manager.broadcast_task_update(day_id, {
        "action": "paused",
        "task_id": task.id,
        "description": task.description,
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
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot modify finalized day")
    
    if task.status != "paused":
        raise HTTPException(status_code=400, detail="Task is not paused")
    
    task.status = "in_progress"
    task.is_paused = False
    task.started_at = datetime.utcnow()  # Reset start time for new session
    
    db.commit()
    
    # Broadcast task resume via WebSocket
    await manager.broadcast_task_update(day_id, {
        "action": "resumed",
        "task_id": task.id,
        "description": task.description,
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
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot modify finalized day")
    
    if task.status not in ["in_progress", "paused"]:
        raise HTTPException(status_code=400, detail="Task is not in progress or paused")
    
    task.status = "completed"
    task.finished_at = datetime.utcnow()
    
    # Calculate total time and labor cost
    if task.started_at:
        total_time = (task.finished_at - task.started_at).total_seconds() / 60  # minutes
        task.total_time_minutes = int(total_time - (task.total_pause_time / 60))
        
        # Calculate labor cost using highest wage among assigned employees
        if task.assigned_employee_ids:
            employee_ids = [int(id) for id in task.assigned_employee_ids.split(',')]
            employees = db.query(User).filter(User.id.in_(employee_ids)).all()
            highest_wage = max(emp.hourly_wage for emp in employees) if employees else current_user.hourly_wage
        else:
            highest_wage = current_user.hourly_wage
        
        task.labor_cost = (task.total_time_minutes / 60) * highest_wage
    
    db.commit()
    
    # Broadcast task completion via WebSocket
    await manager.broadcast_task_update(day_id, {
        "action": "finished",
        "task_id": task.id,
        "description": task.description,
        "finished_by": current_user.full_name or current_user.username
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
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot modify finalized day")
    
    if task.status not in ["in_progress", "paused"]:
        raise HTTPException(status_code=400, detail="Task is not in progress or paused")
    
    task.status = "completed"
    task.finished_at = datetime.utcnow()
    task.made_amount = made_amount
    task.made_unit = made_unit
    
    # Calculate total time and labor cost
    if task.started_at:
        total_time = (task.finished_at - task.started_at).total_seconds() / 60  # minutes
        task.total_time_minutes = int(total_time - (task.total_pause_time / 60))
        
        # Calculate labor cost using highest wage among assigned employees
        if task.assigned_employee_ids:
            employee_ids = [int(id) for id in task.assigned_employee_ids.split(',')]
            employees = db.query(User).filter(User.id.in_(employee_ids)).all()
            highest_wage = max(emp.hourly_wage for emp in employees) if employees else current_user.hourly_wage
        else:
            highest_wage = current_user.hourly_wage
        
        task.labor_cost = (task.total_time_minutes / 60) * highest_wage
    
    # Update inventory if linked to inventory item
    if task.inventory_item:
        day_item = db.query(InventoryDayItem).filter(
            InventoryDayItem.day_id == day_id,
            InventoryDayItem.inventory_item_id == task.inventory_item.id
        ).first()
        
        if day_item:
            # Convert made amount to par units and add to inventory
            made_par_units = task.inventory_item.convert_to_par_units(made_amount, made_unit)
            if made_par_units:
                day_item.quantity += made_par_units
    
    db.commit()
    
    # Broadcast task completion via WebSocket
    await manager.broadcast_task_update(day_id, {
        "action": "finished",
        "task_id": task.id,
        "description": task.description,
        "made_amount": made_amount,
        "made_unit": made_unit,
        "finished_by": current_user.full_name or current_user.username
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
    
    task = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.batch),
        joinedload(Task.inventory_item),
        joinedload(Task.janitorial_task),
        joinedload(Task.category)
    ).filter(Task.id == task_id, Task.day_id == day_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get all employees for reference
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate task summary if completed and has inventory item
    task_summary = None
    if task.status == 'completed' and task.inventory_item:
        task_summary = task.calculate_task_summary(db)
    
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "task": task,
        "employees": employees,
        "task_summary": task_summary
    })

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
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot modify finalized day")
    
    task.notes = notes if notes else None
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)