"""
Notification REST API — lets users fetch and manage their notifications.
  GET  /notifications/              → get my notifications (newest first)
  PATCH /notifications/{id}/read    → mark one as read
  PATCH /notifications/read-all     → mark all as read
"""
from fastapi import APIRouter , Depends , HTTPException , Request , status
from sqlalchemy import select , update
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.auth import get_current_user_id
from app.db.database import get_db
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse , MarkReadResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])

limiter = Limiter(key_func=get_remote_address)


@router.get("/", response_model=list[NotificationResponse])
@limiter.limit("30/minute")
async def get_my_notifications(request: Request, db: AsyncSession = Depends(get_db) , user_id: int = Depends(get_current_user_id),):

    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )

    notifications = result.scalars().all()
    return notifications


@router.patch("/{notification_id}/read", response_model=MarkReadResponse)
@limiter.limit("30/minute")
async def mark_notification_as_read(request: Request, notification_id: int , db: AsyncSession = Depends(get_db) , user_id: int = Depends(get_current_user_id),):
    
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    notification.is_read = True
    await db.commit()

    return {"message": "Notification marked as read"}


@router.patch("/read-all", response_model=MarkReadResponse)
@limiter.limit("10/minute")
async def mark_all_notifications_read(request: Request, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.commit()
    return {"message": "All notifications marked as read"}