from fastapi import FastAPI, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from datetime import datetime, date, timedelta, timezone
from datetime import datetime, timedelta, date, timezone
from typing import List, Optional, Dict, Any
import json

from .database import SessionLocal, engine, get_db
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, VendorUnit, Vendor, ParUnitName
from .auth import hash_password, verify_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Helper function to check if setup is needed
def needs_setup(db: Session):
    return db.query(User).count() == 0

# Helper function to create default categories
def create_default_categories(db: Session):
    default_categories = [
        ("Proteins", "ingredient"),
        ("Vegetables", "ingredient"),
        ("Grains", "ingredient"),
        ("Dairy", "ingredient"),
        ("Spices", "ingredient"),
        ("Appetizers", "dish"),
        ("Entrees", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Prep Items", "batch"),
        ("Sauces", "batch"),
        ("Stocks", "batch"),
        ("Cold Storage", "inventory"),
        ("Dry Storage", "inventory"),
        ("Freezer", "inventory")
    ]
    
    for name, category_type in default_categories:
        # Check if category already exists
        existing = db.query(Category).filter(Category.name == name, Category.type == category_type).first()
        if not existing:
            category = Category(name=name, type=category_type)
            db.add(category)
    
    db.commit()

# Helper function to create default vendor units
def create_default_vendor_units(db: Session):
    default_units = [
        ("lb", "Pounds"),
        ("oz", "Ounces"),
        ("kg", "Kilograms"),
        ("g", "Grams"),
        ("gal", "Gallons"),
        ("qt", "Quarts"),
        ("pt", "Pints"),
        ("cup", "Cups"),
        ("fl_oz", "Fluid Ounces"),
        ("l", "Liters"),
        ("ml", "Milliliters"),
        ("each", "Each/Individual Items"),
        ("dozen", "Dozen (12 items)"),
        ("case", "Case/Box"),
    ]
    
    for name, description in default_units:
        existing = db.query(VendorUnit).filter(VendorUnit.name == name).first()
        if not existing:
            unit = VendorUnit(name=name, description=description)
            db.add(unit)
    
    db.commit()

# Helper function to create default par unit names
def create_default_par_unit_names(db: Session):
    default_par_units = [
        "Tub",
        "Container",
        "Case",
        "Box",
        "Bag",
        "Pan",
        "Sheet",
        "Portion",
        "Batch",
        "Unit"
    ]
    
    for name in default_par_units:
        existing = db.query(ParUnitName).filter(ParUnitName.name == name).first()
        if not existing:
            par_unit = ParUnitName(name=name)
            db.add(par_unit)
    
    db.commit()

# Root redirect
@app.get("/")
async def root():
    return RedirectResponse(url="/home")

# Setup routes
@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    if not needs_setup(db):
        return RedirectResponse(url="/home")
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_post(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not needs_setup(db):
        return RedirectResponse(url="/home")
    
    # Use username as full_name if not provided
    if not full_name.strip():
        full_name = username
    
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
    
    return RedirectResponse(url="/login", status_code=302)

# Authentication routes
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse(url="/setup")
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(
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
    
    if not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Account is inactive"
        })
    
    token = create_jwt({"sub": user.username})
    response = RedirectResponse(url="/home", status_code=302)
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
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response

# Home page
@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Employee management routes
@app.get("/employees", response_class=HTMLResponse)
async def employees_page(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employees = db.query(User).all()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "current_user": current_user,
        "employees": employees
    })

@app.post("/employees/new")
async def create_employee(
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
    
    return RedirectResponse(url="/employees", status_code=302)

@app.get("/employees/{employee_id}", response_class=HTMLResponse)
async def employee_detail(employee_id: int, request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_detail.html", {
        "request": request,
        "current_user": current_user,
        "employee": employee
    })

