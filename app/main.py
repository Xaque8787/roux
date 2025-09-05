from fastapi import FastAPI, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
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
        ("Dairy", "ingredient"),
        ("Grains", "ingredient"),
        ("Spices", "ingredient"),
        ("Appetizers", "dish"),
        ("Main Courses", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Prep Items", "inventory"),
        ("Prep Items", "batch"),
        ("Sauces", "batch"),
        ("Sides", "batch"),
        ("Cold Storage", "inventory"),
        ("Dry Storage", "inventory"),
        ("Freezer", "inventory")
    ]
    
    try:
        for name, category_type in default_categories:
            # Check if category already exists
            existing = db.query(Category).filter(
                Category.name == name,
                Category.type == category_type
            ).first()
            
            if not existing:
                category = Category(name=name, type=category_type)
                db.add(category)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error creating default categories: {e}")

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
    
    # Create default data
    create_default_categories(db)
    create_default_vendor_units(db)
    create_default_par_unit_names(db)
    
    # Redirect to login page after successful setup
    response = RedirectResponse(url="/login", status_code=302)
    return response

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
        db