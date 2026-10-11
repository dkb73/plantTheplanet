"""EcoCrop database lookup and suitability ranking from pipeline output and forecast data.

Queries PostgreSQL for crops matching environmental, soil, and forecast conditions:
1. Hard filtering in SQL WHERE clause using absolute boundaries:
   - Latitude: LATMN, LATMX
   - Altitude / Elevation: ALTMX (e.g., 748 m)
   - Temperature (T2M): TMIN, TMAX
   - Precipitation (PRECTOTCORR annualised): RMIN, RMAX
   - Soil pH (phh2o): PHMIN, PHMAX
   - Classified Soil Texture (TEXT / TEXTR)
   - Classified Soil Fertility (FER / FERR)
   - Classified Soil Drainage (DRA / DRAR)
   - Classified Light Condition (LIOPMN / LIMN / LIMX)
2. Post-fetch incentivisation & sorting:
   - Evaluates optimal intervals (TOPMN..TOPMX, ROPMN..ROPMX, PHOPMN..PHOPMX, LATOPMN..LATOPMX,
     ALTMX elevation compatibility, optimal TEXT, FER, DRA, LIOPMN).
   - Evaluates shortwave solar radiation sum (MJ/m²/day) and 16-day forecast precipitation.
   - Computes composite Suitability Score (0-100%).
   - Returns candidate crops sorted by suitability score in descending order.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))


def get_db_connection():
    """Connect to Postgres using environment variables or compose defaults."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        user=os.getenv("POSTGRES_USER", "plant"),
        password=os.getenv("POSTGRES_PASSWORD", "plant"),
        dbname=os.getenv("POSTGRES_DB", "planttheplanet"),
    )


