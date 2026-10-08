"""Laya-based classification utility for EcoCrop target features.

Classifies soil and weather properties from SoilGrids and NASA POWER (pipeline/main.py) into target categories:
- TEXT:   Soil texture ('heavy', 'medium', 'light', 'organic', 'wide')
          Required properties: clay, sand, silt, soc
- FER:    Soil fertility ('high', 'moderate', 'low')
          Required properties: nitrogen, soc, cec
- DRA:    Soil drainage ('well (dry spells)', 'poorly (saturated >50% of year)', 'excessive (dry/moderately dry)')
          Required properties: clay
- LIOPMN: Light condition ('clear skies', 'very bright', 'cloudy skies', 'light shade', 'heavy shade')
          Required properties: CLOUD_AMT (cloud amount % min, max, median)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from laya import Router

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_TARGETS_YAML = _ROOT / "data" / "target_features.yaml"

# Global lazy router instance to avoid expensive reloads
_ROUTER_INSTANCE: Optional[Router] = None


def get_router() -> Router:
    """Return a singleton Laya Router instance, initializing on first use."""
    global _ROUTER_INSTANCE
    if _ROUTER_INSTANCE is None:
        _ROUTER_INSTANCE = Router(preload=True)
    return _ROUTER_INSTANCE


def load_target_features(yaml_path: Optional[Union[str, Path]] = None) -> Dict[str, List[str]]:
    """Load target feature union lists from YAML file."""
    path = Path(yaml_path) if yaml_path else _DEFAULT_TARGETS_YAML
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data

    # Fallback to standard unions if file is missing
    return {
        "TEXT": ["heavy", "medium", "light", "organic", "wide"],
        "FER": ["high", "low", "moderate"],
        "DRA": [
            "well (dry spells)",
            "poorly (saturated >50% of year)",
            "excessive (dry/moderately dry)",
        ],
        "LIOPMN": [
            "clear skies",
            "very bright",
            "cloudy skies",
            "light shade",
            "heavy shade",
        ],
    }


def normalize_inputs(
    data_input: Union[List[Dict[str, Any]], Dict[str, Any]]
) -> Dict[str, Any]:
    """Extract and normalize soil and weather property values from pipeline output or dict.

    Handles:
    - Single property dict: {"property": "CLOUD_AMT", "min": 60.21, ...} or {"property": "clay", "value": 29.9}
    - List of dicts from pipeline/main.py:
        * Soil items: {"property": "clay", "value": 29.9, ...}
        * Weather items: {"property": "CLOUD_AMT", "min": 60.21, "max": 99.15, "median": 93.02, ...}
    - Dictionary with property names as keys (scalar values or sub-dictionaries).
    """
    normalized: Dict[str, Any] = {}

    if isinstance(data_input, dict) and "property" in data_input:
        data_input = [data_input]

    if isinstance(data_input, list):
        for item in data_input:
            if not isinstance(item, dict) or "property" not in item:
                continue
            prop = str(item["property"]).strip()
            prop_lower = prop.lower()

            # Weather statistics (e.g., CLOUD_AMT)
            if "median" in item or "min" in item or "max" in item:
                for stat in ("median", "min", "max"):
                    if stat in item and item[stat] is not None:
                        try:
                            val = float(item[stat])
                            normalized[f"{prop_lower}_{stat}"] = val
                        except (ValueError, TypeError):
                            pass
                if "median" in item and item["median"] is not None:
                    normalized[prop_lower] = float(item["median"])
            # Soil/standard properties
            elif "value" in item and item["value"] is not None:
                try:
                    normalized[prop_lower] = float(item["value"])
                except (ValueError, TypeError):
                    pass

    elif isinstance(data_input, dict):
        for k, v in data_input.items():
            prop_lower = str(k).strip().lower()
            if isinstance(v, dict):
                if "median" in v or "min" in v or "max" in v:
                    for stat in ("median", "min", "max"):
                        if stat in v and v[stat] is not None:
                            try:
                                normalized[f"{prop_lower}_{stat}"] = float(v[stat])
                            except (ValueError, TypeError):
                                pass
                    if "median" in v and v["median"] is not None:
                        normalized[prop_lower] = float(v["median"])
                elif "value" in v and v["value"] is not None:
                    try:
                        normalized[prop_lower] = float(v["value"])
                    except (ValueError, TypeError):
                        pass
            elif v is not None:
                try:
                    normalized[prop_lower] = float(v)
                except (ValueError, TypeError):
                    pass

    return normalized


# Alias for backward compatibility
normalize_soil_inputs = normalize_inputs


def _formulate_text_state_and_question(
    props: Dict[str, Any], allowed_options: List[str]
) -> tuple[str, Dict[str, Any]]:
    clay = props.get("clay", 0.0)
    sand = props.get("sand", 0.0)
    silt = props.get("silt", 0.0)
    soc = props.get("soc", 0.0)

    state = (
        f"Soil texture physical composition: Sand={sand:.1f}%, Silt={silt:.1f}%, "
        f"Clay={clay:.1f}%, Soil Organic Carbon (SOC)={soc:.1f} g/kg."
    )
    if soc > 120.0:
        state += " This soil is highly organic with peat or muck."
    elif clay > 35.0:
        state += " This soil has high clay content, fine texture, heavy."
    elif sand > 65.0 and clay < 20.0:
        state += " This soil has high sand content, coarse texture, light."
    elif 15.0 <= clay <= 35.0:
        state += " This soil has a balanced loam/silt/clay mix, medium texture."
    else:
        state += " This soil has a mixed or wide texture profile."

    all_criteria = {
        "heavy": "Fine-textured clay soil (>35% clay), heavy and dense.",
        "medium": "Balanced medium-textured loamy soil (15-35% clay).",
        "light": "Coarse sandy light soil (>65% sand, <20% clay).",
        "organic": "Organic soil rich in organic carbon (>120 g/kg).",
        "wide": "Wide adaptability or intermediate texture.",
    }
    criteria = {k: v for k, v in all_criteria.items() if not allowed_options or k in allowed_options}

    question = {
        "type": "choice",
        "instructions": (
            "Classify the soil texture class (TEXT) based on sand, silt, clay, and organic carbon."
        ),
        "criteria": criteria,
    }
    return state, question


def _formulate_fer_state_and_question(
    props: Dict[str, Any], allowed_options: List[str]
) -> tuple[str, Dict[str, Any]]:
    n = props.get("nitrogen", 0.0)
    soc = props.get("soc", 0.0)
    cec = props.get("cec", 0.0)

    state = (
        f"Soil chemical fertility indicators: Nitrogen={n:.2f} g/kg, "
        f"Soil Organic Carbon (SOC)={soc:.1f} g/kg, CEC={cec:.1f} cmol(c)/kg."
    )
    if cec >= 22.0 and (n >= 2.0 or soc >= 20.0):
        state += " High nutrient availability, high CEC, and rich organic matter."
    elif cec < 12.0 and n < 1.0 and soc < 10.0:
        state += " Low nutrient retention, poor fertility, low CEC and low organic matter."
    else:
        state += " Moderate nutrient capacity, standard agricultural fertility."

    all_criteria = {
        "high": "High fertility, rich nutrients, high CEC and organic matter.",
        "moderate": "Moderate fertility, average nutrient retention.",
        "low": "Low fertility, nutrient-poor, low CEC and organic matter.",
    }
    criteria = {k: v for k, v in all_criteria.items() if not allowed_options or k in allowed_options}

    question = {
        "type": "choice",
        "instructions": "Classify soil fertility (FER) into high, moderate, or low.",
        "criteria": criteria,
    }
    return state, question


def _formulate_dra_state_and_question(
    props: Dict[str, Any], allowed_options: List[str]
) -> tuple[str, Dict[str, Any]]:
    clay = props.get("clay", 0.0)

    state = f"Soil drainage evaluation based on clay content: Clay={clay:.1f}%."
    if clay > 35.0:
        state += " High clay content (>35%) causing slow water permeability, leading to poor drainage and waterlogged conditions."
    elif clay < 15.0:
        state += " Low clay content (<15%) causing rapid water percolation, resulting in excessive drainage and dry conditions."
    else:
        state += " Moderate clay content (15-35%) providing good moisture retention and well-drained conditions."

    all_criteria = {
        "well (dry spells)": "Well-drained soil with moderate clay (15-35%), good moisture retention.",
        "poorly (saturated >50% of year)": "Poorly drained soil with high clay (>35%), saturated and waterlogged.",
        "excessive (dry/moderately dry)": "Excessively drained soil with low clay (<15%), dry and fast-draining.",
    }
    criteria = {k: v for k, v in all_criteria.items() if not allowed_options or k in allowed_options}

    question = {
        "type": "choice",
        "instructions": "Classify soil drainage condition (DRA) based on clay percentage.",
        "criteria": criteria,
    }
    return state, question


def _formulate_liopmn_state_and_question(
    props: Dict[str, Any], allowed_options: List[str]
) -> tuple[str, Dict[str, Any]]:
    median_val = props.get("cloud_amt_median", props.get("cloud_amt", 0.0))
    min_val = props.get("cloud_amt_min", median_val)
    max_val = props.get("cloud_amt_max", median_val)

    state = f"Weather observation: Cloud amount is {median_val:.1f}% (min: {min_val:.1f}%, max: {max_val:.1f}%)."
    if median_val > 85.0:
        state += " Sky is completely covered by thick dark clouds producing heavy shade."
    elif median_val > 65.0:
        state += " Sun is obscured behind continuous clouds creating light shade."
    elif median_val > 40.0:
        state += " Sky has substantial cloud cover with cloudy skies."
    elif median_val > 15.0:
        state += " Sun shines intensely with few scattered clouds, very bright."
    else:
        state += " Sky has zero or minimal clouds, clear skies."

    all_criteria = {
        "clear skies": "Minimal cloud cover with clear skies (<15% clouds).",
        "very bright": "Intense sunshine with few clouds (15-40% clouds), very bright.",
        "cloudy skies": "Substantial cloudiness (40-65% clouds), cloudy skies.",
        "light shade": "Sun obscured behind overcast layer (65-85% clouds), light shade.",
        "heavy shade": "Thick dark overcast cover (>85% clouds), heavy shade.",
    }
    criteria = {k: v for k, v in all_criteria.items() if not allowed_options or k in allowed_options}

    question = {
        "type": "choice",
        "instructions": "Classify into the light category (LIOPMN) from cloud cover percentage.",
        "criteria": criteria,
    }
    return state, question


def classify_properties(
    data_input: Union[List[Dict[str, Any]], Dict[str, Any]],
    targets: Optional[List[str]] = None,
    yaml_path: Optional[Union[str, Path]] = None,
    router: Optional[Router] = None,
    return_details: bool = False,
) -> Union[Dict[str, str], Dict[str, Any]]:
    """Classify environmental properties into target features (TEXT, FER, DRA, LIOPMN) using Laya.

    Args:
        data_input: List of dicts from pipeline/main.py or a property dictionary.
        targets: List of target features to classify. If None, auto-selects based on available properties.
        yaml_path: Path to target_features.yaml. Defaults to data/target_features.yaml.
        router: Optional pre-instantiated Laya Router. If None, uses shared singleton.
        return_details: If True, returns full Laya output including probabilities and confidence.

    Returns:
        Dict mapping target feature names to classified classes (or full prediction dict if return_details=True).
    """
    props = normalize_inputs(data_input)
    target_unions = load_target_features(yaml_path)
    active_router = router if router is not None else get_router()

    # Determine targets to run
    if targets is not None:
        targets_to_run = [t.upper() for t in targets]
    else:
        targets_to_run = []
        if any(k in props for k in ("clay", "sand", "silt", "soc")):
            targets_to_run.append("TEXT")
        if any(k in props for k in ("nitrogen", "soc", "cec")):
            targets_to_run.append("FER")
        if "clay" in props:
            targets_to_run.append("DRA")
        if any(k in props for k in ("cloud_amt", "cloud_amt_median")):
            targets_to_run.append("LIOPMN")
        if not targets_to_run:
            targets_to_run = ["TEXT", "FER", "DRA"]

    results: Dict[str, str] = {}
    details: Dict[str, Any] = {}

    for target in targets_to_run:
        target_upper = target.upper()
        allowed = target_unions.get(target_upper, [])

        if target_upper == "TEXT":
            state, q = _formulate_text_state_and_question(props, allowed)
        elif target_upper == "FER":
            state, q = _formulate_fer_state_and_question(props, allowed)
        elif target_upper == "DRA":
            state, q = _formulate_dra_state_and_question(props, allowed)
        elif target_upper == "LIOPMN":
            state, q = _formulate_liopmn_state_and_question(props, allowed)
        else:
            continue

        raw = active_router.predict(state, {target_upper: q})

        ans_info = raw.get("answers", {}).get(target_upper, {})
        choice = ans_info.get("choice", "")
        results[target_upper] = choice
        details[target_upper] = ans_info

    if return_details:
        return {"predictions": results, "details": details}

    return results


# Backward compatibility alias
classify_soil_properties = classify_properties


def classify_text(
    data_input: Union[List[Dict[str, Any]], Dict[str, Any]],
    router: Optional[Router] = None,
) -> str:
    """Classify soil texture (TEXT) using clay, sand, silt, soc."""
    res = classify_properties(data_input, targets=["TEXT"], router=router)
    return res.get("TEXT", "")


def classify_fer(
    data_input: Union[List[Dict[str, Any]], Dict[str, Any]],
    router: Optional[Router] = None,
) -> str:
    """Classify soil fertility (FER) using nitrogen, soc, cec."""
    res = classify_properties(data_input, targets=["FER"], router=router)
    return res.get("FER", "")


def classify_dra(
    data_input: Union[List[Dict[str, Any]], Dict[str, Any]],
    router: Optional[Router] = None,
) -> str:
    """Classify soil drainage (DRA) using clay."""
    res = classify_properties(data_input, targets=["DRA"], router=router)
    return res.get("DRA", "")


def classify_liopmn(
    data_input: Union[List[Dict[str, Any]], Dict[str, Any]],
    router: Optional[Router] = None,
) -> str:
    """Classify light condition (LIOPMN) using CLOUD_AMT."""
    res = classify_properties(data_input, targets=["LIOPMN"], router=router)
    return res.get("LIOPMN", "")


if __name__ == "__main__":
    sample_data = [
        {"property": "phh2o", "depth": "0-5cm", "statistic": "mean", "raw": 57, "value": 5.7, "unit": "-", "mapped_units": "pH*10"},
        {"property": "clay", "depth": "0-5cm", "statistic": "mean", "raw": 299, "value": 29.9, "unit": "%", "mapped_units": "g/kg"},
        {"property": "sand", "depth": "0-5cm", "statistic": "mean", "raw": 421, "value": 42.1, "unit": "%", "mapped_units": "g/kg"},
        {"property": "silt", "depth": "0-5cm", "statistic": "mean", "raw": 280, "value": 28.0, "unit": "%", "mapped_units": "g/kg"},
        {"property": "soc", "depth": "0-5cm", "statistic": "mean", "raw": 250, "value": 25.0, "unit": "g/kg", "mapped_units": "dg/kg"},
        {"property": "nitrogen", "depth": "0-5cm", "statistic": "mean", "raw": 260, "value": 2.6, "unit": "g/kg", "mapped_units": "cg/kg"},
        {"property": "cec", "depth": "0-5cm", "statistic": "mean", "raw": 248, "value": 24.8, "unit": "cmol(c)/kg", "mapped_units": "mmol(c)/kg"},
        {"property": "cfvo", "depth": "0-5cm", "statistic": "mean", "raw": 142, "value": 14.2, "unit": "cm³/100cm³", "mapped_units": "cm³/dm³"},
        {"property": "CLOUD_AMT", "min": 60.21, "max": 99.15, "median": 93.02, "unit": "%"},
    ]
    print("Classifying sample soil and weather properties...")
    classification = classify_properties(sample_data)
    print("Classification result:")
    print(json.dumps(classification, indent=2))
