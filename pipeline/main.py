"""Fetch soil and historical weather for one point and return one list."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "soilgrid"))

from weather_analytics.historical_analysis.historical_weather_data import (
    _load_config,
    fetch_historical_weather,
)
from soilgrid_point import query_soilgrids

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


def main(latitude: float, longitude: float) -> list[dict]:
    """Query SoilGrids and NASA POWER together and append both result lists."""
    demo = _load_config()["demo"]
    with contextlib.redirect_stdout(io.StringIO()):
        with ThreadPoolExecutor(max_workers=2) as pool:
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
            soil_rows = soil.result()["items"]
            weather_rows = weather.result()
    return [*soil_rows, *weather_rows]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python pipeline/main.py <latitude> <longitude>")
    rows = main(float(sys.argv[1]), float(sys.argv[2]))
    json.dump(rows, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
