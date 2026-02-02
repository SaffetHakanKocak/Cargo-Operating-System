import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.user_model import User
from app.core.security import hash_password

def seed_admin_user():
    db = SessionLocal()
    try:
        email = "yusufbulbul475@gmail.com"
        user = db.query(User).filter(User.email == email).first()
        
        if user:
            print(f"User {email} found. Updating password and role...")
            user.password_hash = hash_password("12")
            user.role = "admin"
            db.commit()
            print("User updated successfully.")
        else:
            print(f"User {email} not found. Creating new admin user...")
            new_user = User(
                username="AdminYusufCorrect",
                email=email,
                password_hash=hash_password("12"),
                role="admin",
                is_active=True
            )
            db.add(new_user)
            db.commit()
            print("Admin user created successfully.")
            
    except Exception as e:
        print(f"Error seeding admin: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_admin_user()
