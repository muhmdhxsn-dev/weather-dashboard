import time
import pytest
from unittest.mock import patch, MagicMock
from app import app, limiter
from database.db import (
    init_db,
    add_search_history,
    get_search_history,
    clear_search_history,
    add_favorite,
    get_favorites,
    remove_favorite_by_city
)
from services.cache_service import clear_cache, get_cache_ttl
from services.weather_service import (
    parse_current_weather,
    parse_forecast,
    get_current_weather,
    get_weather_by_coordinates,
    WeatherServiceError
)

# Mock OpenWeatherMap payloads
MOCK_CURRENT_WEATHER_RAW = {
    "coord": {"lon": 74.3587, "lat": 31.5204},
    "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
    "main": {
        "temp": 32.4,
        "feels_like": 35.1,
        "temp_min": 31.0,
        "temp_max": 33.0,
        "pressure": 1012,
        "humidity": 48
    },
    "visibility": 10000,
    "wind": {"speed": 3.33, "deg": 140},
    "clouds": {"all": 20},
    "dt": 1690000000,
    "sys": {
        "type": 1,
        "id": 1234,
        "country": "PK",
        "sunrise": 1689984000,
        "sunset": 1690032000
    },
    "timezone": 18000,
    "id": 1172451,
    "name": "Lahore"
}

