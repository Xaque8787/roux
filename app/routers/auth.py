from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import timedelta
from ..database import get_db
from ..models import User
from ..auth import hash_password, verify_password, create_jwt, ACCESS_TOKEN_EXPIRE_MINUTES
from ..utils.helpers import (create_default_categories, create_default_vendor_units, 
                            create_default_vendors, create_default_par_unit_names)
router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="templates")

@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, db: Session = Depends(get_db)):
    # Check if any admin users exist
    admin_exists = db.query(User).filter(User.role == "admin").first()
    if admin_exists:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("setup.html", {"request": request})

@router.post("/setup")
async def create_admin_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    db: Session = Depends(get_db)
):
    # Check if any admin users exist
    admin_exists = db.query(User).filter(User.role == "admin").first()
    if admin_exists:
        return RedirectResponse(url="/login", status_code=302)
    
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return templates.TemplateResponse("setup.html", {
            "request": request,
            "error": "Username already exists"
        })
    
    # Use username as full_name if not provided
    if not full_name.strip():
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
        hourly_wage=20.0
    )
    
    db.add(admin_user)
    db.commit()
    
    # Create default data
    try:
        print("Creating default categories...")
        create_default_categories(db)
        print("Creating default vendor units...")
        create_default_vendor_units(db)
        print("Creating default vendors...")
        create_default_vendors(db)
        print("Creating default par unit names...")
        create_default_par_unit_names(db)
        print("Default data creation completed")
    except Exception as e:
        print(f"Warning: Could not create some default data: {e}")
        # Don't prevent setup completion if default data creation fails
    
    # Auto-login the admin user
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_jwt(
        data={"sub": admin_user.username}, expires_delta=access_token_expires
    )
    
    response = RedirectResponse(url="/home", status_code=302)
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    return response

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    # Check if setup is needed
    admin_exists = db.query(User).filter(User.role == "admin").first()
    if not admin_exists:
        return RedirectResponse(url="/setup", status_code=302)
    
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
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
    
    if not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Account is deactivated"
        })
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_jwt(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    response = RedirectResponse(url="/home", status_code=302)
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response