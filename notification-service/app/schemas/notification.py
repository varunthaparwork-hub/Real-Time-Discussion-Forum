"""
Shapes of the data the notification API sends back to the frontend.
Pydantic validates these so the frontend always gets a consistent format.
"""
from datetime import datetime
from pydantic import BaseModel

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: str
    title: str
    message: str
    thread_id: int | None
    comment_id: int | None
    action_user_id: int | None
    is_read: bool
    created_at: datetime


class MarkReadResponse(BaseModel):
    message:str