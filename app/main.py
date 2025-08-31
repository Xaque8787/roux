from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, date, timedelta
from typing import Optional, List
import json

from .database import engine, get_db
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, Vendor, VendorUnit, UsageUnit, IngredientUsageUnit, VendorUnitConversion
from .auth import hash_password, verify_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Helper function to check if setup is needed
def needs_setup(db: Session):
    return db.query(User).filter(User.role == "admin").first() is None

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
        ("Prep Items", "batch"),
        ("Sauces", "batch"),
        ("Appetizers", "dish"),
        ("Entrees", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Proteins", "inventory"),
        ("Vegetables", "inventory"),
        ("Dairy", "inventory"),
        ("Dry Goods", "inventory"),
        ("Cleaning", "inventory")
    ]
    
    for name, cat_type in default_categories:
        existing = db.query(Category).filter(Category.name == name, Category.type == cat_type).first()
        if not existing:
            category = Category(name=name, type=cat_type)
            db.add(category)
    
    db.commit()

# Helper function to create default units
def create_default_units(db: Session):
    # Vendor units (what we buy in)
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
        ("each", "Each/Individual")
    ]
    
    for name, description in vendor_units:
        existing = db.query(VendorUnit).filter(VendorUnit.name == name).first()
        if not existing:
            unit = VendorUnit(name=name, description=description)
            db.add(unit)
    
    # Usage units (what we use in recipes)
    usage_units = [
        "lb", "oz", "cup", "tbsp", "tsp", "gal", "qt", "pt", "fl oz",
        "kg", "g", "L", "mL", "each", "clove", "bunch", "head", "can",
        "jar", "bottle", "bag", "box", "package", "slice", "piece"
    ]
    
    for name in usage_units:
        existing = db.query(UsageUnit).filter(UsageUnit.name == name).first()
        if not existing:
            unit = UsageUnit(name=name)
            db.add(unit)
    
    db.commit()
    
    # Create common vendor unit to usage unit conversions
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
        ("pt", "fl oz", 16.0),
        ("kg", "kg", 1.0),
        ("kg", "g", 1000.0),
        ("g", "g", 1.0),
        ("L", "L", 1.0),
        ("L", "mL", 1000.0),
        ("mL", "mL", 1.0),
        ("each", "each", 1.0)
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
async def setup_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not needs_setup(db):
        return RedirectResponse(url="/", status_code=302)
    
    hashed_password = hash_password(password)
    admin_user = User(
        username=username,
        hashed_password=hashed_password,
        full_name=username,
        role="admin",
        is_admin=True,
        hourly_wage=20.0
    )
    
    db.add(admin_user)
    db.commit()
    
    # Create default categories and units
    create_default_categories(db)
    create_default_units(db)
    
    return RedirectResponse(url="/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse(url="/setup", status_code=302)
    
    error = request.query_params.get("error")
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
        return RedirectResponse(url="/login?error=Invalid credentials", status_code=302)
    
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
    role: str = Form("user"),
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
        hashed_password=hashed_password,
        full_name=full_name,
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
async def employee_edit(
    request: Request,
    employee_id: int,
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(""),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form("user"),
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
        return templates.TemplateResponse("employee_edit.html", {
            "request": request,
            "current_user": current_user,
            "employee": employee,
            "error": "Username already exists"
        })
    
    employee.full_name = full_name
    employee.username = username
    if password:  # Only update password if provided
        employee.hashed_password = hash_password(password)
    employee.hourly_wage = hourly_wage
    employee.work_schedule = work_schedule
    employee.role = role
    employee.is_admin = (role == "admin")
    employee.is_active = (is_active == "on")
    
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
        return RedirectResponse(url="/employees", status_code=302)
    
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
        joinedload(Ingredient.vendor_unit)
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
    category_id: Optional[str] = Form(None),
    vendor_id: Optional[str] = Form(None),
    vendor_unit_id: Optional[str] = Form(None),
    purchase_type: str = Form("single"),
    purchase_unit_name: str = Form(...),
    purchase_weight_volume: float = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: Optional[str] = Form(None),
    items_per_case: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Convert string IDs to integers or None
    category_id_int = int(category_id) if category_id else None
    vendor_id_int = int(vendor_id) if vendor_id else None
    vendor_unit_id_int = int(vendor_unit_id) if vendor_unit_id else None
    
    ingredient = Ingredient(
        name=name,
        category_id=category_id_int,
        vendor_id=vendor_id_int,
        vendor_unit_id=vendor_unit_id_int,
        purchase_type=purchase_type,
        purchase_unit_name=purchase_unit_name,
        purchase_weight_volume=purchase_weight_volume,
        purchase_total_cost=purchase_total_cost,
        breakable_case=(breakable_case == "on"),
        items_per_case=items_per_case
    )
    
    db.add(ingredient)
    db.flush()  # Get the ID
    
    # Process usage unit conversions
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
        "ingredient": ingredient,
        "usage_units": ingredient.usage_units
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
        joinedload(Ingredient.usage_units)
    ).filter(Ingredient.id == ingredient_id).first()
    
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    vendor_units = db.query(VendorUnit).all()
    usage_units = db.query(UsageUnit).all()
    
    # Create a dictionary of existing conversions for easy lookup
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
    category_id: Optional[str] = Form(None),
    vendor_id: Optional[str] = Form(None),
    vendor_unit_id: Optional[str] = Form(None),
    purchase_type: str = Form("single"),
    purchase_unit_name: str = Form(...),
    purchase_weight_volume: float = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: Optional[str] = Form(None),
    items_per_case: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    # Convert string IDs to integers or None
    category_id_int = int(category_id) if category_id else None
    vendor_id_int = int(vendor_id) if vendor_id else None
    vendor_unit_id_int = int(vendor_unit_id) if vendor_unit_id else None
    
    # Update ingredient
    ingredient.name = name
    ingredient.category_id = category_id_int
    ingredient.vendor_id = vendor_id_int
    ingredient.vendor_unit_id = vendor_unit_id_int
    ingredient.purchase_type = purchase_type
    ingredient.purchase_unit_name = purchase_unit_name
    ingredient.purchase_weight_volume = purchase_weight_volume
    ingredient.purchase_total_cost = purchase_total_cost
    ingredient.breakable_case = (breakable_case == "on")
    ingredient.items_per_case = items_per_case
    
    # Remove existing usage unit conversions
    db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).delete()
    
    # Process new usage unit conversions
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
    
    # Delete related usage units first
    db.query(IngredientUsageUnit).filter(IngredientUsageUnit.ingredient_id == ingredient_id).delete()
    
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
    category_id: Optional[str] = Form(None),
    ingredients_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    category_id_int = int(category_id) if category_id else None
    
    recipe = Recipe(
        name=name,
        instructions=instructions,
        category_id=category_id_int
    )
    
    db.add(recipe)
    db.flush()  # Get the ID
    
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
async def recipe_edit(
    request: Request,
    recipe_id: int,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: Optional[str] = Form(None),
    ingredients_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    category_id_int = int(category_id) if category_id else None
    
    # Update recipe
    recipe.name = name
    recipe.instructions = instructions
    recipe.category_id = category_id_int
    
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
                quantity=ing_data['quantity']
            )
            db.add(recipe_ingredient)
    except (json.JSONDecodeError, KeyError):
        pass  # Skip if invalid data
    
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
    
    # Delete related ingredients first
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
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
    request: Request,
    recipe_id: int = Form(...),
    yield_amount: float = Form(...),
    yield_unit_id: int = Form(...),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(16.75),
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
        yield_amount=yield_amount,
        yield_unit_id=yield_unit_id,
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
    
    # Get recipe ingredients
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.category),
        joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.usage_units),
        joinedload(RecipeIngredient.usage_unit)
    ).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
    
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
async def batch_edit(
    request: Request,
    batch_id: int,
    recipe_id: int = Form(...),
    yield_amount: float = Form(...),
    yield_unit_id: int = Form(...),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(16.75),
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
    batch.yield_amount = yield_amount
    batch.yield_unit_id = yield_unit_id
    batch.estimated_labor_minutes = estimated_labor_minutes
    batch.hourly_labor_rate = hourly_labor_rate
    batch.can_be_scaled = (can_be_scaled == "on")
    batch.scale_double = (scale_double == "on")
    batch.scale_half = (scale_half == "on")
    batch.scale_quarter = (scale_quarter == "on")
    batch.scale_eighth = (scale_eighth == "on")
    batch.scale_sixteenth = (scale_sixteenth == "on")
    
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
    category_id: Optional[str] = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    category_id_int = int(category_id) if category_id else None
    
    dish = Dish(
        name=name,
        category_id=category_id_int,
        sale_price=sale_price,
        description=description
    )
    
    db.add(dish)
    db.flush()  # Get the ID
    
    # Process batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            dish_batch_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data['batch_id'],
                portion_size=portion_data['portion_size']
            )
            db.add(dish_batch_portion)
    except (json.JSONDecodeError, KeyError):
        pass  # Skip if invalid data
    
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
        joinedload(DishBatchPortion.batch).joinedload(Batch.yield_unit)
    ).filter(DishBatchPortion.dish_id == dish_id).all()
    
    total_cost = sum(portion.cost for portion in dish_batch_portions)
    profit = dish.sale_price - total_cost
    profit_margin = (profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    return templates.TemplateResponse("dish_detail.html", {
        "request": request,
        "current_user": current_user,
        "dish": dish,
        "dish_batch_portions": dish_batch_portions,
        "total_cost": total_cost,
        "profit": profit,
        "profit_margin": profit_margin
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
        joinedload(DishBatchPortion.batch).joinedload(Batch.yield_unit)
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
async def dish_edit(
    request: Request,
    dish_id: int,
    name: str = Form(...),
    category_id: Optional[str] = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form("[]"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    category_id_int = int(category_id) if category_id else None
    
    # Update dish
    dish.name = name
    dish.category_id = category_id_int
    dish.sale_price = sale_price
    dish.description = description
    
    # Remove existing batch portions
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Add new batch portions
    try:
        batch_portions = json.loads(batch_portions_data)
        for portion_data in batch_portions:
            dish_batch_portion = DishBatchPortion(
                dish_id=dish.id,
                batch_id=portion_data['batch_id'],
                portion_size=portion_data['portion_size']
            )
            db.add(dish_batch_portion)
    except (json.JSONDecodeError, KeyError):
        pass  # Skip if invalid data
    
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
    
    # Delete related batch portions first
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    db.delete(dish)
    db.commit()
    
    return RedirectResponse(url="/dishes", status_code=302)

# Inventory routes
@app.get("/inventory", response_class=HTMLResponse)
async def inventory_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).options(
        joinedload(InventoryItem.category),
        joinedload(InventoryItem.batch).joinedload(Batch.recipe)
    ).all()
    
    batches = db.query(Batch).options(
        joinedload(Batch.recipe),
        joinedload(Batch.yield_unit)
    ).all()
    
    categories = db.query(Category).filter(Category.type == "inventory").all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get current day if exists
    today = date.today()
    current_day = db.query(InventoryDay).filter(InventoryDay.date == today).first()
    
    # Get recent finalized days (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    finalized_days = db.query(InventoryDay).filter(
        InventoryDay.date >= thirty_days_ago,
        InventoryDay.finalized == True
    ).order_by(desc(InventoryDay.date)).limit(10).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "current_user": current_user,
        "inventory_items": inventory_items,
        "batches": batches,
        "categories": categories,
        "employees": employees,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "today_date": today.isoformat()
    })

@app.post("/inventory/new_item")
async def create_inventory_item(
    name: str = Form(...),
    par_level: float = Form(...),
    batch_id: Optional[str] = Form(None),
    category_id: Optional[str] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    # Convert string IDs to integers or None
    batch_id_int = int(batch_id) if batch_id else None
    category_id_int = int(category_id) if category_id else None
    
    inventory_item = InventoryItem(
        name=name,
        par_level=par_level,
        batch_id=batch_id_int,
        category_id=category_id_int
    )
    
    db.add(inventory_item)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

@app.post("/inventory/new_day")
async def create_inventory_day(
    request: Request,
    date_str: str = Form(..., alias="date"),
    employees_working: List[str] = Form([]),
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    day_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == day_date).first()
    if existing_day:
        return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=302)
    
    # Create new inventory day
    inventory_day = InventoryDay(
        date=day_date,
        employees_working=",".join(employees_working),
        global_notes=global_notes
    )
    
    db.add(inventory_day)
    db.flush()  # Get the ID
    
    # Create inventory day items for all master inventory items
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
async def inventory_day_detail(
    request: Request,
    day_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item).joinedload(InventoryItem.batch).joinedload(Batch.recipe)
    ).filter(InventoryDayItem.day_id == day_id).all()
    
    tasks = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.inventory_item),
        joinedload(Task.batch).joinedload(Batch.recipe)
    ).filter(Task.day_id == day_id).all()
    
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
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot update finalized day")
    
    # Update global notes
    inventory_day.global_notes = global_notes
    
    # Get form data
    form_data = await request.form()
    
    # Update inventory quantities and overrides
    inventory_day_items = db.query(InventoryDayItem).options(
        joinedload(InventoryDayItem.inventory_item)
    ).filter(InventoryDayItem.day_id == day_id).all()
    
    for item in inventory_day_items:
        quantity_key = f"item_{item.inventory_item.id}"
        override_create_key = f"override_create_{item.inventory_item.id}"
        override_no_task_key = f"override_no_task_{item.inventory_item.id}"
        
        if quantity_key in form_data:
            item.quantity = float(form_data[quantity_key])
        
        item.override_create_task = (override_create_key in form_data)
        item.override_no_task = (override_no_task_key in form_data)
    
    # Delete existing auto-generated tasks
    db.query(Task).filter(Task.day_id == day_id, Task.auto_generated == True).delete()
    
    # Generate new tasks based on updated quantities and overrides
    for item in inventory_day_items:
        should_create_task = False
        
        if item.override_create_task:
            # Force create task regardless of par level
            should_create_task = True
        elif not item.override_no_task:
            # Create task if below par and not overridden to skip
            should_create_task = item.quantity <= item.inventory_item.par_level
        
        if should_create_task:
            task_description = f"Prep {item.inventory_item.name} (Below Par: {item.quantity}/{item.inventory_item.par_level})"
            
            # Create task with inherited batch_id from inventory item
            task = Task(
                day_id=day_id,
                inventory_item_id=item.inventory_item.id,
                batch_id=item.inventory_item.batch_id,  # Inherit batch from inventory item
                description=task_description,
                auto_generated=True
            )
            db.add(task)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/new")
