from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
import os
import json

from .database import SessionLocal, engine, Base
from .models import (
    User, Category, VendorUnit, ParUnitName, Vendor, Ingredient, Recipe, 
    RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, 
    InventoryDay, InventoryDayItem, Task, UtilityCost,
    WEIGHT_CONVERSIONS, VOLUME_CONVERSIONS, BAKING_MEASUREMENTS
)
from .auth import hash_password, verify_password, create_jwt, get_current_user

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def has_admin_user(db: Session):
    """Check if there's at least one admin user in the database"""
    admin_user = db.query(User).filter(User.role == "admin").first()
    return admin_user is not None

@app.get("/")
async def root(request: Request, db: Session = Depends(get_db)):
    if not has_admin_user(db):
        return RedirectResponse(url="/setup", status_code=302)
    return RedirectResponse(url="/home", status_code=302)

@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    if has_admin_user(db):
        return RedirectResponse(url="/home", status_code=302)
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_admin(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(None),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    print(f"Setup attempt - Username: {username}, Full name: {full_name}")
    
    if has_admin_user(db):
        return RedirectResponse(url="/home", status_code=302)
    
    # Validate input
    if not username or not password:
        return templates.TemplateResponse("setup.html", {
            "request": request,
            "error": "Username and password are required"
        })
    
    if len(password) < 4:
        return templates.TemplateResponse("setup.html", {
            "request": request,
            "error": "Password must be at least 4 characters long"
        })
    
    try:
        # Create admin user
        hashed_password = hash_password(password)
        admin_user = User(
            username=username,
            full_name=full_name or username,
            hashed_password=hashed_password,
            role="admin",
            is_admin=True,
            is_active=True,
            hourly_wage=20.0
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
            ("Prep Items", "recipe"),
            ("Sauces", "recipe"),
            ("Sides", "recipe"),
            ("General", "inventory")
        ]
        
        for name, cat_type in default_categories:
            existing_category = db.query(Category).filter(
                Category.name == name, 
                Category.type == cat_type
            ).first()
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
            ("cup", "Cup"),
            ("fl_oz", "Fluid Ounce"),
            ("l", "Liter"),
            ("ml", "Milliliter"),
            ("g", "Gram"),
            ("kg", "Kilogram"),
            ("each", "Each"),
            ("dozen", "Dozen"),
            ("case", "Case")
        ]
        
        for name, description in default_vendor_units:
            existing_unit = db.query(VendorUnit).filter(VendorUnit.name == name).first()
            if not existing_unit:
                vendor_unit = VendorUnit(name=name, description=description)
                db.add(vendor_unit)
        
        # Create default par unit names
        default_par_units = [
            "Tub",
            "Case",
            "Container",
            "Bag",
            "Box",
            "Bottle",
            "Can",
            "Package"
        ]
        
        for name in default_par_units:
            existing_par = db.query(ParUnitName).filter(ParUnitName.name == name).first()
            if not existing_par:
                par_unit = ParUnitName(name=name)
                db.add(par_unit)
        
        db.commit()
        print("Setup completed successfully, redirecting to login")
        return RedirectResponse(url="/login", status_code=302)
        
    except Exception as e:
        print(f"Setup error: {str(e)}")
        db.rollback()
        return templates.TemplateResponse("setup.html", {
            "request": request,
            "error": f"Setup failed: {str(e)}"
        })

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    print(f"Login attempt - Username: {username}")
    
    # Validate input
    if not username or not password:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Username and password are required"
        })
    
    # Find user
    user = db.query(User).filter(User.username == username).first()
    print(f"User found: {user is not None}")
    
    if not user:
        print("User not found in database")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
    print(f"User active: {user.is_active}")
    if not user.is_active:
        print("User account is inactive")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Account is inactive"
        })
    
    # Verify password
    print("Verifying password...")
    if not verify_password(password, user.hashed_password):
        print("Password verification failed")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
    print("Login successful, creating JWT...")
    
    # Create JWT token
    access_token_expires = timedelta(minutes=30)
    access_token = create_jwt(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    print("JWT cookie set, redirecting to /home")
    
    # Create response and set cookie
    response = RedirectResponse(url="/home", status_code=302)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response

@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Employee Management Routes
@app.get("/employees", response_class=HTMLResponse)
async def employees_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
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
        is_active=True
    )
    
    db.add(employee)
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)

@app.get("/employees/{employee_id}", response_class=HTMLResponse)
async def employee_detail(employee_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_detail.html", {
        "request": request,
        "current_user": current_user,
        "employee": employee
    })

