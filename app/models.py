import uuid
from datetime import datetime, timezone, date
from sqlalchemy import (
    Column,
    String,
    Integer,
    SmallInteger,
    Float,
    Numeric,
    Boolean,
    Text,
    Date,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    preferences = relationship("UserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    plantings = relationship("Planting", back_populates="user", cascade="all, delete-orphan")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    growing_scale = Column(String(50), default="home_garden")
    experience_level = Column(String(50), default="beginner")
    preferences = Column(JSON, default=dict)

    user = relationship("User", back_populates="preferences")


class EcoCrop(Base):
    __tablename__ = "ecocrop"

    EcoPortCode = Column("EcoPortCode", Integer, primary_key=True)
    ScientificName = Column("ScientificName", Text, nullable=False)
    COMNAME = Column("COMNAME", Text)
    CAT = Column("CAT", Text)
    LIFO = Column("LIFO", Text)
    TOPMN = Column("TOPMN", SmallInteger)
    TOPMX = Column("TOPMX", SmallInteger)
    TMIN = Column("TMIN", SmallInteger)
    TMAX = Column("TMAX", SmallInteger)
    ROPMN = Column("ROPMN", SmallInteger)
    ROPMX = Column("ROPMX", SmallInteger)
    RMIN = Column("RMIN", SmallInteger)
    RMAX = Column("RMAX", SmallInteger)
    PHOPMN = Column("PHOPMN", Numeric(4, 1))
    PHOPMX = Column("PHOPMX", Numeric(4, 1))
    PHMIN = Column("PHMIN", Numeric(4, 1))
    PHMAX = Column("PHMAX", Numeric(4, 1))
    ALTMX = Column("ALTMX", SmallInteger)
    TEXT = Column("TEXT", Text)
    DRA = Column("DRA", Text)
    FER = Column("FER", Text)
    LIOPMN = Column("LIOPMN", Text)
    GMIN = Column("GMIN", SmallInteger)
    GMAX = Column("GMAX", SmallInteger)


class Planting(Base):
    __tablename__ = "plantings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ecoport_code = Column(Integer, ForeignKey("ecocrop.EcoPortCode"), nullable=False)
    planting_date = Column(Date, nullable=False, default=date.today)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    growing_scale = Column(String(50), default="home_garden", nullable=False)
    status = Column(String(50), default="active", nullable=False)  # active, completed, archived
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="plantings")
    crop = relationship("EcoCrop")
    plans = relationship("PlantPlan", back_populates="planting", cascade="all, delete-orphan", order_by="desc(PlantPlan.version)")
    observations = relationship("PlantObservation", back_populates="planting", cascade="all, delete-orphan", order_by="desc(PlantObservation.created_at)")
    conversation = relationship("PlantConversation", back_populates="planting", uselist=False, cascade="all, delete-orphan")


class PlantPlan(Base):
    __tablename__ = "plant_plans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    planting_id = Column(String(36), ForeignKey("plantings.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    status = Column(String(50), default="ready", nullable=False)  # pending, ready, failed
    summary = Column(Text, default="")
    estimated_total_days = Column(Integer, default=90)
    estimated_harvest_date = Column(Date, nullable=True)
    risks_and_precautions = Column(JSON, default=list)
    raw_plan_data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    planting = relationship("Planting", back_populates="plans")
    stages = relationship("PlantPlanStage", back_populates="plan", cascade="all, delete-orphan", order_by="PlantPlanStage.stage_order")


class PlantPlanStage(Base):
    __tablename__ = "plant_plan_stages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    plan_id = Column(String(36), ForeignKey("plant_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_order = Column(Integer, nullable=False)
    stage_name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    start_day = Column(Integer, nullable=False)
    end_day = Column(Integer, nullable=False)
    milestones = Column(JSON, default=list)
    is_completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    plan = relationship("PlantPlan", back_populates="stages")
    care_tasks = relationship("CareTask", back_populates="stage", cascade="all, delete-orphan")


class CareTask(Base):
    __tablename__ = "care_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    stage_id = Column(String(36), ForeignKey("plant_plan_stages.id", ondelete="CASCADE"), nullable=False, index=True)
    task_name = Column(String(150), nullable=False)
    frequency = Column(String(50), default="daily")
    description = Column(Text, default="")
    is_completed = Column(Boolean, default=False, nullable=False)

    stage = relationship("PlantPlanStage", back_populates="care_tasks")


class PlantObservation(Base):
    __tablename__ = "plant_observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    planting_id = Column(String(36), ForeignKey("plantings.id", ondelete="CASCADE"), nullable=False, index=True)
    observation_date = Column(Date, default=date.today, nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    planting = relationship("Planting", back_populates="observations")


class PlantConversation(Base):
    __tablename__ = "plant_conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    planting_id = Column(String(36), ForeignKey("plantings.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    planting = relationship("Planting", back_populates="conversation")
    messages = relationship("PlantChatMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="PlantChatMessage.created_at")


class PlantChatMessage(Base):
    __tablename__ = "plant_chat_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("plant_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    conversation = relationship("PlantConversation", back_populates="messages")
