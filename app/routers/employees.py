from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import require_admin, get_current_user, require_manager_or_admin
from ..models import User
from ..auth import hash_password

from ..utils.template_helpers import setup_template_filters
from ..utils.slugify import generate_unique_slug
router = APIRouter(prefix="/employees", tags=["employees"])
templates = setup_template_filters(Jinja2Templates(directory="templates"))

@router.get("/", response_class=HTMLResponse)
async def employees_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    employees = db.query(User).all()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "current_user": current_user,
        "employees": employees
    })

@router.post("/new")
async def create_employee(
    request: Request,
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(""),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        employees = db.query(User).all()
        return templates.TemplateResponse("employees.html", {
            "request": request,
            "current_user": current_user,
            "employees": employees,
            "error": "Username already exists"
        })
    
    hashed_password = hash_password(password)
    slug = generate_unique_slug(db, User, username)

    employee = User(
        username=username,
        slug=slug,
        hashed_password=hashed_password,
        full_name=full_name,
        email=email if email else None,
        hourly_wage=hourly_wage,
        work_schedule=work_schedule,
        role=role,
        is_admin=(role == "admin"),
        is_user=True
    )
    
    db.add(employee)
    db.commit()

    return RedirectResponse(url=f"/employees/{slug}", status_code=302)

@router.get("/{slug}", response_class=HTMLResponse)
async def employee_detail(slug: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    employee = db.query(User).filter(User.slug == slug).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_detail.html", {
        "request": request,
        "current_user": current_user,
        "employee": employee
    })

@router.get("/{slug}/edit", response_class=HTMLResponse)
async def employee_edit_page(slug: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    employee = db.query(User).filter(User.slug == slug).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("employee_edit.html", {
        "request": request,
        "current_user": current_user,
        "employee": employee
    })

@router.post("/{slug}/edit")
async def update_employee(
    slug: str,
    request: Request,
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(""),
    email: str = Form(""),
    hourly_wage: float = Form(...),
    work_schedule: str = Form(""),
    role: str = Form(...),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    employee = db.query(User).filter(User.slug == slug).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if employee.username != username:
        employee.slug = generate_unique_slug(db, User, username, exclude_id=employee.id)

    # Check if username already exists (excluding current employee)
    existing_user = db.query(User).filter(User.username == username, User.id != employee.id).first()
    if existing_user:
        return templates.TemplateResponse("employee_edit.html", {
            "request": request,
            "current_user": current_user,
            "employee": employee,
            "error": "Username already exists"
        })
    
    employee.full_name = full_name
    employee.username = username
    employee.email = email if email else None
    employee.hourly_wage = hourly_wage
    employee.work_schedule = work_schedule
    employee.role = role
    employee.is_admin = (role == "admin")
    employee.is_active = is_active
    
    if password:
        employee.hashed_password = hash_password(password)
    
    db.commit()

    return RedirectResponse(url=f"/employees/{employee.slug}", status_code=302)

@router.get("/{slug}/delete")
async def delete_employee(slug: str, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    employee = db.query(User).filter(User.slug == slug).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Don't allow deleting self
    if employee.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    # Deactivate instead of delete to preserve data integrity
    employee.is_active = False
    db.commit()
    
    return RedirectResponse(url="/employees", status_code=302)