@app.get("/employees/{employee_id}/edit", response_class=HTMLResponse)
async def employee_edit(employee_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
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
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(None),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form("user"),
    is_active: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Update employee fields
    employee.full_name = full_name
    employee.username = username
    employee.hourly_wage = hourly_wage
    employee.work_schedule = work_schedule
    employee.role = role
    employee.is_admin = (role == "admin")
    employee.is_active = is_active
    
    # Update password if provided
    if password:
        employee.hashed_password = hash_password(password)
    
    db.commit()
    return RedirectResponse(url=f"/employees/{employee_id}", status_code=302)

@app.get("/employees/{employee_id}/delete")
async def delete_employee(employee_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Don't allow deleting yourself
    if employee.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Deactivate instead of delete to preserve data integrity
    employee.is_active = False
    db.commit()
    return RedirectResponse(url="/employees", status_code=302)

# Ingredients Management Routes
@app.get("/ingredients", response_class=HTMLResponse)
async def ingredients_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def create_ingredient(
    request: Request,
    name: str = Form(...),
    usage_type: str = Form(...),
    category_id: int = Form(None),
    vendor_id: int = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    net_weight_volume_item: float = Form(...),
    net_unit: str = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: int = Form(None),
    net_weight_volume_case: float = Form(None),
    has_baking_conversion: bool = Form(False),
    baking_measurement_unit: str = Form(None),
    baking_weight_amount: float = Form(None),
    baking_weight_unit: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    ingredient = Ingredient(
        name=name,
        usage_type=usage_type,
        category_id=category_id if category_id else None,
        vendor_id=vendor_id if vendor_id else None,
        purchase_type=purchase_type,
        purchase_unit_name=purchase_unit_name,
        net_weight_volume_item=net_weight_volume_item,
        net_unit=net_unit,
        purchase_total_cost=purchase_total_cost,
        breakable_case=breakable_case,
        items_per_case=items_per_case,
        net_weight_volume_case=net_weight_volume_case,
        has_baking_conversion=has_baking_conversion,
        baking_measurement_unit=baking_measurement_unit if has_baking_conversion else None,
        baking_weight_amount=baking_weight_amount if has_baking_conversion else None,
        baking_weight_unit=baking_weight_unit if has_baking_conversion else None
    )
    
    db.add(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

@app.get("/ingredients/{ingredient_id}", response_class=HTMLResponse)
async def ingredient_detail(ingredient_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    return templates.TemplateResponse("ingredient_detail.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient
    })

@app.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
async def ingredient_edit(ingredient_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
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
        "vendor_units": vendor_units,
        "existing_conversions": {}  # Simplified for now
    })

@app.post("/ingredients/{ingredient_id}/edit")
async def update_ingredient(
    ingredient_id: int,
    request: Request,
    name: str = Form(...),
    usage_type: str = Form(...),
    category_id: int = Form(None),
    vendor_id: int = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    net_weight_volume_item: float = Form(...),
    net_unit: str = Form(...),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: int = Form(None),
    net_weight_volume_case: float = Form(None),
    has_baking_conversion: bool = Form(False),
    baking_measurement_unit: str = Form(None),
    baking_weight_amount: float = Form(None),
    baking_weight_unit: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    # Update ingredient fields
    ingredient.name = name
    ingredient.usage_type = usage_type
    ingredient.category_id = category_id if category_id else None
    ingredient.vendor_id = vendor_id if vendor_id else None
    ingredient.purchase_type = purchase_type
    ingredient.purchase_unit_name = purchase_unit_name
    ingredient.net_weight_volume_item = net_weight_volume_item
    ingredient.net_unit = net_unit
    ingredient.purchase_total_cost = purchase_total_cost
    ingredient.breakable_case = breakable_case
    ingredient.items_per_case = items_per_case
    ingredient.net_weight_volume_case = net_weight_volume_case
    ingredient.has_baking_conversion = has_baking_conversion
    ingredient.baking_measurement_unit = baking_measurement_unit if has_baking_conversion else None
    ingredient.baking_weight_amount = baking_weight_amount if has_baking_conversion else None
    ingredient.baking_weight_unit = baking_weight_unit if has_baking_conversion else None
    
    db.commit()
    return RedirectResponse(url=f"/ingredients/{ingredient_id}", status_code=302)

@app.get("/ingredients/{ingredient_id}/delete")
async def delete_ingredient(ingredient_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    db.delete(ingredient)
    db.commit()
    return RedirectResponse(url="/ingredients", status_code=302)

# Recipes Management Routes
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
    request: Request,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: int = Form(None),
    ingredients_data: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    try:
        ingredients = json.loads(ingredients_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid ingredients data")
    
    recipe = Recipe(
        name=name,
        instructions=instructions if instructions else None,
        category_id=category_id if category_id else None
    )
    
    db.add(recipe)
    db.flush()  # Get the recipe ID
    
    # Add recipe ingredients
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
async def recipe_detail(recipe_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def recipe_edit(recipe_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
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
async def update_recipe(
    recipe_id: int,
    request: Request,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: int = Form(None),
    ingredients_data: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    try:
        ingredients = json.loads(ingredients_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid ingredients data")
    
    # Update recipe fields
    recipe.name = name
    recipe.instructions = instructions if instructions else None
    recipe.category_id = category_id if category_id else None
    
    # Delete existing recipe ingredients
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
    # Add new recipe ingredients
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
async def delete_recipe(recipe_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # Delete recipe ingredients first
    db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
    
    # Delete recipe
    db.delete(recipe)
    db.commit()
    return RedirectResponse(url="/recipes", status_code=302)

# Batches Management Routes
@app.get("/batches", response_class=HTMLResponse)
async def batches_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batches = db.query(Batch).all()
    recipes = db.query(Recipe).all()
    
    return templates.TemplateResponse("batches.html", {
        "request": request,
        "current_user": current_user,
        "batches": batches,
        "recipes": recipes
    })

@app.post("/batches/new")
async def create_batch(
    request: Request,
    recipe_id: int = Form(...),
    variable_yield: bool = Form(False),
    yield_amount: float = Form(None),
    yield_unit: str = Form(None),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(...),
    can_be_scaled: bool = Form(False),
    scale_double: bool = Form(False),
    scale_half: bool = Form(False),
    scale_quarter: bool = Form(False),
    scale_eighth: bool = Form(False),
    scale_sixteenth: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
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
async def batch_edit(batch_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
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
async def update_batch(
    batch_id: int,
    request: Request,
    recipe_id: int = Form(...),
    variable_yield: bool = Form(False),
    yield_amount: float = Form(None),
    yield_unit: str = Form(None),
    estimated_labor_minutes: int = Form(...),
    hourly_labor_rate: float = Form(...),
    can_be_scaled: bool = Form(False),
    scale_double: bool = Form(False),
    scale_half: bool = Form(False),
    scale_quarter: bool = Form(False),
    scale_eighth: bool = Form(False),
    scale_sixteenth: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Update batch fields
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
async def delete_batch(batch_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    db.delete(batch)
    db.commit()
    return RedirectResponse(url="/batches", status_code=302)

# Dishes Management Routes
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
    request: Request,
    name: str = Form(...),
    category_id: int = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    try:
        batch_portions = json.loads(batch_portions_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid batch portions data")
    
    dish = Dish(
        name=name,
        category_id=category_id if category_id else None,
        sale_price=sale_price,
        description=description if description else None
    )
    
    db.add(dish)
    db.flush()  # Get the dish ID
    
    # Add dish batch portions
    for portion_data in batch_portions:
        dish_portion = DishBatchPortion(
            dish_id=dish.id,
            batch_id=portion_data['batch_id'],
            portion_size=portion_data['portion_size'],
            portion_unit=portion_data['portion_unit_name']
        )
        db.add(dish_portion)
    
    db.commit()
    return RedirectResponse(url="/dishes", status_code=302)

@app.get("/dishes/{dish_id}", response_class=HTMLResponse)
async def dish_detail(dish_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    
    # Calculate profits
    expected_profit = dish.sale_price - expected_total_cost
    actual_profit = dish.sale_price - actual_total_cost
    actual_profit_week = dish.sale_price - actual_total_cost_week
    actual_profit_month = dish.sale_price - actual_total_cost_month
    actual_profit_all_time = dish.sale_price - actual_total_cost_all_time
    
    # Calculate profit margins
    expected_profit_margin = (expected_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    actual_profit_margin = (actual_profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    actual_profit_margin_week = (actual_profit_week / dish.sale_price * 100) if dish.sale_price > 0 else 0
    actual_profit_margin_month = (actual_profit_month / dish.sale_price * 100) if dish.sale_price > 0 else 0
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
        "actual_profit": actual_profit,
        "actual_profit_week": actual_profit_week,
        "actual_profit_month": actual_profit_month,
        "actual_profit_all_time": actual_profit_all_time,
        "expected_profit_margin": expected_profit_margin,
        "actual_profit_margin": actual_profit_margin,
        "actual_profit_margin_week": actual_profit_margin_week,
        "actual_profit_margin_month": actual_profit_margin_month,
        "actual_profit_margin_all_time": actual_profit_margin_all_time
    })

@app.get("/dishes/{dish_id}/edit", response_class=HTMLResponse)
async def dish_edit(dish_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
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
async def update_dish(
    dish_id: int,
    request: Request,
    name: str = Form(...),
    category_id: int = Form(None),
    sale_price: float = Form(...),
    description: str = Form(""),
    batch_portions_data: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    try:
        batch_portions = json.loads(batch_portions_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid batch portions data")
    
    # Update dish fields
    dish.name = name
    dish.category_id = category_id if category_id else None
    dish.sale_price = sale_price
    dish.description = description if description else None
    
    # Delete existing dish batch portions
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Add new dish batch portions
    for portion_data in batch_portions:
        dish_portion = DishBatchPortion(
            dish_id=dish.id,
            batch_id=portion_data['batch_id'],
            portion_size=portion_data['portion_size'],
            portion_unit=portion_data['portion_unit_name']
        )
        db.add(dish_portion)
    
    db.commit()
    return RedirectResponse(url=f"/dishes/{dish_id}", status_code=302)

@app.get("/dishes/{dish_id}/delete")
async def delete_dish(dish_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    # Delete dish batch portions first
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    # Delete dish
    db.delete(dish)
    db.commit()
    return RedirectResponse(url="/dishes", status_code=302)

# Inventory Management Routes
@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_items = db.query(InventoryItem).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    batches = db.query(Batch).all()
    par_unit_names = db.query(ParUnitName).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Get current day if exists
    today = date.today()
    current_day = db.query(InventoryDay).filter(
        InventoryDay.date == today,
        InventoryDay.finalized == False
    ).first()
    
    # Get recent finalized days
    finalized_days = db.query(InventoryDay).filter(
        InventoryDay.finalized == True,
        InventoryDay.date >= today - timedelta(days=30)
    ).order_by(InventoryDay.date.desc()).limit(10).all()
    
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
        "today_date": today.isoformat()
    })

@app.post("/inventory/new_item")
async def create_inventory_item(
    request: Request,
    name: str = Form(...),
    par_unit_name_id: int = Form(None),
    par_level: float = Form(...),
    batch_id: int = Form(None),
    par_unit_equals_type: str = Form(None),
    par_unit_equals_amount: float = Form(None),
    par_unit_equals_unit: str = Form(None),
    category_id: int = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
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
    request: Request,
    date: str = Form(...),
    employees_working: list = Form([]),
    global_notes: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    # Parse date
    try:
        inventory_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Check if day already exists
    existing_day = db.query(InventoryDay).filter(InventoryDay.date == inventory_date).first()
    if existing_day:
        return RedirectResponse(url=f"/inventory/day/{existing_day.id}", status_code=302)
    
    # Create new inventory day
    inventory_day = InventoryDay(
        date=inventory_date,
        employees_working=",".join(map(str, employees_working)) if employees_working else "",
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
            quantity=0.0
        )
        db.add(day_item)
    
    db.commit()
    return RedirectResponse(url=f"/inventory/day/{inventory_day.id}", status_code=302)

@app.get("/inventory/items/{item_id}/edit", response_class=HTMLResponse)
async def inventory_item_edit(item_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
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
    name: str = Form(...),
    par_level: float = Form(...),
    batch_id: int = Form(None),
    category_id: int = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    # Update item fields
    item.name = name
    item.par_level = par_level
    item.batch_id = batch_id if batch_id else None
    item.category_id = category_id if category_id else None
    
    db.commit()
    return RedirectResponse(url="/inventory", status_code=302)

@app.get("/inventory/items/{item_id}/delete")
async def delete_inventory_item(item_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    db.delete(item)
    db.commit()
    return RedirectResponse(url="/inventory", status_code=302)

@app.get("/inventory/day/{day_id}", response_class=HTMLResponse)
async def inventory_day_detail(day_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate task summaries for completed tasks
    task_summaries = {}
    for task in tasks:
        if task.status == "completed" and task.inventory_item:
            summary = {}
            
            # Get the inventory day item for this task's inventory item
            day_item = None
            for item in inventory_day_items:
                if item.inventory_item_id == task.inventory_item.id:
                    day_item = item
                    break
            
            if day_item:
                summary['par_level'] = task.inventory_item.par_level
                summary['par_unit_name'] = task.inventory_item.par_unit_name.name if task.inventory_item.par_unit_name else 'units'
                summary['par_unit_equals_type'] = task.inventory_item.par_unit_equals_type
                summary['par_unit_equals'] = task.inventory_item.par_unit_equals_calculated
                
                # Determine par unit equals unit
                if task.inventory_item.par_unit_equals_type == 'auto' and task.inventory_item.batch:
                    summary['par_unit_equals_unit'] = task.inventory_item.batch.yield_unit
                elif task.inventory_item.par_unit_equals_type == 'custom':
                    summary['par_unit_equals_unit'] = task.inventory_item.par_unit_equals_unit
                else:
                    summary['par_unit_equals_unit'] = summary['par_unit_name']
                
                # Calculate initial inventory (current - made)
                made_par_units = 0
                if task.inventory_item and task.made_amount and task.made_unit:
                    made_par_units = task.inventory_item.convert_to_par_units(task.made_amount, task.made_unit)
                
                summary['initial_inventory'] = day_item.quantity - made_par_units
                summary['final_inventory'] = day_item.quantity
                
                # Add made amount info if available
                if task.made_amount and task.made_unit:
                    summary['made_amount'] = task.made_amount
                    summary['made_unit'] = task.made_unit
                    summary['made_par_units'] = made_par_units
                
                # Add converted amounts if par unit equals is available
                if summary['par_unit_equals'] and summary['par_unit_equals_type'] != 'par_unit_itself':
                    summary['initial_converted'] = summary['initial_inventory'] * summary['par_unit_equals']
                    summary['final_converted'] = summary['final_inventory'] * summary['par_unit_equals']
                    if 'made_par_units' in summary:
                        summary['made_converted'] = summary['made_par_units'] * summary['par_unit_equals']
                
                task_summaries[task.id] = summary
    
    return templates.TemplateResponse("inventory_day.html", {
        "request": request,
        "current_user": current_user,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
        "employees": employees,
        "task_summaries": task_summaries
    })

@app.post("/inventory/day/{day_id}/update")
async def update_inventory_day(
    day_id: int,
    request: Request,
    global_notes: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    if inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot update finalized day")
    
    # Update global notes
    inventory_day.global_notes = global_notes if global_notes else None
    
    # Update inventory quantities from form data
    form_data = await request.form()
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    
    for item in inventory_day_items:
        quantity_key = f"item_{item.inventory_item.id}"
        override_create_key = f"override_create_{item.inventory_item.id}"
        override_no_task_key = f"override_no_task_{item.inventory_item.id}"
        
        if quantity_key in form_data:
            item.quantity = float(form_data[quantity_key])
        
        item.override_create_task = override_create_key in form_data
        item.override_no_task = override_no_task_key in form_data
    
    # Generate tasks based on inventory levels
    generate_tasks_for_day(db, inventory_day)
    
    db.commit()
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

def generate_tasks_for_day(db: Session, inventory_day: InventoryDay):
    """Generate tasks based on inventory levels and overrides"""
    # Delete existing auto-generated tasks
    db.query(Task).filter(
        Task.day_id == inventory_day.id,
        Task.auto_generated == True
    ).delete()
    
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == inventory_day.id).all()
    
    for item in inventory_day_items:
        should_create_task = False
        
        # Check if item is below par
        is_below_par = item.quantity <= item.inventory_item.par_level
        
        # Determine if task should be created
        if item.override_create_task:
            should_create_task = True
        elif item.override_no_task:
            should_create_task = False
        elif is_below_par:
            should_create_task = True
        
        if should_create_task:
            # Create task
            task_description = f"Prep {item.inventory_item.name}"
            if is_below_par:
                task_description += f" (Below par: {item.quantity}/{item.inventory_item.par_level})"
            
            task = Task(
                day_id=inventory_day.id,
                inventory_item_id=item.inventory_item.id,
                batch_id=item.inventory_item.batch_id,  # Link to batch if available
                description=task_description,
                auto_generated=True
            )
            db.add(task)

@app.post("/inventory/day/{day_id}/finalize")
async def finalize_inventory_day(
    day_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day.finalized = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/reports/{day_id}", status_code=302)

@app.get("/inventory/reports/{day_id}", response_class=HTMLResponse)
async def inventory_report(day_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    inventory_day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    employees = db.query(User).filter(User.is_active == True).all()
    
    # Calculate statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == "completed"])
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

# Task Management Routes
@app.post("/inventory/day/{day_id}/tasks/new")
async def create_manual_task(
    day_id: int,
    request: Request,
    assigned_to_ids: list = Form([]),
    inventory_item_id: int = Form(None),
    description: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot add tasks to finalized day")
    
    # Create tasks for each assigned employee (or one unassigned task)
    if assigned_to_ids:
        for assigned_to_id in assigned_to_ids:
            task = Task(
                day_id=day_id,
                assigned_to_id=int(assigned_to_id),
                inventory_item_id=inventory_item_id if inventory_item_id else None,
                description=description,
                auto_generated=False
            )
            
            # Link to batch if inventory item has one
            if inventory_item_id:
                inventory_item = db.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
                if inventory_item and inventory_item.batch_id:
                    task.batch_id = inventory_item.batch_id
            
            db.add(task)
    else:
        # Create unassigned task
        task = Task(
            day_id=day_id,
            inventory_item_id=inventory_item_id if inventory_item_id else None,
            description=description,
            auto_generated=False
        )
        
        # Link to batch if inventory item has one
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check if task requires scale selection
    if task.batch and task.batch.can_be_scaled and not task.selected_scale:
        # Redirect to scale selection - this should be handled by frontend
        return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)
    
    task.started_at = datetime.utcnow()
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start_with_scale")
async def start_task_with_scale(
    day_id: int,
    task_id: int,
    selected_scale: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "not_started":
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
async def pause_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "in_progress":
        raise HTTPException(status_code=400, detail="Task is not in progress")
    
    task.paused_at = datetime.utcnow()
    task.is_paused = True
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/resume")
async def resume_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "paused":
        raise HTTPException(status_code=400, detail="Task is not paused")
    
    # Add pause time to total
    if task.paused_at:
        pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
        task.total_pause_time += int(pause_duration)
    
    task.paused_at = None
    task.is_paused = False
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish")
async def finish_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in ["in_progress", "paused"]:
        raise HTTPException(status_code=400, detail="Task cannot be finished")
    
    # Handle pause time if currently paused
    if task.is_paused and task.paused_at:
        pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
        task.total_pause_time += int(pause_duration)
    
    task.finished_at = datetime.utcnow()
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in ["in_progress", "paused"]:
        raise HTTPException(status_code=400, detail="Task cannot be finished")
    
    # Update inventory if linked to inventory item
    if task.inventory_item and task.made_amount and task.made_unit:
        # Find the day item for this inventory item
        day_item = db.query(InventoryDayItem).filter(
            InventoryDayItem.day_id == day_id,
            InventoryDayItem.inventory_item_id == task.inventory_item.id
        ).first()
        
        if day_item:
            # Convert made amount to par units and add to inventory
            par_units_made = task.inventory_item.convert_to_par_units(task.made_amount, task.made_unit)
            day_item.quantity += par_units_made
    
    # Handle pause time if currently paused
    if task.is_paused and task.paused_at:
        pause_duration = (datetime.utcnow() - task.paused_at).total_seconds()
        task.total_pause_time += int(pause_duration)
    
    task.made_amount = made_amount
    task.made_unit = made_unit
    task.finished_at = datetime.utcnow()
    task.is_paused = False
    task.paused_at = None
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.day_id == day_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.notes = notes if notes else None
    db.commit()
    
    return RedirectResponse(url=f"/inventory/day/{day_id}/tasks/{task_id}", status_code=302)

# Utilities Management Routes
@app.get("/utilities", response_class=HTMLResponse)
async def utilities_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    utilities = db.query(UtilityCost).all()
    
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "current_user": current_user,
        "utilities": utilities
    })

@app.post("/utilities/new")
async def create_utility_cost(
    request: Request,
    name: str = Form(...),
    monthly_cost: float = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if utility already exists
    existing_utility = db.query(UtilityCost).filter(UtilityCost.name == name).first()
    if existing_utility:
        # Update existing
        existing_utility.monthly_cost = monthly_cost
        existing_utility.last_updated = datetime.utcnow()
    else:
        # Create new
        utility = UtilityCost(
            name=name,
            monthly_cost=monthly_cost
        )
        db.add(utility)
    
    db.commit()
    return RedirectResponse(url="/utilities", status_code=302)

@app.post("/utilities/{utility_id}/delete")
async def delete_utility_cost(
    utility_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
    if not utility:
        raise HTTPException(status_code=404, detail="Utility not found")
    
    db.delete(utility)
    db.commit()
    return RedirectResponse(url="/utilities", status_code=302)

# Category and Vendor Management Routes
@app.post("/categories/new")
async def create_category(
    name: str = Form(...),
    type: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    category = Category(name=name, type=type)
    db.add(category)
    db.commit()
    
    # Redirect based on type
    redirect_map = {
        "ingredient": "/ingredients",
        "recipe": "/recipes",
        "dish": "/dishes",
        "inventory": "/inventory"
    }
    
    return RedirectResponse(url=redirect_map.get(type, "/"), status_code=302)

@app.post("/vendors/new")
async def create_vendor(
    name: str = Form(...),
    contact_info: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    vendor = Vendor(
        name=name,
        contact_info=contact_info if contact_info else None
    )
    db.add(vendor)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

@app.post("/par_unit_names/new")
async def create_par_unit_name(
    name: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    
    par_unit = ParUnitName(name=name)
    db.add(par_unit)
    db.commit()
    
    return RedirectResponse(url="/inventory", status_code=302)

# API Routes
@app.get("/api/ingredients/all")
async def api_get_all_ingredients(db: Session = Depends(get_db)):
    """Get all ingredients with their available units for recipe creation"""
    try:
        ingredients = db.query(Ingredient).all()
        result = []
        
        for ingredient in ingredients:
            # Get available units based on ingredient type
            available_units = ingredient.get_available_units()
            
            result.append({
                "id": ingredient.id,
                "name": ingredient.name,
                "category": ingredient.category.name if ingredient.category else None,
                "usage_type": ingredient.usage_type,
                "available_units": available_units
            })
        
        print(f"API: Returning {len(result)} ingredients")
        return result
    except Exception as e:
        print(f"API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ingredients/{ingredient_id}/cost_per_unit/{unit}")
async def api_get_ingredient_cost_per_unit(ingredient_id: int, unit: str, db: Session = Depends(get_db)):
    """Get cost per unit for a specific ingredient and unit"""
    try:
        ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
        if not ingredient:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        
        cost_per_unit = ingredient.get_cost_per_unit(unit)
        
        return {
            "ingredient_id": ingredient_id,
            "unit": unit,
            "cost_per_unit": cost_per_unit
        }
    except Exception as e:
        print(f"API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recipes/{recipe_id}/available_units")
async def api_get_recipe_available_units(recipe_id: int, db: Session = Depends(get_db)):
    """Get available units for a recipe based on its ingredients"""
    try:
        recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        # Get all ingredients in the recipe
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
        
        # Collect all available units from ingredients
        all_units = set()
        for ri in recipe_ingredients:
            if ri.ingredient:
                ingredient_units = ri.ingredient.get_available_units()
                all_units.update(ingredient_units)
        
        return sorted(list(all_units))
    except Exception as e:
        print(f"API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/batches/all")
async def api_get_all_batches(db: Session = Depends(get_db)):
    """Get all batches for dish creation"""
    try:
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
                "category": batch.recipe.category.name if batch.recipe.category else None,
                "yield_amount": batch.yield_amount,
                "yield_unit": batch.yield_unit,
                "cost_per_unit": cost_per_unit,
                "variable_yield": batch.variable_yield
            })
        
        return result
    except Exception as e:
        print(f"API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/batches/search")
async def api_search_batches(q: str = "", db: Session = Depends(get_db)):
    """Search batches by recipe name"""
    try:
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
            cost_per_unit = total_batch_cost / batch.yield_amount if batch.yield_amount else 0
            
            result.append({
                "id": batch.id,
                "recipe_name": batch.recipe.name,
                "category": batch.recipe.category.name if batch.recipe.category else None,
                "yield_amount": batch.yield_amount,
                "yield_unit": batch.yield_unit,
                "cost_per_unit": cost_per_unit,
                "variable_yield": batch.variable_yield
            })
        
        return result
    except Exception as e:
        print(f"API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/batches/{batch_id}/portion_units")
async def api_get_batch_portion_units(batch_id: int, db: Session = Depends(get_db)):
    """Get available portion units for a batch"""
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        if not batch.yield_unit:
            return []
        
        # Get compatible units based on yield unit type
        yield_unit = batch.yield_unit.lower()
        compatible_units = []
        
        # Weight units
        if yield_unit in WEIGHT_CONVERSIONS:
            compatible_units = list(WEIGHT_CONVERSIONS.keys())
        # Volume units
        elif yield_unit in VOLUME_CONVERSIONS:
            compatible_units = list(VOLUME_CONVERSIONS.keys())
        # Count units
        elif yield_unit in ['each', 'dozen']:
            compatible_units = ['each', 'dozen']
        else:
            # Default to just the yield unit
            compatible_units = [yield_unit]
        
        # Format for frontend
        result = []
        for unit in compatible_units:
            result.append({
                "id": unit,  # Using unit name as ID for simplicity
                "name": unit
            })
        
        return result
    except Exception as e:
        print(f"API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/batches/{batch_id}/cost_per_unit/{unit}")
async def api_get_batch_cost_per_unit(batch_id: int, unit: str, db: Session = Depends(get_db)):
    """Get expected cost per unit for a batch in specified unit"""
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Calculate total batch cost
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == batch.recipe_id).all()
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        total_batch_cost = total_recipe_cost + batch.estimated_labor_cost
        
        if not batch.yield_amount or batch.yield_amount <= 0:
            return {"expected_cost_per_unit": 0}
        
        # Calculate cost per yield unit
        cost_per_yield_unit = total_batch_cost / batch.yield_amount
        
        # Convert to requested unit if different
        if unit == batch.yield_unit:
            expected_cost_per_unit = cost_per_yield_unit
        else:
            # Apply conversion factor
            conversion_factor = get_unit_conversion_factor(batch.yield_unit, unit)
            expected_cost_per_unit = cost_per_yield_unit / conversion_factor if conversion_factor else cost_per_yield_unit
        
        return {
            "batch_id": batch_id,
            "unit": unit,
            "expected_cost_per_unit": expected_cost_per_unit
        }
    except Exception as e:
        print(f"API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def get_unit_conversion_factor(from_unit: str, to_unit: str) -> float:
    """Get conversion factor between units"""
    try:
        # Weight conversions
        if from_unit in WEIGHT_CONVERSIONS and to_unit in WEIGHT_CONVERSIONS:
            # Convert from_unit to base (lb), then to to_unit
            from_factor = WEIGHT_CONVERSIONS[from_unit]
            to_factor = WEIGHT_CONVERSIONS[to_unit]
            return to_factor / from_factor
        
        # Volume conversions
        if from_unit in VOLUME_CONVERSIONS and to_unit in VOLUME_CONVERSIONS:
            # Convert from_unit to base (gal), then to to_unit
            from_factor = VOLUME_CONVERSIONS[from_unit]
            to_factor = VOLUME_CONVERSIONS[to_unit]
            return to_factor / from_factor
        
        # Count conversions
        count_conversions = {'each': 1.0, 'dozen': 12.0}
        if from_unit in count_conversions and to_unit in count_conversions:
            return count_conversions[to_unit] / count_conversions[from_unit]
        
        # No conversion available
        return 1.0
    except:
        return 1.0

@app.get("/api/batches/{batch_id}/labor_stats")
async def api_get_batch_labor_stats(batch_id: int, db: Session = Depends(get_db)):
    """Get labor statistics for a batch"""
    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Get completed tasks for this batch
        completed_tasks = db.query(Task).filter(
            Task.batch_id == batch_id,
            Task.finished_at.isnot(None)
        ).all()
        
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
        most_recent_task = max(completed_tasks, key=lambda t: t.finished_at)
        
        # Time-based filtering
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        week_tasks = [t for t in completed_tasks if t.finished_at >= week_ago]
        month_tasks = [t for t in completed_tasks if t.finished_at >= month_ago]
        
        return {
            "task_count": len(completed_tasks),
            "most_recent_cost": most_recent_task.labor_cost,
            "most_recent_date": most_recent_task.finished_at.strftime('%Y-%m-%d'),
            "average_week": sum(t.labor_cost for t in week_tasks) / len(week_tasks) if week_tasks else batch.estimated_labor_cost,
            "average_month": sum(t.labor_cost for t in month_tasks) / len(month_tasks) if month_tasks else batch.estimated_labor_cost,
            "average_all_time": sum(t.labor_cost for t in completed_tasks) / len(completed_tasks),
            "week_task_count": len(week_tasks),
            "month_task_count": len(month_tasks)
        }
    except Exception as e:
        print(f"API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# API endpoints for frontend JavaScript
@app.get("/api/ingredients/all")
async def get_all_ingredients(db: Session = Depends(get_db)):
    ingredients = db.query(Ingredient).all()
    return [
        {
            "id": ing.id,
            "name": ing.name,
            "category": ing.category.name if ing.category else None,
            "available_units": ing.get_available_units()
        }
        for ing in ingredients
    ]

@app.get("/api/tasks/{task_id}/scale_options")
async def get_task_scale_options(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task or not task.batch:
        return []
    
    return [
        {
            "key": scale[0],
            "label": scale[2],
            "yield": f"{task.batch.get_scaled_yield(scale[1])} {task.batch.yield_unit}" if not task.batch.variable_yield else "Variable"
        }
        for scale in task.batch.get_available_scales()
    ]

@app.get("/api/tasks/{task_id}/finish_requirements")
async def get_task_finish_requirements(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    available_units = []
    inventory_info = None
    
    if task.batch:
        if task.batch.variable_yield:
            # For variable yield, get available units from batch recipe
            available_units = task.batch.recipe.get_available_units() if hasattr(task.batch.recipe, 'get_available_units') else [task.batch.yield_unit]
        else:
            available_units = [task.batch.yield_unit]
    
    # Get inventory information if linked
    if task.inventory_item:
        inventory_day = db.query(InventoryDay).join(Task).filter(Task.id == task_id).first()
        day_item = db.query(InventoryDayItem).filter(
            InventoryDayItem.inventory_item_id == task.inventory_item.id,
            InventoryDayItem.day_id == inventory_day.id
        ).first()
        
        if day_item:
            inventory_info = {
                "current": day_item.quantity,
                "par_level": task.inventory_item.par_level,
                "par_unit_name": task.inventory_item.par_unit_name.name if task.inventory_item.par_unit_name else "units"
            }
    
    return {
        "available_units": available_units,
        "inventory_info": inventory_info
    }

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=302)
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