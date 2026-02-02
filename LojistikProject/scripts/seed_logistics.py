import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.services.logistics_service import LogisticsService
from app.db.models import user_model, logistics_model

def seed():
    print("Seeding logistics data...")
    db = SessionLocal()
    try:
        service = LogisticsService()
        service.seed_data(db)
        print("Logistics data seeded successfully with user provided coordinates.")
    except Exception as e:
        print(f"Error seeding data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
