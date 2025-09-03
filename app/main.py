from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, timedelta, date
from typing import Optional, List
import json
import os

from .database import engine, get_db
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, VendorUnit, UsageUnit, VendorUnitConversion, IngredientUsageUnit, Vendor
from .auth import hash_password, verify_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above
from .conversion_utils import get_batch_to_par_conversion, get_available_units_for_inventory_item, get_scale_options_for_batch, preview_conversion

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
        ("Appetizers", "recipe"),
        ("Entrees", "recipe"),
        ("Desserts", "recipe"),
        ("Beverages", "recipe"),
        ("Appetizers", "dish"),
        ("Entrees", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Proteins", "inventory"),
        ("Produce", "inventory"),
        ("Dairy", "inventory"),
        ("Dry Goods", "inventory"),
    ]
    
    for name, cat_type in default_categories:
        existing = db.query(Category).filter(
            Category.name == name, 
            Category.type == cat_type
        ).first()
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
        ("cup", "Cup"),
        ("kg", "Kilogram"),
        ("g", "Gram"),
        ("l", "Liter"),
        ("ml", "Milliliter"),
    ]
    
    for name, description in vendor_units:
        existing = db.query(VendorUnit).filter(VendorUnit.name == name).first()
        if not existing:
            unit = VendorUnit(name=name, description=description)
            db.add(unit)
    
    # Usage units
    usage_units = [
        ("lb", "Pound"),
        ("oz", "Ounce"),
        ("gal", "Gallon"),
        ("qt", "Quart"),
        ("cup", "Cup"),
        ("tbsp", "Tablespoon"),
        ("tsp", "Teaspoon"),
        ("each", "Each"),
        ("dozen", "Dozen"),
        ("tub", "Tub"),
        ("pan", "Pan"),
        ("sheet", "Sheet"),
        ("bag", "Bag"),
        ("case", "Case"),
    ]
    
    for name, description in usage_units:
        existing = db.query(UsageUnit).filter(UsageUnit.name == name).first()
        if not existing:
            unit = UsageUnit(name=name, description=description)
            db.add(unit)
    
    db.commit()
    
    # Create standard conversions
    conversions = [
        ("lb", "oz", 16.0),
        ("gal", "qt", 4.0),
        ("gal", "cup", 16.0),
        ("qt", "cup", 4.0),
        ("cup", "tbsp", 16.0),
        ("tbsp", "tsp", 3.0),
        ("dozen", "each", 12.0),
    ]
    
    for vendor_name, usage_name, factor in conversions:
        vendor_unit = db.query(VendorUnit).filter(VendorUnit.name == vendor_name).first()
        usage_unit = db.query(UsageUnit).filter(UsageUnit.name == usage_name).first()
        
        if vendor_unit and usage_unit:
            existing = db.query(VendorUnitConversion).filter(
                VendorUnitConversion.vendor_unit_id == vendor_unit.id,
                VendorUnitConversion.usage_unit_id == usage_unit.id
            ).first()
            if not existing:
                conversion = VendorUnitConversion(
                    vendor_unit_id=vendor_unit.id,
                    usage_unit_id=usage_unit.id,
                    conversion_factor=factor
                )
                db.add(conversion)
    
    db.commit()

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse(url="/setup", status_code=302)
    
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    
    return RedirectResponse(url="/home", status_code=302)

