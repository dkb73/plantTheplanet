from datetime import date
from typing import List, Dict, Any, Optional
import requests
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Planting, PlantConversation, PlantChatMessage, EcoCrop
from pipeline.advisor import DEFAULT_FREE_MODELS

def get_or_create_conversation(planting_id: str, db: Session) -> PlantConversation:
    conv = db.query(PlantConversation).filter(PlantConversation.planting_id == planting_id).first()
    if not conv:
        conv = PlantConversation(planting_id=planting_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def chat_with_advisor(planting: Planting, user_message: str, db: Session) -> str:
    """Provide grounded answers using planting timeline, active stage, and chat history."""
    conv = get_or_create_conversation(planting.id, db)
    
    # Save user message
    user_msg_record = PlantChatMessage(
        conversation_id=conv.id,
        role="user",
        content=user_message,
    )
    db.add(user_msg_record)
    db.commit()

    # Build context
    crop = db.query(EcoCrop).filter(EcoCrop.EcoPortCode == planting.ecoport_code).first()
    crop_name = crop.ScientificName if crop else f"Crop #{planting.ecoport_code}"
    common_name = crop.COMNAME if crop and crop.COMNAME else crop_name
    category = crop.CAT if crop and crop.CAT else "Crop"
    
    days_elapsed = (date.today() - planting.planting_date).days
    
    # Determine current stage from active plan
    active_plan = planting.plans[0] if planting.plans else None
    current_stage_info = "Initial establishment"
    plan_summary = "N/A"
    upcoming_tasks = []
    
    if active_plan:
        plan_summary = active_plan.summary
        for stage in active_plan.stages:
            if stage.start_day <= days_elapsed <= stage.end_day:
                current_stage_info = f"Stage {stage.stage_order}: {stage.stage_name} (Days {stage.start_day}-{stage.end_day})"
                for task in stage.care_tasks:
                    if not task.is_completed:
                        upcoming_tasks.append(f"{task.task_name} ({task.frequency})")
                break

    # Recent observations
    obs_notes = [f"- {obs.observation_date}: {obs.note}" for obs in planting.observations[:3]]
    obs_summary = "\n".join(obs_notes) if obs_notes else "None recorded yet."

    system_prompt = f"""You are the PlantMyPlanet AI Botanical Advisor for a specific plant.
You are helping the user care for their plant based on real garden records.

### PLANT CONTEXT:
- Plant: {common_name} ({crop_name})
- Category: {category}
- Growing Scale: {planting.growing_scale}
- Location: Lat {planting.latitude}, Lon {planting.longitude}
- Planting Date: {planting.planting_date} ({days_elapsed} days elapsed)
- Current Stage: {current_stage_info}
- Active Plan Summary: {plan_summary}
- Upcoming Care Activities: {", ".join(upcoming_tasks) if upcoming_tasks else "Regular maintenance"}
- Recent User Observations:
{obs_summary}

### INSTRUCTIONS:
1. Provide practical, supportive, and scientifically sound gardening advice.
2. Relate your response to the plant's actual elapsed age ({days_elapsed} days) and current stage ({current_stage_info}).
3. Address symptoms, watering, nutrition, sunlight, or pest issues clearly and concisely.
4. Keep tone enthusiastic, clear, and reassuring.
"""

    # Fetch recent conversation history
    past_messages = (
        db.query(PlantChatMessage)
        .filter(PlantChatMessage.conversation_id == conv.id)
        .order_by(PlantChatMessage.created_at.asc())
        .all()
    )
    
    # Take last 6 turns (excluding the current user message just inserted)
    chat_history_payload = []
    for m in past_messages[-8:-1]:
        chat_history_payload.append({"role": m.role, "content": m.content})
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history_payload)
    messages.append({"role": "user", "content": user_message})

    # Call OpenRouter with fallback
    reply = None
    if settings.OPENROUTER_API_KEY:
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/planttheplanet",
            "X-Title": "PlantMyPlanet Advisor",
        }
        url = "https://openrouter.ai/api/v1/chat/completions"
        for model in DEFAULT_FREE_MODELS:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.6,
            }
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=25)
                if resp.status_code == 200:
                    reply = resp.json()["choices"][0]["message"]["content"].strip()
                    break
            except Exception:
                continue

    if not reply:
        reply = (
            f"Based on your {common_name} at Day {days_elapsed} ({current_stage_info}), "
            f"ensure the soil remains consistently moist and receives adequate sunlight. "
            f"For {planting.growing_scale}, keep an eye out for balanced nutrition and good drainage!"
        )

    # Save assistant response
    assistant_msg = PlantChatMessage(
        conversation_id=conv.id,
        role="assistant",
        content=reply,
    )
    db.add(assistant_msg)
    db.commit()
    return reply
