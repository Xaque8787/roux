from fastapi import FastAPI, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, or_, and_
from datetime import datetime, timedelta, date, timezone
from typing import Optional, List
import os

from .database import SessionLocal, engine, get_db
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, VendorUnit, Vendor, ParUnitName
from .auth import hash_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Food Cost Management System")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

def create_default_categories(db: Session):
    """Create default categories if they don't exist"""
    default_categories = [
        ("Proteins", "ingredient"),
        ("Vegetables", "ingredient"),
        ("Dairy", "ingredient"),
        ("Grains", "ingredient"),
        ("Spices", "ingredient"),
        ("Oils", "ingredient"),
        ("Appetizers", "recipe"),
        ("Mains", "recipe"),
        ("Desserts", "recipe"),
        ("Beverages", "recipe"),
        ("Prep", "batch"),
        ("Production", "batch"),
        ("Appetizers", "dish"),
        ("Mains", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Proteins", "inventory"),
        ("Vegetables", "inventory"),
        ("Dairy", "inventory"),
        ("Prepared Items", "inventory")
    ]
    
    try:
        for name, cat_type in default_categories:
            existing = db.query(Category).filter(
                Category.name == name,
                Category.type == cat_type
            ).first()
            
            if not existing:
                category = Category(name=name, type=cat_type)
                db.add(category)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error creating default categories: {e}")

def create_default_vendor_units(db: Session):
    """Create default vendor units if they don't exist"""
    default_units = [
        ("lb", "Pounds"),
        ("oz", "Ounces"),
        ("gal", "Gallons"),
        ("qt", "Quarts"),
        ("pt", "Pints"),
        ("cup", "Cups"),
        ("fl_oz", "Fluid Ounces"),
        ("l", "Liters"),
        ("ml", "Milliliters"),
        ("g", "Grams"),
        ("kg", "Kilograms"),
        ("each", "Each/Individual Items"),
        ("dozen", "Dozen (12 items)"),
        ("case", "Case/Box"),
        ("bag", "Bag"),
        ("can", "Can"),
        ("jar", "Jar"),
        ("bottle", "Bottle")
    ]
    
    try:
        for name, description in default_units:
            existing = db.query(VendorUnit).filter(VendorUnit.name == name).first()
            if not existing:
                unit = VendorUnit(name=name, description=description)
                db.add(unit)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error creating default vendor units: {e}")

def create_default_par_unit_names(db: Session):
    """Create default par unit names if they don't exist"""
    default_par_units = [
        "Tub",
        "Container",
        "Case",
        "Box",
        "Bag",
        "Pan",
        "Sheet Pan",
        "Hotel Pan",
        "Cambro",
        "Bucket",
        "Portion"
    ]
    
    try:
        for name in default_par_units:
            existing = db.query(ParUnitName).filter(ParUnitName.name == name).first()
            if not existing:
                par_unit = ParUnitName(name=name)
                db.add(par_unit)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error creating default par unit names: {e}")

def is_setup_complete(db: Session) -> bool:
    """Check if initial setup is complete"""
    return db.query(User).filter(User.role == "admin").first() is not None

# Root redirect
@app.get("/")
async def root():
    return RedirectResponse(url="/home", status_code=307)

# Setup routes
@app.get("/setup", response_class=HTMLResponse)
async def setup_get(request: Request, db: Session = Depends(get_db)):
    if is_setup_complete(db):
        return RedirectResponse(url="/login", status_code=307)
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_post(
    request: Request,
    username: str = Form(...),
    full_name: Optional[str] = Form(None),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if is_setup_complete(db):
        return RedirectResponse(url="/login", status_code=303)
    
    # Use username as full_name if not provided
    if not full_name or full_name.strip() == "":
        full_name = username
    
    # Create admin user
    hashed_password = hash_password(password)
    admin_user = User(
        username=username,
        full_name=full_name,
        hashed_password=hashed_password,
        role="admin",
        is_admin=True,
        is_user=True
    )
    
    db.add(admin_user)
    db.commit()
    
    # Create default categories, vendor units, and par unit names
    create_default_categories(db)
    create_default_vendor_units(db)
    create_default_par_unit_names(db)
    
    return RedirectResponse(url="/login", status_code=303)

# Authentication routes
@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, db: Session = Depends(get_db)):
    if not is_setup_complete(db):
        return RedirectResponse(url="/setup", status_code=307)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    from .auth import verify_password
    
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
    # Create JWT token
    token = create_jwt({"sub": user.username})
    
    # Create response and set cookie
    response = RedirectResponse(url="/home", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response

# Home page
@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Error handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401 and exc.headers and exc.headers.get("Location"):
        return RedirectResponse(url=exc.headers["Location"], status_code=303)
    
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": exc.status_code,
        "detail": exc.detail
    }, status_code=exc.status_code)

# Employee management routes
@app.get("/employees", response_class=HTMLResponse)
async def employees_get(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employees = db.query(User).all()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "current_user": current_user,
        "employees": employees
    })

@app.post("/employees/new")
async def employees_new(
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Check if username already exists
    existing = db.query(User).filter(User.username == username).first()
    if existing:
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
    
    return RedirectResponse(url="/employees", status_code=303)

@app.get("/employees/{employee_id}", response_class=HTMLResponse)
async def employee_detail(
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
        "current_user": current_user,
        "employee": employee
    })

