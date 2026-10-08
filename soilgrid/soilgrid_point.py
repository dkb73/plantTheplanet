

from __future__ import annotations

from typing import Any, Mapping, Sequence
from rich import print
import requests

from soilgrid_config import (
    catalog_depths,
    catalog_properties,
    catalog_statistics,
    demo_query_params,
    rest_settings,
)

_cfg_rest = rest_settings()
REST_QUERY_URL: str = str(_cfg_rest["query_url"])

# Catalogs from soilgrids.yaml (same labels as SoilGrids REST / WCS).
DEPTHS = catalog_depths()
STATISTICS = catalog_statistics()
PROPERTIES = catalog_properties()


def query_soilgrids(
    latitude: float,
    longitude: float,
    properties: Sequence[str],
    depths: Sequence[str],
    statistics: Sequence[str],
    *,
    timeout: float | None = None,
) -> Mapping[str, Any]:
    """
    Return soil values at a WGS84 point for every requested combination.

    Number of logical outputs (one cell each) is always:

        len(properties) * len(depths) * len(statistics)

    REST returns them in a single response; WCS would need that many API calls.
    """
    props = list(properties)
    depth_list = list(depths)
    stat_list = list(statistics)
    expected = len(props) * len(depth_list) * len(stat_list)
    if timeout is None:
        timeout = float(_cfg_rest.get("timeout_s", 60))

    response = requests.get(
        REST_QUERY_URL,
        params={
            "lat": latitude,
            "lon": longitude,
            "property": props,
            "depth": depth_list,
            "value": stat_list,
        },
        headers={"Accept": str(_cfg_rest.get("accept", "application/json"))},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    print("===========")
    print(payload)
    print("===========")
    items: list[dict[str, Any]] = []
    nested: dict[str, dict[str, dict[str, Any]]] = {p: {} for p in props}

    layers = payload.get("properties", {}).get("layers", [])
    layer_by_name = {layer["name"]: layer for layer in layers}

    for prop in props:
        layer = layer_by_name.get(prop)
        if layer is None:
            for depth in depth_list:
                for stat in stat_list:
                    cell = _empty_cell(prop, depth, stat, note="property missing in response")
                    items.append(cell)
                    nested[prop].setdefault(depth, {})[stat] = cell
            continue

        unit_info = layer.get("unit_measure") or {}
        d_factor = unit_info.get("d_factor") or 1
        target_units = unit_info.get("target_units")

        depths_in_response = {d["label"]: d for d in layer.get("depths", [])}

        for depth in depth_list:
            depth_block = depths_in_response.get(depth)
            for stat in stat_list:
                raw = None
                if depth_block is not None:
                    raw = (depth_block.get("values") or {}).get(stat)

                cell = {
                    "property": prop,
                    "depth": depth,
                    "statistic": stat,
                    "raw": raw,
                    "value": (raw / d_factor) if raw is not None else None,
                    "unit": target_units,
                    "mapped_units": unit_info.get("mapped_units"),
                }
                items.append(cell)
                nested[prop].setdefault(depth, {})[stat] = cell

    return {
        "latitude": latitude,
        "longitude": longitude,
        "expected_count": expected,
        "result_count": len(items),
        "items": items,
        "by_property": nested,
        "geometry": payload.get("geometry"),
        "query_time_s": payload.get("query_time_s"),
    }


def _empty_cell(
    prop: str,
    depth: str,
    stat: str,
    *,
    note: str,
) -> dict[str, Any]:
    return {
        "property": prop,
        "depth": depth,
        "statistic": stat,
        "raw": None,
        "value": None,
        "unit": None,
        "mapped_units": None,
        "note": note,
    }


if __name__ == "__main__":
    out = query_soilgrids(
        latitude=12.25,
        longitude=75.75,
        properties=["phh2o", "clay","sand","silt","soc","nitrogen","cec","cfvo"],
        depths=["0-5cm"],
        statistics=["mean"],
    )
    print(f"expected={out['expected_count']} items={out['result_count']} (one REST call)")
    for row in out["items"]:
        print(row)