def extract_environmental_criteria(
    pipeline_output: Dict[str, Any],
    latitude: Optional[float] = None,
    elevation: Optional[float] = None,
    forecast_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract temperature, rainfall, pH, latitude, elevation, radiation, and classifications."""
    # Check forecast container
    fc = forecast_data or pipeline_output.get("forecast") or {}

    lat = latitude
    if lat is None and "latitude" in fc:
        lat = float(fc["latitude"])

    elev = elevation
    if elev is None and "elevation" in fc:
        elev = float(fc["elevation"])

    criteria: Dict[str, Any] = {
        "latitude": lat,
        "elevation": elev,
        "t2m": None,
        "rainfall_annual_mm": None,
        "ph": None,
        "text": None,
        "fer": None,
        "dra": None,
        "liopmn": None,
        "solar_radiation_mean": None,
        "forecast_precip_sum": None,
        "forecast_precip_peak": None,
    }

    # Extract forecast daily series if available
    daily = fc.get("daily", {}) if isinstance(fc, dict) else {}
    if isinstance(daily, dict):
        rad_series = daily.get("shortwave_radiation_sum", [])
        if isinstance(rad_series, list) and rad_series:
            valid_rad = [float(x) for x in rad_series if x is not None]
            if valid_rad:
                criteria["solar_radiation_mean"] = sum(valid_rad) / len(valid_rad)

        precip_series = daily.get("precipitation_sum", [])
        if isinstance(precip_series, list) and precip_series:
            valid_precip = [float(x) for x in precip_series if x is not None]
            if valid_precip:
                criteria["forecast_precip_sum"] = sum(valid_precip)
                criteria["forecast_precip_peak"] = max(valid_precip)

    raw_props = pipeline_output.get("properties", [])
    if isinstance(raw_props, list):
        for item in raw_props:
            if not isinstance(item, dict) or "property" not in item:
                continue
            prop = str(item["property"]).strip()
            prop_upper = prop.upper()

            # Temperature (T2M in °C)
            if prop_upper == "T2M":
                criteria["t2m"] = float(item.get("median", item.get("value", 0.0)))

            # Precipitation (PRECTOTCORR in mm/day -> annual mm)
            elif prop_upper == "PRECTOTCORR":
                daily_mm = float(item.get("median", item.get("value", 0.0)))
                criteria["rainfall_annual_mm"] = daily_mm * 365.0

            # Soil pH
            elif prop.lower() == "phh2o":
                val = item.get("value")
                if val is not None:
                    criteria["ph"] = float(val)

            # Elevation from property list
            elif prop.lower() == "elevation":
                val = item.get("value")
                if val is not None and criteria["elevation"] is None:
                    criteria["elevation"] = float(val)

            # Solar Radiation
            elif "shortwave_radiation" in prop.lower():
                val = item.get("mean", item.get("median", item.get("value")))
                if val is not None and criteria["solar_radiation_mean"] is None:
                    criteria["solar_radiation_mean"] = float(val)

    # Classified features
    classifications = pipeline_output.get("classifications", {})
    if isinstance(classifications, dict):
        criteria["text"] = classifications.get("TEXT")
        criteria["fer"] = classifications.get("FER")
        criteria["dra"] = classifications.get("DRA")
        criteria["liopmn"] = classifications.get("LIOPMN")

    return criteria


def build_sql_query() -> str:
    """Build single SQL query with hard absolute boundary conditions."""
    return """
    SELECT
        "EcoPortCode",
        "ScientificName",
        "COMNAME",
        "LIFO",
        "CAT",
        "TOPMN",
        "TOPMX",
        "TMIN",
        "TMAX",
        "ROPMN",
        "ROPMX",
        "RMIN",
        "RMAX",
        "PHOPMN",
        "PHOPMX",
        "PHMIN",
        "PHMAX",
        "LATOPMN",
        "LATOPMX",
        "LATMN",
        "LATMX",
        "ALTMX",
        "LIOPMN",
        "LIOPMX",
        "LIMN",
        "LIMX",
        "TEXT",
        "TEXTR",
        "FER",
        "FERR",
        "DRA",
        "DRAR",
        "PHOTO",
        "GMIN",
        "GMAX",
        "HABI",
        "LISPA",
        "PLAT",
        "DEP",
        "ABITOL",
        "CLIZ"
    FROM ecocrop
    WHERE
        -- 1. Primary localisation: Latitude limits (with NULL allowance)
        (%(lat)s::real IS NULL OR "LATMN" IS NULL OR "LATMN" <= %(lat)s)
        AND (%(lat)s::real IS NULL OR "LATMX" IS NULL OR %(lat)s <= "LATMX")

        -- 2. Altitude / Elevation tolerance (ALTMX >= elevation)
        AND (%(elevation)s::smallint IS NULL OR "ALTMX" IS NULL OR "ALTMX" >= %(elevation)s)

        -- 3. Absolute Temperature bounds (TMIN <= T2M <= TMAX)
        AND (%(t2m)s::smallint IS NULL OR "TMIN" IS NULL OR "TMIN" <= %(t2m)s)
        AND (%(t2m)s::smallint IS NULL OR "TMAX" IS NULL OR %(t2m)s <= "TMAX")

        -- 4. Absolute Rainfall bounds (RMIN <= Annual Rainfall <= RMAX)
        AND (%(rain)s::smallint IS NULL OR "RMIN" IS NULL OR "RMIN" <= %(rain)s)
        AND (%(rain)s::smallint IS NULL OR "RMAX" IS NULL OR %(rain)s <= "RMAX")

        -- 5. Absolute pH bounds (PHMIN <= pH <= PHMAX)
        AND (%(ph)s::numeric IS NULL OR "PHMIN" IS NULL OR "PHMIN" <= %(ph)s)
        AND (%(ph)s::numeric IS NULL OR "PHMAX" IS NULL OR %(ph)s <= "PHMAX")

        -- 6. Soil Texture: Comma-inclusive match across TEXT and TEXTR
        AND (%(text_pat)s::text IS NULL OR "TEXT" IS NULL OR "TEXT" ILIKE %(text_pat)s OR "TEXTR" ILIKE %(text_pat)s)

        -- 7. Soil Fertility: Match FER or broader FERR
        AND (%(fer_pat)s::text IS NULL OR "FER" IS NULL OR "FER" ILIKE %(fer_pat)s OR "FERR" ILIKE %(fer_pat)s)

        -- 8. Soil Drainage: Comma-inclusive match across DRA and DRAR
        AND (%(dra_pat)s::text IS NULL OR "DRA" IS NULL OR "DRA" ILIKE %(dra_pat)s OR "DRAR" ILIKE %(dra_pat)s)

        -- 9. Light Condition: Match LIOPMN or absolute tolerance LIMN/LIMX (with NULL allowance)
        AND (%(light_pat)s::text IS NULL OR "LIOPMN" IS NULL OR "LIOPMN" ILIKE %(light_pat)s OR "LIMN" ILIKE %(light_pat)s OR "LIMX" ILIKE %(light_pat)s);
    """


def calculate_suitability_score(crop: Dict[str, Any], criteria: Dict[str, Any]) -> Dict[str, Any]:
    """Score candidate crop based on optimal (OP) intervals and compute match metadata."""
    t2m = criteria.get("t2m")
    rain = criteria.get("rainfall_annual_mm")
    ph = criteria.get("ph")
    lat = criteria.get("latitude")
    elev = criteria.get("elevation")
    rad_mean = criteria.get("solar_radiation_mean")
    text = (criteria.get("text") or "").lower()
    fer = (criteria.get("fer") or "").lower()
    dra = (criteria.get("dra") or "").lower()
    liopmn = (criteria.get("liopmn") or "").lower()

    optimal_matches = []
    total_criteria_checked = 9

    # 1. Optimal Temperature (TOPMN <= t2m <= TOPMX)
    topmn = crop.get("TOPMN")
    topmx = crop.get("TOPMX")
    if t2m is not None and topmn is not None and topmx is not None:
        if topmn <= t2m <= topmx:
            optimal_matches.append("temperature")

    # 2. Optimal Rainfall (ROPMN <= rain <= ROPMX)
    ropmn = crop.get("ROPMN")
    ropmx = crop.get("ROPMX")
    if rain is not None and ropmn is not None and ropmx is not None:
        if ropmn <= rain <= ropmx:
            optimal_matches.append("rainfall")

    # 3. Optimal pH (PHOPMN <= ph <= PHOPMX)
    phopmn = crop.get("PHOPMN")
    phopmx = crop.get("PHOPMX")
    if ph is not None and phopmn is not None and phopmx is not None:
        if float(phopmn) <= ph <= float(phopmx):
            optimal_matches.append("pH")

    # 4. Optimal Latitude (LATOPMN <= abs(lat) <= LATOPMX)
    latopmn = crop.get("LATOPMN")
    latopmx = crop.get("LATOPMX")
    if lat is not None and latopmn is not None and latopmx is not None:
        abs_lat = abs(lat)
        if latopmn <= abs_lat <= latopmx:
            optimal_matches.append("latitude")

    # 5. Altitude / Elevation Compatibility (elev <= ALTMX)
    altmx = crop.get("ALTMX")
    if elev is not None and altmx is not None:
        if elev <= altmx:
            optimal_matches.append("elevation")

    # 6. Optimal Soil Texture
    crop_text = (crop.get("TEXT") or "").lower()
    if text and text in crop_text:
        optimal_matches.append("texture")

    # 7. Optimal Soil Fertility
    crop_fer = (crop.get("FER") or "").lower()
    if fer and fer in crop_fer:
        optimal_matches.append("fertility")

    # 8. Optimal Soil Drainage
    crop_dra = (crop.get("DRA") or "").lower()
    if dra and dra in crop_dra:
        optimal_matches.append("drainage")

    # 9. Optimal Light / Solar Radiation
    crop_light = (crop.get("LIOPMN") or "").lower()
    if liopmn and liopmn in crop_light:
        optimal_matches.append("light")
    elif rad_mean is not None and rad_mean >= 19.0 and ("very bright" in crop_light or "clear skies" in crop_light):
        optimal_matches.append("radiation")

    score_pct = round((len(optimal_matches) / total_criteria_checked) * 100.0, 1)

    return {
        "ecoport_code": crop.get("EcoPortCode"),
        "scientific_name": crop.get("ScientificName"),
        "common_name": crop.get("COMNAME"),
        "life_form": crop.get("LIFO") or "Plant / Cultivar",
        "growth_habit": crop.get("HABI"),
        "life_span": crop.get("LISPA"),
        "where_to_grow": crop.get("PLAT"),
        "category": crop.get("CAT"),
        "suitability_score": score_pct,
        "optimal_matches": optimal_matches,
        "optimal_match_count": len(optimal_matches),
        "growing_days_min": crop.get("GMIN"),
        "growing_days_max": crop.get("GMAX"),
        "max_altitude_m": altmx,
        "details": {
            "growth_habit": crop.get("HABI") or "Erect / Natural",
            "life_span": crop.get("LISPA") or "Annual / Perennial",
            "where_to_grow": crop.get("PLAT") or "Garden bed, Container, Farm",
            "soil_depth": crop.get("DEP") or "Medium (50–150 cm)",
            "temperature_optimal": f"{topmn} - {topmx} °C" if topmn and topmx else None,
            "rainfall_optimal": f"{ropmn} - {ropmx} mm" if ropmn and ropmx else None,
            "ph_optimal": f"{phopmn} - {phopmx}" if phopmn and phopmx else None,
            "max_elevation": f"{altmx} m" if altmx else "Unrestricted",
            "optimal_texture": crop.get("TEXT"),
            "optimal_fertility": crop.get("FER"),
            "optimal_drainage": crop.get("DRA"),
            "optimal_light": crop.get("LIOPMN"),
        },
    }


def find_suitable_crops(
    pipeline_output: Dict[str, Any],
    latitude: Optional[float] = None,
    elevation: Optional[float] = None,
    forecast_data: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = 50,
) -> List[Dict[str, Any]]:
    """Execute SQL lookup and return candidate crops sorted by optimal suitability score."""
    criteria = extract_environmental_criteria(
        pipeline_output,
        latitude=latitude,
        elevation=elevation,
        forecast_data=forecast_data,
    )

    sql = build_sql_query()
    abs_lat = abs(criteria["latitude"]) if criteria["latitude"] is not None else None

    params = {
        "lat": abs_lat,
        "elevation": criteria["elevation"],
        "t2m": criteria["t2m"],
        "rain": criteria["rainfall_annual_mm"],
        "ph": criteria["ph"],
        "text_pat": f"%{criteria['text']}%" if criteria["text"] else None,
        "fer_pat": f"%{criteria['fer']}%" if criteria["fer"] else None,
        "dra_pat": f"%{criteria['dra']}%" if criteria["dra"] else None,
        "light_pat": f"%{criteria['liopmn']}%" if criteria["liopmn"] else None,
    }

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    scored_crops = [calculate_suitability_score(dict(row), criteria) for row in rows]

    # Sort descending by suitability score, then by match count
    scored_crops.sort(
        key=lambda x: (x["suitability_score"], x["optimal_match_count"]),
        reverse=True,
    )

    if limit is not None and limit > 0:
        return scored_crops[:limit]

    return scored_crops


if __name__ == "__main__":
    from pipeline.main import main as run_pipeline, fetch_open_meteo_forecast

    # Default coordinates matching user's requested Open-Meteo query
    lat = float(sys.argv[1]) if len(sys.argv) > 1 else 12.2958
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else 76.6394

    print(f"Fetching live forecast from Open-Meteo for Lat={lat}, Lon={lon}...")
    forecast_data = fetch_open_meteo_forecast(lat, lon, forecast_days=16)
    elev = forecast_data.get("elevation", 748.0)
    print(f"Live forecast received: Elevation={elev}m, Days={len(forecast_data.get('daily', {}).get('time', []))}")

    print(f"\nRunning pipeline for: Latitude={lat}, Longitude={lon}...")
    pipeline_res = run_pipeline(lat, lon)

    print("\nClassifications obtained:")
    print(json.dumps(pipeline_res.get("classifications", {}), indent=2))

    print(f"\nPerforming EcoCrop database lookup with live forecast parameters (Elevation={elev}m)...")
    matched_crops = find_suitable_crops(
        pipeline_res,
        latitude=lat,
        elevation=elev,
        forecast_data=forecast_data,
        limit=10,
    )

    print(f"\nTop {len(matched_crops)} suitable crops:")
    for i, c in enumerate(matched_crops, start=1):
        com = c['common_name'] or 'N/A'
        first_common = com.split(',')[0].strip()
        print(
            f"{i:2d}. {c['scientific_name']} ({first_common}) "
            f"— Score: {c['suitability_score']}% "
            f"— Max Alt: {c['details']['max_elevation']} "
            f"— Optimal matches: {c['optimal_matches']}"
        )
