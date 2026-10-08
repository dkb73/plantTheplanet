"""NASA POWER daily point aggregates (min / max / median).

Sources:
- Daily point API: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
- OpenAPI v2.10.0: https://power.larc.nasa.gov/api/temporal/daily/openapi.json
- Parameter dictionary: https://power.larc.nasa.gov/parameters/
"""

from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from statistics import median

import requests
import yaml

_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


@lru_cache(maxsize=1)
def _load_config() -> dict:
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at root of {_CONFIG_PATH}")
    return data


def _yyyymmdd(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y%m%d")
    return str(value).replace("-", "")


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(_yyyymmdd(value), "%Y%m%d").date()


def _n_years_back(today: date, years: int) -> date:
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, day=28)


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _series_values(series: dict, fill_value: float) -> list[float]:
    values = []
    for raw in series.values():
        if raw is None:
            continue
        number = float(raw)
        if number == float(fill_value):
            continue
        values.append(number)
    return values


def fetch_power_aggregates(
    latitude,
    longitude,
    start_date,
    end_date,
    parameters=None,
    community=None,
):
    """Fetch NASA POWER daily point data and aggregate each parameter.

    Returns a list of one-key dicts, in the same order as ``parameters``::

        [{"T2M": {"min": ..., "max": ..., "median": ..., "unit": "C"}}, ...]
    """
    cfg = _load_config()
    parameters = list(parameters or cfg["default_parameters"])
    community = community or cfg["community"]
    start = _yyyymmdd(start_date)
    end = _yyyymmdd(end_date)

    series_by_param = {}
    units_by_param = {}
    fill_value = cfg["fill_value"]

    for group in _chunks(parameters, cfg["max_params_per_request"]):
        response = requests.get(
            cfg["daily_point_url"],
            params={
                "parameters": ",".join(group),
                "community": community,
                "longitude": longitude,
                "latitude": latitude,
                "start": start,
                "end": end,
                "format": cfg["format"],
            },
            timeout=cfg["request_timeout_s"],
        )
        response.raise_for_status()
        payload = response.json()
        fill_value = payload.get("header", {}).get("fill_value", fill_value)
        series_by_param.update(payload.get("properties", {}).get("parameter", {}))
        units_by_param.update(payload.get("parameters", {}))

    result = []
    for name in parameters:
        unit = (units_by_param.get(name) or {}).get("units")
        values = _series_values(series_by_param.get(name, {}), fill_value)
        if not values:
            result.append({name: {"min": None, "max": None, "median": None, "unit": unit}})
            continue
        result.append(
            {
                    "property": name,
                    "min": min(values),
                    "max": max(values),
                    "median": median(values),
                    "unit": unit,
                
            }
        )
    return result


def fetch_historical_weather(
    latitude,
    longitude,
    today,
    harvest_cycle_days,
    parameters=None,
    community=None,
):
    """Window last year's same calendar day through harvest_cycle_days, then aggregate."""
    cfg = _load_config()
    start_date = _n_years_back(_as_date(today), int(cfg["lookback_years"]))
    end_date = start_date + timedelta(days=int(harvest_cycle_days))
    return fetch_power_aggregates(
        latitude,
        longitude,
        start_date,
        end_date,
        parameters=parameters,
        community=community,
    )


if __name__ == "__main__":
    import json

    demo = _load_config()["demo"]
    print(
        json.dumps(
            fetch_historical_weather(
                demo["latitude"],
                demo["longitude"],
                demo["today"],
                demo["harvest_cycle_days"],
            ),
            indent=2,
        )
    )
