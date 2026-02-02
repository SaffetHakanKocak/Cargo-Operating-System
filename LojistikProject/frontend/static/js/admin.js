
const token = localStorage.getItem("token");
const role = localStorage.getItem("role");


if (!token) {
    window.location.href = "login.html";
} else if (role !== 'admin') {
    window.location.href = "user_dashboard.html";
}

const DEFAULT_PARAMS = {
    costPerKm: 1.0,
    rentalCapacity: 500,
    rentalCost: 200,
    truck1Capacity: 500,
    truck2Capacity: 750,
    truck3Capacity: 1000
};

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeAllModals();
        hideLogoutModal();
    }
});

function loadParameters() {
    const saved = localStorage.getItem('vrpParameters');
    if (saved) {
        return JSON.parse(saved);
    }
    return { ...DEFAULT_PARAMS };
}

function saveParametersToStorage(params) {
    localStorage.setItem('vrpParameters', JSON.stringify(params));
}

function getParameters() {
    return loadParameters();
}

function toggleRoutePlanningModal() {
    const modal = document.getElementById('route-planning-modal');
    const overlay = document.getElementById('modal-overlay');
    const isOpen = modal.classList.contains('active');

    if (!isOpen) {
        closeAllModals();
        modal.classList.add('active');
        overlay.classList.add('active');

        const dateInput = document.getElementById('planning-date');
        if (dateInput && !dateInput.value) {
            dateInput.value = new Date().toISOString().split('T')[0];
        }
    } else {
        closeAllModals();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const dateInput = document.getElementById('planning-date');
    if (dateInput) {
        const today = new Date().toISOString().split('T')[0];
        dateInput.value = today;

        dateInput.addEventListener('change', onDateChange);

        setTimeout(() => loadCargoForDate(today), 500);
    }

    const params = loadParameters();
    document.getElementById('param-cost-per-km').value = params.costPerKm;
    document.getElementById('param-rental-capacity').value = params.rentalCapacity;
    document.getElementById('param-rental-cost').value = params.rentalCost;
    document.getElementById('param-truck1-capacity').value = params.truck1Capacity;
    document.getElementById('param-truck2-capacity').value = params.truck2Capacity;
    document.getElementById('param-truck3-capacity').value = params.truck3Capacity;
});

async function onDateChange(e) {
    const targetDate = e.target.value;
    if (targetDate) {
        await loadCargoForDate(targetDate);
    }
}

async function loadCargoForDate(targetDate) {
    try {
        const allRequests = await API.get('/logistics/cargo/me');

        const routes = await API.get(`/logistics/admin/routes/${targetDate}`);

        if (routes && routes.length > 0) {
            const stationNames = new Set();
            routes.forEach(route => {
                let path = typeof route.path_data === 'string' ? JSON.parse(route.path_data) : route.path_data;
                path.forEach(p => {
                    if (p.name && p.name.toLowerCase() !== 'umuttepe') {
                        stationNames.add(p.name);
                    }
                });
            });

            const stationIds = [];
            Object.entries(stationDataMap).forEach(([id, station]) => {
                if (stationNames.has(station.name)) {
                    stationIds.push(parseInt(id));
                }
            });

            highlightMyStations(stationIds);
        } else {
            highlightMyStations([]);
        }
    } catch (err) {
        console.warn("Could not load cargo for date:", err);
    }
}

function logout() {
    showLogoutModal();
}

function showLogoutModal() {
    const modal = document.getElementById('logout-modal-overlay');
    if (modal) {
        modal.classList.add('active');
        setTimeout(() => modal.style.opacity = '1', 10);
    }
}

function hideLogoutModal() {
    const modal = document.getElementById('logout-modal-overlay');
    if (modal) {
        modal.classList.remove('active');
    }
}

function confirmLogout() {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    window.location.href = "index.html";
}

async function deleteRoutes() {
    if (!confirm("Tüm rotaları silmek istediğinize emin misiniz?\n\nNot: Kargo talepleri silinmeyecek.")) return;

    try {
        const result = await API.delete('/logistics/admin/routes');
        alert(result.message || "Rotalar silindi.");

        routeLayers.forEach(l => map.removeLayer(l));
        routeLayers.length = 0;

        document.getElementById('result-panel').style.display = 'none';
        document.getElementById('status-msg').innerText = '';

        highlightMyStations([]);
    } catch (err) {
        console.error("Delete routes error:", err);
        alert("Silme başarısız: " + (err.message || err));
    }
}

function toggleParametersModal() {
    const modal = document.getElementById('parameters-modal');
    const overlay = document.getElementById('modal-overlay');
    const isOpen = modal.classList.contains('active');

    if (!isOpen) {
        closeAllModals();
        modal.classList.add('active');
        overlay.classList.add('active');

        const params = loadParameters();
        document.getElementById('param-cost-per-km').value = params.costPerKm;
        document.getElementById('param-rental-capacity').value = params.rentalCapacity;
        document.getElementById('param-rental-cost').value = params.rentalCost;
        document.getElementById('param-truck1-capacity').value = params.truck1Capacity;
        document.getElementById('param-truck2-capacity').value = params.truck2Capacity;
        document.getElementById('param-truck3-capacity').value = params.truck3Capacity;
    } else {
        closeAllModals();
    }
}

async function saveParameters() {
    const params = {
        costPerKm: parseFloat(document.getElementById('param-cost-per-km').value) || 1.0,
        rentalCapacity: parseInt(document.getElementById('param-rental-capacity').value) || 500,
        rentalCost: parseInt(document.getElementById('param-rental-cost').value) || 200,
        truck1Capacity: parseInt(document.getElementById('param-truck1-capacity').value) || 500,
        truck2Capacity: parseInt(document.getElementById('param-truck2-capacity').value) || 750,
        truck3Capacity: parseInt(document.getElementById('param-truck3-capacity').value) || 1000
    };

    saveParametersToStorage(params);

    try {
        const updates = [
            { name: "Kamyon 1", capacity: params.truck1Capacity },
            { name: "Kamyon 2", capacity: params.truck2Capacity },
            { name: "Tır 1", capacity: params.truck3Capacity }
        ];

        await API.put('/logistics/admin/vehicle-capacities', updates);

        alert("Parametreler ve araç kapasiteleri veritabanına kaydedildi!");
    } catch (err) {
        console.error("Vehicle update error:", err);
        alert("Yerel parametreler kaydedildi, ancak veritabanı güncellenemedi.\n\nHata: " + (err.message || err));
    }

    closeAllModals();
}

