import logging
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = AsyncIOMotorClient(settings.MONGO_URL)

database = client["image_ai_studio_db"]


async def connect_to_mongo():
    try:
        await client.admin.command("ping")
        logger.info("Successfully connected to MongoDB")
        await database.users.create_index("email", unique=True)
        logger.info("Database indexes ensured")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    client.close()
    logger.info("MongoDB connection closed")
