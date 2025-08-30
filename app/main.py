from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import date, datetime
import json
from typing import List
import os

from .database import get_db, engine
from .models import Base, User, Category, Ingredient, Recipe, RecipeIngredient, Batch, Dish, DishBatchPortion, InventoryItem, InventoryDay, InventoryDayItem, Task, UtilityCost, Vendor, UsageUnit, IngredientUsageUnit
from .auth import hash_password, verify_password, create_jwt, get_current_user, require_admin, require_manager_or_admin, require_user_or_above

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Food Cost Management System")

# Mount static files and templates
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Custom exception handler for authentication redirects
@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    if exc.status_code == 401:
        # Check if we have any users in the database
        from .database import SessionLocal
        db = SessionLocal()
        try:
            if not db.query(User).first():
                return RedirectResponse("/setup", status_code=302)
            else:
                return RedirectResponse("/login", status_code=302)
        finally:
            db.close()
    return templates.TemplateResponse("error.html", {
        "request": request, 
        "status_code": exc.status_code,
        "detail": exc.detail
    }, status_code=exc.status_code)
# Root redirect
@app.get("/")
async def root():
    return RedirectResponse("/setup")

# Setup routes
@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    if db.query(User).first():
        return RedirectResponse("/login")
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if db.query(User).first():
        return RedirectResponse("/login")
    
    hashed_password = hash_password(password)
    admin = User(
        username=username,
        full_name=username,
        hashed_password=hashed_password,
        role="admin",
        is_admin=True,
        is_user=True,
        hourly_wage=20.0
    )
    db.add(admin)
    
    # Create default categories and usage units
    categories = [
        Category(name="Produce", type="ingredient"),
        Category(name="Dairy", type="ingredient"),
        Category(name="Meat", type="ingredient"),
        Category(name="Pantry", type="ingredient"),
        Category(name="Dressings", type="recipe"),
        Category(name="Sauces", type="recipe"),
        Category(name="Prep Items", type="batch"),
        Category(name="Salads", type="dish"),
        Category(name="Entrees", type="dish"),
        Category(name="Desserts", type="dish"),
        Category(name="Proteins", type="inventory"),
        Category(name="Vegetables", type="inventory"),
    ]
    
    for category in categories:
        db.add(category)
    
    # Create default usage units
    usage_units = [
        UsageUnit(name="lb"),
        UsageUnit(name="oz"),
        UsageUnit(name="g"),
        UsageUnit(name="kg"),
        UsageUnit(name="tbsp"),
        UsageUnit(name="tsp"),
        UsageUnit(name="cup"),
        UsageUnit(name="fl oz"),
        UsageUnit(name="pt"),
        UsageUnit(name="qt"),
        UsageUnit(name="gal"),
        UsageUnit(name="can"),
        UsageUnit(name="ea"),
        UsageUnit(name="pkg"),
    ]
    
    for unit in usage_units:
        db.add(unit)
    
    # Create default vendor units with common conversions
    vendor_units_data = [
        ("lb", "Pound"),
        ("oz", "Ounce"), 
        ("kg", "Kilogram"),
        ("g", "Gram"),
        ("gal", "Gallon"),
        ("qt", "Quart"),
        ("pt", "Pint"),
        ("fl oz", "Fluid Ounce"),
        ("L", "Liter"),
        ("mL", "Milliliter"),
    ]
    
    vendor_units = []
    for name, description in vendor_units_data:
        vendor_unit = VendorUnit(name=name, description=description)
        db.add(vendor_unit)
        vendor_units.append(vendor_unit)
    
    db.flush()  # Get IDs for vendor units
    
    # Create common conversion factors
    conversions = [
        # Pound conversions
        ("lb", "lb", 1),
        ("lb", "oz", 16),
        ("lb", "kg", 0.453592),
        ("lb", "g", 453.592),
        
        # Ounce conversions
        ("oz", "oz", 1),
        ("oz", "lb", 1/16),
        ("oz", "tbsp", 2),
        ("oz", "tsp", 6),
        ("oz", "g", 28.3495),
        
        # Gallon conversions
        ("gal", "gal", 1),
        ("gal", "qt", 4),
        ("gal", "pt", 8),
        ("gal", "cup", 16),
        ("gal", "fl oz", 128),
        ("gal", "tbsp", 256),
        ("gal", "tsp", 768),
        ("gal", "L", 3.78541),
        
        # Quart conversions
        ("qt", "qt", 1),
        ("qt", "pt", 2),
        ("qt", "cup", 4),
        ("qt", "fl oz", 32),
        ("qt", "tbsp", 64),
        ("qt", "gal", 0.25),
        
        # Kilogram conversions
        ("kg", "kg", 1),
        ("kg", "lb", 2.20462),
        ("kg", "oz", 35.274),
        ("kg", "g", 1000),
    ]
    
    for vendor_unit_name, usage_unit_name, factor in conversions:
        vendor_unit = next((vu for vu in vendor_units if vu.name == vendor_unit_name), None)
        usage_unit = next((uu for uu in usage_units if uu.name == usage_unit_name), None)
        
        if vendor_unit and usage_unit:
            conversion = VendorUnitConversion(
                vendor_unit_id=vendor_unit.id,
                usage_unit_id=usage_unit.id,
                conversion_factor=factor
            )
            db.add(conversion)
    
    db.commit()
    return RedirectResponse("/login", status_code=302)

