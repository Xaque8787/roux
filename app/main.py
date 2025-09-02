from fastapi import FastAPI, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta
from typing import List, Optional
import json

from .database import SessionLocal, engine, get_db
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, VendorUnit, VendorUnitConversion, UsageUnit, IngredientUsageUnit, Vendor
from .auth import hash_password, verify_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Root redirect
@app.get("/")
def root():
    return RedirectResponse(url="/home")

# Check if setup is needed
def needs_setup(db: Session):
    return db.query(User).count() == 0

# Setup route
@app.get("/setup", response_class=HTMLResponse)
def setup_form(request: Request, db: Session = Depends(get_db)):
    if not needs_setup(db):
        return RedirectResponse(url="/home")
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_admin(
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
    
    # Create admin user
    admin_user = User(
        username=username,
        hashed_password=hash_password(password),
        full_name=full_name,
        role="admin",
        is_admin=True
    )
    db.add(admin_user)
    
    # Create default categories
    default_categories = [
        ("Proteins", "ingredient"),
        ("Vegetables", "ingredient"),
        ("Dairy", "ingredient"),
        ("Grains", "ingredient"),
        ("Spices", "ingredient"),
        ("Appetizers", "recipe"),
        ("Main Courses", "recipe"),
        ("Desserts", "recipe"),
        ("Beverages", "recipe"),
        ("Prep Items", "batch"),
        ("Sauces", "batch"),
        ("Appetizers", "dish"),
        ("Entrees", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Proteins", "inventory"),
        ("Vegetables", "inventory"),
        ("Dairy", "inventory"),
        ("Dry Goods", "inventory")
    ]
    
    for name, cat_type in default_categories:
        # Check if category already exists
        existing = db.query(Category).filter(Category.name == name, Category.type == cat_type).first()
        if not existing:
            category = Category(name=name, type=cat_type)
            db.add(category)
    
    # Create default vendor units
    default_vendor_units = [
        ("lb", "Pound"),
        ("oz", "Ounce"),
        ("gal", "Gallon"),
        ("qt", "Quart"),
        ("pt", "Pint"),
        ("fl oz", "Fluid Ounce"),
        ("kg", "Kilogram"),
        ("g", "Gram"),
        ("L", "Liter"),
        ("mL", "Milliliter")
    ]
    
    for name, description in default_vendor_units:
        existing = db.query(VendorUnit).filter(VendorUnit.name == name).first()
        if not existing:
            vendor_unit = VendorUnit(name=name, description=description)
            db.add(vendor_unit)
    
    # Create default usage units
    default_usage_units = [
        "lb", "oz", "cup", "tbsp", "tsp", "gal", "qt", "pt", "fl oz",
        "each", "can", "jar", "bag", "box", "bunch", "head", "clove",
        "slice", "piece", "pinch", "dash", "kg", "g", "L", "mL"
    ]
    
    for unit_name in default_usage_units:
        existing = db.query(UsageUnit).filter(UsageUnit.name == unit_name).first()
        if not existing:
            usage_unit = UsageUnit(name=unit_name)
            db.add(usage_unit)
    
    # Create default vendor unit conversions
    db.flush()  # Ensure units are created before conversions
    
    # Common conversions (vendor unit to usage unit)
    default_conversions = [
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
        ("pt", "fl oz", 16.0),
        ("fl oz", "fl oz", 1.0),
        ("kg", "kg", 1.0),
        ("kg", "g", 1000.0),
        ("kg", "lb", 2.20462),
        ("g", "g", 1.0),
        ("g", "oz", 0.035274),
        ("L", "L", 1.0),
        ("L", "mL", 1000.0),
        ("L", "qt", 1.05669),
        ("mL", "mL", 1.0),
        ("mL", "fl oz", 0.033814)
    ]
    
    for vendor_unit_name, usage_unit_name, factor in default_conversions:
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
    token = create_jwt(data={"sub": username})
    response = RedirectResponse(url="/home", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    return response

# Login routes
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
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
    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
    token = create_jwt(data={"sub": username})
    response = RedirectResponse(url="/home", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax"
    )
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response

# Home page
@app.get("/home", response_class=HTMLResponse)
def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Employee routes
@app.get("/employees", response_class=HTMLResponse)
def employees(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    employees = db.query(User).all()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "current_user": current_user,
        "employees": employees
    })

@app.post("/employees/new")
async def create_employee(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    try:
        form_data = await request.form()
        
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == form_data["username"]).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Handle work schedule
        work_schedule = form_data.get("work_schedule", "")
        
        employee = User(
            username=form_data["username"],
            hashed_password=hash_password(form_data["password"]),
            full_name=form_data["full_name"],
            hourly_wage=float(form_data["hourly_wage"]),
            work_schedule=work_schedule,
            role=form_data["role"],
            is_admin=(form_data["role"] == "admin"),
            is_user=True,
            is_active=True
        )
        
        db.add(employee)
        db.commit()
        
        return RedirectResponse(url="/employees", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/employees/{employee_id}", response_class=HTMLResponse)
def employee_detail(
    employee_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
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
def employee_edit_form(
    employee_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
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
async def update_employee(
    employee_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    try:
        form_data = await request.form()
        
        employee = db.query(User).filter(User.id == employee_id).first()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Check username uniqueness (excluding current user)
        if form_data["username"] != employee.username:
            existing_user = db.query(User).filter(
                User.username == form_data["username"],
                User.id != employee_id
            ).first()
            if existing_user:
                raise HTTPException(status_code=400, detail="Username already exists")
        
        # Update fields
        employee.username = form_data["username"]
        employee.full_name = form_data["full_name"]
        employee.hourly_wage = float(form_data["hourly_wage"])
        employee.work_schedule = form_data.get("work_schedule", "")
        employee.role = form_data["role"]
        employee.is_admin = (form_data["role"] == "admin")
        employee.is_active = "is_active" in form_data
        
        # Update password if provided
        if form_data.get("password"):
            employee.hashed_password = hash_password(form_data["password"])
        
        db.commit()
        return RedirectResponse(url=f"/employees/{employee_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/employees/{employee_id}/delete")
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Don't allow deleting yourself
    if employee.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    # Deactivate instead of delete
    employee.is_active = False
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=303)

# Ingredient routes
@app.get("/ingredients", response_class=HTMLResponse)
def ingredients(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    try:
        form_data = await request.form()
        
        ingredient = Ingredient(
            name=form_data["name"],
            category_id=int(form_data["category_id"]) if form_data.get("category_id") else None,
            vendor_id=int(form_data["vendor_id"]) if form_data.get("vendor_id") else None,
            vendor_unit_id=int(form_data["vendor_unit_id"]) if form_data.get("vendor_unit_id") else None,
            purchase_type=form_data["purchase_type"],
            purchase_unit_name=form_data["purchase_unit_name"],
            purchase_weight_volume=float(form_data["purchase_weight_volume"]),
            purchase_total_cost=float(form_data["purchase_total_cost"]),
            breakable_case="breakable_case" in form_data,
            items_per_case=int(form_data["items_per_case"]) if form_data.get("items_per_case") else None
        )
        
        db.add(ingredient)
        db.flush()  # Get the ingredient ID
        
        # Add usage unit conversions
        for key, value in form_data.items():
            if key.startswith("conversion_") and value:
                usage_unit_id = int(key.split("_")[1])
                conversion_factor = float(value)
                
                ingredient_usage = IngredientUsageUnit(
                    ingredient_id=ingredient.id,
                    usage_unit_id=usage_unit_id,
                    conversion_factor=conversion_factor
                )
                db.add(ingredient_usage)
        
        db.commit()
        return RedirectResponse(url="/ingredients", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/ingredients/{ingredient_id}", response_class=HTMLResponse)
def ingredient_detail(
    ingredient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
def ingredient_edit_form(
    ingredient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
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
    ingredient_usage_units = db.query(IngredientUsageUnit).filter(
        IngredientUsageUnit.ingredient_id == ingredient_id
    ).all()
    for iu in ingredient_usage_units:
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
async def update_ingredient(
    ingredient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    try:
        form_data = await request.form()
        
        ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
        if not ingredient:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        
        # Update ingredient fields
        ingredient.name = form_data["name"]
        ingredient.category_id = int(form_data["category_id"]) if form_data.get("category_id") else None
        ingredient.vendor_id = int(form_data["vendor_id"]) if form_data.get("vendor_id") else None
        ingredient.vendor_unit_id = int(form_data["vendor_unit_id"]) if form_data.get("vendor_unit_id") else None
        ingredient.purchase_type = form_data["purchase_type"]
        ingredient.purchase_unit_name = form_data["purchase_unit_name"]
        ingredient.purchase_weight_volume = float(form_data["purchase_weight_volume"])
        ingredient.purchase_total_cost = float(form_data["purchase_total_cost"])
        ingredient.breakable_case = "breakable_case" in form_data
        ingredient.items_per_case = int(form_data["items_per_case"]) if form_data.get("items_per_case") else None
        
        # Remove existing usage unit conversions
        db.query(IngredientUsageUnit).filter(
            IngredientUsageUnit.ingredient_id == ingredient_id
        ).delete()
        
        # Add new usage unit conversions
        for key, value in form_data.items():
            if key.startswith("conversion_") and value:
                usage_unit_id = int(key.split("_")[1])
                conversion_factor = float(value)
                
                ingredient_usage = IngredientUsageUnit(
                    ingredient_id=ingredient.id,
                    usage_unit_id=usage_unit_id,
                    conversion_factor=conversion_factor
                )
                db.add(ingredient_usage)
        
        db.commit()
        return RedirectResponse(url=f"/ingredients/{ingredient_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/ingredients/{ingredient_id}/delete")
def delete_ingredient(
    ingredient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    db.delete(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=303)

# Recipe routes
@app.get("/recipes", response_class=HTMLResponse)
def recipes(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    try:
        form_data = await request.form()
        
        recipe = Recipe(
            name=form_data["name"],
            instructions=form_data.get("instructions"),
            category_id=int(form_data["category_id"]) if form_data.get("category_id") else None
        )
        
        db.add(recipe)
        db.flush()  # Get the recipe ID
        
        # Add ingredients
        ingredients_data = form_data.get("ingredients_data")
        if ingredients_data:
            ingredients = json.loads(ingredients_data)
            for ing_data in ingredients:
                recipe_ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ing_data["ingredient_id"],
                    usage_unit_id=ing_data["usage_unit_id"],
                    quantity=ing_data["quantity"]
                )
                db.add(recipe_ingredient)
        
        db.commit()
        return RedirectResponse(url="/recipes", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
def recipe_detail(
    recipe_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
def recipe_edit_form(
    recipe_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
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
async def update_recipe(
    recipe_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    try:
        form_data = await request.form()
        
        recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        # Update recipe fields
        recipe.name = form_data["name"]
        recipe.instructions = form_data.get("instructions")
        recipe.category_id = int(form_data["category_id"]) if form_data.get("category_id") else None
        
        # Remove existing ingredients
        db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
        
        # Add new ingredients
        ingredients_data = form_data.get("ingredients_data")
        if ingredients_data:
            ingredients = json.loads(ingredients_data)
            for ing_data in ingredients:
                recipe_ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ing_data["ingredient_id"],
                    usage_unit_id=ing_data["usage_unit_id"],
                    quantity=ing_data["quantity"]
                )
                db.add(recipe_ingredient)
        
        db.commit()
        return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/recipes/{recipe_id}/delete")
def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    db.delete(recipe)
    db.commit()
    
    return RedirectResponse(url="/recipes", status_code=303)

# Batch routes
@app.get("/batches", response_class=HTMLResponse)
def batches(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    try:
        form_data = await request.form()
        
        batch = Batch(
            recipe_id=int(form_data["recipe_id"]),
            yield_amount=float(form_data["yield_amount"]),
            yield_unit_id=int(form_data["yield_unit_id"]),
            estimated_labor_minutes=int(form_data["estimated_labor_minutes"]),
            hourly_labor_rate=float(form_data["hourly_labor_rate"]),
            can_be_scaled="can_be_scaled" in form_data,
            scale_double="scale_double" in form_data,
            scale_half="scale_half" in form_data,
            scale_quarter="scale_quarter" in form_data,
            scale_eighth="scale_eighth" in form_data,
            scale_sixteenth="scale_sixteenth" in form_data
        )
        
        db.add(batch)
        db.commit()
        
        return RedirectResponse(url="/batches", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/batches/{batch_id}", response_class=HTMLResponse)
def batch_detail(
    batch_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
def batch_edit_form(
    batch_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
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
async def update_batch(
    batch_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    try:
        form_data = await request.form()
        
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Update batch fields
        batch.recipe_id = int(form_data["recipe_id"])
        batch.yield_amount = float(form_data["yield_amount"])
        batch.yield_unit_id = int(form_data["yield_unit_id"])
        batch.estimated_labor_minutes = int(form_data["estimated_labor_minutes"])
        batch.hourly_labor_rate = float(form_data["hourly_labor_rate"])
        batch.can_be_scaled = "can_be_scaled" in form_data
        batch.scale_double = "scale_double" in form_data
        batch.scale_half = "scale_half" in form_data
        batch.scale_quarter = "scale_quarter" in form_data
        batch.scale_eighth = "scale_eighth" in form_data
        batch.scale_sixteenth = "scale_sixteenth" in form_data
        
        db.commit()
        return RedirectResponse(url=f"/batches/{batch_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/batches/{batch_id}/delete")
def delete_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    db.delete(batch)
    db.commit()
    
    return RedirectResponse(url="/batches", status_code=303)

# Dish routes
@app.get("/dishes", response_class=HTMLResponse)
def dishes(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    try:
        form_data = await request.form()
        
        dish = Dish(
            name=form_data["name"],
            category_id=int(form_data["category_id"]) if form_data.get("category_id") else None,
            sale_price=float(form_data["sale_price"]),
            description=form_data.get("description")
        )
        
        db.add(dish)
        db.flush()  # Get the dish ID
        
        # Add batch portions
        batch_portions_data = form_data.get("batch_portions_data")
        if batch_portions_data:
            batch_portions = json.loads(batch_portions_data)
            for portion_data in batch_portions:
                dish_batch_portion = DishBatchPortion(
                    dish_id=dish.id,
                    batch_id=portion_data["batch_id"],
                    portion_size=portion_data["portion_size"],
                    portion_unit_id=portion_data.get("portion_unit_id")
                )
                db.add(dish_batch_portion)
        
        db.commit()
        return RedirectResponse(url="/dishes", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/dishes/{dish_id}", response_class=HTMLResponse)
def dish_detail(
    dish_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    dish_batch_portions = db.query(DishBatchPortion).filter(
        DishBatchPortion.dish_id == dish_id
    ).all()
    
    # Calculate costs using the property methods
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
def dish_edit_form(
    dish_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
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
async def update_dish(
    dish_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    try:
        form_data = await request.form()
        
        dish = db.query(Dish).filter(Dish.id == dish_id).first()
        if not dish:
            raise HTTPException(status_code=404, detail="Dish not found")
        
        # Update dish fields
        dish.name = form_data["name"]
        dish.category_id = int(form_data["category_id"]) if form_data.get("category_id") else None
        dish.sale_price = float(form_data["sale_price"])
        dish.description = form_data.get("description")
        
        # Remove existing batch portions
        db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
        
        # Add new batch portions
        batch_portions_data = form_data.get("batch_portions_data")
        if batch_portions_data:
            batch_portions = json.loads(batch_portions_data)
            for portion_data in batch_portions:
                dish_batch_portion = DishBatchPortion(
                    dish_id=dish.id,
                    batch_id=portion_data["batch_id"],
                    portion_size=portion_data["portion_size"],
                    portion_unit_id=portion_data.get("portion_unit_id")
                )
                db.add(dish_batch_portion)
        
        db.commit()
        return RedirectResponse(url=f"/dishes/{dish_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/dishes/{dish_id}/delete")
def delete_dish(
    dish_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    db.delete(dish)
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=303)

# Inventory routes
@app.get("/inventory", response_class=HTMLResponse)
def inventory(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inventory_items = db.query(InventoryItem).all()
    batches = db.query(Batch).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get current day (not finalized)
    current_day = db.query(InventoryDay).filter(
        InventoryDay.finalized == False
    ).order_by(InventoryDay.date.desc()).first()
    
    # Get recent finalized days (last 30 days)
    thirty_days_ago = date.today() - timedelta(days=30)
    finalized_days = db.query(InventoryDay).filter(
        InventoryDay.finalized == True,
        InventoryDay.date >= thirty_days_ago
    ).order_by(InventoryDay.date.desc()).limit(10).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request, 
        "current_user": current_user,
        "inventory_items": inventory_items,
        "batches": batches,
        "categories": categories,
        "employees": employees,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "today_date": date.today().isoformat()
    })

@app.get("/inventory/day/{day_id}")
def inventory_day_detail(
    day_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    # Get inventory day items
    inventory_day_items = db.query(InventoryDayItem).filter(
        InventoryDayItem.day_id == day_id
    ).join(InventoryItem).all()
    
    # Get tasks for this day
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    
    # Get employees
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot update finalized day")
    
    try:
        # Get form data
        form_data = await request.form()
        
        # Update global notes
        inventory_day.global_notes = form_data.get("global_notes", "")
        
        # Update inventory quantities and overrides
        inventory_items = db.query(InventoryDayItem).filter(
            InventoryDayItem.day_id == day_id
        ).all()
        
        for item in inventory_items:
            quantity_key = f"item_{item.inventory_item.id}"
            override_create_key = f"override_create_{item.inventory_item.id}"
            override_no_task_key = f"override_no_task_{item.inventory_item.id}"
            
            if quantity_key in form_data:
                item.quantity = float(form_data[quantity_key])
            
            item.override_create_task = override_create_key in form_data
            item.override_no_task = override_no_task_key in form_data
        
        # Generate tasks for below-par items
        for item in inventory_items:
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
                    task = Task(
                        day_id=day_id,
                        inventory_item_id=item.inventory_item.id,
                        batch_id=item.inventory_item.batch_id,
                        description=f"Prep {item.inventory_item.name}",
                        auto_generated=True
                    )
                    db.add(task)
        
        db.commit()
        return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/inventory/day/{day_id}/tasks/new")
async def create_manual_task(
    day_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    try:
        form_data = await request.form()
        
        # Get assigned employee IDs
        assigned_to_ids = form_data.getlist("assigned_to_ids")
        description = form_data.get("description")
        inventory_item_id = form_data.get("inventory_item_id") or None
        
        if not description:
            raise HTTPException(status_code=400, detail="Description is required")
        
        # Create tasks for each assigned employee or one unassigned task
        if assigned_to_ids:
            for emp_id in assigned_to_ids:
                task = Task(
                    day_id=day_id,
                    assigned_to_id=int(emp_id),
                    inventory_item_id=int(inventory_item_id) if inventory_item_id else None,
                    description=description,
                    auto_generated=False
                )
                # Set batch_id if inventory item has one
                if inventory_item_id:
                    inventory_item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
                    if inventory_item and inventory_item.batch_id:
                        task.batch_id = inventory_item.batch_id
                db.add(task)
        else:
            # Create unassigned task
            task = Task(
                day_id=day_id,
                inventory_item_id=int(inventory_item_id) if inventory_item_id else None,
                description=description,
                auto_generated=False
            )
            # Set batch_id if inventory item has one
            if inventory_item_id:
                inventory_item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
                if inventory_item and inventory_item.batch_id:
                    task.batch_id = inventory_item.batch_id
            db.add(task)
        
        db.commit()
        return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/inventory/day/{day_id}/tasks/{task_id}/assign")
async def assign_task(
    day_id: int,
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    try:
        form_data = await request.form()
        assigned_to_id = form_data.get("assigned_to_id")
        
        task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task.assigned_to_id = int(assigned_to_id) if assigned_to_id else None
        db.commit()
        
        return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start")
def start_task(
    day_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.started_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/pause")
def pause_task(
    day_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.started_at and not task.is_paused:
        task.paused_at = datetime.utcnow()
        task.is_paused = True
        db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/resume")
def resume_task(
    day_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.is_paused and task.paused_at:
        # Add pause time to total
        pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
        task.total_pause_time += int(pause_duration)
        task.is_paused = False
        task.paused_at = None
        db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish")
def finish_task(
    day_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.is_paused and task.paused_at:
        # Add final pause time
        pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
        task.total_pause_time += int(pause_duration)
    
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    task.paused_at = None
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.get("/inventory/day/{day_id}/tasks/{task_id}")
def task_detail(
    day_id: int,
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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

@app.post("/inventory/day/{day_id}/tasks/{task_id}/notes")
async def update_task_notes(
    day_id: int,
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        form_data = await request.form()
        notes = form_data.get("notes", "")
        
        task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task.notes = notes
        db.commit()
        
        return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/inventory/day/{day_id}/finalize")
def finalize_inventory_day(
    day_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day.finalized = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=303)

@app.get("/inventory/reports/{day_id}")
def inventory_report(
    day_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    # Get inventory day items
    inventory_day_items = db.query(InventoryDayItem).filter(
        InventoryDayItem.day_id == day_id
    ).join(InventoryItem).all()
    
    # Get tasks for this day
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    
    # Calculate statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.finished_at])
    below_par_items = len([item for item in inventory_day_items 
                          if item.quantity <= item.inventory_item.par_level])
    
    employees = db.query(User).filter(User.is_active == True).all()
    
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

@app.post("/inventory/new_item")
async def create_inventory_item(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    try:
        form_data = await request.form()
        
        item = InventoryItem(
            name=form_data["name"],
            category_id=int(form_data["category_id"]) if form_data.get("category_id") else None,
            batch_id=int(form_data["batch_id"]) if form_data.get("batch_id") else None,
            par_level=float(form_data["par_level"])
        )
        
        db.add(item)
        db.commit()
        
        return RedirectResponse(url="/inventory", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/inventory/new_day")
async def create_inventory_day(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    try:
        form_data = await request.form()
        
        # Parse date
        day_date = datetime.strptime(form_data["date"], "%Y-%m-%d").date()
        
        # Check if day already exists
        existing_day = db.query(InventoryDay).filter(InventoryDay.date == day_date).first()
        if existing_day:
            raise HTTPException(status_code=400, detail="Inventory day already exists for this date")
        
        # Get employee IDs
        employee_ids = form_data.getlist("employees_working")
        employees_working_str = ",".join(employee_ids) if employee_ids else ""
        
        # Create inventory day
        inventory_day = InventoryDay(
            date=day_date,
            employees_working=employees_working_str,
            global_notes=form_data.get("global_notes", "")
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
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/inventory/items/{item_id}/edit", response_class=HTMLResponse)
def inventory_item_edit_form(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
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
async def update_inventory_item(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    try:
        form_data = await request.form()
        
        item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Inventory item not found")
        
        item.name = form_data["name"]
        item.par_level = float(form_data["par_level"])
        item.batch_id = int(form_data["batch_id"]) if form_data.get("batch_id") else None
        item.category_id = int(form_data["category_id"]) if form_data.get("category_id") else None
        
        db.commit()
        return RedirectResponse(url="/inventory", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/inventory/items/{item_id}/delete")
def delete_inventory_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    db.delete(item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=303)

# Utility routes
@app.get("/utilities", response_class=HTMLResponse)
def utilities(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    utilities = db.query(UtilityCost).all()
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "current_user": current_user,
        "utilities": utilities
    })

@app.post("/utilities/new")
async def create_utility(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    try:
        form_data = await request.form()
        
        # Check if utility already exists
        existing = db.query(UtilityCost).filter(UtilityCost.name == form_data["name"]).first()
        if existing:
            # Update existing
            existing.monthly_cost = float(form_data["monthly_cost"])
            existing.last_updated = datetime.utcnow()
        else:
            # Create new
            utility = UtilityCost(
                name=form_data["name"],
                monthly_cost=float(form_data["monthly_cost"])
            )
            db.add(utility)
        
        db.commit()
        return RedirectResponse(url="/utilities", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/utilities/{utility_id}/delete")
def delete_utility(
    utility_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
    if not utility:
        raise HTTPException(status_code=404, detail="Utility not found")
    
    db.delete(utility)
    db.commit()
    
    return RedirectResponse(url="/utilities", status_code=303)

# Category routes
@app.post("/categories/new")
async def create_category(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    try:
        form_data = await request.form()
        
        category = Category(
            name=form_data["name"],
            type=form_data["type"]
        )
        
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
        
        redirect_url = redirect_map.get(form_data["type"], "/home")
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Vendor routes
@app.post("/vendors/new")
async def create_vendor(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    try:
        form_data = await request.form()
        
        vendor = Vendor(
            name=form_data["name"],
            contact_info=form_data.get("contact_info")
        )
        
        db.add(vendor)
        db.commit()
        
        return RedirectResponse(url="/ingredients", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Vendor unit routes
@app.post("/vendor_units/new")
async def create_vendor_unit(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    try:
        form_data = await request.form()
        
        vendor_unit = VendorUnit(
            name=form_data["name"],
            description=form_data.get("description")
        )
        
        db.add(vendor_unit)
        db.commit()
        
        return RedirectResponse(url="/ingredients", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Usage unit routes
@app.post("/usage_units/new")
async def create_usage_unit(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    try:
        form_data = await request.form()
        
        usage_unit = UsageUnit(name=form_data["name"])
        db.add(usage_unit)
        db.commit()
        
        return RedirectResponse(url="/ingredients", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# API Routes
@app.get("/api/ingredients/all")
def get_all_ingredients(db: Session = Depends(get_db)):
    """Get all ingredients with their usage units for recipe creation"""
    try:
        ingredients = db.query(Ingredient).all()
        result = []
        
        for ingredient in ingredients:
            usage_units = db.query(IngredientUsageUnit).filter(
                IngredientUsageUnit.ingredient_id == ingredient.id
            ).all()
            
            ingredient_data = {
                "id": ingredient.id,
                "name": ingredient.name,
                "category": ingredient.category.name if ingredient.category else None,
                "usage_units": [
                    {
                        "usage_unit_id": iu.usage_unit_id,
                        "usage_unit_name": iu.usage_unit.name,
                        "price_per_usage_unit": iu.price_per_usage_unit
                    }
                    for iu in usage_units
                ]
            }
            result.append(ingredient_data)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vendor_units/{vendor_unit_id}/conversions")
def get_vendor_unit_conversions(vendor_unit_id: int, db: Session = Depends(get_db)):
    """Get conversion factors for a vendor unit to usage units"""
    try:
        conversions = db.query(VendorUnitConversion).filter(
            VendorUnitConversion.vendor_unit_id == vendor_unit_id
        ).all()
        
        result = {}
        for conversion in conversions:
            result[conversion.usage_unit_id] = conversion.conversion_factor
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/batches/search")
def search_batches(q: str = "", db: Session = Depends(get_db)):
    """Search batches for dish creation"""
    try:
        query = db.query(Batch).join(Recipe)
        
        if q:
            query = query.filter(Recipe.name.ilike(f"%{q}%"))
        
        batches = query.limit(20).all()
        
        result = []
        for batch in batches:
            result.append({
                "id": batch.id,
                "recipe_name": batch.recipe.name,
                "yield_amount": batch.yield_amount,
                "yield_unit": batch.yield_unit.name if batch.yield_unit else "",
                "yield_unit_id": batch.yield_unit_id,
                "cost_per_unit": (sum(ri.cost for ri in batch.recipe.ingredients) + batch.estimated_labor_cost) / batch.yield_amount if batch.yield_amount > 0 else 0,
                "category": batch.recipe.category.name if batch.recipe.category else None
            })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/batches/all")
def get_all_batches(db: Session = Depends(get_db)):
    """Get all batches for dish creation"""
    try:
        batches = db.query(Batch).join(Recipe).all()
        
        result = []
        for batch in batches:
            result.append({
                "id": batch.id,
                "recipe_name": batch.recipe.name,
                "yield_amount": batch.yield_amount,
                "yield_unit": batch.yield_unit.name if batch.yield_unit else "",
                "yield_unit_id": batch.yield_unit_id,
                "cost_per_unit": (sum(ri.cost for ri in batch.recipe.ingredients) + batch.estimated_labor_cost) / batch.yield_amount if batch.yield_amount > 0 else 0,
                "category": batch.recipe.category.name if batch.recipe.category else None
            })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recipes/{recipe_id}/usage_units")
def get_recipe_usage_units(recipe_id: int, db: Session = Depends(get_db)):
    """Get all usage units available from recipe ingredients"""
    try:
        # Get all ingredients used in this recipe
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()
        
        usage_unit_ids = set()
        for ri in recipe_ingredients:
            # Add the usage unit from the recipe ingredient
            usage_unit_ids.add(ri.usage_unit_id)
            
            # Add all usage units available for this ingredient
            ingredient_usage_units = db.query(IngredientUsageUnit).filter(
                IngredientUsageUnit.ingredient_id == ri.ingredient_id
            ).all()
            for iu in ingredient_usage_units:
                usage_unit_ids.add(iu.usage_unit_id)
        
        # Get the actual usage unit objects
        usage_units = db.query(UsageUnit).filter(
            UsageUnit.id.in_(usage_unit_ids)
        ).all()
        
        return [{"id": unit.id, "name": unit.name} for unit in usage_units]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/batches/{batch_id}/portion_units")
def get_batch_portion_units(batch_id: int, db: Session = Depends(get_db)):
    """Get all available portion units for a batch based on recipe ingredients"""
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Get all usage units from recipe ingredients
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == batch.recipe_id
        ).all()
        
        usage_unit_ids = set()
        for ri in recipe_ingredients:
            # Add the usage unit from the recipe ingredient
            usage_unit_ids.add(ri.usage_unit_id)
            
            # Add all usage units available for this ingredient
            ingredient_usage_units = db.query(IngredientUsageUnit).filter(
                IngredientUsageUnit.ingredient_id == ri.ingredient_id
            ).all()
            for iu in ingredient_usage_units:
                usage_unit_ids.add(iu.usage_unit_id)
        
        # Get the actual usage unit objects
        usage_units = db.query(UsageUnit).filter(
            UsageUnit.id.in_(usage_unit_ids)
        ).all()
        
        return [{"id": unit.id, "name": unit.name} for unit in usage_units]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/batches/{batch_id}/cost_per_unit/{unit_id}")
def get_batch_cost_per_unit(batch_id: int, unit_id: int, db: Session = Depends(get_db)):
    """Calculate cost per unit for a batch in a specific unit"""
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Calculate total recipe cost
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == batch.recipe_id
        ).all()
        
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        
        # If the unit is the same as yield unit, simple calculation
        if unit_id == batch.yield_unit_id:
            cost_per_unit = total_batch_cost / batch.yield_amount
        else:
            # Need to convert between units - for now, assume 1:1 conversion
            # In a full implementation, you'd need a conversion table
            cost_per_unit = total_batch_cost / batch.yield_amount
        
        return {"expected_cost_per_unit": cost_per_unit}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/batches/{batch_id}/labor_stats")
def get_batch_labor_stats(batch_id: int, db: Session = Depends(get_db)):
    """Get labor statistics for a batch"""
    try:
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
                "most_recent_date": "No completed tasks",
                "average_week": batch.estimated_labor_cost,
                "average_month": batch.estimated_labor_cost,
                "average_all_time": batch.estimated_labor_cost,
                "week_task_count": 0,
                "month_task_count": 0
            }
        
        # Calculate statistics
        week_ago = datetime.utcnow() - timedelta(days=7)
        month_ago = datetime.utcnow() - timedelta(days=30)
        
        week_tasks = [t for t in completed_tasks if t.finished_at >= week_ago]
        month_tasks = [t for t in completed_tasks if t.finished_at >= month_ago]
        
        most_recent = completed_tasks[0]
        
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
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": exc.status_code,
        "detail": exc.detail
    }, status_code=exc.status_code)