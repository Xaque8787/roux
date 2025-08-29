from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import date, datetime
import json
from typing import List
import os

from .database import get_db, engine
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, Vendor, UsageUnit, IngredientUsageUnit
from .auth import hash_password, verify_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Food Cost Management System")

# Mount static files and templates
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Custom exception handler for authentication redirects
@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    if exc.status_code == 401:
        # Check if we have any users in the database
        from .database import SessionLocal
        db = SessionLocal()
        try:
            if not db.query(User).first():
                return RedirectResponse("/setup", status_code=302)
            else:
                return RedirectResponse("/login", status_code=302)
        finally:
            db.close()
    return templates.TemplateResponse("error.html", {
        "request": request, 
        "status_code": exc.status_code,
        "detail": exc.detail
    }, status_code=exc.status_code)
# Root redirect
@app.get("/")
async def root():
    return RedirectResponse("/setup")

# Setup routes
@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    if db.query(User).first():
        return RedirectResponse("/login")
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if db.query(User).first():
        return RedirectResponse("/login")
    
    hashed_password = hash_password(password)
    admin = User(
        username=username,
        full_name=username,
        hashed_password=hashed_password,
        role="admin",
        is_admin=True,
        is_user=True,
        hourly_wage=20.0
    )
    db.add(admin)
    
    # Create default categories and usage units
    categories = [
        Category(name="Produce", type="ingredient"),
        Category(name="Dairy", type="ingredient"),
        Category(name="Meat", type="ingredient"),
        Category(name="Pantry", type="ingredient"),
        Category(name="Dressings", type="recipe"),
        Category(name="Sauces", type="recipe"),
        Category(name="Prep Items", type="batch"),
        Category(name="Salads", type="dish"),
        Category(name="Entrees", type="dish"),
        Category(name="Desserts", type="dish"),
        Category(name="Proteins", type="inventory"),
        Category(name="Vegetables", type="inventory"),
    ]
    
    for category in categories:
        db.add(category)
    
    # Create default usage units
    usage_units = [
        UsageUnit(name="lb"),
        UsageUnit(name="oz"),
        UsageUnit(name="tbsp"),
        UsageUnit(name="tsp"),
        UsageUnit(name="cup"),
        UsageUnit(name="can"),
        UsageUnit(name="ea"),
        UsageUnit(name="pkg"),
        UsageUnit(name="qt"),
        UsageUnit(name="gal"),
    ]
    
    for unit in usage_units:
        db.add(unit)
    
    db.commit()
    return RedirectResponse("/login", status_code=302)

# Login routes
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
    token = create_jwt({
        "sub": user.username,
        "role": user.role,
        "is_admin": user.is_admin,
        "is_user": user.is_user
    })
    response = RedirectResponse("/home", status_code=302)
    response.set_cookie("access_token", token, httponly=True, samesite="strict")
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response

# Home page
@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Employees routes
@app.get("/employees", response_class=HTMLResponse)
async def list_employees(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employees = db.query(User).all()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "employees": employees,
        "current_user": current_user
    })

@app.post("/employees/new")
async def create_employee(
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form("user"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed_password = hash_password(password)
    employee = User(
        full_name=full_name,
        username=username,
        hashed_password=hashed_password,
        hourly_wage=hourly_wage,
        work_schedule=work_schedule,
        role=role,
        is_admin=(role == "admin"),
        is_user=True
    )
    db.add(employee)
    db.commit()
    return RedirectResponse("/employees", status_code=302)

@app.get("/employees/{employee_id}", response_class=HTMLResponse)
async def view_employee(
    employee_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_detail.html", {
        "request": request,
        "employee": employee,
        "current_user": current_user
    })

@app.get("/employees/{employee_id}/edit", response_class=HTMLResponse)
async def edit_employee_form(
    employee_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_edit.html", {
        "request": request,
        "employee": employee,
        "current_user": current_user
    })

