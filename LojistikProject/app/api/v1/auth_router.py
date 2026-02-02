from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.schemas.user_schema import UserRegister, UserLogin, Token
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])
auth_service = AuthService()

@router.post("/register")
def register(data: UserRegister, db: Session = Depends(get_db)):
    return auth_service.register(db, data)

@router.post("/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    return auth_service.login(db, data)

@router.get("/me")
def get_me(current_user = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}
