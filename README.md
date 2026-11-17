# hermes-skills

Hermes Agent skill tap by Agam Gupta (CSCI 599, Assignment 3).
| Skill | What it does | Needs |
|---|---|---|
| [`weather-brief`](skills/weather-brief/SKILL.md) | Weather now / today / tomorrow for any place, plus what to bring | Python 3, internet. No API key |

## Install (Hermes v0.22.7)

```bash
hermes skills tap add agam04/hermes-skills
hermes skills install agam04/hermes-skills/skills/weather-brief
```

Then ask the agent: "weather brief for Seattle".

## Layout

```
skills/<name>/SKILL.md          # the skill
skills/<name>/scripts/*.py      # stdlib-only helpers the skill runs through the terminal tool
tests/                          # offline tests (no network)
```

Data: Open-Meteo (https://open-meteo.com, free, no key; attribution under CC BY 4.0) with the US
National Weather Service (https://api.weather.gov) as the US fallback.

License: MIT.
