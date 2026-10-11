"""Plant advisor LLM chat client using OpenRouter free open-source models.

Injects environmental and matched crop context into system prompt and maintains
conversation history without requiring any vector database or retrieval layer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

_ROOT = Path(__file__).resolve().parents[1]

# Default free models on OpenRouter (in priority order for fallback)
DEFAULT_FREE_MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "liquid/lfm-2.5-2.6b:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
]


def _get_api_key() -> str:
    """Retrieve OpenRouter API key from environment or .env file."""
    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        return key

    env_path = _ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip()

    raise ValueError(
        "OPENROUTER_API_KEY not found in environment or .env file. "
        "Please set it or create a .env file."
    )


def format_advisor_system_prompt(
    environmental_data: Dict[str, Any],
    suitable_crops: List[Dict[str, Any]],
) -> str:
    """Construct structured context prompt containing site parameters and recommended crops."""
    crops_text = []
    for i, c in enumerate(suitable_crops[:10], start=1):
        common = c.get("common_name") or "N/A"
        matches = ", ".join(c.get("optimal_matches", []))
        alt = c.get("details", {}).get("max_elevation") or c.get("max_altitude_m") or "Unrestricted"
        crops_text.append(
            f"{i}. {c.get('scientific_name')} ({common})\n"
            f"   - Match Score: {c.get('suitability_score')}%\n"
            f"   - Optimal Matches: {matches}\n"
            f"   - Max Altitude Tolerance: {alt}"
        )
    crops_summary = "\n".join(crops_text) if crops_text else "No crops provided."

    return f"""You are the PlantThePlanet Botanical and Agricultural Advisor.

The user is planning to grow plants on their specific land. You have been provided with their exact site measurements and database-matched plant recommendations.

### USER'S SITE & ENVIRONMENTAL CONDITIONS:
- Latitude: {environmental_data.get('latitude')}, Elevation: {environmental_data.get('elevation')} meters
- Soil Properties:
  * Texture: {environmental_data.get('text')}
  * Drainage: {environmental_data.get('dra')}
  * Fertility: {environmental_data.get('fer')}
  * pH: {environmental_data.get('ph')}
- Climate & Weather:
  * Temperature: ~{environmental_data.get('t2m')} °C
  * Annual Rainfall: ~{environmental_data.get('rainfall_annual_mm')} mm
  * 16-Day Forecast Rain: ~{environmental_data.get('forecast_precip_sum')} mm
  * Solar Radiation: ~{environmental_data.get('solar_radiation_mean')} MJ/m²/day (Light condition: {environmental_data.get('liopmn')})

### DATABASE-MATCHED CROPS (Top Recommendations):
{crops_summary}

### YOUR INSTRUCTIONS:
1. Always treat the site data and matched crop list above as your primary ground truth.
2. Combine this data with your general botanical and agronomic knowledge to provide helpful, practical guidance (e.g., planting tips, soil preparation, watering schedules, organic fertilizer, pruning, companion crops).
3. If the user asks about a specific crop, explain why it fits (or doesn't fit) their measured soil pH, altitude, temperature, and rainfall.
4. Keep answers friendly, practical, and clear.
"""


def ask_advisor(
    user_message: str,
    environmental_data: Dict[str, Any],
    suitable_crops: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    max_history_turns: int = 6,
    timeout_s: int = 25,
) -> str:
    """Send conversation + context to OpenRouter free open-source LLM and return reply."""
    token = api_key or _get_api_key()
    system_prompt = format_advisor_system_prompt(environmental_data, suitable_crops)

    # Format OpenAI-compatible messages
    messages = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        for msg in conversation_history[-max_history_turns:]:
            role = "user" if msg.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("content", "")})

    messages.append({"role": "user", "content": user_message})

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/planttheplanet",
        "X-Title": "PlantThePlanet Advisor",
    }

    # Model selection with automatic fallback
    candidate_models = [model] if model else DEFAULT_FREE_MODELS
    last_error = ""

    for target_model in candidate_models:
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": 0.7,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                last_error = f"{target_model} returned {resp.status_code}: {resp.text}"
                continue
        except requests.RequestException as exc:
            last_error = str(exc)
            continue

    raise RuntimeError(f"OpenRouter API call failed across all candidate models: {last_error}")


if __name__ == "__main__":
    # Test advisor with our actual pipeline & crop matcher results
    sample_env = {
        "latitude": 12.2958,
        "elevation": 748,
        "t2m": 24.5,
        "rainfall_annual_mm": 2100,
        "forecast_precip_sum": 86.8,
        "solar_radiation_mean": 21.7,
        "liopmn": "very bright",
        "ph": 5.7,
        "text": "medium",
        "dra": "well (dry spells)",
        "fer": "high",
    }

    sample_crops = [
        {
            "scientific_name": "Theobroma cacao",
            "common_name": "cocoa, cacao",
            "suitability_score": 44.4,
            "optimal_matches": ["temperature", "rainfall", "elevation", "radiation"],
            "max_altitude_m": 900,
        },
        {
            "scientific_name": "Mimosa pudica",
            "common_name": "sensitive plant",
            "suitability_score": 33.3,
            "optimal_matches": ["temperature", "rainfall", "radiation"],
            "max_altitude_m": "Unrestricted",
        },
    ]

    query = "Why is Cocoa recommended for my land, and how should I prepare the soil given it will rain 86mm soon?"
    print(f"User: {query}\n")
    print("Calling OpenRouter free model...")
    answer = ask_advisor(query, sample_env, sample_crops)
    print("\n--- Advisor Response ---")
    print(answer)