@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    if not needs_setup(db):
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_submit(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not needs_setup(db):
        return RedirectResponse(url="/", status_code=302)
    
    # Create admin user
    hashed_password = hash_password(password)
    user = User(
        username=username,
        full_name=full_name if full_name else username,
        hashed_password=hashed_password,
        role="admin",
        is_active=True
    )
    db.add(user)
    db.commit()
    
    # Create default categories and units
    create_default_categories(db)
    create_default_units(db)
    
    return RedirectResponse(url="/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, error: str = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid username or password"
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

@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Employees routes
@app.get("/employees", response_class=HTMLResponse)
async def employees_list(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    employees = db.query(User).all()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "current_user": current_user,
        "employees": employees
    })

@app.post("/employees/new")
async def create_employee(
    request: Request,
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
        employees = db.query(User).all()
        return templates.TemplateResponse("employees.html", {
            "request": request,
            "current_user": current_user,
            "employees": employees,
            "error": "Username already exists"
        })
    
    hashed_password = hash_password(password)
    employee = User(
        username=username,
        full_name=full_name,
        hashed_password=hashed_password,
        hourly_wage=hourly_wage,
        work_schedule=work_schedule,
        role=role,
        is_active=True
    )
    db.add(employee)
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)

@app.get("/employees/{employee_id}", response_class=HTMLResponse)
async def employee_detail(
    request: Request,
    employee_id: int,
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
    request: Request,
    employee_id: int,
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
async def employee_edit_submit(
    request: Request,
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
        return templates.TemplateResponse("employee_edit.html", {
            "request": request,
            "current_user": current_user,
            "employee": employee,
            "error": "Username already exists"
        })
    
    employee.full_name = full_name
    employee.username = username
    if password:
        employee.hashed_password = hash_password(password)
    employee.hourly_wage = hourly_wage
    employee.work_schedule = work_schedule
    employee.role = role
    employee.is_active = is_active
    
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
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    # Deactivate instead of delete to preserve data integrity
    employee.is_active = False
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)

# Categories routes
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

# Vendors routes
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

# Vendor Units routes
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

# Usage Units routes
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

# Ingredients routes
@app.get("/ingredients", response_class=HTMLResponse)
async def ingredients_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).options(
        joinedload(Ingredient.category),
        joinedload(Ingredient.vendor),
        joinedload(Ingredient.vendor_unit),
        joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
    ).all()
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
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    vendor_unit_id: Optional[int] = Form(None),
    purchase_weight_volume: float = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Calculate item weight for cases
    item_weight_volume = None
    if purchase_type == "case" and items_per_case:
        item_weight_volume = purchase_weight_volume / items_per_case
    
    ingredient = Ingredient(
        name=name,
        category_id=category_id,
        vendor_id=vendor_id,
        purchase_type=purchase_type,
        purchase_unit_name=purchase_unit_name,
        vendor_unit_id=vendor_unit_id,
        purchase_weight_volume=purchase_weight_volume,
        purchase_total_cost=purchase_total_cost,
        breakable_case=breakable_case,
        items_per_case=items_per_case,
        item_weight_volume=item_weight_volume
    )
    db.add(ingredient)
    db.flush()  # Get the ID
    
    # Handle usage unit conversions
    form_data = await request.form()
    usage_units = db.query(UsageUnit).all()
    
    for unit in usage_units:
        conversion_key = f"conversion_{unit.id}"
        if conversion_key in form_data and form_data[conversion_key]:
            conversion_factor = float(form_data[conversion_key])
            price_per_usage_unit = purchase_total_cost / (purchase_weight_volume * conversion_factor)
            
            usage_unit_rel = IngredientUsageUnit(
                ingredient_id=ingredient.id,
                usage_unit_id=unit.id,
                conversion_factor=conversion_factor,
                price_per_usage_unit=price_per_usage_unit
            )
            db.add(usage_unit_rel)
    
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

@app.get("/ingredients/{ingredient_id}", response_class=HTMLResponse)
async def ingredient_detail(
    request: Request,
    ingredient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).options(
        joinedload(Ingredient.category),
        joinedload(Ingredient.vendor),
        joinedload(Ingredient.vendor_unit),
        joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
    ).filter(Ingredient.id == ingredient_id).first()
    
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    return templates.TemplateResponse("ingredient_detail.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient
    })