@app.get("/employees/{employee_id}/edit", response_class=HTMLResponse)
async def employee_edit_form(employee_id: int, request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
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
    password: str = Form(""),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form(...),
    is_active: bool = Form(False),
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
    employee.is_active = is_active
    
    if password:
        employee.hashed_password = hash_password(password)
    
    db.commit()
    
    return RedirectResponse(url=f"/employees/{employee_id}", status_code=302)

@app.get("/employees/{employee_id}/delete")
async def employee_delete(employee_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if employee_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Deactivate instead of delete to preserve data integrity
    employee.is_active = False
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)

# Category management
@app.post("/categories/new")
async def create_category(
    name: str = Form(...),
    type: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    category = Category(name=name, type=type)
    db.add(category)
    db.commit()
    
    # Redirect based on type
    redirect_map = {
        "ingredient": "/ingredients",
        "recipe": "/recipes",
        "batch": "/batches",
        "dish": "/dishes",
        "inventory": "/inventory"
    }
    return RedirectResponse(url=redirect_map.get(type, "/home"), status_code=302)

# Vendor management
@app.post("/vendors/new")
async def create_vendor(
    name: str = Form(...),
    contact_info: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    vendor = Vendor(name=name, contact_info=contact_info)
    db.add(vendor)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

# Par Unit Name management
@app.post("/par_unit_names/new")
async def create_par_unit_name(
    name: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    par_unit = ParUnitName(name=name)
    db.add(par_unit)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

# Ingredient routes
@app.get("/ingredients", response_class=HTMLResponse)
async def ingredients_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).options(joinedload(Ingredient.category), joinedload(Ingredient.vendor)).all()
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
async def create_ingredient(
    name: str = Form(...),
    usage_type: str = Form(...),
    category_id: Optional[int] = Form(None),
    vendor_id: Optional[int] = Form(None),
    vendor_unit_id: Optional[int] = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    purchase_total_cost: float = Form(...),
    net_weight_volume_item: float = Form(...),
    net_unit: str = Form(...),
    net_weight_volume_case: Optional[float] = Form(None),
    items_per_case: Optional[int] = Form(None),
    breakable_case: bool = Form(False),
    has_baking_conversion: bool = Form(False),
    baking_measurement_unit: Optional[str] = Form(None),
    baking_weight_amount: Optional[float] = Form(None),
    baking_weight_unit: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = Ingredient(
        name=name,
        usage_type=usage_type,
        category_id=category_id if category_id else None,
        vendor_id=vendor_id if vendor_id else None,
        vendor_unit_id=vendor_unit_id if vendor_unit_id else None,
        purchase_type=purchase_type,
        purchase_unit_name=purchase_unit_name,
        purchase_total_cost=purchase_total_cost,
        net_weight_volume_item=net_weight_volume_item,
        net_unit=net_unit,
        net_weight_volume_case=net_weight_volume_case,
        items_per_case=items_per_case,
        breakable_case=breakable_case,
        has_baking_conversion=has_baking_conversion,
        baking_measurement_unit=baking_measurement_unit,
        baking_weight_amount=baking_weight_amount,
        baking_weight_unit=baking_weight_unit
    )
    
    # Calculate net_weight_volume_case if not provided
    if purchase_type == 'case' and items_per_case and not net_weight_volume_case:
        ingredient.net_weight_volume_case = net_weight_volume_item * items_per_case
    
    db.add(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

@app.get("/ingredients/{ingredient_id}", response_class=HTMLResponse)
async def ingredient_detail(ingredient_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).options(
        joinedload(Ingredient.category),
        joinedload(Ingredient.vendor),
        joinedload(Ingredient.vendor_unit)
    ).filter(Ingredient.id == ingredient_id).first()
    
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    return templates.TemplateResponse("ingredient_detail.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient
    })

@app.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
async def ingredient_edit_form(ingredient_id: int, request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).options(
        joinedload(Ingredient.category),
        joinedload(Ingredient.vendor)
    ).filter(Ingredient.id == ingredient_id).first()
    
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

@app.get("/ingredients/{ingredient_id}/delete")
async def ingredient_delete(ingredient_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    db.delete(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

# Recipe routes
@app.get("/recipes", response_class=HTMLResponse)
async def recipes_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipes = db.query(Recipe).options(joinedload(Recipe.category)).all()
    categories = db.query(Category).filter(Category.type == "recipe").all()
    
    return templates.TemplateResponse("recipes.html", {
        "request": request,
        "current_user": current_user,
        "recipes": recipes,
        "categories": categories
    })

@app.post("/recipes/new")
async def create_recipe(
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: Optional[int] = Form(None),
    ingredients_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = Recipe(
        name=name,
        instructions=instructions,
        category_id=category_id if category_id else None
    )
    db.add(recipe)
    db.flush()  # Get the recipe ID
    
    # Parse ingredients data
    try:
        ingredients = json.loads(ingredients_data)
        for ing_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ing_data['ingredient_id'],
                unit=ing_data['unit'],
                quantity=ing_data['quantity']
            )
            db.add(recipe_ingredient)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid ingredients data")
    
    db.commit()
    
    return RedirectResponse(url="/recipes", status_code=302)

@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(recipe_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipe = db.query(Recipe).options(joinedload(Recipe.category)).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.category)
    ).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
    total_cost = sum(ri.cost for ri in recipe_ingredients)
    
    return templates.TemplateResponse("recipe_detail.html", {
        "request": request,
        "current_user": current_user,
        "recipe": recipe,
        "recipe_ingredients": recipe_ingredients,
        "total_cost": total_cost
    })

@app.get("/recipes/{recipe_id}/edit", response_class=HTMLResponse)
async def recipe_edit_form(recipe_id: int, request: Request, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
    recipe = db.query(Recipe).options(joinedload(Recipe.category)).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient)
    ).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
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
    instructions: str = Form(""),
    category_id: Optional[int] = Form(None),
    ingredients_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe.name = name
    recipe.instructions = instructions
    recipe.category_id = category_id if category_id else None
    
    # Delete existing ingredients
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
    # Add new ingredients
    try:
        ingredients = json.loads(ingredients_data)
        for ing_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ing_data['ingredient_id'],
                unit=ing_data['unit'],
                quantity=ing_data['quantity']
            )
            db.add(recipe_ingredient)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid ingredients data")
    
    db.commit()
    
    return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=302)

@app.get("/recipes/{recipe_id}/delete")
async def recipe_delete(recipe_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    db.delete(recipe)
    db.commit()
    
    return RedirectResponse(url="/recipes", status_code=302)

# Batch routes
@app.get("/batches", response_class=HTMLResponse)
async def batches_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batches = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category)
    ).all()
    recipes = db.query(Recipe).all()
    
    return templates.TemplateResponse("batches.html", {
        "request": request,
        "current_user": current_user,
        "batches": batches,
        "recipes": recipes
    })

@app.post("/batches/new")
async def create_batch(
    recipe_id: int = Form(...),
    variable_yield: bool = Form(False),
    yield_amount: Optional[float] = Form(None),
    yield_unit: Optional[str] = Form(None),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(...),
    can_be_scaled: bool = Form(False),
    scale_double: bool = Form(False),
    scale_half: bool = Form(False),
    scale_quarter: bool = Form(False),
    scale_eighth: bool = Form(False),
    scale_sixteenth: bool = Form(False),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    batch = Batch(
        recipe_id=recipe_id,
        variable_yield=variable_yield,
        yield_amount=yield_amount if not variable_yield else None,
        yield_unit=yield_unit if not variable_yield else None,
        estimated_labor_minutes=estimated_labor_minutes,
        hourly_labor_rate=hourly_labor_rate,
        can_be_scaled=can_be_scaled,
        scale_double=scale_double if can_be_scaled else False,
        scale_half=scale_half if can_be_scaled else False,
        scale_quarter=scale_quarter if can_be_scaled else False,
        scale_eighth=scale_eighth if can_be_scaled else False,
        scale_sixteenth=scale_sixteenth if can_be_scaled else False
    )
    db.add(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=302)

@app.get("/batches/{batch_id}", response_class=HTMLResponse)
async def batch_detail(batch_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category)
    ).filter(Batch.id == batch_id).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get recipe ingredients
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.category)
    ).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    
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
async def batch_edit_form(batch_id: int, request: Request, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
    batch = db.query(Batch).options(joinedload(Batch.recipe)).filter(Batch.id == batch_id).first()
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
    variable_yield: bool = Form(False),
    yield_amount: Optional[float] = Form(None),
    yield_unit: Optional[str] = Form(None),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(...),
    can_be_scaled: bool = Form(False),
    scale_double: bool = Form(False),
    scale_half: bool = Form(False),
    scale_quarter: bool = Form(False),
    scale_eighth: bool = Form(False),
    scale_sixteenth: bool = Form(False),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    batch.recipe_id = recipe_id
    batch.variable_yield = variable_yield
    batch.yield_amount = yield_amount if not variable_yield else None
    batch.yield_unit = yield_unit if not variable_yield else None
    batch.estimated_labor_minutes = estimated_labor_minutes
    batch.hourly_labor_rate = hourly_labor_rate
    batch.can_be_scaled = can_be_scaled
    batch.scale_double = scale_double if can_be_scaled else False
    batch.scale_half = scale_half if can_be_scaled else False
    batch.scale_quarter = scale_quarter if can_be_scaled else False
    batch.scale_eighth = scale_eighth if can_be_scaled else False
    batch.scale_sixteenth = scale_sixteenth if can_be_scaled else False
    
    db.commit()
    
    return RedirectResponse(url=f"/batches/{batch_id}", status_code=302)

@app.get("/batches/{batch_id}/delete")
async def batch_delete(batch_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    db.delete(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=302)

# Dish routes
@app.get("/dishes", response_class=HTMLResponse)
async def dishes_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dishes = db.query(Dish).options(joinedload(Dish.category)).all()
    categories = db.query(Category).filter(Category.type == "dish").all()
    
    return templates.TemplateResponse("dishes.html", {
        "request": request,
        "current_user": current_user,
        "dishes": dishes,
        "categories": categories
    })

@app.post("/dishes/new")
async def create_dish(
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = Dish(
        name=name,
        category_id=category_id if category_id else None,
        sale_price=sale_price,
        description=description
    )
    db.add(dish)
    db.flush()  # Get the dish ID
    
    # Parse batch portions data
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            dish_batch_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data['batch_id'],
                portion_size=portion_data['portion_size'],
                portion_unit=portion_data.get('portion_unit_name', '')
            )
            db.add(dish_batch_portion)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid batch portions data")
    
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=302)

@app.get("/dishes/{dish_id}", response_class=HTMLResponse)
async def dish_detail(dish_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dish = db.query(Dish).options(joinedload(Dish.category)).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).options(
        joinedload(DishBatchPortion.batch).joinedload(Batch.recipe)
    ).filter(DishBatchPortion.dish_id == dish_id).all()
    
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
async def dish_edit_form(dish_id: int, request: Request, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
    dish = db.query(Dish).options(joinedload(Dish.category)).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).options(
        joinedload(DishBatchPortion.batch).joinedload(Batch.recipe)
    ).filter(DishBatchPortion.dish_id == dish_id).all()
    
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
    description: str = Form(""),
    batch_portions_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish.name = name
    dish.category_id = category_id if category_id else None
    dish.sale_price = sale_price
    dish.description = description
    
    # Delete existing batch portions
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Add new batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            dish_batch_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data['batch_id'],
                portion_size=portion_data['portion_size'],
                portion_unit=portion_data.get('portion_unit_name', '')
            )
            db.add(dish_batch_portion)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid batch portions data")
    
    db.commit()
    
    return RedirectResponse(url=f"/dishes/{dish_id}", status_code=302)

