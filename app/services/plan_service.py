import json
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
import requests
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Planting, PlantPlan, PlantPlanStage, CareTask, EcoCrop
from pipeline.advisor import DEFAULT_FREE_MODELS

def generate_plan_for_planting(planting: Planting, db: Session) -> PlantPlan:
    """Generate or update personalized lifecycle plan for a planting record."""
    crop = db.query(EcoCrop).filter(EcoCrop.EcoPortCode == planting.ecoport_code).first()
    crop_name = crop.ScientificName if crop else f"Crop #{planting.ecoport_code}"
    common_name = crop.COMNAME if crop and crop.COMNAME else crop_name
    category = crop.CAT if crop and crop.CAT else "General Crop"
    gmin = crop.GMIN if crop and crop.GMIN and crop.GMIN > 0 else 60
    gmax = crop.GMAX if crop and crop.GMAX and crop.GMAX > 0 else 120
    avg_days = (gmin + gmax) // 2
    
    # Try calling OpenRouter LLM for personalized generation
    plan_data = None
    try:
        plan_data = call_llm_for_plan(
            crop_name=crop_name,
            common_name=common_name,
            category=category,
            planting_date=planting.planting_date,
            latitude=planting.latitude,
            longitude=planting.longitude,
            growing_scale=planting.growing_scale,
            gmin=gmin,
            gmax=gmax,
        )
    except Exception as e:
        # Fall back to deterministic agronomic plan
        plan_data = create_fallback_plan(common_name, category, avg_days)

    if not plan_data:
        plan_data = create_fallback_plan(common_name, category, avg_days)

    # Persist the plan
    harvest_days = plan_data.get("estimated_total_days", avg_days)
    estimated_harvest = planting.planting_date + timedelta(days=harvest_days)
    
    plan = PlantPlan(
        planting_id=planting.id,
        version=len(planting.plans) + 1,
        status="ready",
        summary=plan_data.get("summary", f"Personalized lifecycle plan for {common_name}"),
        estimated_total_days=harvest_days,
        estimated_harvest_date=estimated_harvest,
        risks_and_precautions=plan_data.get("risks_and_precautions", []),
        raw_plan_data=plan_data,
    )
    db.add(plan)
    db.flush()

    # Create stages and care tasks
    stages_input = plan_data.get("stages", [])
    for idx, s in enumerate(stages_input, start=1):
        stage = PlantPlanStage(
            plan_id=plan.id,
            stage_order=s.get("stage_order", idx),
            stage_name=s.get("stage_name", f"Stage {idx}"),
            description=s.get("description", ""),
            start_day=int(s.get("start_day", 0)),
            end_day=int(s.get("end_day", harvest_days)),
            milestones=s.get("milestones", []),
            is_completed=False,
        )
        db.add(stage)
        db.flush()

        for t in s.get("care_tasks", []):
            task = CareTask(
                stage_id=stage.id,
                task_name=t.get("task_name", "Care Activity"),
                frequency=t.get("frequency", "regular"),
                description=t.get("description", ""),
                is_completed=False,
            )
            db.add(task)

    db.commit()
    db.refresh(plan)
    return plan


def call_llm_for_plan(
    crop_name: str,
    common_name: str,
    category: str,
    planting_date: date,
    latitude: float,
    longitude: float,
    growing_scale: str,
    gmin: int,
    gmax: int,
) -> Optional[Dict[str, Any]]:
    """Prompt OpenRouter to generate structured JSON lifecycle plan."""
    if not settings.OPENROUTER_API_KEY:
        return None

    prompt = f"""You are an expert botanical garden planner.
Generate a structured, 4 to 5 stage lifecycle plan for growing:
- Plant: {common_name} ({crop_name})
- Category: {category}
- Growing Scale: {growing_scale}
- Location: Lat {latitude}, Lon {longitude}
- Planting Date: {planting_date.isoformat()}
- Maturity Range: {gmin} to {gmax} days (approx. {(gmin+gmax)//2} days)

REQUIREMENTS:
1. Divide the lifecycle into 4 to 5 realistic stages (e.g. Germination, Seedling Establishment, Vegetative Growth, Flowering/Fruiting, Harvesting).
2. The days must progress sequentially starting at day 0 up to approximately {(gmin+gmax)//2} days total.
3. For each stage, provide 1 to 3 practical care tasks with frequencies and milestones.
4. Output MUST be ONLY valid JSON matching this schema, with no markdown fences, no comments, and no preamble:

{{
  "summary": "Concise summary of the plant's journey and primary growth goals.",
  "estimated_total_days": {(gmin+gmax)//2},
  "stages": [
    {{
      "stage_order": 1,
      "stage_name": "Stage Name",
      "description": "Clear guidance for this stage.",
      "start_day": 0,
      "end_day": 14,
      "milestones": ["Milestone 1"],
      "care_tasks": [
        {{
          "task_name": "Task Name",
          "frequency": "daily/weekly",
          "description": "Specific action."
        }}
      ]
    }}
  ],
  "risks_and_precautions": ["Risk 1", "Risk 2"]
}}
"""

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/planttheplanet",
        "X-Title": "PlantMyPlanet Plan Generator",
    }
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    for model in DEFAULT_FREE_MODELS:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a botanical planning assistant that outputs strict JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"].strip()
                # Clean up any potential markdown code blocks
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\n?", "", content)
                    content = re.sub(r"\n?```$", "", content)
                data = json.loads(content)
                if "stages" in data and len(data["stages"]) >= 3:
                    return data
        except Exception:
            continue
    
    return None


