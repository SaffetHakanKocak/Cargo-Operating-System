from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime, date

class StationOut(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    class Config:
        from_attributes = True

class StationCreate(BaseModel):
    name: str
    latitude: float
    longitude: float

class CargoRequestCreate(BaseModel):
    station_id: int
    weight: float
    cargo_count: int = 1
    request_date: Optional[datetime] = None

class CargoRequestOut(BaseModel):
    id: int
    user_id: int
    weight: float
    cargo_count: int
    request_date: datetime
    station: StationOut
    class Config:
        from_attributes = True

class VehicleOut(BaseModel):
    id: int
    name: str
    capacity: float
    current_load: float
    is_rented: bool
    class Config:
        from_attributes = True

class RouteOut(BaseModel):
    id: int
    vehicle_id: int
    path_data: Any
    total_distance: Optional[float] = None
    total_cost: Optional[float] = None
    route_date: Optional[date] = None
    scenario_type: Optional[str] = None
    cargo_weight: Optional[float] = None
    cargo_count: Optional[int] = None
    vehicle: Optional[VehicleOut] = None
    class Config:
        from_attributes = True

class VehicleCapacityUpdate(BaseModel):
    name: str
    capacity: float
