from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Date, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base
# Note: String reference used for User to avoid circular imports if needed, 
# but we can assume safe imports here or use string "User"

class Station(Base):
    __tablename__ = "stations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    cargo_requests = relationship("CargoRequest", back_populates="station")

class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50))
    capacity = Column(Float, nullable=False) # kg
    current_load = Column(Float, default=0.0)
    is_rented = Column(Boolean, default=False)
    rental_cost = Column(Float, default=0.0)
    
    routes = relationship("Route", back_populates="vehicle")

class CargoRequest(Base):
    __tablename__ = "cargo_requests"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    station_id = Column(Integer, ForeignKey("stations.id"))
    weight = Column(Float, nullable=False) # kg
    cargo_count = Column(Integer, default=1)
    request_date = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("app.db.models.user_model.User")
    station = relationship("Station", back_populates="cargo_requests")

class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    
    # Stores the ordered list of station IDs or coordinates visited
    path_data = Column(JSON) 
    
    total_distance = Column(Float)
    total_cost = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # New fields for day-based routing
    route_date = Column(Date)  # Which day this route is for
    scenario_type = Column(String(20))  # "unlimited" or "limited"
    cargo_weight = Column(Float)  # Total weight carried (kg)
    cargo_count = Column(Integer)  # Number of cargo items
    
    vehicle = relationship("Vehicle", back_populates="routes")

