from sqlalchemy.orm import Session
from app.db.models.user_model import User

class UserRepository:

    def create(self, db: Session, user: User):
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def get_by_email(self, db: Session, email: str):
        return db.query(User).filter(User.email == email).first()

    def get_by_username(self, db: Session, username: str):
        return db.query(User).filter(User.username == username).first()

    def get_by_id(self, db: Session, user_id: int):
        return db.query(User).filter(User.id == user_id).first()
