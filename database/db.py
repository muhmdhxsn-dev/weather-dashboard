import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Detect Vercel serverless environment and set appropriate database path
if os.getenv("VERCEL"):
    DB_DIR = Path("/tmp") / "database"
else:
    DB_DIR = BASE_DIR / "database"

DB_PATH = DB_DIR / "weather.db"


def get_db_connection():
    """Establish and return a connection to the SQLite database."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables for search history and favorite cities."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Search history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            country TEXT NOT NULL,
            searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Favorite cities table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorite_cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL UNIQUE,
            country TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# Search History Operations
def add_search_history(city: str, country: str):
    """Add a search query to search history. Removes duplicate recent entries."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM search_history WHERE LOWER(city) = LOWER(?)", (city.strip(),))
        cursor.execute(
            "INSERT INTO search_history (city, country) VALUES (?, ?)",
            (city.strip(), country.strip())
        )
        cursor.execute("""
            DELETE FROM search_history 
            WHERE id NOT IN (
                SELECT id FROM search_history ORDER BY id DESC LIMIT 20
            )
        """)
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"Database write error (search_history): {exc}")


def get_search_history(limit: int = 8) -> list:
    """Retrieve recent search history items ordered by search timestamp."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, city, country, searched_at FROM search_history ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as exc:
        print(f"Database read error (search_history): {exc}")
        return []


def clear_search_history():
    """Clear all entries from search history."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM search_history")
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"Database write error (clear_search_history): {exc}")


# Favorite Cities Operations
def add_favorite(city: str, country: str) -> dict:
    """Add a city to favorites list using parameterized query."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO favorite_cities (city, country) VALUES (?, ?)",
            (city.strip(), country.strip())
        )
        conn.commit()
        fav_id = cursor.lastrowid
        conn.close()
        return {"id": fav_id, "city": city.strip(), "country": country.strip()}
    except sqlite3.IntegrityError:
        fav = get_favorite_by_city(city)
        return fav if fav else {"city": city.strip(), "country": country.strip()}
    except Exception as exc:
        print(f"Database write error (add_favorite): {exc}")
        return {"city": city.strip(), "country": country.strip()}


def remove_favorite_by_id(fav_id: int) -> bool:
    """Remove a favorite city by database ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM favorite_cities WHERE id = ?", (fav_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    except Exception as exc:
        print(f"Database write error (remove_favorite_by_id): {exc}")
        return False


def remove_favorite_by_city(city: str) -> bool:
    """Remove a favorite city by city name."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM favorite_cities WHERE LOWER(city) = LOWER(?)", (city.strip(),))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    except Exception as exc:
        print(f"Database write error (remove_favorite_by_city): {exc}")
        return False


def get_favorites() -> list:
    """Retrieve all favorite cities."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, city, country, created_at FROM favorite_cities ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as exc:
        print(f"Database read error (get_favorites): {exc}")
        return []


def get_favorite_by_city(city: str) -> dict | None:
    """Check if a city is in favorites."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, city, country, created_at FROM favorite_cities WHERE LOWER(city) = LOWER(?)", (city.strip(),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as exc:
        print(f"Database read error (get_favorite_by_city): {exc}")
        return None
