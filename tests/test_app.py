import pytest
from unittest.mock import patch, MagicMock
from app import app
from database.db import (
    init_db,
    add_search_history,
    get_search_history,
    clear_search_history,
    add_favorite,
    get_favorites,
    remove_favorite_by_city
)
from services.weather_service import (
    parse_current_weather,
    parse_forecast,
    get_current_weather,
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
def client():
    app.config['TESTING'] = True
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
def test_api_current_weather_route_success(mock_getenv, mock_requests_get, client):
    """Test GET /api/weather endpoint success response."""
    mock_getenv.return_value = "valid_test_key"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_CURRENT_WEATHER_RAW
    mock_requests_get.return_value = mock_response

    response = client.get('/api/weather?city=Lahore')
    assert response.status_code == 200
    data = response.get_json()
    assert data['city'] == 'Lahore'
    assert data['temp'] == 32
    assert 'is_favorite' in data


def test_api_current_weather_empty_city(client):
    """Test GET /api/weather with missing city query parameter."""
    response = client.get('/api/weather?city=')
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


@patch('services.weather_service.requests.get')
@patch('services.weather_service.os.getenv')
def test_api_weather_location_route(mock_getenv, mock_requests_get, client):
    """Test GET /api/weather/location endpoint with coordinates."""
    mock_getenv.return_value = "valid_test_key"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_CURRENT_WEATHER_RAW
    mock_requests_get.return_value = mock_response

    response = client.get('/api/weather/location?lat=31.5204&lon=74.3587')
    assert response.status_code == 200
    data = response.get_json()
    assert data['city'] == 'Lahore'


def test_api_weather_location_invalid_coords(client):
    """Test GET /api/weather/location with invalid coordinate parameters."""
    response = client.get('/api/weather/location?lat=abc&lon=def')
    assert response.status_code == 400
    data = response.get_json()
    assert 'Invalid latitude or longitude' in data['error']


def test_search_history_db_operations(client):
    """Test search history CRUD operations."""
    add_search_history("Islamabad", "PK")
    add_search_history("Karachi", "PK")
    
    response = client.get('/api/history')
    assert response.status_code == 200
    history = response.get_json()
    assert len(history) == 2
    assert history[0]['city'] == 'Karachi'

    # Clear history
    del_response = client.delete('/api/history')
    assert del_response.status_code == 200
    assert len(get_search_history()) == 0


def test_favorites_api(client):
    """Test favorite cities POST, GET, DELETE endpoints."""
    # Add favorite
    post_res = client.post('/api/favorites', json={'city': 'Tokyo', 'country': 'JP'})
    assert post_res.status_code == 201

    # Get favorites
    get_res = client.get('/api/favorites')
    assert get_res.status_code == 200
    favs = get_res.get_json()
    assert len(favs) >= 1
    assert favs[0]['city'] == 'Tokyo'

    # Delete favorite
    del_res = client.delete('/api/favorites?city=Tokyo')
    assert del_res.status_code == 200
    assert len(get_favorites()) == 0
