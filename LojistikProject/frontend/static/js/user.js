
const token = localStorage.getItem("token");
const role = localStorage.getItem("role");

if (!token) {
    window.location.href = "login.html";
} else if (role === 'admin') {
    window.location.href = "admin_dashboard.html";
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        hideLogoutModal();
    }
});
let currentDate = new Date();

function updateDateDisplay() {
    const dateDisplay = document.getElementById('request-date-display');
    if (dateDisplay) {
        dateDisplay.value = currentDate.toLocaleDateString('tr-TR');
    }
}

function adjustDate(days) {
    currentDate.setDate(currentDate.getDate() + days);
    updateDateDisplay();
}

document.addEventListener('DOMContentLoaded', async () => {
    updateDateDisplay();

    try {
        const user = await API.get('/auth/me');
        const nameDisplay = document.getElementById('user-name-display');
        const avatarDisplay = document.getElementById('user-avatar');

        if (nameDisplay) nameDisplay.innerText = user.username;
        if (avatarDisplay && user.username) {
            avatarDisplay.innerText = user.username.charAt(0).toUpperCase();
        }
    } catch (err) {
        console.error("Failed to fetch user info", err);
    }
});

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

async function loadStations() {
    try {
        const stations = await API.get('/logistics/stations');
        const select = document.getElementById('station-select');
        select.innerHTML = '<option value="">Seçiniz...</option>'; // Reset
        stations.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = s.name;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error("Failed to load stations", err);
    }
}