# Login routes
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
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
    token = create_jwt({
        "sub": user.username,
        "role": user.role,
        "is_admin": user.is_admin,
        "is_user": user.is_user
    })
    response = RedirectResponse("/home", status_code=302)
    response.set_cookie("access_token", token, httponly=True, samesite="strict")
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response

# Home page
@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Employees routes
@app.get("/employees", response_class=HTMLResponse)
async def list_employees(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employees = db.query(User).all()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "employees": employees,
        "current_user": current_user
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
    return RedirectResponse("/employees", status_code=302)

@app.get("/employees/{employee_id}", response_class=HTMLResponse)
async def view_employee(
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
        "employee": employee,
        "current_user": current_user
    })

@app.get("/employees/{employee_id}/edit", response_class=HTMLResponse)
async def edit_employee_form(
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
        "employee": employee,
        "current_user": current_user
    })

@app.post("/employees/{employee_id}/edit")
async def update_employee(
    employee_id: int,
    full_name: str = Form(...),
    username: str = Form(...),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form("user"),
    is_active: bool = Form(False),
    password: str = Form(""),
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
    return RedirectResponse(f"/employees/{employee_id}", status_code=302)

@app.get("/employees/{employee_id}/delete")
async def delete_employee(
    employee_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    employee = db.query(User).filter(User.id == employee_id).first()
    if employee and employee.id != current_user.id:  # Can't delete yourself
        employee.is_active = False  # Soft delete
        db.commit()
    return RedirectResponse("/employees", status_code=302)

# Ingredients routes
@app.get("/ingredients", response_class=HTMLResponse)
async def list_ingredients(
    request: Request,
    current_user: User = Depends(require_user_or_above),
    db: Session = Depends(get_db)
):
    ingredients = db.query(Ingredient).all()
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    usage_units = db.query(UsageUnit).all()
    return templates.TemplateResponse("ingredients.html", {
        "request": request,
        "ingredients": ingredients,
        "categories": categories,
        "vendors": vendors,
        "usage_units": usage_units,
        "current_user": current_user
    })

@app.post("/ingredients/new")
async def create_ingredient(
    request: Request,
    name: str = Form(...),
    category_id: int = Form(None),
    vendor_id: int = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    purchase_quantity_description: str = Form(""),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: int = Form(None),
    item_unit_name: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    form = await request.form()
    
    ingredient = Ingredient(
        name=name,
        category_id=category_id if category_id else None,
        vendor_id=vendor_id if vendor_id else None,
        purchase_type=purchase_type,
        purchase_unit_name=purchase_unit_name,
        purchase_quantity_description=purchase_quantity_description,
        purchase_total_cost=purchase_total_cost,
        breakable_case=breakable_case,
        items_per_case=items_per_case if items_per_case else None,
        item_unit_name=item_unit_name
    )
    db.add(ingredient)
    db.flush()
    
    # Add usage units and conversion factors
    usage_units = db.query(UsageUnit).all()
    for unit in usage_units:
        conversion_key = f"conversion_{unit.id}"
        if conversion_key in form and form[conversion_key]:
            conversion_factor = float(form[conversion_key])
            if conversion_factor > 0:
                ingredient_usage = IngredientUsageUnit(
                    ingredient_id=ingredient.id,
                    usage_unit_id=unit.id,
                    conversion_factor=conversion_factor
                )
                db.add(ingredient_usage)
    
    db.commit()
    return RedirectResponse("/ingredients", status_code=302)

@app.get("/ingredients/{ingredient_id}", response_class=HTMLResponse)
async def view_ingredient(
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
        "ingredient": ingredient,
        "usage_units": usage_units,
        "current_user": current_user
    })

@app.get("/ingredients/{ingredient_id}/edit", response_class=HTMLResponse)
async def edit_ingredient_form(
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
    usage_units = db.query(UsageUnit).all()
    ingredient_usage_units = db.query(IngredientUsageUnit).filter(
        IngredientUsageUnit.ingredient_id == ingredient_id
    ).all()
    
    # Create a dict for easy lookup of existing conversion factors
    existing_conversions = {iu.usage_unit_id: iu.conversion_factor for iu in ingredient_usage_units}
    
    return templates.TemplateResponse("ingredient_edit.html", {
        "request": request,
        "ingredient": ingredient,
        "categories": categories,
        "vendors": vendors,
        "usage_units": usage_units,
        "existing_conversions": existing_conversions,
        "current_user": current_user
    })

@app.post("/ingredients/{ingredient_id}/edit")
async def update_ingredient(
    ingredient_id: int,
    request: Request,
    name: str = Form(...),
    category_id: int = Form(None),
    vendor_id: int = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    purchase_quantity_description: str = Form(""),
    purchase_total_cost: float = Form(...),
    breakable_case: bool = Form(False),
    items_per_case: int = Form(None),
    item_unit_name: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    form = await request.form()
    
    # Update ingredient fields
    ingredient.name = name
    ingredient.category_id = category_id if category_id else None
    ingredient.vendor_id = vendor_id if vendor_id else None
    ingredient.purchase_type = purchase_type
    ingredient.purchase_unit_name = purchase_unit_name
    ingredient.purchase_quantity_description = purchase_quantity_description
    ingredient.purchase_total_cost = purchase_total_cost
    ingredient.breakable_case = breakable_case
    ingredient.items_per_case = items_per_case if items_per_case else None
    ingredient.item_unit_name = item_unit_name
    
    # Update usage units - delete existing and recreate
    db.query(IngredientUsageUnit).filter(
        IngredientUsageUnit.ingredient_id == ingredient_id
    ).delete()
    
    usage_units = db.query(UsageUnit).all()
    for unit in usage_units:
        conversion_key = f"conversion_{unit.id}"
        if conversion_key in form and form[conversion_key]:
            conversion_factor = float(form[conversion_key])
            if conversion_factor > 0:
                ingredient_usage = IngredientUsageUnit(
                    ingredient_id=ingredient.id,
                    usage_unit_id=unit.id,
                    conversion_factor=conversion_factor
                )
                db.add(ingredient_usage)
    
    db.commit()
    return RedirectResponse(f"/ingredients/{ingredient_id}", status_code=302)

@app.get("/ingredients/{ingredient_id}/delete")
async def delete_ingredient(
    ingredient_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if ingredient:
        # Delete related usage units first
        db.query(IngredientUsageUnit).filter(
            IngredientUsageUnit.ingredient_id == ingredient_id
        ).delete()
        db.delete(ingredient)
        db.commit()
    return RedirectResponse("/ingredients", status_code=302)

# Category management routes
@app.post("/categories/new")
async def create_category(
    name: str = Form(...),
    type: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    category = Category(name=name, type=type)
    db.add(category)
    db.commit()
    
    # Redirect based on type
    if type == "ingredient":
        return RedirectResponse("/ingredients", status_code=302)
    elif type == "recipe":
        return RedirectResponse("/recipes", status_code=302)
    elif type == "dish":
        return RedirectResponse("/dishes", status_code=302)
    elif type == "inventory":
        return RedirectResponse("/inventory", status_code=302)
    else:
        return RedirectResponse("/", status_code=302)

# Vendor management routes
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
    return RedirectResponse("/ingredients", status_code=302)

# Usage Unit management routes
@app.post("/usage_units/new")
async def create_usage_unit(
    name: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    usage_unit = UsageUnit(name=name)
    db.add(usage_unit)
    db.commit()
    return RedirectResponse("/ingredients", status_code=302)

# Recipes routes
@app.get("/recipes", response_class=HTMLResponse)
async def list_recipes(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recipes = db.query(Recipe).all()
    categories = db.query(Category).filter(Category.type == "recipe").all()
    return templates.TemplateResponse("recipes.html", {
        "request": request,
        "recipes": recipes,
        "categories": categories,
        "current_user": current_user
    })

@app.post("/recipes/new")
async def create_recipe(
    request: Request,
    name: str = Form(...),
    instructions: str = Form(""),
    category_id: int = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    form = await request.form()
    
    recipe = Recipe(
        name=name,
        instructions=instructions,
        category_id=category_id if category_id else None
    )
    db.add(recipe)
    db.flush()
    
    # Add ingredients from JSON data
    ingredients_data = form.get("ingredients_data")
    if ingredients_data:
        import json
        ingredients_list = json.loads(ingredients_data)
        for ingredient_data in ingredients_list:
            if ingredient_data.get('quantity') and float(ingredient_data['quantity']) > 0:
                recipe_ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=int(ingredient_data['ingredient_id']),
                    usage_unit_id=int(ingredient_data['usage_unit_id']),
                    quantity=float(ingredient_data['quantity'])
                )
                db.add(recipe_ingredient)
    
    db.commit()
    return RedirectResponse("/recipes", status_code=302)

@app.get("/recipes/{recipe_id}")
async def view_recipe(
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
    
    # Calculate total recipe cost
    total_cost = sum(ri.cost for ri in recipe_ingredients)
    
    return templates.TemplateResponse("recipe_detail.html", {
        "request": request,
        "recipe": recipe,
        "recipe_ingredients": recipe_ingredients,
        "total_cost": total_cost,
        "current_user": current_user
    })

@app.get("/recipes/{recipe_id}/delete")
async def delete_recipe(
    recipe_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if recipe:
        # Delete recipe ingredients first
        db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
        db.delete(recipe)
        db.commit()
    return RedirectResponse("/recipes", status_code=302)

# Batches routes
@app.get("/batches", response_class=HTMLResponse)
async def list_batches(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batches = db.query(Batch).all()
    recipes = db.query(Recipe).all()
    usage_units = db.query(UsageUnit).all()
    return templates.TemplateResponse("batches.html", {
        "request": request,
        "batches": batches,
        "recipes": recipes,
        "usage_units": usage_units,
        "current_user": current_user
    })

@app.post("/batches/new")
async def create_batch(
    recipe_id: int = Form(...),
    yield_amount: float = Form(...),
    yield_unit_id: int = Form(...),
    labor_minutes: int = Form(...),
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
        labor_minutes=labor_minutes,
        can_be_scaled=can_be_scaled,
        scale_double=scale_double,
        scale_half=scale_half,
        scale_quarter=scale_quarter,
        scale_eighth=scale_eighth,
        scale_sixteenth=scale_sixteenth
    )
    db.add(batch)
    db.commit()
    return RedirectResponse("/batches", status_code=302)

@app.get("/batches/{batch_id}/delete")
async def delete_batch(
    batch_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if batch:
        db.delete(batch)
        db.commit()
    return RedirectResponse("/batches", status_code=302)

@app.get("/batches/{batch_id}", response_class=HTMLResponse)
async def view_batch(
    batch_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get recipe ingredients for cost calculation
    recipe_ingredients = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == batch.recipe_id
    ).all()
    
    # Calculate total recipe cost
    total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
    
    # Calculate cost per yield unit
    cost_per_yield_unit = total_recipe_cost / batch.yield_amount if batch.yield_amount > 0 else 0
    
    # Calculate labor cost (assuming current user's wage for display)
    labor_cost = (batch.labor_minutes / 60) * current_user.hourly_wage
    
    # Total batch cost including labor
    total_batch_cost = total_recipe_cost + labor_cost
    
    return templates.TemplateResponse("batch_detail.html", {
        "request": request,
        "batch": batch,
        "recipe_ingredients": recipe_ingredients,
        "total_recipe_cost": total_recipe_cost,
        "cost_per_yield_unit": cost_per_yield_unit,
        "labor_cost": labor_cost,
        "total_batch_cost": total_batch_cost,
        "current_user": current_user
    })

@app.get("/batches/{batch_id}/edit", response_class=HTMLResponse)
async def edit_batch_form(
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
        "batch": batch,
        "recipes": recipes,
        "usage_units": usage_units,
        "current_user": current_user
    })

@app.post("/batches/{batch_id}/edit")
async def update_batch(
    batch_id: int,
    recipe_id: int = Form(...),
    yield_amount: float = Form(...),
    yield_unit_id: int = Form(...),
    labor_minutes: int = Form(...),
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
    batch.labor_minutes = labor_minutes
    batch.can_be_scaled = can_be_scaled
    batch.scale_double = scale_double
    batch.scale_half = scale_half
    batch.scale_quarter = scale_quarter
    batch.scale_eighth = scale_eighth
    batch.scale_sixteenth = scale_sixteenth
    
    db.commit()
    return RedirectResponse(f"/batches/{batch_id}", status_code=302)

@app.get("/api/recipes/{recipe_id}/usage_units")
async def get_recipe_usage_units(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all usage units used in a recipe's ingredients"""
    recipe_ingredients = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == recipe_id
    ).all()
    
    usage_unit_ids = set()
    for ri in recipe_ingredients:
        # Get all usage units from the ingredient's usage units
        for iu in ri.ingredient.usage_units:
            usage_unit_ids.add(iu.usage_unit_id)
    
    usage_units = db.query(UsageUnit).filter(UsageUnit.id.in_(usage_unit_ids)).all()
    
    return [{"id": unit.id, "name": unit.name} for unit in usage_units]

# Dishes routes
@app.get("/dishes", response_class=HTMLResponse)
async def list_dishes(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    dishes = db.query(Dish).all()
    categories = db.query(Category).filter(Category.type == "dish").all()
    return templates.TemplateResponse("dishes.html", {
        "request": request,
        "dishes": dishes,
        "categories": categories,
        "current_user": current_user
    })

@app.post("/dishes/new")
async def create_dish(
    request: Request,
    name: str = Form(...),
    sale_price: float = Form(...),
    description: str = Form(""),
    category_id: int = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    form = await request.form()
    
    dish = Dish(
        name=name,
        sale_price=sale_price,
        description=description,
        category_id=category_id if category_id else None
    )
    db.add(dish)
    db.flush()
    
    # Add batch portions from JSON data
    batch_portions_data = form.get("batch_portions_data")
    if batch_portions_data:
        import json
        batch_portions_list = json.loads(batch_portions_data)
        for portion_data in batch_portions_list:
            if portion_data.get('portion_size') and float(portion_data['portion_size']) > 0:
                dish_batch_portion = DishBatchPortion(
                    dish_id=dish.id,
                    batch_id=int(portion_data['batch_id']),
                    portion_size=float(portion_data['portion_size']),
                    portion_unit_id=int(portion_data['portion_unit_id']) if portion_data.get('portion_unit_id') else None
                )
                db.add(dish_batch_portion)
    
    db.commit()
    return RedirectResponse("/dishes", status_code=302)

@app.get("/dishes/{dish_id}/delete")
async def delete_dish(
    dish_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if dish:
        # Delete dish batch portions first
        db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
        db.delete(dish)
        db.commit()
    return RedirectResponse("/dishes", status_code=302)

# Inventory routes
@app.get("/inventory", response_class=HTMLResponse)
async def view_inventory_master(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_items = db.query(InventoryItem).all()
    categories = db.query(Category).filter(Category.type == "inventory").all()
    employees = db.query(User).filter(User.is_user == True).all()
    
    # Get current inventory day if exists
    today = date.today()
    current_day = db.query(InventoryDay).filter(InventoryDay.date == today).first()
    
    # Get recent finalized days (last 30 days)
    from datetime import timedelta
    thirty_days_ago = today - timedelta(days=30)
    finalized_days = db.query(InventoryDay).filter(
        InventoryDay.finalized == True,
        InventoryDay.date >= thirty_days_ago
    ).order_by(InventoryDay.date.desc()).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "inventory_items": inventory_items,
        "categories": categories,
        "employees": employees,
        "current_day": current_day,
        "finalized_days": finalized_days,
        "today_date": today.isoformat(),
        "current_user": current_user
    })

@app.post("/inventory/new_item")
async def create_inventory_item(
    name: str = Form(...),
    par_level: float = Form(...),
    category_id: int = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = InventoryItem(
        name=name,
        par_level=par_level,
        category_id=category_id if category_id else None
    )
    db.add(item)
    db.commit()
    return RedirectResponse("/inventory", status_code=302)

@app.post("/inventory/new_day")
async def create_new_day(
    request: Request,
    date_input: str = Form(..., alias="date"),
    global_notes: str = Form(""),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    form = await request.form()
    employees_working = form.getlist("employees_working")
    
    inventory_day = InventoryDay(
        date=datetime.strptime(date_input, "%Y-%m-%d").date(),
        employees_working=",".join(employees_working),
        global_notes=global_notes
    )
    db.add(inventory_day)
    db.flush()
    
    # Copy master inventory items to day items
    inventory_items = db.query(InventoryItem).all()
    for item in inventory_items:
        day_item = InventoryDayItem(
            day_id=inventory_day.id,
            inventory_item_id=item.id,
            quantity=0
        )
        db.add(day_item)
    
    db.commit()
    return RedirectResponse(f"/inventory/day/{inventory_day.id}", status_code=302)

@app.get("/inventory/day/{day_id}", response_class=HTMLResponse)
async def view_inventory_day(
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
    employees = db.query(User).filter(User.is_user == True).all()
    
    return templates.TemplateResponse("inventory_day.html", {
        "request": request,
        "inventory_day": inventory_day,
        "inventory_day_items": inventory_day_items,
        "tasks": tasks,
        "employees": employees,
        "current_user": current_user
    })

def _auto_generate_tasks(day_id: int, db: Session):
    """Auto-generate tasks for items below par level"""
    # Get all day items for this day
    day_items = db.query(InventoryDayItem).filter(InventoryDayItem.day_id == day_id).all()
    
    # Delete existing auto-generated tasks to regenerate
    db.query(Task).filter(Task.day_id == day_id, Task.auto_generated == True).delete()
    
    for day_item in day_items:
        item = day_item.inventory_item
        
        # Check if item is below par and should generate a task
        should_generate_task = False
        
        if day_item.quantity <= item.par_level:
            # Below par - generate task unless overridden
            if not day_item.override_no_task:
                should_generate_task = True
        else:
            # Above par - only generate if override is set
            if day_item.override_create_task:
                should_generate_task = True
        
        if should_generate_task:
            # Create auto-generated task
            if day_item.quantity <= item.par_level:
                description = f"Restock {item.name} (Below Par: {day_item.quantity}/{item.par_level})"
            else:
                description = f"Check {item.name} (Override requested)"
            
            task = Task(
                day_id=day_id,
                assigned_to_id=None,  # Will be assigned manually
                description=description,
                auto_generated=True
            )
            db.add(task)
    
    db.flush()

@app.post("/inventory/day/{day_id}/update")
async def update_inventory_day_items(
    day_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day or inventory_day.finalized:
        raise HTTPException(status_code=400, detail="Cannot update finalized day")
    
    form = await request.form()
    
    # Update global notes if provided
    if "global_notes" in form:
        inventory_day.global_notes = form["global_notes"]
    
    # Update inventory quantities and task overrides
    for key, value in form.items():
        if key.startswith("item_"):
            item_id = int(key.replace("item_", ""))
            day_item = db.query(InventoryDayItem).filter(
                InventoryDayItem.day_id == day_id,
                InventoryDayItem.inventory_item_id == item_id
            ).first()
            if day_item:
                day_item.quantity = float(value) if value else 0
        elif key.startswith("override_create_"):
            item_id = int(key.replace("override_create_", ""))
            day_item = db.query(InventoryDayItem).filter(
                InventoryDayItem.day_id == day_id,
                InventoryDayItem.inventory_item_id == item_id
            ).first()
            if day_item:
                day_item.override_create_task = True
        elif key.startswith("override_no_task_"):
            item_id = int(key.replace("override_no_task_", ""))
            day_item = db.query(InventoryDayItem).filter(
                InventoryDayItem.day_id == day_id,
                InventoryDayItem.inventory_item_id == item_id
            ).first()
            if day_item:
                day_item.override_no_task = True
    
    # Auto-generate tasks for below par items (if not overridden)
    _auto_generate_tasks(day_id, db)
    
    db.commit()
    return RedirectResponse(f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/new")
async def create_task(
    day_id: int,
    assigned_to_id: int = Form(...),
    description: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = Task(
        day_id=day_id,
        assigned_to_id=assigned_to_id,
        description=description
    )
    db.add(task)
    db.commit()
    return RedirectResponse(f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/start")
async def start_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task and not task.started_at:
        task.started_at = datetime.utcnow()
        task.is_paused = False
        db.commit()
    return RedirectResponse(f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/tasks/{task_id}/finish")
async def finish_task(
    day_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task and task.started_at and not task.finished_at:
        task.finished_at = datetime.utcnow()
        task.is_paused = False
        db.commit()
    return RedirectResponse(f"/inventory/day/{day_id}", status_code=302)

@app.post("/inventory/day/{day_id}/finalize")
async def finalize_day(
    day_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if inventory_day:
        inventory_day.finalized = True
        db.commit()
    return RedirectResponse(f"/inventory/day/{day_id}", status_code=302)

@app.get("/inventory/reports/{day_id}")
async def view_day_report(
    day_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inventory_day = db.query(InventoryDay).filter(InventoryDay.id == day_id).first()
    if not inventory_day:
        raise HTTPException(status_code=404, detail="Inventory day not found")
    
    # Get all tasks for this day
    tasks = db.query(Task).filter(Task.day_id == day_id).all()
    
    # Get inventory items with their quantities
    inventory_day_items = db.query(InventoryDayItem).filter(
        InventoryDayItem.day_id == day_id
    ).all()
    
    # Calculate summary statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.finished_at])
    below_par_items = len([item for item in inventory_day_items 
                          if item.quantity <= item.inventory_item.par_level])
    
    return templates.TemplateResponse("inventory_report.html", {
        "request": request,
        "inventory_day": inventory_day,
        "tasks": tasks,
        "inventory_day_items": inventory_day_items,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "below_par_items": below_par_items,
        "current_user": current_user
    })

# Utilities routes
@app.get("/utilities", response_class=HTMLResponse)
async def view_utilities(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    utilities = db.query(UtilityCost).all()
    return templates.TemplateResponse("utilities.html", {
        "request": request,
        "utilities": utilities,
        "current_user": current_user
    })

@app.post("/utilities/new")
async def add_utility(
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
    return RedirectResponse("/utilities", status_code=302)

@app.post("/utilities/{utility_id}/delete")
async def delete_utility(
    utility_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    utility = db.query(UtilityCost).filter(UtilityCost.id == utility_id).first()
    if utility:
        db.delete(utility)
        db.commit()
    return RedirectResponse("/utilities", status_code=302)

# API endpoints for dishes
@app.get("/api/batches/search")
async def search_batches(
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search batches for autocomplete"""
    batches = db.query(Batch).join(Recipe).filter(
        Recipe.name.ilike(f"%{q}%")
    ).limit(10).all()
    
    result = []
    for batch in batches:
        # Calculate batch cost for display
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == batch.recipe_id
        ).all()
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        labor_cost = (batch.labor_minutes / 60) * current_user.hourly_wage
        total_batch_cost = total_recipe_cost + labor_cost
        cost_per_yield_unit = total_batch_cost / batch.yield_amount if batch.yield_amount > 0 else 0
        
        result.append({
            "id": batch.id,
            "recipe_name": batch.recipe.name,
            "yield_amount": batch.yield_amount,
            "yield_unit": batch.yield_unit.name if batch.yield_unit else "",
            "cost_per_unit": cost_per_yield_unit,
            "category": batch.recipe.category.name if batch.recipe.category else None
        })
    
    return result

@app.get("/dishes/{dish_id}")
async def view_dish(
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
    
    # Calculate total dish cost
    total_cost = sum(portion.cost for portion in dish_batch_portions)
    
    # Calculate profit margin
    profit = dish.sale_price - total_cost
    profit_margin = (profit / dish.sale_price * 100) if dish.sale_price > 0 else 0
    
    return templates.TemplateResponse("dish_detail.html", {
        "request": request,
        "dish": dish,
        "dish_batch_portions": dish_batch_portions,
        "total_cost": total_cost,
        "profit": profit,
        "profit_margin": profit_margin,
        "current_user": current_user
    })

@app.get("/dishes/{dish_id}/edit", response_class=HTMLResponse)
async def edit_dish_form(
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
        "dish": dish,
        "categories": categories,
        "dish_batch_portions": dish_batch_portions,
        "current_user": current_user
    })

@app.post("/dishes/{dish_id}/edit")
async def update_dish(
    dish_id: int,
    request: Request,
    name: str = Form(...),
    sale_price: float = Form(...),
    description: str = Form(""),
    category_id: int = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    dish = db.query(Dish).filter(Dish.id == dish_id).first()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    form = await request.form()
    
    # Update dish fields
    dish.name = name
    dish.sale_price = sale_price
    dish.description = description
    dish.category_id = category_id if category_id else None
    
    # Update batch portions - delete existing and recreate
    db.query(DishBatchPortion).filter(DishBatchPortion.dish_id == dish_id).delete()
    
    batch_portions_data = form.get("batch_portions_data")
    if batch_portions_data:
        import json
        batch_portions_list = json.loads(batch_portions_data)
        for portion_data in batch_portions_list:
            if portion_data.get('portion_size') and float(portion_data['portion_size']) > 0:
                dish_batch_portion = DishBatchPortion(
                    dish_id=dish.id,
                    batch_id=int(portion_data['batch_id']),
                    portion_size=float(portion_data['portion_size']),
                    portion_unit_id=int(portion_data['portion_unit_id']) if portion_data.get('portion_unit_id') else None
                )
                db.add(dish_batch_portion)
    
    db.commit()
    return RedirectResponse(f"/dishes/{dish_id}", status_code=302)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)