async function optimizeRoutes(scenario, optimizationMode = 'max_count') {
    const dateInput = document.getElementById('planning-date');
    const statusMsg = document.getElementById('status-msg');
    const resultPanel = document.getElementById('result-panel');
    const rejectionPanel = document.getElementById('rejection-panel');

    if (!dateInput || !dateInput.value) {
        alert("Lütfen planlama tarihi seçin.");
        return;
    }

    const targetDate = dateInput.value;
    const params = getParameters();

    let scenarioName = '';
    if (scenario === 'unlimited') {
        scenarioName = 'Sınırsız Araç (Min Maliyet)';
    } else if (optimizationMode === 'max_count') {
        scenarioName = 'Belirli Araç - Maksimum Kargo Sayısı';
    } else {
        scenarioName = 'Belirli Araç - Maksimum Kargo Ağırlığı';
    }

    let confirmMsg = `${targetDate} tarihi için ${scenarioName} optimizasyonu başlatılsın mı?\n\n`;
    if (scenario === 'unlimited') {
        confirmMsg += `Parametreler:\n- Km başı: ${params.costPerKm} birim\n- Kiralık araç kapasitesi: ${params.rentalCapacity} kg\n- Kiralık araç bedeli: ${params.rentalCost} birim`;
    } else {
        confirmMsg += `🔒 Sadece mevcut filo kullanılacak!\n\nMevcut Araç Kapasiteleri:\n- Kamyon 1: ${params.truck1Capacity} kg\n- Kamyon 2: ${params.truck2Capacity} kg\n- Tır 1: ${params.truck3Capacity} kg\n\nToplam Kapasite: ${params.truck1Capacity + params.truck2Capacity + params.truck3Capacity} kg`;
    }

    if (!confirm(confirmMsg)) {
        return;
    }

    statusMsg.innerText = "Optimizasyon yapılıyor...";
    statusMsg.style.color = "var(--primary)";
    resultPanel.style.display = "none";
    if (rejectionPanel) rejectionPanel.style.display = "none";

    try {
        let url = `/logistics/admin/optimize?target_date=${targetDate}&scenario=${scenario}&cost_per_km=${params.costPerKm}`;

        if (scenario === 'unlimited') {
            url += `&rental_cost=${params.rentalCost}&rental_capacity=${params.rentalCapacity}`;
        } else {
            url += `&optimization_mode=${optimizationMode}`;
        }

        const result = await API.post(url, {});

        if (result.status === "success") {
            statusMsg.innerText = result.message;
            statusMsg.style.color = "var(--success)";

            const resultTitle = document.getElementById('result-title');
            if (resultTitle) {
                if (scenario === 'unlimited') {
                    resultTitle.innerText = '✅ Sınırsız Araç Sonucu';
                    resultTitle.style.color = 'var(--success)';
                } else {
                    resultTitle.innerText = optimizationMode === 'max_count'
                        ? '📦 Max Kargo Sayısı Sonucu'
                        : '⚖️ Max Kargo Ağırlığı Sonucu';
                    resultTitle.style.color = '#e65100';
                }
            }

            document.getElementById('result-cost').innerText = result.total_cost + " birim";
            document.getElementById('result-distance').innerText = result.total_distance + " km";
            document.getElementById('result-vehicles').innerText = result.routes_count;
            document.getElementById('result-cargo').innerText = result.total_cargo + " adet";

            const resultWeight = document.getElementById('result-weight');
            if (resultWeight) {
                resultWeight.innerText = (result.total_weight || 0) + " kg";
            }

            resultPanel.style.display = "block";

            if (scenario !== 'unlimited' && rejectionPanel) {
                if (result.rejected_cargo_count > 0 || result.rejected_cargo_weight > 0) {
                    rejectionPanel.innerHTML = `
                        <div style="font-weight: 600; color: #c62828; margin-bottom: 0.25rem;">⚠️ Reddedilen Kargolar</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.25rem; font-size: 0.85rem;">
                            <div>Reddedilen Adet:</div>
                            <div style="font-weight: 600; color: #c62828;">${result.rejected_cargo_count} adet</div>
                            <div>Reddedilen Ağırlık:</div>
                            <div style="font-weight: 600; color: #c62828;">${result.rejected_cargo_weight} kg</div>
                            <div>Kabul Oranı (Adet):</div>
                            <div style="font-weight: 600; color: #2e7d32;">${result.acceptance_rate_count}%</div>
                            <div>Kabul Oranı (kg):</div>
                            <div style="font-weight: 600; color: #2e7d32;">${result.acceptance_rate_weight}%</div>
                        </div>
                    `;
                    rejectionPanel.style.background = '#fff5f5';
                    rejectionPanel.style.borderColor = '#ffcdd2';
                    rejectionPanel.style.display = "block";
                } else {
                    rejectionPanel.innerHTML = `
                        <div style="font-weight: 600; color: #2e7d32; margin-bottom: 0.25rem;">✅ Tüm Kargolar Kabul Edildi</div>
                        <p style="font-size: 0.85rem; color: #555; margin: 0;">Mevcut filo kapasitesi tüm kargolar için yeterli.</p>
                    `;
                    rejectionPanel.style.background = '#e8f5e9';
                    rejectionPanel.style.borderColor = '#a5d6a7';
                    rejectionPanel.style.display = "block";
                }
            } else if (rejectionPanel) {
                rejectionPanel.style.display = "none";
            }

            await loadRoutesList(targetDate);
            selectAllRoutes();
            await applyRouteFilter();

            await loadCargoForDate(targetDate);
        } else {
            statusMsg.innerText = result.message || "Optimizasyon başarısız.";
            statusMsg.style.color = "var(--danger)";
        }
    } catch (err) {
        console.error("Optimize error:", err);
        statusMsg.innerText = "Hata: " + (err.message || err);
        statusMsg.style.color = "var(--danger)";
    }
}

