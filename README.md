# Nimbus — Production-Quality Weather Dashboard

A modern, SaaS-style Weather Dashboard built with **Python 3.12+**, **Flask**, **SQLite**, **HTML5/CSS3/Vanilla JS**, and **Chart.js**.

---

## 🌟 Features

* **Live Weather Data**: Real-time temperature, condition, feels-like, wind speed/direction, humidity, visibility, pressure, and cloud coverage powered by OpenWeatherMap API.
* **Hourly & 5-Day Forecast**: Clean visual cards for upcoming hourly breakdown and 5-day weather trends.
* **Interactive Temperature Chart**: Dynamic hourly temperature visualizations using Chart.js.
* **Search History & Favorites**: Persisted search log and quick-access favorite cities powered by SQLite.
* **Browser Geolocation**: Instant weather lookup based on device latitude and longitude.
* **Dark / Light Mode**: Smooth theme toggling with `localStorage` persistence.
* **Dynamic Weather Backgrounds**: Adaptive visual accents matching current weather conditions.
* **Responsive SaaS Design**: Mobile-first design optimized across desktop, tablet, and mobile screens.

---

## 🛠️ Tech Stack

* **Backend**: Python 3.12+, Flask, Requests, SQLite, python-dotenv
* **Frontend**: HTML5, CSS3 (Vanilla design tokens & grid), Vanilla JavaScript (ES6+), Chart.js
* **Testing**: Pytest

---

## 🚀 Installation & Setup

### 1. Clone & Navigate
```bash
git clone https://github.com/your-username/weather-dashboard.git
cd weather-dashboard
```

### 2. Set Up Virtual Environment

**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows CMD:**
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a local `.env` file in the root directory:
```bash
copy .env.example .env
```
Edit `.env` and set your configuration:
```env
WEATHER_API_KEY=your_actual_api_key
SECRET_KEY=your_actual_secret_key
FLASK_ENV=development
```

> [!IMPORTANT]  
> The `.env` file contains your private API key and secrets. It **MUST NEVER** be committed to GitHub or public version control. It is already included in `.gitignore`.

### 5. Run the Application
```bash
python app.py
```
Open your browser at `http://127.0.0.1:5000`.

---

## ☁️ SQLite & Deployment Note

SQLite is used for local development. Serverless deployment environments such as Vercel may not provide persistent local filesystem storage, so persistent favorites/search history may require a hosted database such as PostgreSQL in a future deployment phase.

---

## 📁 Project Structure

```text
weather-dashboard/
│
├── app.py                  # Flask application routes and initialization
├── requirements.txt        # Python package dependencies
├── vercel.json             # Vercel serverless deployment config
├── .env                    # Environment variables (IGNORED BY GIT)
├── .env.example            # Environment template
├── .gitignore              # Git ignore rules
├── README.md               # Documentation
│
├── database/
│   └── db.py               # SQLite database helper & migrations
│
├── services/
│   └── weather_service.py  # OpenWeatherMap API service & normalization
│
├── templates/
│   └── index.html          # Main HTML dashboard template
│
├── static/
│   ├── css/
│   │   └── style.css       # Custom styles, layout & CSS themes
│   └── js/
│       └── app.js          # Dynamic UI controller & Chart.js logic
│
└── tests/
    └── test_app.py         # Pytest test suite
```

---

## 📸 Screenshots

*(Screenshots placeholder — preview images will be added here)*

---

## 🔬 Running Automated Tests

Run all unit and integration tests using Pytest:
```bash
pytest
```

---

## 🔮 Future Improvements

- PostgreSQL for persistent production storage
- API response caching
- Rate limiting
- User authentication
- More detailed weather analytics
- Improved deployment infrastructure
