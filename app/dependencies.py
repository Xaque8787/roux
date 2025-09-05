from fastapi import HTTPException, Depends, Request
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
from .auth import verify_jwt

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=401, 
            detail="Not authenticated",
            headers={"Location": "/login"}
        )
    
    payload = verify_jwt(token)
    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401, 
            detail="User not found",
            headers={"Location": "/login"}
        )
    return user

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def require_manager_or_admin(current_user: User = Depends(get_current_user)):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")
    return current_user

def require_user_or_above(current_user: User = Depends(get_current_user)):
    if current_user.role not in ["admin", "manager", "user"]:
        raise HTTPException(status_code=403, detail="User access required")
    return current_user