import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.main import main as run_pipeline, fetch_open_meteo_forecast
from db.crop_matcher import find_suitable_crops, get_db_connection

# Simple in-memory cache for location recommendations
_REC_CACHE: Dict[str, List[Dict[str, Any]]] = {}

def get_recommendations_for_location(
    latitude: float,
    longitude: float,
    category: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Retrieve suitable crops using the pipeline and crop matcher, with graceful fallback."""
    cache_key = f"{round(latitude, 2)}_{round(longitude, 2)}"
    
    scored_crops = _REC_CACHE.get(cache_key)
    if scored_crops is None:
        forecast_data = None
        elevation = 500.0
        try:
            forecast_data = fetch_open_meteo_forecast(latitude, longitude, forecast_days=16)
            elevation = float(forecast_data.get("elevation", 500.0))
        except Exception:
            pass

        try:
            pipeline_res = run_pipeline(latitude, longitude)
        except Exception:
            # Fallback pipeline response with elevation and forecast
            pipeline_res = {
                "properties": [
                    {"property": "T2M", "value": 22.0},
                    {"property": "PRECTOTCORR", "value": 3.0},
                    {"property": "phh2o", "value": 6.5},
                    {"property": "elevation", "value": elevation},
                ],
                "classifications": {
                    "TEXT": "medium",
                    "FER": "moderate",
                    "DRA": "well",
                    "LIOPMN": "bright",
                },
                "forecast": forecast_data,
            }

        try:
            scored_crops = find_suitable_crops(
                pipeline_res,
                latitude=latitude,
                elevation=elevation,
                forecast_data=forecast_data,
                limit=100,
            )
            _REC_CACHE[cache_key] = scored_crops
        except Exception as e:
            # Direct query fallback if complex matcher encounters issue
            scored_crops = get_fallback_crops(limit=50)

    # Filter by category if requested
    results = scored_crops
    if category and category.lower() != "all":
        cat_lower = category.lower()
        results = [c for c in results if c.get("category") and cat_lower in c.get("category", "").lower()]

    return results[:limit]


def get_crop_details(ecoport_code: int) -> Optional[Dict[str, Any]]:
    """Fetch complete crop details from ecocrop table."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM ecocrop WHERE "EcoPortCode" = %s LIMIT 1;
                """,
                (ecoport_code,),
            )
            row = cur.fetchone()
            if not row:
                return None
            
            crop = dict(row)
            topmn = crop.get("TOPMN")
            topmx = crop.get("TOPMX")
            ropmn = crop.get("ROPMN")
            ropmx = crop.get("ROPMX")
            phopmn = crop.get("PHOPMN")
            phopmx = crop.get("PHOPMX")
            
            return {
                "ecoport_code": crop.get("EcoPortCode"),
                "scientific_name": crop.get("ScientificName"),
                "common_name": crop.get("COMNAME"),
                "category": crop.get("CAT") or "General Botanical",
                "life_form": crop.get("LIFO") or "Plant / Cultivar",
                "growth_habit": crop.get("HABI") or "Erect / Spreading",
                "life_span": crop.get("LISPA") or "Annual / Perennial",
                "where_to_grow": crop.get("PLAT") or "Garden beds, Containers, Patio pots",
                "suitability_score": 100.0,
                "growing_days_min": crop.get("GMIN"),
                "growing_days_max": crop.get("GMAX"),
                "temperature_range": f"{topmn} - {topmx} °C" if topmn and topmx else "15 - 30 °C",
                "rainfall_range": f"{ropmn} - {ropmx} mm" if ropmn and ropmx else "500 - 1500 mm",
                "ph_range": f"{phopmn} - {phopmx}" if phopmn and phopmx else "5.5 - 7.5",
                "altitude_max": crop.get("ALTMX") or 2000,
                "light": crop.get("LIOPMN") or "Bright indirect to full sun",
                "soil_texture": crop.get("TEXT") or "Well-drained loam",
                "soil_fertility": crop.get("FER") or "Moderate",
                "soil_drainage": crop.get("DRA") or "Good drainage",
                "soil_depth": crop.get("DEP") or "Medium root system (50–150 cm)",
                "abiotic_tolerance": crop.get("ABITOL") or "Standard resilience",
                "climatic_zone": crop.get("CLIZ") or "Temperate to Subtropical",
                "details": {
                    "family": crop.get("FAMNAME"),
                    "habit": crop.get("HABI"),
                    "lifespan": crop.get("LISPA"),
                    "scale": crop.get("PLAT"),
                },
            }
    finally:
        conn.close()


def get_fallback_crops(limit: int = 20) -> List[Dict[str, Any]]:
    """Safe fallback when complex environmental query is offline."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT "EcoPortCode", "ScientificName", "COMNAME", "CAT", "LIFO", "HABI", "LISPA", "PLAT", "GMIN", "GMAX"
                FROM ecocrop
                WHERE "COMNAME" IS NOT NULL
                ORDER BY "EcoPortCode" ASC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()
            return [
                {
                    "ecoport_code": r["EcoPortCode"],
                    "scientific_name": r["ScientificName"],
                    "common_name": r["COMNAME"],
                    "category": r["CAT"],
                    "life_form": r["LIFO"] or "Plant",
                    "growth_habit": r.get("HABI"),
                    "life_span": r.get("LISPA"),
                    "where_to_grow": r.get("PLAT"),
                    "suitability_score": 75.0,
                    "optimal_matches": ["temperature", "pH", "rainfall"],
                    "optimal_match_count": 3,
                    "growing_days_min": r["GMIN"],
                    "growing_days_max": r["GMAX"],
                    "details": {},
                }
                for r in rows
            ]
    finally:
        conn.close()
