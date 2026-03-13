from datetime import datetime, timezone
from bson import ObjectId
from app.database.mongodb import database


async def get_user_by_email(email: str) -> dict | None:
    return await database.users.find_one({"email": email})


async def get_user_by_id(user_id: str) -> dict | None:
    return await database.users.find_one({"_id": ObjectId(user_id)})


async def get_user_by_provider(provider: str, provider_uid: str) -> dict | None:
    return await database.users.find_one({
        "auth_provider": provider,
        "provider_uid": provider_uid,
    })


async def create_user(user_data: dict) -> dict:
    user_data["created_at"] = datetime.now(timezone.utc)
    user_data["updated_at"] = datetime.now(timezone.utc)
    result = await database.users.insert_one(user_data)
    user_data["_id"] = result.inserted_id
    return user_data


async def update_user(user_id: str, updates: dict) -> None:
    updates["updated_at"] = datetime.now(timezone.utc)
    await database.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": updates},
    )