@app.get("/dishes/{dish_id}/delete")
async def dish_delete(dish_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    db.delete(dish)
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=302)

# Inventory routes
@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).options(
        joinedload(InventoryItem.category),
        joinedload(InventoryItem.batch).joinedload(Batch.recipe),
        joinedload(InventoryItem.par_unit_name)
    ).all()
    
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).options(joinedload(Batch.recipe)).all()
    par_unit_names = db.query(ParUnitName).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get current day
    current_day = db.query(InventoryDay).filter(
        InventoryDay.finalized == False
    ).order_by(desc(InventoryDay.date)).first()
    
    # Get recent finalized days
    finalized_days = db.query(InventoryDay).filter(
        InventoryDay.finalized == True,
        InventoryDay.date >= date.today() - timedelta(days=30)
    ).order_by(desc(InventoryDay.date)).limit(10).all()
    
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
        "today_date": date.today().isoformat()
    })

@app.post("/inventory/new_item")
async def create_inventory_item(
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
    
    return RedirectResponse(url="/inventory", status_code=302)

@app.post("/inventory/new_day")
async def create_inventory_day(
    date: date = Form(...),
    employees_working: List[int] = Form(...),
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if existing_day:
        return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=302)
    
    inventory_day = InventoryDay(
        date=date,
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
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

@app.get("/inventory/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_detail(day_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item).joinedload(InventoryItem.batch).joinedload(Batch.recipe),
        joinedload(InventoryDayItem.inventory_item).joinedload(InventoryItem.par_unit_name)
    ).filter(InventoryDayItem.day_id == day_id).all()
    
    tasks = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.inventory_item),
        joinedload(Task.batch).joinedload(Batch.recipe)
    ).filter(Task.day_id == day_id).all()
    
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
        "task_summaries": task_summaries,
        "employees": employees
    })

