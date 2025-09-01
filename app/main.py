# Food Cost Management System - Updated with working setup
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from datetime import datetime, timedelta, date
from typing import Optional, List
import os

from .database import SessionLocal, engine, Base
from .models import *
from .auth import *
from .schemas import *

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_setup_required(db: Session):
    """Check if initial setup is required"""
    user_count = db.query(User).count()
    return user_count == 0

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/home", status_code=307)

@app.get("/setup", response_class=HTMLResponse)
async def setup_form(request: Request, db: Session = Depends(get_db)):
    if not check_setup_required(db):
        return RedirectResponse(url="/home", status_code=307)
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def create_admin_user(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not check_setup_required(db):
        return RedirectResponse(url="/home", status_code=307)
    
    try:
        # Use username as full_name if not provided
        if not full_name or full_name.strip() == "":
            full_name = username
        
        # Create admin user
        hashed_password = hash_password(password)
        admin_user = User(
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            role="admin",
            is_admin=True,
            is_user=True,
            hourly_wage=15.0
        )
        db.add(admin_user)
        
        # Create default categories
        categories = [
            Category(name="Proteins", type="ingredient"),
            Category(name="Vegetables", type="ingredient"),
            Category(name="Dairy", type="ingredient"),
            Category(name="Grains", type="ingredient"),
            Category(name="Spices", type="ingredient"),
            Category(name="Appetizers", type="dish"),
            Category(name="Entrees", type="dish"),
            Category(name="Desserts", type="dish"),
            Category(name="Beverages", type="dish"),
            Category(name="Sauces", type="recipe"),
            Category(name="Soups", type="recipe"),
            Category(name="Salads", type="recipe"),
            Category(name="Prep Items", type="inventory"),
            Category(name="Finished Goods", type="inventory")
        ]
        
        for category in categories:
            db.add(category)
        
        # Create vendor units
        vendor_units = [
            VendorUnit(name="lb", description="Pound"),
            VendorUnit(name="oz", description="Ounce"),
            VendorUnit(name="gal", description="Gallon"),
            VendorUnit(name="qt", description="Quart"),
            VendorUnit(name="pt", description="Pint"),
            VendorUnit(name="fl oz", description="Fluid Ounce"),
            VendorUnit(name="kg", description="Kilogram"),
            VendorUnit(name="g", description="Gram"),
            VendorUnit(name="L", description="Liter"),
            VendorUnit(name="mL", description="Milliliter")
        ]
        
        for unit in vendor_units:
            db.add(unit)
        
        # Create usage units
        usage_units = [
            UsageUnit(name="cup"),
            UsageUnit(name="tbsp"),
            UsageUnit(name="tsp"),
            UsageUnit(name="oz"),
            UsageUnit(name="lb"),
            UsageUnit(name="each"),
            UsageUnit(name="piece"),
            UsageUnit(name="slice"),
            UsageUnit(name="clove"),
            UsageUnit(name="bunch"),
            UsageUnit(name="head"),
            UsageUnit(name="can"),
            UsageUnit(name="bottle"),
            UsageUnit(name="bag"),
            UsageUnit(name="box"),
            UsageUnit(name="gal"),
            UsageUnit(name="qt"),
            UsageUnit(name="pt"),
            UsageUnit(name="fl oz")
        ]
        
        for unit in usage_units:
            db.add(unit)
        
        # Commit to get IDs
        db.commit()
        
        # Create vendor unit conversions
        # Get the units we just created
        lb_unit = db.query(VendorUnit).filter(VendorUnit.name == "lb").first()
        oz_unit = db.query(VendorUnit).filter(VendorUnit.name == "oz").first()
        gal_unit = db.query(VendorUnit).filter(VendorUnit.name == "gal").first()
        qt_unit = db.query(VendorUnit).filter(VendorUnit.name == "qt").first()
        pt_unit = db.query(VendorUnit).filter(VendorUnit.name == "pt").first()
        fl_oz_unit = db.query(VendorUnit).filter(VendorUnit.name == "fl oz").first()
        
        # Get usage units
        cup_usage = db.query(UsageUnit).filter(UsageUnit.name == "cup").first()
        tbsp_usage = db.query(UsageUnit).filter(UsageUnit.name == "tbsp").first()
        tsp_usage = db.query(UsageUnit).filter(UsageUnit.name == "tsp").first()
        oz_usage = db.query(UsageUnit).filter(UsageUnit.name == "oz").first()
        lb_usage = db.query(UsageUnit).filter(UsageUnit.name == "lb").first()
        gal_usage = db.query(UsageUnit).filter(UsageUnit.name == "gal").first()
        qt_usage = db.query(UsageUnit).filter(UsageUnit.name == "qt").first()
        pt_usage = db.query(UsageUnit).filter(UsageUnit.name == "pt").first()
        fl_oz_usage = db.query(UsageUnit).filter(UsageUnit.name == "fl oz").first()
        
        # Create conversions
        conversions = []
        
        # Pound conversions
        if lb_unit and oz_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=lb_unit.id, usage_unit_id=oz_usage.id, conversion_factor=16))
        if lb_unit and lb_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=lb_unit.id, usage_unit_id=lb_usage.id, conversion_factor=1))
        if lb_unit and cup_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=lb_unit.id, usage_unit_id=cup_usage.id, conversion_factor=2))  # Approximate for flour
        
        # Ounce conversions
        if oz_unit and oz_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=oz_unit.id, usage_unit_id=oz_usage.id, conversion_factor=1))
        if oz_unit and tbsp_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=oz_unit.id, usage_unit_id=tbsp_usage.id, conversion_factor=2))
        if oz_unit and tsp_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=oz_unit.id, usage_unit_id=tsp_usage.id, conversion_factor=6))
        
        # Gallon conversions
        if gal_unit and gal_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=gal_unit.id, usage_unit_id=gal_usage.id, conversion_factor=1))
        if gal_unit and qt_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=gal_unit.id, usage_unit_id=qt_usage.id, conversion_factor=4))
        if gal_unit and pt_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=gal_unit.id, usage_unit_id=pt_usage.id, conversion_factor=8))
        if gal_unit and cup_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=gal_unit.id, usage_unit_id=cup_usage.id, conversion_factor=16))
        if gal_unit and fl_oz_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=gal_unit.id, usage_unit_id=fl_oz_usage.id, conversion_factor=128))
        
        # Quart conversions
        if qt_unit and qt_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=qt_unit.id, usage_unit_id=qt_usage.id, conversion_factor=1))
        if qt_unit and pt_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=qt_unit.id, usage_unit_id=pt_usage.id, conversion_factor=2))
        if qt_unit and cup_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=qt_unit.id, usage_unit_id=cup_usage.id, conversion_factor=4))
        if qt_unit and fl_oz_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=qt_unit.id, usage_unit_id=fl_oz_usage.id, conversion_factor=32))
        
        # Pint conversions
        if pt_unit and pt_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=pt_unit.id, usage_unit_id=pt_usage.id, conversion_factor=1))
        if pt_unit and cup_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=pt_unit.id, usage_unit_id=cup_usage.id, conversion_factor=2))
        if pt_unit and fl_oz_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=pt_unit.id, usage_unit_id=fl_oz_usage.id, conversion_factor=16))
        
        # Fluid ounce conversions
        if fl_oz_unit and fl_oz_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=fl_oz_unit.id, usage_unit_id=fl_oz_usage.id, conversion_factor=1))
        if fl_oz_unit and tbsp_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=fl_oz_unit.id, usage_unit_id=tbsp_usage.id, conversion_factor=2))
        if fl_oz_unit and tsp_usage:
            conversions.append(VendorUnitConversion(vendor_unit_id=fl_oz_unit.id, usage_unit_id=tsp_usage.id, conversion_factor=6))
        
        # Add all conversions
        for conversion in conversions:
            db.add(conversion)
        
        db.commit()
        
        # Redirect to login page after successful setup
        return RedirectResponse(url="/login", status_code=303)
        
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("setup.html", {
            "request": request, 
            "error": f"Error creating admin user: {str(e)}"
        })

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, db: Session = Depends(get_db)):
    if check_setup_required(db):
        return RedirectResponse(url="/setup", status_code=307)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if check_setup_required(db):
        return RedirectResponse(url="/setup", status_code=307)
    
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
    
    # Create JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_jwt(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Create response and set cookie
    response = RedirectResponse(url="/home", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="access_token")
    return response

@app.get("/home", response_class=HTMLResponse)
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user
    })

# Error handlers
@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        raise exc
    return RedirectResponse(url="/login", status_code=303)

@app.exception_handler(403)
async def forbidden_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 403,
        "detail": "Access forbidden"
    }, status_code=403)

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": 404,
        "detail": "Page not found"
    }, status_code=404)