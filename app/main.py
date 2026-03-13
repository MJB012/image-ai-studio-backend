from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routes import user_routes, auth_routes
from app.database.mongodb import connect_to_mongo, close_mongo_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(title="Image AI Studio Backend", lifespan=lifespan)

app.include_router(auth_routes.router, prefix="/auth", tags=["Auth"])
app.include_router(user_routes.router, prefix="/users", tags=["Users"])

@app.get("/")
async def home():
    return {"message": "Image AI Studio Backend Running"}