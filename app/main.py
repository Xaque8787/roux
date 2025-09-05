from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, date, timedelta
import os
from typing import Optional, List
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

def create_default_categories(db: Session):
    """Create default categories if they don't exist"""
    try:
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
            ("Production", "batch"),
            ("Prep", "batch"),
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
            existing = db.query(Category).filter(
                Category.name == name, 
                Category.type == cat_type
            ).first()
            if not existing:
                category = Category(name=name, type=cat_type)
                db.add(category)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error creating default categories: {e}")

def create_default_vendor_units(db: Session):
    """Create default vendor units if they don't exist"""
    try:
        default_units = [
            ("lb", "Pounds"),
            ("oz", "Ounces"),
            ("g", "Grams"),
            ("kg", "Kilograms"),
            ("gal", "Gallons"),
            ("qt", "Quarts"),
            ("pt", "Pints"),
            ("cup", "Cups"),
            ("fl_oz", "Fluid Ounces"),
            ("l", "Liters"),
            ("ml", "Milliliters"),
            ("each", "Each/Individual Items"),
            ("dozen", "Dozen (12 items)"),
            ("case", "Case/Box")
        ]
        
        for name, description in default_units:
            existing = db.query(VendorUnit).filter(VendorUnit.name == name).first()
            if not existing:
                unit = VendorUnit(name=name, description=description)
                db.add(unit)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error creating default vendor units: {e}")

def create_default_par_unit_names(db: Session):
    """Create default par unit names if they don't exist"""
    try:
        default_par_units = [
            "Tub",
            "Container",
            "Case",
            "Box",
            "Bag",
            "Bottle",
            "Can",
            "Jar",
            "Package",
            "Bundle"
        ]
        
        for name in default_par_units:
            existing = db.query(ParUnitName).filter(ParUnitName.name == name).first()
            if not existing:
                par_unit = ParUnitName(name=name)
                db.add(par_unit)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error creating default par unit names: {e}")

@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
    try:
        create_default_categories(db)
        create_default_vendor_units(db)
        create_default_par_unit_names(db)
    finally:
        db.close()

# Check if setup is needed
def needs_setup(db: Session):
    return db.query(User).count() == 0

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse(url="/setup", status_code=302)
    
    # Check if user is logged in
    try:
        current_user = get_current_user(request, db)
        return RedirectResponse(url="/home", status_code=302)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    if not needs_setup(db):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_post(
    request: Request,
    username: str = Form(...),
    full_name: Optional[str] = Form(None),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not needs_setup(db):
        return RedirectResponse(url="/", status_code=302)
    
    # Use username as full_name if not provided
    if not full_name or full_name.strip() == "":
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
    db.commit()
    
    return RedirectResponse(url="/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login")
async def login_post(
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

@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# API endpoint for task scale options
@app.get("/api/tasks/{task_id}/scale_options")
async def get_task_scale_options(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).options(joinedload(Task.batch).joinedload(Batch.recipe)).filter(Task.id == task_id).first()
    if not task or not task.batch:
        raise HTTPException(status_code=404, detail="Task or batch not found")
    
    batch = task.batch
    if not batch.can_be_scaled:
        return [{"key": "full", "label": "Full Batch", "yield": f"{batch.yield_amount} {batch.yield_unit}" if not batch.variable_yield else "Variable"}]
    
    scales = [{"key": "full", "label": "Full Batch", "yield": f"{batch.yield_amount} {batch.yield_unit}" if not batch.variable_yield else "Variable"}]
    
    if batch.scale_double:
        yield_text = f"{batch.yield_amount * 2} {batch.yield_unit}" if not batch.variable_yield else "Variable (2x)"
        scales.append({"key": "double", "label": "Double Batch", "yield": yield_text})
    
    if batch.scale_half:
        yield_text = f"{batch.yield_amount / 2} {batch.yield_unit}" if not batch.variable_yield else "Variable (1/2x)"
        scales.append({"key": "half", "label": "Half Batch", "yield": yield_text})
    
    if batch.scale_quarter:
        yield_text = f"{batch.yield_amount / 4} {batch.yield_unit}" if not batch.variable_yield else "Variable (1/4x)"
        scales.append({"key": "quarter", "label": "Quarter Batch", "yield": yield_text})
    
    if batch.scale_eighth:
        yield_text = f"{batch.yield_amount / 8} {batch.yield_unit}" if not batch.variable_yield else "Variable (1/8x)"
        scales.append({"key": "eighth", "label": "Eighth Batch", "yield": yield_text})
    
    if batch.scale_sixteenth:
        yield_text = f"{batch.yield_amount / 16} {batch.yield_unit}" if not batch.variable_yield else "Variable (1/16x)"
        scales.append({"key": "sixteenth", "label": "Sixteenth Batch", "yield": yield_text})
    
    return scales

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 404,
        "detail": "Page not found"
    }, status_code=404)

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 500,
        "detail": "Internal server error"
    }, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)