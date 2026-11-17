#!/usr/bin/env python3
"""weather-brief helper: forecast for a place name or coordinates, as compact JSON.

Standard library only, no API keys. Open-Meteo first (geocoding + forecast); for US coordinates the
US National Weather Service (api.weather.gov) is the fallback when Open-Meteo errors or hangs.
The output always names the source that answered.

    python3 weather_brief.py --place "Los Angeles" [--days 2] [--units f|c]
    python3 weather_brief.py --lat 34.05 --lon -118.24 [--days 2]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from typing import Any

GEO = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
NWS = "https://api.weather.gov"
UA = "hermes-weather-brief/1.0 (+https://github.com/agam04/hermes-skills)"
TIMEOUT = 8.0

# WMO weather interpretation codes (Open-Meteo docs).
WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog",
    48: "depositing rime fog", 51: "light drizzle", 53: "drizzle", 55: "dense drizzle",
    56: "light freezing drizzle", 57: "freezing drizzle", 61: "light rain", 63: "rain",
    65: "heavy rain", 66: "light freezing rain", 67: "freezing rain", 71: "light snow", 73: "snow",
    75: "heavy snow", 77: "snow grains", 80: "light showers", 81: "showers", 82: "violent showers",
    85: "light snow showers", 86: "snow showers", 95: "thunderstorm", 96: "thunderstorm with hail",
    99: "thunderstorm with heavy hail",
}


def describe(code: Any) -> str:
    try:
        return WMO.get(int(code), f"code {code}")
    except (TypeError, ValueError):
        return "unknown"


def get_json(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 (fixed https hosts)
        return json.load(r)


def geocode(place: str) -> dict[str, Any]:
    d = get_json(GEO, {"name": place, "count": 1, "language": "en", "format": "json"})
    hits = d.get("results") or []
    if not hits:
        raise LookupError(f"place_not_found: {place}")
    h = hits[0]
    label = ", ".join(str(x) for x in (h.get("name"), h.get("admin1"), h.get("country_code")) if x)
    return {"name": label, "lat": h["latitude"], "lon": h["longitude"], "timezone": h.get("timezone", "auto")}


def open_meteo(lat: float, lon: float, tz: str, days: int, units: str) -> dict[str, Any]:
    f = units == "f"
    d = get_json(
        FORECAST,
        {
            "latitude": lat, "longitude": lon, "timezone": tz or "auto", "forecast_days": days,
            "temperature_unit": "fahrenheit" if f else "celsius",
            "wind_speed_unit": "mph" if f else "kmh",
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max",
        },
    )
    cur, daily = d.get("current") or {}, d.get("daily") or {}

    def at(key: str, i: int) -> Any:
        vals = daily.get(key) or []
        return vals[i] if i < len(vals) else None

    return {
        "timezone": d.get("timezone"),
        "current": {
            "time": cur.get("time"), "temp": cur.get("temperature_2m"),
            "feelsLike": cur.get("apparent_temperature"), "summary": describe(cur.get("weather_code")),
            "wind": cur.get("wind_speed_10m"),
        },
        "days": [
            {
                "date": day, "summary": describe(at("weather_code", i)), "high": at("temperature_2m_max", i),
                "low": at("temperature_2m_min", i), "precipChancePct": at("precipitation_probability_max", i),
                "uvMax": at("uv_index_max", i),
            }
            for i, day in enumerate(daily.get("time") or [])
        ],
        "source": "Open-Meteo (open-meteo.com), no API key",
    }


def nws(lat: float, lon: float, days: int) -> dict[str, Any]:
    """US only. /points -> forecast URL -> 12-hour periods folded into daily high/low. Fahrenheit."""
    h = {"Accept": "application/geo+json"}
    url = str(get_json(f"{NWS}/points/{lat:.4f},{lon:.4f}", headers=h)["properties"]["forecast"])
    if not url.startswith(NWS + "/"):
        raise RuntimeError("nws_unexpected_forecast_url")
    periods = get_json(url, headers=h)["properties"]["periods"]
    by_day: dict[str, dict[str, Any]] = {}
    for p in periods:
        day = str(p.get("startTime", ""))[:10]
        d = by_day.setdefault(day, {"date": day, "summary": "", "high": None, "low": None, "precipChancePct": None})
        chance = (p.get("probabilityOfPrecipitation") or {}).get("value")
        if p.get("isDaytime"):
            d["high"], d["summary"] = p.get("temperature"), p.get("shortForecast", "")
        else:
            d["low"] = p.get("temperature")
            d["summary"] = d["summary"] or p.get("shortForecast", "")
        if chance is not None:
            d["precipChancePct"] = max(chance, d["precipChancePct"] or 0)
    first = periods[0] if periods else {}
    return {
        "current": {"time": first.get("startTime"), "temp": first.get("temperature"), "summary": first.get("shortForecast")},
        "days": list(by_day.values())[:days],
        "source": "US National Weather Service (api.weather.gov), no API key",
    }


def advice(days: list[dict[str, Any]], units: str) -> list[str]:
    """Deterministic hints for the first day, so the model doesn't have to guess thresholds."""
    if not days:
        return []
    d, out = days[0], []
    cold, hot = (45, 88) if units == "f" else (7, 31)
    if (d.get("precipChancePct") or 0) >= 40:
        out.append("umbrella")
    if d.get("low") is not None and d["low"] <= cold:
        out.append("warm jacket")
    if d.get("high") is not None and d["high"] >= hot:
        out.append("heat: water and shade")
    if (d.get("uvMax") or 0) >= 6:
        out.append("sunscreen")
    return out


def brief(place: str | None, lat: float | None, lon: float | None, days: int, units: str) -> dict[str, Any]:
    days = max(1, min(days, 7))
    loc = geocode(place) if place else {"name": f"{lat:.3f},{lon:.3f}", "lat": lat, "lon": lon, "timezone": "auto"}
    try:
        data = open_meteo(loc["lat"], loc["lon"], loc["timezone"], days, units)
    except Exception as first:  # noqa: BLE001
        if units != "f" or not (24 <= loc["lat"] <= 50 and -125 <= loc["lon"] <= -66):
            raise RuntimeError(f"weather_unavailable: open-meteo {type(first).__name__}") from first
        data = nws(loc["lat"], loc["lon"], days)
        data["fallbackFrom"] = f"open-meteo ({type(first).__name__})"
    return {"ok": True, "place": loc["name"], "units": "F/mph" if units == "f" else "C/kmh", **data,
            "advice": advice(data["days"], units)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--place")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--units", choices=["f", "c"], default="f")
    a = ap.parse_args(argv)
    if not a.place and (a.lat is None or a.lon is None):
        ap.error("give --place or both --lat and --lon")
    try:
        out = brief(a.place, a.lat, a.lon, a.days, a.units)
    except Exception as e:  # noqa: BLE001
        out = {"ok": False, "error": str(e) or type(e).__name__}
    print(json.dumps(out, indent=1))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
