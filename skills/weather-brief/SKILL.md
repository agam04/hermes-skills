---
name: weather-brief
description: "Short, practical weather brief for any place: now, today, tomorrow, plus what to bring (umbrella, jacket, sunscreen). No API key."
version: 1.0.0
author: Agam Gupta (with Claude Opus 5.5)
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [weather, forecast, daily, briefing, open-meteo]
    category: productivity
    related_skills: []
---

# Weather brief

Use this when the user asks about the weather, whether to bring an umbrella or a jacket, or wants
weather in a morning briefing: "weather in Seattle tomorrow?", "do I need an umbrella today?",
"weather brief for Austin".

The data comes from Open-Meteo (no key). For US places the US National Weather Service is the
automatic fallback. `scripts/weather_brief.py` is stdlib-only Python 3; it geocodes the place,
fetches the forecast and adds deterministic "what to bring" hints.

## Prerequisites

- Python 3.9+ on the machine that runs the terminal tool. Outbound HTTPS to
  `geocoding-api.open-meteo.com`, `api.open-meteo.com` and (US fallback) `api.weather.gov`.
- No credentials, no environment variables, nothing to configure.

## How to run

The script lives in this skill's directory. `skill_view` returns it as `skill_dir`; for a hub
install it is normally `~/.hermes/skills/weather-brief/`.

```bash
S=~/.hermes/skills/weather-brief/scripts/weather_brief.py
python3 "$S" --place "Seattle" --days 2          # Fahrenheit/mph (default)
python3 "$S" --place "Berlin" --days 3 --units c # Celsius/kmh
python3 "$S" --lat 34.05 --lon -118.24           # coordinates instead of a name
```

Output is JSON: `place`, `timezone`, `current` (temp, feelsLike, summary, wind), `days[]` (date,
summary, high, low, precipChancePct, uvMax), `advice[]`, `source`, and `fallbackFrom` when the
NWS fallback answered. On failure: `{"ok": false, "error": ...}` and exit code 1.

Place resolution: if the user names no place, use the place in USER.md or memory if there is one;
otherwise ask once. If the name is ambiguous ("Springfield"), add the state or country.

No terminal available? Fetch the same data with `web_extract` (or any HTTP tool) from
`https://api.open-meteo.com/v1/forecast?latitude=<lat>&longitude=<lon>&timezone=auto&forecast_days=2&temperature_unit=fahrenheit&current=temperature_2m,weather_code&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max`
and use the WMO code table in the script for the summary words.

## Reply format (keep it short)

```
<Place>: <temp> now, <summary>. Today <high>/<low>, <chance>% rain.
Tomorrow: <summary>, <high>/<low>, <chance>% rain.
Bring: <advice items, or "nothing special">.
(Source: <source>)
```

## Rules

- Only numbers from the script or the API. Never estimate or fill in a missing value; say
  "not available" instead.
- Report the dates as given by `days[].date` (the place's local date). Don't relabel days.
- Mention the source in one short line, and say so if the NWS fallback was used.
- If both sources fail, say the weather service is unavailable right now. Don't guess.
