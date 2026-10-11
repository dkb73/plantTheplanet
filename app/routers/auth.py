from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserPreference
from app.schemas import UserRegister, UserLogin, UserOut, TokenOut, UserPreferenceOut, UserPreferenceUpdate
from app.security import hash_password, verify_password, create_access_token
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )
    
    user = User(
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.flush()

    # Create default preferences
    pref = UserPreference(
        user_id=user.id,
        growing_scale="home_garden",
        experience_level="beginner",
        preferences={},
    )
    db.add(pref)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id, "email": user.email})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/login", response_model=TokenOut)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    token = create_access_token({"sub": user.id, "email": user.email})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/preferences", response_model=UserPreferenceOut)
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


@router.put("/preferences", response_model=UserPreferenceOut)
def update_preferences(
    data: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)
    
    if data.growing_scale is not None:
        pref.growing_scale = data.growing_scale
    if data.experience_level is not None:
        pref.experience_level = data.experience_level
    if data.preferences is not None:
        pref.preferences = data.preferences
    
    db.commit()
    db.refresh(pref)
    return pref
