import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.domain.models import User
from app.domain.schemas import UserCreate, UserResponse, Token, UserLogin
from app.core.security import hash_password, verify_password, create_access_token
from app.core.limiter import limiter
from app.core.metrics import (
    AUTH_REGISTRATIONS, AUTH_LOGINS, AUTH_FAILURES,
    ACTIVE_USERS_GAUGE, ACTIVE_SESSIONS_GAUGE
)

router = APIRouter(tags=["Authentication"])
logger = logging.getLogger(__name__)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new user account. Password is bcrypt-hashed before storage.",
)
@limiter.limit("5/minute")          # 🔒 Security: max 5 registrations/min per IP
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 📊 Observability: track registrations + total users
    AUTH_REGISTRATIONS.inc()
    ACTIVE_USERS_GAUGE.set(db.query(User).count())

    logger.info(f"New user registered: {user.username}")
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Login and get JWT token",
    description="Validates credentials and returns a Bearer JWT token valid for 24h.",
)
@limiter.limit("10/minute")         # 🔒 Security: brute-force protection
def login(request: Request, payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        AUTH_FAILURES.labels(reason="invalid_credentials").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        AUTH_FAILURES.labels(reason="inactive_account").inc()
        raise HTTPException(status_code=403, detail="Account is inactive")

    token = create_access_token({"sub": user.username})

    AUTH_LOGINS.inc()
    logger.info(f"User logged in: {user.username}")
    return Token(access_token=token, user=UserResponse.model_validate(user))


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Returns the profile of the currently authenticated user.",
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user