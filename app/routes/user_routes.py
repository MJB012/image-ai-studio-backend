from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user
from app.schemas.user_schema import UserResponse, UserUpdateRequest
from app.services.user_service import update_user

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user["_id"]),
        full_name=current_user["full_name"],
        email=current_user["email"],
        profile_url=current_user.get("profile_url"),
        auth_provider=current_user["auth_provider"],
    )


@router.put("/me", response_model=UserResponse)
async def update_profile(
    request: UserUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    updates = request.model_dump(exclude_none=True)
    if updates:
        await update_user(str(current_user["_id"]), updates)
        current_user.update(updates)

    return UserResponse(
        id=str(current_user["_id"]),
        full_name=current_user["full_name"],
        email=current_user["email"],
        profile_url=current_user.get("profile_url"),
        auth_provider=current_user["auth_provider"],
    )