async def create_manual_task(
    request: Request,
    day_id: int,
    assigned_to_ids: List[str] = Form([]),
    inventory_item_id: Optional[str] = Form(None),
    description: str = Form(...),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot add tasks to finalized day")
    
    # Get batch_id from inventory item if linked
    batch_id = None
    inventory_item_id_int = int(inventory_item_id) if inventory_item_id else None
    if inventory_item_id_int:
        inventory_item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id_int).first()
        if inventory_item:
            batch_id = inventory_item.batch_id
    
    # Create tasks for each assigned employee or one unassigned task
    if assigned_to_ids:
        for assigned_to_id in assigned_to_ids:
            task = Task(
                day_id=day_id,
                assigned_to_id=int(assigned_to_id),
                inventory_item_id=inventory_item_id_int,
                batch_id=batch_id,  # Inherit batch from inventory item
                description=description,
                auto_generated=False
            )
            db.add(task)
    else:
        # Create unassigned task
        task = Task(
            day_id=day_id,
            inventory_item_id=inventory_item_id_int,
            batch_id=batch_id,  # Inherit batch from inventory item
            description=description,
            auto_generated=False
        )
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
    
    task.paused_at = datetime.utcnow()
    task.is_paused = True
    
    # Calculate pause time if there was a previous pause
    if task.started_at and task.paused_at:
        # Add current session time to total pause time
        # This is a simplified approach - in production you'd want more sophisticated pause tracking
        pass
    
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
    
    if task.paused_at and task.started_at:
        # Add pause duration to total pause time
        pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
        task.total_pause_time += int(pause_duration)
    
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
    
    # If task was paused, add final pause duration
    if task.paused_at and task.started_at:
        pause_duration = (task.finished_at - task.paused_at).total_seconds()
        task.total_pause_time += int(pause_duration)
    
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.get("/inventory/day/{day_id}/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(
    request: Request,
    day_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).options(
        joinedload(Task.assigned_to),
        joinedload(Task.inventory_item),
        joinedload(Task.batch).joinedload(Batch.recipe)
    ).filter(Task.id == task_id, Task.day_id == day_id).first()
    
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
    notes: str = Form(""),
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
    
    inventory_day.finalized = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/reports/{day_id}", status_code=302)

