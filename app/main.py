from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta
import json
from typing import List, Optional

from .database import engine, get_db
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, VendorUnit, UsageUnit, VendorUnitConversion, IngredientUsageUnit, Vendor
from .auth import hash_password, verify_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above
from .conversion_utils import get_batch_to_par_conversion, get_available_units_for_inventory_item, get_scale_options_for_batch, preview_conversion
from .conversion_utils import get_batch_to_par_conversion, get_available_units_for_inventory_item, get_scale_options_for_batch, preview_conversion

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Helper function to check if setup is needed
def needs_setup(db: Session):
    return db.query(User).filter(User.role == "admin").first() is None

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse(url="/setup", status_code=307)
    return RedirectResponse(url="/home", status_code=307)

@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    if not needs_setup(db):
        return RedirectResponse(url="/home", status_code=307)
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup", response_class=HTMLResponse)
async def setup_admin(request: Request, username: str = Form(...), full_name: str = Form(""), password: str = Form(...), db: Session = Depends(get_db)):
    if not needs_setup(db):
        return RedirectResponse(url="/home", status_code=307)
    
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
        is_user=True
    )
    db.add(admin_user)
    
    # Create default categories
    default_categories = [
        ("Proteins", "ingredient"),
        ("Vegetables", "ingredient"),
        ("Dairy", "ingredient"),
        ("Grains", "ingredient"),
        ("Spices", "ingredient"),
        ("Appetizers", "dish"),
        ("Entrees", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Prep Items", "batch"),
        ("Sauces", "batch"),
        ("Sides", "batch"),
        ("Cold Storage", "inventory"),
        ("Dry Storage", "inventory"),
        ("Freezer", "inventory")
    ]
    
    for name, cat_type in default_categories:
        existing_category = db.query(Category).filter(Category.name == name, Category.type == cat_type).first()
        if not existing_category:
            category = Category(name=name, type=cat_type)
            db.add(category)
    
    # Create default vendor units
    default_vendor_units = [
        ("lb", "Pound"),
        ("oz", "Ounce"),
        ("gal", "Gallon"),
        ("qt", "Quart"),
        ("pt", "Pint"),
        ("kg", "Kilogram"),
        ("g", "Gram"),
        ("L", "Liter"),
        ("mL", "Milliliter")
    ]
    
    for name, description in default_vendor_units:
        existing_unit = db.query(VendorUnit).filter(VendorUnit.name == name).first()
        if not existing_unit:
            vendor_unit = VendorUnit(name=name, description=description)
            db.add(vendor_unit)
    
    # Create default usage units
    default_usage_units = [
        "lb", "oz", "cup", "tbsp", "tsp", "gal", "qt", "pt", "fl oz", 
        "each", "can", "jar", "bag", "box", "bunch", "head", "clove", 
        "slice", "piece", "portion", "serving"
    ]
    
    for unit_name in default_usage_units:
        existing_unit = db.query(UsageUnit).filter(UsageUnit.name == unit_name).first()
        if not existing_unit:
            usage_unit = UsageUnit(name=unit_name)
            db.add(usage_unit)
    
    db.flush()  # Ensure units are created before conversions
    
    # Create some common vendor unit to usage unit conversions
    conversions = [
        ("lb", "lb", 1.0),
        ("lb", "oz", 16.0),
        ("oz", "oz", 1.0),
        ("oz", "lb", 0.0625),
        ("gal", "gal", 1.0),
        ("gal", "qt", 4.0),
        ("gal", "pt", 8.0),
        ("gal", "cup", 16.0),
        ("gal", "fl oz", 128.0),
        ("qt", "qt", 1.0),
        ("qt", "pt", 2.0),
        ("qt", "cup", 4.0),
        ("qt", "fl oz", 32.0),
        ("pt", "pt", 1.0),
        ("pt", "cup", 2.0),
        ("pt", "fl oz", 16.0)
    ]
    
    for vendor_unit_name, usage_unit_name, factor in conversions:
        vendor_unit = db.query(VendorUnit).filter(VendorUnit.name == vendor_unit_name).first()
        usage_unit = db.query(UsageUnit).filter(UsageUnit.name == usage_unit_name).first()
        
        if vendor_unit and usage_unit:
            existing_conversion = db.query(VendorUnitConversion).filter(
                VendorUnitConversion.vendor_unit_id == vendor_unit.id,
                VendorUnitConversion.usage_unit_id == usage_unit.id
            ).first()
            
            if not existing_conversion:
                conversion = VendorUnitConversion(
                    vendor_unit_id=vendor_unit.id,
                    usage_unit_id=usage_unit.id,
                    conversion_factor=factor
                )
                db.add(conversion)
    
    db.commit()
    
    # Create JWT token and set cookie
    token = create_jwt({"sub": username})
    response = RedirectResponse(url="/home", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    return response

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse(url="/setup", status_code=307)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid username or password"
        })
    
    token = create_jwt({"sub": username})
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

