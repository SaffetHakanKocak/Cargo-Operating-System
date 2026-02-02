
var map = L.map('map', {
    zoomControl: false
}).setView([40.7653, 29.9408], 11);

L.control.zoom({
    position: 'bottomright'
}).addTo(map);

L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
}).addTo(map);

var legend = L.control({ position: 'bottomleft' });

legend.onAdd = function (map) {
    var div = L.DomUtil.create('div', 'info legend');
    div.style.backgroundColor = "white";
    div.style.padding = "15px";
    div.style.borderRadius = "5px";
    div.style.boxShadow = "0 0 15px rgba(0,0,0,0.2)";
    div.style.fontSize = "1.2rem";


    div.innerHTML += '<div style="display: flex; align-items: center; margin-bottom: 8px;"><img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png" style="height: 30px; margin-right: 8px;"> <span>Hedef (Umuttepe)</span></div>';
    div.innerHTML += '<div style="display: flex; align-items: center; margin-bottom: 8px;"><img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png" style="height: 30px; margin-right: 8px;"> <span>İstasyon</span></div>';
    div.innerHTML += '<div style="display: flex; align-items: center;"><img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-orange.png" style="height: 30px; margin-right: 8px;"> <span>Kargo Verilen İstasyon</span></div>';
    return div;
};

legend.addTo(map);

let coordPopup = null;
map.on('contextmenu', function (e) {
    if (coordPopup) {
        map.removeLayer(coordPopup);
        coordPopup = null;
    } else {
        coordPopup = L.popup()
            .setLatLng(e.latlng)
            .setContent("Lat: " + e.latlng.lat.toFixed(4) + "<br>Lon: " + e.latlng.lng.toFixed(4))
            .openOn(map);
    }
});

const districtMarkers = {};
const routeLayers = [];
const stationsLayer = L.layerGroup();
let areStationsVisible = true;

const colors = ['red', 'blue', 'green', 'orange', 'purple'];

const blueIcon = new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

const orangeIcon = new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-orange.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

const greenIcon = new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

async function initMap() {
    try {
        const stations = await API.get('/logistics/stations');
        stations.forEach(s => {
            stationDataMap[s.id] = { name: s.name, latitude: s.latitude, longitude: s.longitude };

            const isTarget = s.name.toLowerCase() === 'umuttepe';
            const icon = isTarget ? greenIcon : blueIcon;
            const marker = L.marker([s.latitude, s.longitude], { icon: icon });
            const popupContent = isTarget
                ? `<b>${s.name}</b> (Hedef)<br>Lat: ${s.latitude}<br>Lon: ${s.longitude}`
                : `<b>${s.name}</b><br>Lat: ${s.latitude}<br>Lon: ${s.longitude}`;
            marker.bindPopup(popupContent);
            stationsLayer.addLayer(marker);
            districtMarkers[s.id] = marker;
        });

        if (areStationsVisible) {
            stationsLayer.addTo(map);
        }
    } catch (err) {
        console.error("Error loading stations:", err);
    }

    loadRoutes();
}

let stationDataMap = {};

function highlightMyStations(stationIds) {
    Object.entries(districtMarkers).forEach(([id, marker]) => {
        const stationName = stationDataMap[id]?.name || '';
        const isTarget = stationName.toLowerCase() === 'umuttepe';
        marker.setIcon(isTarget ? greenIcon : blueIcon);
    });

    stationIds.forEach(id => {
        if (districtMarkers[id]) {
            const stationName = stationDataMap[id]?.name || '';
            if (stationName.toLowerCase() !== 'umuttepe') {
                districtMarkers[id].setIcon(orangeIcon);
            }
        }
    });
}


function toggleStationMarkers() {
    areStationsVisible = !areStationsVisible;
    const btn = document.getElementById('toggle-stations-btn');

    if (areStationsVisible) {
        stationsLayer.addTo(map);
        if (btn) btn.innerText = "İstasyonları Gizle";
    } else {
        stationsLayer.remove();
        if (btn) btn.innerText = "İstasyonları Göster";
    }
}

