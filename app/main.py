from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from datetime import datetime, date, timedelta
from typing import Optional, List
import json
import logging

from .database import engine, get_db
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, Vendor, VendorUnit, VendorUnitConversion, UsageUnit, IngredientUsageUnit
from .auth import hash_password, verify_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

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
        ("Entrees", "recipe"),
        ("Desserts", "recipe"),
        ("Sides", "recipe"),
        ("Prep Items", "batch"),
        ("Sauces", "batch"),
        ("Doughs", "batch"),
        ("Appetizers", "dish"),
        ("Entrees", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Proteins", "inventory"),
        ("Vegetables", "inventory"),
        ("Dairy", "inventory"),
        ("Dry Goods", "inventory"),
        ("Prepared Items", "inventory"),
    ]
    
    for name, cat_type in default_categories:
        existing = db.query(Category).filter(and_(Category.name == name, Category.type == cat_type)).first()
        if not existing:
            category = Category(name=name, type=cat_type)
            db.add(category)
    
    db.commit()

# Helper function to create default units
def create_default_units(db: Session):
    # Vendor units
    vendor_units = [
        ("lb", "Pound"),
        ("oz", "Ounce"),
        ("gal", "Gallon"),
        ("qt", "Quart"),
        ("each", "Each"),
        ("case", "Case"),
        ("bag", "Bag"),
        ("box", "Box"),
    ]
    
    for name, description in vendor_units:
        existing = db.query(VendorUnit).filter(VendorUnit.name == name).first()
        if not existing:
            unit = VendorUnit(name=name, description=description)
            db.add(unit)
    
    # Usage units
    usage_units = [
        "lb", "lbs", "oz", "ounces", "gal", "gallons", "qt", "quarts", 
        "cups", "tbsp", "tsp", "each", "piece", "can", "bottle", "bag",
        "ml", "liters", "kg", "grams"
    ]
    
    for name in usage_units:
        existing = db.query(UsageUnit).filter(UsageUnit.name == name).first()
        if not existing:
            unit = UsageUnit(name=name)
            db.add(unit)
    
    db.commit()
    
    # Create basic conversions
    conversions = [
        ("lb", "lbs", 1.0),
        ("lb", "oz", 16.0),
        ("lb", "ounces", 16.0),
        ("gal", "gallons", 1.0),
        ("gal", "qt", 4.0),
        ("gal", "quarts", 4.0),
        ("qt", "cups", 4.0),
        ("each", "piece", 1.0),
    ]
    
    for vendor_name, usage_name, factor in conversions:
        vendor_unit = db.query(VendorUnit).filter(VendorUnit.name == vendor_name).first()
        usage_unit = db.query(UsageUnit).filter(UsageUnit.name == usage_name).first()
        
        if vendor_unit and usage_unit:
            existing = db.query(VendorUnitConversion).filter(
                and_(
                    VendorUnitConversion.vendor_unit_id == vendor_unit.id,
                    VendorUnitConversion.usage_unit_id == usage_unit.id
                )
            ).first()
            
            if not existing:
                conversion = VendorUnitConversion(
                    vendor_unit_id=vendor_unit.id,
                    usage_unit_id=usage_unit.id,
                    conversion_factor=factor
                )
                db.add(conversion)
    
    db.commit()

# Helper function to get batch actual labor cost
def get_batch_actual_labor_cost(batch_id: int, db: Session, period: str = "recent"):
    """Get actual labor cost for a batch based on completed tasks"""
    base_query = db.query(Task).filter(
        and_(
            Task.batch_id == batch_id,
            Task.finished_at.isnot(None)
        )
    )
    
    if period == "recent":
        # Most recent completed task
        task = base_query.order_by(Task.finished_at.desc()).first()
        return task.labor_cost if task else 0
    elif period == "week":
        # Average from past week
        week_ago = datetime.utcnow() - timedelta(days=7)
        tasks = base_query.filter(Task.finished_at >= week_ago).all()
        return sum(t.labor_cost for t in tasks) / len(tasks) if tasks else 0
    elif period == "month":
        # Average from past month
        month_ago = datetime.utcnow() - timedelta(days=30)
        tasks = base_query.filter(Task.finished_at >= month_ago).all()
        return sum(t.labor_cost for t in tasks) / len(tasks) if tasks else 0
    else:
        # All time average
        tasks = base_query.all()
        return sum(t.labor_cost for t in tasks) / len(tasks) if tasks else 0

# Helper function to check unit compatibility
def are_units_compatible(unit1_name: str, unit2_name: str) -> bool:
    """Check if two units can be converted between each other"""
    weight_units = {"lb", "lbs", "oz", "ounces", "kg", "grams"}
    volume_units = {"gal", "gallons", "qt", "quarts", "cups", "tbsp", "tsp", "ml", "liters"}
    count_units = {"each", "piece", "can", "bottle", "bag"}
    
    unit1_lower = unit1_name.lower()
    unit2_lower = unit2_name.lower()
    
    # Same unit
    if unit1_lower == unit2_lower:
        return True
    
    # Check if both are in the same category
    if unit1_lower in weight_units and unit2_lower in weight_units:
        return True
    if unit1_lower in volume_units and unit2_lower in volume_units:
        return True
    if unit1_lower in count_units and unit2_lower in count_units:
        return True
    
    return False