@app.get("/employees/{employee_id}/edit", response_class=HTMLResponse)
async def employee_edit_get(
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
        "current_user": current_user,
        "employee": employee
    })

@app.post("/employees/{employee_id}/edit")
async def employee_edit_post(
    employee_id: int,
    full_name: str = Form(...),
    username: str = Form(...),
    password: Optional[str] = Form(None),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form(...),
    is_active: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check if username is taken by another user
    existing = db.query(User).filter(User.username == username, User.id != employee_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    employee.full_name = full_name
    employee.username = username
    employee.hourly_wage = hourly_wage
    employee.work_schedule = work_schedule
    employee.role = role
    employee.is_admin = (role == "admin")
    employee.is_active = (is_active == "on")
    
    if password and password.strip():
        employee.hashed_password = hash_password(password)
    
    db.commit()
    
    return RedirectResponse(url=f"/employees/{employee_id}", status_code=303)

@app.get("/employees/{employee_id}/delete")
async def employee_delete(
    employee_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Don't allow deleting yourself
    if employee.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Deactivate instead of delete to preserve task history
    employee.is_active = False
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=303)

# Ingredient management routes
@app.get("/ingredients", response_class=HTMLResponse)
async def ingredients_get(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).all()
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    vendor_units = db.query(VendorUnit).all()
    
    return templates.TemplateResponse("ingredients.html", {
        "request": request,
        "current_user": current_user,
        "ingredients": ingredients,
        "categories": categories,
        "vendors": vendors,
        "vendor_units": vendor_units
    })

@app.post("/ingredients/new")
async def ingredients_new(
    name: str = Form(...),
    usage_type: str = Form(...),
    category_id: Optional[int] = Form(None),
    vendor_id: Optional[int] = Form(None),
    vendor_unit_id: Optional[int] = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    net_weight_volume_item: float = Form(...),
    net_weight_volume_case: Optional[float] = Form(None),
    net_unit: str = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: Optional[str] = Form(None),
    items_per_case: Optional[int] = Form(None),
    has_baking_conversion: Optional[str] = Form(None),
    baking_measurement_unit: Optional[str] = Form(None),
    baking_measurement_amount: Optional[float] = Form(None),
    baking_weight_amount: Optional[float] = Form(None),
    baking_weight_unit: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Calculate net_weight_volume_case if not provided
    if purchase_type == 'case' and items_per_case and not net_weight_volume_case:
        net_weight_volume_case = net_weight_volume_item * items_per_case
    
    ingredient = Ingredient(
        name=name,
        usage_type=usage_type,
        category_id=category_id if category_id else None,
        vendor_id=vendor_id if vendor_id else None,
        vendor_unit_id=vendor_unit_id if vendor_unit_id else None,
        purchase_type=purchase_type,
        purchase_unit_name=purchase_unit_name,
        net_weight_volume_item=net_weight_volume_item,
        net_weight_volume_case=net_weight_volume_case,
        net_unit=net_unit,
        purchase_total_cost=purchase_total_cost,
        breakable_case=(breakable_case == "on"),
        items_per_case=items_per_case,
        has_baking_conversion=(has_baking_conversion == "on"),
        baking_measurement_unit=baking_measurement_unit,
        baking_measurement_amount=baking_measurement_amount,
        baking_weight_amount=baking_weight_amount,
        baking_weight_unit=baking_weight_unit
    )
    
    db.add(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=303)

@app.get("/ingredients/{ingredient_id}", response_class=HTMLResponse)
async def ingredient_detail(
    ingredient_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    return templates.TemplateResponse("ingredient_detail.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient
    })

@app.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
async def ingredient_edit_get(
    ingredient_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    vendor_units = db.query(VendorUnit).all()
    
    return templates.TemplateResponse("ingredient_edit.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient,
        "categories": categories,
        "vendors": vendors,
        "vendor_units": vendor_units
    })

@app.post("/ingredients/{ingredient_id}/edit")
async def ingredient_edit_post(
    ingredient_id: int,
    name: str = Form(...),
    usage_type: str = Form(...),
    category_id: Optional[int] = Form(None),
    vendor_id: Optional[int] = Form(None),
    vendor_unit_id: Optional[int] = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    net_weight_volume_item: float = Form(...),
    net_weight_volume_case: Optional[float] = Form(None),
    net_unit: str = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: Optional[str] = Form(None),
    items_per_case: Optional[int] = Form(None),
    has_baking_conversion: Optional[str] = Form(None),
    baking_measurement_unit: Optional[str] = Form(None),
    baking_measurement_amount: Optional[float] = Form(None),
    baking_weight_amount: Optional[float] = Form(None),
    baking_weight_unit: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    # Calculate net_weight_volume_case if not provided
    if purchase_type == 'case' and items_per_case and not net_weight_volume_case:
        net_weight_volume_case = net_weight_volume_item * items_per_case
    
    ingredient.name = name
    ingredient.usage_type = usage_type
    ingredient.category_id = category_id if category_id else None
    ingredient.vendor_id = vendor_id if vendor_id else None
    ingredient.vendor_unit_id = vendor_unit_id if vendor_unit_id else None
    ingredient.purchase_type = purchase_type
    ingredient.purchase_unit_name = purchase_unit_name
    ingredient.net_weight_volume_item = net_weight_volume_item
    ingredient.net_weight_volume_case = net_weight_volume_case
    ingredient.net_unit = net_unit
    ingredient.purchase_total_cost = purchase_total_cost
    ingredient.breakable_case = (breakable_case == "on")
    ingredient.items_per_case = items_per_case
    ingredient.has_baking_conversion = (has_baking_conversion == "on")
    ingredient.baking_measurement_unit = baking_measurement_unit
    ingredient.baking_measurement_amount = baking_measurement_amount
    ingredient.baking_weight_amount = baking_weight_amount
    ingredient.baking_weight_unit = baking_weight_unit
    
    db.commit()
    
    return RedirectResponse(url=f"/ingredients/{ingredient_id}", status_code=303)

@app.get("/ingredients/{ingredient_id}/delete")
async def ingredient_delete(
    ingredient_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    db.delete(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=303)

# Recipe management routes
@app.get("/recipes", response_class=HTMLResponse)
async def recipes_get(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipes = db.query(Recipe).all()
    categories = db.query(Category).filter(Category.type == "recipe").all()
    
    return templates.TemplateResponse("recipes.html", {
        "request": request,
        "current_user": current_user,
        "recipes": recipes,
        "categories": categories
    })

@app.post("/recipes/new")
async def recipes_new(
    name: str = Form(...),
    instructions: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    ingredients_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    import json
    
    recipe = Recipe(
        name=name,
        instructions=instructions,
        category_id=category_id if category_id else None
    )
    
    db.add(recipe)
    db.flush()  # Get the recipe ID
    
    # Add ingredients
    ingredients_list = json.loads(ingredients_data)
    for ingredient_data in ingredients_list:
        recipe_ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=ingredient_data['ingredient_id'],
            unit=ingredient_data['unit'],
            quantity=ingredient_data['quantity']
        )
        db.add(recipe_ingredient)
    
    db.commit()
    
    return RedirectResponse(url="/recipes", status_code=303)

@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(
    recipe_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
    total_cost = sum(ri.cost for ri in recipe_ingredients)
    
    return templates.TemplateResponse("recipe_detail.html", {
        "request": request,
        "current_user": current_user,
        "recipe": recipe,
        "recipe_ingredients": recipe_ingredients,
        "total_cost": total_cost
    })

@app.get("/recipes/{recipe_id}/edit", response_class=HTMLResponse)
async def recipe_edit_get(
    recipe_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
    categories = db.query(Category).filter(Category.type == "recipe").all()
    
    return templates.TemplateResponse("recipe_edit.html", {
        "request": request,
        "current_user": current_user,
        "recipe": recipe,
        "recipe_ingredients": recipe_ingredients,
        "categories": categories
    })

@app.post("/recipes/{recipe_id}/edit")
async def recipe_edit_post(
    recipe_id: int,
    name: str = Form(...),
    instructions: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    ingredients_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    import json
    
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe.name = name
    recipe.instructions = instructions
    recipe.category_id = category_id if category_id else None
    
    # Remove existing ingredients
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
    # Add new ingredients
    ingredients_list = json.loads(ingredients_data)
    for ingredient_data in ingredients_list:
        recipe_ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=ingredient_data['ingredient_id'],
            unit=ingredient_data['unit'],
            quantity=ingredient_data['quantity']
        )
        db.add(recipe_ingredient)
    
    db.commit()
    
    return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=303)

@app.get("/recipes/{recipe_id}/delete")
async def recipe_delete(
    recipe_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    db.delete(recipe)
    db.commit()
    
    return RedirectResponse(url="/recipes", status_code=303)

# Batch management routes
@app.get("/batches", response_class=HTMLResponse)
async def batches_get(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batches = db.query(Batch).all()
    recipes = db.query(Recipe).all()
    
    return templates.TemplateResponse("batches.html", {
        "request": request,
        "current_user": current_user,
        "batches": batches,
        "recipes": recipes
    })

@app.post("/batches/new")
async def batches_new(
    recipe_id: int = Form(...),
    variable_yield: Optional[str] = Form(None),
    yield_amount: Optional[float] = Form(None),
    yield_unit: Optional[str] = Form(None),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(...),
    can_be_scaled: Optional[str] = Form(None),
    scale_double: Optional[str] = Form(None),
    scale_half: Optional[str] = Form(None),
    scale_quarter: Optional[str] = Form(None),
    scale_eighth: Optional[str] = Form(None),
    scale_sixteenth: Optional[str] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    batch = Batch(
        recipe_id=recipe_id,
        variable_yield=(variable_yield == "on"),
        yield_amount=yield_amount,
        yield_unit=yield_unit,
        estimated_labor_minutes=estimated_labor_minutes,
        hourly_labor_rate=hourly_labor_rate,
        can_be_scaled=(can_be_scaled == "on"),
        scale_double=(scale_double == "on"),
        scale_half=(scale_half == "on"),
        scale_quarter=(scale_quarter == "on"),
        scale_eighth=(scale_eighth == "on"),
        scale_sixteenth=(scale_sixteenth == "on")
    )
    
    db.add(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=303)

@app.get("/batches/{batch_id}", response_class=HTMLResponse)
async def batch_detail(
    batch_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
    cost_per_yield_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
    
    return templates.TemplateResponse("batch_detail.html", {
        "request": request,
        "current_user": current_user,
        "batch": batch,
        "recipe_ingredients": recipe_ingredients,
        "total_recipe_cost": total_recipe_cost,
        "total_batch_cost": total_batch_cost,
        "cost_per_yield_unit": cost_per_yield_unit
    })

@app.get("/batches/{batch_id}/edit", response_class=HTMLResponse)
async def batch_edit_get(
    batch_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipes = db.query(Recipe).all()
    
    return templates.TemplateResponse("batch_edit.html", {
        "request": request,
        "current_user": current_user,
        "batch": batch,
        "recipes": recipes
    })

@app.post("/batches/{batch_id}/edit")
async def batch_edit_post(
    batch_id: int,
    recipe_id: int = Form(...),
    variable_yield: Optional[str] = Form(None),
    yield_amount: Optional[float] = Form(None),
    yield_unit: Optional[str] = Form(None),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(...),
    can_be_scaled: Optional[str] = Form(None),
    scale_double: Optional[str] = Form(None),
    scale_half: Optional[str] = Form(None),
    scale_quarter: Optional[str] = Form(None),
    scale_eighth: Optional[str] = Form(None),
    scale_sixteenth: Optional[str] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    batch.recipe_id = recipe_id
    batch.variable_yield = (variable_yield == "on")
    batch.yield_amount = yield_amount
    batch.yield_unit = yield_unit
    batch.estimated_labor_minutes = estimated_labor_minutes
    batch.hourly_labor_rate = hourly_labor_rate
    batch.can_be_scaled = (can_be_scaled == "on")
    batch.scale_double = (scale_double == "on")
    batch.scale_half = (scale_half == "on")
    batch.scale_quarter = (scale_quarter == "on")
    batch.scale_eighth = (scale_eighth == "on")
    batch.scale_sixteenth = (scale_sixteenth == "on")
    
    db.commit()
    
    return RedirectResponse(url=f"/batches/{batch_id}", status_code=303)

@app.get("/batches/{batch_id}/delete")
async def batch_delete(
    batch_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    db.delete(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=303)

# Dish management routes
@app.get("/dishes", response_class=HTMLResponse)
async def dishes_get(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dishes = db.query(Dish).all()
    categories = db.query(Category).filter(Category.type == "dish").all()
    
    return templates.TemplateResponse("dishes.html", {
        "request": request,
        "current_user": current_user,
        "dishes": dishes,
        "categories": categories
    })

@app.post("/dishes/new")
async def dishes_new(
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    sale_price: float = Form(...),
    description: Optional[str] = Form(None),
    batch_portions_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    import json
    
    dish = Dish(
        name=name,
        category_id=category_id if category_id else None,
        sale_price=sale_price,
        description=description
    )
    
    db.add(dish)
    db.flush()  # Get the dish ID
    
    # Add batch portions
    batch_portions_list = json.loads(batch_portions_data)
    for portion_data in batch_portions_list:
        dish_batch_portion = DishBatchPortion(
            dish_id=dish.id,
            batch_id=portion_data['batch_id'],
            portion_size=portion_data['portion_size'],
            portion_unit=portion_data['portion_unit_name']
        )
        db.add(dish_batch_portion)
    
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=303)

@app.get("/dishes/{dish_id}", response_class=HTMLResponse)
async def dish_detail(
    dish_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).all()
    
    # Calculate costs
    expected_total_cost = sum(portion.expected_cost for portion in dish_batch_portions)
    actual_total_cost = sum(portion.actual_cost for portion in dish_batch_portions)
    actual_total_cost_week = sum(portion.actual_cost_week_avg for portion in dish_batch_portions)
    actual_total_cost_month = sum(portion.actual_cost_month_avg for portion in dish_batch_portions)
    actual_total_cost_all_time = sum(portion.actual_cost_all_time_avg for portion in dish_batch_portions)
    
    # Calculate profits and margins
    expected_profit = dish.sale_price - expected_total_cost
    expected_profit_margin = (expected_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_profit = dish.sale_price - actual_total_cost
    actual_profit_margin = (actual_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_profit_week = dish.sale_price - actual_total_cost_week
    actual_profit_margin_week = (actual_profit_week / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_profit_month = dish.sale_price - actual_total_cost_month
    actual_profit_margin_month = (actual_profit_month / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_profit_all_time = dish.sale_price - actual_total_cost_all_time
    actual_profit_margin_all_time = (actual_profit_all_time / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    return templates.TemplateResponse("dish_detail.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "dish_batch_portions": dish_batch_portions,
        "expected_total_cost": expected_total_cost,
        "actual_total_cost": actual_total_cost,
        "actual_total_cost_week": actual_total_cost_week,
        "actual_total_cost_month": actual_total_cost_month,
        "actual_total_cost_all_time": actual_total_cost_all_time,
        "expected_profit": expected_profit,
        "expected_profit_margin": expected_profit_margin,
        "actual_profit": actual_profit,
        "actual_profit_margin": actual_profit_margin,
        "actual_profit_week": actual_profit_week,
        "actual_profit_margin_week": actual_profit_margin_week,
        "actual_profit_month": actual_profit_month,
        "actual_profit_margin_month": actual_profit_margin_month,
        "actual_profit_all_time": actual_profit_all_time,
        "actual_profit_margin_all_time": actual_profit_margin_all_time
    })

@app.get("/dishes/{dish_id}/edit", response_class=HTMLResponse)
async def dish_edit_get(
    dish_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).all()
    categories = db.query(Category).filter(Category.type == "dish").all()
    
    return templates.TemplateResponse("dish_edit.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "dish_batch_portions": dish_batch_portions,
        "categories": categories
    })

@app.post("/dishes/{dish_id}/edit")
async def dish_edit_post(
    dish_id: int,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    sale_price: float = Form(...),
    description: Optional[str] = Form(None),
    batch_portions_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    import json
    
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish.name = name
    dish.category_id = category_id if category_id else None
    dish.sale_price = sale_price
    dish.description = description
    
    # Remove existing batch portions
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Add new batch portions
    batch_portions_list = json.loads(batch_portions_data)
    for portion_data in batch_portions_list:
        dish_batch_portion = DishBatchPortion(
            dish_id=dish.id,
            batch_id=portion_data['batch_id'],
            portion_size=portion_data['portion_size'],
            portion_unit=portion_data['portion_unit_name']
        )
        db.add(dish_batch_portion)
    
    db.commit()
    
    return RedirectResponse(url=f"/dishes/{dish_id}", status_code=303)

@app.get("/dishes/{dish_id}/delete")
async def dish_delete(
    dish_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    db.delete(dish)
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=303)

# Inventory management routes
@app.get("/inventory", response_class=HTMLResponse)
async def inventory_get(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    employees = db.query(User).filter(User.is_active == True).all()
    par_unit_names = db.query(ParUnitName).all()
    
    # Get current day if exists
    today = date.today()
    current_day = db.query(InventoryDay).filter(
        InventoryDay.date == today,
        InventoryDay.finalized == False
    ).first()
    
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
        "categories": categories,
        "batches": batches,
        "employees": employees,
        "par_unit_names": par_unit_names,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "today_date": today.isoformat()
    })

@app.post("/inventory/new_item")
async def inventory_new_item(
    name: str = Form(...),
    par_unit_name_id: Optional[int] = Form(None),
    par_level: float = Form(...),
    batch_id: Optional[int] = Form(None),
    par_unit_equals_type: str = Form(...),
    par_unit_equals_amount: Optional[float] = Form(None),
    par_unit_equals_unit: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_item = InventoryItem(
        name=name,
        par_unit_name_id=par_unit_name_id if par_unit_name_id else None,
        par_level=par_level,
        batch_id=batch_id if batch_id else None,
        par_unit_equals_type=par_unit_equals_type,
        par_unit_equals_amount=par_unit_equals_amount,
        par_unit_equals_unit=par_unit_equals_unit,
        category_id=category_id if category_id else None
    )
    
    db.add(inventory_item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=303)

@app.post("/inventory/new_day")
async def inventory_new_day(
    date_str: str = Form(..., alias="date"),
    employees_working: List[int] = Form(...),
    global_notes: Optional[str] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    from datetime import datetime
    
    inventory_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == inventory_date).first()
    if existing_day:
        raise HTTPException(status_code=400, detail="Inventory day already exists for this date")
    
    # Create new inventory day
    inventory_day = InventoryDay(
        date=inventory_date,
        employees_working=",".join(map(str, employees_working)),
        global_notes=global_notes
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
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=303)

@app.get("/inventory/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_get(
    day_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
            summary = calculate_task_summary(task, inventory_day_items, db)
            if summary:
                task_summaries[task.id] = summary
    
    return templates.TemplateResponse("inventory_day.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
        "task_summaries": task_summaries,
        "employees": employees
    })

def calculate_task_summary(task, inventory_day_items, db):
    """Calculate task summary information for completed tasks"""
    if not task.inventory_item or task.status != "completed":
        return None
    
    # Find the inventory day item
    day_item = None
    for item in inventory_day_items:
        if item.inventory_item_id == task.inventory_item.id:
            day_item = item
            break
    
    if not day_item:
        return None
    
    inventory_item = task.inventory_item
    
    # Basic information
    summary = {
        'par_level': inventory_item.par_level,
        'par_unit_name': inventory_item.par_unit_name.name if inventory_item.par_unit_name else 'units',
        'par_unit_equals_type': inventory_item.par_unit_equals_type,
        'par_unit_equals': inventory_item.par_unit_equals_calculated,
        'par_unit_equals_unit': inventory_item.par_unit_equals_unit,
        'initial_inventory': day_item.quantity,
        'initial_converted': None,
        'made_amount': task.made_amount,
        'made_unit': task.made_unit,
        'made_par_units': 0,
        'made_converted': None,
        'made_amount_par_units': 0,
        'final_inventory': day_item.quantity,
        'final_converted': None
    }
    
    # Calculate conversions if we have par unit equals information
    if inventory_item.par_unit_equals_calculated and inventory_item.par_unit_equals_unit:
        # Convert initial inventory to par unit equals unit
        if inventory_item.par_unit_equals_type == 'custom':
            summary['initial_converted'] = day_item.quantity * inventory_item.par_unit_equals_calculated
        
        # Convert made amount to par units and par unit equals unit
        if task.made_amount and task.made_unit:
            if inventory_item.par_unit_equals_type == 'auto' and inventory_item.batch:
                # For auto type, convert made amount to par units using batch yield
                if task.made_unit == inventory_item.batch.yield_unit:
                    summary['made_par_units'] = task.made_amount / inventory_item.par_unit_equals_calculated
                    summary['made_converted'] = task.made_amount
                    summary['made_amount_par_units'] = summary['made_par_units']
            elif inventory_item.par_unit_equals_type == 'custom':
                # For custom type, convert made amount to par unit equals unit first
                if task.made_unit == inventory_item.par_unit_equals_unit:
                    summary['made_converted'] = task.made_amount
                    summary['made_par_units'] = task.made_amount / inventory_item.par_unit_equals_calculated
                    summary['made_amount_par_units'] = summary['made_par_units']
            elif inventory_item.par_unit_equals_type == 'par_unit_itself':
                # For par unit itself, made amount is directly in par units
                summary['made_par_units'] = task.made_amount
                summary['made_converted'] = task.made_amount
                summary['made_amount_par_units'] = task.made_amount
    
    # Calculate final inventory
    summary['final_inventory'] = summary['initial_inventory'] + summary['made_amount_par_units']
    
    if summary['initial_converted'] is not None and summary['made_converted'] is not None:
        summary['final_converted'] = summary['initial_converted'] + summary['made_converted']
    
    return summary

@app.post("/inventory/day/{day_id}/update")
async def inventory_day_update(
    day_id: int,
    request: Request,
    global_notes: Optional[str] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot update finalized inventory day")
    
    # Update global notes
    inventory_day.global_notes = global_notes
    
    # Get form data
    form_data = await request.form()
    
    # Update inventory quantities and overrides
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    
    for day_item in inventory_day_items:
        # Update quantity
        quantity_key = f"item_{day_item.inventory_item_id}"
        if quantity_key in form_data:
            day_item.quantity = float(form_data[quantity_key])
        
        # Update overrides
        override_create_key = f"override_create_{day_item.inventory_item_id}"
        day_item.override_create_task = override_create_key in form_data
        
        override_no_task_key = f"override_no_task_{day_item.inventory_item_id}"
        day_item.override_no_task = override_no_task_key in form_data
    
    # Generate tasks based on inventory levels
    generate_inventory_tasks(inventory_day, inventory_day_items, db)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

def generate_inventory_tasks(inventory_day, inventory_day_items, db):
    """Generate tasks for items that are below par or have overrides"""
    # Remove existing auto-generated tasks
    db.query(Task).filter(
        Task.day_id == inventory_day.id,
        Task.auto_generated == True
    ).delete()
    
    for day_item in inventory_day_items:
        inventory_item = day_item.inventory_item
        is_below_par = day_item.quantity <= inventory_item.par_level
        
        # Create task if below par (and not overridden to not create) or if overridden to create
        should_create_task = (is_below_par and not day_item.override_no_task) or day_item.override_create_task
        
        if should_create_task:
            task_description = f"Prep {inventory_item.name}"
            if is_below_par:
                task_description += f" (Below par: {day_item.quantity}/{inventory_item.par_level})"
            
            task = Task(
                day_id=inventory_day.id,
                inventory_item_id=inventory_item.id,
                batch_id=inventory_item.batch_id,  # Link to batch if available
                description=task_description,
                auto_generated=True
            )
            
            db.add(task)

@app.post("/inventory/day/{day_id}/tasks/new")
async def inventory_day_tasks_new(
    day_id: int,
    assigned_to_ids: List[int] = Form([]),
    inventory_item_id: Optional[int] = Form(None),
    description: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot add tasks to finalized inventory day")
    
    # Get batch_id from inventory item if linked
    batch_id = None
    if inventory_item_id:
        inventory_item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
        if inventory_item and inventory_item.batch_id:
            batch_id = inventory_item.batch_id
    
    # Create tasks for each assigned employee or one unassigned task
    if assigned_to_ids:
        for assigned_to_id in assigned_to_ids:
            task = Task(
                day_id=day_id,
                assigned_to_id=assigned_to_id,
                inventory_item_id=inventory_item_id,
                batch_id=batch_id,
                description=description,
                auto_generated=False
            )
            db.add(task)
    else:
        # Create unassigned task
        task = Task(
            day_id=day_id,
            inventory_item_id=inventory_item_id,
            batch_id=batch_id,
            description=description,
            auto_generated=False
        )
        db.add(task)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/assign")
async def inventory_day_task_assign(
    day_id: int,
    task_id: int,
    assigned_to_id: int = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.assigned_to_id = assigned_to_id
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start")
async def inventory_day_task_start(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.started_at:
        raise HTTPException(status_code=400, detail="Task already started")
    
    task.started_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start_with_scale")
async def inventory_day_task_start_with_scale(
    day_id: int,
    task_id: int,
    selected_scale: str = Form(...),
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.started_at:
        raise HTTPException(status_code=400, detail="Task already started")
    
    # Set scale information
    scale_factors = {
        'full': 1.0,
        'double': 2.0,
        'half': 0.5,
        'quarter': 0.25,
        'eighth': 0.125,
        'sixteenth': 0.0625
    }
    
    task.selected_scale = selected_scale
    task.scale_factor = scale_factors.get(selected_scale, 1.0)
    task.started_at = datetime.utcnow()
    task.is_paused = False
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/pause")
async def inventory_day_task_pause(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.started_at or task.finished_at:
        raise HTTPException(status_code=400, detail="Task not in progress")
    
    task.paused_at = datetime.utcnow()
    task.is_paused = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/resume")
async def inventory_day_task_resume(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.is_paused or not task.paused_at:
        raise HTTPException(status_code=400, detail="Task not paused")
    
    # Add pause time to total
    pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
    task.total_pause_time += int(pause_duration)
    
    task.paused_at = None
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish")
async def inventory_day_task_finish(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.started_at or task.finished_at:
        raise HTTPException(status_code=400, detail="Task not started or already finished")
    
    # If task was paused, add final pause time
    if task.is_paused and task.paused_at:
        pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
        task.total_pause_time += int(pause_duration)
    
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    task.paused_at = None
    
    # For non-variable yield batches, set made amount based on scale
    if task.batch and not task.batch.variable_yield and task.scale_factor:
        task.made_amount = task.batch.yield_amount * task.scale_factor
        task.made_unit = task.batch.yield_unit
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish_with_amount")
async def inventory_day_task_finish_with_amount(
    day_id: int,
    task_id: int,
    made_amount: float = Form(...),
    made_unit: str = Form(...),
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.started_at or task.finished_at:
        raise HTTPException(status_code=400, detail="Task not started or already finished")
    
    # If task was paused, add final pause time
    if task.is_paused and task.paused_at:
        pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
        task.total_pause_time += int(pause_duration)
    
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    task.paused_at = None
    task.made_amount = made_amount
    task.made_unit = made_unit
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.get("/inventory/day/{day_id}/tasks/{task_id}", response_class=HTMLResponse)
async def inventory_day_task_detail(
    day_id: int,
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate task summary if completed
    task_summary = None
    if task.status == "completed" and task.inventory_item:
        inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
        task_summary = calculate_task_summary(task, inventory_day_items, db)
    
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "task": task,
        "task_summary": task_summary,
        "employees": employees
    })

@app.post("/inventory/day/{day_id}/tasks/{task_id}/notes")
async def inventory_day_task_notes(
    day_id: int,
    task_id: int,
    notes: str = Form(...),
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.notes = notes
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=303)

@app.post("/inventory/day/{day_id}/finalize")
async def inventory_day_finalize(
    day_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Inventory day already finalized")
    
    inventory_day.finalized = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/reports/{day_id}", status_code=303)

@app.get("/inventory/reports/{day_id}", response_class=HTMLResponse)
async def inventory_report(
    day_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.finished_at])
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

@app.get("/inventory/items/{item_id}/edit", response_class=HTMLResponse)
async def inventory_item_edit_get(
    item_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
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

@app.post("/inventory/items/{item_id}/edit")
async def inventory_item_edit_post(
    item_id: int,
    name: str = Form(...),
    par_level: float = Form(...),
    batch_id: Optional[int] = Form(None),
    category_id: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    item.name = name
    item.par_level = par_level
    item.batch_id = batch_id if batch_id else None
    item.category_id = category_id if category_id else None
    
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=303)

@app.get("/inventory/items/{item_id}/delete")
async def inventory_item_delete(
    item_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    db.delete(item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=303)

# Utility management routes
@app.get("/utilities", response_class=HTMLResponse)
async def utilities_get(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    utilities = db.query(UtilityCost).all()
    
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "current_user": current_user,
        "utilities": utilities
    })

@app.post("/utilities/new")
async def utilities_new(
    name: str = Form(...),
    monthly_cost: float = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Check if utility already exists
    existing = db.query(UtilityCost).filter(UtilityCost.name == name).first()
    if existing:
        # Update existing
        existing.monthly_cost = monthly_cost
        existing.last_updated = datetime.utcnow()
    else:
        # Create new
        utility = UtilityCost(
            name=name,
            monthly_cost=monthly_cost
        )
        db.add(utility)
    
    db.commit()
    
    return RedirectResponse(url="/utilities", status_code=303)

@app.post("/utilities/{utility_id}/delete")
async def utilities_delete(
    utility_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
    if not utility:
        raise HTTPException(status_code=404, detail="Utility not found")
    
    db.delete(utility)
    db.commit()
    
    return RedirectResponse(url="/utilities", status_code=303)

# Category management
@app.post("/categories/new")
async def categories_new(
    name: str = Form(...),
    type: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    category = Category(name=name, type=type)
    db.add(category)
    db.commit()
    
    # Redirect based on type
    redirect_urls = {
        "ingredient": "/ingredients",
        "recipe": "/recipes",
        "batch": "/batches",
        "dish": "/dishes",
        "inventory": "/inventory"
    }
    
    return RedirectResponse(url=redirect_urls.get(type, "/home"), status_code=303)

# Vendor management
@app.post("/vendors/new")
async def vendors_new(
    name: str = Form(...),
    contact_info: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    vendor = Vendor(name=name, contact_info=contact_info)
    db.add(vendor)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=303)

# Par Unit Name management
@app.post("/par_unit_names/new")
async def par_unit_names_new(
    name: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    par_unit_name = ParUnitName(name=name)
    db.add(par_unit_name)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=303)

# API endpoints for AJAX requests
@app.get("/api/ingredients/all")
async def api_ingredients_all(db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).all()
    result = []
    for ingredient in ingredients:
        result.append({
            "id": ingredient.id,
            "name": ingredient.name,
            "category": ingredient.category.name if ingredient.category else None,
            "available_units": ingredient.get_available_units()
        })
    return result

@app.get("/api/ingredients/{ingredient_id}/cost_per_unit/{unit}")
async def api_ingredient_cost_per_unit(ingredient_id: int, unit: str, db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    cost_per_unit = ingredient.get_cost_per_unit(unit)
    return {"cost_per_unit": cost_per_unit}

@app.get("/api/recipes/{recipe_id}/available_units")
async def api_recipe_available_units(recipe_id: int, db: Session = Depends(get_db)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # Get all units used by ingredients in this recipe
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
    available_units = set()
    
    for ri in recipe_ingredients:
        ingredient_units = ri.ingredient.get_available_units()
        available_units.update(ingredient_units)
    
    return sorted(list(available_units))

@app.get("/api/batches/all")
async def api_batches_all(db: Session = Depends(get_db)):
    batches = db.query(Batch).all()
    result = []
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
        
        result.append({
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit,
            "cost_per_unit": cost_per_unit,
            "category": batch.recipe.category.name if batch.recipe.category else None
        })
    return result

@app.get("/api/batches/search")
async def api_batches_search(q: str, db: Session = Depends(get_db)):
    batches = db.query(Batch).join(Recipe).filter(
        Recipe.name.ilike(f"%{q}%")
    ).all()
    
    result = []
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
        
        result.append({
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit,
            "cost_per_unit": cost_per_unit,
            "category": batch.recipe.category.name if batch.recipe.category else None
        })
    return result

@app.get("/api/batches/{batch_id}/portion_units")
async def api_batch_portion_units(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get available units from the recipe ingredients
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    available_units = set()
    
    for ri in recipe_ingredients:
        ingredient_units = ri.ingredient.get_available_units()
        available_units.update(ingredient_units)
    
    # Add the batch yield unit
    if batch.yield_unit:
        available_units.add(batch.yield_unit)
    
    # Convert to list of dicts with id and name
    result = []
    unit_id = 1
    for unit in sorted(available_units):
        result.append({
            "id": unit_id,
            "name": unit
        })
        unit_id += 1
    
    return result

@app.get("/api/batches/{batch_id}/cost_per_unit/{unit_id}")
async def api_batch_cost_per_unit(batch_id: int, unit_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get available units (this is a simplified approach)
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    available_units = set()
    
    for ri in recipe_ingredients:
        ingredient_units = ri.ingredient.get_available_units()
        available_units.update(ingredient_units)
    
    if batch.yield_unit:
        available_units.add(batch.yield_unit)
    
    # Get the unit name by index (simplified)
    sorted_units = sorted(available_units)
    if unit_id <= len(sorted_units):
        unit_name = sorted_units[unit_id - 1]
        
        # Calculate cost per unit
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        
        if batch.yield_unit == unit_name and batch.yield_amount:
            cost_per_unit = total_batch_cost / batch.yield_amount
        else:
            # For now, assume 1:1 conversion (this would need proper unit conversion)
            cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
        
        return {"expected_cost_per_unit": cost_per_unit}
    
    raise HTTPException(status_code=404, detail="Unit not found")

@app.get("/api/batches/{batch_id}/available_units")
async def api_batch_available_units(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get available units from the recipe ingredients
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    available_units = set()
    
    for ri in recipe_ingredients:
        ingredient_units = ri.ingredient.get_available_units()
        available_units.update(ingredient_units)
    
    # Add the batch yield unit
    if batch.yield_unit:
        available_units.add(batch.yield_unit)
    
    return sorted(list(available_units))

@app.get("/api/batches/{batch_id}/labor_stats")
async def api_batch_labor_stats(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get all completed tasks for this batch (both direct batch link and inventory item batch link)
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
            "most_recent_date": "No tasks completed",
            "average_week": batch.estimated_labor_cost,
            "average_month": batch.estimated_labor_cost,
            "average_all_time": batch.estimated_labor_cost,
            "week_task_count": 0,
            "month_task_count": 0
        }
    
    # Calculate statistics
    most_recent = completed_tasks[0]
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
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

@app.get("/api/tasks/{task_id}/scale_options")
async def api_task_scale_options(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task or not task.batch:
        raise HTTPException(status_code=404, detail="Task or batch not found")
    
    return task.batch.get_available_scales()

@app.get("/api/tasks/{task_id}/finish_requirements")
async def api_task_finish_requirements(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result = {"available_units": []}
    
    if task.batch:
        if task.batch.variable_yield:
            # Get available units from recipe ingredients
            recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == task.batch.recipe_id).all()
            available_units = set()
            
            for ri in recipe_ingredients:
                ingredient_units = ri.ingredient.get_available_units()
                available_units.update(ingredient_units)
            
            result["available_units"] = sorted(list(available_units))
        else:
            # Fixed yield - use batch yield unit
            result["available_units"] = [task.batch.yield_unit] if task.batch.yield_unit else []
    
    # Add inventory information if available
    if task.inventory_item:
        day_item = db.query(InventoryDayItem).filter(
            InventoryDayItem.day_id == task.day_id,
            InventoryDayItem.inventory_item_id == task.inventory_item.id
        ).first()
        
        if day_item:
            result["inventory_info"] = {
                "current": day_item.quantity,
                "par_level": task.inventory_item.par_level,
                "par_unit_name": task.inventory_item.par_unit_name.name if task.inventory_item.par_unit_name else "units"
            }
    
    return result