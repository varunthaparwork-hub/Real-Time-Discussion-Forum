# Shapes of the data for comment requests and responses.
# Input fields are sanitized to strip HTML/script tags (XSS prevention).
from datetime import datetime
from pydantic import BaseModel, field_validator
from app.core.sanitizer import sanitize_rich_text

class CommentCreate(BaseModel):
    content: str
    thread_id: int
    parent_id: int| None = None

    @field_validator("content")
    @classmethod
    def clean_content(cls, v: str) -> str:
        cleaned = sanitize_rich_text(v)
        if not cleaned:
            raise ValueError("Comment content cannot be empty")
        return cleaned

class CommentUpdate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def clean_content(cls, v: str) -> str:
        cleaned = sanitize_rich_text(v)
        if not cleaned:
            raise ValueError("Comment content cannot be empty")
        return cleaned

class CommentResponse(BaseModel):
    id: int
    content: str
    username: str
    avatar: str | None = None
    thread_id: int
    parent_id: int | None
    created_at: datetime