@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Employee Management (Admin only)
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
    new_user = User(
        username=username,
        full_name=full_name,
        hashed_password=hashed_password,
        hourly_wage=hourly_wage,
        work_schedule=work_schedule,
        role=role,
        is_admin=(role == "admin"),
        is_user=True
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/employees", status_code=302)

@app.get("/employees/{employee_id}", response_class=HTMLResponse)
async def employee_detail(request: Request, employee_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_detail.html", {
        "request": request,
        "current_user": current_user,
        "employee": employee
    })

@app.get("/employees/{employee_id}/edit", response_class=HTMLResponse)
async def employee_edit_form(request: Request, employee_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
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
    work_schedule: str = Form(""),
    role: str = Form("user"),
    is_active: bool = Form(False),
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
    return RedirectResponse(url=f"/employees/{employee_id}", status_code=302)

@app.get("/employees/{employee_id}/delete")
async def employee_delete(employee_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Don't allow deleting yourself
    if employee.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Deactivate instead of delete to preserve task history
    employee.is_active = False
    db.commit()
    return RedirectResponse(url="/employees", status_code=302)

# Categories
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
    elif type == "dish":
        return RedirectResponse(url="/dishes", status_code=302)
    elif type == "inventory":
        return RedirectResponse(url="/inventory", status_code=302)
    else:
        return RedirectResponse(url="/home", status_code=302)

# Vendors
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

# Vendor Units
@app.post("/vendor_units/new")
async def create_vendor_unit(
    name: str = Form(...),
    description: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    vendor_unit = VendorUnit(name=name, description=description)
    db.add(vendor_unit)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

# Usage Units
@app.post("/usage_units/new")
async def create_usage_unit(
    name: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    usage_unit = UsageUnit(name=name)
    db.add(usage_unit)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

# Ingredients
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
    current_user: User = Depends(require_manager_or_admin),
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
        items_per_case=items_per_case if purchase_type == 'case' else None
    )
    db.add(ingredient)
    db.flush()  # Get the ingredient ID
    
    # Process usage unit conversions
    form_data = await request.form()
    usage_units = db.query(UsageUnit).all()
    
    for usage_unit in usage_units:
        conversion_key = f"conversion_{usage_unit.id}"
        if conversion_key in form_data and form_data[conversion_key]:
            conversion_factor = float(form_data[conversion_key])
            ingredient_usage = IngredientUsageUnit(
                ingredient_id=ingredient.id,
                usage_unit_id=usage_unit.id,
                conversion_factor=conversion_factor
            )
            db.add(ingredient_usage)
    
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

@app.get("/ingredients/{ingredient_id}", response_class=HTMLResponse)
async def ingredient_detail(request: Request, ingredient_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    usage_units = db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).all()
    
    return templates.TemplateResponse("ingredient_detail.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient,
        "usage_units": usage_units
    })

@app.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
async def ingredient_edit_form(request: Request, ingredient_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
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
    request: Request,
    ingredient_id: int,
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
    ingredient.items_per_case = items_per_case if purchase_type == 'case' else None
    
    # Delete existing usage unit conversions
    db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).delete()
    
    # Process new usage unit conversions
    form_data = await request.form()
    usage_units = db.query(UsageUnit).all()
    
    for usage_unit in usage_units:
        conversion_key = f"conversion_{usage_unit.id}"
        if conversion_key in form_data and form_data[conversion_key]:
            conversion_factor = float(form_data[conversion_key])
            ingredient_usage = IngredientUsageUnit(
                ingredient_id=ingredient.id,
                usage_unit_id=usage_unit.id,
                conversion_factor=conversion_factor
            )
            db.add(ingredient_usage)
    
    db.commit()
    return RedirectResponse(url=f"/ingredients/{ingredient_id}", status_code=302)

@app.get("/ingredients/{ingredient_id}/delete")
async def ingredient_delete(ingredient_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    db.delete(ingredient)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

# Recipes
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
        instructions=instructions if instructions else None,
        category_id=category_id if category_id else None
    )
    db.add(recipe)
    db.flush()  # Get the recipe ID
    
    # Process ingredients
    try:
        ingredients = json.loads(ingredients_data)
        for ing_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ing_data['ingredient_id'],
                usage_unit_id=ing_data['usage_unit_id'],
                quantity=ing_data['quantity']
            )
            db.add(recipe_ingredient)
    except (json.JSONDecodeError, KeyError):
        pass  # Skip if invalid data
    
    db.commit()
    return RedirectResponse(url="/recipes", status_code=302)

@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(request: Request, recipe_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def recipe_edit_form(request: Request, recipe_id: int, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    categories = db.query(Category).filter(Category.type == "recipe").all()
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
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
    recipe.instructions = instructions if instructions else None
    recipe.category_id = category_id if category_id else None
    
    # Delete existing ingredients
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
    # Process new ingredients
    try:
        ingredients = json.loads(ingredients_data)
        for ing_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ing_data['ingredient_id'],
                usage_unit_id=ing_data['usage_unit_id'],
                quantity=ing_data['quantity']
            )
            db.add(recipe_ingredient)
    except (json.JSONDecodeError, KeyError):
        pass  # Skip if invalid data
    
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

# Batches
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
    is_variable: bool = Form(False),
    yield_amount: float = Form(...),
    is_variable: bool = Form(False),
    yield_unit_id: int = Form(...),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(16.75),
    can_be_scaled: bool = Form(False),
    scale_double: bool = Form(False),
    scale_half: bool = Form(False),
    scale_quarter: bool = Form(False),
    scale_eighth: bool = Form(False),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Validate required fields based on variable yield
    if not is_variable and (yield_amount is None or yield_unit_id is None):
        raise HTTPException(status_code=400, detail="Yield amount and unit required for non-variable batches")
    
    if is_variable:
        yield_amount = None
        yield_unit_id = None
    
    batch = Batch(
        recipe_id=recipe_id,
        is_variable=is_variable,
        is_variable=is_variable,
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
async def batch_detail(request: Request, batch_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
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
async def batch_edit_form(request: Request, batch_id: int, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
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
    yield_amount: Optional[float] = Form(None),
    yield_unit_id: Optional[int] = Form(None),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(16.75),
    can_be_scaled: bool = Form(False),
    scale_double: bool = Form(False),
    scale_half: bool = Form(False),
    scale_quarter: bool = Form(False),
    scale_eighth: bool = Form(False),
    scale_sixteenth: bool = Form(False),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Validate yield fields for non-variable batches
    if not is_variable and (not yield_amount or not yield_unit_id):
        raise HTTPException(status_code=400, detail="Yield amount and unit required for non-variable batches")
    
    # For variable batches, clear yield fields
    if is_variable:
        yield_amount = None
        yield_unit_id = None
    
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
async def batch_delete(batch_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    db.delete(batch)
    db.commit()
    return RedirectResponse(url="/batches", status_code=302)

# Dishes
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
        description=description if description else None
    )
    db.add(dish)
    db.flush()  # Get the dish ID
    
    # Process batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            dish_batch_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data['batch_id'],
                portion_size=portion_data['portion_size'],
                portion_unit_id=portion_data.get('portion_unit_id')
            )
            db.add(dish_batch_portion)
    except (json.JSONDecodeError, KeyError):
        pass  # Skip if invalid data
    
    db.commit()
    return RedirectResponse(url="/dishes", status_code=302)

@app.get("/dishes/{dish_id}", response_class=HTMLResponse)
async def dish_detail(request: Request, dish_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def dish_edit_form(request: Request, dish_id: int, current_user: User = Depends(require_manager_or_admin), db: Session = Depends(get_db)):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    categories = db.query(Category).filter(Category.type == "dish").all()
    dish_batch_portions = db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).all()
    
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
    dish.description = description if description else None
    
    # Delete existing batch portions
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Process new batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            dish_batch_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data['batch_id'],
                portion_size=portion_data['portion_size'],
                portion_unit_id=portion_data.get('portion_unit_id')
            )
            db.add(dish_batch_portion)
    except (json.JSONDecodeError, KeyError):
        pass  # Skip if invalid data
    
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

# Inventory
@app.get("/inventory", response_class=HTMLResponse)
async def inventory(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
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
        "employees": employees,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "today_date": today.isoformat()
    })

@app.post("/inventory/new_item")
async def create_inventory_item(
    name: str = Form(...),
    par_level: float = Form(...),
    batch_id: Optional[int] = Form(None),
    par_unit_equals_amount: float = Form(1.0),
    par_unit_equals_unit_id: Optional[int] = Form(None),
    manual_conversion_factor: Optional[float] = Form(None),
    conversion_notes: Optional[str] = Form(None),
    par_unit_equals_amount: float = Form(1.0),
    par_unit_equals_unit_id: Optional[int] = Form(None),
    manual_conversion_factor: Optional[float] = Form(None),
    conversion_notes: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_item = InventoryItem(
        name=name,
        par_level=par_level,
        par_unit_equals_amount=par_unit_equals_amount,
        par_unit_equals_unit_id=par_unit_equals_unit_id,
        manual_conversion_factor=manual_conversion_factor,
        conversion_notes=conversion_notes,
        par_unit_equals_amount=par_unit_equals_amount,
        par_unit_equals_unit_id=par_unit_equals_unit_id,
        manual_conversion_factor=manual_conversion_factor,
        conversion_notes=conversion_notes,
        batch_id=batch_id if batch_id else None,
        category_id=category_id if category_id else None
    )
    db.add(inventory_item)
    db.commit()
    return RedirectResponse(url="/inventory", status_code=302)

@app.get("/inventory/items/{item_id}/edit", response_class=HTMLResponse)
async def inventory_item_edit_form(request: Request, item_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    
    return templates.TemplateResponse("inventory_item_edit.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "usage_units": usage_units,
        "batches": batches,
        "categories": categories
    })

@app.get("/inventory/items/{item_id}/edit")
async def edit_inventory_item_form(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    item = db.query(InventoryItem).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    usage_units = db.query(UsageUnit).all()
    batches = db.query(Batch).join(Recipe).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    
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
    batch_id: Optional[int] = Form(None),
    par_unit_equals_amount: float = Form(1.0),
    par_unit_equals_unit_id: Optional[int] = Form(None),
    manual_conversion_factor: Optional[float] = Form(None),
    conversion_notes: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    item.name = name
    item.par_level = par_level
    item.par_unit_equals_amount = par_unit_equals_amount
    item.par_unit_equals_unit_id = par_unit_equals_unit_id
    item.manual_conversion_factor = manual_conversion_factor
    item.conversion_notes = conversion_notes
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

@app.post("/inventory/new_day")
async def create_inventory_day(
    request: Request,
    date: date = Form(...),
    employees_working: List[int] = Form([]),
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == date).first()
    if existing_day:
        return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=302)
    
    # Get employees_working from form data
    form_data = await request.form()
    employee_ids = form_data.getlist("employees_working")
    employees_working_str = ",".join(employee_ids)
    
    # Create inventory day
    inventory_day = InventoryDay(
        date=date,
        employees_working=employees_working_str,
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
            quantity=0  # Default to 0, will be updated by user
        )
        db.add(day_item)
    
    db.commit()
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

@app.get("/inventory/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_detail(request: Request, day_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
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
    request: Request,
    day_id: int,
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=404, detail="Inventory day not found or finalized")
    
    # Update global notes
    inventory_day.global_notes = global_notes if global_notes else None
    
    # Get form data
    form_data = await request.form()
    
    # Update inventory quantities
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    for item in inventory_day_items:
        quantity_key = f"item_{item.inventory_item.id}"
        override_create_key = f"override_create_{item.inventory_item.id}"
        override_no_task_key = f"override_no_task_{item.inventory_item.id}"
        
        if quantity_key in form_data:
            item.quantity = float(form_data[quantity_key])
        
        item.override_create_task = override_create_key in form_data
        item.override_no_task = override_no_task_key in form_data
    
    # Generate tasks for below-par items
    for item in inventory_day_items:
        is_below_par = item.quantity <= item.inventory_item.par_level
        should_create_task = (is_below_par and not item.override_no_task) or item.override_create_task
        
        if should_create_task:
            # Check if task already exists for this item
            existing_task = db.query(Task).filter(
                Task.day_id == day_id,
                Task.inventory_item_id == item.inventory_item.id,
                Task.auto_generated == True
            ).first()
            
            if not existing_task:
                task_description = f"Prep {item.inventory_item.name} (Below Par: {item.quantity}/{item.inventory_item.par_level})"
                task = Task(
                    day_id=day_id,
                    inventory_item_id=item.inventory_item.id,
                    batch_id=item.inventory_item.batch_id,  # Link to batch if available
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
    return RedirectResponse(url=f"/inventory/reports/{day_id}", status_code=302)

@app.get("/inventory/reports/{day_id}", response_class=HTMLResponse)
async def inventory_report(request: Request, day_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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

# Task Management
@app.post("/inventory/day/{day_id}/tasks/new")
async def create_task(
    request: Request,
    day_id: int,
    description: str = Form(...),
    inventory_item_id: Optional[int] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=404, detail="Inventory day not found or finalized")
    
    # Get assigned employee IDs from form
    form_data = await request.form()
    assigned_to_ids = form_data.getlist("assigned_to_ids")
    
    # Get batch_id if inventory item is linked to a batch
    batch_id = None
    if inventory_item_id:
        inventory_item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
        
        # Calculate par and inventory in actual units
        par_in_units = inventory_item.par_level * inventory_item.par_unit_equals_amount if inventory_item.par_unit_equals_amount else inventory_item.par_level
        inventory_in_units = item.quantity * inventory_item.par_unit_equals_amount if inventory_item.par_unit_equals_amount else item.quantity
        
        # Determine if task should be created
        if inventory_item and inventory_item.batch_id:
            batch_id = inventory_item.batch_id
    
    if assigned_to_ids:
        # Create a task for each assigned employee
        for assigned_to_id in assigned_to_ids:
            # Determine if manual made amount is required
            requires_manual = (
                inventory_item.batch.is_variable or 
                not inventory_item.par_unit_equals_unit_id or
                not inventory_item.batch.yield_unit_id
            )
            
            # Create task description with unit information
            unit_info = ""
            if inventory_item.par_unit_equals_unit:
                unit_info = f" (Par: {inventory_item.par_level} = {par_in_units:.1f} {inventory_item.par_unit_equals_unit.name}, Current: {item.quantity} = {inventory_in_units:.1f} {inventory_item.par_unit_equals_unit.name})"
            
            task = Task(
                day_id=day_id,
                assigned_to_id=int(assigned_to_id),
                description=f"Prep {inventory_item.name}{unit_info}",
                batch_id=batch_id,
                description=description,
                auto_generated=True,
                requires_manual_made=requires_manual
            )
            db.add(task)
    else:
        # Create unassigned task
        task = Task(
            day_id=day_id,
            inventory_item_id=inventory_item_id if inventory_item_id else None,
            batch_id=batch_id,
            description=description,
            auto_generated=False
        )
        db.add(task)
    
    db.commit()
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.get("/inventory/day/{day_id}/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(request: Request, day_id: int, task_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
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
    
    task.started_at = datetime.utcnow()
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
    
    if task.started_at and not task.is_paused:
        task.paused_at = datetime.utcnow()
        task.is_paused = True
        
        # Calculate pause time if resuming from a previous pause
        if task.paused_at and task.started_at:
            current_session_time = (task.paused_at - task.started_at).total_seconds()
            task.total_pause_time = task.total_pause_time or 0
    
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
    
    if task.is_paused and task.paused_at:
        # Calculate pause duration and add to total
        pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
        task.total_pause_time = (task.total_pause_time or 0) + pause_duration
        
        task.is_paused = False
        task.paused_at = None
    
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
    
    task.finished_at = datetime.utcnow()
    task.is_paused = False
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
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.notes = notes if notes else None
    db.commit()
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)

# Utilities (Admin only)
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
    # Check if utility with same name exists
    existing_utility = db.query(UtilityCost).filter(UtilityCost.name == name).first()
    if existing_utility:
        # Update existing
        existing_utility.monthly_cost = monthly_cost
        existing_utility.last_updated = datetime.utcnow()
    else:
        # Create new
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

# API Endpoints for AJAX calls
@app.get("/api/ingredients/all")
async def api_ingredients_all(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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

@app.get("/api/vendor_units/{vendor_unit_id}/conversions")
async def api_vendor_unit_conversions(vendor_unit_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversions = db.query(VendorUnitConversion).filter(VendorUnitConversion.vendor_unit_id == vendor_unit_id).all()
    result = {}
    for conversion in conversions:
        result[conversion.usage_unit_id] = conversion.conversion_factor
    return result

@app.get("/api/recipes/{recipe_id}/usage_units")
async def api_recipe_usage_units(recipe_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Get all usage units used in this recipe
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
    usage_unit_ids = set(ri.usage_unit_id for ri in recipe_ingredients)
    
    usage_units = db.query(UsageUnit).filter(UsageUnit.id.in_(usage_unit_ids)).all()
    
    return [{"id": unit.id, "name": unit.name} for unit in usage_units]

@app.get("/api/batches/search")
async def api_batches_search(q: str = "", current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Batch).join(Recipe)
    
    if q:
        query = query.filter(Recipe.name.ilike(f"%{q}%"))
    
    batches = query.all()
    result = []
    
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount > 0 else 0
        
        result.append({
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "category": batch.recipe.category.name if batch.recipe.category else None,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit.name if batch.yield_unit else "",
            "yield_unit_id": batch.yield_unit_id,
            "cost_per_unit": cost_per_unit
        })
    
    return result

@app.get("/api/batches/all")
async def api_batches_all(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await api_batches_search("", current_user, db)

@app.get("/api/batches/{batch_id}/portion_units")
async def api_batch_portion_units(batch_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get usage units from recipe ingredients
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    usage_unit_ids = set(ri.usage_unit_id for ri in recipe_ingredients)
    
    # Add the batch yield unit
    if batch.yield_unit_id:
        usage_unit_ids.add(batch.yield_unit_id)
    
    usage_units = db.query(UsageUnit).filter(UsageUnit.id.in_(usage_unit_ids)).all()
    
    return [{"id": unit.id, "name": unit.name} for unit in usage_units]

@app.get("/api/batches/{batch_id}/cost_per_unit/{unit_id}")
async def api_batch_cost_per_unit(batch_id: int, unit_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Calculate total batch cost
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    
    # Expected cost (with estimated labor)
    expected_total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
    expected_cost_per_yield_unit = expected_total_batch_cost / batch.yield_amount if batch.yield_amount > 0 else 0
    
    # Actual cost (with actual labor from most recent task)
    actual_total_batch_cost = total_recipe_cost + batch.actual_labor_cost
    actual_cost_per_yield_unit = actual_total_batch_cost / batch.yield_amount if batch.yield_amount > 0 else 0
    
    # For now, assume 1:1 conversion between yield unit and requested unit
    # In a full implementation, you'd need proper unit conversion logic
    return {
        "expected_cost_per_unit": expected_cost_per_yield_unit,
        "actual_cost_per_unit": actual_cost_per_yield_unit
    }

@app.get("/api/batches/{batch_id}/labor_stats")
async def api_batch_labor_stats(batch_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get all completed tasks for this batch
    completed_tasks = db.query(Task).filter(
        Task.batch_id == batch_id,
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
    
    # Most recent task
    most_recent = completed_tasks[0]
    
    # Filter by time periods
    week_ago = datetime.utcnow() - timedelta(days=7)
    month_ago = datetime.utcnow() - timedelta(days=30)
    
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

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 404,
        "detail": "Page not found"
    }, status_code=404)

@app.exception_handler(403)
async def forbidden_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 403,
        "detail": "Access forbidden"
    }, status_code=403)

@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: HTTPException):
    return RedirectResponse(url="/login", status_code=302)