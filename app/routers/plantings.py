from datetime import date, datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import User, Planting, PlantPlan, PlantPlanStage, CareTask, PlantObservation, EcoCrop
from app.schemas import (
    PlantingCreate,
    PlantingSummaryOut,
    PlantingDetailOut,
    ObservationCreate,
    ObservationOut,
    PlanOut,
)
from app.dependencies import get_current_user
from app.services.plan_service import generate_plan_for_planting

router = APIRouter(prefix="/plantings", tags=["User Garden & Plantings"])


def format_planting_summary(p: Planting) -> dict:
    crop = p.crop
    sci_name = crop.ScientificName if crop else f"Crop #{p.ecoport_code}"
    com_name = crop.COMNAME if crop and crop.COMNAME else sci_name
    cat = crop.CAT if crop and crop.CAT else None

    days_elapsed = max(0, (date.today() - p.planting_date).days)
    
    active_plan = p.plans[0] if p.plans else None
    est_harvest = active_plan.estimated_harvest_date if active_plan else None

    current_stage_name = "Not Started"
    next_act = "Review planting guide"
    completed_cnt = 0
    total_cnt = len(active_plan.stages) if active_plan else 0

    if active_plan and active_plan.stages:
        for stage in active_plan.stages:
            if stage.is_completed:
                completed_cnt += 1
            elif stage.start_day <= days_elapsed <= stage.end_day:
                current_stage_name = stage.stage_name
                # Find first incomplete task
                for t in stage.care_tasks:
                    if not t.is_completed:
                        next_act = f"{t.task_name} ({t.frequency})"
                        break
        
        # If all stages completed or days past last stage
        if completed_cnt == total_cnt and total_cnt > 0:
            current_stage_name = "Completed / Harvested"
            next_act = "Celebrate harvest!"
        elif current_stage_name == "Not Started" and active_plan.stages:
            current_stage_name = active_plan.stages[0].stage_name

    return {
        "id": p.id,
        "ecoport_code": p.ecoport_code,
        "scientific_name": sci_name,
        "common_name": com_name,
        "category": cat,
        "planting_date": p.planting_date,
        "latitude": p.latitude,
        "longitude": p.longitude,
        "growing_scale": p.growing_scale,
        "status": p.status,
        "days_elapsed": days_elapsed,
        "estimated_harvest_date": est_harvest,
        "current_stage_name": current_stage_name,
        "next_activity": next_act,
        "completed_stages_count": completed_cnt,
        "total_stages_count": total_cnt,
        "created_at": p.created_at,
    }


@router.post("", response_model=PlantingDetailOut, status_code=status.HTTP_201_CREATED)
def create_planting(
    data: PlantingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    planting = Planting(
        user_id=current_user.id,
        ecoport_code=data.ecoport_code,
        planting_date=data.planting_date or date.today(),
        latitude=data.latitude,
        longitude=data.longitude,
        growing_scale=data.growing_scale or "home_garden",
        status="active",
    )
    db.add(planting)
    db.commit()
    db.refresh(planting)

    # Generate initial personalized plan
    generate_plan_for_planting(planting, db)
    db.refresh(planting)

    summary = format_planting_summary(planting)
    summary["active_plan"] = planting.plans[0] if planting.plans else None
    summary["observations"] = planting.observations
    return summary


@router.get("", response_model=List[PlantingSummaryOut])
def list_plantings(
    search: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = Query("planting_date", enum=["planting_date", "created_at"]),
    order: str = Query("desc", enum=["asc", "desc"]),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Planting).filter(Planting.user_id == current_user.id)
    
    if status:
        query = query.filter(Planting.status == status)
    
    plantings = query.all()
    summaries = [format_planting_summary(p) for p in plantings]

    # In-memory search & category filtering for rich text
    if search:
        s_term = search.lower()
        summaries = [
            s for s in summaries
            if s_term in s["scientific_name"].lower()
            or (s["common_name"] and s_term in s["common_name"].lower())
        ]

    if category and category.lower() != "all":
        c_term = category.lower()
        summaries = [
            s for s in summaries
            if s["category"] and c_term in s["category"].lower()
        ]

    # Sorting
    reverse = (order == "desc")
    if sort_by == "planting_date":
        summaries.sort(key=lambda x: x["planting_date"], reverse=reverse)
    else:
        summaries.sort(key=lambda x: x["created_at"], reverse=reverse)

    start = (page - 1) * page_size
    return summaries[start : start + page_size]


@router.get("/{id}", response_model=PlantingDetailOut)
def get_planting(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    planting = db.query(Planting).filter(Planting.id == id, Planting.user_id == current_user.id).first()
    if not planting:
        raise HTTPException(status_code=404, detail="Planting not found")

    summary = format_planting_summary(planting)
    summary["active_plan"] = planting.plans[0] if planting.plans else None
    summary["observations"] = planting.observations
    return summary


@router.post("/{id}/retry-plan", response_model=PlanOut)
def retry_plan(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    planting = db.query(Planting).filter(Planting.id == id, Planting.user_id == current_user.id).first()
    if not planting:
        raise HTTPException(status_code=404, detail="Planting not found")

    new_plan = generate_plan_for_planting(planting, db)
    return new_plan


@router.post("/{id}/observations", response_model=ObservationOut)
def add_observation(
    id: str,
    data: ObservationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    planting = db.query(Planting).filter(Planting.id == id, Planting.user_id == current_user.id).first()
    if not planting:
        raise HTTPException(status_code=404, detail="Planting not found")

    obs = PlantObservation(
        planting_id=planting.id,
        observation_date=data.observation_date or date.today(),
        note=data.note,
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)
    return obs


@router.patch("/stages/{stage_id}/complete")
def toggle_stage_completion(
    stage_id: str,
    completed: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stage = (
        db.query(PlantPlanStage)
        .join(PlantPlan)
        .join(Planting)
        .filter(PlantPlanStage.id == stage_id, Planting.user_id == current_user.id)
        .first()
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found or access denied")

    stage.is_completed = completed
    stage.completed_at = datetime.now(timezone.utc) if completed else None
    db.commit()
    return {"stage_id": stage.id, "is_completed": stage.is_completed}


@router.patch("/tasks/{task_id}/complete")
def toggle_task_completion(
    task_id: str,
    completed: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(CareTask)
        .join(PlantPlanStage)
        .join(PlantPlan)
        .join(Planting)
        .filter(CareTask.id == task_id, Planting.user_id == current_user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or access denied")

    task.is_completed = completed
    db.commit()
    return {"task_id": task.id, "is_completed": task.is_completed}
