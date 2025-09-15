from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..auth import verify_password, hash_password, create_jwt
from ..utils.helpers import create_default_categories, create_default_vendor_units, create_default_vendors, create_default_par_unit_names

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="templates")

@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, db: Session = Depends(get_db)):
    # Check if any users exist
    user_count = db.query(User).count()
    if user_count > 0:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("setup.html", {"request": request})

@router.post("/setup")
async def setup_admin(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Check if any users exist
    user_count = db.query(User).count()
    if user_count > 0:
        return RedirectResponse(url="/login", status_code=302)
    
    # Create admin user
    hashed_password = hash_password(password)
    admin_user = User(
        username=username,
        hashed_password=hashed_password,
        full_name=full_name if full_name else username,
        role="admin",
        is_admin=True,
        is_user=True,
        hourly_wage=20.0
    )
    
    db.add(admin_user)
    
    # Create default categories
    try:
        create_default_categories(db)
        create_default_vendor_units(db)
        create_default_vendors(db)
        create_default_par_unit_names(db)
    except Exception as e:
        print(f"Warning: Could not create default data: {e}")
    
    db.commit()
    
    return RedirectResponse(url="/login", status_code=302)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
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
    
    # Create JWT token
    token = create_jwt(data={"sub": user.username})
    
    # Create response and set cookie
    response = RedirectResponse(url="/home", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        path="/",
        max_age=86400  # 24 hours
    )
    
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token", path="/")
    return response

@router.get("/debug-cookies")
async def debug_cookies(request: Request):
    """Debug endpoint to check what cookies are available"""
    cookies = dict(request.cookies)
    return {
        "cookies": cookies,
        "access_token_present": "access_token" in cookies,
        "cookie_count": len(cookies)
    }

# Check if setup is needed
@router.get("/")
async def root_redirect(db: Session = Depends(get_db)):
    user_count = db.query(User).count()
    if user_count == 0:
        return RedirectResponse(url="/setup", status_code=302)
    return RedirectResponse(url="/home", status_code=302)