async function drawOSRMRoute(coordinates, color, vehicleInfo) {
    const coordString = coordinates.map(c => `${c.lon},${c.lat}`).join(';');
    const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${coordString}?overview=full&geometries=geojson`;

    try {
        const response = await fetch(osrmUrl);
        const data = await response.json();

        if (data.code === 'Ok' && data.routes && data.routes[0]) {
            const routeGeometry = data.routes[0].geometry;
            const routeLayer = L.geoJSON(routeGeometry, {
                style: { color: color, weight: 5, opacity: 0.8 }
            });


            routeLayer.bindPopup(`<b>${vehicleInfo.name}</b><br>Mesafe: ${vehicleInfo.distance} km<br>Maliyet: ${vehicleInfo.cost} birim<br>Kargo: ${vehicleInfo.cargoCount} adet`);
            routeLayer.addTo(map);
            routeLayers.push(routeLayer);

            addNumberedMarkers(coordinates, color);

            return { distance: vehicleInfo.distance };
        } else {
            console.warn("OSRM fallback to polyline:", data);
            return drawSimplePolyline(coordinates, color, vehicleInfo);
        }
    } catch (err) {
        console.warn("OSRM error, using fallback:", err);
        return drawSimplePolyline(coordinates, color, vehicleInfo);
    }
}

function addNumberedMarkers(coordinates, color) {
    let stationNumber = 0;

    coordinates.forEach((coord, index) => {
        const isStartDepot = coord.is_depot && coord.is_start;
        const isEndDepot = coord.is_depot && !coord.is_start;
        const isStation = !coord.is_depot;

        if (isStartDepot) {
            return;
        }

        if (isStation) {
            stationNumber++;
        }

        const icon = L.divIcon({
            className: 'numbered-marker',
            html: `<div style="
                background: ${isEndDepot ? '#28a745' : color};
                color: white;
                width: 24px;
                height: 24px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 12px;
                border: 2px solid white;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            ">${isEndDepot ? '★' : stationNumber}</div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        });

        const marker = L.marker([coord.lat, coord.lon], { icon: icon });

        const popupContent = isEndDepot
            ? `<b>${coord.name}</b> (Hedef)`
            : `<b>${stationNumber}. ${coord.name}</b><br>Ağırlık: ${coord.weight} kg<br>Kargo: ${coord.count} adet`;
        marker.bindPopup(popupContent);

        marker.addTo(map);
        routeLayers.push(marker);
    });
}

function drawSimplePolyline(coordinates, color, vehicleInfo) {
    const latlngs = coordinates.map(c => [c.lat, c.lon]);
    const line = L.polyline(latlngs, { color: color, weight: 4, dashArray: '10, 10' }).addTo(map);
    line.bindPopup(`<b>${vehicleInfo.name}</b> (Kuş Uçuşu)<br>Mesafe: ${vehicleInfo.distance} km<br>Maliyet: ${vehicleInfo.cost} birim<br>Kargo: ${vehicleInfo.cargoCount} adet`);
    routeLayers.push(line);

    addNumberedMarkers(coordinates, color);

    return { distance: vehicleInfo.distance };
}

async function loadRoutesForDateWithOSRM(targetDate) {
    routeLayers.forEach(l => map.removeLayer(l));
    routeLayers.length = 0;

    try {
        const routes = await API.get(`/logistics/admin/routes/${targetDate}`);

        if (!routes || routes.length === 0) {
            console.log("No routes for this date.");
            return;
        }

        for (let i = 0; i < routes.length; i++) {
            const route = routes[i];
            let path = typeof route.path_data === 'string' ? JSON.parse(route.path_data) : route.path_data;

            const color = colors[i % colors.length];
            const vehicleName = route.vehicle ? route.vehicle.name : `Araç ${route.vehicle_id}`;

            await drawOSRMRoute(path, color, {
                name: vehicleName,
                distance: route.total_distance,
                cost: route.total_cost,
                cargoCount: route.cargo_count
            });
        }

        if (routeLayers.length > 0) {
            const group = L.featureGroup(routeLayers);
            map.fitBounds(group.getBounds().pad(0.1));
        }
    } catch (err) {
        console.warn("Could not load routes:", err);
    }
}

async function loadRoutesForDate(targetDate) {
    return loadRoutesForDateWithOSRM(targetDate);
}

async function toggleStationsModal() {
    const modal = document.getElementById('stations-modal');
    const overlay = document.getElementById('modal-overlay');
    const isOpen = modal.classList.contains('active');

    if (!isOpen) {
        closeAllModals();

        modal.classList.add('active');
        overlay.classList.add('active');

        try {
            const stations = await API.get('/logistics/stations');
            renderStationsTable(stations);
        } catch (err) {
            console.error("Failed to fetch stations", err);
            alert("İstasyonlar yüklenemedi.");
        }
    } else {
        closeAllModals();
    }
}

