from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from datetime import date, timedelta
from ..database import get_db
from ..dependencies import require_manager_or_admin, get_current_user, require_admin
from ..models import (InventoryItem, Category, Batch, ParUnitName, InventoryDay,
                     InventoryDayItem, Task, User, JanitorialTask, JanitorialTaskDay)
from ..utils.helpers import get_today_date
from datetime import datetime

# Import SSE broadcasting functions
from ..sse import broadcast_task_update, broadcast_inventory_update, broadcast_day_update

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def inventory_page(request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    inventory_items = db.query(InventoryItem).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    par_unit_names = db.query(ParUnitName).all()
    employees = db.query(User).filter(User.is_active == True).all()
    janitorial_tasks = db.query(JanitorialTask).all()
    
    # Get current day (today's inventory day if exists)
    today = date.today()
    current_day = db.query(InventoryDay).filter(InventoryDay.date == today).first()
    
    # Get recent finalized days (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    finalized_days = db.query(InventoryDay).filter(
        InventoryDay.finalized == True,
        InventoryDay.date >= thirty_days_ago
    ).order_by(InventoryDay.date.desc()).limit(10).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "current_user": current_user,
        "inventory_items": inventory_items,
        "categories": categories,
        "batches": batches,
        "par_unit_names": par_unit_names,
        "employees": employees,
        "current_day": current_day,
        "janitorial_tasks": janitorial_tasks,
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
    par_unit_equals_type: str = Form(...),
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
        par_unit_equals_amount=par_unit_equals_amount if par_unit_equals_type == 'custom' else None,
        par_unit_equals_unit=par_unit_equals_unit if par_unit_equals_type == 'custom' else None,
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

@router.get("/janitorial_tasks/{task_id}/delete")
async def delete_janitorial_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    janitorial_task = db.query(JanitorialTask).filter(JanitorialTask.id == task_id).first()
    if not janitorial_task:
        raise HTTPException(status_code=404, detail="Janitorial task not found")
    
    # Delete associated day tasks first
    db.query(JanitorialTaskDay).filter(JanitorialTaskDay.janitorial_task_id == task_id).delete()
    
    # Delete any tasks linked to this janitorial task
    db.query(Task).filter(Task.janitorial_task_id == task_id).delete()
    
    db.delete(janitorial_task)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@router.post("/new_day")