@app.get("/inventory/reports/{day_id}", response_class=HTMLResponse)
async def inventory_report(
    request: Request,
    day_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
async def inventory_item_edit_form(
    request: Request,
    item_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).options(
        joinedload(InventoryItem.category),
        joinedload(InventoryItem.batch).joinedload(Batch.recipe)
    ).filter(InventoryItem.id == item_id).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    batches = db.query(Batch).options(
        joinedload(Batch.recipe),
        joinedload(Batch.yield_unit)
    ).all()
    
    categories = db.query(Category).filter(Category.type == "inventory").all()
    
    return templates.TemplateResponse("inventory_item_edit.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "batches": batches,
        "categories": categories
    })

@app.post("/inventory/items/{item_id}/edit")
async def inventory_item_edit(
    item_id: int,
    name: str = Form(...),
    par_level: float = Form(...),
    batch_id: Optional[str] = Form(None),
    category_id: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    # Convert string IDs to integers or None
    batch_id_int = int(batch_id) if batch_id else None
    category_id_int = int(category_id) if category_id else None
    
    item.name = name
    item.par_level = par_level
    item.batch_id = batch_id_int
    item.category_id = category_id_int
    
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

# Utilities routes
@app.get("/utilities", response_class=HTMLResponse)
async def utilities_list(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
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
    # Check if utility with this name already exists
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
async def utility_delete(
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
async def get_all_ingredients(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).options(
        joinedload(Ingredient.category),
        joinedload(Ingredient.usage_units).joinedload(IngredientUsageUnit.usage_unit)
    ).all()
    
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

@app.get("/api/batches/search")
async def search_batches(
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batches = db.query(Batch).options(
        joinedload(Batch.recipe).joinedload(Recipe.category),
        joinedload(Batch.yield_unit)
    ).join(Recipe).filter(
        Recipe.name.ilike(f"%{q}%")
    ).limit(10).all()
    
    result = []
    for batch in batches:
        # Calculate cost per unit
        recipe_ingredients = db.query(RecipeIngredient).options(
            joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.usage_units)
        ).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount > 0 else 0
        
        result.append({
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit.name if batch.yield_unit else "",
            "cost_per_unit": cost_per_unit,
            "category": batch.recipe.category.name if batch.recipe.category else None
        })
    
    return result

@app.get("/api/recipes/{recipe_id}/usage_units")
async def get_recipe_usage_units(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get all usage units used in this recipe
    recipe_ingredients = db.query(RecipeIngredient).options(
        joinedload(RecipeIngredient.usage_unit)
    ).filter(RecipeIngredient.recipe_id == recipe_id).all()
    
    usage_units = []
    seen_units = set()
    
    for ri in recipe_ingredients:
        if ri.usage_unit_id not in seen_units:
            usage_units.append({
                "id": ri.usage_unit.id,
                "name": ri.usage_unit.name
            })
            seen_units.add(ri.usage_unit_id)
    
    return usage_units

@app.get("/api/vendor_units/{vendor_unit_id}/conversions")
async def get_vendor_unit_conversions(
    vendor_unit_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conversions = db.query(VendorUnitConversion).filter(
        VendorUnitConversion.vendor_unit_id == vendor_unit_id
    ).all()
    
    result = {}
    for conversion in conversions:
        result[conversion.usage_unit_id] = conversion.conversion_factor
    
    return result

@app.get("/api/batches/{batch_id}/labor_stats")
async def get_batch_labor_stats(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get all completed tasks for this batch
    completed_tasks = db.query(Task).options(
        joinedload(Task.assigned_to)
    ).filter(
        Task.batch_id == batch_id,
        Task.finished_at.isnot(None)
    ).order_by(desc(Task.finished_at)).all()
    
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
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Most recent task
    most_recent = completed_tasks[0]
    
    # Filter tasks by time periods
    week_tasks = [t for t in completed_tasks if t.finished_at >= week_ago]
    month_tasks = [t for t in completed_tasks if t.finished_at >= month_ago]
    
    # Calculate averages
    def avg_cost(tasks):
        if not tasks:
            return 0
        return sum(t.labor_cost for t in tasks) / len(tasks)
    
    return {
        "task_count": len(completed_tasks),
        "most_recent_cost": most_recent.labor_cost,
        "most_recent_date": most_recent.finished_at.strftime('%Y-%m-%d'),
        "average_week": avg_cost(week_tasks),
        "average_month": avg_cost(month_tasks),
        "average_all_time": avg_cost(completed_tasks),
        "week_task_count": len(week_tasks),
        "month_task_count": len(month_tasks)
    }

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": exc.status_code,
        "detail": exc.detail
    }, status_code=exc.status_code)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)