def create_fallback_plan(common_name: str, category: str, total_days: int) -> Dict[str, Any]:
    """Deterministic, high quality 5-stage agronomic plan."""
    d1 = max(5, int(total_days * 0.12))
    d2 = max(d1 + 7, int(total_days * 0.30))
    d3 = max(d2 + 10, int(total_days * 0.65))
    d4 = max(d3 + 10, int(total_days * 0.88))
    d5 = total_days

    return {
        "summary": f"Personalized 5-stage lifecycle plan for growing {common_name} ({category}).",
        "estimated_total_days": total_days,
        "stages": [
            {
                "stage_order": 1,
                "stage_name": "Germination & Soil Preparation",
                "description": f"Prepare well-draining soil and sow {common_name} seeds at optimal depth.",
                "start_day": 0,
                "end_day": d1,
                "milestones": ["Seed coat cracks", "First sprout emerges from soil"],
                "care_tasks": [
                    {"task_name": "Moisture Check", "frequency": "daily", "description": "Keep soil evenly damp without waterlogging."},
                    {"task_name": "Temperature & Light", "frequency": "daily", "description": "Provide gentle warmth and indirect light."},
                ],
            },
            {
                "stage_order": 2,
                "stage_name": "Seedling Development",
                "description": "Support root establishment and healthy early true foliage.",
                "start_day": d1 + 1,
                "end_day": d2,
                "milestones": ["First set of true leaves appear", "Root system anchors"],
                "care_tasks": [
                    {"task_name": "Direct Sunlight", "frequency": "daily", "description": "Ensure 4-6 hours of daily sunlight."},
                    {"task_name": "Light Thinning", "frequency": "as needed", "description": "Thin seedlings if crowded to give ample space."},
                ],
            },
            {
                "stage_order": 3,
                "stage_name": "Vegetative Growth",
                "description": "Rapid stem expansion and vigorous leaf production.",
                "start_day": d2 + 1,
                "end_day": d3,
                "milestones": ["Sturdy main stem formed", "Abundant canopy"],
                "care_tasks": [
                    {"task_name": "Deep Watering", "frequency": "every 2-3 days", "description": "Water deeply at root level in early morning."},
                    {"task_name": "Organic Nutrition", "frequency": "bi-weekly", "description": "Apply balanced compost or organic fertilizer."},
                ],
            },
            {
                "stage_order": 4,
                "stage_name": "Budding & Maturation",
                "description": "Floral buds or fruiting nodes develop into mature produce.",
                "start_day": d3 + 1,
                "end_day": d4,
                "milestones": ["Flowers/pods develop", "Fruit reaches full size"],
                "care_tasks": [
                    {"task_name": "Pest & Mildew Inspection", "frequency": "weekly", "description": "Examine underside of leaves for pests."},
                    {"task_name": "Staking / Support", "frequency": "as needed", "description": "Stake heavy stems to prevent breakage."},
                ],
            },
            {
                "stage_order": 5,
                "stage_name": "Harvest & Preservation",
                "description": f"Pick {common_name} at peak flavor, nutrition, and firmness.",
                "start_day": d4 + 1,
                "end_day": d5,
                "milestones": ["Target color and firm texture achieved", "Bountiful harvest complete"],
                "care_tasks": [
                    {"task_name": "Gentle Harvesting", "frequency": "on maturity", "description": "Harvest using sharp clean shears."},
                    {"task_name": "Post-Harvest Bed Care", "frequency": "once", "description": "Mulch bed and rotate nutrients for next cycle."},
                ],
            },
        ],
        "risks_and_precautions": [
            "Protect young sprouts from intense afternoon heat.",
            "Avoid overwatering to prevent root fungal issues.",
            "Maintain consistent soil moisture during the budding stage.",
        ],
    }
