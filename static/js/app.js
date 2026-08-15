/**
 * Nimbus Weather Dashboard — Client JavaScript Architecture
 */

// Global state
let tempChartInstance = null;
let currentCityData = null;

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initEventListeners();
    
    // Initial data load: fetch saved favorites, search history, and initial default city (Lahore)
    loadFavorites();
    loadSearchHistory();
    searchWeather('Lahore');
});

/**
 * Theme Manager (Light / Dark mode persistence)
 */
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
            
            // Re-render chart with theme-aware colors if active
            if (currentCityData && currentCityData.hourly) {
                updateTemperatureChart(currentCityData.hourly);
            }
        });
    }
}

function updateThemeIcon(theme) {
    const icon = document.querySelector('#theme-toggle i');
    if (!icon) return;
    icon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
}

/**
 * Event Listeners Initialization
 */
function initEventListeners() {
    // City Search Form
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const cityInput = document.getElementById('city-input');
            const query = cityInput ? cityInput.value.strip ? cityInput.value.strip() : cityInput.value.trim() : '';
            if (query) {
                searchWeather(query);
            } else {
                showNotification('Please enter a city name.', 'warning');
            }
        });
    }

    // Geolocation Button
    const locationBtn = document.getElementById('location-btn');
    if (locationBtn) {
        locationBtn.addEventListener('click', getCurrentLocation);
    }

    // Favorite Heart Toggle Button
    const favToggleBtn = document.getElementById('fav-toggle-btn');
    if (favToggleBtn) {
        favToggleBtn.addEventListener('click', toggleFavorite);
    }

    // Clear History Button
    const clearHistoryBtn = document.getElementById('clear-history-btn');
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', clearSearchHistory);
    }

    // Notification Banner Close Button
    const notifCloseBtn = document.getElementById('notification-close');
    if (notifCloseBtn) {
        notifCloseBtn.addEventListener('click', hideNotification);
    }
}

/**
 * Primary Search Handler
 */
async function searchWeather(cityName) {
    if (!cityName) return;

    hideNotification();
    showLoading(true);

    try {
        // Parallel requests for current weather & forecast
        const [weatherRes, forecastRes] = await Promise.all([
            fetch(`/api/weather?city=${encodeURIComponent(cityName)}`),
            fetch(`/api/forecast?city=${encodeURIComponent(cityName)}`)
        ]);

        const weatherData = await weatherRes.json();
        const forecastData = await forecastRes.json();

        if (!weatherRes.ok) {
            throw new Error(weatherData.error || 'City not found.');
        }

        if (!forecastRes.ok) {
            throw new Error(forecastData.error || 'Forecast unavailable.');
        }

        // Store active data state
        currentCityData = {
            current: weatherData,
            hourly: forecastData.hourly,
            daily: forecastData.daily
        };

        // Render dashboard UI components
        displayCurrentWeather(weatherData);
        displayHourlyForecast(forecastData.hourly);
        displayDailyForecast(forecastData.daily);
        updateTemperatureChart(forecastData.hourly);
        setWeatherBackgroundCondition(weatherData.condition, weatherData.is_day);

        // Refresh search history sidebar list
        loadSearchHistory();

    } catch (err) {
        showNotification(err.message || 'Unable to fetch weather data.', 'error');
    } finally {
        showLoading(false);
    }
}

/**
 * Geolocation Weather Handler
 */