async function loadMyRequests() {
    try {
        const requests = await API.get('/logistics/cargo/me');
        const container = document.getElementById('requests-container');
        const countBadge = document.getElementById('requests-count-badge');
        container.innerHTML = '';
        const myStationIds = [];

        if (countBadge) {
            countBadge.textContent = requests.length;
        }

        if (requests.length === 0) {
            container.innerHTML = `
                <div style="padding: 2rem; text-align: center; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 12px; border: 2px dashed #e2e8f0;">
                    <div style="font-size: 3rem; margin-bottom: 0.5rem;">📭</div>
                    <div style="color: #64748b; font-weight: 500;">Henüz kargo talebiniz bulunmuyor</div>
                    <div style="color: #94a3b8; font-size: 0.85rem; margin-top: 0.25rem;">Yeni talep oluşturmak için yukarıdaki formu kullanın</div>
                </div>
            `;
            return;
        }

        const groupedByDate = {};
        requests.forEach(r => {
            const dateKey = new Date(r.request_date).toLocaleDateString('tr-TR');
            if (!groupedByDate[dateKey]) {
                groupedByDate[dateKey] = [];
            }
            groupedByDate[dateKey].push(r);
            if (r.station && r.station.id) {
                myStationIds.push(r.station.id);
            }
        });

        Object.keys(groupedByDate).sort((a, b) => {
            const dateA = new Date(a.split('.').reverse().join('-'));
            const dateB = new Date(b.split('.').reverse().join('-'));
            return dateB - dateA;
        }).forEach(dateKey => {
            const dateRequests = groupedByDate[dateKey];
            const totalWeight = dateRequests.reduce((sum, r) => sum + r.weight, 0);
            const totalCount = dateRequests.reduce((sum, r) => sum + r.cargo_count, 0);

            const dateSection = document.createElement('div');
            dateSection.style.marginBottom = '1rem';
            dateSection.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; padding: 0.5rem 0; border-bottom: 1px solid #e5e7eb;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 1rem;">📅</span>
                        <span style="font-weight: 600; color: #374151;">${dateKey}</span>
                    </div>
                    <div style="display: flex; gap: 0.75rem;">
                        <span style="background: #f0f9ff; color: #0369a1; padding: 0.2rem 0.6rem; border-radius: 8px; font-size: 0.75rem; font-weight: 600;">${totalWeight} kg</span>
                        <span style="background: #fef3c7; color: #92400e; padding: 0.2rem 0.6rem; border-radius: 8px; font-size: 0.75rem; font-weight: 600;">${totalCount} adet</span>
                    </div>
                </div>
            `;

            const cardsContainer = document.createElement('div');
            cardsContainer.style.display = 'flex';
            cardsContainer.style.flexDirection = 'column';
            cardsContainer.style.gap = '0.5rem';

            dateRequests.forEach(r => {
                const card = document.createElement('div');
                card.style.cssText = `
                    background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
                    border: 1px solid #e5e7eb;
                    border-left: 4px solid #667eea;
                    border-radius: 10px;
                    padding: 0.75rem 1rem;
                    display: grid;
                    grid-template-columns: 1fr auto;
                    gap: 0.5rem;
                    align-items: center;
                    transition: all 0.2s ease;
                    cursor: default;
                `;
                card.onmouseover = () => {
                    card.style.borderLeftColor = '#764ba2';
                    card.style.boxShadow = '0 4px 12px rgba(102, 126, 234, 0.15)';
                    card.style.transform = 'translateX(4px)';
                };
                card.onmouseout = () => {
                    card.style.borderLeftColor = '#667eea';
                    card.style.boxShadow = 'none';
                    card.style.transform = 'translateX(0)';
                };

                card.innerHTML = `
                    <div>
                        <div style="font-weight: 600; color: #1f2937; font-size: 0.95rem; display: flex; align-items: center; gap: 0.35rem;">
                            <span style="color: #ef4444;">📍</span>
                            ${r.station.name}
                        </div>
                    </div>
                    <div style="display: flex; gap: 0.5rem; align-items: center;">
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.3rem 0.6rem; border-radius: 8px; font-size: 0.8rem; font-weight: 600;">
                            ${r.weight} kg
                        </div>
                        <div style="background: #f1f5f9; color: #475569; padding: 0.3rem 0.6rem; border-radius: 8px; font-size: 0.8rem; font-weight: 500;">
                            ${r.cargo_count} adet
                        </div>
                    </div>
                `;
                cardsContainer.appendChild(card);
            });

            dateSection.appendChild(cardsContainer);
            container.appendChild(dateSection);
        });

        const uniqueStationIds = [...new Set(myStationIds)];
        console.log("My Station IDs to highlight:", uniqueStationIds);

        const tryHighlight = (attempts = 0) => {
            if (typeof highlightMyStations === 'function' && Object.keys(districtMarkers).length > 0) {
                highlightMyStations(uniqueStationIds);
            } else if (attempts < 10) {
                setTimeout(() => tryHighlight(attempts + 1), 500);
            }
        };

        tryHighlight();
    } catch (err) {
        console.error("Failed to load requests", err);
    }
}

const cargoForm = document.getElementById('cargo-form');
if (cargoForm) {
    cargoForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const station_id = document.getElementById('station-select').value;
        const weight = document.getElementById('weight').value;
        const count = document.getElementById('count').value;

        try {
            await API.post('/logistics/cargo', {
                station_id: parseInt(station_id),
                weight: parseFloat(weight),
                cargo_count: parseInt(count),
                request_date: currentDate.toISOString()
            });

            const msg = document.getElementById('success-message');
            if (msg) {
                msg.style.display = 'inline';
                setTimeout(() => { msg.style.display = 'none'; }, 3000);
            }

            loadMyRequests();
            cargoForm.reset();

            currentDate = new Date();
            updateDateDisplay();

        } catch (err) {
            alert(err.message);
        }
    });
}

function togglePanel(id) {
    const panel = document.getElementById(id);
    if (panel.style.display === 'none' || panel.style.display === '') {
        panel.style.display = 'block';
    } else {
        panel.style.display = 'none';
    }
}


let myRouteLayers = [];

const routeColors = ['#2563eb', '#dc2626', '#16a34a', '#ea580c', '#7c3aed', '#0891b2'];

async function loadMyRoute() {
    const dateInput = document.getElementById('route-view-date');
    const resultDiv = document.getElementById('my-route-result');
    const statusDiv = document.getElementById('my-route-status');
    const detailsDiv = document.getElementById('my-route-details');
    const routesListDiv = document.getElementById('my-routes-list');

    if (!dateInput || !dateInput.value) {
        alert("Lütfen bir tarih seçin.");
        return;
    }

    const targetDate = dateInput.value;

    resultDiv.style.display = 'block';
    statusDiv.innerHTML = '<em>Rota yükleniyor...</em>';
    statusDiv.style.background = '#e3f2fd';
    statusDiv.style.color = '#1565c0';
    detailsDiv.style.display = 'none';

    try {
        const result = await API.get(`/logistics/routes/my/${targetDate}`);

        if (result.status === 'success' && result.routes && result.routes.length > 0) {
            statusDiv.innerHTML = `✅ ${result.message}`;
            statusDiv.style.background = '#e8f5e9';
            statusDiv.style.color = '#2e7d32';

            const cargoSummaryDiv = document.getElementById('cargo-summary-section');
            if (result.user_cargo && cargoSummaryDiv) {
                cargoSummaryDiv.innerHTML = `
                    <div style="background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border: 1px solid #86efac; border-radius: 12px; padding: 1rem; margin-bottom: 1rem;">
                        <div style="font-weight: 600; color: #166534; margin-bottom: 0.5rem;">📦 Kargo Özetiniz</div>
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; font-size: 0.9rem;">
                            <div style="color: #6b7280;">Toplam Ağırlık:</div>
                            <div style="font-weight: 700; color: #166534;">${result.user_cargo.total_weight} kg</div>
                            <div style="color: #6b7280;">Toplam Kargo:</div>
                            <div style="font-weight: 700; color: #166534;">${result.user_cargo.total_count} adet</div>
                        </div>
                    </div>
                `;
            }


            let routesHtml = '';
            result.routes.forEach((route, index) => {
                const color = routeColors[index % routeColors.length];
                const isRented = route.vehicle_name && route.vehicle_name.toLowerCase().includes('kiralık');

                routesHtml += `
                    <div style="background: linear-gradient(135deg, ${color}15 0%, ${color}08 100%); padding: 1rem; border-radius: 12px; margin-bottom: 0.75rem; border-left: 4px solid ${color}; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                        <!-- Vehicle Header -->
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                            <div style="display: flex; align-items: center; gap: 0.5rem;">
                                <span style="font-size: 1.5rem;">🚛</span>
                                <div>
                                    <strong style="font-size: 1rem; color: #374151;">${route.vehicle_name}</strong>
                                    ${isRented ? '<span style="background: #fef3c7; color: #92400e; padding: 0.15rem 0.5rem; border-radius: 10px; font-size: 0.7rem; margin-left: 0.5rem;">Kiralık</span>' : ''}
                                </div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 0.75rem; color: #6b7280;">Maliyet</div>
                                <div style="font-weight: 700; color: ${color};">${route.total_cost} birim</div>
                            </div>
                        </div>
                        
                        <!-- Route Stats -->
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin-bottom: 0.75rem;">
                            <div style="background: white; padding: 0.5rem; border-radius: 8px; text-align: center;">
                                <div style="font-size: 0.7rem; color: #6b7280;">📏 Mesafe</div>
                                <div style="font-weight: 600; color: #374151;">${route.total_distance} km</div>
                            </div>
                            <div style="background: white; padding: 0.5rem; border-radius: 8px; text-align: center;">
                                <div style="font-size: 0.7rem; color: #6b7280;">📦 Kargo</div>
                                <div style="font-weight: 600; color: #374151;">${route.cargo_count} adet</div>
                            </div>
                            <div style="background: white; padding: 0.5rem; border-radius: 8px; text-align: center;">
                                <div style="font-size: 0.7rem; color: #6b7280;">⚖️ Yük</div>
                                <div style="font-weight: 600; color: #374151;">${route.cargo_weight} kg</div>
                            </div>
                        </div>
                        
                        <!-- Your Stations -->
                        <div>
                            <div style="font-size: 0.8rem; color: #6b7280; margin-bottom: 0.35rem;">📍 Kargonuzun Bulunduğu İstasyonlar:</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 0.25rem;">
                                ${route.user_stations.map(s => `<span style="background: linear-gradient(135deg, ${color} 0%, ${color}dd 100%); color: white; padding: 0.25rem 0.6rem; border-radius: 15px; font-size: 0.75rem; font-weight: 500;">${s}</span>`).join('')}
                            </div>
                        </div>
                    </div>
                `;
            });

            routesListDiv.innerHTML = routesHtml;
            detailsDiv.style.display = 'block';

            clearMyRoute(false);
            for (let i = 0; i < result.routes.length; i++) {
                const route = result.routes[i];
                const color = routeColors[i % routeColors.length];
                await drawMyRoute(route, color, i);
            }

            if (myRouteLayers.length > 0) {
                const group = L.featureGroup(myRouteLayers);
                map.fitBounds(group.getBounds().pad(0.1));
            }

        } else if (result.status === 'no_cargo') {
            statusDiv.innerHTML = `ℹ️ ${result.message}`;
            statusDiv.style.background = '#fff3e0';
            statusDiv.style.color = '#e65100';
        } else if (result.status === 'no_routes') {
            statusDiv.innerHTML = `⏳ ${result.message}`;
            statusDiv.style.background = '#fff3e0';
            statusDiv.style.color = '#e65100';
            if (result.user_stations && result.user_stations.length > 0) {
                statusDiv.innerHTML += `<br><small>İstasyonlarınız: ${result.user_stations.join(', ')}</small>`;
            }
        } else if (result.status === 'not_assigned') {
            statusDiv.innerHTML = `⚠️ ${result.message}`;
            statusDiv.style.background = '#fce4ec';
            statusDiv.style.color = '#c62828';
        } else {
            statusDiv.innerHTML = `❌ ${result.message || 'Bilinmeyen hata'}`;
            statusDiv.style.background = '#ffebee';
            statusDiv.style.color = '#c62828';
        }

    } catch (err) {
        console.error("Failed to load route:", err);
        statusDiv.innerHTML = `❌ Hata: ${err.message || 'Rota yüklenemedi'}`;
        statusDiv.style.background = '#ffebee';
        statusDiv.style.color = '#c62828';
    }
}

function isUserStationMatch(stationName, userStations) {
    if (!stationName || !userStations || !userStations.length) return false;

    if (userStations.includes(stationName)) return true;

    for (const userStation of userStations) {
        if (stationName.startsWith(userStation)) return true;
        if (userStation.startsWith(stationName)) return true;
    }

    const baseName = stationName.replace(/\s*\(.*\)\s*$/, '').trim();
    if (userStations.includes(baseName)) return true;

    return false;
}

async function drawMyRoute(route, color = '#2563eb', routeIndex = 0) {

    const pathData = route.path_data;
    const path = pathData.path || pathData;

    if (!path || path.length < 2) {
        console.warn("Not enough points to draw route");
        return;
    }

    const coordinates = path.map(p => ({ lat: p.lat, lon: p.lon, name: p.name }));

    const coordString = coordinates.map(c => `${c.lon},${c.lat}`).join(';');
    const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${coordString}?overview=full&geometries=geojson`;

    try {
        const response = await fetch(osrmUrl);
        const data = await response.json();

        if (data.code === 'Ok' && data.routes && data.routes[0]) {
            const routeGeometry = data.routes[0].geometry;

            const routeLayer = L.geoJSON(routeGeometry, {
                style: { color: color, weight: 6, opacity: 0.8 }
            });

            routeLayer.bindPopup(`<b>${route.vehicle_name}</b><br>Mesafe: ${route.total_distance} km`);
            routeLayer.addTo(map);
            myRouteLayers.push(routeLayer);

            coordinates.forEach((coord, index) => {
                const isDepot = coord.name && coord.name.toLowerCase().includes('umuttepe');
                const isUserStation = isUserStationMatch(coord.name, route.user_stations);

                const icon = L.divIcon({
                    className: 'route-marker',
                    html: `<div style="
                        background: ${isDepot ? '#22c55e' : (isUserStation ? color : '#64748b')};
                        color: white;
                        width: ${isUserStation ? '28px' : '24px'};
                        height: ${isUserStation ? '28px' : '24px'};
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-weight: bold;
                        font-size: ${isUserStation ? '14px' : '12px'};
                        border: 3px solid white;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                    ">${isDepot ? '🏠' : (index + 1)}</div>`,
                    iconSize: [isUserStation ? 28 : 24, isUserStation ? 28 : 24],
                    iconAnchor: [isUserStation ? 14 : 12, isUserStation ? 14 : 12]
                });

                const marker = L.marker([coord.lat, coord.lon], { icon: icon });

                const popupText = isDepot
                    ? `<b>${coord.name}</b> (Hedef)`
                    : `<b>${route.vehicle_name} - ${index + 1}. ${coord.name}</b>${isUserStation ? '<br><span style="color:' + color + '; font-weight:bold;">📦 Sizin kargonuz</span>' : ''}`;
                marker.bindPopup(popupText);

                marker.addTo(map);
                myRouteLayers.push(marker);
            });

        } else {
            drawSimpleRoute(path, route.user_stations, color, route.vehicle_name);
        }
    } catch (err) {
        console.warn("OSRM error, using fallback:", err);
        drawSimpleRoute(path, route.user_stations, color, route.vehicle_name);
    }
}

function drawSimpleRoute(path, userStations, color = '#2563eb', vehicleName = 'Araç') {
    const latlngs = path.map(p => [p.lat, p.lon]);
    const line = L.polyline(latlngs, { color: color, weight: 4, dashArray: '10, 10' }).addTo(map);
    line.bindPopup(`<b>${vehicleName}</b> (Kuş Uçuşu)`);
    myRouteLayers.push(line);

    path.forEach((coord, index) => {
        const isDepot = coord.name && coord.name.toLowerCase().includes('umuttepe');
        const isUserStation = isUserStationMatch(coord.name, userStations);

        const marker = L.circleMarker([coord.lat, coord.lon], {
            radius: isUserStation ? 10 : 7,
            fillColor: isDepot ? '#22c55e' : (isUserStation ? color : '#64748b'),
            color: 'white',
            weight: 2,
            fillOpacity: 1
        });

        marker.bindPopup(`<b>${coord.name}</b>${isUserStation ? '<br>📦 Sizin kargonuz' : ''}`);
        marker.addTo(map);
        myRouteLayers.push(marker);
    });

    if (myRouteLayers.length > 0) {
        const group = L.featureGroup(myRouteLayers);
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

function clearMyRoute(resetUI = true) {
    myRouteLayers.forEach(layer => {
        if (map.hasLayer(layer)) {
            map.removeLayer(layer);
        }
    });
    myRouteLayers = [];

    if (resetUI) {
        document.getElementById('my-route-result').style.display = 'none';
        document.getElementById('my-route-details').style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const routeDateInput = document.getElementById('route-view-date');
    if (routeDateInput) {
        routeDateInput.value = new Date().toISOString().split('T')[0];
    }
});

loadStations();
loadMyRequests();