@app.post("/inventory/day/{day_id}/update")
async def update_inventory_day(
    day_id: int,
    request: Request,
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot update finalized day")
    
    inventory_day.global_notes = global_notes
    
    # Get form data
    form_data = await request.form()
    
    # Update inventory quantities
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    for item in inventory_day_items:
        quantity_key = f"item_{item.inventory_item_id}"
        override_create_key = f"override_create_{item.inventory_item_id}"
        override_no_task_key = f"override_no_task_{item.inventory_item_id}"
        
        if quantity_key in form_data:
            item.quantity = float(form_data[quantity_key])
        
        item.override_create_task = override_create_key in form_data
        item.override_no_task = override_no_task_key in form_data
    
    # Generate tasks for below-par items
    generate_tasks_for_day(inventory_day, db)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/new")
async def create_manual_task(
    day_id: int,
    assigned_to_ids: List[int] = Form([]),
    inventory_item_id: Optional[int] = Form(None),
    description: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot add tasks to finalized day")
    
    # Create tasks for each assigned employee or one unassigned task
    if assigned_to_ids:
        for assigned_to_id in assigned_to_ids:
            task = Task(
                day_id=day_id,
                assigned_to_id=assigned_to_id,
                inventory_item_id=inventory_item_id if inventory_item_id else None,
                description=description,
                auto_generated=False
            )
            
            # Set batch_id if inventory item has a linked batch
            if inventory_item_id:
                inventory_item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
                if inventory_item and inventory_item.batch_id:
                    task.batch_id = inventory_item.batch_id
            
            db.add(task)
    else:
        # Create unassigned task
        task = Task(
            day_id=day_id,
            assigned_to_id=None,
            inventory_item_id=inventory_item_id if inventory_item_id else None,
            description=description,
            auto_generated=False
        )
        
        # Set batch_id if inventory item has a linked batch
        if inventory_item_id:
            inventory_item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
            if inventory_item and inventory_item.batch_id:
                task.batch_id = inventory_item.batch_id
        
        db.add(task)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/assign")
async def assign_task(
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
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start")
async def start_task(
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
    
    task.started_at = datetime.now(timezone.utc)
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start_with_scale")
async def start_task_with_scale(
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
    task.started_at = datetime.now(timezone.utc)
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/pause")
async def pause_task(
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
    
    task.paused_at = datetime.now(timezone.utc)
    task.is_paused = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/resume")
async def resume_task(
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
    pause_duration = (datetime.now(timezone.utc) - task.paused_at).total_seconds()
    task.total_pause_time += int(pause_duration)
    task.paused_at = None
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish")
async def finish_task(
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
    
    # If task was paused, add final pause time
    if task.is_paused and task.paused_at:
        pause_duration = (datetime.now(timezone.utc) - task.paused_at).total_seconds()
        task.total_pause_time += int(pause_duration)
    
    task.finished_at = datetime.now(timezone.utc)
    task.is_paused = False
    task.paused_at = None
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish_with_amount")
async def finish_task_with_amount(
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
        raise HTTPException(status_code=400, detail="Task not in progress")
    
    # Set made amount
    task.made_amount = made_amount
    task.made_unit = made_unit
    
    # If task was paused, add final pause time
    if task.is_paused and task.paused_at:
        pause_duration = (datetime.now(timezone.utc) - task.paused_at).total_seconds()
        task.total_pause_time += int(pause_duration)
    
    task.finished_at = datetime.now(timezone.utc)
    task.is_paused = False
    task.paused_at = None
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.get("/inventory/day/{day_id}/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(day_id: int, task_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    task = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.inventory_item).joinedload(InventoryItem.par_unit_name),
        joinedload(Task.batch).joinedload(Batch.recipe)
    ).filter(Task.id == task_id, Task.day_id == day_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate task summary if completed
    task_summary = None
    if task.status == "completed" and task.inventory_item:
        task_summary = calculate_task_summary(task, db)
    
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "task": task,
        "task_summary": task_summary,
        "employees": employees
    })

@app.post("/inventory/day/{day_id}/tasks/{task_id}/notes")
async def update_task_notes(
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
    
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)

@app.post("/inventory/day/{day_id}/finalize")
async def finalize_inventory_day(
    day_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Day already finalized")
    
    inventory_day.finalized = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/reports/{day_id}", status_code=302)

@app.get("/inventory/reports/{day_id}", response_class=HTMLResponse)
async def inventory_report(day_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item)
    ).filter(InventoryDayItem.day_id == day_id).all()
    
    tasks = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.inventory_item),
        joinedload(Task.batch).joinedload(Batch.recipe)
    ).filter(Task.day_id == day_id).all()
    
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
async def inventory_item_edit_form(item_id: int, request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.query(InventoryItem).options(
        joinedload(InventoryItem.category),
        joinedload(InventoryItem.batch).joinedload(Batch.recipe),
        joinedload(InventoryItem.par_unit_name)
    ).filter(InventoryItem.id == item_id).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).options(joinedload(Batch.recipe)).all()
    par_unit_names = db.query(ParUnitName).all()
    
    return templates.TemplateResponse("inventory_item_edit.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "categories": categories,
        "batches": batches,
        "par_unit_names": par_unit_names
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
    
    return RedirectResponse(url="/inventory", status_code=302)

@app.get("/inventory/items/{item_id}/delete")
async def inventory_item_delete(item_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    db.delete(item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

# Utility routes
@app.get("/utilities", response_class=HTMLResponse)
async def utilities_page(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    utilities = db.query(UtilityCost).all()
    
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "current_user": current_user,
        "utilities": utilities
    })

@app.post("/utilities/new")
async def create_utility(
    name: str = Form(...),
    monthly_cost: float = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Check if utility already exists
    existing = db.query(UtilityCost).filter(UtilityCost.name == name).first()
    if existing:
        existing.monthly_cost = monthly_cost
        existing.last_updated = datetime.now(timezone.utc)
    else:
        utility = UtilityCost(name=name, monthly_cost=monthly_cost)
        db.add(utility)
    
    db.commit()
    
    return RedirectResponse(url="/utilities", status_code=302)

@app.post("/utilities/{utility_id}/delete")
async def utility_delete(utility_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
    if not utility:
        raise HTTPException(status_code=404, detail="Utility not found")
    
    db.delete(utility)
    db.commit()
    
    return RedirectResponse(url="/utilities", status_code=302)

# API Routes
@app.get("/api/ingredients/all")
async def api_ingredients_all(db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).options(joinedload(Ingredient.category)).all()
    
    result = []
    for ingredient in ingredients:
        available_units = ingredient.get_available_units()
        result.append({
            "id": ingredient.id,
            "name": ingredient.name,
            "category": ingredient.category.name if ingredient.category else None,
            "available_units": available_units
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
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient)
    ).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
    units_set = set()
    for ri in recipe_ingredients:
        if ri.ingredient:
            available_units = ri.ingredient.get_available_units()
            units_set.update(available_units)
    
    return list(units_set) if units_set else ["units"]

@app.get("/api/batches/all")
async def api_batches_all(db: Session = Depends(get_db)):
    batches = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category)
    ).all()
    
    result = []
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == batch.recipe_id
        ).all()
        
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
        
        result.append({
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "category": batch.recipe.category.name if batch.recipe.category else None,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit,
            "cost_per_unit": cost_per_unit
        })
    
    return result

@app.get("/api/batches/search")
async def api_batches_search(q: str, db: Session = Depends(get_db)):
    batches = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category)
    ).join(Recipe).filter(
        Recipe.name.ilike(f"%{q}%")
    ).all()
    
    result = []
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == batch.recipe_id
        ).all()
        
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
        
        result.append({
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "category": batch.recipe.category.name if batch.recipe.category else None,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit,
            "cost_per_unit": cost_per_unit
        })
    
    return result

@app.get("/api/batches/{batch_id}/portion_units")
async def api_batch_portion_units(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # For now, return the yield unit
    # In the future, this could be expanded to include compatible units
    units = []
    if batch.yield_unit:
        units.append({
            "id": 1,  # Placeholder ID
            "name": batch.yield_unit
        })
    
    return units

@app.get("/api/batches/{batch_id}/cost_per_unit/{unit_id}")
async def api_batch_cost_per_unit(batch_id: int, unit_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Calculate cost per unit
    recipe_ingredients = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == batch.recipe_id
    ).all()
    
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
    expected_cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
    
    return {"expected_cost_per_unit": expected_cost_per_unit}

@app.get("/api/batches/{batch_id}/available_units")
async def api_batch_available_units(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get available units from the recipe ingredients
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient)
    ).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    
    units_set = set()
    for ri in recipe_ingredients:
        if ri.ingredient:
            available_units = ri.ingredient.get_available_units()
            units_set.update(available_units)
    
    # Add the batch yield unit if it exists
    if batch.yield_unit:
        units_set.add(batch.yield_unit)
    
    return list(units_set) if units_set else ["units"]


@app.get("/api/batches/{batch_id}/labor_stats")
async def api_batch_labor_stats(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
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
            "average_week": batch.estimated_labor_cost,
            "average_month": batch.estimated_labor_cost,
            "average_all_time": batch.estimated_labor_cost,
            "week_task_count": 0,
            "month_task_count": 0
        }
    
    # Calculate statistics
    most_recent = completed_tasks[0]
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
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
    task = db.query(Task).options(joinedload(Task.batch)).filter(Task.id == task_id).first()
    if not task or not task.batch:
        raise HTTPException(status_code=404, detail="Task or batch not found")
    
    scales = task.batch.get_available_scales()
    
    result = []
    for scale_key, scale_factor, scale_label in scales:
        if task.batch.yield_amount:
            yield_amount = task.batch.get_scaled_yield(scale_factor)
            yield_text = f"{yield_amount} {task.batch.yield_unit}"
        else:
            yield_text = "Variable yield"
        
        result.append({
            "key": scale_key,
            "factor": scale_factor,
            "label": scale_label,
            "yield": yield_text
        })
    
    return result

@app.get("/api/tasks/{task_id}/finish_requirements")
async def get_task_finish_requirements(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).options(
        joinedload(Task.batch),
        joinedload(Task.inventory_item).joinedload(InventoryItem.par_unit_name)
    ).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Determine available units
    unit = "units"  # Default fallback
    
    if task.batch and task.batch.variable_yield and task.inventory_item:
        # Variable yield batch with inventory item - use inventory item's unit configuration
        if task.inventory_item.par_unit_equals_type == "par_unit_itself":
            unit = task.inventory_item.par_unit_name.name if task.inventory_item.par_unit_name else "units"
        elif task.inventory_item.par_unit_equals_type == "custom":
            unit = task.inventory_item.par_unit_equals_unit or "units"
        elif task.inventory_item.par_unit_equals_type == "auto":
            unit = task.batch.yield_unit or "units"
    elif task.batch:
        # Any batch - use batch yield unit
        unit = task.batch.yield_unit or "units"
    
    # Get inventory info if available
    inventory_info = None
    if task.inventory_item:
        day_item = db.query(InventoryDayItem).filter(
            InventoryDayItem.day_id == task.day_id,
            InventoryDayItem.inventory_item_id == task.inventory_item.id
        ).first()
        
        if day_item:
            inventory_info = {
                "current": day_item.quantity,
                "par_level": task.inventory_item.par_level,
                "par_unit_name": task.inventory_item.par_unit_name.name if task.inventory_item.par_unit_name else "units"
            }
    
    return {
        "available_units": [unit],
        "inventory_info": inventory_info
    }

# Helper functions
def generate_tasks_for_day(inventory_day: InventoryDay, db: Session):
    """Generate tasks for below-par items"""
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item).joinedload(InventoryItem.batch).joinedload(Batch.recipe)
    ).filter(InventoryDayItem.day_id == inventory_day.id).all()
    
    # Get working employees
    working_employee_ids = []
    if inventory_day.employees_working:
        working_employee_ids = [int(id) for id in inventory_day.employees_working.split(',')]
    
    for item in inventory_day_items:
        is_below_par = item.quantity <= item.inventory_item.par_level
        
        # Check if we should create a task
        should_create_task = False
        if is_below_par and not item.override_no_task:
            should_create_task = True
        elif not is_below_par and item.override_create_task:
            should_create_task = True
        
        if should_create_task:
            # Check if task already exists for this item
            existing_task = db.query(Task).filter(
                Task.day_id == inventory_day.id,
                Task.inventory_item_id == item.inventory_item.id,
                Task.auto_generated == True
            ).first()
            
            if not existing_task:
                # Create task description
                if item.inventory_item.batch:
                    description = f"Make {item.inventory_item.name} ({item.inventory_item.batch.recipe.name})"
                else:
                    description = f"Restock {item.inventory_item.name}"
                
                # Assign to first working employee or leave unassigned
                assigned_to_id = working_employee_ids[0] if working_employee_ids else None
                
                task = Task(
                    day_id=inventory_day.id,
                    assigned_to_id=assigned_to_id,
                    inventory_item_id=item.inventory_item.id,
                    batch_id=item.inventory_item.batch_id,
                    description=description,
                    auto_generated=True
                )
                db.add(task)

def calculate_task_summary(task: Task, db: Session) -> Optional[Dict[str, Any]]:
    """Calculate task summary information for completed tasks"""
    if not task.inventory_item or task.status != "completed":
        return None
    
    inventory_item = task.inventory_item
    
    # Get the inventory day item
    day_item = db.query(InventoryDayItem).filter(
        InventoryDayItem.day_id == task.day_id,
        InventoryDayItem.inventory_item_id == inventory_item.id
    ).first()
    
    if not day_item:
        return None
    
    summary = {
        "par_level": inventory_item.par_level,
        "par_unit_name": inventory_item.par_unit_name.name if inventory_item.par_unit_name else "units",
        "par_unit_equals_type": inventory_item.par_unit_equals_type,
        "par_unit_equals": inventory_item.par_unit_equals_calculated,
        "par_unit_equals_unit": inventory_item.par_unit_equals_unit,
        "initial_inventory": day_item.quantity,
        "initial_converted": None,
        "made_amount": task.made_amount,
        "made_unit": task.made_unit,
        "made_par_units": 0.0,
        "made_converted": None,
        "made_amount_par_units": 0.0,
        "final_inventory": day_item.quantity,
        "final_converted": None
    }
    
    # Calculate conversions if we have par unit equals
    if inventory_item.par_unit_equals_calculated and inventory_item.par_unit_equals_unit:
        summary["initial_converted"] = day_item.quantity * inventory_item.par_unit_equals_calculated
    
    # Calculate made amount in par units
    if task.made_amount and task.made_unit:
        # Convert made amount to par units
        made_par_units = inventory_item.convert_to_par_units(task.made_amount, task.made_unit)
        summary["made_par_units"] = made_par_units
        summary["made_amount_par_units"] = made_par_units
        
        # Calculate made converted amount
        if inventory_item.par_unit_equals_calculated and inventory_item.par_unit_equals_unit:
            summary["made_converted"] = made_par_units * inventory_item.par_unit_equals_calculated
    elif task.batch and not task.batch.variable_yield and task.scale_factor:
        # For fixed yield batches with scaling, calculate made amount from batch yield
        batch_yield_amount = task.batch.yield_amount * task.scale_factor
        batch_yield_unit = task.batch.yield_unit
        
        # Convert batch yield to par units
        made_par_units = inventory_item.convert_to_par_units(batch_yield_amount, batch_yield_unit)
        summary["made_par_units"] = made_par_units
        summary["made_amount_par_units"] = made_par_units
        summary["made_amount"] = batch_yield_amount
        summary["made_unit"] = batch_yield_unit
        
        # Calculate made converted amount
        if inventory_item.par_unit_equals_calculated and inventory_item.par_unit_equals_unit:
            summary["made_converted"] = made_par_units * inventory_item.par_unit_equals_calculated
    
    # Calculate final inventory
    summary["final_inventory"] = summary["initial_inventory"] + summary["made_amount_par_units"]
    
    # Calculate final converted amount
    if inventory_item.par_unit_equals_calculated and inventory_item.par_unit_equals_unit:
        summary["final_converted"] = summary["final_inventory"] * inventory_item.par_unit_equals_calculated
    
    return summary

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login")
    elif exc.status_code == 403:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "status_code": exc.status_code,
            "detail": exc.detail
        }, status_code=exc.status_code)
    else:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "status_code": exc.status_code,
            "detail": exc.detail
        }, status_code=exc.status_code)