function getCurrentLocation() {
    if (!navigator.geolocation) {
        showNotification('Geolocation is not supported by your browser. Please search for a city manually.', 'warning');
        return;
    }

    showLoading(true);
    hideNotification();

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;

            try {
                const [weatherRes, forecastRes] = await Promise.all([
                    fetch(`/api/weather/location?lat=${lat}&lon=${lon}`),
                    fetch(`/api/forecast/location?lat=${lat}&lon=${lon}`)
                ]);

                const weatherData = await weatherRes.json();
                const forecastData = await forecastRes.json();

                if (!weatherRes.ok) throw new Error(weatherData.error || 'Location weather failed.');
                if (!forecastRes.ok) throw new Error(forecastData.error || 'Location forecast failed.');

                currentCityData = {
                    current: weatherData,
                    hourly: forecastData.hourly,
                    daily: forecastData.daily
                };

                displayCurrentWeather(weatherData);
                displayHourlyForecast(forecastData.hourly);
                displayDailyForecast(forecastData.daily);
                updateTemperatureChart(forecastData.hourly);
                setWeatherBackgroundCondition(weatherData.condition, weatherData.is_day);
                
                // Update search input field with detected city name
                const cityInput = document.getElementById('city-input');
                if (cityInput) cityInput.value = weatherData.city;

                loadSearchHistory();

            } catch (err) {
                showNotification(err.message || 'Failed to fetch weather for your location.', 'error');
            } finally {
                showLoading(false);
            }
        },
        (error) => {
            showLoading(false);
            let message = 'Unable to access your location. Please search for a city instead.';
            if (error.code === error.PERMISSION_DENIED) {
                message = 'Location access permission denied. Please search for a city manually.';
            }
            showNotification(message, 'warning');
        },
        { timeout: 10000, enableHighAccuracy: true }
    );
}

/**
 * Render Current Weather Card & Details
 */
function displayCurrentWeather(data) {
    document.getElementById('cw-city').textContent = data.city;
    document.getElementById('cw-country').textContent = data.country || '';
    document.getElementById('cw-time').textContent = `Local Time: ${data.local_time}`;

    const iconImg = document.getElementById('cw-icon');
    if (iconImg) {
        iconImg.src = `https://openweathermap.org/img/wn/${data.icon}@4x.png`;
        iconImg.alt = data.description;
    }

    document.getElementById('cw-temp').textContent = data.temp;
    document.getElementById('cw-condition').textContent = data.condition;
    document.getElementById('cw-description').textContent = data.description;
    document.getElementById('cw-feels').textContent = `${data.feels_like}°C`;
    document.getElementById('cw-min').textContent = `${data.temp_min}°C`;
    document.getElementById('cw-max').textContent = `${data.temp_max}°C`;

    // Footer stats
    document.getElementById('cw-stat-humidity').textContent = `${data.humidity}%`;
    document.getElementById('cw-stat-wind').textContent = `${data.wind_speed} km/h`;
    document.getElementById('cw-stat-visibility').textContent = `${data.visibility} km`;

    // Grid stat cards
    document.getElementById('card-stat-humidity').textContent = `${data.humidity}%`;
    document.getElementById('card-stat-wind').textContent = `${data.wind_speed} km/h`;
    document.getElementById('card-stat-wind-deg').textContent = `Direction: ${data.wind_deg}°`;
    document.getElementById('card-stat-pressure').textContent = `${data.pressure} hPa`;
    document.getElementById('card-stat-visibility').textContent = `${data.visibility} km`;
    document.getElementById('card-stat-clouds').textContent = `${data.clouds}%`;
    document.getElementById('card-stat-sunrise').textContent = data.sunrise;
    document.getElementById('card-stat-sunset').textContent = data.sunset;

    // Update favorite heart icon state
    updateFavButtonUI(data.is_favorite);
}

/**
 * Render Hourly Forecast Strip
 */
function displayHourlyForecast(hourlyList) {
    const container = document.getElementById('hourly-forecast-container');
    if (!container) return;

    if (!hourlyList || hourlyList.length === 0) {
        container.innerHTML = '<p class="empty-state">No hourly data available.</p>';
        return;
    }

    container.innerHTML = hourlyList.map(item => `
        <div class="hour-card">
            <span class="hour-time">${item.time}</span>
            <img src="https://openweathermap.org/img/wn/${item.icon}@2x.png" alt="${item.description}" width="48" height="48">
            <span class="hour-temp">${item.temp}°C</span>
            <span class="hour-pop"><i class="fa-solid fa-droplet"></i> ${item.pop}%</span>
        </div>
    `).join('');
}

/**
 * Render 5-Day Daily Forecast Cards
 */
