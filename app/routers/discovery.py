from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from app.schemas import RecommendationRequest, CropSummaryOut, CropDetailOut
from app.services.discovery_service import get_recommendations_for_location, get_crop_details

router = APIRouter(prefix="/discovery", tags=["Plant Discovery"])

@router.post("/recommendations", response_model=List[CropSummaryOut])
def get_recommendations(payload: RecommendationRequest):
    if not (-90.0 <= payload.latitude <= 90.0):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
    if not (-180.0 <= payload.longitude <= 180.0):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")

    crops = get_recommendations_for_location(
        latitude=payload.latitude,
        longitude=payload.longitude,
        category=payload.category,
        limit=payload.limit or 20,
    )
    return crops


@router.get("/crops/{ecoport_code}", response_model=CropDetailOut)
def get_crop(ecoport_code: int):
    crop = get_crop_details(ecoport_code)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found in catalog")
    return crop


@router.get("/categories", response_model=List[str])
def get_categories():
    return [
        "Vegetable",
        "Fruit",
        "Herb / Spice",
        "Grain / Cereal",
        "Legume / Pulse",
        "Flower / Ornamental",
        "Medicinal",
    ]
