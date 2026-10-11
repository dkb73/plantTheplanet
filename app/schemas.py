from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Auth schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    created_at: datetime

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# User Preference schemas
class UserPreferenceUpdate(BaseModel):
    growing_scale: Optional[str] = "home_garden"
    experience_level: Optional[str] = "beginner"
    preferences: Optional[Dict[str, Any]] = None

class UserPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    growing_scale: str
    experience_level: str
    preferences: Dict[str, Any]

# Discovery schemas
class RecommendationRequest(BaseModel):
    latitude: float
    longitude: float
    category: Optional[str] = None
    limit: Optional[int] = 20

class CropSummaryOut(BaseModel):
    ecoport_code: int
    scientific_name: str
    common_name: Optional[str] = None
    category: Optional[str] = None
    life_form: Optional[str] = None
    growth_habit: Optional[str] = None
    life_span: Optional[str] = None
    where_to_grow: Optional[str] = None
    suitability_score: float
    optimal_matches: List[str] = []
    optimal_match_count: int = 0
    growing_days_min: Optional[int] = None
    growing_days_max: Optional[int] = None
    details: Dict[str, Any] = {}

class CropDetailOut(CropSummaryOut):
    temperature_range: Optional[str] = None
    rainfall_range: Optional[str] = None
    ph_range: Optional[str] = None
    altitude_max: Optional[int] = None
    light: Optional[str] = None
    soil_texture: Optional[str] = None
    soil_fertility: Optional[str] = None
    soil_drainage: Optional[str] = None
    soil_depth: Optional[str] = None
    abiotic_tolerance: Optional[str] = None
    climatic_zone: Optional[str] = None
    frost_sensitivity: Optional[str] = None

# Planting & Plan schemas
class PlantingCreate(BaseModel):
    ecoport_code: int
    planting_date: Optional[date] = None
    latitude: float
    longitude: float
    growing_scale: Optional[str] = "home_garden"

class CareTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_name: str
    frequency: str
    description: str
    is_completed: bool

class PlanStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    stage_order: int
    stage_name: str
    description: str
    start_day: int
    end_day: int
    milestones: List[str] = []
    is_completed: bool
    completed_at: Optional[datetime] = None
    care_tasks: List[CareTaskOut] = []

class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    planting_id: str
    version: int
    status: str
    summary: str
    estimated_total_days: int
    estimated_harvest_date: Optional[date] = None
    risks_and_precautions: List[str] = []
    stages: List[PlanStageOut] = []

class ObservationCreate(BaseModel):
    observation_date: Optional[date] = None
    note: str = Field(..., min_length=1)

class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    observation_date: date
    note: str
    created_at: datetime

class PlantingSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ecoport_code: int
    scientific_name: str
    common_name: Optional[str] = None
    category: Optional[str] = None
    planting_date: date
    latitude: float
    longitude: float
    growing_scale: str
    status: str
    days_elapsed: int
    estimated_harvest_date: Optional[date] = None
    current_stage_name: Optional[str] = None
    next_activity: Optional[str] = None
    completed_stages_count: int = 0
    total_stages_count: int = 0
    created_at: datetime

class PlantingDetailOut(PlantingSummaryOut):
    active_plan: Optional[PlanOut] = None
    observations: List[ObservationOut] = []

# Chat schemas
class ChatMessageCreate(BaseModel):
    message: str = Field(..., min_length=1)

class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    content: str
    created_at: datetime
