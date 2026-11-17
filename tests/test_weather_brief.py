"""Offline tests for weather_brief.py (network replaced by canned responses)."""

import importlib.util
import json
import pathlib

import pytest

P = pathlib.Path(__file__).parents[1] / "skills/weather-brief/scripts/weather_brief.py"
spec = importlib.util.spec_from_file_location("weather_brief", P)
wb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wb)

GEO = {"results": [{"name": "Seattle", "admin1": "Washington", "country_code": "US",
                    "latitude": 47.6, "longitude": -122.3, "timezone": "America/Los_Angeles"}]}
OM = {"timezone": "America/Los_Angeles",
      "current": {"time": "2026-11-16T08:00", "temperature_2m": 44.0, "apparent_temperature": 40.0,
                  "weather_code": 61, "wind_speed_10m": 7.0},
      "daily": {"time": ["2026-11-16", "2026-11-17"], "weather_code": [63, 3],
                "temperature_2m_max": [50.0, 52.0], "temperature_2m_min": [41.0, 43.0],
                "precipitation_probability_max": [80, 20], "uv_index_max": [1.0, 2.0]}}


def fake(routes):
    def get_json(url, params=None, headers=None):
        for key, val in routes.items():
            if key in url:
                if isinstance(val, Exception):
                    raise val
                return val
        raise AssertionError(url)
    return get_json


def test_open_meteo_brief(monkeypatch):
    monkeypatch.setattr(wb, "get_json", fake({"geocoding": GEO, "api.open-meteo.com": OM}))
    out = wb.brief("Seattle", None, None, 2, "f")
    assert out["place"] == "Seattle, Washington, US"
    assert out["days"][0]["summary"] == "rain" and out["days"][0]["precipChancePct"] == 80
    assert out["advice"] == ["umbrella", "warm jacket"]
    assert "Open-Meteo" in out["source"]


def test_nws_fallback_for_us(monkeypatch):
    nws_points = {"properties": {"forecast": "https://api.weather.gov/gridpoints/SEW/1,1/forecast"}}
    nws_fc = {"properties": {"periods": [
        {"startTime": "2026-11-16T06:00:00-08:00", "isDaytime": True, "temperature": 50,
         "shortForecast": "Rain", "probabilityOfPrecipitation": {"value": 70}},
        {"startTime": "2026-11-16T18:00:00-08:00", "isDaytime": False, "temperature": 41,
         "shortForecast": "Rain", "probabilityOfPrecipitation": {"value": 60}}]}}
    monkeypatch.setattr(wb, "get_json", fake({
        "geocoding": GEO, "api.open-meteo.com": TimeoutError("hang"),
        "/points/": nws_points, "/gridpoints/": nws_fc}))
    out = wb.brief("Seattle", None, None, 1, "f")
    assert out["fallbackFrom"] == "open-meteo (TimeoutError)"
    assert out["days"] == [{"date": "2026-11-16", "summary": "Rain", "high": 50, "low": 41, "precipChancePct": 70}]


def test_non_us_no_fallback(monkeypatch):
    geo = {"results": [{"name": "Berlin", "country_code": "DE", "latitude": 52.5, "longitude": 13.4}]}
    monkeypatch.setattr(wb, "get_json", fake({"geocoding": geo, "api.open-meteo.com": TimeoutError()}))
    with pytest.raises(RuntimeError, match="weather_unavailable"):
        wb.brief("Berlin", None, None, 1, "c")


def test_cli_place_not_found(monkeypatch, capsys):
    monkeypatch.setattr(wb, "get_json", fake({"geocoding": {"results": []}}))
    assert wb.main(["--place", "Nowhere"]) == 1
    assert json.loads(capsys.readouterr().out)["error"].startswith("place_not_found")


def test_cli_requires_location():
    with pytest.raises(SystemExit):
        wb.main([])