async function loadRoutes() {
    routeLayers.forEach(l => map.removeLayer(l));
    routeLayers.length = 0;

    try {
        const routes = await API.get('/logistics/admin/routes');
        const statusDiv = document.getElementById('status-msg');

        if (statusDiv) {
            if (routes.length === 0) {
                statusDiv.innerText = "Henüz rota planlanmadı.";
                return;
            }
            statusDiv.innerText = `${routes.length} araç için rota planlandı.`;
        }


        routes.forEach((route, index) => {
            let path = typeof route.path_data === 'string' ? JSON.parse(route.path_data) : route.path_data;

            const latlngs = path.map(p => [p.lat, p.lon]);

            const color = colors[index % colors.length];
            const line = L.polyline(latlngs, { color: color, weight: 4 }).addTo(map);
            routeLayers.push(line);

            line.bindPopup(`<b>Araç: ${route.vehicle_id}</b><br>Maliyet: ${route.total_cost}<br>Mesafe: ${route.total_distance} km`);
        });
    } catch (err) {
        console.warn("Could not load routes (normal for non-admins):", err);
    }
}

function optimize(scenario) {
    if (!confirm(scenario + " senaryosu için optimizasyon başlatılsın mı? Mevcut rotalar silinecek.")) return;

    API.post('/logistics/admin/optimize?scenario=' + scenario, {})
        .then(res => {
            alert("Optimizasyon Tamamlandı!");
            loadRoutes();
        })
        .catch(err => alert("Hata: " + err.message));
}


function closeAllModals() {
    document.getElementById('stations-modal').classList.remove('active');
    document.getElementById('station-name-modal').classList.remove('active');
    const paramsModal = document.getElementById('parameters-modal');
    if (paramsModal) paramsModal.classList.remove('active');
    const routeModal = document.getElementById('route-planning-modal');
    if (routeModal) routeModal.classList.remove('active');
    const routeDisplayModal = document.getElementById('route-display-modal');
    if (routeDisplayModal) routeDisplayModal.classList.remove('active');
    const matrixModal = document.getElementById('distance-matrix-modal');
    if (matrixModal) matrixModal.classList.remove('active');
    const inspectModal = document.getElementById('route-inspect-modal');
    if (inspectModal) inspectModal.classList.remove('active');
    const statsModal = document.getElementById('statistics-modal');
    if (statsModal) statsModal.classList.remove('active');
    const archiveModal = document.getElementById('archive-modal');
    if (archiveModal) archiveModal.classList.remove('active');
    document.getElementById('modal-overlay').classList.remove('active');
}

let isAddStationMode = false;
let tempStationCoords = null;

function toggleAddStationMode() {
    const btn = document.getElementById('add-station-btn');
    if (!btn) return;

    isAddStationMode = !isAddStationMode;

    if (isAddStationMode) {
        btn.classList.add('btn-danger');
        btn.innerText = "İptal Et";
        map.getContainer().style.cursor = 'crosshair';
    } else {
        btn.classList.remove('btn-danger');
        btn.innerText = "İstasyon Ekle";
        map.getContainer().style.cursor = '';
        tempStationCoords = null;
    }
}

map.on('click', function (e) {
    if (!isAddStationMode) return;

    tempStationCoords = { lat: e.latlng.lat, lon: e.latlng.lng };

    const modal = document.getElementById('station-name-modal');
    const overlay = document.getElementById('modal-overlay');
    const input = document.getElementById('new-station-name');
    const errorDiv = document.getElementById('station-modal-error');

    input.value = "";
    if (errorDiv) {
        errorDiv.innerText = "";
        errorDiv.style.display = "none";
    }

    modal.classList.add('active');
    overlay.classList.add('active');

    setTimeout(() => input.focus(), 100);
});

function handleEnterKey(e) {
    if (e.key === 'Enter') {
        confirmAddStation();
    }
}

async function confirmAddStation() {
    if (!tempStationCoords) return;

    const input = document.getElementById('new-station-name');
    const errorDiv = document.getElementById('station-modal-error');
    const stationName = input.value.trim();

    if (!stationName) {
        if (errorDiv) {
            errorDiv.innerText = "Lütfen bir isim giriniz.";
            errorDiv.style.display = "block";
        }
        return;
    }

    try {
        const newStation = await API.post('/logistics/stations', {
            name: stationName,
            latitude: tempStationCoords.lat,
            longitude: tempStationCoords.lon
        });

        const marker = L.marker([newStation.latitude, newStation.longitude]);
        marker.bindPopup(`<b>${newStation.name}</b><br>Lat: ${newStation.latitude}<br>Lon: ${newStation.longitude}`);
        stationsLayer.addLayer(marker);
        marker.openPopup();

        if (!areStationsVisible) {
            toggleStationMarkers();
        }

        closeAllModals();
        toggleAddStationMode();
    } catch (err) {
        console.error("Station add error:", err);
        if (errorDiv) {
            errorDiv.innerText = err.message || "İstasyon eklenirken hata oluştu.";
            errorDiv.style.display = "block";
        } else {
            alert("Hata: " + (err.message || err));
        }
    }
}
