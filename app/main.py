from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta
import json
import os

from .database import engine, get_db
from .models import Base, User, Category, Ingredient, Recipe, Batch, Dish, InventoryItem, InventoryDay, Task, UtilityCost
from .models import VendorUnit, Vendor, UsageUnit, IngredientUsageUnit, RecipeIngredient, DishBatchPortion
from .models import InventoryDayItem, VendorUnitConversion
from .auth import hash_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Food Cost Management System")

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
        ("Sides", "recipe"),
        ("Prep Items", "batch"),
        ("Sauces", "batch"),
        ("Appetizers", "dish"),
        ("Entrees", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Proteins", "inventory"),
        ("Vegetables", "inventory"),
        ("Prep Items", "inventory"),
        ("Cleaning Supplies", "inventory"),
    ]
    
    for name, cat_type in default_categories:
        existing = db.query(Category).filter(Category.name == name, Category.type == cat_type).first()
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
        ("pt", "Pint"),
        ("kg", "Kilogram"),
        ("g", "Gram"),
        ("L", "Liter"),
        ("mL", "Milliliter"),
    ]
    
    for name, description in vendor_units:
        existing = db.query(VendorUnit).filter(VendorUnit.name == name).first()
        if not existing:
            unit = VendorUnit(name=name, description=description)
            db.add(unit)
    
    # Usage units
    usage_units = [
        "lb", "oz", "g", "kg", "gal", "qt", "pt", "cup", "fl oz", "mL", "L",
        "tbsp", "tsp", "each", "piece", "slice", "can", "jar", "bag", "box",
        "bunch", "head", "clove", "pinch", "dash"
    ]
    
    for name in usage_units:
        existing = db.query(UsageUnit).filter(UsageUnit.name == name).first()
        if not existing:
            unit = UsageUnit(name=name)
            db.add(unit)
    
    db.commit()

# Root redirect
@app.get("/")
async def root():
    return RedirectResponse(url="/home", status_code=307)

