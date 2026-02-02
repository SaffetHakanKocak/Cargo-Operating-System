from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, text
from app.db.models.logistics_model import Station, Vehicle, CargoRequest, Route
from app.schemas.logistics_schema import CargoRequestCreate, StationCreate
from fastapi import HTTPException
from datetime import date, datetime
from typing import List, Dict, Optional
import json
import math
import requests

DISTRICTS = [
    {"name": "Başiskele", "lat": 40.7140, "lon": 29.9268},
    {"name": "Çayırova", "lat": 40.8176, "lon": 29.3669},
    {"name": "Darıca", "lat": 40.7624, "lon":  29.3849},
    {"name": "Derince", "lat": 40.7573, "lon": 29.8318},
    {"name": "Dilovası", "lat": 40.7829, "lon": 29.5295},
    {"name": "Gebze", "lat": 40.8012, "lon": 29.4319},
    {"name": "Gölcük", "lat": 40.7175, "lon": 29.8196},
    {"name": "Kandıra", "lat": 41.0699, "lon":  30.1528},
    {"name": "Karamürsel", "lat": 40.6920, "lon": 29.6170},
    {"name": "Kartepe", "lat": 40.7240, "lon": 30.0025},
    {"name": "Körfez", "lat": 40.7716, "lon": 29.7836},
    {"name": "İzmit", "lat": 40.7650, "lon": 29.9404},
    {"name": "Umuttepe", "lat": 40.8241, "lon": 29.9259},
] 

DEPOT_NAME = "Umuttepe"
DEPOT_COORDS = {"lat": 40.8241, "lon": 29.9259}

DEFAULT_VEHICLE_CAPACITY = 500.0  
DEFAULT_COST_PER_KM = 1.0  