async def create_inventory_day(
    request: Request,
    date: str = Form(...),
    employees_working: list = Form([]),
    global_notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    # Convert string date to date object
    from datetime import date as date_class
    inventory_date_obj = date_class.fromisoformat(date)
    
    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == inventory_date_obj).first()
    if existing_day:
        return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=302)
    
    # Create new inventory day
    inventory_day = InventoryDay(
        date=inventory_date_obj,
        employees_working=','.join(map(str, employees_working)) if employees_working else '',
        global_notes=global_notes if global_notes else None
    )
    
    db.add(inventory_day)
    db.flush()  # Get the day ID
    
    # Create inventory day items for all inventory items
    inventory_items = db.query(InventoryItem).all()
    for item in inventory_items:
        day_item = InventoryDayItem(
            day_id=inventory_day.id,
            inventory_item_id=item.id,
            quantity=0.0
        )
        db.add(day_item)
    
    # Create janitorial task day items for all janitorial tasks
    janitorial_tasks = db.query(JanitorialTask).all()
    for janitorial_task in janitorial_tasks:
        janitorial_day_item = JanitorialTaskDay(
            day_id=inventory_day.id,
            janitorial_task_id=janitorial_task.id,
            include_task=(janitorial_task.task_type == 'daily')  # Auto-include daily tasks
        )
        db.add(janitorial_day_item)
    
    db.commit()
    
    # Broadcast day creation
    try:
        await broadcast_day_update(inventory_day.id, "day_created", {
            "date": inventory_date_obj.isoformat(),
            "employees_working": inventory_day.employees_working
        })
        print(f"✅ Broadcasted day creation for day {inventory_day.id}")
    except Exception as e:
        print(f"❌ Error broadcasting day creation: {e}")
        # Don't fail the request if broadcasting fails
        pass
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

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
    
    # Update day notes
    inventory_day.global_notes = global_notes if global_notes else None
    
    # Get all form data to process inventory items
    form_data = await request.form()
    
    # Process inventory item quantities
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    janitorial_day_items = db.query(JanitorialTaskDay).filter(JanitorialTaskDay.day_id == day_id).all()
    
    for day_item in inventory_day_items:
        item_key = f"item_{day_item.inventory_item_id}"
        override_create_key = f"override_create_{day_item.inventory_item_id}"
        override_no_task_key = f"override_no_task_{day_item.inventory_item_id}"
        
        if item_key in form_data:
            day_item.quantity = float(form_data[item_key]) if form_data[item_key] else 0.0
        
        day_item.override_create_task = override_create_key in form_data
        day_item.override_no_task = override_no_task_key in form_data
    
    # Process janitorial task inclusion
    for janitorial_day_item in janitorial_day_items:
        if janitorial_day_item.janitorial_task.task_type == 'manual':
            janitorial_key = f"janitorial_{janitorial_day_item.janitorial_task_id}"
            janitorial_day_item.include_task = janitorial_key in form_data
    
    # Generate tasks based on inventory levels
    generate_tasks_for_day(db, inventory_day, inventory_day_items, janitorial_day_items, force_regenerate)
    
    db.commit()
    
    # Broadcast inventory updates and task generation
    try:
        updated_items = []
        for day_item in inventory_day_items:
            updated_items.append({
                "item_id": day_item.inventory_item_id,
                "item_name": day_item.inventory_item.name,
                "quantity": day_item.quantity,
                "par_level": day_item.inventory_item.par_level,
                "status": "below_par" if day_item.quantity < day_item.inventory_item.par_level else "good"
            })
        
        await broadcast_inventory_update(inventory_day.id, 0, "inventory_batch_updated", {
            "items": updated_items,
            "force_regenerate": force_regenerate
        })
        print(f"✅ Broadcasted inventory update for day {inventory_day.id}")
        
        # Get newly created tasks to broadcast
        new_tasks = db.query(Task).filter(Task.day_id == day_id).all()
        tasks_data = []
        for task in new_tasks:
            task_info = {
                "id": task.id,
                "description": task.description,
                "status": task.status,
                "auto_generated": task.auto_generated,
                "assigned_to": task.assigned_to.full_name if task.assigned_to else None,
                "batch_name": task.batch.recipe.name if task.batch else None,
                "inventory_item": task.inventory_item.name if task.inventory_item else None,
                "janitorial_task": task.janitorial_task.title if task.janitorial_task else None
            }
            tasks_data.append(task_info)
        
        await broadcast_task_update(inventory_day.id, 0, "tasks_generated", {
            "tasks": tasks_data,
            "force_regenerate": force_regenerate
        })
        print(f"✅ Broadcasted task generation for day {inventory_day.id}")
        
    except Exception as e:
        print(f"❌ Error broadcasting updates: {e}")
        # Don't fail the request if broadcasting fails
        pass
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/new")
async def create_manual_task(
    day_id: int,
    request: Request,
    inventory_item_id: int = Form(None),
    batch_id: int = Form(None),
    category_id: int = Form(None),
    description: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    # Get form data to handle checkbox values
    form_data = await request.form()
    assigned_to_ids = []
    
    # Extract employee IDs from form data
    for key, value in form_data.items():
        if key.startswith('assigned_to_ids'):
            try:
                assigned_to_ids.append(int(value))
            except ValueError:
                continue
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot add tasks to finalized day")
    
    # Create a single task with multiple employees assigned
    task = Task(
        day_id=day_id,
        assigned_to_id=assigned_to_ids[0] if assigned_to_ids else None,  # Primary assignee
        inventory_item_id=inventory_item_id if inventory_item_id else None,
        batch_id=batch_id if batch_id else None,  # Direct batch assignment or from inventory item
        category_id=category_id if category_id else None,
        description=description,
        auto_generated=False,
        assigned_employee_ids=','.join(map(str, assigned_to_ids)) if assigned_to_ids else None
    )
    
    # Set batch_id from inventory item if linked and no direct batch selected
    if inventory_item_id and not batch_id:
        inventory_item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
        if inventory_item and inventory_item.batch_id:
            task.batch_id = inventory_item.batch_id
    
    db.add(task)
    db.commit()
    
    # Broadcast new manual task creation
    try:
        await broadcast_task_update(day_id, task.id, "task_created", {
            "description": task.description,
            "assigned_employees": [emp.full_name for emp in db.query(User).filter(User.id.in_(assigned_to_ids)).all()] if assigned_to_ids else [],
            "inventory_item": task.inventory_item.name if task.inventory_item else None,
            "batch_name": task.batch.recipe.name if task.batch else None,
            "category": task.category.name if task.category else None,
            "auto_generated": False
        })
        print(f"✅ Broadcasted manual task creation for task {task.id}")
    except Exception as e:
        print(f"❌ Error broadcasting task creation: {e}")
        pass
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/assign")
async def assign_task(
    day_id: int,
    task_id: int,
    assigned_to_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.assigned_to_id = assigned_to_id
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/assign_multiple")
async def assign_multiple_employees_to_task(
    day_id: int,
    task_id: int,
    assigned_to_ids: list[int] = Form([]),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not assigned_to_ids:
        raise HTTPException(status_code=400, detail="At least one employee must be selected")
    
    # Set primary assignee to first selected employee
    task.assigned_to_id = assigned_to_ids[0]
    
    # Store all assigned employee IDs
    task.assigned_employee_ids = ','.join(map(str, assigned_to_ids))
    
    # Broadcast BEFORE committing to ensure connections are still active
    try:
        assigned_employees = [emp.full_name for emp in db.query(User).filter(User.id.in_(assigned_to_ids)).all()] if assigned_to_ids else []
        await broadcast_task_update(day_id, task_id, "task_assigned", {
            "assigned_employees": assigned_employees,
            "primary_assignee": assigned_employees[0] if assigned_employees else None,
            "team_size": len(assigned_employees)
        })
        print(f"✅ Broadcasted task assignment for task {task_id}")
    except Exception as e:
        print(f"❌ Error broadcasting task assignment: {e}")
        pass
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/start")
async def start_task(
    day_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "not_started":
        raise HTTPException(status_code=400, detail="Task already started")
    
    task.started_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/start_with_scale")
async def start_task_with_scale(
    day_id: int,
    task_id: int,
    selected_scale: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "not_started":
        raise HTTPException(status_code=400, detail="Task already started")
    
    # Set scale information
    task.selected_scale = selected_scale
    
    # Calculate scale factor
    scale_factors = {
        'full': 1.0,
        'double': 2.0,
        'half': 0.5,
        'quarter': 0.25,
        'eighth': 0.125,
        'sixteenth': 0.0625
    }
    task.scale_factor = scale_factors.get(selected_scale, 1.0)
    
    # Start the task
    task.started_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/pause")
async def pause_task(
    day_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "in_progress":
        raise HTTPException(status_code=400, detail="Task is not in progress")
    
    # Broadcast BEFORE committing
    try:
        await broadcast_task_update(day_id, task_id, "task_paused", {
            "paused_at": datetime.utcnow().isoformat(),
            "paused_by": current_user.full_name or current_user.username
        })
        print(f"✅ Broadcasted task pause for task {task_id}")
    except Exception as e:
        print(f"❌ Error broadcasting task pause: {e}")
        pass
    
    task.paused_at = datetime.utcnow()
    task.is_paused = True
    db.commit()
    
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "paused":
        raise HTTPException(status_code=400, detail="Task is not paused")
    
    # Add pause time to total
    if task.paused_at:
        pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
        task.total_pause_time += int(pause_duration)
    
    task.paused_at = None
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/finish")
async def finish_task(
    day_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in ["in_progress", "paused"]:
        raise HTTPException(status_code=400, detail="Task cannot be finished")
    
    # Broadcast BEFORE committing
    try:
        await broadcast_task_update(day_id, task_id, "task_completed", {
            "finished_at": datetime.utcnow().isoformat(),
            "total_time": task.total_time_minutes,
            "labor_cost": task.labor_cost,
            "completed_by": current_user.full_name or current_user.username
        })
        print(f"✅ Broadcasted task completion for task {task_id}")
    except Exception as e:
        print(f"❌ Error broadcasting task completion: {e}")
        pass
    
    # Handle paused task
    if task.is_paused and task.paused_at:
        # Don't add more pause time, just finish from paused state
        pass
    
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    task.paused_at = None
    
    # For non-variable yield batches, set made amount automatically
    if task.batch and not task.batch.variable_yield and task.scale_factor:
        task.made_amount = task.batch.yield_amount * task.scale_factor
        task.made_unit = task.batch.yield_unit
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.post("/day/{day_id}/tasks/{task_id}/finish_with_amount")
async def finish_task_with_amount(
    day_id: int,
    task_id: int,
    made_amount: float = Form(...),
    made_unit: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in ["in_progress", "paused"]:
        raise HTTPException(status_code=400, detail="Task cannot be finished")
    
    # Set made amount
    task.made_amount = made_amount
    task.made_unit = made_unit
    
    # Broadcast BEFORE committing
    try:
        await broadcast_task_update(day_id, task_id, "task_completed", {
            "finished_at": datetime.utcnow().isoformat(),
            "total_time": task.total_time_minutes,
            "made_amount": task.made_amount,
            "made_unit": task.made_unit,
            "labor_cost": task.labor_cost,
            "completed_by": current_user.full_name or current_user.username
        })
        print(f"✅ Broadcasted task completion with amount for task {task_id}")
    except Exception as e:
        print(f"❌ Error broadcasting task completion: {e}")
        pass
    
    # Finish the task
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    task.paused_at = None
    
    db.commit()
    
    
    task.notes = notes if notes.strip() else None
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)

@router.get("/day/{day_id}/tasks/{task_id}")
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
        joinedload(Task.batch).joinedload(Batch.recipe)
    ).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate task summary if completed and linked to inventory item
    task_summary = None
    if task.status == "completed" and task.inventory_item:
        task_summary = calculate_task_summary(task, db)
    
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "task": task,
        "employees": employees,
        "task_summary": task_summary
    })

@router.post("/day/{day_id}/finalize")
async def finalize_inventory_day(
    day_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Day is already finalized")
    
    inventory_day.finalized = True
    db.commit()
    
    # Broadcast day finalization
    try:
        await broadcast_day_update(day_id, "day_finalized", {
            "finalized_at": datetime.utcnow().isoformat()
        })
        print(f"✅ Broadcasted day finalization for day {day_id}")
    except Exception as e:
        print(f"❌ Error broadcasting day finalization: {e}")
        pass
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@router.get("/reports/{day_id}")
async def inventory_report(
    day_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if not inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Day must be finalized to view report")
    
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == "completed"])
    below_par_items = len([item for item in inventory_day_items if item.quantity <= item.inventory_item.par_level])
    
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
def generate_tasks_for_day(db: Session, inventory_day: InventoryDay, inventory_day_items, janitorial_day_items, force_regenerate: bool = False):
    """Generate tasks for items that are below par level"""
    
    if force_regenerate:
        # Force regenerate: delete ALL tasks for this day
        db.query(Task).filter(Task.day_id == inventory_day.id).delete()
    else:
        # Normal operation: only delete auto-generated tasks that haven't been started
        db.query(Task).filter(
            Task.day_id == inventory_day.id,
            Task.auto_generated == True,
            Task.started_at.is_(None)  # Only delete tasks that haven't been started
        ).delete()
    
    for day_item in inventory_day_items:
        item = day_item.inventory_item
        is_below_par = day_item.quantity < item.par_level
        
        # Check if task already exists for this item (unless force regenerating)
        if not force_regenerate:
            existing_task = db.query(Task).filter(
                Task.day_id == inventory_day.id,
                Task.inventory_item_id == item.id
            ).first()
            
            # Skip if task already exists and has been started
            if existing_task and existing_task.started_at:
                continue
        
        # Create task if:
        # 1. Item is below par and not overridden to skip
        # 2. Item is above par but overridden to create task
        should_create_task = (
            (is_below_par and not day_item.override_no_task) or
            (not is_below_par and day_item.override_create_task)
        )
        
        if should_create_task:
            # Create task description
            if item.batch:
                description = f"Make {item.name} - {item.batch.recipe.name}"
            else:
                description = f"Restock {item.name}"
            
            task = Task(
                day_id=inventory_day.id,
                inventory_item_id=item.id,
                batch_id=item.batch_id if item.batch else None,
                description=description,
                auto_generated=True
            )
            db.add(task)
    
    # Generate janitorial tasks
    for janitorial_day_item in janitorial_day_items:
        janitorial_task = janitorial_day_item.janitorial_task
        
        # Check if task already exists for this janitorial task (unless force regenerating)
        if not force_regenerate:
            existing_task = db.query(Task).filter(
                Task.day_id == inventory_day.id,
                Task.janitorial_task_id == janitorial_task.id
            ).first()
            
            # Skip if task already exists and has been started
            if existing_task and existing_task.started_at:
                continue
        
        # Create task if:
        # 1. Daily task (always included)
        # 2. Manual task that is checked to be included
        should_create_task = (
            janitorial_task.task_type == 'daily' or
            (janitorial_task.task_type == 'manual' and janitorial_day_item.include_task)
        )
        
        if should_create_task:
            task = Task(
                day_id=inventory_day.id,
                janitorial_task_id=janitorial_task.id,
                description=janitorial_task.title,
                auto_generated=(janitorial_task.task_type == 'daily')
            )
            db.add(task)

@router.get("/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_detail(day_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    janitorial_day_items = db.query(JanitorialTaskDay).filter(JanitorialTaskDay.day_id == day_id).all()
    tasks = db.query(Task).filter(Task.day_id == day_id).order_by(Task.id).all()
    employees = db.query(User).filter(User.is_active == True).all()
    batches = db.query(Batch).all()  # Add batches for manual task creation
    categories = db.query(Category).filter(Category.type.in_(["batch", "inventory"])).all()
    
    # Calculate task summaries for completed tasks
    task_summaries = {}
    for task in tasks:
        if task.status == "completed" and task.inventory_item:
            summary = calculate_task_summary(task, db)
            if summary:
                task_summaries[task.id] = summary
    
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
        "task_summaries": task_summaries
    })

def calculate_task_summary(task, db):
    """Calculate task summary information"""
    if not task.inventory_item:
        return None
    
    # Get the inventory day item for initial inventory
    day_item = db.query(InventoryDayItem).filter(
        InventoryDayItem.day_id == task.day_id,
        InventoryDayItem.inventory_item_id == task.inventory_item.id
    ).first()
    
    if not day_item:
        return None
    
    item = task.inventory_item
    
    # Basic information
    summary = {
        'par_level': item.par_level,
        'par_unit_name': item.par_unit_name.name if item.par_unit_name else 'units',
        'par_unit_equals_type': item.par_unit_equals_type,
        'par_unit_equals': item.par_unit_equals_calculated,
        'par_unit_equals_unit': item.par_unit_equals_unit,
        'initial_inventory': day_item.quantity,
        'made_amount': task.made_amount,
        'made_unit': task.made_unit,
        'made_par_units': 0,
        'made_amount_par_units': 0,
        'final_inventory': day_item.quantity,
        'initial_converted': None,
        'made_converted': None,
        'final_converted': None,
        'made_quantity_equivalent': None,
        'made_quantity_unit': None
    }
    
    # Calculate made amount in par units and quantity equivalents
    if task.made_amount and task.made_unit:
        # For par unit tasks, the made_amount is already in par units
        if item.par_unit_name and task.made_unit == item.par_unit_name.name:
            summary['made_par_units'] = task.made_amount
            summary['made_amount_par_units'] = task.made_amount
            
            # Calculate quantity equivalent if custom par unit equals
            if item.par_unit_equals_type == 'custom' and item.par_unit_equals_amount and item.par_unit_equals_unit:
                quantity_equivalent = task.made_amount * item.par_unit_equals_amount
                summary['made_quantity_equivalent'] = quantity_equivalent
                summary['made_quantity_unit'] = item.par_unit_equals_unit
        else:
            # Regular unit conversion
            made_par_units = item.convert_to_par_units(task.made_amount, task.made_unit)
            summary['made_par_units'] = made_par_units
            summary['made_amount_par_units'] = made_par_units
        
        summary['final_inventory'] = day_item.quantity + summary['made_amount_par_units']
    
    # Calculate conversions if custom par unit equals
    if item.par_unit_equals_type == 'custom' and item.par_unit_equals_calculated:
        summary['initial_converted'] = day_item.quantity * item.par_unit_equals_calculated
        if summary['made_amount_par_units']:
            summary['made_converted'] = summary['made_amount_par_units'] * item.par_unit_equals_calculated
        summary['final_converted'] = summary['final_inventory'] * item.par_unit_equals_calculated
    
    return summary

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
    par_unit_equals_type: str = Form(...),
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
    item.par_unit_equals_amount = par_unit_equals_amount if par_unit_equals_type == 'custom' else None
    item.par_unit_equals_unit = par_unit_equals_unit if par_unit_equals_type == 'custom' else None
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