@app.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
async def ingredient_edit_form(
    request: Request,
    ingredient_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).options(
        joinedload(Ingredient.category),
        joinedload(Ingredient.vendor),
        joinedload(Ingredient.vendor_unit),
        joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
    ).filter(Ingredient.id == ingredient_id).first()
    
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
async def ingredient_edit_submit(
    request: Request,
    ingredient_id: int,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    vendor_id: Optional[int] = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    vendor_unit_id: Optional[int] = Form(None),
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
    
    # Calculate item weight for cases
    item_weight_volume = None
    if purchase_type == "case" and items_per_case:
        item_weight_volume = purchase_weight_volume / items_per_case
    
    # Update ingredient
    ingredient.name = name
    ingredient.category_id = category_id
    ingredient.vendor_id = vendor_id
    ingredient.purchase_type = purchase_type
    ingredient.purchase_unit_name = purchase_unit_name
    ingredient.vendor_unit_id = vendor_unit_id
    ingredient.purchase_weight_volume = purchase_weight_volume
    ingredient.purchase_total_cost = purchase_total_cost
    ingredient.breakable_case = breakable_case
    ingredient.items_per_case = items_per_case
    ingredient.item_weight_volume = item_weight_volume
    
    # Update usage unit conversions
    form_data = await request.form()
    
    # Remove existing conversions
    db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).delete()
    
    # Add new conversions
    usage_units = db.query(UsageUnit).all()
    for unit in usage_units:
        conversion_key = f"conversion_{unit.id}"
        if conversion_key in form_data and form_data[conversion_key]:
            conversion_factor = float(form_data[conversion_key])
            price_per_usage_unit = purchase_total_cost / (purchase_weight_volume * conversion_factor)
            
            usage_unit_rel = IngredientUsageUnit(
                ingredient_id=ingredient.id,
                usage_unit_id=unit.id,
                conversion_factor=conversion_factor,
                price_per_usage_unit=price_per_usage_unit
            )
            db.add(usage_unit_rel)
    
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

# Recipes routes
@app.get("/recipes", response_class=HTMLResponse)
async def recipes_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    request: Request,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: Optional[int] = Form(None),
    ingredients_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = Recipe(
        name=name,
        instructions=instructions,
        category_id=category_id
    )
    db.add(recipe)
    db.flush()
    
    # Parse ingredients data
    try:
        ingredients = json.loads(ingredients_data)
        for ing_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ing_data['ingredient_id'],
                usage_unit_id=ing_data['usage_unit_id'],
                quantity=ing_data['quantity'],
                cost=ing_data['estimated_cost']
            )
            db.add(recipe_ingredient)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid ingredients data")
    
    db.commit()
    return RedirectResponse(url="/recipes", status_code=302)

@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(
    request: Request,
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).options(joinedload(Recipe.category)).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.category),
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.usage_units),
        joinedload(RecipeIngredient.usage_unit)
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
async def recipe_edit_form(
    request: Request,
    recipe_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).options(joinedload(Recipe.category)).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient),
        joinedload(RecipeIngredient.usage_unit)
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
async def recipe_edit_submit(
    request: Request,
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
    recipe.category_id = category_id
    
    # Remove existing ingredients
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
    # Add new ingredients
    try:
        ingredients = json.loads(ingredients_data)
        for ing_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ing_data['ingredient_id'],
                usage_unit_id=ing_data['usage_unit_id'],
                quantity=ing_data['quantity'],
                cost=ing_data['estimated_cost']
            )
            db.add(recipe_ingredient)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid ingredients data")
    
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

# Batches routes
@app.get("/batches", response_class=HTMLResponse)
async def batches_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batches = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category),
        joinedload(Batch.yield_unit)
    ).all()
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
    # Validation for variable vs fixed yield
    if not is_variable and (not yield_amount or not yield_unit_id):
        raise HTTPException(status_code=400, detail="Yield amount and unit required for non-variable batches")
    
    if is_variable:
        yield_amount = None
        yield_unit_id = None
    
    batch = Batch(
        recipe_id=recipe_id,
        is_variable=is_variable,
        yield_amount=yield_amount,
        yield_unit_id=yield_unit_id,
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
async def batch_detail(
    request: Request,
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category),
        joinedload(Batch.yield_unit)
    ).filter(Batch.id == batch_id).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.category),
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.usage_units),
        joinedload(RecipeIngredient.usage_unit)
    ).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    total_batch_cost = total_recipe_cost + (batch.estimated_labor_cost or 0)
    cost_per_yield_unit = total_batch_cost / (batch.yield_amount or 1) if batch.yield_amount else 0
    
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
    request: Request,
    batch_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).options(
        joinedload(Batch.recipe),
        joinedload(Batch.yield_unit)
    ).filter(Batch.id == batch_id).first()
    
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
async def batch_edit_submit(
    batch_id: int,
    recipe_id: int = Form(...),
    is_variable: bool = Form(False),
    yield_amount: Optional[float] = Form(None),
    yield_unit_id: Optional[int] = Form(None),
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
    
    # Validation for variable vs fixed yield
    if not is_variable and (not yield_amount or not yield_unit_id):
        raise HTTPException(status_code=400, detail="Yield amount and unit required for non-variable batches")
    
    if is_variable:
        yield_amount = None
        yield_unit_id = None
    
    # Update batch
    batch.recipe_id = recipe_id
    batch.is_variable = is_variable
    batch.yield_amount = yield_amount
    batch.yield_unit_id = yield_unit_id
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

# Dishes routes
@app.get("/dishes", response_class=HTMLResponse)
async def dishes_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    request: Request,
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form("[]"),
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
    db.flush()
    
    # Parse batch portions data
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            dish_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data['batch_id'],
                portion_unit_id=portion_data['portion_unit_id'],
                portion_size=portion_data['portion_size'],
                expected_cost=portion_data['estimated_cost'],
                actual_cost=0.0  # Will be calculated later
            )
            db.add(dish_portion)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid batch portions data")
    
    db.commit()
    return RedirectResponse(url="/dishes", status_code=302)

