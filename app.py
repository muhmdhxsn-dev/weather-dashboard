import os
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv

from database.db import (
    init_db,
    add_search_history,
    get_search_history,
    clear_search_history,
    add_favorite,
    remove_favorite_by_id,
    remove_favorite_by_city,
    get_favorites,
    get_favorite_by_city
)
from services.weather_service import (
    get_current_weather,
    get_forecast,
    get_weather_by_coordinates,
    get_forecast_by_coordinates,
    check_api_key,
    WeatherServiceError
)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Secret Key safely for local development and production
flask_env = os.getenv("FLASK_ENV", "development")
secret_key = os.getenv("SECRET_KEY")

if not secret_key:
    if flask_env == "production":
        raise ValueError("SECRET_KEY environment variable is required in production mode.")
    secret_key = "dev-secret-key-change-in-production"

app.secret_key = secret_key

# Ensure database tables exist on startup
with app.app_context():
    init_db()


@app.route("/")
def index():
    """Render the main Weather Dashboard web application."""
    return render_template("index.html")


@app.route("/api/health")
def health_check():
    """Health check endpoint to verify server status and API key configuration."""
    api_key_configured = check_api_key()
    return jsonify({
        "status": "healthy",
        "api_key_configured": api_key_configured,
        "message": "Nimbus Weather Dashboard Backend Operational"
    }), 200


@app.route("/api/weather")
def api_current_weather():
    """Endpoint: GET /api/weather?city=Lahore"""
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({"error": "Please enter a city name."}), 400

    try:
        data = get_current_weather(city)
        # Log to search history on successful query
        add_search_history(data["city"], data["country"])
        # Check if city is favorited
        is_fav = get_favorite_by_city(data["city"]) is not None
        data["is_favorite"] = is_fav
        return jsonify(data), 200
    except WeatherServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    except Exception:
        return jsonify({"error": "Weather service is temporarily unavailable. Please try again later."}), 500


@app.route("/api/forecast")
def api_forecast():
    """Endpoint: GET /api/forecast?city=Lahore"""
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({"error": "Please enter a city name."}), 400

    try:
        data = get_forecast(city)
        return jsonify(data), 200
    except WeatherServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    except Exception:
        return jsonify({"error": "Weather service is temporarily unavailable. Please try again later."}), 500


@app.route("/api/weather/location")
def api_weather_location():
    """Endpoint: GET /api/weather/location?lat=31.5204&lon=74.3587"""
    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon")

    if lat_raw is None or lon_raw is None:
        return jsonify({"error": "Missing latitude or longitude parameters."}), 400

    try:
        lat = float(lat_raw)
        lon = float(lon_raw)
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return jsonify({"error": "Latitude or longitude values are out of range."}), 400
    except ValueError:
        return jsonify({"error": "Invalid latitude or longitude format."}), 400

    try:
        data = get_weather_by_coordinates(lat, lon)
        add_search_history(data["city"], data["country"])
        is_fav = get_favorite_by_city(data["city"]) is not None
        data["is_favorite"] = is_fav
        return jsonify(data), 200
    except WeatherServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    except Exception:
        return jsonify({"error": "Weather service is temporarily unavailable. Please try again later."}), 500


@app.route("/api/forecast/location")
def api_forecast_location():
    """Endpoint: GET /api/forecast/location?lat=31.5204&lon=74.3587"""
    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon")

    if lat_raw is None or lon_raw is None:
        return jsonify({"error": "Missing latitude or longitude parameters."}), 400

    try:
        lat = float(lat_raw)
        lon = float(lon_raw)
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return jsonify({"error": "Latitude or longitude values are out of range."}), 400
    except ValueError:
        return jsonify({"error": "Invalid latitude or longitude format."}), 400

    try:
        data = get_forecast_by_coordinates(lat, lon)
        return jsonify(data), 200
    except WeatherServiceError as exc:
        return jsonify({"error": exc.message}), exc.status_code
    except Exception:
        return jsonify({"error": "Weather service is temporarily unavailable. Please try again later."}), 500


@app.route("/api/history", methods=["GET", "DELETE"])
def api_search_history():
    """Endpoint: GET /api/history or DELETE /api/history"""
    if request.method == "DELETE":
        clear_search_history()
        return jsonify({"message": "Search history cleared."}), 200

    history = get_search_history()
    return jsonify(history), 200


@app.route("/api/favorites", methods=["GET", "POST", "DELETE"])
def api_favorites():
    """Endpoint for managing favorite cities."""
    if request.method == "GET":
        favorites = get_favorites()
        return jsonify(favorites), 200

    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        city = payload.get("city", "").strip()
        country = payload.get("country", "").strip()

        if not city:
            return jsonify({"error": "City name is required."}), 400

        result = add_favorite(city, country)
        return jsonify(result), 201

    if request.method == "DELETE":
        city = request.args.get("city", "").strip()
        fav_id = request.args.get("id")

        if fav_id and fav_id.isdigit():
            success = remove_favorite_by_id(int(fav_id))
        elif city:
            success = remove_favorite_by_city(city)
        else:
            return jsonify({"error": "Must specify favorite ID or city name."}), 400

        if success:
            return jsonify({"message": "Favorite removed successfully."}), 200
        else:
            return jsonify({"error": "Favorite city not found."}), 404


@app.route("/api/favorites/<int:fav_id>", methods=["DELETE"])
def api_delete_favorite_by_id(fav_id):
    """Endpoint: DELETE /api/favorites/<id>"""
    success = remove_favorite_by_id(fav_id)
    if success:
        return jsonify({"message": "Favorite removed successfully."}), 200
    return jsonify({"error": "Favorite city not found."}), 404


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    app.run(host=host, port=port, debug=debug)