@app.post("/employees/{employee_id}/edit")
async def update_employee(
    employee_id: int,
    full_name: str = Form(...),
    username: str = Form(...),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form("user"),
    is_active: bool = Form(False),
    password: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check if username is taken by another user
    existing_user = db.query(User).filter(User.username == username, User.id != employee_id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    employee.full_name = full_name
    employee.username = username
    employee.hourly_wage = hourly_wage
    employee.work_schedule = work_schedule
    employee.role = role
    employee.is_admin = (role == "admin")
    employee.is_active = is_active
    
    if password:
        employee.hashed_password = hash_password(password)
    
    db.commit()
    return RedirectResponse(f"/employees/{employee_id}", status_code=302)

@app.get("/employees/{employee_id}/delete")
async def delete_employee(
    employee_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if employee and employee.id != current_user.id:  # Can't delete yourself
        employee.is_active = False  # Soft delete
        db.commit()
    return RedirectResponse("/employees", status_code=302)

# Ingredients routes
@app.get("/ingredients", response_class=HTMLResponse)
async def list_ingredients(
    request: Request,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    ingredients = db.query(Ingredient).all()
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    usage_units = db.query(UsageUnit).all()
    return templates.TemplateResponse("ingredients.html", {
        "request": request,
        "ingredients": ingredients,
        "categories": categories,
        "vendors": vendors,
        "usage_units": usage_units,
        "current_user": current_user
    })

@app.post("/ingredients/new")
async def create_ingredient(
    name: str = Form(...),
    unit: str = Form(...),
    unit_cost: float = Form(...),
    category_id: int = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ingredient = Ingredient(
        name=name,
        unit=unit,
        unit_cost=unit_cost,
        category_id=category_id if category_id else None
    )
    db.add(ingredient)
    db.commit()
    return RedirectResponse("/ingredients", status_code=302)

@app.get("/ingredients/{ingredient_id}/delete")
async def delete_ingredient(
    ingredient_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if ingredient:
        db.delete(ingredient)
        db.commit()
    return RedirectResponse("/ingredients", status_code=302)

# Recipes routes
@app.get("/recipes", response_class=HTMLResponse)
async def list_recipes(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recipes = db.query(Recipe).all()
    ingredients = db.query(Ingredient).all()
    categories = db.query(Category).filter(Category.type == "recipe").all()
    return templates.TemplateResponse("recipes.html", {
        "request": request,
        "recipes": recipes,
        "ingredients": ingredients,
        "categories": categories,
        "current_user": current_user
    })

@app.post("/recipes/new")
async def create_recipe(
    request: Request,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: int = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    form = await request.form()
    
    recipe = Recipe(
        name=name,
        instructions=instructions,
        category_id=category_id if category_id else None
    )
    db.add(recipe)
    db.flush()
    
    # Add ingredients
    for key, value in form.items():
        if key.startswith("ingredient_") and value and float(value) > 0:
            ingredient_id = int(key.replace("ingredient_", ""))
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ingredient_id,
                quantity=float(value)
            )
            db.add(recipe_ingredient)
    
    db.commit()
    return RedirectResponse("/recipes", status_code=302)

@app.get("/recipes/{recipe_id}")
async def view_recipe(
    recipe_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe_ingredients = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == recipe_id
    ).all()
    
    return templates.TemplateResponse("recipe_detail.html", {
        "request": request,
        "recipe": recipe,
        "recipe_ingredients": recipe_ingredients,
        "current_user": current_user
    })

@app.get("/recipes/{recipe_id}/delete")
async def delete_recipe(
    recipe_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if recipe:
        # Delete recipe ingredients first
        db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
        db.delete(recipe)
        db.commit()
    return RedirectResponse("/recipes", status_code=302)

# Batches routes
@app.get("/batches", response_class=HTMLResponse)
async def list_batches(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batches = db.query(Batch).all()
    recipes = db.query(Recipe).all()
    return templates.TemplateResponse("batches.html", {
        "request": request,
        "batches": batches,
        "recipes": recipes,
        "current_user": current_user
    })

@app.post("/batches/new")
async def create_batch(
    recipe_id: int = Form(...),
    yield_amount: float = Form(...),
    labor_minutes: int = Form(...),
    can_be_broken_down: bool = Form(False),
    breakdown_sizes: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batch = Batch(
        recipe_id=recipe_id,
        yield_amount=yield_amount,
        labor_minutes=labor_minutes,
        can_be_broken_down=can_be_broken_down,
        breakdown_sizes=breakdown_sizes if breakdown_sizes else None
    )
    db.add(batch)
    db.commit()
    return RedirectResponse("/batches", status_code=302)

@app.get("/batches/{batch_id}/delete")
async def delete_batch(
    batch_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if batch:
        db.delete(batch)
        db.commit()
    return RedirectResponse("/batches", status_code=302)

# Dishes routes
@app.get("/dishes", response_class=HTMLResponse)
async def list_dishes(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    dishes = db.query(Dish).all()
    batches = db.query(Batch).all()
    categories = db.query(Category).filter(Category.type == "dish").all()
    return templates.TemplateResponse("dishes.html", {
        "request": request,
        "dishes": dishes,
        "batches": batches,
        "categories": categories,
        "current_user": current_user
    })

@app.post("/dishes/new")
async def create_dish(
    request: Request,
    name: str = Form(...),
    sale_price: float = Form(...),
    description: str = Form(""),
    category_id: int = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    form = await request.form()
    
    dish = Dish(
        name=name,
        sale_price=sale_price,
        description=description,
        category_id=category_id if category_id else None
    )
    db.add(dish)
    db.flush()
    
    # Add batch portions
    for key, value in form.items():
        if key.startswith("batch_") and value and float(value) > 0:
            batch_id = int(key.replace("batch_", ""))
            dish_batch_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=batch_id,
                portion_size=float(value)
            )
            db.add(dish_batch_portion)
    
    db.commit()
    return RedirectResponse("/dishes", status_code=302)

@app.get("/dishes/{dish_id}/delete")
async def delete_dish(
    dish_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if dish:
        # Delete dish batch portions first
        db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
        db.delete(dish)
        db.commit()
    return RedirectResponse("/dishes", status_code=302)

# Inventory routes
@app.get("/inventory", response_class=HTMLResponse)
async def view_inventory_master(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_items = db.query(InventoryItem).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    employees = db.query(User).filter(User.is_user == True).all()
    
    # Get current inventory day if exists
    today = date.today()
    current_day = db.query(InventoryDay).filter(InventoryDay.date == today).first()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "inventory_items": inventory_items,
        "categories": categories,
        "employees": employees,
        "current_day": current_day,
        "today_date": today.isoformat(),
        "current_user": current_user
    })

@app.post("/inventory/new_item")
async def create_inventory_item(
    name: str = Form(...),
    par_level: float = Form(...),
    category_id: int = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = InventoryItem(
        name=name,
        par_level=par_level,
        category_id=category_id if category_id else None
    )
    db.add(item)
    db.commit()
    return RedirectResponse("/inventory", status_code=302)

@app.post("/inventory/new_day")
async def create_new_day(
    request: Request,
    date_input: str = Form(..., alias="date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    form = await request.form()
    employees_working = form.getlist("employees_working")
    
    inventory_day = InventoryDay(
        date=datetime.strptime(date_input, "%Y-%m-%d").date(),
        employees_working=",".join(employees_working)
    )
    db.add(inventory_day)
    db.flush()
    
    # Copy master inventory items to day items
    inventory_items = db.query(InventoryItem).all()
    for item in inventory_items:
        day_item = InventoryDayItem(
            day_id=inventory_day.id,
            inventory_item_id=item.id,
            quantity=0
        )
        db.add(day_item)
    
    db.commit()
    return RedirectResponse(f"/inventory/day/{inventory_day.id}", status_code=302)

@app.get("/inventory/day/{day_id}", response_class=HTMLResponse)
async def view_inventory_day(
    day_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).filter(
        InventoryDayItem.day_id == day_id
    ).all()
    
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    employees = db.query(User).filter(User.is_user == True).all()
    
    return templates.TemplateResponse("inventory_day.html", {
        "request": request,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
        "employees": employees,
        "current_user": current_user
    })

@app.post("/inventory/day/{day_id}/update")
async def update_inventory_day_items(
    day_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    form = await request.form()
    
    for key, value in form.items():
        if key.startswith("item_"):
            item_id = int(key.replace("item_", ""))
            day_item = db.query(InventoryDayItem).filter(
                InventoryDayItem.day_id == day_id,
                InventoryDayItem.inventory_item_id == item_id
            ).first()
            if day_item:
                day_item.quantity = float(value) if value else 0
    
    db.commit()
    return RedirectResponse(f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/new")
async def create_task(
    day_id: int,
    assigned_to_id: int = Form(...),
    description: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = Task(
        day_id=day_id,
        assigned_to_id=assigned_to_id,
        description=description
    )
    db.add(task)
    db.commit()
    return RedirectResponse(f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start")
async def start_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.started_at = datetime.utcnow()
        db.commit()
    return RedirectResponse(f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish")
async def finish_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.finished_at = datetime.utcnow()
        db.commit()
    return RedirectResponse(f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/finalize")
async def finalize_day(
    day_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if inventory_day:
        inventory_day.finalized = True
        db.commit()
    return RedirectResponse(f"/inventory/day/{day_id}", status_code=302)

# Utilities routes
@app.get("/utilities", response_class=HTMLResponse)
async def view_utilities(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    utilities = db.query(UtilityCost).all()
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "utilities": utilities,
        "current_user": current_user
    })

@app.post("/utilities/new")
async def add_utility(
    name: str = Form(...),
    monthly_cost: float = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Check if utility already exists
    existing = db.query(UtilityCost).filter(UtilityCost.name == name).first()
    if existing:
        existing.monthly_cost = monthly_cost
        existing.last_updated = datetime.utcnow()
    else:
        utility = UtilityCost(name=name, monthly_cost=monthly_cost)
        db.add(utility)
    
    db.commit()
    return RedirectResponse("/utilities", status_code=302)

@app.post("/utilities/{utility_id}/delete")
async def delete_utility(
    utility_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
    if utility:
        db.delete(utility)
        db.commit()
    return RedirectResponse("/utilities", status_code=302)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)