class LogisticsService:
    
    def seed_data(self, db: Session):
        db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        db.execute(text("TRUNCATE TABLE routes"))
        db.execute(text("TRUNCATE TABLE cargo_requests"))
        db.execute(text("TRUNCATE TABLE stations"))
        db.execute(text("TRUNCATE TABLE vehicles"))
        db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        db.commit()
        
        for d in DISTRICTS:
            station = Station(name=d["name"], latitude=d["lat"], longitude=d["lon"])
            db.add(station)
        db.commit()
            
        vehicles = [
            Vehicle(name="Kamyon 1", capacity=500.0),
            Vehicle(name="Kamyon 2", capacity=750.0),
            Vehicle(name="Tır 1", capacity=1000.0)
        ]
        db.add_all(vehicles)
        db.commit()

    def create_cargo_request(self, db: Session, user_id: int, data: CargoRequestCreate):
        req = CargoRequest(
            user_id=user_id,
            station_id=data.station_id,
            weight=data.weight,
            cargo_count=data.cargo_count,
            request_date=data.request_date or datetime.utcnow()
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        return req

    def create_station(self, db: Session, data: StationCreate):
        try:
            station = Station(
                name=data.name,
                latitude=data.latitude,
                longitude=data.longitude
            )
            db.add(station)
            db.commit()
            db.refresh(station)
            return station
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail="Bu isimde bir istasyon zaten mevcut.")

    def delete_station(self, db: Session, station_id: int):
        station = db.query(Station).filter(Station.id == station_id).first()
        if not station:
            raise HTTPException(status_code=404, detail="İstasyon bulunamadı.")
        

        cargo_count = db.query(CargoRequest).filter(CargoRequest.station_id == station_id).count()
        if cargo_count > 0:
            raise HTTPException(status_code=400, detail=f"Bu istasyona ait {cargo_count} kargo talebi var. Silinemez.")
            
        try:
            db.delete(station)
            db.commit()
            return {"status": "success", "message": "İstasyon silindi."}
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail="İstasyon silinemedi (ilişkili veri hatası).")

    def get_stations(self, db: Session):
        return db.query(Station).all()
        
    def get_my_requests(self, db: Session, user_id: int):
        return db.query(CargoRequest).filter(CargoRequest.user_id == user_id).all()

    def get_all_routes(self, db: Session):
        return db.query(Route).all()
    
    def get_routes_by_date(self, db: Session, target_date: date):
        return db.query(Route).filter(Route.route_date == target_date).all()
    
    def get_routes_archive(self, db: Session) -> Dict:
        all_routes = db.query(Route).order_by(Route.route_date.desc()).all()
        
        if not all_routes:
            return {
                "status": "no_data",
                "message": "Hiç rota kaydı bulunamadı.",
                "dates": [],
                "total_routes": 0
            }
        
        grouped = {}
        for route in all_routes:
            date_key = route.route_date.isoformat() if route.route_date else "unknown"
            if date_key not in grouped:
                grouped[date_key] = {
                    "date": date_key,
                    "routes": [],
                    "total_cost": 0,
                    "total_distance": 0,
                    "total_cargo_count": 0,
                    "total_cargo_weight": 0,
                    "vehicle_count": 0,
                    "rented_count": 0,
                    "scenario_type": route.scenario_type or "unknown"
                }
            
            grouped[date_key]["routes"].append({
                "id": route.id,
                "vehicle_id": route.vehicle_id,
                "vehicle_name": route.vehicle.name if route.vehicle else f"Araç {route.vehicle_id}",
                "is_rented": route.vehicle.is_rented if route.vehicle else False,
                "total_cost": route.total_cost,
                "total_distance": route.total_distance,
                "cargo_count": route.cargo_count,
                "cargo_weight": route.cargo_weight
            })
            
            grouped[date_key]["total_cost"] += route.total_cost or 0
            grouped[date_key]["total_distance"] += route.total_distance or 0
            grouped[date_key]["total_cargo_count"] += route.cargo_count or 0
            grouped[date_key]["total_cargo_weight"] += route.cargo_weight or 0
            grouped[date_key]["vehicle_count"] += 1
            if route.vehicle and route.vehicle.is_rented:
                grouped[date_key]["rented_count"] += 1

        dates_list = []
        for date_key, data in sorted(grouped.items(), reverse=True):
            data["total_cost"] = round(data["total_cost"], 2)
            data["total_distance"] = round(data["total_distance"], 2)
            data["total_cargo_weight"] = round(data["total_cargo_weight"], 2)
            dates_list.append(data)
        
        return {
            "status": "success",
            "dates": dates_list,
            "total_routes": len(all_routes),
            "total_dates": len(dates_list)
        }
    
    def get_user_route(self, db: Session, user_id: int, target_date: date) -> Dict:
        import json
        
        user_cargo = db.query(CargoRequest).filter(
            CargoRequest.user_id == user_id,
            func.date(CargoRequest.request_date) == target_date
        ).all()
        
        if not user_cargo:
            return {
                "status": "no_cargo",
                "message": "Bu tarihte kargo talebiniz bulunmuyor.",
                "routes": []
            }
        
        user_station_ids = set(c.station_id for c in user_cargo)
        user_station_names = set(c.station.name for c in user_cargo)
        
        all_routes = db.query(Route).filter(Route.route_date == target_date).all()
        
        if not all_routes:
            return {
                "status": "no_routes",
                "message": "Bu tarih için henüz rota planlaması yapılmamış.",
                "routes": [],
                "user_stations": list(user_station_names)
            }
        
        matching_routes = []
        
        for route in all_routes:
            try:
                path_data = json.loads(route.path_data) if isinstance(route.path_data, str) else route.path_data
                path = path_data.get("path", path_data) if isinstance(path_data, dict) else path_data
                
                route_station_ids = set()
                route_station_names = set()
                
                for stop in path:
                    if stop.get("station_id"):
                        route_station_ids.add(stop["station_id"])
                    if stop.get("name"):
                        route_station_names.add(stop["name"])

                matching_stations = user_station_ids.intersection(route_station_ids)

                matching_names_flexible = set()
                for route_name in route_station_names:
                    for user_name in user_station_names:
                        if route_name == user_name:
                            matching_names_flexible.add(user_name)
                        elif route_name.startswith(user_name):
                            matching_names_flexible.add(user_name)
                        elif route_name.split('(')[0].strip() == user_name:
                            matching_names_flexible.add(user_name)
                
                if matching_stations or matching_names_flexible:
                    vehicle_name = route.vehicle.name if route.vehicle else f"Araç {route.vehicle_id}"
                    
                    actual_user_stations_in_route = set()
                    for user_sid in user_station_ids:
                        if user_sid in route_station_ids:
                            for cargo in user_cargo:
                                if cargo.station_id == user_sid:
                                    actual_user_stations_in_route.add(cargo.station.name)
                                    break
                    
                    if not actual_user_stations_in_route:
                        actual_user_stations_in_route = matching_names_flexible
                    
                    matching_routes.append({
                        "route_id": route.id,
                        "vehicle_name": vehicle_name,
                        "vehicle_id": route.vehicle_id,
                        "total_distance": route.total_distance,
                        "total_cost": route.total_cost,
                        "cargo_weight": route.cargo_weight,
                        "cargo_count": route.cargo_count,
                        "path_data": path_data,
                        "scenario_type": route.scenario_type,
                        "user_stations": list(actual_user_stations_in_route)
                    })
            except Exception as e:
                print(f"Error parsing route {route.id}: {e}")
                continue
        
        if not matching_routes:
            return {
                "status": "not_assigned",
                "message": "Kargonuz henüz bir rotaya atanmamış. Lütfen daha sonra tekrar kontrol edin.",
                "routes": [],
                "user_stations": list(user_station_names)
            }
        
        user_cargo_summary = {
            "total_weight": sum(c.weight for c in user_cargo),
            "total_count": sum(c.cargo_count for c in user_cargo),
            "stations": list(user_station_names)
        }
        
        return {
            "status": "success",
            "message": f"Kargonuz {len(matching_routes)} rotada taşınıyor.",
            "routes": matching_routes,
            "user_cargo": user_cargo_summary
        }

    
    def get_available_dates(self, db: Session) -> List[date]:
        results = db.query(func.date(CargoRequest.request_date)).distinct().all()
        return [r[0] for r in results]
    
    def delete_all_routes(self, db: Session) -> Dict:
        route_count = db.query(Route).count()
        
        db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        db.execute(text("TRUNCATE TABLE routes"))
        db.execute(text("TRUNCATE TABLE vehicles"))
        db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        db.commit()
        
        vehicles = [
            Vehicle(name="Kamyon 1", capacity=500.0),
            Vehicle(name="Kamyon 2", capacity=750.0),
            Vehicle(name="Tır 1", capacity=1000.0)
        ]
        db.add_all(vehicles)
        db.commit()
        
        return {
            "status": "success",
            "message": f"{route_count} rota silindi.",
            "deleted_routes": route_count
        }
    
    def get_distance_matrix(self, db: Session) -> Dict:
        stations = db.query(Station).all()
        
        if not stations:
            return {"stations": [], "matrix": []}
        
        matrix_dict = self.build_distance_matrix_osrm(stations)
        
        station_names = [s.name for s in stations]
        station_ids = [s.id for s in stations]
        
        matrix_2d = []
        for from_s in stations:
            row = []
            for to_s in stations:
                if from_s.id == to_s.id:
                    row.append(0)
                else:
                    dist = matrix_dict.get((from_s.id, to_s.id), 0)
                    row.append(round(dist, 2))
            matrix_2d.append(row)
        
        return {
            "stations": station_names,
            "station_ids": station_ids,
            "matrix": matrix_2d
        }

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        try:
            url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            if data.get("code") == "Ok" and data.get("routes"):
                distance_km = data["routes"][0]["distance"] / 1000
                return distance_km
            else:
                return self._haversine_distance(lat1, lon1, lat2, lon2)
        except Exception as e:
            print(f"OSRM error, using Haversine: {e}")
            return self._haversine_distance(lat1, lon1, lat2, lon2)
    
    def build_distance_matrix_osrm(self, stations: List[Station]) -> Dict:
        if not stations:
            return {}
        
        coords = ";".join([f"{s.longitude},{s.latitude}" for s in stations])
        url = f"https://router.project-osrm.org/table/v1/driving/{coords}?annotations=distance"
        
        try:
            response = requests.get(url, timeout=30)
            data = response.json()
            
            if data.get("code") == "Ok" and data.get("distances"):
                distances = data["distances"]
                matrix = {}
                for i, from_station in enumerate(stations):
                    for j, to_station in enumerate(stations):
                        if i != j:
                            dist_km = distances[i][j] / 1000
                            matrix[(from_station.id, to_station.id)] = dist_km
                print(f"OSRM Table API: Built {len(matrix)} distance pairs")
                return matrix
            else:
                print(f"OSRM Table API failed: {data.get('code')}")
                return self._build_haversine_matrix(stations)
        except Exception as e:
            print(f"OSRM Table API error: {e}")
            return self._build_haversine_matrix(stations)
    
    def _build_haversine_matrix(self, stations: List[Station]) -> Dict:
        matrix = {}
        for from_s in stations:
            for to_s in stations:
                if from_s.id != to_s.id:
                    dist = self._haversine_distance(
                        from_s.latitude, from_s.longitude,
                        to_s.latitude, to_s.longitude
                    )
                    matrix[(from_s.id, to_s.id)] = dist
        print(f"Haversine fallback: Built {len(matrix)} distance pairs")
        return matrix
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371  # km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2) * math.sin(dlat/2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dlon/2) * math.sin(dlon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    def get_cargo_by_date(self, db: Session, target_date: date) -> List[CargoRequest]:
        return db.query(CargoRequest).filter(
            func.date(CargoRequest.request_date) == target_date
        ).all()
    
    def aggregate_cargo_by_station(self, requests: List[CargoRequest]) -> Dict:
        cargo_data = {}
        for req in requests:
            sid = req.station_id
            if sid not in cargo_data:
                cargo_data[sid] = {
                    "station": req.station,
                    "total_weight": 0.0,
                    "total_count": 0,
                    "requests": []
                }
            cargo_data[sid]["total_weight"] += req.weight
            cargo_data[sid]["total_count"] += req.cargo_count
            cargo_data[sid]["requests"].append(req)
        return cargo_data
    
    def get_depot_station(self, db: Session) -> Optional[Station]:
        return db.query(Station).filter(Station.name == DEPOT_NAME).first()
    
    def solve_vrp(self, db: Session, target_date: date, scenario_type: str = "unlimited",
                  cost_per_km: float = 1.0, rental_cost: float = 200.0, rental_capacity: float = 500.0,
                  optimization_mode: str = "max_count") -> Dict:
        
        db.query(Route).filter(Route.route_date == target_date).delete()
        db.commit()
        
        requests = self.get_cargo_by_date(db, target_date)
        print(f"📦 Tarih {target_date} için {len(requests)} kargo talebi bulundu")
        for req in requests[:10]:  
            print(f"   - Request ID:{req.id}, Station:{req.station_id}, Weight:{req.weight}, Count:{req.cargo_count}, Date:{req.request_date}")
        if not requests:
            return {
                "status": "error",
                "message": "Bu tarih için kargo talebi bulunamadı.",
                "routes": [],
                "total_cost": 0,
                "total_distance": 0
            }
        
        cargo_data = self.aggregate_cargo_by_station(requests)
        
        depot = self.get_depot_station(db)
        if not depot:
            return {
                "status": "error",
                "message": "Hedef istasyon (Umuttepe) bulunamadı!",
                "routes": [],
                "total_cost": 0,
                "total_distance": 0
            }
        
        cargo_data = {k: v for k, v in cargo_data.items() if v["station"].name != DEPOT_NAME}
        
        if not cargo_data:
            return {
                "status": "error",
                "message": "Teslim edilecek kargo bulunamadı (sadece Umuttepe'de kargo var).",
                "routes": [],
                "total_cost": 0,
                "total_distance": 0
            }
        
        total_cargo_before = sum(c["total_count"] for c in cargo_data.values())
        total_weight_before = sum(c["total_weight"] for c in cargo_data.values())
        
        if scenario_type == "unlimited":
            routes = self.solve_unlimited(db, cargo_data, depot, target_date, cost_per_km, rental_cost, rental_capacity)
            rejected_count = 0
            rejected_weight = 0
        else:
            routes, rejected_count, rejected_weight = self.solve_limited(
                db, cargo_data, depot, target_date, cost_per_km, optimization_mode
            )
        
        total_cost = sum(r.total_cost for r in routes)
        total_distance = sum(r.total_distance for r in routes)
        total_cargo = sum(r.cargo_count for r in routes)
        total_weight = sum(r.cargo_weight for r in routes)
        
        print(f"📊 Sonuç Özeti ({len(routes)} rota):")
        for r in routes:
            print(f"   - Rota ID:{r.id}, Araç:{r.vehicle_id}, Kargo:{r.cargo_count} adet, Ağırlık:{r.cargo_weight} kg")
        print(f"   TOPLAM: {total_cargo} adet, {total_weight} kg")
        
        result = {
            "status": "success",
            "message": f"{len(routes)} rota oluşturuldu.",
            "routes_count": len(routes),
            "total_cost": round(total_cost, 2),
            "total_distance": round(total_distance, 2),
            "total_cargo": total_cargo,
            "total_weight": round(total_weight, 2)
        }
        
        if scenario_type != "unlimited":
            result["rejected_cargo_count"] = rejected_count
            result["rejected_cargo_weight"] = round(rejected_weight, 2)
            result["acceptance_rate_count"] = round((total_cargo / total_cargo_before * 100), 1) if total_cargo_before > 0 else 0
            result["acceptance_rate_weight"] = round((total_weight / total_weight_before * 100), 1) if total_weight_before > 0 else 0
            result["optimization_mode"] = optimization_mode
        
        return result
    
    def solve_unlimited(self, db: Session, cargo_data: Dict, depot: Station, target_date: date,
                         cost_per_km: float, rental_cost: float, rental_capacity: float) -> List[Route]:
        
        all_stations = [cargo_data[sid]["station"] for sid in cargo_data.keys()]
        all_stations.append(depot)
        self.distance_matrix = self.build_distance_matrix_osrm(all_stations)
        
        existing_vehicles = db.query(Vehicle).filter(Vehicle.is_rented == False).order_by(Vehicle.capacity.desc()).all()
        num_existing = len(existing_vehicles) if existing_vehicles else 1
        
        total_cargo_weight = sum(c["total_weight"] for c in cargo_data.values())
        total_capacity = sum(v.capacity for v in existing_vehicles) if existing_vehicles else 0
        
        num_stations = len(cargo_data)
        
        max_vehicle_capacity = max(v.capacity for v in existing_vehicles) if existing_vehicles else rental_capacity
        min_vehicles_needed = max(1, int((total_cargo_weight + max_vehicle_capacity - 1) / max_vehicle_capacity))
        
        min_clusters = min_vehicles_needed
        max_clusters = min(num_stations, max(num_existing, min_vehicles_needed) + 3)
        
        print(f"🔍 Maliyet Optimizasyonu: {min_clusters} - {max_clusters} küme (cluster) konfigürasyonu deneniyor...")
        
        best_config = None
        best_cost = float('inf')
        
        for num_clusters in range(min_clusters, max_clusters + 1):
            simulated_cost = self._simulate_configuration_cost(
                cargo_data, depot, num_clusters, existing_vehicles,
                cost_per_km, rental_cost, rental_capacity
            )
            
            print(f"   📊 {num_clusters} küme: Tahmini maliyet = {simulated_cost:.2f} birim")
            
            if simulated_cost < best_cost:
                best_cost = simulated_cost
                best_config = num_clusters
        
        print(f"✅ En iyi konfigürasyon: {best_config} küme (+ overflow için kiralık), Tahmini Maliyet: {best_cost:.2f} birim")
        
        return self._execute_configuration(
            db, cargo_data, depot, target_date, best_config,
            existing_vehicles, cost_per_km, rental_cost, rental_capacity
        )
    
    def _simulate_configuration_cost(self, cargo_data: Dict, depot: Station, num_clusters: int,
                                      existing_vehicles: List, cost_per_km: float, 
                                      rental_cost: float, rental_capacity: float) -> float:
        if num_clusters == 0:
            return float('inf')
        
        station_ids = list(cargo_data.keys())
        if not station_ids:
            return 0
        
        clusters = self._create_clusters(cargo_data, depot, num_clusters, station_ids.copy())
        clusters.sort(key=lambda x: x["total_weight"], reverse=True)
        
        vehicles_sorted = sorted(existing_vehicles, key=lambda v: v.capacity, reverse=True)
        
        if num_clusters <= len(vehicles_sorted):
            max_cluster_weight = max(c["total_weight"] for c in clusters) if clusters else 0
            max_vehicle_capacity = vehicles_sorted[0].capacity if vehicles_sorted else 0
            
            if max_cluster_weight > max_vehicle_capacity * 1.3:
                alt_clusters = self._create_capacity_aware_clusters(
                    cargo_data, depot, num_clusters, vehicles_sorted
                )
                if alt_clusters is not None:
                    alt_clusters.sort(key=lambda x: x["total_weight"], reverse=True)
                    alt_cost = self._calculate_clusters_cost(
                        alt_clusters, cargo_data, depot, vehicles_sorted, 
                        cost_per_km, rental_cost, rental_capacity
                    )
                    orig_cost = self._calculate_clusters_cost(
                        clusters, cargo_data, depot, vehicles_sorted,
                        cost_per_km, rental_cost, rental_capacity
                    )
                    return min(alt_cost, orig_cost)
        
        total_cost = 0
        overflow_pool = [] 
        
        for i, cluster in enumerate(clusters):
            if i < len(vehicles_sorted):
                vehicle_capacity = vehicles_sorted[i].capacity
            else:
                for sid in cluster["stations"]:
                    overflow_pool.append({
                        "sid": sid,
                        "weight": cargo_data[sid]["total_weight"]
                    })
                continue
            
            remaining_capacity = vehicle_capacity
            cluster_stations = []
            for sid in cluster["stations"]:
                cluster_stations.append({
                    "sid": sid,
                    "weight": cargo_data[sid]["total_weight"]
                })
            cluster_stations.sort(key=lambda x: -x["weight"])
            
            cluster_route_sids = []
            for cs in cluster_stations:
                if cs["weight"] <= remaining_capacity:
                    cluster_route_sids.append(cs["sid"])
                    remaining_capacity -= cs["weight"]
                elif remaining_capacity > 0:
                    cluster_route_sids.append(cs["sid"])
                    overflow_pool.append({
                        "sid": cs["sid"],
                        "weight": cs["weight"] - remaining_capacity
                    })
                    remaining_capacity = 0
                else:
                    overflow_pool.append(cs)
            
            if cluster_route_sids:
                route_dist = self._calculate_simple_route_distance(cluster_route_sids, cargo_data, depot)
                total_cost += route_dist * cost_per_km
        
        if overflow_pool:
            total_overflow = sum(o["weight"] for o in overflow_pool)
            min_rentals_needed = max(1, int((total_overflow + rental_capacity - 1) / rental_capacity))
            
            total_cost += min_rentals_needed * rental_cost
            
            overflow_pool.sort(key=lambda x: -x["weight"])
            rental_bins = [{"sids": [], "remaining": rental_capacity} for _ in range(min_rentals_needed)]
            
            for o in overflow_pool:
                for rb in rental_bins:
                    if o["weight"] <= rb["remaining"]:
                        if o["sid"] not in rb["sids"]:
                            rb["sids"].append(o["sid"])
                        rb["remaining"] -= o["weight"]
                        break
            
            for rb in rental_bins:
                if rb["sids"]:
                    route_dist = self._calculate_simple_route_distance(rb["sids"], cargo_data, depot)
                    total_cost += route_dist * cost_per_km
        
        return total_cost
    
    def _calculate_clusters_cost(self, clusters: List[Dict], cargo_data: Dict, depot: Station,
                                 vehicles_sorted: List, cost_per_km: float, 
                                 rental_cost: float, rental_capacity: float) -> float:
        total_cost = 0
        overflow_pool = []
        
        for i, cluster in enumerate(clusters):
            if i < len(vehicles_sorted):
                vehicle_capacity = vehicles_sorted[i].capacity
            else:
                for sid in cluster["stations"]:
                    overflow_pool.append({
                        "sid": sid,
                        "weight": cargo_data[sid]["total_weight"]
                    })
                continue
            
            remaining_capacity = vehicle_capacity
            cluster_stations = []
            for sid in cluster["stations"]:
                cluster_stations.append({
                    "sid": sid,
                    "weight": cargo_data[sid]["total_weight"]
                })
            cluster_stations.sort(key=lambda x: -x["weight"])
            
            cluster_route_sids = []
            for cs in cluster_stations:
                if cs["weight"] <= remaining_capacity:
                    cluster_route_sids.append(cs["sid"])
                    remaining_capacity -= cs["weight"]
                elif remaining_capacity > 0:
                    cluster_route_sids.append(cs["sid"])
                    overflow_pool.append({
                        "sid": cs["sid"],
                        "weight": cs["weight"] - remaining_capacity
                    })
                    remaining_capacity = 0
                else:
                    overflow_pool.append(cs)
            
            if cluster_route_sids:
                route_dist = self._calculate_simple_route_distance(cluster_route_sids, cargo_data, depot)
                total_cost += route_dist * cost_per_km
        
        if overflow_pool:
            total_overflow = sum(o["weight"] for o in overflow_pool)
            min_rentals_needed = max(1, int((total_overflow + rental_capacity - 1) / rental_capacity))
            
            total_cost += min_rentals_needed * rental_cost
            
            overflow_pool.sort(key=lambda x: -x["weight"])
            rental_bins = [{"sids": [], "remaining": rental_capacity} for _ in range(min_rentals_needed)]
            
            for o in overflow_pool:
                for rb in rental_bins:
                    if o["weight"] <= rb["remaining"]:
                        if o["sid"] not in rb["sids"]:
                            rb["sids"].append(o["sid"])
                        rb["remaining"] -= o["weight"]
                        break
            
            for rb in rental_bins:
                if rb["sids"]:
                    route_dist = self._calculate_simple_route_distance(rb["sids"], cargo_data, depot)
                    total_cost += route_dist * cost_per_km
        
        return total_cost
    
    def _calculate_simple_route_distance(self, station_ids: List[int], cargo_data: Dict, depot: Station) -> float:
        if not station_ids:
            return 0
        
        ordered = self._order_stations_nn(station_ids, cargo_data, depot)
        ordered = self._quick_2opt(ordered, cargo_data, depot)
        
        total_dist = self._get_dist(depot.id, ordered[0], cargo_data, depot)
        for i in range(len(ordered) - 1):
            total_dist += self._get_dist(ordered[i], ordered[i+1], cargo_data)
        total_dist += self._get_dist(ordered[-1], depot.id, cargo_data, depot)
        
        return total_dist
    
    def _create_clusters(self, cargo_data: Dict, depot: Station, num_clusters: int, 
                         unvisited: List) -> List[Dict]:
        clusters = []
        used_seeds = []
        
        for _ in range(num_clusters):
            if not unvisited:
                break
            
            candidates = []
            for sid in unvisited:
                d = self._get_dist(sid, depot.id, cargo_data, depot)
                candidates.append((sid, d))
            candidates.sort(key=lambda x: x[1], reverse=True)
            
            buffer = 25.0 if num_clusters <= 3 else 15.0
            seed = None
            for sid, _ in candidates:
                valid = True
                for us in used_seeds:
                    if self._get_dist(sid, us, cargo_data) < buffer:
                        valid = False
                        break
                if valid:
                    seed = sid
                    break
            
            if seed is None:
                seed = candidates[0][0]
            
            used_seeds.append(seed)
            clusters.append({
                "seed_sid": seed,
                "stations": [seed],
                "total_weight": cargo_data[seed]["total_weight"]
            })
            unvisited.remove(seed)
        
        while unvisited:
            best_choice = None
            min_detour = float('inf')
            
            for sid in unvisited:
                for c_idx, cluster in enumerate(clusters):
                    seed_sid = cluster["seed_sid"]
                    d_seed_st = self._get_dist(seed_sid, sid, cargo_data)
                    d_st_depot = self._get_dist(sid, depot.id, cargo_data, depot)
                    d_seed_depot = self._get_dist(seed_sid, depot.id, cargo_data, depot)
                    detour = d_seed_st + d_st_depot - d_seed_depot
                    
                    if detour < min_detour:
                        min_detour = detour
                        best_choice = (sid, c_idx)
            

            if best_choice:
                sid, c_idx = best_choice

                clusters[c_idx]["stations"].append(sid)
                clusters[c_idx]["total_weight"] += cargo_data[sid]["total_weight"]
                unvisited.remove(sid)
            else:
                break
        
        return clusters
    
    def _create_capacity_aware_clusters(self, cargo_data: Dict, depot: Station, 
                                        num_clusters: int, vehicles_sorted: List) -> List[Dict]:
        if num_clusters > len(vehicles_sorted):
            return None
        
        vehicle_capacities = [v.capacity for v in vehicles_sorted[:num_clusters]]
        
        station_ids = list(cargo_data.keys())
        total_weight = sum(cargo_data[sid]["total_weight"] for sid in station_ids)
        
        if total_weight > sum(vehicle_capacities):
            return None

        clusters = []
        for i in range(num_clusters):
            clusters.append({
                "seed_sid": None,
                "stations": [],
                "total_weight": 0,
                "capacity": vehicle_capacities[i]
            })
        
        stations_by_distance = []
        for sid in station_ids:
            d = self._get_dist(sid, depot.id, cargo_data, depot)
            w = cargo_data[sid]["total_weight"]
            stations_by_distance.append((sid, d, w))
        stations_by_distance.sort(key=lambda x: x[1], reverse=True)
        
        used_seeds = []
        unassigned = [x[0] for x in stations_by_distance]
        
        for i, cluster in enumerate(clusters):
            best_seed = None
            for sid, dist, weight in stations_by_distance:
                if sid not in unassigned:
                    continue
                if weight > cluster["capacity"]:
                    continue  
                
                min_dist_to_seeds = float('inf')
                for used in used_seeds:
                    d = self._get_dist(sid, used, cargo_data)
                    if d < min_dist_to_seeds:
                        min_dist_to_seeds = d
                
                if not used_seeds or min_dist_to_seeds > 15: 
                    best_seed = sid
                    break
            
            if best_seed is None:
                for sid in unassigned:
                    if cargo_data[sid]["total_weight"] <= cluster["capacity"]:
                        best_seed = sid
                        break
            
            if best_seed:
                cluster["seed_sid"] = best_seed
                cluster["stations"].append(best_seed)
                cluster["total_weight"] = cargo_data[best_seed]["total_weight"]
                unassigned.remove(best_seed)
                used_seeds.append(best_seed)
        
        while unassigned:
            best_assignment = None
            best_score = float('inf') 
            
            for sid in unassigned:
                station_weight = cargo_data[sid]["total_weight"]
                
                for c_idx, cluster in enumerate(clusters):
                    if cluster["total_weight"] + station_weight > cluster["capacity"]:
                        continue
                    
                    if cluster["seed_sid"]:
                        seed_sid = cluster["seed_sid"]
                        d_seed_st = self._get_dist(seed_sid, sid, cargo_data)
                        d_st_depot = self._get_dist(sid, depot.id, cargo_data, depot)
                        d_seed_depot = self._get_dist(seed_sid, depot.id, cargo_data, depot)
                        detour = d_seed_st + d_st_depot - d_seed_depot
                    else:
                        detour = self._get_dist(sid, depot.id, cargo_data, depot)
                    
                    if detour < best_score:
                        best_score = detour
                        best_assignment = (sid, c_idx)
            
            if best_assignment is None:
                print(f"         ❌ Kalan {len(unassigned)} istasyon atanamadı")
                return None
            
            sid, c_idx = best_assignment
            clusters[c_idx]["stations"].append(sid)
            clusters[c_idx]["total_weight"] += cargo_data[sid]["total_weight"]
            unassigned.remove(sid)
        
        for i, cluster in enumerate(clusters):
            if cluster["total_weight"] > cluster["capacity"]:
                return None

        for cluster in clusters:
            del cluster["capacity"]
        
        return clusters
    
    def _calculate_cluster_route_distance(self, cluster: Dict, cargo_data: Dict, depot: Station) -> float:
        stations = cluster["stations"]
        if not stations:
            return 0
        
        ordered = []
        remaining = stations.copy()
        current_id = depot.id
        
        while remaining:
            nearest = None
            min_dist = float('inf')
            for sid in remaining:
                d = self._get_dist(current_id, sid, cargo_data, depot)
                if d < min_dist:
                    min_dist = d
                    nearest = sid
            if nearest:
                ordered.append(nearest)
                remaining.remove(nearest)
                current_id = nearest
        
        ordered = self._quick_2opt(ordered, cargo_data, depot)
        
        total_dist = 0
        prev_id = depot.id
        for sid in ordered:
            total_dist += self._get_dist(prev_id, sid, cargo_data, depot)
            prev_id = sid
        
        total_dist += self._get_dist(prev_id, depot.id, cargo_data, depot)
        
        return total_dist
    
    def _execute_configuration(self, db: Session, cargo_data: Dict, depot: Station, 
                               target_date: date, num_clusters: int, existing_vehicles: List,
                               cost_per_km: float, rental_cost: float, rental_capacity: float) -> List[Route]:
        
        final_routes = []
        station_ids = list(cargo_data.keys())
        
        clusters = self._create_clusters(cargo_data, depot, num_clusters, station_ids.copy())
        clusters.sort(key=lambda x: x["total_weight"], reverse=True)
        
        vehicles_sorted = sorted(existing_vehicles, key=lambda v: v.capacity, reverse=True)
        
        if num_clusters <= len(vehicles_sorted) and clusters:
            max_cluster_weight = max(c["total_weight"] for c in clusters)
            max_vehicle_capacity = vehicles_sorted[0].capacity if vehicles_sorted else 0
            
            if max_cluster_weight > max_vehicle_capacity * 1.3:
                alt_clusters = self._create_capacity_aware_clusters(
                    cargo_data, depot, num_clusters, vehicles_sorted
                )
                if alt_clusters is not None:
                    alt_clusters.sort(key=lambda x: x["total_weight"], reverse=True)
                    clusters = alt_clusters 
        
        assignments = []  
        overflow_pool = []  
        
        for i, cluster in enumerate(clusters):
            if i < len(vehicles_sorted):
                vehicle = vehicles_sorted[i]
                vehicle_capacity = vehicle.capacity
            else:
                for sid in cluster["stations"]:
                    overflow_pool.append({
                        "sid": sid,
                        "weight": cargo_data[sid]["total_weight"],
                        "count": cargo_data[sid]["total_count"],
                        "station": cargo_data[sid]["station"]
                    })
                continue
            
            vehicle_assignments = []
            remaining_capacity = vehicle_capacity
            
            cluster_stations = []
            for sid in cluster["stations"]:
                cluster_stations.append({
                    "sid": sid,
                    "weight": cargo_data[sid]["total_weight"],
                    "count": cargo_data[sid]["total_count"],
                    "station": cargo_data[sid]["station"]
                })
            cluster_stations.sort(key=lambda x: -x["weight"])
            
            for cs in cluster_stations:
                if cs["weight"] <= remaining_capacity:
                    vehicle_assignments.append(cs)
                    remaining_capacity -= cs["weight"]
                elif remaining_capacity > 0:
                    portion = remaining_capacity / cs["weight"]
                    partial_count = max(1, int(cs["count"] * portion))
                    
                    vehicle_assignments.append({
                        "sid": cs["sid"],
                        "weight": remaining_capacity,
                        "count": partial_count,
                        "station": cs["station"],
                        "is_partial": True
                    })
                    
                    overflow_pool.append({
                        "sid": cs["sid"],
                        "weight": cs["weight"] - remaining_capacity,
                        "count": cs["count"] - partial_count,
                        "station": cs["station"],
                        "is_partial": True
                    })
                    remaining_capacity = 0
                else:
                    overflow_pool.append(cs)
            
            if vehicle_assignments:
                assignments.append({
                    "vehicle": vehicle,
                    "cargo_list": vehicle_assignments
                })
        
        if overflow_pool:
            overflow_pool.sort(key=lambda x: -x["weight"])

            for assign in assignments:
                vehicle = assign["vehicle"]
                current_weight = sum(c["weight"] for c in assign["cargo_list"])
                remaining_cap = vehicle.capacity - current_weight
                
                if remaining_cap > 0:
                    still_overflow = []
                    for ov in overflow_pool:
                        if ov["weight"] <= remaining_cap:
                            assign["cargo_list"].append(ov)
                            remaining_cap -= ov["weight"]
                        else:
                            still_overflow.append(ov)
                    overflow_pool = still_overflow
                    
                    if not overflow_pool:
                        break  
            
            if overflow_pool:
                total_overflow = sum(o["weight"] for o in overflow_pool)
                min_rentals_needed = max(1, int((total_overflow + rental_capacity - 1) / rental_capacity))
                
                print(f"   📦 Overflow: {total_overflow:.1f} kg | {min_rentals_needed} kiralık araç gerekli")
                print(f"   🚚 Toplam Araç: {len(assignments)} mevcut + {min_rentals_needed} kiralık = {len(assignments) + min_rentals_needed} araç")
                
                rental_vehicles = []
                rental_counter = 1
                for _ in range(min_rentals_needed):
                    rv = Vehicle(
                        name=f"Kiralık Araç {rental_counter}",
                        capacity=rental_capacity,
                        is_rented=True,
                        rental_cost=rental_cost
                    )
                    db.add(rv)
                    db.commit()
                    db.refresh(rv)
                    rental_vehicles.append(rv)
                    rental_counter += 1

                rental_assignments = [{
                    "vehicle": rv,
                    "cargo_list": [],
                    "remaining_capacity": rental_capacity
                } for rv in rental_vehicles]
                
                for overflow_item in overflow_pool:
                    assigned = False
                    for ra in rental_assignments:
                        if overflow_item["weight"] <= ra["remaining_capacity"]:
                            ra["cargo_list"].append(overflow_item)
                            ra["remaining_capacity"] -= overflow_item["weight"]
                            assigned = True
                            break
                    
                    if not assigned:
                        rv = Vehicle(
                            name=f"Kiralık Araç {rental_counter}",
                            capacity=rental_capacity,
                            is_rented=True,
                            rental_cost=rental_cost
                        )
                        db.add(rv)
                        db.commit()
                        db.refresh(rv)
                        rental_counter += 1
                        
                        rental_assignments.append({
                            "vehicle": rv,
                            "cargo_list": [overflow_item],
                            "remaining_capacity": rental_capacity - overflow_item["weight"]
                        })

                for ra in rental_assignments:
                    if ra["cargo_list"]:
                        assignments.append({
                            "vehicle": ra["vehicle"],
                            "cargo_list": ra["cargo_list"]
                        })
        

        has_partial_splits = any(
            any(c.get("is_partial") for c in assign["cargo_list"])
            for assign in assignments
        )
        
        if len(assignments) >= 2 and not has_partial_splits:
            print("   🔀 Inter-route optimizasyonu uygulanıyor...")
        elif has_partial_splits:
            print("   ⚠️ Parçalı kargo mevcut - Inter-route optimizasyonu atlandı")
        
        if len(assignments) >= 2 and not has_partial_splits:
            vehicle_bins_for_iro = []
            for assign in assignments:
                vehicle = assign["vehicle"]
                cargo_list = assign["cargo_list"]
                stations = list(set(c["sid"] for c in cargo_list))
                total_weight = sum(c["weight"] for c in cargo_list)
                total_count = sum(c["count"] for c in cargo_list)
                vehicle_bins_for_iro.append({
                    "vehicle": vehicle,
                    "stations": stations,
                    "total_weight": total_weight,
                    "total_count": total_count
                })
            
            vehicle_bins_for_iro = self._inter_route_optimization(vehicle_bins_for_iro, cargo_data, depot, cost_per_km)
            
            for i, vbin in enumerate(vehicle_bins_for_iro):
                if i < len(assignments):
                    new_cargo_list = []
                    for sid in vbin["stations"]:
                        station = cargo_data[sid]["station"]
                        weight = cargo_data[sid]["total_weight"]
                        count = cargo_data[sid]["total_count"]
                        new_cargo_list.append({
                            "sid": sid,
                            "station": station,
                            "weight": weight,
                            "count": count
                        })
                    assignments[i]["cargo_list"] = new_cargo_list
            
            active_routes = sum(1 for a in assignments if a["cargo_list"])
            if active_routes < len(vehicle_bins_for_iro):
                print(f"   📊 Rota konsolidasyonu: {len(vehicle_bins_for_iro)} küme → {active_routes} aktif rota")
        
        for assign in assignments:
            vehicle = assign["vehicle"]
            cargo_list = assign["cargo_list"]
            
            if not cargo_list:
                continue
            
            station_sids = [c["sid"] for c in cargo_list]
            
            vehicle_cargo = {}
            for c in cargo_list:
                sid = c["sid"]
                if sid not in vehicle_cargo:
                    vehicle_cargo[sid] = {
                        "station": c["station"],
                        "total_weight": c["weight"],
                        "total_count": c["count"]
                    }
                else:
                    vehicle_cargo[sid]["total_weight"] += c["weight"]
                    vehicle_cargo[sid]["total_count"] += c["count"]
            
            unique_sids = list(vehicle_cargo.keys())
            ordered_stations = self._order_stations_nn(unique_sids, cargo_data, depot)
            
            ordered_stations = self._optimize_route_2opt(ordered_stations, vehicle_cargo, depot)
            
            route_path = []
            route_logs = []
            route_dist = 0
            route_weight = 0
            route_count = 0
            
            total_assigned = sum(c["weight"] for c in cargo_list)
            route_logs.append(f"ℹ️ Rota Planı: Toplam {total_assigned:.1f} kg yük için {vehicle.name} ({vehicle.capacity} kg) atandı.")
            
            if vehicle.is_rented:
                route_logs.append(f"💰 Kiralık Araç Maliyeti: {rental_cost} birim eklendi.")
            
            route_path.append({
                "station_id": depot.id,
                "lat": depot.latitude,
                "lon": depot.longitude,
                "name": depot.name,
                "weight": 0,
                "count": 0,
                "is_depot": True,
                "is_start": True
            })
            route_logs.append(f"🚀 Başlangıç: {depot.name} (Depo)")
            
            current_sid = depot.id
            
            for sid in ordered_stations:
                station = vehicle_cargo[sid]["station"]
                weight = vehicle_cargo[sid]["total_weight"]
                count = vehicle_cargo[sid]["total_count"]
                
                dist = self._get_dist(current_sid, sid, cargo_data, depot)
                route_dist += dist
                route_weight += weight
                route_count += count
                
                station_name = station.name
                if any(c.get("is_partial") for c in cargo_list if c["sid"] == sid):
                    station_name = f"{station.name} (Parça)"
                
                route_path.append({
                    "station_id": sid,
                    "lat": station.latitude,
                    "lon": station.longitude,
                    "name": station_name,
                    "weight": weight,
                    "count": count
                })
                
                remaining_cap = vehicle.capacity - route_weight
                if current_sid == depot.id:
                    route_logs.append(f"✅ Gidilen İstasyon: {station_name} | Mesafe: {dist:.2f} km (Depodan) | Toplam Yol: {route_dist:.2f} km | Alınan Yük: {weight:.1f} kg | Kalan Kapasite: {remaining_cap:.1f} kg")
                else:
                    route_logs.append(f"✅ Gidilen İstasyon: {station_name} | Mesafe: {dist:.2f} km | Toplam Yol: {route_dist:.2f} km | Alınan Yük: {weight:.1f} kg | Kalan Kapasite: {remaining_cap:.1f} kg")
                
                current_sid = sid
            
            return_dist = self._get_dist(current_sid, depot.id, cargo_data, depot)
            route_dist += return_dist
            
            route_logs.append(f"🏁 Hedefe (Umuttepe) Gidiliyor. Son Mesafe: {return_dist:.2f} km | Toplam Yol: {route_dist:.2f} km")
            
            route_path.append({
                "station_id": depot.id,
                "lat": depot.latitude,
                "lon": depot.longitude,
                "name": depot.name,
                "weight": 0,
                "count": 0,
                "is_depot": True
            })
            
            total_cost = route_dist * cost_per_km
            if vehicle.is_rented:
                total_cost += rental_cost
            
            route = Route(
                vehicle_id=vehicle.id,
                path_data=json.dumps({"path": route_path, "logs": route_logs}),
                total_distance=round(route_dist, 2),
                total_cost=round(total_cost, 2),
                route_date=target_date,
                scenario_type="unlimited",
                cargo_weight=round(route_weight, 2),
                cargo_count=route_count
            )
            db.add(route)
            db.commit()
            final_routes.append(route)
        
        return final_routes
    
    def _optimize_route_2opt(self, route: List[int], cargo_data: Dict, depot: Station) -> List[int]:
        if len(route) <= 2:
            return route  
        
        def calculate_total_distance(r):
            if not r:
                return 0
            total = self._get_dist(depot.id, r[0], cargo_data, depot)  
            for i in range(len(r) - 1):
                total += self._get_dist(r[i], r[i+1], cargo_data)
            total += self._get_dist(r[-1], depot.id, cargo_data, depot)  
            return total
        
        best = route.copy()
        best_distance = calculate_total_distance(best)
        initial_distance = best_distance
        improved = True
        iterations = 0
        max_iterations = 100  
        
        while improved and iterations < max_iterations:
            improved = False
            iterations += 1
            
            for i in range(len(best) - 1):
                for j in range(i + 2, len(best)):
                    new_route = best[:i+1] + best[i+1:j+1][::-1] + best[j+1:]
                    new_distance = calculate_total_distance(new_route)
                    
                    if new_distance < best_distance - 0.01:
                        best = new_route
                        best_distance = new_distance
                        improved = True
                        break
                if improved:
                    break
        
        if best_distance < calculate_total_distance(route):
            improvement = calculate_total_distance(route) - best_distance
            print(f"   🔄 2-opt: Rota iyileştirildi! {improvement:.2f} km tasarruf.")
        
        or_opt_improved = True
        or_iterations = 0
        while or_opt_improved and or_iterations < 50:
            or_opt_improved = False
            or_iterations += 1
            
            for i in range(len(best)):
                station = best[i]
                current_dist = calculate_total_distance(best)
                
                for j in range(len(best) + 1):
                    if j == i or j == i + 1:
                        continue
                    
                    new_route = best[:i] + best[i+1:] 
                    if j > i:
                        new_route = new_route[:j-1] + [station] + new_route[j-1:]
                    else:
                        new_route = new_route[:j] + [station] + new_route[j:]
                    
                    new_dist = calculate_total_distance(new_route)
                    
                    if new_dist < best_distance - 0.1:
                        improvement = best_distance - new_dist
                        print(f"      📍 Or-opt: İstasyon {i+1} → pozisyon {j+1}, {improvement:.2f} km tasarruf")
                        best = new_route
                        best_distance = new_dist
                        or_opt_improved = True
                        break
                
                if or_opt_improved:
                    break
        
        if or_iterations > 1:
            print(f"   🔄 Or-opt: Toplam {or_iterations} iyileştirme yapıldı")
        
        return best
    
    def _quick_2opt(self, route: List[int], cargo_data: Dict, depot: Station) -> List[int]:
        if len(route) <= 2:
            return route
        
        def calc_dist(r):
            if not r:
                return 0
            total = self._get_dist(depot.id, r[0], cargo_data, depot)
            for i in range(len(r) - 1):
                total += self._get_dist(r[i], r[i+1], cargo_data)
            total += self._get_dist(r[-1], depot.id, cargo_data, depot)
            return total
        
        best = route.copy()
        best_dist = calc_dist(best)
        
        for i in range(len(best) - 1):
            for j in range(i + 2, len(best)):
                new_route = best[:i+1] + best[i+1:j+1][::-1] + best[j+1:]
                new_dist = calc_dist(new_route)
                if new_dist < best_dist - 0.01:
                    best = new_route
                    best_dist = new_dist
        
        return best
    
    def _inter_route_optimization(self, routes_data: List[Dict], cargo_data: Dict, 
                                   depot: Station, cost_per_km: float = 1.0) -> List[Dict]:
        if len(routes_data) < 2:
            return routes_data  
        
        def calc_route_distance(station_ids):
            if not station_ids:
                return 0
            total = self._get_dist(depot.id, station_ids[0], cargo_data, depot)
            for i in range(len(station_ids) - 1):
                total += self._get_dist(station_ids[i], station_ids[i+1], cargo_data)
            total += self._get_dist(station_ids[-1], depot.id, cargo_data, depot)
            return total
        
        routes = []
        for rd in routes_data:
            routes.append({
                "vehicle": rd.get("vehicle"),
                "capacity": rd.get("vehicle").capacity if rd.get("vehicle") else rd.get("capacity", 1000),
                "stations": list(rd.get("stations", [])),
                "total_weight": rd.get("total_weight", 0),
                "total_count": rd.get("total_count", 0)
            })
        
        improved = True
        total_improvement = 0
        iteration = 0
        max_iterations = 50  
        
        while improved and iteration < max_iterations:
            improved = False
            iteration += 1
            
            for i, route_a in enumerate(routes):
                if not route_a["stations"]:
                    continue
                
                for sid_idx, sid in enumerate(route_a["stations"].copy()):
                    station_weight = cargo_data[sid]["total_weight"]
                    station_count = cargo_data[sid]["total_count"]
                    
                    current_dist_a = calc_route_distance(route_a["stations"])
                    
                    best_move = None
                    best_savings = 0
                    
                    for j, route_b in enumerate(routes):
                        if i == j:
                            continue
                        
                        if route_b["total_weight"] + station_weight > route_b["capacity"]:
                            continue
                        
                        new_stations_a = [s for s in route_a["stations"] if s != sid]
                        new_stations_b = route_b["stations"] + [sid]
                        
                        if new_stations_a:
                            new_stations_a = self._quick_2opt(new_stations_a, cargo_data, depot)
                        new_stations_b = self._quick_2opt(new_stations_b, cargo_data, depot)
                        
                        new_dist_a = calc_route_distance(new_stations_a)
                        new_dist_b = calc_route_distance(new_stations_b)
                        current_dist_b = calc_route_distance(route_b["stations"])
                        
                        old_total = current_dist_a + current_dist_b
                        new_total = new_dist_a + new_dist_b
                        savings = old_total - new_total
                        
                        if savings > 0.5:
                            if savings > best_savings:
                                best_savings = savings
                                best_move = {
                                    "from_route": i,
                                    "to_route": j,
                                    "sid": sid,
                                    "new_stations_a": new_stations_a,
                                    "new_stations_b": new_stations_b,
                                    "weight": station_weight,
                                    "count": station_count
                                }
                    
                    if best_move:
                        from_r = routes[best_move["from_route"]]
                        to_r = routes[best_move["to_route"]]
                        
                        from_r["stations"] = best_move["new_stations_a"]
                        to_r["stations"] = best_move["new_stations_b"]
                        
                        from_r["total_weight"] -= best_move["weight"]
                        to_r["total_weight"] += best_move["weight"]
                        from_r["total_count"] -= best_move["count"]
                        to_r["total_count"] += best_move["count"]
                        
                        total_improvement += best_savings
                        improved = True
                        break  
                
                if improved:
                    break
        
        if total_improvement > 0:
            print(f"   🔀 Inter-route optimizasyonu: {total_improvement:.2f} km tasarruf ({iteration} iterasyon)")
        
        for idx, rd in enumerate(routes_data):
            if idx < len(routes):
                rd["stations"] = routes[idx]["stations"]
                rd["total_weight"] = routes[idx]["total_weight"]
                rd["total_count"] = routes[idx]["total_count"]
        
        return routes_data
    
    def _create_agent(self, vehicle):
        return {
            "vehicle": vehicle,
            "start_sid": None,
            "assigned_sids": [],
            "remaining_cap": vehicle.capacity,
            "total_weight": 0.0,
            "total_count": 0,
            "logs": [],
            "path": [],
            "active": True
        }

    def _get_dist(self, sid1, sid2, cargo_data, depot=None):
        id1 = sid1
        id2 = sid2
        
        station1 = depot if depot and sid1 == depot.id else cargo_data[sid1]["station"]
        station2 = depot if depot and sid2 == depot.id else cargo_data[sid2]["station"]
        
        dist = self.distance_matrix.get((id1, id2), 0)
        if dist == 0 and id1 != id2:
             dist = self._haversine_distance(station1.latitude, station1.longitude, station2.latitude, station2.longitude)
        return dist
    
    def solve_limited(self, db: Session, cargo_data: Dict, depot: Station, target_date: date,
                       cost_per_km: float = 1.0, optimization_mode: str = "max_count") -> tuple:
        final_routes = []
        
        all_stations = [cargo_data[sid]["station"] for sid in cargo_data.keys()]
        all_stations.append(depot)
        self.distance_matrix = self.build_distance_matrix_osrm(all_stations)
        
        existing_vehicles = db.query(Vehicle).filter(Vehicle.is_rented == False).order_by(Vehicle.capacity.desc()).all()
        
        if not existing_vehicles:
            total_rejected_count = sum(c["total_count"] for c in cargo_data.values())
            total_rejected_weight = sum(c["total_weight"] for c in cargo_data.values())
            return [], total_rejected_count, total_rejected_weight
        
        total_fleet_capacity = sum(v.capacity for v in existing_vehicles)
        total_cargo_weight = sum(c["total_weight"] for c in cargo_data.values())
        total_cargo_count = sum(c["total_count"] for c in cargo_data.values())
        num_vehicles = len(existing_vehicles)
        
        print(f"📊 Sınırlı Araç: {num_vehicles} araç, {total_fleet_capacity} kg kapasite")
        print(f"📦 Toplam Kargo: {total_cargo_count} adet, {total_cargo_weight} kg")
        
        capacity_sufficient = total_cargo_weight <= total_fleet_capacity
        
        if capacity_sufficient:
            print(f"✅ Kapasite yeterli! Coğrafi kümeleme ile minimum maliyet hedefleniyor...")
            vehicle_bins = self._assign_by_geographic_clustering(
                cargo_data, depot, existing_vehicles, cost_per_km
            )
            rejected_stations = []
        else:
            print(f"⚠️ Kapasite yetersiz! Best Fit Decreasing ile maksimum kargo hedefleniyor...")
            vehicle_bins, rejected_stations = self._assign_by_best_fit(
                cargo_data, existing_vehicles, optimization_mode
            )
        
        rejected_count = sum(cargo_data[sid]["total_count"] for sid in rejected_stations)
        rejected_weight = sum(cargo_data[sid]["total_weight"] for sid in rejected_stations)
        
        accepted_weight = total_cargo_weight - rejected_weight
        print(f"✅ Kabul: {total_cargo_count - rejected_count} adet, {accepted_weight:.1f} kg")
        if rejected_stations:
            print(f"❌ Red: {rejected_count} adet, {rejected_weight:.1f} kg")
        
        initial_routes = len([v for v in vehicle_bins if v.get("stations")])
        vehicle_bins = self._inter_route_optimization(vehicle_bins, cargo_data, depot, cost_per_km)
        active_routes = len([v for v in vehicle_bins if v.get("stations")])
        if active_routes < initial_routes:
            print(f"   📊 Rota konsolidasyonu: {initial_routes} → {active_routes} aktif rota")
        
        for vbin in vehicle_bins:
            vehicle = vbin["vehicle"]
            stations_to_visit = vbin["stations"]
            station_assignments = vbin.get("station_assignments", [])
            
            if not stations_to_visit:
                continue
            
            assignment_lookup = {}
            for assign in station_assignments:
                sid = assign["sid"]
                if sid not in assignment_lookup:
                    assignment_lookup[sid] = {"weight": 0, "count": 0, "is_partial": False}
                assignment_lookup[sid]["weight"] += assign["weight"]
                assignment_lookup[sid]["count"] += assign["count"]
                if assign.get("is_partial"):
                    assignment_lookup[sid]["is_partial"] = True
            
            vehicle_cargo_data = {}
            for sid in stations_to_visit:
                vehicle_cargo_data[sid] = cargo_data[sid]
            
            ordered_stations = self._order_stations_nn(stations_to_visit, cargo_data, depot)
            
            ordered_stations = self._optimize_route_2opt(ordered_stations, vehicle_cargo_data, depot)
            
            route_path = []
            route_logs = []
            route_distance = 0
            route_weight = 0
            route_count = 0
            
            route_logs.append(f"ℹ️ Araç: {vehicle.name} | Kapasite: {vehicle.capacity} kg | Atanan Yük: {vbin['total_weight']:.1f} kg")
            route_logs.append(f"📋 Optimizasyon Modu: {'Maksimum Kargo Sayısı' if optimization_mode == 'max_count' else 'Maksimum Kargo Ağırlığı'}")
            
            route_path.append({
                "station_id": depot.id,
                "lat": depot.latitude,
                "lon": depot.longitude,
                "name": depot.name,
                "weight": 0,
                "count": 0,
                "is_depot": True,
                "is_start": True
            })
            route_logs.append(f"🚀 Başlangıç: {depot.name} (Depo)")
            
            current_sid = depot.id
            
            for sid in ordered_stations:
                station = cargo_data[sid]["station"]

                if sid in assignment_lookup:
                    weight = assignment_lookup[sid]["weight"]
                    count = assignment_lookup[sid]["count"]
                    is_partial = assignment_lookup[sid]["is_partial"]
                else:
                    weight = cargo_data[sid]["total_weight"]
                    count = cargo_data[sid]["total_count"]
                    is_partial = False
                
                dist = self._get_dist(current_sid, sid, cargo_data, depot)
                route_distance += dist
                route_weight += weight
                route_count += count
                
                station_name = station.name
                if is_partial:
                    station_name = f"{station.name} (Parça)"
                
                route_path.append({
                    "station_id": sid,
                    "lat": station.latitude,
                    "lon": station.longitude,
                    "name": station_name,
                    "weight": weight,
                    "count": count
                })
                
                remaining_cap = vehicle.capacity - route_weight
                if current_sid == depot.id:
                    route_logs.append(f"✅ Gidilen İstasyon: {station_name} | Mesafe: {dist:.2f} km (Depodan) | Toplam Yol: {route_distance:.2f} km | Alınan Yük: {weight:.1f} kg | Kalan Kapasite: {remaining_cap:.1f} kg")
                else:
                    route_logs.append(f"✅ Gidilen İstasyon: {station_name} | Mesafe: {dist:.2f} km | Toplam Yol: {route_distance:.2f} km | Alınan Yük: {weight:.1f} kg | Kalan Kapasite: {remaining_cap:.1f} kg")
                
                current_sid = sid

            return_dist = self._get_dist(current_sid, depot.id, cargo_data, depot)
            route_distance += return_dist
            
            route_logs.append(f"🏁 Hedefe (Umuttepe) Gidiliyor. Son Mesafe: {return_dist:.2f} km | Toplam Yol: {route_distance:.2f} km")
            
            route_path.append({
                "station_id": depot.id,
                "lat": depot.latitude,
                "lon": depot.longitude,
                "name": depot.name,
                "weight": 0,
                "count": 0,
                "is_depot": True
            })
            
            total_cost = route_distance * cost_per_km
            route_logs.append(f"💰 Toplam Maliyet: {total_cost:.2f} birim (Kiralama maliyeti yok)")
            
            route = Route(
                vehicle_id=vehicle.id,
                path_data=json.dumps({"path": route_path, "logs": route_logs}),
                total_distance=round(route_distance, 2),
                total_cost=round(total_cost, 2),
                route_date=target_date,
                scenario_type=f"limited_{optimization_mode}",
                cargo_weight=round(route_weight, 2),
                cargo_count=route_count
            )
            db.add(route)
            db.commit()
            final_routes.append(route)
        
        return final_routes, rejected_count, rejected_weight
    
    def _assign_by_geographic_clustering(self, cargo_data: Dict, depot: Station, 
                                          existing_vehicles: List, cost_per_km: float) -> List[Dict]:
        num_vehicles = len(existing_vehicles)
        station_ids = list(cargo_data.keys())
        total_cargo_weight = sum(c["total_weight"] for c in cargo_data.values())
        
        vehicles_sorted = sorted(existing_vehicles, key=lambda v: v.capacity, reverse=True)
        max_vehicle_capacity = vehicles_sorted[0].capacity if vehicles_sorted else 0
        
        min_clusters = max(1, int((total_cargo_weight + max_vehicle_capacity - 1) / max_vehicle_capacity))
        max_clusters = min(num_vehicles, len(station_ids))
        
        best_clusters = None
        best_cost = float('inf')
        best_cluster_count = min_clusters
        
        print(f"   🔍 Sınırlı Araç: {min_clusters} - {max_clusters} küme deneniyor...")
        
        for num_clusters in range(min_clusters, max_clusters + 1):
            test_clusters = self._create_clusters(cargo_data, depot, num_clusters, station_ids.copy())
            
            test_clusters_sorted = sorted(test_clusters, key=lambda x: x["total_weight"], reverse=True)
            all_fit = True
            for i, cluster in enumerate(test_clusters_sorted):
                if i < len(vehicles_sorted):
                    if cluster["total_weight"] > vehicles_sorted[i].capacity:
                        all_fit = False
                        break
            
            if not all_fit:
                print(f"      ⚠️ {num_clusters} küme (k-means): Kapasite aşımı - alternatif deneniyor...")
                test_clusters = self._create_capacity_aware_clusters(
                    cargo_data, depot, num_clusters, vehicles_sorted
                )
                
                if test_clusters is None:
                    print(f"      ❌ {num_clusters} küme: Kapasite-duyarlı kümeleme de başarısız - atlandı")
                    continue
                else:
                    print(f"      ✅ {num_clusters} küme: Kapasite-duyarlı kümeleme başarılı!")
            
            test_cost = 0
            for cluster in test_clusters:
                route_dist = self._calculate_cluster_route_distance(cluster, cargo_data, depot)
                test_cost += route_dist * cost_per_km
            
            print(f"      📊 {num_clusters} küme: Tahmini maliyet = {test_cost:.2f} birim")
            
            if test_cost < best_cost:
                best_cost = test_cost
                best_clusters = test_clusters
                best_cluster_count = num_clusters
        
        if best_clusters is None:
            best_clusters = self._create_clusters(cargo_data, depot, num_vehicles, station_ids.copy())
            best_cluster_count = num_vehicles
        
        print(f"   🚚 Sınırlı Araç Optimizasyonu: {best_cluster_count} araç (mevcut: {num_vehicles}), Tahmini: {best_cost:.2f} birim")
        
        clusters = best_clusters
        clusters.sort(key=lambda x: x["total_weight"], reverse=True)
        
        vehicle_bins = []
        for i, vehicle in enumerate(vehicles_sorted):
            if i < len(clusters):
                cluster = clusters[i]
                cluster_weight = cluster["total_weight"]
                
                if cluster_weight <= vehicle.capacity:
                    station_list = list(cluster["stations"])
                    station_assignments = []
                    for sid in station_list:
                        station_assignments.append({
                            "sid": sid,
                            "weight": cargo_data[sid]["total_weight"],
                            "count": cargo_data[sid]["total_count"]
                        })
                    
                    vehicle_bins.append({
                        "vehicle": vehicle,
                        "stations": station_list,
                        "station_assignments": station_assignments,
                        "remaining_capacity": vehicle.capacity - cluster_weight,
                        "total_weight": cluster_weight,
                        "total_count": sum(cargo_data[sid]["total_count"] for sid in cluster["stations"])
                    })
                else:
                    assigned_weight = 0
                    assigned_stations = []
                    station_assignments = []
                    for sid in cluster["stations"]:
                        if assigned_weight + cargo_data[sid]["total_weight"] <= vehicle.capacity:
                            assigned_stations.append(sid)
                            station_assignments.append({
                                "sid": sid,
                                "weight": cargo_data[sid]["total_weight"],
                                "count": cargo_data[sid]["total_count"]
                            })
                            assigned_weight += cargo_data[sid]["total_weight"]
                    
                    vehicle_bins.append({
                        "vehicle": vehicle,
                        "stations": assigned_stations,
                        "station_assignments": station_assignments,
                        "remaining_capacity": vehicle.capacity - assigned_weight,
                        "total_weight": assigned_weight,
                        "total_count": sum(cargo_data[sid]["total_count"] for sid in assigned_stations)
                    })
            else:
                vehicle_bins.append({
                    "vehicle": vehicle,
                    "stations": [],
                    "station_assignments": [],
                    "remaining_capacity": vehicle.capacity,
                    "total_weight": 0,
                    "total_count": 0
                })
        
        return vehicle_bins
    
    def _assign_by_best_fit(self, cargo_data: Dict, existing_vehicles: List, 
                            optimization_mode: str) -> tuple:
        vehicle_bins = []
        for v in sorted(existing_vehicles, key=lambda x: -x.capacity):
            vehicle_bins.append({
                "vehicle": v,
                "stations": [],  
                "station_assignments": [],  
                "remaining_capacity": v.capacity,
                "total_weight": 0,
                "total_count": 0
            })
        
        station_list = []
        for sid in cargo_data.keys():
            weight = cargo_data[sid]["total_weight"]
            count = cargo_data[sid]["total_count"]
            weight_per_count = weight / count if count > 0 else float('inf')
            station_list.append({
                "sid": sid,
                "weight": weight,
                "count": count,
                "weight_per_count": weight_per_count
            })
        

        if optimization_mode == "max_count":
            station_list.sort(key=lambda x: x["weight_per_count"])
            print(f"   📊 max_count modu: Kargo sayısı öncelikli sıralama (düşük kg/adet oranı önce)")
        else:  

            station_list.sort(key=lambda x: -x["weight"])
            print(f"   📊 max_weight modu: Kargo ağırlığı öncelikli sıralama (ağır kargolar önce)")
        
        print(f"   📋 Öncelik Sırası:")
        for i, s in enumerate(station_list, 1):
            print(f"      {i}. Station {s['sid']}: {s['count']} adet, {s['weight']} kg, {s['weight_per_count']:.1f} kg/adet")
        
        accepted_stations = []
        rejected_stations = []
        
        for station in station_list:
            best_fit = None
            min_remaining = float('inf')
            
            for vbin in vehicle_bins:
                if station["weight"] <= vbin["remaining_capacity"]:
                    if vbin["remaining_capacity"] < min_remaining:
                        min_remaining = vbin["remaining_capacity"]
                        best_fit = vbin
            
            if best_fit:
                best_fit["stations"].append(station["sid"])
                best_fit["station_assignments"].append({
                    "sid": station["sid"],
                    "weight": station["weight"],
                    "count": station["count"]
                })
                best_fit["remaining_capacity"] -= station["weight"]
                best_fit["total_weight"] += station["weight"]
                best_fit["total_count"] += station["count"]
                accepted_stations.append(station["sid"])
                print(f"      ✅ Station {station['sid']}: {station['weight']} kg → {best_fit['vehicle'].name} (kalan: {best_fit['remaining_capacity']:.0f} kg)")
            
            elif optimization_mode == "max_count":
                weight_per_item = station["weight_per_count"]
                remaining_weight = station["weight"]
                remaining_count = station["count"]
                items_placed_total = 0
                
                sorted_bins = sorted(vehicle_bins, key=lambda x: -x["remaining_capacity"])
                
                for vbin in sorted_bins:
                    if remaining_count <= 0:
                        break
                    
                    if vbin["remaining_capacity"] >= weight_per_item:
                        items_can_fit = int(vbin["remaining_capacity"] / weight_per_item)
                        items_to_place = min(items_can_fit, remaining_count)
                        
                        if items_to_place > 0:
                            weight_to_place = items_to_place * weight_per_item
                            
                            if station["sid"] not in vbin["stations"]:
                                vbin["stations"].append(station["sid"])
                            vbin["station_assignments"].append({
                                "sid": station["sid"],
                                "weight": weight_to_place,
                                "count": items_to_place,
                                "is_partial": True
                            })
                            vbin["remaining_capacity"] -= weight_to_place
                            vbin["total_weight"] += weight_to_place
                            vbin["total_count"] += items_to_place
                            
                            items_placed_total += items_to_place
                            remaining_weight -= weight_to_place
                            remaining_count -= items_to_place
                            
                            print(f"      🔀 Station {station['sid']}: {items_to_place} adet ({weight_to_place:.0f} kg) → {vbin['vehicle'].name} (PARÇA, kalan: {vbin['remaining_capacity']:.0f} kg)")
                
                if items_placed_total > 0:
                    if remaining_count > 0:
                        print(f"      ⚠️ Station {station['sid']}: {remaining_count} adet ({remaining_weight:.0f} kg) → REDDEDİLDİ")
                        rejected_stations.append(station["sid"])  # Track as partially rejected
                    else:
                        accepted_stations.append(station["sid"])
                else:
                    rejected_stations.append(station["sid"])
                    print(f"      ❌ Station {station['sid']}: {station['weight']} kg → REDDEDİLDİ (hiçbir araca sığmıyor)")
            else:
                rejected_stations.append(station["sid"])
                print(f"      ❌ Station {station['sid']}: {station['weight']} kg → REDDEDİLDİ (hiçbir araca sığmıyor)")
        
        return vehicle_bins, rejected_stations
    
    def _select_cargo_for_capacity(self, cluster: Dict, cargo_data: Dict, 
                                    capacity: float, optimization_mode: str) -> tuple:
        stations = cluster["stations"]
        
        station_list = []
        for sid in stations:
            station_list.append({
                "sid": sid,
                "weight": cargo_data[sid]["total_weight"],
                "count": cargo_data[sid]["total_count"],
                "weight_per_count": cargo_data[sid]["total_weight"] / cargo_data[sid]["total_count"] if cargo_data[sid]["total_count"] > 0 else float('inf')
            })
        
        if optimization_mode == "max_count":
            station_list.sort(key=lambda x: x["weight_per_count"])
        else: 

            station_list.sort(key=lambda x: -x["weight"])
        
        accepted = []
        rejected = []
        remaining_capacity = capacity
        
        for s in station_list:
            if s["weight"] <= remaining_capacity:
                accepted.append(s["sid"])
                remaining_capacity -= s["weight"]
            else:
                rejected.append(s["sid"])
        
        return accepted, rejected
    
    def _order_stations_nn(self, stations: List[int], cargo_data: Dict, depot: Station) -> List[int]:
        if not stations:
            return []
        
        if len(stations) == 1:
            return stations.copy()
        
        farthest_sid = None
        max_dist = -1
        for sid in stations:
            d = self._get_dist(depot.id, sid, cargo_data, depot)
            if d > max_dist:
                max_dist = d
                farthest_sid = sid
        
        ordered = [farthest_sid]
        remaining = [s for s in stations if s != farthest_sid]
        current_id = farthest_sid
        
        while remaining:
            best = None
            best_score = float('inf')
            
            for sid in remaining:
                dist_from_current = self._get_dist(current_id, sid, cargo_data, depot)
                dist_to_depot = self._get_dist(sid, depot.id, cargo_data, depot)
                
                score = dist_from_current - (dist_to_depot * 0.1)
                
                if score < best_score:
                    best_score = score
                    best = sid
            
            if best:
                ordered.append(best)
                remaining.remove(best)
                current_id = best
        
        return ordered
    
    def _find_farthest_station(self, station_ids: List[int], cargo_data: Dict, depot: Station) -> int:
        max_dist = -1
        farthest_sid = station_ids[0]
        
        for sid in station_ids:
            dist = self.distance_matrix.get((sid, depot.id), 0)
            if dist == 0:
                station = cargo_data[sid]["station"]
                dist = self._haversine_distance(
                    station.latitude, station.longitude,
                    depot.latitude, depot.longitude
                )
            if dist > max_dist:
                max_dist = dist
                farthest_sid = sid
        
        return farthest_sid
    
    def _find_nearest_feasible(self, current: Station, unvisited: List[int], 
                                cargo_data: Dict, remaining_capacity: float) -> tuple[Optional[int], List[str]]:
        min_dist = float('inf')
        nearest_sid = None
        logs = []
        
        candidates = []
        
        for sid in unvisited:
            station = cargo_data[sid]["station"]
            weight = cargo_data[sid]["total_weight"]
            
            dist = self.distance_matrix.get((current.id, sid), 0)
            if dist == 0:
                dist = self._haversine_distance(
                    current.latitude, current.longitude,
                    station.latitude, station.longitude
                )
            candidates.append({
                "sid": sid,
                "name": station.name,
                "weight": weight,
                "dist": dist
            })

        candidates.sort(key=lambda x: x["dist"])
        
        for cand in candidates:
            if cand["weight"] <= remaining_capacity:
                if nearest_sid is None:
                    nearest_sid = cand["sid"]
                    min_dist = cand["dist"]
                    break
            else:
                logs.append(
                    f"⚠️ {cand['name']} ({cand['dist']:.1f} km) en yakındı, ancak yükü ({cand['weight']} kg) kalan kapasiteyi ({remaining_capacity} kg) aşıyor."
                )
        
        return nearest_sid, logs
    
    
    def get_statistics(self, db: Session, target_date: date) -> Dict:
        import json
        
        routes = db.query(Route).filter(Route.route_date == target_date).all()
        
        if not routes:
            return {
                "status": "no_data",
                "message": "Bu tarih için rota bulunamadı.",
                "summary": None,
                "vehicle_breakdown": [],
                "station_breakdown": []
            }
        
        requests = self.get_cargo_by_date(db, target_date)
        cargo_data = self.aggregate_cargo_by_station(requests)
        
        total_cost = sum(r.total_cost for r in routes)
        total_distance = sum(r.total_distance for r in routes)
        total_cargo = sum(r.cargo_count for r in routes)
        total_weight = sum(r.cargo_weight for r in routes)
        
        total_requested_weight = sum(c["total_weight"] for c in cargo_data.values())
        total_requested_count = sum(c["total_count"] for c in cargo_data.values())

        vehicle_breakdown = []
        unique_owned_ids = set()
        unique_rented_ids = set()
        
        owned_cost = 0
        rented_cost = 0
        
        for route in routes:
            vehicle = route.vehicle
            is_rented = vehicle.is_rented if vehicle else False
            
            if is_rented:
                unique_rented_ids.add(route.vehicle_id)
                rented_cost += route.total_cost
            else:
                unique_owned_ids.add(route.vehicle_id)
                owned_cost += route.total_cost
            
            try:
                path_data = json.loads(route.path_data) if isinstance(route.path_data, str) else route.path_data
                path = path_data.get("path", []) if isinstance(path_data, dict) else path_data
                stations_visited = [p.get("name") for p in path if p.get("name") and not p.get("is_depot")]
            except:
                stations_visited = []
            
            vehicle_breakdown.append({
                "vehicle_id": route.vehicle_id,
                "vehicle_name": vehicle.name if vehicle else f"Araç {route.vehicle_id}",
                "is_rented": is_rented,
                "capacity": vehicle.capacity if vehicle else 0,
                "cargo_weight": route.cargo_weight,
                "cargo_count": route.cargo_count,
                "distance": route.total_distance,
                "cost": route.total_cost,
                "utilization": round((route.cargo_weight / vehicle.capacity * 100) if vehicle and vehicle.capacity else 0, 1),
                "stations": stations_visited,
                "scenario_type": route.scenario_type
            })
        
        station_breakdown = []
        for sid, data in cargo_data.items():
            station = data["station"]
            station_breakdown.append({
                "station_id": sid,
                "station_name": station.name,
                "total_weight": data["total_weight"],
                "total_count": data["total_count"],
                "latitude": station.latitude,
                "longitude": station.longitude
            })

        station_breakdown.sort(key=lambda x: x["total_weight"], reverse=True)

        total_fleet_size = db.query(Vehicle).filter(Vehicle.is_rented == False).count()
        
        summary = {
            "total_routes": len(routes),
            "total_cost": round(total_cost, 2),
            "total_distance": round(total_distance, 2),
            "total_cargo_transported": total_cargo,
            "total_weight_transported": round(total_weight, 2),
            "total_cargo_requested": total_requested_count,
            "total_weight_requested": round(total_requested_weight, 2),
            "acceptance_rate_count": round((total_cargo / total_requested_count * 100), 1) if total_requested_count > 0 else 100,
            "acceptance_rate_weight": round((total_weight / total_requested_weight * 100), 1) if total_requested_weight > 0 else 100,
            "owned_vehicles_used": len(unique_owned_ids),
            "rented_vehicles_used": len(unique_rented_ids),
            "total_fleet_size": total_fleet_size,
            "owned_cost": round(owned_cost, 2),
            "rented_cost": round(rented_cost, 2),
            "avg_cost_per_route": round(total_cost / len(routes), 2) if routes else 0,
            "avg_distance_per_route": round(total_distance / len(routes), 2) if routes else 0,
            "cost_per_kg": round(total_cost / total_weight, 2) if total_weight > 0 else 0,
            "cost_per_km": round(total_cost / total_distance, 2) if total_distance > 0 else 0,
            "scenario_type": routes[0].scenario_type if routes else "unknown"
        }
        
        return {
            "status": "success",
            "summary": summary,
            "vehicle_breakdown": vehicle_breakdown,
            "station_breakdown": station_breakdown
        }
    
    def get_vehicle_users(self, db: Session, target_date: date) -> Dict:
        import json
        
        routes = db.query(Route).filter(Route.route_date == target_date).all()
        
        if not routes:
            return {
                "status": "no_data",
                "message": "Bu tarih için rota bulunamadı.",
                "vehicles": []
            }
        
        requests = self.get_cargo_by_date(db, target_date)

        station_users = {}
        for req in requests:
            sid = req.station_id
            if sid not in station_users:
                station_users[sid] = []

            user = req.user
            user_info = {
                "user_id": req.user_id,
                "username": user.username if user else f"Kullanıcı {req.user_id}",
                "email": user.email if user else None,
                "cargo_weight": req.weight,
                "cargo_count": req.cargo_count,
                "station_name": req.station.name if req.station else None
            }
            station_users[sid].append(user_info)

        vehicles = []
        for route in routes:
            vehicle = route.vehicle

            try:
                path_data = json.loads(route.path_data) if isinstance(route.path_data, str) else route.path_data
                path = path_data.get("path", []) if isinstance(path_data, dict) else path_data
            except:
                path = []
            

            route_users = []
            stations_in_route = set()
            route_user_ids = set() 
            
            for stop in path:
                sid = stop.get("station_id")
                if sid and sid in station_users and sid not in stations_in_route:
                    stations_in_route.add(sid)
                    for user_info in station_users[sid]:
                        route_users.append(user_info)
                        route_user_ids.add(user_info["user_id"])
            
            vehicles.append({
                "vehicle_id": route.vehicle_id,
                "vehicle_name": vehicle.name if vehicle else f"Araç {route.vehicle_id}",
                "is_rented": vehicle.is_rented if vehicle else False,
                "capacity": vehicle.capacity if vehicle else 0,
                "cargo_weight": route.cargo_weight,
                "cargo_count": route.cargo_count,
                "distance": route.total_distance,
                "cost": route.total_cost,
                "route_id": route.id,
                "users": route_users,
                "user_count": len(route_user_ids)  
            })

        all_user_ids = set()
        for v in vehicles:
            for u in v["users"]:
                all_user_ids.add(u["user_id"])
        
        return {
            "status": "success",
            "date": target_date.isoformat(),
            "vehicles": vehicles,
            "total_users": len(all_user_ids)  
        }
    
    def _simulate_scenario_run(self, vehicles: List[Vehicle], items: List[Dict], mode: str) -> Dict:
        pool = [item.copy() for item in items]
        
        if mode == 'max_count':
             pool.sort(key=lambda x: x['weight'])
        elif mode == 'max_weight':
             pool.sort(key=lambda x: x['weight'], reverse=True)

        if mode == 'unlimited':
            return {
                "accepted_weight": sum(i['weight'] for i in pool),
                "accepted_count": sum(i['count'] for i in pool),
                "rejected_weight": 0,
                "rejected_count": 0,
                "vehicles_used": 0 
            }
            
        
        total_capacity = sum(v.capacity for v in vehicles)
        accepted_weight = 0
        accepted_count = 0
        rejected_weight = 0
        rejected_count = 0
        
        current_fill = 0
        
        for item in pool:
            w = item['weight']
            c = item['count']
            
            if current_fill + w <= total_capacity:
                current_fill += w
                accepted_weight += w
                accepted_count += c
            else:
                remaining = total_capacity - current_fill
                if remaining > 0:
                    current_fill += remaining
                    accepted_weight += remaining
                    ratio = remaining / w
                    accepted_count += int(c * ratio)
                    
                    rejected_weight += (w - remaining)
                    rejected_count += (c - int(c * ratio))
                else:
                    rejected_weight += w
                    rejected_count += c

        return {
            "accepted_weight": round(accepted_weight, 2),
            "accepted_count": int(accepted_count),
            "rejected_weight": round(rejected_weight, 2),
            "rejected_count": int(rejected_count)
        }

    def compare_scenarios(self, db: Session, target_date: date) -> Dict:
        requests = self.get_cargo_by_date(db, target_date)
        if not requests:
            return {
                "status": "error",
                "message": f"{target_date} tarihi için kargo talebi bulunamadı. Lütfen önce veri yükleyin."
            }
        
        items = []
        for r in requests:
            items.append({
                "weight": r.weight,
                "count": r.cargo_count
            })
            
        total_cargo = sum(i["count"] for i in items)
        total_weight = sum(i["weight"] for i in items)
        

        existing_vehicles = db.query(Vehicle).filter(Vehicle.is_rented == False).all()
        total_capacity = sum(v.capacity for v in existing_vehicles)
        
        needs_rental = total_weight > total_capacity
        capacity_utilization = round((total_weight / total_capacity * 100), 1) if total_capacity > 0 else 0
        

        unlimited_vehs = len(existing_vehicles)
        if needs_rental:
             rental_cap = 500 
             overflow = total_weight - total_capacity
             rentals = max(1, int((overflow + rental_cap - 1) / rental_cap))
             unlimited_vehs += rentals

        unlimited_scenario = {
            "scenario": "unlimited",
            "name": "Sınırsız Araç Senaryosu",
            "description": "Tüm kargolar taşınır. Gerekirse araç kiralanır.",
            "cargo_count": total_cargo,
            "cargo_weight": round(total_weight, 2),
            "acceptance_rate": 100,
            "needs_rental": needs_rental,
            "vehicles_used": unlimited_vehs
        }
        
        sim_count = self._simulate_scenario_run(existing_vehicles, items, 'max_count')
        limited_max_count = {
            "scenario": "limited_max_count",
            "name": "Belirli Araç - Max Kargo Sayısı",
            "description": "Mevcut filonun kapasitesi kadar kargo taşınır, kargo sayısı önceliklidir.",
            "max_cargo_count": sim_count["accepted_count"],
            "max_cargo_weight": sim_count["accepted_weight"],
            "acceptance_rate": round((sim_count["accepted_count"] / total_cargo * 100), 1) if total_cargo > 0 else 0,
            "rejected_cargo_count": sim_count["rejected_count"],
            "rejected_cargo_weight": sim_count["rejected_weight"],
            "vehicles_used": len(existing_vehicles)
        }
        
        sim_weight = self._simulate_scenario_run(existing_vehicles, items, 'max_weight')
        limited_max_weight = {
            "scenario": "limited_max_weight",
            "name": "Belirli Araç - Max Kargo Ağırlığı",
            "description": "Mevcut filonun kapasitesi kadar kargo taşınır, ağırlık önceliklidir.",
            "max_cargo_count": sim_weight["accepted_count"],
            "max_cargo_weight": sim_weight["accepted_weight"],
             "acceptance_rate": round((sim_weight["accepted_weight"] / total_weight * 100), 1) if total_weight > 0 else 0,
            "rejected_cargo_count": sim_weight["rejected_count"],
            "rejected_cargo_weight": sim_weight["rejected_weight"],
            "vehicles_used": len(existing_vehicles)
        }
        
        return {
            "status": "success",
            "date": target_date.isoformat(),
            "cargo_summary": {
                "total_cargo_count": total_cargo,
                "total_cargo_weight": round(total_weight, 2),
                "station_count": len(set(r.station_id for r in requests))
            },
            "fleet_summary": {
                "owned_vehicles": len(existing_vehicles),
                "total_capacity": total_capacity,
                "capacity_utilization": capacity_utilization,
                "needs_rental": needs_rental
            },
            "scenarios": {
                "unlimited": unlimited_scenario,
                "limited_max_count": limited_max_count,
                "limited_max_weight": limited_max_weight
            },
            "recommendation": "unlimited" if needs_rental else "limited_max_count"
        }

    
    def get_cargo_summary(self, db: Session, target_date: date) -> Dict:
        requests = self.get_cargo_by_date(db, target_date)
        
        if not requests:
            return {
                "status": "no_data",
                "message": "Bu tarih için kargo talebi bulunamadı.",
                "stations": [],
                "totals": None
            }
        
        station_data = {}
        for req in requests:
            sid = req.station_id
            if sid not in station_data:
                station_data[sid] = {
                    "station_id": sid,
                    "station_name": req.station.name if req.station else f"İstasyon {sid}",
                    "latitude": req.station.latitude if req.station else 0,
                    "longitude": req.station.longitude if req.station else 0,
                    "total_weight": 0,
                    "total_count": 0,
                    "users": []
                }
            
            station_data[sid]["total_weight"] += req.weight
            station_data[sid]["total_count"] += req.cargo_count
            
            user = req.user
            station_data[sid]["users"].append({
                "user_id": req.user_id,
                "username": user.username if user else f"Kullanıcı {req.user_id}",
                "weight": req.weight,
                "count": req.cargo_count
            })
        
        stations = list(station_data.values())
        stations.sort(key=lambda x: x["total_weight"], reverse=True)
        
        totals = {
            "total_stations": len(stations),
            "total_weight": round(sum(s["total_weight"] for s in stations), 2),
            "total_count": sum(s["total_count"] for s in stations),
            "total_users": sum(len(s["users"]) for s in stations)
        }
        
        return {
            "status": "success",
            "date": target_date.isoformat(),
            "stations": stations,
            "totals": totals
        }


    def update_vehicle_capacities(self, db: Session, updates: List[Dict]) -> Dict:
        updated_count = 0
        
        for up in updates:
            name = up.get("name")
            cap = up.get("capacity")
            if name and cap is not None:
                vehicle = db.query(Vehicle).filter(Vehicle.name == name).first()
                if vehicle:
                    vehicle.capacity = float(cap)
                    updated_count += 1
        
        db.commit()
        return {"status": "success", "message": f"{updated_count} araç kapasitesi güncellendi."}
