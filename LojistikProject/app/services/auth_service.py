from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.schemas.user_schema import UserRegister, UserLogin
from app.db.models.user_model import User
from app.repositories.user_repository import UserRepository
from app.core.security import hash_password, verify_password, create_access_token

user_repo = UserRepository()

class AuthService:

    def register(self, db: Session, data: UserRegister):
        if data.password != data.password_confirm:
            raise HTTPException(400, "Şifreler eşleşmiyor")

        if user_repo.get_by_email(db, data.email):
            raise HTTPException(400, "E-posta zaten kullanımda")

        if user_repo.get_by_username(db, data.username):
            raise HTTPException(400, "Kullanıcı adı zaten kullanımda")

        new_user = User(
            username=data.username,
            email=data.email,
            password_hash=hash_password(data.password),
            role=data.role
        )

        return user_repo.create(db, new_user)

    def login(self, db: Session, data: UserLogin):
        user = user_repo.get_by_email(db, data.email)
        if not user:
            raise HTTPException(400, "Geçersiz e-posta veya şifre")

        if not verify_password(data.password, user.password_hash):
            raise HTTPException(400, "Geçersiz e-posta veya şifre")

        token = create_access_token({"user_id": user.id, "sub": user.email, "role": user.role})
        return {"access_token": token, "token_type": "bearer", "role": user.role}
