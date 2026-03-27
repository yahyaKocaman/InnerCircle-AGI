"""
Profile API — /profile
────────────────────────
User profile management. Profile data enriches agent context,
enabling more personalized council responses.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.domain.models import User, UserProfile
from app.domain.schemas import ProfileCreate, ProfileUpdate, ProfileResponse

router = APIRouter(tags=["Profile"])
logger = logging.getLogger(__name__)


@router.get(
    "/",
    response_model=ProfileResponse,
    summary="Get user profile",
    description="Returns the authenticated user's enrichment profile used by council agents.",
)
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(UserProfile).filter(
        UserProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found. Create one with POST /profile.",
        )
    return profile


@router.post(
    "/",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create profile",
    description="Create an enrichment profile. This data feeds into every agent's context.",
)
def create_profile(
    payload: ProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(UserProfile).filter(
        UserProfile.user_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Profile already exists. Use PUT /profile to update.",
        )

    profile = UserProfile(
        user_id=current_user.id,
        **payload.model_dump(exclude_none=True),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    logger.info(f"Profile created for user {current_user.username}")
    return profile


@router.put(
    "/",
    response_model=ProfileResponse,
    summary="Update profile",
    description="Update enrichment profile. All fields are optional (partial update).",
)
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(UserProfile).filter(
        UserProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Create it first.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    logger.info(f"Profile updated for user {current_user.username}")
    return profile


@router.delete(
    "/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete profile",
)
def delete_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(UserProfile).filter(
        UserProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(profile)
    db.commit()
