import os
import logging
from datetime import datetime, timezone, timedelta
import requests
from dotenv import load_dotenv

from services.cache_service import (
    get_cached,
    set_cached,
    make_city_cache_key,
    make_coords_cache_key
)

load_dotenv()

# Setup module logger
logger = logging.getLogger(__name__)

BASE_URL = "https://api.openweathermap.org/data/2.5"


class WeatherServiceError(Exception):
    """Custom exception raised for errors during Weather API interaction."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_api_key() -> str:
    """Retrieve and validate OpenWeatherMap API key from environment."""
    key = os.getenv("WEATHER_API_KEY", "").strip()
    if not key or key == "your_api_key_here":
        raise WeatherServiceError(
            "Weather API key is not configured on the server. Please set WEATHER_API_KEY in .env.",
            status_code=500
        )
    return key


def check_api_key() -> bool:
    """Check if a valid API key string exists in environment."""
    key = os.getenv("WEATHER_API_KEY", "").strip()
    return bool(key and key != "your_api_key_here")


def _format_time_with_offset(unix_timestamp: int, offset_seconds: int) -> str:
    """Format Unix timestamp into 12-hour AM/PM string applying local UTC offset."""
    tz = timezone(timedelta(seconds=offset_seconds))
    local_dt = datetime.fromtimestamp(unix_timestamp, tz=tz)
    return local_dt.strftime("%I:%M %p").lstrip("0")


def _format_day_name(unix_timestamp: int, offset_seconds: int) -> str:
    """Format Unix timestamp into abbreviated day name (e.g. MON, TUE)."""
    tz = timezone(timedelta(seconds=offset_seconds))
    local_dt = datetime.fromtimestamp(unix_timestamp, tz=tz)
    return local_dt.strftime("%a").upper()


def _format_date_short(unix_timestamp: int, offset_seconds: int) -> str:
    """Format Unix timestamp into short date (e.g. Oct 24)."""
    tz = timezone(timedelta(seconds=offset_seconds))
    local_dt = datetime.fromtimestamp(unix_timestamp, tz=tz)
    return local_dt.strftime("%b %d")


def _format_hour_label(unix_timestamp: int, offset_seconds: int, is_first: bool = False) -> str:
    """Format hour for hourly timeline (e.g., 'NOW', '2 PM')."""
    if is_first:
        return "NOW"
    tz = timezone(timedelta(seconds=offset_seconds))
    local_dt = datetime.fromtimestamp(unix_timestamp, tz=tz)
    return local_dt.strftime("%I %p").lstrip("0")


def _is_daytime(unix_now: int, sunrise: int, sunset: int) -> bool:
    """Determine if current time falls between sunrise and sunset."""
    return sunrise <= unix_now <= sunset


def parse_current_weather(data: dict) -> dict:
    """Normalize raw OpenWeatherMap current weather response into clean schema."""
    sys_data = data.get("sys", {})
    main_data = data.get("main", {})
    weather_list = data.get("weather", [{}])
    weather_info = weather_list[0] if weather_list else {}
    wind_data = data.get("wind", {})
    clouds_data = data.get("clouds", {})
    coord_data = data.get("coord", {})
    
    offset_seconds = data.get("timezone", 0)
    unix_now = data.get("dt", int(datetime.now(timezone.utc).timestamp()))
    sunrise = sys_data.get("sunrise", 0)
    sunset = sys_data.get("sunset", 0)
    
    wind_speed_ms = wind_data.get("speed", 0)
    wind_speed_kmh = round(wind_speed_ms * 3.6, 1)
    
    visibility_meters = data.get("visibility", 10000)
    visibility_km = round(visibility_meters / 1000, 1)

    return {
        "city": data.get("name", "Unknown"),
        "country": sys_data.get("country", ""),
        "coord": {
            "lat": coord_data.get("lat"),
            "lon": coord_data.get("lon")
        },
        "temp": round(main_data.get("temp", 0)),
        "feels_like": round(main_data.get("feels_like", 0)),
        "temp_min": round(main_data.get("temp_min", 0)),
        "temp_max": round(main_data.get("temp_max", 0)),
        "condition": weather_info.get("main", "Clear"),
        "description": weather_info.get("description", "").title(),
        "icon": weather_info.get("icon", "01d"),
        "humidity": main_data.get("humidity", 0),
        "wind_speed": wind_speed_kmh,
        "wind_deg": wind_data.get("deg", 0),
        "pressure": main_data.get("pressure", 1013),
        "visibility": visibility_km,
        "clouds": clouds_data.get("all", 0),
        "sunrise": _format_time_with_offset(sunrise, offset_seconds) if sunrise else "N/A",
        "sunset": _format_time_with_offset(sunset, offset_seconds) if sunset else "N/A",
        "local_time": _format_time_with_offset(unix_now, offset_seconds),
        "is_day": _is_daytime(unix_now, sunrise, sunset) if (sunrise and sunset) else True,
        "timezone_offset": offset_seconds
    }


def parse_forecast(data: dict) -> dict:
    """
    Parse 5-day / 3-hour OpenWeatherMap forecast payload.
    Produces hourly forecast timeline (next 24h) and 5-day aggregated forecast.
    """
    city_info = data.get("city", {})
    offset_seconds = city_info.get("timezone", 0)
    forecast_list = data.get("list", [])
    
    # 1. Parse Hourly Forecast (Next 8 slots = ~24 hours)
    hourly = []
    for idx, item in enumerate(forecast_list[:8]):
        main_item = item.get("main", {})
        weather_item = (item.get("weather") or [{}])[0]
        pop = round(item.get("pop", 0) * 100)  # probability of precipitation %
        dt = item.get("dt", 0)

        hourly.append({
            "time": _format_hour_label(dt, offset_seconds, is_first=(idx == 0)),
            "temp": round(main_item.get("temp", 0)),
            "feels_like": round(main_item.get("feels_like", 0)),
            "condition": weather_item.get("main", "Clear"),
            "description": weather_item.get("description", "").title(),
            "icon": weather_item.get("icon", "01d"),
            "pop": pop,
            "humidity": main_item.get("humidity", 0),
            "dt": dt
        })

    # 2. Parse Daily Forecast (Aggregate 3-hour entries by date string)
    daily_buckets = {}
    for item in forecast_list:
        dt = item.get("dt", 0)
        tz = timezone(timedelta(seconds=offset_seconds))
        local_date = datetime.fromtimestamp(dt, tz=tz).strftime("%Y-%m-%d")
        
        main_item = item.get("main", {})
        weather_item = (item.get("weather") or [{}])[0]
        temp = main_item.get("temp", 0)
        pop = round(item.get("pop", 0) * 100)
        humidity = main_item.get("humidity", 0)

        if local_date not in daily_buckets:
            daily_buckets[local_date] = {
                "day_name": _format_day_name(dt, offset_seconds),
                "date_short": _format_date_short(dt, offset_seconds),
                "temps": [temp],
                "humidities": [humidity],
                "pops": [pop],
                "conditions": [weather_item.get("main", "Clear")],
                "descriptions": [weather_item.get("description", "").title()],
                "icons": [weather_item.get("icon", "01d")],
                "dt": dt
            }
        else:
            daily_buckets[local_date]["temps"].append(temp)
            daily_buckets[local_date]["humidities"].append(humidity)
            daily_buckets[local_date]["pops"].append(pop)
            daily_buckets[local_date]["conditions"].append(weather_item.get("main", "Clear"))
            daily_buckets[local_date]["descriptions"].append(weather_item.get("description", "").title())
            daily_buckets[local_date]["icons"].append(weather_item.get("icon", "01d"))

    daily = []
    # Take up to 5 consecutive days
    for date_str, bucket in list(daily_buckets.items())[:5]:
        day_icons = [icon for icon in bucket["icons"] if icon.endswith("d")]
        selected_icon = day_icons[len(day_icons) // 2] if day_icons else bucket["icons"][len(bucket["icons"]) // 2]
        selected_condition = bucket["conditions"][len(bucket["conditions"]) // 2]
        selected_description = bucket["descriptions"][len(bucket["descriptions"]) // 2]

        daily.append({
            "date": date_str,
            "day": bucket["day_name"],
            "date_short": bucket["date_short"],
            "temp_max": round(max(bucket["temps"])),
            "temp_min": round(min(bucket["temps"])),
            "condition": selected_condition,
            "description": selected_description,
            "icon": selected_icon,
            "humidity": round(sum(bucket["humidities"]) / len(bucket["humidities"])),
            "pop": max(bucket["pops"])
        })

    return {
        "city": city_info.get("name", ""),
        "country": city_info.get("country", ""),
        "hourly": hourly,
        "daily": daily
    }


def _execute_api_request(url: str, params: dict) -> dict:
    """Helper to execute HTTP GET request to OpenWeatherMap API and handle response status."""
    try:
        response = requests.get(url, params=params, timeout=8)
    except requests.exceptions.Timeout:
        raise WeatherServiceError("Weather service connection timed out. Please try again.", status_code=504)
    except requests.exceptions.RequestException:
        raise WeatherServiceError("Unable to reach weather service. Check network connection.", status_code=503)

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        raise WeatherServiceError("City not found. Please check spelling and try again.", status_code=404)
    elif response.status_code == 401:
        raise WeatherServiceError("Invalid Weather API key provided.", status_code=401)
    elif response.status_code == 429:
        raise WeatherServiceError("Weather API rate limit exceeded. Please wait a moment.", status_code=429)
    else:
        raise WeatherServiceError(f"Weather API returned unexpected status code {response.status_code}.", status_code=response.status_code)


def get_current_weather(city: str) -> dict:
    """Fetch current weather data for a specified city name (with caching)."""
    if not city or not city.strip():
        raise WeatherServiceError("Please enter a city name.", status_code=400)

    cache_key = make_city_cache_key("weather", city)
    cached_data = get_cached(cache_key)
    if cached_data:
        logger.info(f"CACHE HIT for key: {cache_key}")
        return cached_data

    logger.info(f"CACHE MISS for key: {cache_key}")
    api_key = get_api_key()
    url = f"{BASE_URL}/weather"
    params = {
        "q": city.strip(),
        "appid": api_key,
        "units": "metric"
    }
    raw_data = _execute_api_request(url, params)
    parsed_data = parse_current_weather(raw_data)
    
    # Store successful response in cache
    set_cached(cache_key, parsed_data)
    return parsed_data


def get_forecast(city: str) -> dict:
    """Fetch 5-day / 3-hour forecast data for a specified city name (with caching)."""
    if not city or not city.strip():
        raise WeatherServiceError("Please enter a city name.", status_code=400)

    cache_key = make_city_cache_key("forecast", city)
    cached_data = get_cached(cache_key)
    if cached_data:
        logger.info(f"CACHE HIT for key: {cache_key}")
        return cached_data

    logger.info(f"CACHE MISS for key: {cache_key}")
    api_key = get_api_key()
    url = f"{BASE_URL}/forecast"
    params = {
        "q": city.strip(),
        "appid": api_key,
        "units": "metric"
    }
    raw_data = _execute_api_request(url, params)
    parsed_data = parse_forecast(raw_data)

    set_cached(cache_key, parsed_data)
    return parsed_data


def get_weather_by_coordinates(lat: float, lon: float) -> dict:
    """Fetch current weather using latitude and longitude coordinates (with caching)."""
    cache_key = make_coords_cache_key("weather", lat, lon)
    cached_data = get_cached(cache_key)
    if cached_data:
        logger.info(f"CACHE HIT for key: {cache_key}")
        return cached_data

    logger.info(f"CACHE MISS for key: {cache_key}")
    api_key = get_api_key()
    url = f"{BASE_URL}/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }
    raw_data = _execute_api_request(url, params)
    parsed_data = parse_current_weather(raw_data)

    set_cached(cache_key, parsed_data)
    return parsed_data


def get_forecast_by_coordinates(lat: float, lon: float) -> dict:
    """Fetch forecast data using latitude and longitude coordinates (with caching)."""
    cache_key = make_coords_cache_key("forecast", lat, lon)
    cached_data = get_cached(cache_key)
    if cached_data:
        logger.info(f"CACHE HIT for key: {cache_key}")
        return cached_data

    logger.info(f"CACHE MISS for key: {cache_key}")
    api_key = get_api_key()
    url = f"{BASE_URL}/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }
    raw_data = _execute_api_request(url, params)
    parsed_data = parse_forecast(raw_data)

    set_cached(cache_key, parsed_data)
    return parsed_data