# Helper function to get basic conversion factor
def get_basic_conversion_factor(from_unit: str, to_unit: str) -> float:
    """Get basic conversion factor between common units"""
    conversions = {
        # Weight conversions
        ("lb", "oz"): 16.0, ("lbs", "oz"): 16.0,
        ("lb", "ounces"): 16.0, ("lbs", "ounces"): 16.0,
        ("oz", "lb"): 1/16.0, ("ounces", "lb"): 1/16.0,
        ("oz", "lbs"): 1/16.0, ("ounces", "lbs"): 1/16.0,
        
        # Volume conversions
        ("gal", "qt"): 4.0, ("gallons", "qt"): 4.0,
        ("gal", "quarts"): 4.0, ("gallons", "quarts"): 4.0,
        ("qt", "gal"): 1/4.0, ("quarts", "gal"): 1/4.0,
        ("qt", "gallons"): 1/4.0, ("quarts", "gallons"): 1/4.0,
        ("qt", "cups"): 4.0, ("quarts", "cups"): 4.0,
        ("cups", "qt"): 1/4.0, ("cups", "quarts"): 1/4.0,
        
        # Count conversions
        ("each", "piece"): 1.0, ("piece", "each"): 1.0,
    }
    
    key = (from_unit.lower(), to_unit.lower())
    return conversions.get(key, 1.0)  # Default to 1:1 if no conversion found

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
async def setup_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    db: Session = Depends(get_db)
):
    if not needs_setup(db):
        return RedirectResponse(url="/home")
    
    # Create admin user
    hashed_password = hash_password(password)
    admin_user = User(
        username=username,
        hashed_password=hashed_password,
        full_name=full_name,
        role="admin",
        is_admin=True,
        is_user=True
    )
    db.add(admin_user)
    db.commit()
    
    # Create default categories and units
    create_default_categories(db)
    create_default_units(db)
    
    return RedirectResponse(url="/login", status_code=302)

# Authentication routes
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse(url="/setup")
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
    
    if not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Account is deactivated"
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

# Home route
@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Employee routes (Admin only)
@app.get("/employees", response_class=HTMLResponse)
async def employees(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employees = db.query(User).all()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "current_user": current_user,
        "employees": employees
    })

