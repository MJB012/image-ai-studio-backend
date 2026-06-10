import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.schemas.image_schema import (
    GenerateImageRequest,
    GenerateImageResponse,
    ImageResponse,
    ImageListResponse,
)
from app.services.gemini_service import generate_image, RateLimitedError
from app.services.cloudinary_service import upload_image, delete_image as delete_cloudinary_image
from app.services.image_service import (
    save_image,
    get_images_by_user,
    get_image_by_id,
    delete_image,
    get_image_count,
)

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_ASPECT_RATIOS = {
    "1:1", "1:4", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9",
}


@router.post("/generate", response_model=GenerateImageResponse)
async def generate(
    request: GenerateImageRequest,
    current_user: dict = Depends(get_current_user),
):
    if request.aspect_ratio not in VALID_ASPECT_RATIOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid aspect ratio. Supported: {', '.join(sorted(VALID_ASPECT_RATIOS))}",
        )

    # Step 1: Generate image with Gemini
    try:
        image_bytes, response_text = await generate_image(
            prompt=request.prompt,
            reference_image_b64=request.reference_image,
            aspect_ratio=request.aspect_ratio,
        )
    except RateLimitedError as e:
        logger.warning(
            "Gemini rate-limit hit for user %s (retry_after=%ss)",
            current_user["_id"],
            e.retry_after_seconds,
        )
        headers = (
            {"Retry-After": str(e.retry_after_seconds)}
            if e.retry_after_seconds is not None
            else None
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers=headers,
        )
    except ValueError as e:
        logger.error(f"Image generation failed for user {current_user['_id']}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )

    # Step 2: Upload to Cloudinary
    try:
        cloud_result = await upload_image(image_bytes)
    except ValueError as e:
        logger.error(f"Cloudinary upload failed for user {current_user['_id']}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to upload image. Please try again.",
        )

    # Step 3: Save record to MongoDB
    user_id = str(current_user["_id"])
    doc = await save_image(
        user_id=user_id,
        prompt=request.prompt,
        image_url=cloud_result["secure_url"],
        public_id=cloud_result["public_id"],
    )

    logger.info(f"Image generated and uploaded for user {user_id}")

    return GenerateImageResponse(
        id=str(doc["_id"]),
        prompt=doc["prompt"],
        image_url=doc["image_url"],
        response_text=response_text,
        created_at=doc["created_at"].isoformat(),
    )


@router.get("/", response_model=ImageListResponse)
async def list_images(
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["_id"])
    images = await get_images_by_user(user_id, skip=skip, limit=limit)
    total = await get_image_count(user_id)

    return ImageListResponse(
        images=[
            ImageResponse(
                id=str(img["_id"]),
                prompt=img["prompt"],
                image_url=img["image_url"],
                created_at=img["created_at"].isoformat(),
            )
            for img in images
        ],
        total=total,
    )


@router.get("/{image_id}", response_model=ImageResponse)
async def get_image(
    image_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["_id"])
    image = await get_image_by_id(image_id, user_id)

    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    return ImageResponse(
        id=str(image["_id"]),
        prompt=image["prompt"],
        image_url=image["image_url"],
        created_at=image["created_at"].isoformat(),
    )


@router.delete("/{image_id}")
async def remove_image(
    image_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["_id"])
    doc = await delete_image(image_id, user_id)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    # Clean up from Cloudinary
    if doc.get("public_id"):
        try:
            await delete_cloudinary_image(doc["public_id"])
        except Exception as e:
            logger.warning(f"Failed to delete from Cloudinary: {e}")

    return {"message": "Image deleted successfully"}
