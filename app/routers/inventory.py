from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import case
from datetime import date, timedelta
from ..database import get_db
from ..dependencies import require_manager_or_admin, get_current_user, require_admin
from ..models import (InventoryItem, Category, Batch, ParUnitName, InventoryDay,
                     InventoryDayItem, Task, User, JanitorialTask, JanitorialTaskDay)
from ..utils.helpers import get_today_date
from datetime import datetime
from ..utils.datetime_utils import get_naive_local_time

# Import SSE broadcasting functions
from ..sse import broadcast_task_update, broadcast_inventory_update, broadcast_day_update

from ..utils.template_helpers import setup_template_filters
from ..utils.slugify import slugify, generate_unique_slug

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = setup_template_filters(Jinja2Templates(directory="templates"))


def get_task_by_slug(db: Session, day_id: int, task_slug: str):
    """Helper function to get a task by its slug within a specific day."""
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    for task in tasks:
        if task.slug == task_slug:
            return task
    return None

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
    slug = generate_unique_slug(db, InventoryItem, name)

    inventory_item = InventoryItem(
        name=name,
        slug=slug,
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

@router.get("/janitorial_tasks/{task_id}/edit", response_class=HTMLResponse)
async def janitorial_task_edit_page(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    janitorial_task = db.query(JanitorialTask).filter(JanitorialTask.id == task_id).first()
    if not janitorial_task:
        raise HTTPException(status_code=404, detail="Janitorial task not found")
    
    return templates.TemplateResponse("janitorial_task_edit.html", {
        "request": request,
        "current_user": current_user,
        "janitorial_task": janitorial_task
    })

@router.post("/janitorial_tasks/{task_id}/edit")
async def update_janitorial_task(
    task_id: int,
    request: Request,
    title: str = Form(...),
    instructions: str = Form(""),
    task_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    janitorial_task = db.query(JanitorialTask).filter(JanitorialTask.id == task_id).first()
    if not janitorial_task:
        raise HTTPException(status_code=404, detail="Janitorial task not found")
    
    janitorial_task.title = title
    janitorial_task.instructions = instructions if instructions else None
    janitorial_task.task_type = task_type
    
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

    # Check if at least one employee is assigned
    if not employees_working or len(employees_working) == 0:
        raise HTTPException(status_code=400, detail="At least one employee must be assigned to create a new day")

    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == inventory_date_obj).first()
    if existing_day:
        return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=302)
    
    # Create new inventory day
    inventory_day = InventoryDay(
        date=inventory_date_obj,
        employees_working=','.join(map(str, employees_working)) if employees_working else '',
        global_notes=global_notes if global_notes else None,
        started_at=get_naive_local_time()
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

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.post("/day/{date}/update")
async def update_inventory_day(
    date: str,
    request: Request,
    global_notes: str = Form(""),
    force_regenerate: bool = Form(False),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot update finalized day")

    # Update day notes
    inventory_day.global_notes = global_notes if global_notes else None

    # Get all form data to process inventory items
    form_data = await request.form()

    # Process inventory item quantities
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == inventory_day.id).all()
    janitorial_day_items = db.query(JanitorialTaskDay).filter(JanitorialTaskDay.day_id == inventory_day.id).all()
    
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
    
    # Broadcast inventory updates and task generation BEFORE committing
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
        
        await broadcast_inventory_update(inventory_day.id, 0, "inventory_updated", {
            "items": updated_items,
            "force_regenerate": force_regenerate
        })
        print(f"✅ Broadcasted inventory update for day {inventory_day.id}")
        
    except Exception as e:
        print(f"❌ Error broadcasting inventory update: {e}")
        pass
    
    db.commit()
    
    # Broadcast task generation AFTER committing to get accurate task data
    try:
        # Get all tasks to broadcast (including newly created ones)
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
        print(f"❌ Error broadcasting task generation: {e}")
        pass

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.post("/day/{date}/tasks/new")
async def create_manual_task(
    date: str,
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
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot add tasks to finalized day")

    # Create a single task with multiple employees assigned
    task = Task(
        day_id=inventory_day.id,
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
    
    # Broadcast manual task creation AFTER committing
    try:
        assigned_employees = []
        if assigned_to_ids:
            employees = db.query(User).filter(User.id.in_(assigned_to_ids)).all()
            assigned_employees = [emp.full_name or emp.username for emp in employees]

        await broadcast_task_update(inventory_day.id, task.id, "task_created", {
            "description": task.description,
            "assigned_employees": assigned_employees,
            "inventory_item": task.inventory_item.name if task.inventory_item else None,
            "batch_name": task.batch.recipe.name if task.batch else None,
            "category": task.category.name if task.category else None,
            "auto_generated": False
        })
        print(f"✅ Broadcasted manual task creation for task {task.id}")
    except Exception as e:
        print(f"❌ Error broadcasting task creation: {e}")
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.post("/day/{date}/tasks/{task_slug}/assign")
async def assign_task(
    date: str,
    task_slug: str,
    assigned_to_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    task = get_task_by_slug(db, inventory_day.id, task_slug)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.assigned_to_id = assigned_to_id
    
    db.commit()
    
    # Broadcast AFTER committing to ensure data is saved
    try:
        assigned_employee = db.query(User).filter(User.id == assigned_to_id).first()
        await broadcast_task_update(inventory_day.id, task.id, "task_assigned", {
            "assigned_to": assigned_employee.full_name or assigned_employee.username if assigned_employee else None,
            "assigned_by": current_user.full_name or current_user.username
        })
        print(f"✅ Broadcasted task assignment for task {task.id}")
    except Exception as e:
        print(f"❌ Error broadcasting task assignment: {e}")
        pass

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.post("/day/{date}/tasks/{task_slug}/assign_multiple")
async def assign_multiple_employees_to_task(
    date: str,
    task_slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    print(f"🔍 Assigning employees to task - task_slug: {task_slug}, date: {date}")

    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        print(f"❌ Inventory day not found: {date}")
        raise HTTPException(status_code=404, detail="Inventory day not found")

    # Get form data to handle checkbox values
    form_data = await request.form()
    assigned_to_ids = []

    # Extract employee IDs from form data - use multi_items() for multiple values with same name
    for key, value in form_data.multi_items():
        if key == 'assigned_to_ids':
            try:
                assigned_to_ids.append(int(value))
            except ValueError:
                continue

    print(f"📝 Received employee IDs: {assigned_to_ids}")

    task = get_task_by_slug(db, inventory_day.id, task_slug)
    if not task:
        print(f"❌ Task not found: {task_slug} in day {inventory_day.id}")
        # List all tasks for debugging
        all_tasks = db.query(Task).filter(Task.day_id == inventory_day.id).all()
        print(f"Available tasks: {[(t.id, t.slug, t.description, t.auto_generated) for t in all_tasks]}")
        raise HTTPException(status_code=404, detail="Task not found")

    if not assigned_to_ids:
        print(f"❌ No employees selected")
        raise HTTPException(status_code=400, detail="At least one employee must be selected")

    print(f"✅ Found task: id={task.id}, description='{task.description}', auto_generated={task.auto_generated}")

    # Set primary assignee to first selected employee
    task.assigned_to_id = assigned_to_ids[0]

    # Store all assigned employee IDs
    task.assigned_employee_ids = ','.join(map(str, assigned_to_ids))

    print(f"💾 Saving assignment: assigned_to_id={task.assigned_to_id}, assigned_employee_ids={task.assigned_employee_ids}")

    db.commit()

    print(f"✅ Assignment saved successfully!")
    
    # Broadcast assignment AFTER committing
    try:
        assigned_employees = []
        if assigned_to_ids:
            employees = db.query(User).filter(User.id.in_(assigned_to_ids)).all()
            assigned_employees = [emp.full_name or emp.username for emp in employees]

        await broadcast_task_update(inventory_day.id, task.id, "task_assigned", {
            "assigned_employees": assigned_employees,
            "primary_assignee": assigned_employees[0] if assigned_employees else None,
            "team_size": len(assigned_employees),
            "assigned_by": current_user.full_name or current_user.username
        })
        print(f"✅ Broadcasted task assignment for task {task.id}")
    except Exception as e:
        print(f"❌ Error broadcasting task assignment: {e}")

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.post("/day/{date}/tasks/bulk_assign")
async def bulk_assign_tasks(
    date: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    """Bulk assign multiple tasks to employees"""
    # Get the inventory day first
    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    form_data = await request.form()

    # Parse form data: task_1_emp_5, task_2_emp_7, etc.
    task_assignments = {}  # {task_id: [emp_id1, emp_id2]}

    for key, value in form_data.multi_items():
        if key.startswith('task_'):
            # Parse: task_1_emp_5 -> task_id=1, emp_id=5
            parts = key.split('_')
            if len(parts) >= 4:
                try:
                    task_id = int(parts[1])
                    emp_id = int(parts[3])

                    if task_id not in task_assignments:
                        task_assignments[task_id] = []
                    task_assignments[task_id].append(emp_id)
                except (ValueError, IndexError):
                    continue

    # Get all tasks for this day
    all_tasks = db.query(Task).filter(Task.day_id == inventory_day.id, Task.status != 'completed').all()

    # Update each task
    updated_count = 0
    for task in all_tasks:
        employee_ids = task_assignments.get(task.id, [])

        # Update task assignments (even if empty - allows unassigning all)
        if employee_ids:
            task.assigned_to_id = employee_ids[0]  # Set primary assignee to first
            task.assigned_employee_ids = ','.join(map(str, employee_ids))
        else:
            # Clear assignments
            task.assigned_to_id = None
            task.assigned_employee_ids = None

        updated_count += 1

    db.commit()

    # Broadcast bulk assignment update
    try:
        await broadcast_day_update(inventory_day.id, "bulk_assignments_updated", {
            "updated_count": updated_count,
            "assigned_by": current_user.full_name or current_user.username
        })
        print(f"✅ Broadcasted bulk assignment for {updated_count} tasks")
    except Exception as e:
        print(f"❌ Error broadcasting bulk assignment: {e}")

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=303)

@router.post("/day/{date}/tasks/{task_slug}/start")
async def start_task(
    date: str,
    task_slug: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    from ..models import TaskSession

    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    task = get_task_by_slug(db, inventory_day.id, task_slug)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "not_started":
        raise HTTPException(status_code=400, detail="Task already started")

    # Check if task has assigned employees
    if not task.assigned_to_id and not task.assigned_employee_ids:
        raise HTTPException(status_code=400, detail="Please assign employees before starting this task")

    now = get_naive_local_time()
    task.started_at = now
    task.is_paused = False

    # Create new session
    session = TaskSession(
        task_id=task.id,
        started_at=now
    )
    db.add(session)
    db.commit()

    # Broadcast AFTER committing
    try:
        await broadcast_task_update(inventory_day.id, task.id, "task_started", {
            "started_at": now.isoformat(),
            "started_by": current_user.full_name or current_user.username
        })
        print(f"✅ Broadcasted task start for task {task.id}")
    except Exception as e:
        print(f"❌ Error broadcasting task start: {e}")
        pass

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.post("/day/{date}/tasks/{task_slug}/start_with_scale")
async def start_task_with_scale(
    date: str,
    task_slug: str,
    selected_scale: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    from ..models import TaskSession

    print(f"🔍 Starting task with scale - task_slug: {task_slug}, selected_scale: {selected_scale}")

    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        print(f"❌ Inventory day not found: {date}")
        raise HTTPException(status_code=404, detail="Inventory day not found")

    task = get_task_by_slug(db, inventory_day.id, task_slug)
    if not task:
        print(f"❌ Task not found: {task_slug} in day {inventory_day.id}")
        # List all tasks for debugging
        all_tasks = db.query(Task).filter(Task.day_id == inventory_day.id).all()
        print(f"Available tasks: {[(t.id, t.slug, t.description) for t in all_tasks]}")
        raise HTTPException(status_code=404, detail="Task not found")

    print(f"✅ Found task: id={task.id}, status={task.status}, assigned_to_id={task.assigned_to_id}, assigned_employee_ids={task.assigned_employee_ids}")

    if task.status != "not_started":
        print(f"❌ Task already started: {task.status}")
        raise HTTPException(status_code=400, detail="Task already started")

    # Check if task has assigned employees
    if not task.assigned_to_id and not task.assigned_employee_ids:
        print(f"❌ No employees assigned")
        raise HTTPException(status_code=400, detail="Please assign employees before starting this task")

    # Set scale information
    task.selected_scale = selected_scale

    # Calculate scale factor
    scale_factors = {
        'full': 1.0,
        'double': 2.0,
        'triple': 3.0,
        'quadruple': 4.0,
        'three_quarters': 0.75,
        'two_thirds': 0.6667,
        'half': 0.5,
        'quarter': 0.25,
        'eighth': 0.125,
        'sixteenth': 0.0625
    }
    task.scale_factor = scale_factors.get(selected_scale, 1.0)

    if selected_scale not in scale_factors:
        print(f"⚠️ Warning: Unknown scale '{selected_scale}', using default 1.0")

    # Start the task
    now = get_naive_local_time()
    task.started_at = now
    task.is_paused = False

    # Create new session
    session = TaskSession(
        task_id=task.id,
        started_at=now
    )
    db.add(session)
    db.commit()

    # Broadcast AFTER committing
    try:
        await broadcast_task_update(inventory_day.id, task.id, "task_started", {
            "started_at": now.isoformat(),
            "started_by": current_user.full_name or current_user.username,
            "scale": selected_scale
        })
        print(f"✅ Broadcasted task start with scale for task {task.id}")
    except Exception as e:
        print(f"❌ Error broadcasting task start: {e}")
        pass

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.post("/day/{date}/tasks/{task_slug}/pause")
async def pause_task(
    date: str,
    task_slug: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    task = get_task_by_slug(db, inventory_day.id, task_slug)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "in_progress":
        raise HTTPException(status_code=400, detail="Task is not in progress")

    now = get_naive_local_time()
    task.paused_at = now
    task.is_paused = True
    db.commit()

    # Broadcast AFTER committing
    try:
        await broadcast_task_update(inventory_day.id, task.id, "task_paused", {
            "paused_at": now.isoformat(),
            "paused_by": current_user.full_name or current_user.username,
            "total_pause_time": task.total_pause_time
        })
        print(f"✅ Broadcasted task pause for task {task.id}")
    except Exception as e:
        print(f"❌ Error broadcasting task pause: {e}")

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.post("/day/{date}/tasks/{task_slug}/resume")
async def resume_task(
    date: str,
    task_slug: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    from ..models import TaskSession

    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    task = get_task_by_slug(db, inventory_day.id, task_slug)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "paused":
        raise HTTPException(status_code=400, detail="Task is not paused")

    now = get_naive_local_time()

    # Add pause time to total and current session
    if task.paused_at:
        pause_duration = int((now - task.paused_at).total_seconds())
        task.total_pause_time += pause_duration

        # Update current session pause duration
        current_session = db.query(TaskSession).filter(
            TaskSession.task_id == task.id,
            TaskSession.ended_at.is_(None)
        ).first()

        if current_session:
            current_session.pause_duration += pause_duration

    task.paused_at = None
    task.is_paused = False
    db.commit()

    # Broadcast AFTER committing
    try:
        await broadcast_task_update(inventory_day.id, task.id, "task_resumed", {
            "resumed_at": now.isoformat(),
            "resumed_by": current_user.full_name or current_user.username,
            "total_pause_time": task.total_pause_time
        })
        print(f"✅ Broadcasted task resume for task {task.id}")
    except Exception as e:
        print(f"❌ Error broadcasting task resume: {e}")

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.post("/day/{date}/tasks/{task_slug}/finish")
async def finish_task(
    date: str,
    task_slug: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    from ..models import TaskSession

    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    task = get_task_by_slug(db, inventory_day.id, task_slug)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in ["in_progress", "paused"]:
        raise HTTPException(status_code=400, detail="Task cannot be finished")

    now = get_naive_local_time()

    # Handle paused task - add pause time to total and current session
    if task.is_paused and task.paused_at:
        pause_duration = int((now - task.paused_at).total_seconds())
        task.total_pause_time += pause_duration

        # Update current session pause duration
        current_session = db.query(TaskSession).filter(
            TaskSession.task_id == task.id,
            TaskSession.ended_at.is_(None)
        ).first()

        if current_session:
            current_session.pause_duration += pause_duration

    task.finished_at = now
    task.is_paused = False
    task.paused_at = None

    # Close the current session
    current_session = db.query(TaskSession).filter(
        TaskSession.task_id == task.id,
        TaskSession.ended_at.is_(None)
    ).first()

    if current_session:
        current_session.ended_at = now

    # For non-variable yield batches, set made amount automatically
    if task.batch and not task.batch.variable_yield and task.scale_factor:
        task.made_amount = task.batch.yield_amount * task.scale_factor
        task.made_unit = task.batch.yield_unit

    db.commit()

    # Broadcast AFTER committing
    try:
        await broadcast_task_update(inventory_day.id, task.id, "task_completed", {
            "finished_at": now.isoformat(),
            "total_time": task.total_time_minutes,
            "labor_cost": task.labor_cost,
            "completed_by": current_user.full_name or current_user.username,
            "made_amount": task.made_amount,
            "made_unit": task.made_unit
        })
        print(f"✅ Broadcasted task completion for task {task.id}")
    except Exception as e:
        print(f"❌ Error broadcasting task completion: {e}")

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.post("/day/{date}/tasks/{task_slug}/finish_with_amount")
async def finish_task_with_amount(
    date: str,
    task_slug: str,
    made_amount: float = Form(...),
    made_unit: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    from ..models import TaskSession

    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    task = get_task_by_slug(db, inventory_day.id, task_slug)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in ["in_progress", "paused"]:
        raise HTTPException(status_code=400, detail="Task cannot be finished")

    now = get_naive_local_time()

    # Set made amount
    task.made_amount = made_amount
    task.made_unit = made_unit

    # Handle paused task - add pause time to total and current session
    if task.is_paused and task.paused_at:
        pause_duration = int((now - task.paused_at).total_seconds())
        task.total_pause_time += pause_duration

        # Update current session pause duration
        current_session = db.query(TaskSession).filter(
            TaskSession.task_id == task.id,
            TaskSession.ended_at.is_(None)
        ).first()

        if current_session:
            current_session.pause_duration += pause_duration

    # Finish the task
    task.finished_at = now
    task.is_paused = False
    task.paused_at = None

    # Close the current session
    current_session = db.query(TaskSession).filter(
        TaskSession.task_id == task.id,
        TaskSession.ended_at.is_(None)
    ).first()

    if current_session:
        current_session.ended_at = now

    db.commit()

    # Broadcast AFTER committing
    try:
        await broadcast_task_update(inventory_day.id, task.id, "task_completed", {
            "finished_at": now.isoformat(),
            "total_time": task.total_time_minutes,
            "made_amount": task.made_amount,
            "made_unit": task.made_unit,
            "labor_cost": task.labor_cost,
            "completed_by": current_user.full_name or current_user.username
        })
        print(f"✅ Broadcasted task completion with amount for task {task.id}")
    except Exception as e:
        print(f"❌ Error broadcasting task completion: {e}")

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.post("/day/{date}/tasks/{task_slug}/reopen")
async def reopen_task(
    date: str,
    task_slug: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    from ..models import TaskSession

    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    task = get_task_by_slug(db, inventory_day.id, task_slug)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="Only completed tasks can be reopened")

    now = get_naive_local_time()

    # Use the model's reopen method to clear completion data
    task.reopen()

    # Create a new session for the reopened task
    new_session = TaskSession(
        task_id=task.id,
        started_at=now
    )
    db.add(new_session)

    db.commit()

    # Broadcast AFTER committing
    try:
        await broadcast_task_update(inventory_day.id, task.id, "task_reopened", {
            "reopened_at": now.isoformat(),
            "reopened_by": current_user.full_name or current_user.username
        })
        print(f"✅ Broadcasted task reopen for task {task.id}")
    except Exception as e:
        print(f"❌ Error broadcasting task reopen: {e}")
        pass

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.post("/day/{date}/tasks/{task_slug}/notes")
async def update_task_notes(
    date: str,
    task_slug: str,
    notes: str = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    task = get_task_by_slug(db, inventory_day.id, task_slug)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.notes = notes
    db.commit()

    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}/tasks/{task.slug}", status_code=302)

@router.get("/day/{date}/tasks/{task_slug}", response_class=HTMLResponse)
async def task_detail(
    date: str,
    task_slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    task = get_task_by_slug(db, inventory_day.id, task_slug)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Load relationships
    db.refresh(task)
    if task.batch:
        db.refresh(task.batch)
    
    employees = db.query(User).filter(User.is_active == True).all()

    # Convert employees to serializable format for JavaScript
    employees_data = [
        {
            "id": emp.id,
            "username": emp.username,
            "full_name": emp.full_name
        }
        for emp in employees
    ]

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
        "employees_data": employees_data,
        "task_summary": task_summary
    })

@router.post("/day/{date}/finalize")
async def finalize_inventory_day(
    date: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Day is already finalized")

    inventory_day.finalized = True
    inventory_day.finalized_at = get_naive_local_time()
    db.commit()
    
    # Broadcast day finalization
    try:
        await broadcast_day_update(day_id, "day_finalized", {
            "finalized_at": get_naive_local_time().isoformat()
        })
        print(f"✅ Broadcasted day finalization for day {day_id}")
    except Exception as e:
        print(f"❌ Error broadcasting day finalization: {e}")
        pass
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.date}", status_code=302)

@router.get("/reports/{date}")
async def inventory_report(
    date: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    if not inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Day must be finalized to view report")

    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == inventory_day.id).all()
    tasks = db.query(Task).filter(Task.day_id == inventory_day.id).all()
    employees = db.query(User).filter(User.is_active == True).all()

    # Filter out inventory day items where inventory item was deleted
    inventory_day_items = [item for item in inventory_day_items if item.inventory_item is not None]

    # Calculate statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == "completed"])
    below_par_items = len([item for item in inventory_day_items if item.quantity <= item.inventory_item.par_level])

    # Calculate time metrics
    total_task_time = sum(t.total_time_minutes for t in tasks if t.total_time_minutes)
    total_shift_duration = None
    off_task_time = None
    shift_efficiency = None

    if inventory_day.started_at and inventory_day.finalized_at:
        shift_duration_seconds = (inventory_day.finalized_at - inventory_day.started_at).total_seconds()
        total_shift_duration = shift_duration_seconds / 60  # Convert to minutes
        off_task_time = total_shift_duration - total_task_time
        if total_shift_duration > 0:
            shift_efficiency = (total_task_time / total_shift_duration) * 100

    return templates.TemplateResponse("inventory_report.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
        "employees": employees,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "below_par_items": below_par_items,
        "total_shift_duration": total_shift_duration,
        "off_task_time": off_task_time,
        "shift_efficiency": shift_efficiency
    })
def generate_tasks_for_day(db: Session, inventory_day: InventoryDay, inventory_day_items, janitorial_day_items, force_regenerate: bool = False):
    """Generate tasks for items that are below par level"""

    if force_regenerate:
        # Force regenerate: delete ALL tasks for this day
        db.query(Task).filter(Task.day_id == inventory_day.id).delete()
    else:
        # Normal operation: only delete auto-generated tasks that haven't been started AND have changed
        pass  # We'll handle deletions on a per-task basis below

    for day_item in inventory_day_items:
        item = day_item.inventory_item
        is_below_par = day_item.quantity < item.par_level

        # Check if task already exists for this item
        existing_task = db.query(Task).filter(
            Task.day_id == inventory_day.id,
            Task.inventory_item_id == item.id
        ).first()

        # CRITICAL: Never modify tasks that have been started or completed
        if existing_task and existing_task.started_at:
            continue

        # Check if inventory values have changed since task was created
        inventory_changed = False
        if existing_task:
            # If snapshot fields are None (old tasks), treat as changed to update them
            if existing_task.snapshot_quantity is None:
                inventory_changed = True
            else:
                # Compare current values with snapshot
                inventory_changed = (
                    existing_task.snapshot_quantity != day_item.quantity or
                    existing_task.snapshot_par_level != item.par_level or
                    existing_task.snapshot_override_create != day_item.override_create_task or
                    existing_task.snapshot_override_no_task != day_item.override_no_task
                )

        # If task exists, inventory hasn't changed, and not force regenerating - skip it
        if existing_task and not inventory_changed and not force_regenerate:
            continue

        # Create task if:
        # 1. Item is below par and not overridden to skip
        # 2. Item is above par but overridden to create task
        should_create_task = (
            (is_below_par and not day_item.override_no_task) or
            (not is_below_par and day_item.override_create_task)
        )

        # If task exists but should no longer exist, delete it
        if existing_task and not should_create_task:
            db.delete(existing_task)
            continue

        # If task should exist but doesn't, or inventory changed, create/update it
        if should_create_task:
            # If task exists and inventory changed, delete and recreate
            if existing_task:
                db.delete(existing_task)

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
                auto_generated=True,
                snapshot_quantity=day_item.quantity,
                snapshot_par_level=item.par_level,
                snapshot_override_create=day_item.override_create_task,
                snapshot_override_no_task=day_item.override_no_task
            )
            db.add(task)
    
    # Generate janitorial tasks
    for janitorial_day_item in janitorial_day_items:
        janitorial_task = janitorial_day_item.janitorial_task

        # Check if task already exists for this janitorial task
        existing_task = db.query(Task).filter(
            Task.day_id == inventory_day.id,
            Task.janitorial_task_id == janitorial_task.id
        ).first()

        # CRITICAL: Never modify tasks that have been started or completed
        if existing_task and existing_task.started_at:
            continue

        # Determine if task should be included
        should_include = (
            janitorial_task.task_type == 'daily' or
            (janitorial_task.task_type == 'manual' and janitorial_day_item.include_task)
        )

        # If task exists but should no longer exist, delete it
        if existing_task and not should_include:
            db.delete(existing_task)
            continue

        # If task should exist but doesn't, create it
        if should_include and not existing_task:
            task = Task(
                day_id=inventory_day.id,
                janitorial_task_id=janitorial_task.id,
                description=janitorial_task.title,
                auto_generated=(janitorial_task.task_type == 'daily')
            )
            db.add(task)

@router.get("/day/{date}", response_class=HTMLResponse)
async def inventory_day_detail(date: str, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")

    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == inventory_day.id).all()
    janitorial_day_items = db.query(JanitorialTaskDay).filter(JanitorialTaskDay.day_id == inventory_day.id).all()

    # Query tasks with category sorting
    # Create aliases for categories from different sources
    inventory_category = db.query(Category).join(InventoryItem).filter(
        InventoryItem.id == Task.inventory_item_id
    ).correlate(Task).scalar_subquery()

    janitorial_category = db.query(Category).join(JanitorialTask).filter(
        JanitorialTask.id == Task.janitorial_task_id
    ).correlate(Task).scalar_subquery()

    # Get tasks and sort by category name (prioritizing inventory item category, then janitorial category)
    tasks = db.query(Task)\
        .outerjoin(InventoryItem, Task.inventory_item_id == InventoryItem.id)\
        .outerjoin(Category, InventoryItem.category_id == Category.id)\
        .filter(Task.day_id == inventory_day.id)\
        .order_by(
            case(
                (Category.name.isnot(None), Category.name),
                else_=''
            ),
            Task.id
        )\
        .all()
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

@router.get("/items/{item_slug}/edit", response_class=HTMLResponse)
async def inventory_item_edit_page(item_slug: str, request: Request, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    item = db.query(InventoryItem).filter(InventoryItem.slug == item_slug).first()
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

@router.post("/items/{item_slug}/edit")
async def update_inventory_item(
    item_slug: str,
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
    item = db.query(InventoryItem).filter(InventoryItem.slug == item_slug).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    if item.name != name:
        item.slug = generate_unique_slug(db, InventoryItem, name, exclude_id=item.id)

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

@router.get("/items/{item_slug}/delete")
async def delete_inventory_item(item_slug: str, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    item = db.query(InventoryItem).filter(InventoryItem.slug == item_slug).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    db.delete(item)
    db.commit()

    return RedirectResponse(url="/inventory", status_code=302)

@router.get("/all_completed_days")
async def get_all_completed_days(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    finalized_days = db.query(InventoryDay).filter(
        InventoryDay.finalized == True
    ).order_by(InventoryDay.date.desc()).all()

    return {
        "days": [
            {
                "id": day.id,
                "date": day.date.strftime('%Y-%m-%d'),
                "day_name": day.date.strftime('%A')
            }
            for day in finalized_days
        ]
    }