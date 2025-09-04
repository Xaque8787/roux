from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func
from datetime import datetime, date, timedelta
from typing import Optional, List
import json

from .database import get_db, engine
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, Vendor, VendorUnit, ParUnitName
from .auth import get_current_user, require_admin, require_manager_or_admin, require_user_or_above, hash_password, create_jwt, verify_password
from .schemas import *

# Create tables
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
        ("Appetizers", "recipe"),
        ("Main Courses", "recipe"),
        ("Desserts", "recipe"),
        ("Sides", "recipe"),
        ("Prep Items", "batch"),
        ("Sauces", "batch"),
        ("Proteins", "dish"),
        ("Appetizers", "dish"),
        ("Desserts", "dish"),
        ("Fresh Items", "inventory"),
        ("Dry Goods", "inventory"),
        ("Frozen Items", "inventory"),
    ]
    
    for name, cat_type in default_categories:
        existing = db.query(Category).filter(Category.name == name, Category.type == cat_type).first()
        if not existing:
            category = Category(name=name, type=cat_type)
            db.add(category)
    
    db.commit()

# Helper function to create default vendor units
def create_default_vendor_units(db: Session):
    default_units = [
        ("lb", "Pounds"),
        ("oz", "Ounces"),
        ("gal", "Gallons"),
        ("qt", "Quarts"),
        ("pt", "Pints"),
        ("cup", "Cups"),
        ("fl_oz", "Fluid Ounces"),
        ("g", "Grams"),
        ("kg", "Kilograms"),
        ("l", "Liters"),
        ("ml", "Milliliters"),
        ("each", "Each/Individual Items"),
        ("dozen", "Dozen (12 items)"),
        ("case", "Case (varies by product)"),
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
        "Case", 
        "Container",
        "Bag",
        "Box",
        "Bottle",
        "Can",
        "Jar",
        "Package",
        "Bundle",
        "Sheet Pan",
        "Hotel Pan",
        "Portion",
    ]
    
    for name in default_par_units:
        existing = db.query(ParUnitName).filter(ParUnitName.name == name).first()
        if not existing:
            par_unit = ParUnitName(name=name)
            db.add(par_unit)
    
    db.commit()

# Setup route
@app.get("/setup", response_class=HTMLResponse)
def setup_form(request: Request, db: Session = Depends(get_db)):
    if not needs_setup(db):
        return RedirectResponse(url="/home", status_code=302)
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
def create_admin_user(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not needs_setup(db):
        return RedirectResponse(url="/home", status_code=302)
    
    # Use username as full_name if not provided
    if not full_name.strip():
        full_name = username
    
    # Create admin user
    hashed_password = hash_password(password)
    admin_user = User(
        username=username,
        full_name=full_name,
        hashed_password=hashed_password,
        role="admin",
        is_admin=True,
        is_user=True,
        hourly_wage=20.0
    )
    db.add(admin_user)
    db.commit()
    
    # Create default categories, vendor units, and par unit names
    create_default_categories(db)
    create_default_vendor_units(db)
    create_default_par_unit_names(db)
    
    return RedirectResponse(url="/login", status_code=302)

# Login routes
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse(url="/setup", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(
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
            "error": "Account is deactivated"
        })
    
    # Create JWT token
    token = create_jwt({"sub": user.username})
    
    # Create response and set cookie
    response = RedirectResponse(url="/home", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=1800,  # 30 minutes
        samesite="lax"
    )
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response

# Home route
@app.get("/", response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse(url="/setup", status_code=302)
    return RedirectResponse(url="/home", status_code=302)

@app.get("/home", response_class=HTMLResponse)
def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Employee management routes (Admin only)
@app.get("/employees", response_class=HTMLResponse)
def employees_list(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employees = db.query(User).all()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "current_user": current_user,
        "employees": employees
    })

@app.post("/employees/new")
def create_employee(
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
        username=username,
        full_name=full_name,
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
def employee_detail(employee_id: int, request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_detail.html", {
        "request": request,
        "current_user": current_user,
        "employee": employee
    })

@app.get("/employees/{employee_id}/edit", response_class=HTMLResponse)
def employee_edit_form(employee_id: int, request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_edit.html", {
        "request": request,
        "current_user": current_user,
        "employee": employee
    })

