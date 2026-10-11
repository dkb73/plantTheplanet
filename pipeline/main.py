"""Fetch soil and historical weather for one point, classify with Laya, and return combined results."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "soilgrid"))

import requests
from weather_analytics.historical_analysis.historical_weather_data import (
    _load_config,
    fetch_historical_weather,
)
from soilgrid_point import query_soilgrids

try:
    from pipeline.classifier import classify_properties
except ImportError:
    from classifier import classify_properties

_SOIL_PROPERTIES = (
    "phh2o",
    "clay",
    "sand",
    "silt",
    "soc",
    "nitrogen",
    "cec",
    "cfvo",
)


def fetch_open_meteo_forecast(
    latitude: float,
    longitude: float,
    forecast_days: int = 16,
    timeout_s: int = 15,
) -> Dict[str, Any]:
    """Fetch 16-day daily forecast from Open-Meteo for precipitation and shortwave radiation."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        f"&daily=precipitation_sum,shortwave_radiation_sum"
        f"&timezone=auto&forecast_days={forecast_days}"
    )
    resp = requests.get(url, timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


def main(latitude: float, longitude: float) -> Dict[str, Any]:
    """Query SoilGrids, NASA POWER, and Open-Meteo forecast, then classify target features with Laya."""
    demo = _load_config()["demo"]
    with contextlib.redirect_stdout(io.StringIO()):
        with ThreadPoolExecutor(max_workers=3) as pool:
            soil = pool.submit(
                query_soilgrids,
                latitude=latitude,
                longitude=longitude,
                properties=_SOIL_PROPERTIES,
                depths=["0-5cm"],
                statistics=["mean"],
            )
            weather = pool.submit(
                fetch_historical_weather,
                latitude,
                longitude,
                demo["today"],
                demo["harvest_cycle_days"],
            )
            forecast = pool.submit(
                fetch_open_meteo_forecast,
                latitude,
                longitude,
                16,
            )

            soil_rows = soil.result()["items"]
            weather_rows = weather.result()
            try:
                forecast_data = forecast.result()
            except Exception:
                forecast_data = None

    raw_properties = [*soil_rows, *weather_rows]

    # Incorporate forecast parameters into raw_properties for classification and lookup
    if forecast_data:
        if "elevation" in forecast_data and forecast_data["elevation"] is not None:
            raw_properties.append({
                "property": "elevation",
                "value": float(forecast_data["elevation"]),
                "unit": "m",
            })

        daily = forecast_data.get("daily", {})
        rad_series = daily.get("shortwave_radiation_sum", [])
        if isinstance(rad_series, list) and rad_series:
            valid_rad = [float(x) for x in rad_series if x is not None]
            if valid_rad:
                raw_properties.append({
                    "property": "shortwave_radiation_sum",
                    "mean": sum(valid_rad) / len(valid_rad),
                    "median": sorted(valid_rad)[len(valid_rad) // 2],
                    "min": min(valid_rad),
                    "max": max(valid_rad),
                    "unit": "MJ/m²",
                })

        precip_series = daily.get("precipitation_sum", [])
        if isinstance(precip_series, list) and precip_series:
            valid_p = [float(x) for x in precip_series if x is not None]
            if valid_p:
                raw_properties.append({
                    "property": "forecast_precipitation_sum",
                    "sum": sum(valid_p),
                    "mean": sum(valid_p) / len(valid_p),
                    "max": max(valid_p),
                    "unit": "mm",
                })

    classifications = classify_properties(raw_properties)

    return {
        "properties": raw_properties,
        "classifications": classifications,
        "forecast": forecast_data,
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python pipeline/main.py <latitude> <longitude>")
    result = main(float(sys.argv[1]), float(sys.argv[2]))
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")