@app.get("/dishes/{dish_id}", response_class=HTMLResponse)
async def dish_detail(
    request: Request,
    dish_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).options(joinedload(Dish.category)).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).options(
        joinedload(DishBatchPortion.batch).joinedload(Batch.recipe).joinedload(Recipe.category),
        joinedload(DishBatchPortion.batch).joinedload(Batch.yield_unit),
        joinedload(DishBatchPortion.portion_unit)
    ).filter(DishBatchPortion.dish_id == dish_id).all()
    
    expected_total_cost = sum(portion.expected_cost or 0 for portion in dish_batch_portions)
    actual_total_cost = sum(portion.actual_cost or 0 for portion in dish_batch_portions)
    
    expected_profit = dish.sale_price - expected_total_cost
    expected_profit_margin = (expected_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_profit = dish.sale_price - actual_total_cost
    actual_profit_margin = (actual_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    # Calculate week and month averages (placeholder for now)
    actual_total_cost_week = actual_total_cost
    actual_profit_week = dish.sale_price - actual_total_cost_week
    actual_profit_margin_week = (actual_profit_week / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_total_cost_month = actual_total_cost
    actual_profit_month = dish.sale_price - actual_total_cost_month
    actual_profit_margin_month = (actual_profit_month / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_total_cost_all_time = actual_total_cost
    actual_profit_all_time = dish.sale_price - actual_total_cost_all_time
    actual_profit_margin_all_time = (actual_profit_all_time / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    return templates.TemplateResponse("dish_detail.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "dish_batch_portions": dish_batch_portions,
        "expected_total_cost": expected_total_cost,
        "actual_total_cost": actual_total_cost,
        "expected_profit": expected_profit,
        "expected_profit_margin": expected_profit_margin,
        "actual_profit": actual_profit,
        "actual_profit_margin": actual_profit_margin,
        "actual_total_cost_week": actual_total_cost_week,
        "actual_profit_week": actual_profit_week,
        "actual_profit_margin_week": actual_profit_margin_week,
        "actual_total_cost_month": actual_total_cost_month,
        "actual_profit_month": actual_profit_month,
        "actual_profit_margin_month": actual_profit_margin_month,
        "actual_total_cost_all_time": actual_total_cost_all_time,
        "actual_profit_all_time": actual_profit_all_time,
        "actual_profit_margin_all_time": actual_profit_margin_all_time
    })

@app.get("/dishes/{dish_id}/edit", response_class=HTMLResponse)
async def dish_edit_form(
    request: Request,
    dish_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).options(joinedload(Dish.category)).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).options(
        joinedload(DishBatchPortion.batch).joinedload(Batch.recipe),
        joinedload(DishBatchPortion.batch).joinedload(Batch.yield_unit),
        joinedload(DishBatchPortion.portion_unit)
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
async def dish_edit_submit(
    request: Request,
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
    dish.category_id = category_id
    dish.sale_price = sale_price
    dish.description = description
    
    # Remove existing batch portions
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Add new batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            dish_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data['batch_id'],
                portion_unit_id=portion_data['portion_unit_id'],
                portion_size=portion_data['portion_size'],
                expected_cost=portion_data['estimated_cost'],
                actual_cost=0.0
            )
            db.add(dish_portion)
    except (json.JSONDecodeError, KeyError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid batch portions data")
    
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
async def inventory_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).options(
        joinedload(InventoryItem.category),
        joinedload(InventoryItem.batch).joinedload(Batch.recipe),
        joinedload(InventoryItem.par_unit_equals