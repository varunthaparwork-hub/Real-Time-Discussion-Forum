# Shapes of the data for like responses (count, status, message).
from pydantic import BaseModel


class LikeResponse(BaseModel):
    message: str

class LikeCountResponse(BaseModel):
    target_id: int
    like_count: int

class LikeStatusResponse(BaseModel):
    has_liked: bool