MOCK_FORECAST_RAW = {
    "cod": "200",
    "message": 0,
    "cnt": 40,
    "list": [
        {
            "dt": 1690000000 + i * 10800,
            "main": {
                "temp": 30.0 + (i % 3),
                "feels_like": 31.0,
                "temp_min": 28.0,
                "temp_max": 34.0,
                "pressure": 1012,
                "humidity": 50
            },
            "weather": [{"main": "Clear", "description": "clear sky", "icon": "01d"}],
            "clouds": {"all": 10},
            "wind": {"speed": 2.5, "deg": 120},
            "visibility": 10000,
            "pop": 0.1
        } for i in range(40)
    ],
    "city": {
        "id": 1172451,
        "name": "Lahore",
        "coord": {"lat": 31.5204, "lon": 74.3587},
        "country": "PK",
        "timezone": 18000
    }
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Fixture providing a test client configured with an isolated temporary SQLite database."""
    test_db = tmp_path / "test_weather.db"
    monkeypatch.setattr("database.db.DB_PATH", test_db)
    monkeypatch.setattr("database.db.DB_DIR", tmp_path)

    app.config['TESTING'] = True
    limiter.reset()
    clear_cache()
    with app.test_client() as client:
        with app.app_context():
            init_db()
            clear_search_history()
        yield client


def test_homepage_loads(client):
    """Test that homepage returns 200 OK."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Nimbus' in response.data


def test_health_check_endpoint(client):
    """Test health check JSON endpoint."""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'


def test_parse_current_weather():
    """Test current weather normalization logic."""
    parsed = parse_current_weather(MOCK_CURRENT_WEATHER_RAW)
    assert parsed['city'] == 'Lahore'
    assert parsed['country'] == 'PK'
    assert parsed['temp'] == 32
    assert parsed['feels_like'] == 35
    assert parsed['humidity'] == 48


def test_parse_forecast():
    """Test forecast normalization logic for hourly and daily arrays."""
    parsed = parse_forecast(MOCK_FORECAST_RAW)
    assert parsed['city'] == 'Lahore'
    assert len(parsed['hourly']) == 8
    assert len(parsed['daily']) <= 5


@patch('services.weather_service.requests.get')
@patch('services.weather_service.os.getenv')
def test_cache_miss_and_hit(mock_getenv, mock_requests_get, client):
    """Test cache miss (first fetch calls API) and cache hit (subsequent fetch uses cache)."""
    mock_getenv.return_value = "valid_test_key"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_CURRENT_WEATHER_RAW
    mock_requests_get.return_value = mock_response

    # First Call -> Cache Miss -> API called once
    res1 = get_current_weather("Lahore")
    assert res1['city'] == "Lahore"
    assert mock_requests_get.call_count == 1

    # Second Call -> Cache Hit -> API not called again
    res2 = get_current_weather("Lahore")
    assert res2['city'] == "Lahore"
    assert mock_requests_get.call_count == 1


@patch('services.weather_service.requests.get')
@patch('services.weather_service.os.getenv')
def test_case_normalization_caching(mock_getenv, mock_requests_get, client):
    """Test that 'Lahore', 'lahore', and 'LAHORE' resolve to the same cache entry."""
    mock_getenv.return_value = "valid_test_key"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_CURRENT_WEATHER_RAW
    mock_requests_get.return_value = mock_response

    get_current_weather("Lahore")
    get_current_weather("lahore")
    get_current_weather("LAHORE")

    assert mock_requests_get.call_count == 1


@patch('services.weather_service.requests.get')
@patch('services.weather_service.os.getenv')
def test_different_cities_cache_isolation(mock_getenv, mock_requests_get, client):
    """Test that different cities do not share cache entries."""
    mock_getenv.return_value = "valid_test_key"
    mock_response1 = MagicMock()
    mock_response1.status_code = 200
    mock_response1.json.return_value = MOCK_CURRENT_WEATHER_RAW

    mock_response2 = MagicMock()
    mock_response2.status_code = 200
    mock_response2.json.return_value = {**MOCK_CURRENT_WEATHER_RAW, "name": "Karachi"}

    mock_requests_get.side_effect = [mock_response1, mock_response2]

    res_lahore = get_current_weather("Lahore")
    res_karachi = get_current_weather("Karachi")

    assert res_lahore['city'] == "Lahore"
    assert res_karachi['city'] == "Karachi"
    assert mock_requests_get.call_count == 2


@patch('services.weather_service.requests.get')
@patch('services.weather_service.os.getenv')
def test_coordinate_caching_normalization(mock_getenv, mock_requests_get, client):
    """Test coordinate rounding and normalization caching."""
    mock_getenv.return_value = "valid_test_key"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_CURRENT_WEATHER_RAW
    mock_requests_get.return_value = mock_response

    get_weather_by_coordinates(31.520411, 74.358711)
    get_weather_by_coordinates(31.520444, 74.358744)

    assert mock_requests_get.call_count == 1


@patch('services.cache_service.time.time')
@patch('services.weather_service.requests.get')
@patch('services.weather_service.os.getenv')
def test_cache_expiration(mock_getenv, mock_requests_get, mock_time, client):
    """Test cache expiration after TTL."""
    mock_getenv.return_value = "valid_test_key"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_CURRENT_WEATHER_RAW
    mock_requests_get.return_value = mock_response

    mock_time.return_value = 1000.0
    get_current_weather("Lahore")
    assert mock_requests_get.call_count == 1

    mock_time.return_value = 1000.0 + 601.0
    get_current_weather("Lahore")
    assert mock_requests_get.call_count == 2


def test_rate_limiting(client):
    """Test that exceeding the rate limit returns HTTP 429."""
    limiter.enabled = True

    for _ in range(60):
        res = client.get('/api/weather?city=Lahore')
        assert res.status_code in [200, 400, 500]

    res_exceeded = client.get('/api/weather?city=Lahore')
    assert res_exceeded.status_code == 429
    data = res_exceeded.get_json()
    assert data['success'] is False
    assert "Too many requests" in data['error']


def test_search_history_db_operations(client):
    """Test search history CRUD operations."""
    add_search_history("Islamabad", "PK")
    add_search_history("Karachi", "PK")
    
    response = client.get('/api/history')
    assert response.status_code == 200
    history = response.get_json()
    assert len(history) == 2
    assert history[0]['city'] == 'Karachi'

    del_response = client.delete('/api/history')
    assert del_response.status_code == 200
    assert len(get_search_history()) == 0


def test_favorites_api(client):
    """Test favorite cities POST, GET, DELETE endpoints."""
    post_res = client.post('/api/favorites', json={'city': 'Tokyo', 'country': 'JP'})
    assert post_res.status_code == 201

    get_res = client.get('/api/favorites')
    assert get_res.status_code == 200
    favs = get_res.get_json()
    assert len(favs) >= 1
    assert favs[0]['city'] == 'Tokyo'

    del_res = client.delete('/api/favorites?city=Tokyo')
    assert del_res.status_code == 200
    assert len(get_favorites()) == 0
