import logging
import random
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, status
from pymongo.errors import DuplicateKeyError
from app.enums.auth_provider import AuthProvider
from app.database.mongodb import database
from app.schemas.auth_schema import (
    LoginRequest,
    GoogleSignInRequest,
    AppleSignInRequest,
    RegisterResponse,
    TokenResponse,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    VerifyCodeRequest,
    ResetPasswordRequest,
)
from app.schemas.user_schema import UserRegisterRequest
from app.services.auth_service import (
    hash_password,
    verify_password,
    decode_token,
    generate_login_response,
)
from app.services.user_service import get_user_by_email, get_user_by_id, create_user, update_user
from app.services.google_auth_service import verify_google_token
from app.services.apple_auth_service import verify_apple_token

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
async def register(request: UserRegisterRequest):
    existing = await get_user_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user_data = {
        "full_name": request.full_name,
        "email": request.email,
        "password": hash_password(request.password),
        "profile_url": None,
        "auth_provider": AuthProvider.EMAIL.value,
    }

    try:
        await create_user(user_data)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    logger.info(f"User registered: {request.email}")
    return RegisterResponse(message="User registered successfully")


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    user = await get_user_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.get("auth_provider") != AuthProvider.EMAIL.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"This account uses {user['auth_provider']} sign-in",
        )

    if not verify_password(request.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    logger.info(f"User logged in: {request.email}")
    return generate_login_response(user)


@router.post("/google", response_model=TokenResponse)
async def google_sign_in(request: GoogleSignInRequest):
    try:
        id_info = await verify_google_token(request.id_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {e}",
        )

    email = id_info["email"]
    existing = await get_user_by_email(email)

    if existing:
        if existing.get("auth_provider") != AuthProvider.GOOGLE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Account already exists with {existing['auth_provider']} sign-in",
            )
        logger.info(f"Google sign-in: {email}")
        return generate_login_response(existing)

    user_data = {
        "full_name": id_info.get("name", ""),
        "email": email,
        "password": None,
        "profile_url": id_info.get("picture"),
        "auth_provider": AuthProvider.GOOGLE.value,
    }

    user = await create_user(user_data)
    logger.info(f"New Google user created: {email}")
    return generate_login_response(user)


@router.post("/apple", response_model=TokenResponse)
async def apple_sign_in(request: AppleSignInRequest):
    try:
        payload = await verify_apple_token(request.id_token)
    except (ValueError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Apple token: {e}",
        )

    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not provided by Apple",
        )

    existing = await get_user_by_email(email)

    if existing:
        if existing.get("auth_provider") != AuthProvider.APPLE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Account already exists with {existing['auth_provider']} sign-in",
            )
        logger.info(f"Apple sign-in: {email}")
        return generate_login_response(existing)

    user_data = {
        "full_name": request.full_name or "Apple User",
        "email": email,
        "password": None,
        "profile_url": None,
        "auth_provider": AuthProvider.APPLE.value,
    }

    user = await create_user(user_data)
    logger.info(f"New Apple user created: {email}")
    return generate_login_response(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    try:
        payload = decode_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = payload["sub"]
    user = await get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return generate_login_response(user)


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    user = await get_user_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email",
        )

    code = str(random.randint(100000, 999999))

    await database.password_resets.delete_many({"email": request.email})
    await database.password_resets.insert_one({
        "email": request.email,
        "code": code,
        "created_at": datetime.now(timezone.utc),
    })

    logger.info(f"Password reset code for {request.email}: {code}")
    return {"message": "Verification code sent to your email"}


@router.post("/verify-code")
async def verify_code(request: VerifyCodeRequest):
    record = await database.password_resets.find_one({"email": request.email})
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No verification code found. Please request a new one.",
        )

    if datetime.now(timezone.utc) - record["created_at"] > timedelta(minutes=10):
        await database.password_resets.delete_one({"_id": record["_id"]})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new one.",
        )

    if record["code"] != request.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )

    return {"message": "Code verified successfully"}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    if request.new_password != request.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )

    record = await database.password_resets.find_one({"email": request.email})
    if not record or record["code"] != request.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    if datetime.now(timezone.utc) - record["created_at"] > timedelta(minutes=10):
        await database.password_resets.delete_one({"_id": record["_id"]})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired",
        )

    user = await get_user_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await update_user(str(user["_id"]), {"password": hash_password(request.new_password)})
    await database.password_resets.delete_many({"email": request.email})

    logger.info(f"Password reset successful for {request.email}")
    return {"message": "Password reset successfully"}