# Setup routes
@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    if not needs_setup(db):
        return RedirectResponse(url="/home", status_code=302)
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_create_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(default=""),
    db: Session = Depends(get_db)
):
    if not needs_setup(db):
        return RedirectResponse(url="/home", status_code=302)
    
    try:
        # Create admin user
        hashed_password = hash_password(password)
        admin_user = User(
            username=username,
            hashed_password=hashed_password,
            full_name=full_name or username,
            role="admin",
            is_admin=True,
            is_user=True,
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        
        # Create default categories and units
        create_default_categories(db)
        create_default_units(db)
        
        return RedirectResponse(url="/login", status_code=302)
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("setup.html", {
            "request": request,
            "error": f"Error creating admin user: {str(e)}"
        })

# Login routes
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse(url="/setup", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
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
    work_schedule: str = Form(default=""),
    role: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        hashed_password = hash_password(password)
        employee = User(
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            hourly_wage=hourly_wage,
            work_schedule=work_schedule,
            role=role,
            is_admin=(role == "admin"),
            is_user=True,
            is_active=True
        )
        db.add(employee)
        db.commit()
        return RedirectResponse(url="/employees", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
async def update_employee(
    employee_id: int,
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(default=""),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(default=""),
    role: str = Form(...),
    is_active: bool = Form(default=False),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    try:
        employee.full_name = full_name
        employee.username = username
        employee.hourly_wage = hourly_wage
        employee.work_schedule = work_schedule
        employee.role = role
        employee.is_admin = (role == "admin")
        employee.is_active = is_active
        
        if password:  # Only update password if provided
            employee.hashed_password = hash_password(password)
        
        db.commit()
        return RedirectResponse(url=f"/employees/{employee_id}", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/employees/{employee_id}/delete")
async def delete_employee(
    employee_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    if employee_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
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
    try:
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Vendor management
@app.post("/vendors/new")
async def create_vendor(
    name: str = Form(...),
    contact_info: str = Form(default=""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        vendor = Vendor(name=name, contact_info=contact_info)
        db.add(vendor)
        db.commit()
        return RedirectResponse(url="/ingredients", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Vendor unit management
@app.post("/vendor_units/new")
async def create_vendor_unit(
    name: str = Form(...),
    description: str = Form(default=""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        unit = VendorUnit(name=name, description=description)
        db.add(unit)
        db.commit()
        return RedirectResponse(url="/ingredients", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Usage unit management
@app.post("/usage_units/new")
async def create_usage_unit(
    name: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        unit = UsageUnit(name=name)
        db.add(unit)
        db.commit()
        return RedirectResponse(url="/ingredients", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Ingredient routes
@app.get("/ingredients", response_class=HTMLResponse)
async def ingredients_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        form_data = await request.form()
        
        # Create ingredient
        ingredient = Ingredient(
            name=form_data.get("name"),
            category_id=int(form_data.get("category_id")) if form_data.get("category_id") else None,
            vendor_id=int(form_data.get("vendor_id")) if form_data.get("vendor_id") else None,
            vendor_unit_id=int(form_data.get("vendor_unit_id")) if form_data.get("vendor_unit_id") else None,
            purchase_type=form_data.get("purchase_type"),
            purchase_unit_name=form_data.get("purchase_unit_name"),
            purchase_weight_volume=float(form_data.get("purchase_weight_volume")) if form_data.get("purchase_weight_volume") else None,
            purchase_total_cost=float(form_data.get("purchase_total_cost")),
            breakable_case=bool(form_data.get("breakable_case")),
            items_per_case=int(form_data.get("items_per_case")) if form_data.get("items_per_case") else None
        )
        
        db.add(ingredient)
        db.flush()  # Get the ingredient ID
        
        # Add usage units
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
    
    usage_units = db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).all()
    
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
async def update_ingredient(
    ingredient_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    try:
        form_data = await request.form()
        
        # Update ingredient
        ingredient.name = form_data.get("name")
        ingredient.category_id = int(form_data.get("category_id")) if form_data.get("category_id") else None
        ingredient.vendor_id = int(form_data.get("vendor_id")) if form_data.get("vendor_id") else None
        ingredient.vendor_unit_id = int(form_data.get("vendor_unit_id")) if form_data.get("vendor_unit_id") else None
        ingredient.purchase_type = form_data.get("purchase_type")
        ingredient.purchase_unit_name = form_data.get("purchase_unit_name")
        ingredient.purchase_weight_volume = float(form_data.get("purchase_weight_volume")) if form_data.get("purchase_weight_volume") else None
        ingredient.purchase_total_cost = float(form_data.get("purchase_total_cost"))
        ingredient.breakable_case = bool(form_data.get("breakable_case"))
        ingredient.items_per_case = int(form_data.get("items_per_case")) if form_data.get("items_per_case") else None
        
        # Update usage units - remove existing and add new ones
        db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).delete()
        
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/ingredients/{ingredient_id}/delete")
async def delete_ingredient(
    ingredient_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    try:
        # Delete related usage units first
        db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).delete()
        db.delete(ingredient)
        db.commit()
        return RedirectResponse(url="/ingredients", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Recipe routes
@app.get("/recipes", response_class=HTMLResponse)
async def recipes_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    instructions: str = Form(default=""),
    category_id: int = Form(None),
    ingredients_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        # Create recipe
        recipe = Recipe(
            name=name,
            instructions=instructions,
            category_id=category_id if category_id else None
        )
        db.add(recipe)
        db.flush()  # Get the recipe ID
        
        # Add ingredients
        ingredients = json.loads(ingredients_data)
        for ingredient_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ingredient_data["ingredient_id"],
                usage_unit_id=ingredient_data["usage_unit_id"],
                quantity=ingredient_data["quantity"]
            )
            db.add(recipe_ingredient)
        
        db.commit()
        return RedirectResponse(url="/recipes", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
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
    name: str = Form(...),
    instructions: str = Form(default=""),
    category_id: int = Form(None),
    ingredients_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    try:
        # Update recipe
        recipe.name = name
        recipe.instructions = instructions
        recipe.category_id = category_id if category_id else None
        
        # Update ingredients - remove existing and add new ones
        db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
        
        ingredients = json.loads(ingredients_data)
        for ingredient_data in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ingredient_data["ingredient_id"],
                usage_unit_id=ingredient_data["usage_unit_id"],
                quantity=ingredient_data["quantity"]
            )
            db.add(recipe_ingredient)
        
        db.commit()
        return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/recipes/{recipe_id}/delete")
async def delete_recipe(
    recipe_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    try:
        # Delete related ingredients first
        db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
        db.delete(recipe)
        db.commit()
        return RedirectResponse(url="/recipes", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Batch routes
@app.get("/batches", response_class=HTMLResponse)
async def batches_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    hourly_labor_rate: float = Form(16.75),
    can_be_scaled: bool = Form(default=False),
    scale_double: bool = Form(default=False),
    scale_half: bool = Form(default=False),
    scale_quarter: bool = Form(default=False),
    scale_eighth: bool = Form(default=False),
    scale_sixteenth: bool = Form(default=False),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
async def update_batch(
    batch_id: int,
    recipe_id: int = Form(...),
    yield_amount: float = Form(...),
    yield_unit_id: int = Form(...),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(...),
    can_be_scaled: bool = Form(default=False),
    scale_double: bool = Form(default=False),
    scale_half: bool = Form(default=False),
    scale_quarter: bool = Form(default=False),
    scale_eighth: bool = Form(default=False),
    scale_sixteenth: bool = Form(default=False),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    try:
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/batches/{batch_id}/delete")
async def delete_batch(
    batch_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    try:
        db.delete(batch)
        db.commit()
        return RedirectResponse(url="/batches", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Dish routes
@app.get("/dishes", response_class=HTMLResponse)
async def dishes_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    category_id: int = Form(None),
    sale_price: float = Form(...),
    description: str = Form(default=""),
    batch_portions_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        # Create dish
        dish = Dish(
            name=name,
            category_id=category_id if category_id else None,
            sale_price=sale_price,
            description=description
        )
        db.add(dish)
        db.flush()  # Get the dish ID
        
        # Add batch portions
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
        return RedirectResponse(url="/dishes", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
    expected_total_cost = 0
    actual_total_cost = 0
    
    for portion in dish_batch_portions:
        # Calculate expected cost based on batch recipe cost + estimated labor
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == portion.batch.recipe_id).all()
        recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        batch_cost = recipe_cost + portion.batch.estimated_labor_cost
        cost_per_unit = batch_cost / portion.batch.yield_amount if portion.batch.yield_amount > 0 else 0
        portion.expected_cost = portion.portion_size * cost_per_unit
        expected_total_cost += portion.expected_cost
        
        # For actual cost, we would need to calculate based on actual labor data
        # For now, use expected cost as placeholder
        portion.actual_cost = portion.expected_cost
        actual_total_cost += portion.actual_cost
    
    expected_profit = dish.sale_price - expected_total_cost
    expected_profit_margin = (expected_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    actual_profit = dish.sale_price - actual_total_cost
    actual_profit_margin = (actual_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
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
    dish_batch_portions = db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).all()
    
    # Calculate expected costs for existing portions
    for portion in dish_batch_portions:
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == portion.batch.recipe_id).all()
        recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        batch_cost = recipe_cost + portion.batch.estimated_labor_cost
        cost_per_unit = batch_cost / portion.batch.yield_amount if portion.batch.yield_amount > 0 else 0
        portion.expected_cost = portion.portion_size * cost_per_unit
    
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
    name: str = Form(...),
    category_id: int = Form(None),
    sale_price: float = Form(...),
    description: str = Form(default=""),
    batch_portions_data: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    try:
        # Update dish
        dish.name = name
        dish.category_id = category_id if category_id else None
        dish.sale_price = sale_price
        dish.description = description
        
        # Update batch portions - remove existing and add new ones
        db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
        
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
        return RedirectResponse(url=f"/dishes/{dish_id}", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/dishes/{dish_id}/delete")
async def delete_dish(
    dish_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    try:
        # Delete related batch portions first
        db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
        db.delete(dish)
        db.commit()
        return RedirectResponse(url="/dishes", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Inventory routes
@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get current day
    today = date.today()
    current_day = db.query(InventoryDay).filter(InventoryDay.date == today, InventoryDay.finalized == False).first()
    
    # Get recent finalized days
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
        "current_day": current_day,
        "finalized_days": finalized_days,
        "today_date": today.isoformat()
    })

@app.post("/inventory/new_item")
async def create_inventory_item(
    name: str = Form(...),
    par_level: float = Form(...),
    batch_id: int = Form(None),
    category_id: int = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        item = InventoryItem(
            name=name,
            par_level=par_level,
            batch_id=batch_id if batch_id else None,
            category_id=category_id if category_id else None
        )
        db.add(item)
        db.commit()
        return RedirectResponse(url="/inventory", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/inventory/new_day")
async def create_inventory_day(
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        form_data = await request.form()
        inventory_date = datetime.strptime(form_data.get("date"), "%Y-%m-%d").date()
        
        # Check if day already exists
        existing_day = db.query(InventoryDay).filter(InventoryDay.date == inventory_date).first()
        if existing_day:
            return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=302)
        
        # Get selected employees
        employees_working = form_data.getlist("employees_working")
        employees_working_str = ",".join(employees_working) if employees_working else ""
        
        # Create inventory day
        inventory_day = InventoryDay(
            date=inventory_date,
            employees_working=employees_working_str,
            global_notes=form_data.get("global_notes", "")
        )
        db.add(inventory_day)
        db.flush()  # Get the day ID
        
        # Create inventory day items for all master items
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
    
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    tasks = db.query(Task).filter(Task.day_id == day_id).order_by(Task.id.desc()).all()
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
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot update finalized day")
    
    try:
        form_data = await request.form()
        
        # Update global notes
        inventory_day.global_notes = form_data.get("global_notes", "")
        
        # Update inventory quantities and generate tasks
        inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
        
        for item in inventory_day_items:
            quantity_key = f"item_{item.inventory_item.id}"
            override_create_key = f"override_create_{item.inventory_item.id}"
            override_no_task_key = f"override_no_task_{item.inventory_item.id}"
            
            if quantity_key in form_data:
                item.quantity = float(form_data[quantity_key])
                item.override_create_task = bool(form_data.get(override_create_key))
                item.override_no_task = bool(form_data.get(override_no_task_key))
                
                # Generate task if needed
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
                        task_description = f"Prep {item.inventory_item.name}"
                        if item.inventory_item.batch:
                            task_description += f" ({item.inventory_item.batch.recipe.name})"
                        
                        task = Task(
                            day_id=day_id,
                            inventory_item_id=item.inventory_item.id,
                            batch_id=item.inventory_item.batch_id,
                            description=task_description,
                            auto_generated=True
                        )
                        db.add(task)
        
        db.commit()
        return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/inventory/day/{day_id}/finalize")
async def finalize_inventory_day(
    day_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    try:
        inventory_day.finalized = True
        db.commit()
        return RedirectResponse(url=f"/inventory/reports/{day_id}", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Task management
@app.post("/inventory/day/{day_id}/tasks/new")
async def create_task(
    day_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    try:
        form_data = await request.form()
        assigned_to_ids = form_data.getlist("assigned_to_ids")
        inventory_item_id = int(form_data.get("inventory_item_id")) if form_data.get("inventory_item_id") else None
        description = form_data.get("description")
        
        # Get batch_id from inventory item if linked
        batch_id = None
        if inventory_item_id:
            inventory_item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
            if inventory_item and inventory_item.batch_id:
                batch_id = inventory_item.batch_id
        
        if assigned_to_ids:
            # Create separate task for each assigned employee
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
    
    try:
        task.assigned_to_id = assigned_to_id
        db.commit()
        return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
    
    try:
        task.started_at = datetime.utcnow()
        task.is_paused = False
        db.commit()
        return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
    
    try:
        task.paused_at = datetime.utcnow()
        task.is_paused = True
        db.commit()
        return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
    
    try:
        if task.paused_at and task.started_at:
            pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
            task.total_pause_time += int(pause_duration)
        
        task.paused_at = None
        task.is_paused = False
        db.commit()
        return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
    
    try:
        task.finished_at = datetime.utcnow()
        task.is_paused = False
        db.commit()
        return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/inventory/day/{day_id}/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(
    day_id: int,
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    notes: str = Form(...),
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    try:
        task.notes = notes
        db.commit()
        return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Inventory item management
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
async def update_inventory_item(
    item_id: int,
    name: str = Form(...),
    par_level: float = Form(...),
    batch_id: int = Form(None),
    category_id: int = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    try:
        item.name = name
        item.par_level = par_level
        item.batch_id = batch_id if batch_id else None
        item.category_id = category_id if category_id else None
        
        db.commit()
        return RedirectResponse(url="/inventory", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/inventory/items/{item_id}/delete")
async def delete_inventory_item(
    item_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    try:
        db.delete(item)
        db.commit()
        return RedirectResponse(url="/inventory", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Inventory reports
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
async def create_utility_cost(
    name: str = Form(...),
    monthly_cost: float = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/utilities/{utility_id}/delete")
async def delete_utility_cost(
    utility_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
    if not utility:
        raise HTTPException(status_code=404, detail="Utility not found")
    
    try:
        db.delete(utility)
        db.commit()
        return RedirectResponse(url="/utilities", status_code=302)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# API endpoints for AJAX requests
@app.get("/api/ingredients/all")
async def api_get_all_ingredients(db: Session = Depends(get_db)):
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
async def api_get_recipe_usage_units(recipe_id: int, db: Session = Depends(get_db)):
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
    usage_unit_ids = set()
    
    for ri in recipe_ingredients:
        for iu in ri.ingredient.usage_units:
            usage_unit_ids.add(iu.usage_unit_id)
    
    usage_units = db.query(UsageUnit).filter(UsageUnit.id.in_(usage_unit_ids)).all()
    return [{"id": unit.id, "name": unit.name} for unit in usage_units]

@app.get("/api/batches/all")
async def api_get_all_batches(db: Session = Depends(get_db)):
    batches = db.query(Batch).all()
    result = []
    
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        recipe_cost = sum(ri.cost for ri in recipe_ingredients)
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

@app.get("/api/batches/search")
async def api_search_batches(q: str, db: Session = Depends(get_db)):
    batches = db.query(Batch).join(Recipe).filter(Recipe.name.ilike(f"%{q}%")).all()
    result = []
    
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        recipe_cost = sum(ri.cost for ri in recipe_ingredients)
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
async def api_get_batch_portion_units(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get recipe usage units
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    usage_unit_ids = set()
    
    for ri in recipe_ingredients:
        for iu in ri.ingredient.usage_units:
            usage_unit_ids.add(iu.usage_unit_id)
    
    # Always include the batch yield unit
    usage_unit_ids.add(batch.yield_unit_id)
    
    usage_units = db.query(UsageUnit).filter(UsageUnit.id.in_(usage_unit_ids)).all()
    return [{"id": unit.id, "name": unit.name} for unit in usage_units]

@app.get("/api/batches/{batch_id}/cost_per_unit/{unit_id}")
async def api_get_batch_cost_per_unit(batch_id: int, unit_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Calculate total batch cost
    recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    total_cost = recipe_cost + batch.estimated_labor_cost
    
    # If requesting yield unit, return direct cost per yield unit
    if unit_id == batch.yield_unit_id:
        cost_per_unit = total_cost / batch.yield_amount if batch.yield_amount > 0 else 0
        return {"expected_cost_per_unit": cost_per_unit}
    
    # For other units, we need conversion logic (simplified for now)
    # In a real implementation, you'd need proper unit conversion
    cost_per_yield_unit = total_cost / batch.yield_amount if batch.yield_amount > 0 else 0
    return {"expected_cost_per_unit": cost_per_yield_unit}

@app.get("/api/batches/{batch_id}/labor_stats")
async def api_get_batch_labor_stats(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get completed tasks for this batch
    completed_tasks = db.query(Task).filter(
        Task.batch_id == batch_id,
        Task.finished_at.isnot(None)
    ).order_by(Task.finished_at.desc()).all()
    
    if not completed_tasks:
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
    
    # Calculate statistics
    most_recent = completed_tasks[0]
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    
    week_tasks = [t for t in completed_tasks if t.finished_at >= one_week_ago]
    month_tasks = [t for t in completed_tasks if t.finished_at >= one_month_ago]
    
    return {
        "task_count": len(completed_tasks),
        "most_recent_cost": most_recent.labor_cost,
        "most_recent_date": most_recent.finished_at.strftime("%Y-%m-%d"),
        "average_week": sum(t.labor_cost for t in week_tasks) / len(week_tasks) if week_tasks else 0,
        "average_month": sum(t.labor_cost for t in month_tasks) / len(month_tasks) if month_tasks else 0,
        "average_all_time": sum(t.labor_cost for t in completed_tasks) / len(completed_tasks),
        "week_task_count": len(week_tasks),
        "month_task_count": len(month_tasks)
    }

@app.get("/api/vendor_units/{vendor_unit_id}/conversions")
async def api_get_vendor_unit_conversions(vendor_unit_id: int, db: Session = Depends(get_db)):
    conversions = db.query(VendorUnitConversion).filter(VendorUnitConversion.vendor_unit_id == vendor_unit_id).all()
    result = {}
    for conversion in conversions:
        result[conversion.usage_unit_id] = conversion.conversion_factor
    return result

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

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 500,
        "detail": "Internal server error"
    }, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)