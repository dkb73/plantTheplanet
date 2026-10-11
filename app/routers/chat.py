from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Planting, PlantConversation, PlantChatMessage
from app.schemas import ChatMessageCreate, ChatMessageOut
from app.dependencies import get_current_user
from app.services.chat_service import chat_with_advisor, get_or_create_conversation

router = APIRouter(prefix="/plantings/{id}/chat", tags=["Plant AI Chat"])

@router.get("", response_model=List[ChatMessageOut])
def get_chat_history(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    planting = db.query(Planting).filter(Planting.id == id, Planting.user_id == current_user.id).first()
    if not planting:
        raise HTTPException(status_code=404, detail="Planting not found")

    conv = get_or_create_conversation(planting.id, db)
    messages = (
        db.query(PlantChatMessage)
        .filter(PlantChatMessage.conversation_id == conv.id)
        .order_by(PlantChatMessage.created_at.asc())
        .all()
    )
    return messages


@router.post("", response_model=ChatMessageOut)
def send_chat_message(
    id: str,
    data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    planting = db.query(Planting).filter(Planting.id == id, Planting.user_id == current_user.id).first()
    if not planting:
        raise HTTPException(status_code=404, detail="Planting not found")

    reply = chat_with_advisor(planting, data.message, db)

    # Return the latest assistant message
    conv = get_or_create_conversation(planting.id, db)
    latest_msg = (
        db.query(PlantChatMessage)
        .filter(PlantChatMessage.conversation_id == conv.id, PlantChatMessage.role == "assistant")
        .order_by(PlantChatMessage.created_at.desc())
        .first()
    )
    return latest_msg
