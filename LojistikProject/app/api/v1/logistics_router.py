from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.api.deps import get_db, get_current_user, get_current_admin
from app.schemas.logistics_schema import CargoRequestCreate, CargoRequestOut, StationOut, RouteOut, StationCreate, VehicleCapacityUpdate
from app.services.logistics_service import LogisticsService
from app.db.models.user_model import User

router = APIRouter(prefix="/logistics", tags=["Logistics"])
service = LogisticsService()

@router.get("/seed")
def seed_data(db: Session = Depends(get_db)):
    service.seed_data(db)
    return {"message": "Data seeded successfully"}

@router.get("/stations", response_model=List[StationOut])
def get_stations(db: Session = Depends(get_db)):
    return service.get_stations(db)

@router.post("/stations", response_model=StationOut)
def create_station(
    data: StationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    return service.create_station(db, data)

@router.delete("/stations/{station_id}")
def delete_station(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):

    return service.delete_station(db, station_id)

@router.post("/cargo", response_model=CargoRequestOut)
def create_cargo(
    data: CargoRequestCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return service.create_cargo_request(db, current_user.id, data)

@router.get("/cargo/me", response_model=List[CargoRequestOut])
def get_my_cargo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return service.get_my_requests(db, current_user.id)

@router.get("/cargo/dates")
def get_available_dates(db: Session = Depends(get_db)):
    dates = service.get_available_dates(db)
    return {"dates": [d.isoformat() for d in dates]}

@router.post("/admin/optimize")
def optimize_routes(
    target_date: str, 
    scenario: str = "unlimited",  
    cost_per_km: float = 1.0, 
    rental_cost: float = 200.0,
    rental_capacity: float = 500.0,  
    optimization_mode: str = "max_count",  
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
   
    try:
        date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD kullanın.")
    
    return service.solve_vrp(db, date_obj, scenario, cost_per_km, rental_cost, rental_capacity, optimization_mode)

@router.get("/admin/routes")
def get_all_routes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    return service.get_all_routes(db)

@router.get("/admin/routes/{target_date}")
def get_routes_by_date(
    target_date: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):

    try:
        date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD kullanın.")
    
    return service.get_routes_by_date(db, date_obj)

@router.get("/admin/routes-archive")
def get_routes_archive(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):

    return service.get_routes_archive(db)

@router.delete("/admin/routes")
def delete_all_routes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    return service.delete_all_routes(db)

@router.get("/admin/distance-matrix")
def get_distance_matrix(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    return service.get_distance_matrix(db)

@router.get("/admin/statistics/{target_date}")
def get_statistics(
    target_date: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD kullanın.")
    
    return service.get_statistics(db, date_obj)

@router.get("/admin/vehicle-users/{target_date}")
def get_vehicle_users(
    target_date: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD kullanın.")
    
    return service.get_vehicle_users(db, date_obj)

@router.post("/admin/compare-scenarios")
def compare_scenarios(
    target_date: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    try:
        date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD kullanın.")
    
    return service.compare_scenarios(db, date_obj)

@router.get("/routes/my/{target_date}")
def get_my_route(
    target_date: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD kullanın.")
    
    result = service.get_user_route(db, current_user.id, date_obj)
    return result

@router.put("/admin/vehicle-capacities")
def update_vehicle_capacities(
    updates: List[VehicleCapacityUpdate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    return service.update_vehicle_capacities(db, [u.dict() for u in updates])
