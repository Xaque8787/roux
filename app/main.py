from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os

from .database import SessionLocal, engine, Base
from .models import User, Category, VendorUnit, ParUnitName
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

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": exc.status_code,
        "detail": exc.detail
    })