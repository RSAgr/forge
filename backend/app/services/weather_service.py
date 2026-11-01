from app.services.geospatial_service import _get


async def current_weather(latitude: float, longitude: float):
    return await _get("https://api.open-meteo.com/v1/forecast", {
        "latitude": latitude, "longitude": longitude,
        "current": "temperature_2m,precipitation,rain,weather_code",
        "hourly": "precipitation,rain", "past_days": 1, "forecast_days": 1,
    }, f"weather:{latitude:.2f}:{longitude:.2f}")
