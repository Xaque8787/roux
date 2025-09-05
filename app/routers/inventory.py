from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date, timedelta
from ..database import get_db
from ..dependencies import require_manager_or_admin, get_current_user, require_admin
from ..models import (InventoryItem, Category, Batch, ParUnitName, InventoryDay, 
                     InventoryDayItem, Task, User)
from ..utils.helpers import get_today_date
from datetime import datetime

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def inventory_page(request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    inventory_items = db.query(InventoryItem).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    par_unit_names = db.query(ParUnitName).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
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
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

@router.post("/day/{day_id}/update")
async def update_inventory_day(
    day_id: int,
    request: Request,
    global_notes: str = Form(""),
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
    
    for day_item in inventory_day_items:
        item_key = f"item_{day_item.inventory_item_id}"
        override_create_key = f"override_create_{day_item.inventory_item_id}"
        override_no_task_key = f"override_no_task_{day_item.inventory_item_id}"
        
        if item_key in form_data:
            day_item.quantity = float(form_data[item_key]) if form_data[item_key] else 0.0
        
        day_item.override_create_task = override_create_key in form_data
        day_item.override_no_task = override_no_task_key in form_data
    
    # Generate tasks based on inventory levels
    generate_tasks_for_day(db, inventory_day, inventory_day_items)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

def generate_tasks_for_day(db: Session, inventory_day: InventoryDay, inventory_day_items):
    """Generate tasks for items that are below par level"""
    
    # Delete existing auto-generated tasks for this day
    db.query(Task).filter(
        Task.day_id == inventory_day.id,
        Task.auto_generated == True
    ).delete()
    
    for day_item in inventory_day_items:
        item = day_item.inventory_item
        is_below_par = day_item.quantity <= item.par_level
        
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
@router.get("/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_detail(day_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    tasks = db.query(Task).filter(Task.day_id == day_id).order_by(Task.id).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
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
        "tasks": tasks,
        "employees": employees,
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
        'final_converted': None
    }
    
    # Calculate made amount in par units
    if task.made_amount and task.made_unit:
        made_par_units = item.convert_to_par_units(task.made_amount, task.made_unit)
        summary['made_par_units'] = made_par_units
        summary['made_amount_par_units'] = made_par_units
        summary['final_inventory'] = day_item.quantity + made_par_units
    
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
    
    return templates.TemplateResponse("inventory_item_edit.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "categories": categories,
        "batches": batches
    })

@router.post("/items/{item_id}/edit")
async def update_inventory_item(
    item_id: int,
    request: Request,
    name: str = Form(...),
    par_level: float = Form(...),
    batch_id: int = Form(None),
    category_id: int = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    item.name = name
    item.par_level = par_level
    item.batch_id = batch_id if batch_id else None
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