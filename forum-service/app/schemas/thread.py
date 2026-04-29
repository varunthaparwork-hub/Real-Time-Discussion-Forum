# Shapes of the data for thread requests and responses.
# Pydantic validates these automatically.
# Input fields are sanitized to strip HTML/script tags (XSS prevention).
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from app.core.sanitizer import sanitize_text, sanitize_rich_text

class ThreadCreate(BaseModel):
    title: str
    description: str

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        cleaned = sanitize_text(v)
        if not cleaned:
            raise ValueError("Title cannot be empty")
        return cleaned

    @field_validator("description")
    @classmethod
    def clean_description(cls, v: str) -> str:
        cleaned = sanitize_rich_text(v)
        if not cleaned:
            raise ValueError("Description cannot be empty")
        return cleaned
    

class ThreadUpdate(BaseModel):
    title: str| None = None
    description: str| None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cleaned = sanitize_text(v)
        if not cleaned:
            raise ValueError("Title cannot be empty")
        return cleaned

    @field_validator("description")
    @classmethod
    def clean_description(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cleaned = sanitize_rich_text(v)
        if not cleaned:
            raise ValueError("Description cannot be empty")
        return cleaned
    

class ThreadResponse(BaseModel):
    id: int
    title: str
    description: str
    username: str
    avatar: str | None = None
    created_at: datetime


class PaginatedThreadResponse(BaseModel):
    threads: list[ThreadResponse]
    total: int
    page: int
    limit: int
    total_pages: int