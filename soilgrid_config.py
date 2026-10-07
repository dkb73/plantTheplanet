"""Load static SoilGrids settings from config/soilgrids.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "soilgrids.yaml"


@lru_cache(maxsize=1)
def load_soilgrids_config(path: Path | None = None) -> Mapping[str, Any]:
    config_path = path or _CONFIG_PATH
    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, Mapping):
        raise ValueError(f"Expected mapping at root of {config_path}")
    return data


def _as_str_sequence(value: Any, *, field: str) -> tuple[str, ...]:
    if value is None:
        raise ValueError(f"{field} must be a list of strings")
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a list of strings")
    return tuple(str(item) for item in value)


def catalog_depths(config: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    cfg = config or load_soilgrids_config()
    return _as_str_sequence(cfg.get("depths"), field="depths")


def catalog_statistics(config: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    cfg = config or load_soilgrids_config()
    return _as_str_sequence(cfg.get("statistics"), field="statistics")


def catalog_properties(config: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    cfg = config or load_soilgrids_config()
    return _as_str_sequence(cfg.get("properties"), field="properties")


def rest_settings(config: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    cfg = config or load_soilgrids_config()
    rest = cfg.get("rest")
    if not isinstance(rest, Mapping):
        raise ValueError("config.rest must be a mapping")
    return rest


def resolve_list(
    key: str,
    *,
    catalog: Sequence[str],
    config: Mapping[str, Any],
    section: Mapping[str, Any] | None = None,
) -> list[str]:
    """Use section[key] if set, else config.defaults[key], else full catalog."""
    section = section or {}
    defaults = config.get("defaults") or {}
    if not isinstance(defaults, Mapping):
        defaults = {}

    raw = section.get(key)
    if raw is None:
        raw = defaults.get(key)
    if raw is None:
        return list(catalog)
    return list(_as_str_sequence(raw, field=key))


def demo_query_params(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(config or load_soilgrids_config())
    demo = cfg.get("demo")
    if not isinstance(demo, Mapping):
        raise ValueError("config.demo must be a mapping")

    props = catalog_properties(cfg)
    depths = catalog_depths(cfg)
    stats = catalog_statistics(cfg)

    return {
        "latitude": float(demo["latitude"]),
        "longitude": float(demo["longitude"]),
        "properties": resolve_list("properties", catalog=props, config=cfg, section=demo),
        "depths": resolve_list("depths", catalog=depths, config=cfg, section=demo),
        "statistics": resolve_list("statistics", catalog=stats, config=cfg, section=demo),
        "timeout": float(rest_settings(cfg).get("timeout_s", 60)),
    }