@app.post("/employees/{employee_id}/edit")
def employee_edit(
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
def employee_delete(employee_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if employee_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Deactivate instead of delete to preserve task history
    employee.is_active = False
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)

# Category management
@app.post("/categories/new")
def create_category(
    name: str = Form(...),
    type: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    category = Category(name=name, type=type)
    db.add(category)
    db.commit()
    
    # Redirect based on type
    if type == "ingredient":
        return RedirectResponse(url="/ingredients", status_code=302)
    elif type == "recipe":
        return RedirectResponse(url="/recipes", status_code=302)
    elif type == "batch":
        return RedirectResponse(url="/batches", status_code=302)
    elif type == "dish":
        return RedirectResponse(url="/dishes", status_code=302)
    elif type == "inventory":
        return RedirectResponse(url="/inventory", status_code=302)
    else:
        return RedirectResponse(url="/home", status_code=302)

# Vendor management
@app.post("/vendors/new")
def create_vendor(
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
def create_par_unit_name(
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
def ingredients_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
def create_ingredient(
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
    breakable_case: bool = Form(False),
    items_per_case: Optional[int] = Form(None),
    has_baking_conversion: bool = Form(False),
    baking_measurement_unit: Optional[str] = Form(None),
    baking_weight_amount: Optional[float] = Form(None),
    baking_weight_unit: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Calculate net_weight_volume_case if not provided
    if purchase_type == "case" and items_per_case and not net_weight_volume_case:
        net_weight_volume_case = net_weight_volume_item * items_per_case
    
    ingredient = Ingredient(
        name=name,
        usage_type=usage_type,
        category_id=category_id,
        vendor_id=vendor_id,
        vendor_unit_id=vendor_unit_id,
        purchase_type=purchase_type,
        purchase_unit_name=purchase_unit_name,
        net_weight_volume_item=net_weight_volume_item,
        net_weight_volume_case=net_weight_volume_case,
        net_unit=net_unit,
        purchase_total_cost=purchase_total_cost,
        breakable_case=breakable_case,
        items_per_case=items_per_case,
        has_baking_conversion=has_baking_conversion,
        baking_measurement_unit=baking_measurement_unit,
        baking_weight_amount=baking_weight_amount,
        baking_weight_unit=baking_weight_unit
    )
    
    db.add(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

@app.get("/ingredients/{ingredient_id}", response_class=HTMLResponse)
def ingredient_detail(ingredient_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
def ingredient_edit_form(ingredient_id: int, request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
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

@app.post("/ingredients/{ingredient_id}/edit")
def ingredient_edit(
    ingredient_id: int,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    vendor_id: Optional[int] = Form(None),
    vendor_unit_id: Optional[int] = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    ingredient.name = name
    ingredient.category_id = category_id
    ingredient.vendor_id = vendor_id
    ingredient.vendor_unit_id = vendor_unit_id
    ingredient.purchase_type = purchase_type
    ingredient.purchase_unit_name = purchase_unit_name
    ingredient.purchase_total_cost = purchase_total_cost
    ingredient.breakable_case = breakable_case
    ingredient.items_per_case = items_per_case
    
    db.commit()
    
    return RedirectResponse(url=f"/ingredients/{ingredient_id}", status_code=302)

@app.get("/ingredients/{ingredient_id}/delete")
def ingredient_delete(ingredient_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    db.delete(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

# Recipe routes
@app.get("/recipes", response_class=HTMLResponse)
def recipes_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipes = db.query(Recipe).options(joinedload(Recipe.category)).all()
    categories = db.query(Category).filter(Category.type == "recipe").all()
    
    return templates.TemplateResponse("recipes.html", {
        "request": request,
        "current_user": current_user,
        "recipes": recipes,
        "categories": categories
    })

@app.post("/recipes/new")
def create_recipe(
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
        category_id=category_id
    )
    db.add(recipe)
    db.flush()  # Get the recipe ID
    
    # Parse ingredients data
    ingredients = json.loads(ingredients_data)
    for ing_data in ingredients:
        recipe_ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=ing_data['ingredient_id'],
            unit=ing_data['unit'],
            quantity=ing_data['quantity']
        )
        db.add(recipe_ingredient)
    
    db.commit()
    
    return RedirectResponse(url="/recipes", status_code=302)

@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
def recipe_detail(recipe_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
def recipe_edit_form(recipe_id: int, request: Request, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
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
def recipe_edit(
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
    recipe.category_id = category_id
    
    # Delete existing ingredients
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
    # Add new ingredients
    ingredients = json.loads(ingredients_data)
    for ing_data in ingredients:
        recipe_ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=ing_data['ingredient_id'],
            unit=ing_data['unit'],
            quantity=ing_data['quantity']
        )
        db.add(recipe_ingredient)
    
    db.commit()
    
    return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=302)

@app.get("/recipes/{recipe_id}/delete")
def recipe_delete(recipe_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    db.delete(recipe)
    db.commit()
    
    return RedirectResponse(url="/recipes", status_code=302)

# Batch routes
@app.get("/batches", response_class=HTMLResponse)
def batches_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
def create_batch(
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
        yield_amount=yield_amount,
        yield_unit=yield_unit,
        estimated_labor_minutes=estimated_labor_minutes,
        hourly_labor_rate=hourly_labor_rate,
        can_be_scaled=can_be_scaled,
        scale_double=scale_double,
        scale_half=scale_half,
        scale_quarter=scale_quarter,
        scale_eighth=scale_eighth,
        scale_sixteenth=scale_sixteenth
    )
    db.add(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=302)

@app.get("/batches/{batch_id}", response_class=HTMLResponse)
def batch_detail(batch_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category)
    ).filter(Batch.id == batch_id).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
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
def batch_edit_form(batch_id: int, request: Request, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
    batch = db.query(Batch).options(
        joinedload(Batch.recipe)
    ).filter(Batch.id == batch_id).first()
    
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
def batch_edit(
    batch_id: int,
    recipe_id: int = Form(...),
    yield_amount: float = Form(...),
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
    batch.yield_amount = yield_amount
    batch.estimated_labor_minutes = estimated_labor_minutes
    batch.hourly_labor_rate = hourly_labor_rate
    batch.can_be_scaled = can_be_scaled
    batch.scale_double = scale_double
    batch.scale_half = scale_half
    batch.scale_quarter = scale_quarter
    batch.scale_eighth = scale_eighth
    batch.scale_sixteenth = scale_sixteenth
    
    db.commit()
    
    return RedirectResponse(url=f"/batches/{batch_id}", status_code=302)

@app.get("/batches/{batch_id}/delete")
def batch_delete(batch_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    db.delete(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=302)

# Dish routes
@app.get("/dishes", response_class=HTMLResponse)
def dishes_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dishes = db.query(Dish).options(joinedload(Dish.category)).all()
    categories = db.query(Category).filter(Category.type == "dish").all()
    
    return templates.TemplateResponse("dishes.html", {
        "request": request,
        "current_user": current_user,
        "dishes": dishes,
        "categories": categories
    })

@app.post("/dishes/new")
def create_dish(
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
        category_id=category_id,
        sale_price=sale_price,
        description=description
    )
    db.add(dish)
    db.flush()  # Get the dish ID
    
    # Parse batch portions data
    batch_portions = json.loads(batch_portions_data)
    for portion_data in batch_portions:
        dish_batch_portion = DishBatchPortion(
            dish_id=dish.id,
            batch_id=portion_data['batch_id'],
            portion_size=portion_data['portion_size'],
            portion_unit=portion_data['portion_unit_name']
        )
        db.add(dish_batch_portion)
    
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=302)

@app.get("/dishes/{dish_id}", response_class=HTMLResponse)
def dish_detail(dish_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dish = db.query(Dish).options(joinedload(Dish.category)).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).options(
        joinedload(DishBatchPortion.batch).joinedload(Batch.recipe).joinedload(Recipe.category)
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
def dish_edit_form(dish_id: int, request: Request, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
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
def dish_edit(
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
    dish.category_id = category_id
    dish.sale_price = sale_price
    dish.description = description
    
    # Delete existing batch portions
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Add new batch portions
    batch_portions = json.loads(batch_portions_data)
    for portion_data in batch_portions:
        dish_batch_portion = DishBatchPortion(
            dish_id=dish.id,
            batch_id=portion_data['batch_id'],
            portion_size=portion_data['portion_size'],
            portion_unit=portion_data['portion_unit_name']
        )
        db.add(dish_batch_portion)
    
    db.commit()
    
    return RedirectResponse(url=f"/dishes/{dish_id}", status_code=302)

@app.get("/dishes/{dish_id}/delete")
def dish_delete(dish_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    db.delete(dish)
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=302)

# Inventory routes
@app.get("/inventory", response_class=HTMLResponse)
def inventory_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    current_day = db.query(InventoryDay).filter(InventoryDay.finalized == False).first()
    
    # Get recent finalized days (last 30 days)
    thirty_days_ago = date.today() - timedelta(days=30)
    finalized_days = db.query(InventoryDay).filter(
        InventoryDay.finalized == True,
        InventoryDay.date >= thirty_days_ago
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
def create_inventory_item(
    name: str = Form(...),
    par_unit_name_id: Optional[int] = Form(None),
    par_level: float = Form(...),
    batch_id: Optional[int] = Form(None),
    par_unit_equals_type: Optional[str] = Form(None),
    par_unit_equals_amount: Optional[float] = Form(None),
    par_unit_equals_unit: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_item = InventoryItem(
        name=name,
        par_unit_name_id=par_unit_name_id,
        par_level=par_level,
        batch_id=batch_id,
        par_unit_equals_type=par_unit_equals_type,
        par_unit_equals_amount=par_unit_equals_amount,
        par_unit_equals_unit=par_unit_equals_unit,
        category_id=category_id
    )
    db.add(inventory_item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@app.post("/inventory/new_day")
def create_inventory_day(
    date: str = Form(...),
    employees_working: List[int] = Form(...),
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Check if there's already an active day
    existing_day = db.query(InventoryDay).filter(InventoryDay.finalized == False).first()
    if existing_day:
        raise HTTPException(status_code=400, detail="There is already an active inventory day. Please finalize it first.")
    
    # Parse date
    inventory_date = datetime.strptime(date, "%Y-%m-%d").date()
    
    # Create inventory day
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
        inventory_day_item = InventoryDayItem(
            day_id=inventory_day.id,
            inventory_item_id=item.id,
            quantity=0.0  # Default to 0, will be updated by user
        )
        db.add(inventory_day_item)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

@app.get("/inventory/day/{day_id}", response_class=HTMLResponse)
def inventory_day_detail(day_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
        if task.finished_at and task.inventory_item:
            task_summary = calculate_task_summary(task, db)
            if task_summary:
                task_summaries[task.id] = task_summary
    
    return templates.TemplateResponse("inventory_day.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
        "task_summaries": task_summaries,
        "employees": employees
    })

def calculate_task_summary(task: Task, db: Session):
    """Calculate comprehensive task summary with inventory flow"""
    if not task.inventory_item or not task.finished_at:
        return None
    
    print(f"DEBUG: Calculating task summary for task {task.id}")
    
    inventory_item = task.inventory_item
    
    # Get current inventory day item
    day_item = db.query(InventoryDayItem).filter(
        InventoryDayItem.day_id == task.day_id,
        InventoryDayItem.inventory_item_id == inventory_item.id
    ).first()
    
    if not day_item:
        print(f"DEBUG: No day item found for task {task.id}")
        return None
    
    # Basic inventory info
    par_level = inventory_item.par_level
    par_unit_name = inventory_item.par_unit_name.name if inventory_item.par_unit_name else "units"
    current_quantity = day_item.quantity
    
    print(f"DEBUG: Par level: {par_level}, Current quantity: {current_quantity}")
    
    # Par unit equals calculation
    par_unit_equals = inventory_item.par_unit_equals_calculated
    par_unit_equals_type = inventory_item.par_unit_equals_type
    par_unit_equals_unit = inventory_item.par_unit_equals_unit
    
    print(f"DEBUG: Par unit equals: {par_unit_equals}, Type: {par_unit_equals_type}")
    
    # Calculate made amount based on batch and scale
    made_amount = None
    made_unit = None
    made_par_units = 0
    
    if task.batch:
        print(f"DEBUG: Task has batch: {task.batch.recipe.name}")
        
        if task.batch.variable_yield and task.made_amount and task.made_unit:
            # Variable yield - use actual made amount
            made_amount = task.made_amount
            made_unit = task.made_unit
            print(f"DEBUG: Variable yield - Made: {made_amount} {made_unit}")
        elif not task.batch.variable_yield and task.batch.yield_amount:
            # Fixed yield - use batch yield with scale factor
            scale_factor = task.scale_factor or 1.0
            made_amount = task.batch.yield_amount * scale_factor
            made_unit = task.batch.yield_unit
            print(f"DEBUG: Fixed yield - Made: {made_amount} {made_unit} (scale: {scale_factor})")
        
        # Convert made amount to par units
        if made_amount and par_unit_equals and par_unit_equals > 0:
            if par_unit_equals_type == 'auto':
                # Auto: batch yield divided by par level gives par unit equals
                made_par_units = made_amount / par_unit_equals
                print(f"DEBUG: Auto conversion - {made_amount} / {par_unit_equals} = {made_par_units} par units")
            elif par_unit_equals_type == 'custom':
                # Custom: convert using custom factor
                made_par_units = made_amount / par_unit_equals
                print(f"DEBUG: Custom conversion - {made_amount} / {par_unit_equals} = {made_par_units} par units")
            elif par_unit_equals_type == 'par_unit_itself':
                # Par unit itself - direct conversion
                made_par_units = made_amount
                print(f"DEBUG: Direct conversion - {made_amount} par units")
    
    # Calculate initial inventory (current - made)
    initial_inventory = current_quantity - made_par_units
    final_inventory = current_quantity
    
    print(f"DEBUG: Initial: {initial_inventory}, Final: {final_inventory}, Made: {made_par_units}")
    
    # Convert to other units if applicable
    initial_converted = None
    made_converted = None
    final_converted = None
    
    if par_unit_equals and par_unit_equals > 0 and par_unit_equals_unit:
        initial_converted = initial_inventory * par_unit_equals
        made_converted = made_par_units * par_unit_equals if made_par_units else None
        final_converted = final_inventory * par_unit_equals
        print(f"DEBUG: Converted - Initial: {initial_converted}, Made: {made_converted}, Final: {final_converted}")
    
    return {
        'par_level': par_level,
        'par_unit_name': par_unit_name,
        'par_unit_equals': par_unit_equals,
        'par_unit_equals_type': par_unit_equals_type,
        'par_unit_equals_unit': par_unit_equals_unit,
        'initial_inventory': initial_inventory,
        'made_amount': made_amount,
        'made_unit': made_unit,
        'made_par_units': made_par_units,
        'final_inventory': final_inventory,
        'initial_converted': initial_converted,
        'made_converted': made_converted,
        'final_converted': final_converted
    }

@app.post("/inventory/day/{day_id}/update")
def update_inventory_day(
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
        raise HTTPException(status_code=400, detail="Cannot update finalized inventory day")
    
    # Update global notes
    inventory_day.global_notes = global_notes
    
    # Get form data
    form_data = await request.form()
    
    # Update inventory quantities and overrides
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    
    for item in inventory_day_items:
        # Update quantity
        quantity_key = f"item_{item.inventory_item_id}"
        if quantity_key in form_data:
            item.quantity = float(form_data[quantity_key])
        
        # Update overrides
        override_create_key = f"override_create_{item.inventory_item_id}"
        item.override_create_task = override_create_key in form_data
        
        override_no_task_key = f"override_no_task_{item.inventory_item_id}"
        item.override_no_task = override_no_task_key in form_data
    
    # Generate tasks based on inventory levels
    generate_inventory_tasks(inventory_day, db)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

def generate_inventory_tasks(inventory_day: InventoryDay, db: Session):
    """Generate tasks for items that are below par or have overrides"""
    
    # Get all inventory day items
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item).joinedload(InventoryItem.batch)
    ).filter(InventoryDayItem.day_id == inventory_day.id).all()
    
    # Delete existing auto-generated tasks for this day
    db.query(Task).filter(Task.day_id == inventory_day.id, Task.auto_generated == True).delete()
    
    for day_item in inventory_day_items:
        inventory_item = day_item.inventory_item
        
        # Determine if task should be created
        should_create_task = False
        
        if day_item.override_create_task:
            # Force create task
            should_create_task = True
        elif day_item.override_no_task:
            # Force no task
            should_create_task = False
        else:
            # Auto-generate based on par level
            should_create_task = day_item.quantity <= inventory_item.par_level
        
        if should_create_task:
            # Create task
            task_description = f"Prep {inventory_item.name} (Below Par: {day_item.quantity}/{inventory_item.par_level})"
            
            task = Task(
                day_id=inventory_day.id,
                inventory_item_id=inventory_item.id,
                batch_id=inventory_item.batch_id,  # Link to batch if available
                description=task_description,
                auto_generated=True
            )
            db.add(task)

@app.post("/inventory/day/{day_id}/tasks/new")
def create_manual_task(
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
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/assign")
def assign_task(
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
def start_task(
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
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start_with_scale")
def start_task_with_scale(
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
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/pause")
def pause_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.started_at or task.finished_at:
        raise HTTPException(status_code=400, detail="Task is not in progress")
    
    task.paused_at = datetime.utcnow()
    task.is_paused = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/resume")
def resume_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.is_paused or not task.paused_at:
        raise HTTPException(status_code=400, detail="Task is not paused")
    
    # Add pause time to total
    pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
    task.total_pause_time += int(pause_duration)
    
    task.paused_at = None
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish")
def finish_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.started_at or task.finished_at:
        raise HTTPException(status_code=400, detail="Task is not in progress")
    
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    
    # Update inventory if this task produced something
    update_inventory_from_task(task, db)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish_with_amount")
def finish_task_with_amount(
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
        raise HTTPException(status_code=400, detail="Task is not in progress")
    
    task.made_amount = made_amount
    task.made_unit = made_unit
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    
    # Update inventory if this task produced something
    update_inventory_from_task(task, db)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

def update_inventory_from_task(task: Task, db: Session):
    """Update inventory quantities when a task is completed"""
    if not task.inventory_item or not task.finished_at:
        return
    
    # Get the inventory day item
    day_item = db.query(InventoryDayItem).filter(
        InventoryDayItem.day_id == task.day_id,
        InventoryDayItem.inventory_item_id == task.inventory_item.id
    ).first()
    
    if not day_item:
        return
    
    # Calculate how much was made in par units
    made_par_units = 0
    
    if task.batch:
        if task.batch.variable_yield and task.made_amount and task.made_unit:
            # Variable yield - use actual made amount
            made_amount = task.made_amount
            made_unit = task.made_unit
        elif not task.batch.variable_yield and task.batch.yield_amount:
            # Fixed yield - use batch yield with scale factor
            scale_factor = task.scale_factor or 1.0
            made_amount = task.batch.yield_amount * scale_factor
            made_unit = task.batch.yield_unit
        else:
            return  # Can't determine made amount
        
        # Convert to par units
        inventory_item = task.inventory_item
        par_unit_equals = inventory_item.par_unit_equals_calculated
        
        if par_unit_equals and par_unit_equals > 0:
            if inventory_item.par_unit_equals_type == 'auto':
                made_par_units = made_amount / par_unit_equals
            elif inventory_item.par_unit_equals_type == 'custom':
                made_par_units = made_amount / par_unit_equals
            elif inventory_item.par_unit_equals_type == 'par_unit_itself':
                made_par_units = made_amount
        
        # Update inventory quantity
        day_item.quantity += made_par_units

@app.post("/inventory/day/{day_id}/tasks/{task_id}/notes")
def update_task_notes(
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

@app.get("/inventory/day/{day_id}/tasks/{task_id}", response_class=HTMLResponse)
def task_detail(day_id: int, task_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    task = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.inventory_item),
        joinedload(Task.batch).joinedload(Batch.recipe)
    ).filter(Task.id == task_id, Task.day_id == day_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate task summary if task is completed
    task_summary = None
    if task.finished_at and task.inventory_item:
        task_summary = calculate_task_summary(task, db)
    
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "task": task,
        "task_summary": task_summary,
        "employees": employees
    })

@app.post("/inventory/day/{day_id}/finalize")
def finalize_inventory_day(
    day_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Inventory day is already finalized")
    
    inventory_day.finalized = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/reports/{day_id}", status_code=302)

@app.get("/inventory/reports/{day_id}", response_class=HTMLResponse)
def inventory_report(day_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
def inventory_item_edit_form(item_id: int, request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.query(InventoryItem).options(
        joinedload(InventoryItem.category),
        joinedload(InventoryItem.batch).joinedload(Batch.recipe)
    ).filter(InventoryItem.id == item_id).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).options(joinedload(Batch.recipe)).all()
    
    return templates.TemplateResponse("inventory_item_edit.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "categories": categories,
        "batches": batches
    })

@app.post("/inventory/items/{item_id}/edit")
def inventory_item_edit(
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
    item.batch_id = batch_id
    item.category_id = category_id
    
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@app.get("/inventory/items/{item_id}/delete")
def inventory_item_delete(item_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    db.delete(item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

# Utility routes (Admin only)
@app.get("/utilities", response_class=HTMLResponse)
def utilities_list(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    utilities = db.query(UtilityCost).all()
    
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "current_user": current_user,
        "utilities": utilities
    })

@app.post("/utilities/new")
def create_or_update_utility(
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
        utility = UtilityCost(name=name, monthly_cost=monthly_cost)
        db.add(utility)
    
    db.commit()
    
    return RedirectResponse(url="/utilities", status_code=302)

@app.post("/utilities/{utility_id}/delete")
def utility_delete(utility_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
    if not utility:
        raise HTTPException(status_code=404, detail="Utility not found")
    
    db.delete(utility)
    db.commit()
    
    return RedirectResponse(url="/utilities", status_code=302)

# API routes for AJAX requests
@app.get("/api/ingredients/all")
def api_ingredients_all(db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).options(joinedload(Ingredient.category)).all()
    
    result = []
    for ingredient in ingredients:
        available_units = ingredient.get_available_units()
        result.append({
            'id': ingredient.id,
            'name': ingredient.name,
            'category': ingredient.category.name if ingredient.category else None,
            'available_units': available_units
        })
    
    return result

@app.get("/api/ingredients/{ingredient_id}/cost_per_unit/{unit}")
def api_ingredient_cost_per_unit(ingredient_id: int, unit: str, db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    cost_per_unit = ingredient.get_cost_per_unit(unit)
    
    return {
        'ingredient_id': ingredient_id,
        'unit': unit,
        'cost_per_unit': cost_per_unit
    }

@app.get("/api/recipes/{recipe_id}/available_units")
def api_recipe_available_units(recipe_id: int, db: Session = Depends(get_db)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # Get all units used by ingredients in this recipe
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient)
    ).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
    available_units = set()
    for ri in recipe_ingredients:
        ingredient_units = ri.ingredient.get_available_units()
        available_units.update(ingredient_units)
    
    return sorted(list(available_units))

@app.get("/api/batches/all")
def api_batches_all(db: Session = Depends(get_db)):
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
            'id': batch.id,
            'recipe_name': batch.recipe.name,
            'category': batch.recipe.category.name if batch.recipe.category else None,
            'yield_amount': batch.yield_amount,
            'yield_unit': batch.yield_unit,
            'cost_per_unit': cost_per_unit,
            'variable_yield': batch.variable_yield
        })
    
    return result

@app.get("/api/batches/search")
def api_batches_search(q: str, db: Session = Depends(get_db)):
    batches = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category)
    ).filter(Recipe.name.ilike(f"%{q}%")).all()
    
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
            'id': batch.id,
            'recipe_name': batch.recipe.name,
            'category': batch.recipe.category.name if batch.recipe.category else None,
            'yield_amount': batch.yield_amount,
            'yield_unit': batch.yield_unit,
            'cost_per_unit': cost_per_unit,
            'variable_yield': batch.variable_yield
        })
    
    return result

@app.get("/api/batches/{batch_id}/portion_units")
def api_batch_portion_units(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # For now, return the yield unit - in future could expand to include compatible units
    units = []
    if batch.yield_unit:
        units.append({
            'id': 1,  # Placeholder ID
            'name': batch.yield_unit
        })
    
    return units

@app.get("/api/batches/{batch_id}/cost_per_unit/{unit_id}")
def api_batch_cost_per_unit(batch_id: int, unit_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Calculate cost per unit
    recipe_ingredients = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == batch.recipe_id
    ).all()
    
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    
    # Expected cost (with estimated labor)
    expected_total_cost = total_recipe_cost + batch.estimated_labor_cost
    expected_cost_per_unit = expected_total_cost / batch.yield_amount if batch.yield_amount else 0
    
    # Actual cost (with most recent actual labor)
    actual_total_cost = total_recipe_cost + batch.actual_labor_cost
    actual_cost_per_unit = actual_total_cost / batch.yield_amount if batch.yield_amount else 0
    
    return {
        'batch_id': batch_id,
        'unit_id': unit_id,
        'expected_cost_per_unit': expected_cost_per_unit,
        'actual_cost_per_unit': actual_cost_per_unit
    }

@app.get("/api/batches/{batch_id}/available_units")
def api_batch_available_units(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get available units from recipe ingredients
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient)
    ).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    
    available_units = set()
    for ri in recipe_ingredients:
        ingredient_units = ri.ingredient.get_available_units()
        available_units.update(ingredient_units)
    
    # Add batch yield unit if not already included
    if batch.yield_unit:
        available_units.add(batch.yield_unit)
    
    return sorted(list(available_units))

@app.get("/api/batches/{batch_id}/labor_stats")
def api_batch_labor_stats(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get completed tasks for this batch
    completed_tasks = db.query(Task).options(joinedload(Task.assigned_to)).filter(
        Task.batch_id == batch_id,
        Task.finished_at.isnot(None)
    ).all()
    
    if not completed_tasks:
        return {
            'task_count': 0,
            'most_recent_cost': batch.estimated_labor_cost,
            'most_recent_date': 'No tasks completed',
            'average_week': batch.estimated_labor_cost,
            'average_month': batch.estimated_labor_cost,
            'average_all_time': batch.estimated_labor_cost,
            'week_task_count': 0,
            'month_task_count': 0
        }
    
    # Most recent task
    most_recent = max(completed_tasks, key=lambda t: t.finished_at)
    
    # Time-based filtering
    week_ago = datetime.utcnow() - timedelta(days=7)
    month_ago = datetime.utcnow() - timedelta(days=30)
    
    week_tasks = [t for t in completed_tasks if t.finished_at >= week_ago]
    month_tasks = [t for t in completed_tasks if t.finished_at >= month_ago]
    
    # Calculate averages
    average_week = sum(t.labor_cost for t in week_tasks) / len(week_tasks) if week_tasks else batch.estimated_labor_cost
    average_month = sum(t.labor_cost for t in month_tasks) / len(month_tasks) if month_tasks else batch.estimated_labor_cost
    average_all_time = sum(t.labor_cost for t in completed_tasks) / len(completed_tasks)
    
    return {
        'task_count': len(completed_tasks),
        'most_recent_cost': most_recent.labor_cost,
        'most_recent_date': most_recent.finished_at.strftime('%Y-%m-%d'),
        'average_week': average_week,
        'average_month': average_month,
        'average_all_time': average_all_time,
        'week_task_count': len(week_tasks),
        'month_task_count': len(month_tasks)
    }

@app.get("/api/tasks/{task_id}/scale_options")
def api_task_scale_options(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).options(joinedload(Task.batch)).filter(Task.id == task_id).first()
    if not task or not task.batch:
        raise HTTPException(status_code=404, detail="Task or batch not found")
    
    return task.batch.get_available_scales()

@app.get("/api/tasks/{task_id}/finish_requirements")
def api_task_finish_requirements(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).options(
        joinedload(Task.batch),
        joinedload(Task.inventory_item)
    ).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result = {
        'available_units': [],
        'inventory_info': None
    }
    
    # Get available units from batch
    if task.batch:
        # Get units from recipe ingredients
        recipe_ingredients = db.query(RecipeIngredient).options(
            joinedload(RecipeIngredient.ingredient)
        ).filter(RecipeIngredient.recipe_id == task.batch.recipe_id).all()
        
        available_units = set()
        for ri in recipe_ingredients:
            ingredient_units = ri.ingredient.get_available_units()
            available_units.update(ingredient_units)
        
        # Add batch yield unit
        if task.batch.yield_unit:
            available_units.add(task.batch.yield_unit)
        
        result['available_units'] = sorted(list(available_units))
    
    # Get inventory info if linked
    if task.inventory_item:
        day_item = db.query(InventoryDayItem).filter(
            InventoryDayItem.day_id == task.day_id,
            InventoryDayItem.inventory_item_id == task.inventory_item.id
        ).first()
        
        if day_item:
            result['inventory_info'] = {
                'current': day_item.quantity,
                'par_level': task.inventory_item.par_level,
                'par_unit_name': task.inventory_item.par_unit_name.name if task.inventory_item.par_unit_name else 'units'
            }
    
    return result

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=302)
    elif exc.status_code == 403:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "status_code": 403,
            "detail": "Access denied. You don't have permission to access this resource."
        }, status_code=403)
    elif exc.status_code == 404:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "status_code": 404,
            "detail": "The requested resource was not found."
        }, status_code=404)
    else:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "status_code": exc.status_code,
            "detail": exc.detail
        }, status_code=exc.status_code)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)