function displayDailyForecast(dailyList) {
    const container = document.getElementById('daily-forecast-container');
    if (!container) return;

    if (!dailyList || dailyList.length === 0) {
        container.innerHTML = '<p class="empty-state">No daily forecast available.</p>';
        return;
    }

    container.innerHTML = dailyList.map(day => `
        <div class="daily-card">
            <span class="day-name">${day.day}</span>
            <span class="day-date">${day.date_short}</span>
            <img src="https://openweathermap.org/img/wn/${day.icon}@2x.png" alt="${day.description}" width="54" height="54">
            <span class="day-condition">${day.description}</span>
            <div class="day-temp-group">
                <span class="temp-max">${day.temp_max}°</span>
                <span class="temp-min">${day.temp_min}°</span>
            </div>
            <span class="hour-pop"><i class="fa-solid fa-droplet"></i> ${day.pop}%</span>
        </div>
    `).join('');
}

/**
 * Chart.js Hourly Temperature Trend Visualization
 */
function updateTemperatureChart(hourlyList) {
    const canvas = document.getElementById('tempChart');
    if (!canvas) return;

    const labels = hourlyList.map(h => h.time);
    const temps = hourlyList.map(h => h.temp);

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const lineColor = isDark ? '#38bdf8' : '#2563eb';
    const fillColor = isDark ? 'rgba(56, 189, 248, 0.15)' : 'rgba(37, 99, 235, 0.1)';
    const textColor = isDark ? '#94a3b8' : '#64748b';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';

    // Safely destroy existing chart instance to prevent canvas overlay bugs
    if (tempChartInstance) {
        tempChartInstance.destroy();
    }

    const ctx = canvas.getContext('2d');
    tempChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Temperature (°C)',
                data: temps,
                borderColor: lineColor,
                backgroundColor: fillColor,
                borderWidth: 3,
                tension: 0.4,
                fill: true,
                pointRadius: 4,
                pointHoverRadius: 7,
                pointBackgroundColor: lineColor,
                pointBorderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: isDark ? '#1e293b' : '#ffffff',
                    titleColor: isDark ? '#f8fafc' : '#0f172a',
                    bodyColor: isDark ? '#f8fafc' : '#0f172a',
                    borderColor: isDark ? '#334155' : '#e2e8f0',
                    borderWidth: 1,
                    padding: 10,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return ` Temp: ${context.parsed.y}°C`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: gridColor },
                    ticks: { color: textColor, font: { family: 'Plus Jakarta Sans', weight: '600' } }
                },
                y: {
                    grid: { color: gridColor },
                    ticks: {
                        color: textColor,
                        font: { family: 'Plus Jakarta Sans', weight: '600' },
                        callback: function(val) { return val + '°'; }
                    }
                }
            }
        }
    });
}

/**
 * Search History & Favorites Handlers
 */
async function loadSearchHistory() {
    try {
        const res = await fetch('/api/history');
        if (!res.ok) return;
        const history = await res.json();
        renderSearchHistory(history);
    } catch (e) {
        console.error('Failed to load history:', e);
    }
}

function renderSearchHistory(history) {
    const container = document.getElementById('history-list');
    if (!container) return;

    if (!history || history.length === 0) {
        container.innerHTML = '<li class="empty-state">No recent searches.</li>';
        return;
    }

    container.innerHTML = history.map(item => `
        <li class="sidebar-item" onclick="searchWeather('${item.city}')">
            <span class="city-name">${item.city}</span>
            <span class="country-code">${item.country}</span>
        </li>
    `).join('');
}

async function clearSearchHistory() {
    try {
        await fetch('/api/history', { method: 'DELETE' });
        loadSearchHistory();
    } catch (e) {
        console.error('Failed to clear history:', e);
    }
}

async function loadFavorites() {
    try {
        const res = await fetch('/api/favorites');
        if (!res.ok) return;
        const favorites = await res.json();
        renderFavorites(favorites);
    } catch (e) {
        console.error('Failed to load favorites:', e);
    }
}

function renderFavorites(favorites) {
    const container = document.getElementById('favorites-list');
    if (!container) return;

    if (!favorites || favorites.length === 0) {
        container.innerHTML = '<li class="empty-state">No favorite cities saved yet.</li>';
        return;
    }

    container.innerHTML = favorites.map(fav => `
        <li class="sidebar-item">
            <span class="city-name" onclick="searchWeather('${fav.city}')">${fav.city} (${fav.country})</span>
            <button class="btn-text text-danger" onclick="removeFavorite('${fav.city}', event)" title="Remove favorite">
                <i class="fa-solid fa-xmark"></i>
            </button>
        </li>
    `).join('');
}

