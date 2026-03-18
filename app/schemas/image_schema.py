from typing import Optional
from pydantic import BaseModel, Field


class GenerateImageRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    reference_image: Optional[str] = None  # base64-encoded image
    aspect_ratio: str = "1:1"


class GenerateImageResponse(BaseModel):
    id: str
    prompt: str
    image_url: str
    response_text: Optional[str] = None
    created_at: str


class ImageResponse(BaseModel):
    id: str
    prompt: str
    image_url: str
    created_at: str


class ImageListResponse(BaseModel):
    images: list[ImageResponse]
    total: int