function renderStationsTable(stations) {
    const tbody = document.getElementById('stations-list');
    tbody.innerHTML = '';
    stations.forEach(s => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="padding: 0.5rem;">${s.id}</td>
            <td style="padding: 0.5rem;">${s.name}</td>
            <td style="padding: 0.5rem;">${s.latitude}</td>
            <td style="padding: 0.5rem;">${s.longitude}</td>
            <td style="padding: 0.5rem; text-align: right;">
                <button class="btn btn-danger" style="padding: 0.25rem 0.5rem; font-size: 0.8rem;" 
                    onclick="deleteStation(${s.id}, '${s.name}')">Sil</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function deleteStation(id, name) {
    if (!confirm(`${name} istasyonunu silmek istediğinize emin misiniz?`)) return;

    try {
        await API.delete(`/logistics/stations/${id}`);
        const stations = await API.get('/logistics/stations');
        renderStationsTable(stations);
        alert("İstasyon silindi.");
    } catch (err) {
        console.error("Delete station error:", err);
        alert("Hata: " + (err.message || "İstasyon silinemedi."));
    }
}



let loadedRoutes = [];

function toggleRouteDisplayModal() {
    const modal = document.getElementById('route-display-modal');
    const overlay = document.getElementById('modal-overlay');
    const isOpen = modal.classList.contains('active');

    if (!isOpen) {
        closeAllModals();
        modal.classList.add('active');
        overlay.classList.add('active');

        const dateInput = document.getElementById('route-display-date');
        if (dateInput && !dateInput.value) {
            dateInput.value = new Date().toISOString().split('T')[0];
        }

        loadRoutesList();
    } else {
        closeAllModals();
    }
}

async function loadRoutesList() {
    const dateInput = document.getElementById('route-display-date');
    const routesList = document.getElementById('routes-list');

    if (!dateInput || !dateInput.value) {
        routesList.innerHTML = '<p style="color: var(--text-light); text-align: center;">Tarih seçin...</p>';
        return;
    }

    const targetDate = dateInput.value;

    try {
        const routes = await API.get(`/logistics/admin/routes/${targetDate}`);
        loadedRoutes = routes;

        if (!routes || routes.length === 0) {
            routesList.innerHTML = '<p style="color: var(--text-light); text-align: center;">Bu tarihte rota bulunamadı.</p>';
            return;
        }

        routesList.innerHTML = '';
        routes.forEach((route, index) => {
            const vehicleName = route.vehicle ? route.vehicle.name : `Araç ${route.vehicle_id}`;
            const color = colors[index % colors.length];

            const div = document.createElement('div');
            div.style.cssText = 'display: flex; align-items: center; padding: 0.5rem; background: #f8f9fa; border-radius: 4px;';
            div.innerHTML = `
                <input type="checkbox" id="route-check-${route.id}" checked 
                    style="width: 18px; height: 18px; margin-right: 0.75rem; cursor: pointer;">
                <div style="width: 16px; height: 16px; background: ${color}; border-radius: 3px; margin-right: 0.75rem;"></div>
                <label for="route-check-${route.id}" style="cursor: pointer; flex: 1;">
                    <strong>${vehicleName}</strong><br>
                    <span style="font-size: 0.85rem; color: var(--text-light);">${route.total_distance} km · ${route.cargo_count} kargo</span>
                </label>
            `;
            routesList.appendChild(div);
        });
    } catch (err) {
        console.error("Failed to load routes:", err);
        routesList.innerHTML = '<p style="color: var(--danger); text-align: center;">Rotalar yüklenemedi.</p>';
    }
}

function selectAllRoutes() {
    loadedRoutes.forEach(route => {
        const checkbox = document.getElementById(`route-check-${route.id}`);
        if (checkbox) checkbox.checked = true;
    });
}

function deselectAllRoutes() {
    loadedRoutes.forEach(route => {
        const checkbox = document.getElementById(`route-check-${route.id}`);
        if (checkbox) checkbox.checked = false;
    });
}

async function applyRouteFilter() {
    routeLayers.forEach(l => map.removeLayer(l));
    routeLayers.length = 0;

    const selectedRoutes = loadedRoutes.filter(route => {
        const checkbox = document.getElementById(`route-check-${route.id}`);
        return checkbox && checkbox.checked;
    });

    if (selectedRoutes.length === 0) {
        closeAllModals();
        return;
    }

    for (let i = 0; i < selectedRoutes.length; i++) {
        const route = selectedRoutes[i];
        const originalIndex = loadedRoutes.indexOf(route);
        let rawData = typeof route.path_data === 'string' ? JSON.parse(route.path_data) : route.path_data;
        let path = Array.isArray(rawData) ? rawData : rawData.path;

        const color = colors[originalIndex % colors.length];
        const vehicleName = route.vehicle ? route.vehicle.name : `Araç ${route.vehicle_id}`;

        await drawOSRMRoute(path, color, {
            name: vehicleName,
            distance: route.total_distance,
            cost: route.total_cost,
            cargoCount: route.cargo_count
        });
    }

    if (routeLayers.length > 0) {
        const group = L.featureGroup(routeLayers);
        map.fitBounds(group.getBounds().pad(0.1));
    }

    const stationNames = new Set();
    selectedRoutes.forEach(route => {
        let rawData = typeof route.path_data === 'string' ? JSON.parse(route.path_data) : route.path_data;
        let path = Array.isArray(rawData) ? rawData : rawData.path;

        path.forEach(p => {
            if (p.name && p.name.toLowerCase() !== 'umuttepe') {
                stationNames.add(p.name);
            }
        });
    });

    const stationIds = [];
    Object.entries(stationDataMap).forEach(([id, station]) => {
        if (stationNames.has(station.name)) {
            stationIds.push(parseInt(id));
        }
    });
    highlightMyStations(stationIds);

    closeAllModals();
}


async function toggleDistanceMatrixModal() {
    const modal = document.getElementById('distance-matrix-modal');
    const overlay = document.getElementById('modal-overlay');
    const isOpen = modal.classList.contains('active');

    if (!isOpen) {
        closeAllModals();
        modal.classList.add('active');
        overlay.classList.add('active');


        document.getElementById('matrix-loading').style.display = 'block';
        document.getElementById('matrix-container').style.display = 'none';


        await loadDistanceMatrix();
    } else {
        closeAllModals();
    }
}

async function loadDistanceMatrix() {
    try {
        const data = await API.get('/logistics/admin/distance-matrix');

        if (!data.stations || data.stations.length === 0) {
            document.getElementById('matrix-loading').innerHTML = '<p>İstasyon bulunamadı.</p>';
            return;
        }

        const stations = data.stations;
        const matrix = data.matrix;


        let html = '<thead><tr><th style="position: sticky; left: 0; background: #f8f9fa; z-index: 2; padding: 8px; border: 1px solid #ddd;"></th>';


        stations.forEach(name => {
            html += `<th style="padding: 8px; border: 1px solid #ddd; background: #4a90d9; color: white; min-width: 80px; white-space: nowrap;">${name}</th>`;
        });
        html += '</tr></thead><tbody>';


        matrix.forEach((row, i) => {
            html += `<tr><th style="position: sticky; left: 0; background: #4a90d9; color: white; z-index: 1; padding: 8px; border: 1px solid #ddd; white-space: nowrap;">${stations[i]}</th>`;
            row.forEach((dist, j) => {
                const isZero = dist === 0;
                const bgColor = isZero ? '#f0f0f0' : (dist < 30 ? '#d4edda' : (dist < 60 ? '#fff3cd' : '#f8d7da'));
                html += `<td style="padding: 8px; border: 1px solid #ddd; text-align: center; background: ${bgColor};">${isZero ? '-' : dist}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody>';

        document.getElementById('distance-matrix-table').innerHTML = html;
        document.getElementById('matrix-loading').style.display = 'none';
        document.getElementById('matrix-container').style.display = 'block';

    } catch (err) {
        console.error("Failed to load distance matrix:", err);
        document.getElementById('matrix-loading').innerHTML = '<p style="color: red;">Mesafe matrisi yüklenemedi: ' + (err.message || err) + '</p>';
    }
}


async function toggleRouteInspectModal() {
    const modal = document.getElementById('route-inspect-modal');
    const overlay = document.getElementById('modal-overlay');
    const isOpen = modal.classList.contains('active');

    if (!isOpen) {
        closeAllModals();
        modal.classList.add('active');
        overlay.classList.add('active');

        const dateInput = document.getElementById('inspect-date');
        if (!dateInput.value) {
            dateInput.value = new Date().toISOString().split('T')[0];
        }
        loadInspectRoutes();
    } else {
        closeAllModals();
    }
}

let inspectRoutesCache = [];

async function loadInspectRoutes() {
    const dateInput = document.getElementById('inspect-date');
    if (!dateInput.value) return;

    const container = document.getElementById('inspect-vehicle-list');
    container.innerHTML = '<p>Yükleniyor...</p>';
    document.getElementById('inspect-logs-container').innerHTML = '<p style="color: #666; font-style: italic;">Detayları görmek için soldan bir araç seçin.</p>';

    try {
        const routes = await API.get(`/logistics/admin/routes/${dateInput.value}`);
        inspectRoutesCache = routes;

        if (routes.length === 0) {
            container.innerHTML = '<p>Bu tarih için kayıtlı rota bulunamadı.</p>';
            return;
        }

        container.innerHTML = '';
        routes.forEach((route, index) => {
            const vehicleName = route.vehicle ? route.vehicle.name : `Araç ${route.vehicle_id}`;
            const div = document.createElement('div');
            div.className = 'inspect-vehicle-item';
            div.style.padding = '10px';
            div.style.borderBottom = '1px solid #eee';
            div.style.cursor = 'pointer';
            div.style.transition = 'background 0.2s';

            div.onmouseover = () => div.style.background = '#f8f9fa';
            div.onmouseout = () => div.style.background = 'transparent';

            div.innerHTML = `
                <div style="font-weight: bold; color: var(--primary);">🚛 ${vehicleName}</div>
                <div style="font-size: 0.85rem; color: #666;">
                    Yük: ${route.cargo_weight} kg | Mesafe: ${route.total_distance} km
                </div>
            `;

            div.onclick = () => showRouteDetails(index);
            container.appendChild(div);
        });

    } catch (err) {
        container.innerHTML = '<p style="color: red;">Rotalar yüklenirken hata oluştu.</p>';
        console.error(err);
    }
}

function showRouteDetails(index) {
    const route = inspectRoutesCache[index];
    const container = document.getElementById('inspect-logs-container');
    const title = document.getElementById('inspect-details-title');

    const vehicleName = route.vehicle ? route.vehicle.name : `Araç ${route.vehicle_id}`;
    title.innerText = `${vehicleName} - Rota Detayları`;

    let logs = [];

    try {
        let rawData = typeof route.path_data === 'string' ? JSON.parse(route.path_data) : route.path_data;
        if (rawData.logs && Array.isArray(rawData.logs)) {
            logs = rawData.logs;
        } else {
            logs = ["⚠️ Bu rota için detaylı karar günlüğü bulunamadı (Eski veri)."];
        }
    } catch (e) {
        logs = ["Veri okuma hatası."];
    }

    let html = `
        <table style="width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.9rem;">
            <thead>
                <tr style="background: #f8f9fa; color: #495057;">
                    <th style="padding: 12px; border-bottom: 2px solid #dee2e6; text-align: left;">İstasyon / Durum</th>
                    <th style="padding: 12px; border-bottom: 2px solid #dee2e6; text-align: right;">Mesafe</th>
                    <th style="padding: 12px; border-bottom: 2px solid #dee2e6; text-align: right;">Toplam Yol</th>
                    <th style="padding: 12px; border-bottom: 2px solid #dee2e6; text-align: right;">Yük</th>
                    <th style="padding: 12px; border-bottom: 2px solid #dee2e6; text-align: right;">Kalan Kap.</th>
                </tr>
            </thead>
            <tbody>
    `;

    logs.forEach(log => {
        if (log.includes('✅ Gidilen İstasyon:')) {
            try {
                const text = log.replace('✅ ', '');
                const parts = text.split(' | ');

                const station = parts[0].split(': ')[1];
                const dist = parts[1].split(': ')[1];
                const totalDist = parts[2].split(': ')[1];
                const weight = parts[3].split(': ')[1];
                const cap = parts[4].split(': ')[1];

                html += `
                    <tr style="background: #ffffff; transition: background 0.2s;">
                        <td style="padding: 12px; border-bottom: 1px solid #dee2e6; font-weight: 500; color: #28a745;">✅ ${station}</td>
                        <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: right;">${dist}</td>
                        <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: right;">${totalDist}</td>
                        <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: right;">${weight}</td>
                        <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">${cap}</td>
                    </tr>
                `;
            } catch (err) {
                html += `<tr><td colspan="5" style="padding: 10px; border-bottom: 1px solid #eee;">${log}</td></tr>`;
            }
        } else {
            let bg = '#fff';
            let color = '#333';
            let icon = '•';

            if (log.includes('⚠️')) { icon = '⚠️'; color = '#856404'; bg = '#fff3cd'; }
            else if (log.includes('🛑')) { icon = '🛑'; color = '#721c24'; bg = '#f8d7da'; }
            else if (log.includes('🏁')) { icon = '🏁'; color = '#004085'; bg = '#cce5ff'; }
            else if (log.includes('📦')) { icon = '📦'; color = '#0c5460'; bg = '#d1ecf1'; }

            const smoothText = log.replace(/^[⚠️✅🛑🏁📦]\s*/, '');

            html += `
                <tr style="background: ${bg};">
                    <td colspan="5" style="padding: 10px 12px; border-bottom: 1px solid rgba(0,0,0,0.05); color: ${color};">
                        <span style="margin-right: 8px;">${icon}</span>
                        ${smoothText}
                    </td>
                </tr>
            `;
        }
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}


let capacityChart = null;
let stationChart = null;
let cachedStats = null;
let cachedVehicleUsers = null;


function toggleStatisticsModal() {
    const modal = document.getElementById('statistics-modal');
    const overlay = document.getElementById('modal-overlay');
    const isOpen = modal.classList.contains('active');

    if (!isOpen) {
        closeAllModals();
        modal.classList.add('active');
        overlay.classList.add('active');

        const dateInput = document.getElementById('stats-date');
        if (dateInput && !dateInput.value) {
            dateInput.value = new Date().toISOString().split('T')[0];
        }
    } else {
        closeAllModals();
    }
}


function switchStatsTab(tabName) {
    document.querySelectorAll('.modal-tab').forEach(tab => {
        tab.classList.remove('active');
        tab.style.background = 'transparent';
    });
    event.target.classList.add('active');
    event.target.style.background = 'white';

    document.querySelectorAll('.stats-tab-content').forEach(content => {
        content.style.display = 'none';
    });

    const tabContent = document.getElementById(`stats-${tabName}`);
    if (tabContent) {
        tabContent.style.display = 'block';
    }

    if (tabName === 'users' && cachedVehicleUsers) {
        renderVehicleUsers(cachedVehicleUsers);
    } else if (tabName === 'comparison' && cachedComparison) {
        renderComparison(cachedComparison);
    }
}

async function loadStatistics() {
    const dateInput = document.getElementById('stats-date');
    if (!dateInput || !dateInput.value) {
        alert("Lütfen bir tarih seçin.");
        return;
    }

    const targetDate = dateInput.value;

    document.getElementById('stats-loading').style.display = 'block';
    document.getElementById('stats-content').style.display = 'none';

    try {
        const stats = await API.get(`/logistics/admin/statistics/${targetDate}`);
        cachedStats = stats;

        if (stats.status === 'no_data') {
            document.getElementById('stats-loading').innerHTML = `
                <p style="color: #6b7280;">📅 ${targetDate} tarihi için rota bulunamadı.</p>
                <p style="font-size: 0.9rem; color: #9ca3af;">Önce "Rota Oluştur" ile optimizasyon yapın.</p>
            `;
            return;
        }

        const vehicleUsers = await API.get(`/logistics/admin/vehicle-users/${targetDate}`);
        cachedVehicleUsers = vehicleUsers;



        renderStatisticsOverview(stats);
        renderVehicleBreakdown(stats.vehicle_breakdown);
        renderVehicleUsers(vehicleUsers);


        document.getElementById('stats-loading').style.display = 'none';
        document.getElementById('stats-content').style.display = 'block';

    } catch (err) {
        console.error("Failed to load statistics:", err);
        document.getElementById('stats-loading').innerHTML = `
            <p style="color: #ef4444;">❌ İstatistikler yüklenirken hata oluştu.</p>
            <p style="font-size: 0.9rem; color: #6b7280;">${err.message || err}</p>
        `;
    }
}

function renderStatisticsOverview(stats) {
    const summary = stats.summary;

    document.getElementById('stat-total-cost').innerText = summary.total_cost.toLocaleString();
    document.getElementById('stat-total-distance').innerText = summary.total_distance.toLocaleString();
    document.getElementById('stat-total-cargo').innerText = summary.total_cargo_transported;
    document.getElementById('stat-total-weight').innerText = summary.total_weight_transported;
    document.getElementById('stat-vehicle-count').innerText = summary.total_routes;

    const fleetInfo = summary.total_fleet_size
        ? `${summary.owned_vehicles_used} / ${summary.total_fleet_size}`
        : summary.owned_vehicles_used;

    document.getElementById('stat-owned').innerText = fleetInfo;
    document.getElementById('stat-rented').innerText = summary.rented_vehicles_used;

    document.getElementById('stat-avg-cost').innerText = summary.avg_cost_per_route + ' birim';
    document.getElementById('stat-avg-distance').innerText = summary.avg_distance_per_route + ' km';
    document.getElementById('stat-cost-per-kg').innerText = summary.cost_per_kg + ' birim/kg';
    document.getElementById('stat-acceptance-rate').innerText = summary.acceptance_rate_weight + '%';

    renderCapacityChart(stats.vehicle_breakdown);
    renderStationChart(stats.station_breakdown);
}


function renderCapacityChart(vehicles) {
    const ctx = document.getElementById('capacity-chart');
    if (!ctx) return;

    if (capacityChart) {
        capacityChart.destroy();
    }

    const labels = vehicles.map(v => v.vehicle_name);
    const utilization = vehicles.map(v => v.utilization);
    const chartColors = vehicles.map(v => v.is_rented ? 'rgba(245, 87, 108, 0.8)' : 'rgba(102, 126, 234, 0.8)');

    capacityChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Kapasite Kullanımı (%)',
                data: utilization,
                backgroundColor: chartColors,
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: value => value + '%'
                    }
                }
            }
        }
    });
}

function renderStationChart(stations) {
    const ctx = document.getElementById('station-chart');
    if (!ctx) return;

    if (stationChart) {
        stationChart.destroy();
    }

    const labels = stations.map(s => s.station_name);
    const weights = stations.map(s => s.total_weight);

    const generateColors = (count) => {
        const colors = [];
        for (let i = 0; i < count; i++) {
            const hue = (i * 137.508) % 360;
            colors.push(`hsla(${hue}, 70%, 60%, 0.8)`);
        }
        return colors;
    };

    const colors = generateColors(stations.length);

    stationChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: weights,
                backgroundColor: colors,
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        boxWidth: 12,
                        font: { size: 11 }
                    }
                }
            }
        }
    });
}

function renderVehicleBreakdown(vehicles) {
    const container = document.getElementById('vehicles-list');
    if (!container) return;

    if (!vehicles || vehicles.length === 0) {
        container.innerHTML = '<p style="color: #6b7280; text-align: center;">Araç verisi bulunamadı.</p>';
        return;
    }

    let html = '';
    vehicles.forEach(v => {
        const rentedBadge = v.is_rented
            ? '<span class="badge badge-warning">Kiralık</span>'
            : '<span class="badge badge-success">Mevcut</span>';

        html += `
            <div class="vehicle-card ${v.is_rented ? 'rented' : ''}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 1.5rem;">🚛</span>
                        <div>
                            <strong style="font-size: 1rem;">${v.vehicle_name}</strong>
                            ${rentedBadge}
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-weight: 700; color: #667eea;">${v.cost.toFixed(2)} birim</div>
                        <div style="font-size: 0.8rem; color: #6b7280;">${v.distance.toFixed(2)} km</div>
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin: 0.75rem 0;">
                    <div style="background: #f8fafc; padding: 0.5rem; border-radius: 6px; text-align: center;">
                        <div style="font-size: 0.75rem; color: #6b7280;">Kapasite</div>
                        <div style="font-weight: 600;">${v.capacity} kg</div>
                    </div>
                    <div style="background: #f8fafc; padding: 0.5rem; border-radius: 6px; text-align: center;">
                        <div style="font-size: 0.75rem; color: #6b7280;">Yük</div>
                        <div style="font-weight: 600;">${v.cargo_weight} kg</div>
                    </div>
                    <div style="background: #f8fafc; padding: 0.5rem; border-radius: 6px; text-align: center;">
                        <div style="font-size: 0.75rem; color: #6b7280;">Doluluk</div>
                        <div style="font-weight: 600; color: ${v.utilization > 80 ? '#22c55e' : '#f59e0b'};">${v.utilization}%</div>
                    </div>
                </div>
                
                <div style="margin-top: 0.5rem;">
                    <div style="font-size: 0.8rem; color: #6b7280; margin-bottom: 0.25rem;">Ziyaret Edilen İstasyonlar:</div>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.25rem;">
                        ${v.stations.map(s => `<span style="background: #e0e7ff; color: #4338ca; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.75rem;">${s}</span>`).join('')}
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function renderVehicleUsers(data) {
    const container = document.getElementById('users-list');
    if (!container) return;

    if (!data || data.status === 'no_data' || !data.vehicles || data.vehicles.length === 0) {
        container.innerHTML = '<p style="color: #6b7280; text-align: center;">Kullanıcı verisi bulunamadı.</p>';
        return;
    }

    let html = `
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem; border-radius: 12px; margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 0.9rem; opacity: 0.9;">Toplam Kullanıcı</div>
                    <div style="font-size: 2rem; font-weight: 700;">${data.total_users}</div>
                </div>
                <div style="font-size: 3rem; opacity: 0.3;">👥</div>
            </div>
        </div>
    `;

    data.vehicles.forEach(v => {
        html += `
            <div class="vehicle-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                    <div>
                        <strong>🚛 ${v.vehicle_name}</strong>
                        <span class="badge badge-info" style="margin-left: 0.5rem;">${v.user_count} kullanıcı</span>
                    </div>
                    <div style="font-size: 0.9rem; color: #6b7280;">${v.cargo_weight} kg</div>
                </div>
                
                <div style="display: flex; flex-wrap: wrap; gap: 0.25rem;">
                    ${v.users.map(u => `
                        <div class="user-chip">
                            <span>👤</span>
                            <span>${u.username}</span>
                            <span style="color: #818cf8; font-size: 0.7rem;">${u.cargo_weight}kg</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}




let cachedArchive = null;

function toggleArchiveModal() {
    const modal = document.getElementById('archive-modal');
    const overlay = document.getElementById('modal-overlay');
    const isOpen = modal.classList.contains('active');

    if (!isOpen) {
        closeAllModals();
        modal.classList.add('active');
        overlay.classList.add('active');
        loadArchive();
    } else {
        closeAllModals();
    }
}

async function loadArchive() {
    const loadingEl = document.getElementById('archive-loading');
    const contentEl = document.getElementById('archive-content');
    const emptyEl = document.getElementById('archive-empty');

    loadingEl.style.display = 'block';
    contentEl.style.display = 'none';
    emptyEl.style.display = 'none';

    try {
        const data = await API.get('/logistics/admin/routes-archive');
        cachedArchive = data;

        if (data.status === 'no_data' || !data.dates || data.dates.length === 0) {
            loadingEl.style.display = 'none';
            emptyEl.style.display = 'block';
            return;
        }

        let totalCargo = 0;
        let totalCost = 0;
        data.dates.forEach(d => {
            totalCargo += d.total_cargo_count;
            totalCost += d.total_cost;
        });

        document.getElementById('archive-total-routes').textContent = data.total_routes;
        document.getElementById('archive-total-dates').textContent = data.total_dates;
        document.getElementById('archive-total-cargo').textContent = totalCargo.toLocaleString();
        document.getElementById('archive-total-cost').textContent = totalCost.toLocaleString();

        renderArchiveDates(data.dates);

        loadingEl.style.display = 'none';
        contentEl.style.display = 'block';

    } catch (err) {
        console.error("Failed to load archive:", err);
        loadingEl.innerHTML = `
            <div style="color: #ef4444;">
                <div style="font-size: 2rem; margin-bottom: 1rem;">❌</div>
                <p>Arşiv yüklenirken hata oluştu.</p>
                <p style="font-size: 0.85rem; color: #6b7280;">${err.message || err}</p>
            </div>
        `;
    }
}

function renderArchiveDates(dates) {
    const container = document.getElementById('archive-dates-list');

    if (!dates || dates.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #6b7280;">Veri bulunamadı.</p>';
        return;
    }

    let html = '';

    dates.forEach((dateData, index) => {
        const formattedDate = new Date(dateData.date).toLocaleDateString('tr-TR', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });

        const scenarioBadge = dateData.scenario_type === 'unlimited'
            ? '<span style="background: #dcfce7; color: #16a34a; padding: 0.25rem 0.5rem; border-radius: 6px; font-size: 0.75rem; font-weight: 600;">Sınırsız Araç</span>'
            : '<span style="background: #fef3c7; color: #92400e; padding: 0.25rem 0.5rem; border-radius: 6px; font-size: 0.75rem; font-weight: 600;">Belirli Araç</span>';

        html += `
            <div style="background: white; border: 1px solid #e5e7eb; border-radius: 12px; margin-bottom: 1rem; overflow: hidden;">
                <div style="padding: 1rem; cursor: pointer; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);" 
                     onclick="toggleArchiveDetails(${index})">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="display: flex; align-items: center; gap: 1rem;">
                            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; width: 50px; height: 50px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.25rem;">
                                📅
                            </div>
                            <div>
                                <div style="font-weight: 700; color: #1f2937; font-size: 1.1rem;">${formattedDate}</div>
                                <div style="display: flex; gap: 0.5rem; margin-top: 0.25rem;">
                                    ${scenarioBadge}
                                    <span style="color: #6b7280; font-size: 0.85rem;">${dateData.vehicle_count} araç</span>
                                    ${dateData.rented_count > 0 ? `<span style="color: #f59e0b; font-size: 0.85rem;">(${dateData.rented_count} kiralık)</span>` : ''}
                                </div>
                            </div>
                        </div>
                        <div style="display: flex; gap: 1.5rem; align-items: center;">
                            <div style="text-align: center;">
                                <div style="font-size: 0.75rem; color: #6b7280;">Mesafe</div>
                                <div style="font-weight: 700; color: #374151;">${dateData.total_distance.toLocaleString()} km</div>
                            </div>
                            <div style="text-align: center;">
                                <div style="font-size: 0.75rem; color: #6b7280;">Maliyet</div>
                                <div style="font-weight: 700; color: #667eea;">${dateData.total_cost.toLocaleString()} ₺</div>
                            </div>
                            <div style="text-align: center;">
                                <div style="font-size: 0.75rem; color: #6b7280;">Kargo</div>
                                <div style="font-weight: 700; color: #11998e;">${dateData.total_cargo_count} adet</div>
                            </div>
                            <div style="transform: rotate(0deg); transition: transform 0.3s;" id="archive-arrow-${index}">▼</div>
                        </div>
                    </div>
                </div>
                
                <div id="archive-details-${index}" style="display: none; padding: 1rem; border-top: 1px solid #e5e7eb;">
                    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 0.75rem;">
                        ${dateData.routes.map(route => `
                            <div style="background: ${route.is_rented ? '#fef3c7' : '#f0f9ff'}; padding: 0.75rem; border-radius: 8px; border-left: 4px solid ${route.is_rented ? '#f59e0b' : '#3b82f6'};">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                    <strong style="color: #374151;">🚛 ${route.vehicle_name}</strong>
                                    ${route.is_rented ? '<span style="font-size: 0.7rem; background: #f59e0b; color: white; padding: 0.15rem 0.4rem; border-radius: 4px;">Kiralık</span>' : ''}
                                </div>
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.25rem; font-size: 0.85rem; color: #6b7280;">
                                    <div>📦 ${route.cargo_count} adet</div>
                                    <div>⚖️ ${route.cargo_weight} kg</div>
                                    <div>📍 ${route.total_distance.toFixed(2)} km</div>
                                    <div>💰 ${route.total_cost.toFixed(2)} ₺</div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function toggleArchiveDetails(index) {
    const details = document.getElementById(`archive-details-${index}`);
    const arrow = document.getElementById(`archive-arrow-${index}`);

    if (details.style.display === 'none') {
        details.style.display = 'block';
        arrow.style.transform = 'rotate(180deg)';
    } else {
        details.style.display = 'none';
        arrow.style.transform = 'rotate(0deg)';
    }
}

function viewArchiveDateOnMap(dateStr) {
    closeAllModals();

    const dateInput = document.getElementById('route-display-date');
    if (dateInput) {
        dateInput.value = dateStr;
    }

    loadRoutesForDateWithOSRM(dateStr);

    alert(`${dateStr} tarihli rotalar haritada gösteriliyor.`);
}