async function toggleFavorite() {
    if (!currentCityData || !currentCityData.current) return;

    const city = currentCityData.current.city;
    const country = currentCityData.current.country;
    const isFav = currentCityData.current.is_favorite;

    try {
        if (isFav) {
            // Remove favorite
            const res = await fetch(`/api/favorites?city=${encodeURIComponent(city)}`, { method: 'DELETE' });
            if (res.ok) {
                currentCityData.current.is_favorite = false;
                updateFavButtonUI(false);
                loadFavorites();
                showNotification(`Removed ${city} from favorites.`, 'info');
            }
        } else {
            // Add favorite
            const res = await fetch('/api/favorites', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ city, country })
            });
            if (res.ok) {
                currentCityData.current.is_favorite = true;
                updateFavButtonUI(true);
                loadFavorites();
                showNotification(`Saved ${city} to favorites!`, 'success');
            }
        }
    } catch (e) {
        showNotification('Failed to update favorites.', 'error');
    }
}

async function removeFavorite(city, event) {
    if (event) event.stopPropagation();
    try {
        const res = await fetch(`/api/favorites?city=${encodeURIComponent(city)}`, { method: 'DELETE' });
        if (res.ok) {
            if (currentCityData && currentCityData.current && currentCityData.current.city.toLowerCase() === city.toLowerCase()) {
                currentCityData.current.is_favorite = false;
                updateFavButtonUI(false);
            }
            loadFavorites();
        }
    } catch (e) {
        console.error('Failed to remove favorite:', e);
    }
}

function updateFavButtonUI(isFav) {
    const btn = document.getElementById('fav-toggle-btn');
    if (!btn) return;

    if (isFav) {
        btn.classList.add('active');
        btn.innerHTML = '<i class="fa-solid fa-heart"></i>';
        btn.title = 'Remove from favorites';
    } else {
        btn.classList.remove('active');
        btn.innerHTML = '<i class="fa-regular fa-heart"></i>';
        btn.title = 'Add to favorites';
    }
}

/**
 * Dynamic Weather Background Controller
 */
function setWeatherBackgroundCondition(condition, isDay) {
    const body = document.body;
    body.className = ''; // Reset weather background classes

    const condLower = (condition || '').toLowerCase();
    
    if (condLower.includes('clear')) {
        body.classList.add(isDay ? 'weather-clear-day' : 'weather-clear-night');
    } else if (condLower.includes('cloud')) {
        body.classList.add('weather-clouds');
    } else if (condLower.includes('rain') || condLower.includes('drizzle')) {
        body.classList.add('weather-rain');
    } else if (condLower.includes('thunderstorm')) {
        body.classList.add('weather-thunderstorm');
    } else if (condLower.includes('snow')) {
        body.classList.add('weather-snow');
    }
}

/**
 * UI State Utilities: Loading & Notifications
 */
function showLoading(isLoading) {
    const searchBtn = document.getElementById('search-btn');
    const skeleton = document.getElementById('skeleton-loader');
    const dashboardView = document.getElementById('dashboard-view');

    if (searchBtn) {
        searchBtn.disabled = isLoading;
        searchBtn.innerHTML = isLoading ? '<i class="fa-solid fa-spinner fa-spin"></i>' : '<span>Search</span>';
    }

    if (skeleton && dashboardView) {
        if (isLoading) {
            skeleton.classList.remove('hidden');
            dashboardView.style.opacity = '0.4';
        } else {
            skeleton.classList.add('hidden');
            dashboardView.style.opacity = '1';
        }
    }
}

function showNotification(message, type = 'error') {
    const banner = document.getElementById('notification-banner');
    const msgSpan = document.getElementById('notification-message');
    if (!banner || !msgSpan) return;

    msgSpan.textContent = message;
    banner.classList.remove('hidden');
}

function hideNotification() {
    const banner = document.getElementById('notification-banner');
    if (banner) banner.classList.add('hidden');
}