@app.post("/employees/new")
async def create_employee(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    hourly_wage: float = Form(...),
    role: str = Form(...),
    work_schedule: str = Form(""),
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
        hashed_password=hashed_password,
        full_name=full_name,
        hourly_wage=hourly_wage,
        role=role,
        work_schedule=work_schedule,
        is_admin=(role == "admin"),
        is_user=True
    )
    db.add(employee)
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)

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
async def employee_edit_form(
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
async def employee_edit(
    employee_id: int,
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(""),
    hourly_wage: float = Form(...),
    role: str = Form(...),
    work_schedule: str = Form(""),
    is_active: bool = Form(False),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check if username is taken by another user
    existing = db.query(User).filter(and_(User.username == username, User.id != employee_id)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    employee.full_name = full_name
    employee.username = username
    employee.hourly_wage = hourly_wage
    employee.role = role
    employee.work_schedule = work_schedule
    employee.is_active = is_active
    employee.is_admin = (role == "admin")
    
    if password:
        employee.hashed_password = hash_password(password)
    
    db.commit()
    return RedirectResponse(url=f"/employees/{employee_id}", status_code=302)

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
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    
    employee.is_active = False
    db.commit()
    return RedirectResponse(url="/employees", status_code=302)

# Category routes
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

# Vendor routes
@app.post("/vendors/new")
async def create_vendor(
    name: str = Form(...),
    contact_info: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    vendor = Vendor(name=name, contact_info=contact_info)
    db.add(vendor)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

# Vendor Unit routes
@app.post("/vendor_units/new")
async def create_vendor_unit(
    name: str = Form(...),
    description: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    unit = VendorUnit(name=name, description=description)
    db.add(unit)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

# Usage Unit routes
@app.post("/usage_units/new")
async def create_usage_unit(
    name: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    unit = UsageUnit(name=name)
    db.add(unit)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

# Ingredient routes
@app.get("/ingredients", response_class=HTMLResponse)
async def ingredients(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).all()
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    vendor_units = db.query(VendorUnit).all()
    usage_units = db.query(UsageUnit).all()
    
    return templates.TemplateResponse("ingredients.html", {
        "request": request,
        "current_user": current_user,
        "ingredients": ingredients,
        "categories": categories,
        "vendors": vendors,
        "vendor_units": vendor_units,
        "usage_units": usage_units
    })

@app.post("/ingredients/new")
async def create_ingredient(
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    vendor_id: Optional[int] = Form(None),
    vendor_unit_id: Optional[int] = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    purchase_weight_volume: float = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Create ingredient
    ingredient = Ingredient(
        name=name,
        category_id=category_id if category_id else None,
        vendor_id=vendor_id if vendor_id else None,
        vendor_unit_id=vendor_unit_id if vendor_unit_id else None,
        purchase_type=purchase_type,
        purchase_unit_name=purchase_unit_name,
        purchase_weight_volume=purchase_weight_volume,
        purchase_total_cost=purchase_total_cost,
        breakable_case=breakable_case,
        items_per_case=items_per_case if purchase_type == "case" else None
    )
    db.add(ingredient)
    db.flush()  # Get the ID
    
    # Process usage units
    form_data = await request.form()
    usage_units = db.query(UsageUnit).all()
    
    for unit in usage_units:
        conversion_key = f"conversion_{unit.id}"
        if conversion_key in form_data and form_data[conversion_key]:
            conversion_factor = float(form_data[conversion_key])
            ingredient_usage = IngredientUsageUnit(
                ingredient_id=ingredient.id,
                usage_unit_id=unit.id,
                conversion_factor=conversion_factor
            )
            db.add(ingredient_usage)
    
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

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
    
    usage_units = db.query(IngredientUsageUnit).filter(
        IngredientUsageUnit.ingredient_id == ingredient_id
    ).all()
    
    return templates.TemplateResponse("ingredient_detail.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient,
        "usage_units": usage_units
    })

@app.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
async def ingredient_edit_form(
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
    usage_units = db.query(UsageUnit).all()
    
    # Get existing conversions
    existing_conversions = {}
    for iu in ingredient.usage_units:
        existing_conversions[iu.usage_unit_id] = iu.conversion_factor
    
    return templates.TemplateResponse("ingredient_edit.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient,
        "categories": categories,
        "vendors": vendors,
        "vendor_units": vendor_units,
        "usage_units": usage_units,
        "existing_conversions": existing_conversions
    })

@app.post("/ingredients/{ingredient_id}/edit")
async def ingredient_edit(
    ingredient_id: int,
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    vendor_id: Optional[int] = Form(None),
    vendor_unit_id: Optional[int] = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    purchase_weight_volume: float = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    # Update ingredient
    ingredient.name = name
    ingredient.category_id = category_id if category_id else None
    ingredient.vendor_id = vendor_id if vendor_id else None
    ingredient.vendor_unit_id = vendor_unit_id if vendor_unit_id else None
    ingredient.purchase_type = purchase_type
    ingredient.purchase_unit_name = purchase_unit_name
    ingredient.purchase_weight_volume = purchase_weight_volume
    ingredient.purchase_total_cost = purchase_total_cost
    ingredient.breakable_case = breakable_case
    ingredient.items_per_case = items_per_case if purchase_type == "case" else None
    
    # Update usage units - remove existing ones first
    db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).delete()
    
    # Process new usage units
    form_data = await request.form()
    usage_units = db.query(UsageUnit).all()
    
    for unit in usage_units:
        conversion_key = f"conversion_{unit.id}"
        if conversion_key in form_data and form_data[conversion_key]:
            conversion_factor = float(form_data[conversion_key])
            ingredient_usage = IngredientUsageUnit(
                ingredient_id=ingredient.id,
                usage_unit_id=unit.id,
                conversion_factor=conversion_factor
            )
            db.add(ingredient_usage)
    
    db.commit()
    return RedirectResponse(url=f"/ingredients/{ingredient_id}", status_code=302)

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
    return RedirectResponse(url="/ingredients", status_code=302)

# Recipe routes
@app.get("/recipes", response_class=HTMLResponse)
async def recipes(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipes = db.query(Recipe).all()
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
    ingredients_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Create recipe
    recipe = Recipe(
        name=name,
        instructions=instructions,
        category_id=category_id if category_id else None
    )
    db.add(recipe)
    db.flush()  # Get the ID
    
    # Process ingredients
    try:
        ingredients = json.loads(ingredients_data)
        for ing_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ing_data["ingredient_id"],
                usage_unit_id=ing_data["usage_unit_id"],
                quantity=ing_data["quantity"]
            )
            db.add(recipe_ingredient)
    except json.JSONDecodeError:
        pass  # No ingredients data
    
    db.commit()
    return RedirectResponse(url="/recipes", status_code=302)

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
    
    recipe_ingredients = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == recipe_id
    ).all()
    
    total_cost = sum(ri.cost for ri in recipe_ingredients)
    
    return templates.TemplateResponse("recipe_detail.html", {
        "request": request,
        "current_user": current_user,
        "recipe": recipe,
        "recipe_ingredients": recipe_ingredients,
        "total_cost": total_cost
    })

@app.get("/recipes/{recipe_id}/edit", response_class=HTMLResponse)
async def recipe_edit_form(
    recipe_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    categories = db.query(Category).filter(Category.type == "recipe").all()
    recipe_ingredients = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == recipe_id
    ).all()
    
    return templates.TemplateResponse("recipe_edit.html", {
        "request": request,
        "current_user": current_user,
        "recipe": recipe,
        "categories": categories,
        "recipe_ingredients": recipe_ingredients
    })

@app.post("/recipes/{recipe_id}/edit")
async def recipe_edit(
    recipe_id: int,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: Optional[int] = Form(None),
    ingredients_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # Update recipe
    recipe.name = name
    recipe.instructions = instructions
    recipe.category_id = category_id if category_id else None
    
    # Remove existing ingredients
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
    # Add new ingredients
    try:
        ingredients = json.loads(ingredients_data)
        for ing_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ing_data["ingredient_id"],
                usage_unit_id=ing_data["usage_unit_id"],
                quantity=ing_data["quantity"]
            )
            db.add(recipe_ingredient)
    except json.JSONDecodeError:
        pass  # No ingredients data
    
    db.commit()
    return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=302)

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
    return RedirectResponse(url="/recipes", status_code=302)

# Batch routes
@app.get("/batches", response_class=HTMLResponse)
async def batches(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batches = db.query(Batch).all()
    recipes = db.query(Recipe).all()
    usage_units = db.query(UsageUnit).all()
    
    return templates.TemplateResponse("batches.html", {
        "request": request,
        "current_user": current_user,
        "batches": batches,
        "recipes": recipes,
        "usage_units": usage_units
    })

@app.post("/batches/new")
async def create_batch(
    recipe_id: int = Form(...),
    yield_amount: float = Form(...),
    yield_unit_id: int = Form(...),
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
        yield_amount=yield_amount,
        yield_unit_id=yield_unit_id,
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
async def batch_detail(
    batch_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipe_ingredients = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == batch.recipe_id
    ).all()
    
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
    cost_per_yield_unit = total_batch_cost / batch.yield_amount if batch.yield_amount > 0 else 0
    
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
async def batch_edit_form(
    batch_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipes = db.query(Recipe).all()
    usage_units = db.query(UsageUnit).all()
    
    return templates.TemplateResponse("batch_edit.html", {
        "request": request,
        "current_user": current_user,
        "batch": batch,
        "recipes": recipes,
        "usage_units": usage_units
    })

@app.post("/batches/{batch_id}/edit")
async def batch_edit(
    batch_id: int,
    recipe_id: int = Form(...),
    yield_amount: float = Form(...),
    yield_unit_id: int = Form(...),
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
    batch.yield_unit_id = yield_unit_id
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
    return RedirectResponse(url="/batches", status_code=302)

# Dish routes
@app.get("/dishes", response_class=HTMLResponse)
async def dishes(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dishes = db.query(Dish).all()
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
    batch_portions_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Create dish
    dish = Dish(
        name=name,
        category_id=category_id if category_id else None,
        sale_price=sale_price,
        description=description
    )
    db.add(dish)
    db.flush()  # Get the ID
    
    # Process batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data["batch_id"],
                portion_size=portion_data["portion_size"],
                portion_unit_id=portion_data.get("portion_unit_id")
            )
            db.add(portion)
    except json.JSONDecodeError:
        pass  # No batch portions data
    
    db.commit()
    return RedirectResponse(url="/dishes", status_code=302)

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
    
    dish_batch_portions = db.query(DishBatchPortion).filter(
        DishBatchPortion.dish_id == dish_id
    ).all()
    
    # Calculate expected and actual costs
    expected_total_cost = 0
    actual_total_cost = 0
    
    for portion in dish_batch_portions:
        # Expected cost (using estimated labor)
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == portion.batch.recipe_id
        ).all()
        recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        expected_labor_cost = portion.batch.estimated_labor_cost
        expected_batch_cost = recipe_cost + expected_labor_cost
        
        # Actual cost (using actual labor from tasks)
        actual_labor_cost = get_batch_actual_labor_cost(portion.batch_id, db)
        actual_batch_cost = recipe_cost + actual_labor_cost
        
        # Calculate portion costs
        if portion.portion_unit_id == portion.batch.yield_unit_id:
            # Same unit as batch yield
            portion.expected_cost = (expected_batch_cost / portion.batch.yield_amount) * portion.portion_size
            portion.actual_cost = (actual_batch_cost / portion.batch.yield_amount) * portion.portion_size
        else:
            # Different unit - need conversion
            conversion_factor = get_unit_conversion_factor(
                portion.batch.yield_unit_id, 
                portion.portion_unit_id, 
                portion.batch_id, 
                db
            )
            portion.expected_cost = (expected_batch_cost / portion.batch.yield_amount) * portion.portion_size * conversion_factor
            portion.actual_cost = (actual_batch_cost / portion.batch.yield_amount) * portion.portion_size * conversion_factor
        
        expected_total_cost += portion.expected_cost
        actual_total_cost += portion.actual_cost
    
    # Calculate profit margins
    expected_profit = dish.sale_price - expected_total_cost
    actual_profit = dish.sale_price - actual_total_cost
    expected_profit_margin = (expected_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    actual_profit_margin = (actual_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    return templates.TemplateResponse("dish_detail.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "dish_batch_portions": dish_batch_portions,
        "expected_total_cost": expected_total_cost,
        "actual_total_cost": actual_total_cost,
        "expected_profit": expected_profit,
        "actual_profit": actual_profit,
        "expected_profit_margin": expected_profit_margin,
        "actual_profit_margin": actual_profit_margin
    })

@app.get("/dishes/{dish_id}/edit", response_class=HTMLResponse)
async def dish_edit_form(
    dish_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    categories = db.query(Category).filter(Category.type == "dish").all()
    dish_batch_portions = db.query(DishBatchPortion).filter(
        DishBatchPortion.dish_id == dish_id
    ).all()
    
    return templates.TemplateResponse("dish_edit.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "categories": categories,
        "dish_batch_portions": dish_batch_portions
    })

@app.post("/dishes/{dish_id}/edit")
async def dish_edit(
    dish_id: int,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    # Update dish
    dish.name = name
    dish.category_id = category_id if category_id else None
    dish.sale_price = sale_price
    dish.description = description
    
    # Remove existing batch portions
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Add new batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data["batch_id"],
                portion_size=portion_data["portion_size"],
                portion_unit_id=portion_data.get("portion_unit_id")
            )
            db.add(portion)
    except json.JSONDecodeError:
        pass  # No batch portions data
    
    db.commit()
    return RedirectResponse(url=f"/dishes/{dish_id}", status_code=302)

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
    return RedirectResponse(url="/dishes", status_code=302)

# Inventory routes
@app.get("/inventory", response_class=HTMLResponse)
async def inventory(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get current day if exists
    today = date.today()
    current_day = db.query(InventoryDay).filter(InventoryDay.date == today).first()
    
    # Get recent finalized days
    thirty_days_ago = today - timedelta(days=30)
    finalized_days = db.query(InventoryDay).filter(
        and_(
            InventoryDay.date >= thirty_days_ago,
            InventoryDay.finalized == True
        )
    ).order_by(InventoryDay.date.desc()).limit(10).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "current_user": current_user,
        "inventory_items": inventory_items,
        "categories": categories,
        "batches": batches,
        "employees": employees,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "today_date": today.isoformat()
    })

@app.post("/inventory/new_item")
async def create_inventory_item(
    name: str = Form(...),
    par_level: float = Form(...),
    category_id: Optional[int] = Form(None),
    batch_id: Optional[int] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    item = InventoryItem(
        name=name,
        par_level=par_level,
        category_id=category_id if category_id else None,
        batch_id=batch_id if batch_id else None
    )
    db.add(item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@app.post("/inventory/new_day")
async def create_inventory_day(
    request: Request,
    date: str = Form(...),
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Parse employees working
    form_data = await request.form()
    employees_working = []
    for key, value in form_data.items():
        if key == "employees_working":
            if isinstance(value, list):
                employees_working.extend(value)
            else:
                employees_working.append(value)
    
    employees_working_str = ",".join(employees_working)
    
    # Create inventory day
    inventory_day = InventoryDay(
        date=datetime.strptime(date, "%Y-%m-%d").date(),
        employees_working=employees_working_str,
        global_notes=global_notes
    )
    db.add(inventory_day)
    db.flush()
    
    # Create inventory day items for all inventory items
    inventory_items = db.query(InventoryItem).all()
    for item in inventory_items:
        day_item = InventoryDayItem(
            day_id=inventory_day.id,
            inventory_item_id=item.id,
            quantity=0
        )
        db.add(day_item)
    
    db.commit()
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

@app.get("/inventory/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_detail(
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
    employees = db.query(User).filter(User.is_active == True).all()
    
    return templates.TemplateResponse("inventory_day.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
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
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot update finalized day")
    
    # Update global notes
    inventory_day.global_notes = global_notes
    
    # Process form data
    form_data = await request.form()
    
    # Update inventory quantities
    for key, value in form_data.items():
        if key.startswith("item_"):
            item_id = int(key.split("_")[1])
            quantity = float(value) if value else 0
            
            day_item = db.query(InventoryDayItem).filter(
                and_(
                    InventoryDayItem.day_id == day_id,
                    InventoryDayItem.inventory_item_id == item_id
                )
            ).first()
            
            if day_item:
                day_item.quantity = quantity
                
                # Check for override flags
                override_create_key = f"override_create_{item_id}"
                override_no_task_key = f"override_no_task_{item_id}"
                
                day_item.override_create_task = override_create_key in form_data
                day_item.override_no_task = override_no_task_key in form_data
    
    # Generate tasks for below-par items
    inventory_day_items = db.query(InventoryDayItem).filter(
        InventoryDayItem.day_id == day_id
    ).all()
    
    for day_item in inventory_day_items:
        is_below_par = day_item.quantity <= day_item.inventory_item.par_level
        should_create_task = (is_below_par and not day_item.override_no_task) or day_item.override_create_task
        
        if should_create_task:
            # Check if task already exists
            existing_task = db.query(Task).filter(
                and_(
                    Task.day_id == day_id,
                    Task.inventory_item_id == day_item.inventory_item_id,
                    Task.auto_generated == True
                )
            ).first()
            
            if not existing_task:
                task_description = f"Prep {day_item.inventory_item.name}"
                if day_item.inventory_item.batch:
                    task_description = f"Make {day_item.inventory_item.batch.recipe.name}"
                
                task = Task(
                    day_id=day_id,
                    inventory_item_id=day_item.inventory_item_id,
                    batch_id=day_item.inventory_item.batch_id,
                    description=task_description,
                    auto_generated=True
                )
                db.add(task)
    
    db.commit()
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/finalize")
async def finalize_inventory_day(
    day_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day.finalized = True
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

# Task routes
@app.post("/inventory/day/{day_id}/tasks/new")
async def create_task(
    day_id: int,
    request: Request,
    description: str = Form(...),
    inventory_item_id: Optional[int] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Parse assigned employees
    form_data = await request.form()
    assigned_to_ids = []
    for key, value in form_data.items():
        if key == "assigned_to_ids":
            if isinstance(value, list):
                assigned_to_ids.extend(value)
            else:
                assigned_to_ids.append(value)
    
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
                assigned_to_id=int(assigned_to_id),
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

@app.get("/inventory/day/{day_id}/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(
    day_id: int,
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    employees = db.query(User).filter(User.is_active == True).all()
    
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "current_user": current_user,
        "task": task,
        "inventory_day": inventory_day,
        "employees": employees
    })

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start")
async def start_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.started_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/pause")
async def pause_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.started_at and not task.is_paused:
        task.paused_at = datetime.utcnow()
        task.is_paused = True
        
        # Add to total pause time
        if task.paused_at and task.started_at:
            pause_duration = (task.paused_at - task.started_at).total_seconds()
            task.total_pause_time += int(pause_duration)
    
    db.commit()
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/resume")
async def resume_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.is_paused:
        task.started_at = datetime.utcnow()  # Reset start time
        task.is_paused = False
        task.paused_at = None
    
    db.commit()
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish")
async def finish_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/assign")
async def assign_task(
    day_id: int,
    task_id: int,
    assigned_to_id: int = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.assigned_to_id = assigned_to_id
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/notes")
async def update_task_notes(
    day_id: int,
    task_id: int,
    notes: str = Form(""),
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.notes = notes
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)

@app.get("/inventory/items/{item_id}/edit", response_class=HTMLResponse)
async def inventory_item_edit_form(
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
async def inventory_item_edit(
    item_id: int,
    name: str = Form(...),
    par_level: float = Form(...),
    category_id: Optional[int] = Form(None),
    batch_id: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    item.name = name
    item.par_level = par_level
    item.category_id = category_id if category_id else None
    item.batch_id = batch_id if batch_id else None
    
    db.commit()
    return RedirectResponse(url="/inventory", status_code=302)

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
    return RedirectResponse(url="/inventory", status_code=302)

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
    
    inventory_day_items = db.query(InventoryDayItem).filter(
        InventoryDayItem.day_id == day_id
    ).all()
    
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.finished_at])
    below_par_items = len([item for item in inventory_day_items 
                          if item.quantity <= item.inventory_item.par_level])
    
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

# Utility routes (Admin only)
@app.get("/utilities", response_class=HTMLResponse)
async def utilities(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
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
        existing.last_updated = datetime.utcnow()
    else:
        utility = UtilityCost(name=name, monthly_cost=monthly_cost)
        db.add(utility)
    
    db.commit()
    return RedirectResponse(url="/utilities", status_code=302)

@app.post("/utilities/{utility_id}/delete")
async def delete_utility(
    utility_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
    if not utility:
        raise HTTPException(status_code=404, detail="Utility not found")
    
    db.delete(utility)
    db.commit()
    return RedirectResponse(url="/utilities", status_code=302)

# API routes for AJAX calls
@app.get("/api/ingredients/all")
async def api_ingredients_all(db: Session = Depends(get_db)):
    """Get all ingredients with their usage units for recipe creation"""
    ingredients = db.query(Ingredient).all()
    result = []
    
    for ingredient in ingredients:
        usage_units = []
        for iu in ingredient.usage_units:
            usage_units.append({
                "usage_unit_id": iu.usage_unit_id,
                "usage_unit_name": iu.usage_unit.name,
                "price_per_usage_unit": iu.price_per_usage_unit
            })
        
        result.append({
            "id": ingredient.id,
            "name": ingredient.name,
            "category": ingredient.category.name if ingredient.category else None,
            "usage_units": usage_units
        })
    
    return result

@app.get("/api/recipes/{recipe_id}/usage_units")
async def api_recipes_usage_units(recipe_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get all usage units from ingredients used in a recipe"""
    try:
        logger.debug(f"Loading usage units for recipe {recipe_id}")
        
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).options(
            joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
        ).all()
        
        logger.debug(f"Found {len(recipe_ingredients)} recipe ingredients")
        
        usage_units = []
        seen_unit_ids = set()
        
        for recipe_ingredient in recipe_ingredients:
            logger.debug(f"Processing ingredient: {recipe_ingredient.ingredient.name}")
            logger.debug(f"Ingredient has {len(recipe_ingredient.ingredient.usage_units)} usage units")
            
            for ingredient_usage in recipe_ingredient.ingredient.usage_units:
                logger.debug(f"  - Usage unit: {ingredient_usage.usage_unit.name}")
                
                if ingredient_usage.usage_unit.id not in seen_unit_ids:
                    logger.debug(f"    Adding to available units")
                    usage_units.append({
                        "id": ingredient_usage.usage_unit.id,
                        "name": ingredient_usage.usage_unit.name
                    })
                    seen_unit_ids.add(ingredient_usage.usage_unit.id)
                else:
                    logger.debug(f"    Already in available units")
        
        logger.debug(f"Final usage units: {[u['name'] for u in usage_units]}")
        return JSONResponse(usage_units)
        
    except Exception as e:
        logger.error(f"Error loading recipe usage units: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/batches/search")
async def api_batches_search(q: str = "", db: Session = Depends(get_db)):
    """Search batches for dish creation"""
    query = db.query(Batch).join(Recipe)
    
    if q:
        query = query.filter(Recipe.name.ilike(f"%{q}%"))
    
    batches = query.limit(10).all()
    result = []
    
    for batch in batches:
        # Calculate cost per unit
        recipe_cost = sum(ri.cost for ri in batch.recipe.ingredients)
        total_cost = recipe_cost + batch.estimated_labor_cost
        cost_per_unit = total_cost / batch.yield_amount if batch.yield_amount > 0 else 0
        
        result.append({
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit.name if batch.yield_unit else "",
            "yield_unit_id": batch.yield_unit_id,
            "cost_per_unit": cost_per_unit,
            "category": batch.recipe.category.name if batch.recipe.category else None
        })
    
    return result

@app.get("/api/batches/{batch_id}/portion_units")
async def api_batch_portion_units(batch_id: int, db: Session = Depends(get_db)):
    """Get available portion units for a batch"""
    logger.debug(f"Getting portion units for batch {batch_id}")
    
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        logger.error(f"Batch {batch_id} not found")
        raise HTTPException(status_code=404, detail="Batch not found")
    
    logger.debug(f"Found batch: {batch.recipe.name}")
    
    available_units = []
    seen_unit_ids = set()
    
    # Add batch yield unit
    if batch.yield_unit_id and batch.yield_unit_id not in seen_unit_ids:
        available_units.append({
            "id": batch.yield_unit_id,
            "name": batch.yield_unit.name,
            "type": "yield"
        })
        seen_unit_ids.add(batch.yield_unit_id)
        logger.debug(f"Added yield unit: {batch.yield_unit.name}")
    
    # Get all usage units from recipe ingredients
    recipe_ingredients = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == batch.recipe_id
    ).all()
    
    logger.debug(f"Processing {len(recipe_ingredients)} recipe ingredients")
    
    for ri in recipe_ingredients:
        logger.debug(f"Processing ingredient: {ri.ingredient.name}")
        
        # Get all usage units for this ingredient
        ingredient_usage_units = db.query(IngredientUsageUnit).filter(
            IngredientUsageUnit.ingredient_id == ri.ingredient_id
        ).all()
        
        logger.debug(f"Found {len(ingredient_usage_units)} usage units for {ri.ingredient.name}")
        
        for iu in ingredient_usage_units:
            if iu.usage_unit_id not in seen_unit_ids:
                # Check if this unit is compatible with batch yield unit
                if batch.yield_unit and are_units_compatible(batch.yield_unit.name, iu.usage_unit.name):
                    available_units.append({
                        "id": iu.usage_unit_id,
                        "name": iu.usage_unit.name,
                        "type": "ingredient"
                    })
                    seen_unit_ids.add(iu.usage_unit_id)
                    logger.debug(f"Added convertible unit: {iu.usage_unit.name}")
                else:
                    logger.debug(f"Skipped incompatible unit: {iu.usage_unit.name} (not compatible with {batch.yield_unit.name})")
    
    logger.debug(f"Returning {len(available_units)} available units: {[u['name'] for u in available_units]}")
    return available_units

@app.get("/api/batches/{batch_id}/cost_per_unit/{unit_id}")
async def api_batch_cost_per_unit(batch_id: int, unit_id: int, db: Session = Depends(get_db)):
    """Calculate cost per unit for a specific unit"""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    unit = db.query(UsageUnit).filter(UsageUnit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    # Calculate base costs
    recipe_cost = sum(ri.cost for ri in batch.recipe.ingredients)
    expected_total_cost = recipe_cost + batch.estimated_labor_cost
    actual_labor_cost = get_batch_actual_labor_cost(batch_id, db)
    actual_total_cost = recipe_cost + actual_labor_cost
    
    # Calculate cost per unit
    if unit_id == batch.yield_unit_id:
        # Same as yield unit
        expected_cost_per_unit = expected_total_cost / batch.yield_amount
        actual_cost_per_unit = actual_total_cost / batch.yield_amount
    else:
        # Different unit - need conversion
        conversion_factor = get_unit_conversion_factor(batch.yield_unit_id, unit_id, batch_id, db)
        expected_cost_per_unit = (expected_total_cost / batch.yield_amount) * conversion_factor
        actual_cost_per_unit = (actual_total_cost / batch.yield_amount) * conversion_factor
    
    return {
        "expected_cost_per_unit": expected_cost_per_unit,
        "actual_cost_per_unit": actual_cost_per_unit
    }

def get_unit_conversion_factor(from_unit_id: int, to_unit_id: int, batch_id: int, db: Session) -> float:
    """Get conversion factor between two units for a specific batch"""
    if from_unit_id == to_unit_id:
        return 1.0
    
    from_unit = db.query(UsageUnit).filter(UsageUnit.id == from_unit_id).first()
    to_unit = db.query(UsageUnit).filter(UsageUnit.id == to_unit_id).first()
    
    if not from_unit or not to_unit:
        return 1.0
    
    # Try to find conversion through recipe ingredients
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if batch:
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == batch.recipe_id
        ).all()
        
        for ri in recipe_ingredients:
            # Check if this ingredient uses both units
            from_usage = db.query(IngredientUsageUnit).filter(
                and_(
                    IngredientUsageUnit.ingredient_id == ri.ingredient_id,
                    IngredientUsageUnit.usage_unit_id == from_unit_id
                )
            ).first()
            
            to_usage = db.query(IngredientUsageUnit).filter(
                and_(
                    IngredientUsageUnit.ingredient_id == ri.ingredient_id,
                    IngredientUsageUnit.usage_unit_id == to_unit_id
                )
            ).first()
            
            if from_usage and to_usage:
                # Calculate conversion through ingredient
                return from_usage.conversion_factor / to_usage.conversion_factor
    
    # Fallback to basic conversion
    return get_basic_conversion_factor(from_unit.name, to_unit.name)

@app.get("/api/batches/{batch_id}/labor_stats")
async def api_batch_labor_stats(batch_id: int, db: Session = Depends(get_db)):
    """Get labor statistics for a batch"""
    tasks = db.query(Task).filter(
        and_(
            Task.batch_id == batch_id,
            Task.finished_at.isnot(None)
        )
    ).order_by(Task.finished_at.desc()).all()
    
    if not tasks:
        return {
            "task_count": 0,
            "most_recent_cost": 0,
            "most_recent_date": None,
            "average_week": 0,
            "average_month": 0,
            "average_all_time": 0,
            "week_task_count": 0,
            "month_task_count": 0
        }
    
    # Most recent
    most_recent = tasks[0]
    
    # Time-based filtering
    week_ago = datetime.utcnow() - timedelta(days=7)
    month_ago = datetime.utcnow() - timedelta(days=30)
    
    week_tasks = [t for t in tasks if t.finished_at >= week_ago]
    month_tasks = [t for t in tasks if t.finished_at >= month_ago]
    
    return {
        "task_count": len(tasks),
        "most_recent_cost": most_recent.labor_cost,
        "most_recent_date": most_recent.finished_at.strftime('%Y-%m-%d'),
        "average_week": sum(t.labor_cost for t in week_tasks) / len(week_tasks) if week_tasks else 0,
        "average_month": sum(t.labor_cost for t in month_tasks) / len(month_tasks) if month_tasks else 0,
        "average_all_time": sum(t.labor_cost for t in tasks) / len(tasks),
        "week_task_count": len(week_tasks),
        "month_task_count": len(month_tasks)
    }

@app.get("/api/vendor_units/{vendor_unit_id}/conversions")
async def api_vendor_unit_conversions(vendor_unit_id: int, db: Session = Depends(get_db)):
    """Get conversion factors for a vendor unit"""
    conversions = db.query(VendorUnitConversion).filter(
        VendorUnitConversion.vendor_unit_id == vendor_unit_id
    ).all()
    
    result = {}
    for conversion in conversions:
        result[conversion.usage_unit_id] = conversion.conversion_factor
    
    return result

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)