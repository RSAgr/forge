import asyncio
import time

import httpx

from app.config import settings

_cache: dict[str, tuple[float, object]] = {}
_ttl = 3600
_headers = {"User-Agent": f"CivicLens/1.0 ({settings.nominatim_contact_email})" if settings.nominatim_contact_email else "CivicLens/1.0 (civic grievance platform)"}
_nominatim_lock = asyncio.Lock()
_last_nominatim = 0.0


async def _get(url: str, params: dict, key: str):
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < _ttl:
        return cached[1]
    async with httpx.AsyncClient(timeout=20, headers=_headers) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    _cache[key] = (time.time(), data)
    return data


async def reverse_geocode(latitude: float, longitude: float) -> str:
    global _last_nominatim
    key = f"nominatim:{latitude:.5f}:{longitude:.5f}"
    async with _nominatim_lock:
        cached = _cache.get(key)
        if cached and time.time() - cached[0] < _ttl:
            return cached[1].get("display_name", "")
        wait = 1 - (time.monotonic() - _last_nominatim)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_nominatim = time.monotonic()
        data = await _get("https://nominatim.openstreetmap.org/reverse", {"lat": latitude, "lon": longitude, "format": "jsonv2"}, key)
        return data.get("display_name", "")


async def nearby_features(latitude: float, longitude: float, radius: int = 1000):
    query = f"""[out:json][timeout:20];(way(around:{radius},{latitude},{longitude})[highway];node(around:{radius},{latitude},{longitude})[amenity~"hospital|school|clinic"];way(around:{radius},{latitude},{longitude})[amenity~"hospital|school|clinic"];);out center tags;"""
    key = f"overpass:{latitude:.3f}:{longitude:.3f}:{radius}"
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < _ttl:
        return cached[1]
    async with httpx.AsyncClient(timeout=25, headers=_headers) as client:
        response = await client.post("https://overpass-api.de/api/interpreter", data={"data": query})
        response.raise_for_status()
        data = response.json()
    _cache[key] = (time.time(), data)
    return data
