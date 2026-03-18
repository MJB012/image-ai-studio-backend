from datetime import datetime, timezone
from bson import ObjectId
from app.database.mongodb import database


async def save_image(
    user_id: str,
    prompt: str,
    image_url: str,
    public_id: str,
) -> dict:
    """Save a generated image record to the database."""
    doc = {
        "user_id": ObjectId(user_id),
        "prompt": prompt,
        "image_url": image_url,
        "public_id": public_id,
        "created_at": datetime.now(timezone.utc),
    }
    result = await database.images.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_images_by_user(user_id: str, skip: int = 0, limit: int = 50) -> list[dict]:
    """Get all images for a user, newest first."""
    cursor = (
        database.images.find({"user_id": ObjectId(user_id)})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def get_image_by_id(image_id: str, user_id: str) -> dict | None:
    """Get a single image by ID, scoped to the user."""
    return await database.images.find_one({
        "_id": ObjectId(image_id),
        "user_id": ObjectId(user_id),
    })


async def delete_image(image_id: str, user_id: str) -> dict | None:
    """Delete an image by ID, scoped to the user. Returns the doc before deletion."""
    return await database.images.find_one_and_delete({
        "_id": ObjectId(image_id),
        "user_id": ObjectId(user_id),
    })


async def get_image_count(user_id: str) -> int:
    """Get total image count for a user."""
    return await database.images.count_documents({"user_id": ObjectId(user_id)})
