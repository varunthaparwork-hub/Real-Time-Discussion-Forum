# Thread endpoints — create, read, update, delete discussion threads.
# Also handles search and pagination.
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, get_current_auth_user, AuthUser
from app.core.rate_limiter import limiter
from app.db.database import get_db
from app.models.thread import Thread
from app.schemas.thread import ThreadCreate, ThreadUpdate, ThreadResponse, PaginatedThreadResponse
from app.services.auth_client import get_user_map, get_user_role
from app.services.response_builder import serialize_thread_with_username


router = APIRouter(prefix="/threads", tags=["Threads"])


@router.post("/", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_thread(
    request: Request,
    payload: ThreadCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    new_thread = Thread(
        title=payload.title,
        description=payload.description,
        user_id=user_id,
    )

    db.add(new_thread)
    await db.commit()
    await db.refresh(new_thread)

    user_map = await get_user_map([new_thread.user_id])
    return serialize_thread_with_username(new_thread, user_map)


@router.get("/", response_model=PaginatedThreadResponse)
@limiter.limit("60/minute")
async def get_all_threads(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # Count total
    count_result = await db.execute(select(func.count(Thread.id)))
    total = count_result.scalar() or 0

    offset = (page - 1) * limit
    result = await db.execute(
        select(Thread).order_by(Thread.created_at.desc()).offset(offset).limit(limit)
    )
    threads = result.scalars().all()

    user_ids = [thread.user_id for thread in threads]
    user_map = await get_user_map(user_ids)

    return {
        "threads": [serialize_thread_with_username(thread, user_map) for thread in threads],
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit,
    }


@router.get("/search", response_model=List[ThreadResponse])
@limiter.limit("30/minute")
async def search_threads(request: Request, q: str = "", db: AsyncSession = Depends(get_db)):
    if not q.strip():
        return []

    result = await db.execute(
        select(Thread)
        .where(
            or_(
                Thread.title.ilike(f"%{q}%"),
                Thread.description.ilike(f"%{q}%"),
            )
        )
        .order_by(Thread.created_at.desc())
    )
    threads = result.scalars().all()

    user_ids = [thread.user_id for thread in threads]
    user_map = await get_user_map(user_ids)

    return [serialize_thread_with_username(thread, user_map) for thread in threads]


@router.get("/{thread_id}", response_model=ThreadResponse)
@limiter.limit("60/minute")
async def get_single_thread(request: Request, thread_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    user_map = await get_user_map([thread.user_id])
    return serialize_thread_with_username(thread, user_map)


@router.put("/{thread_id}", response_model=ThreadResponse)
@limiter.limit("10/minute")
async def update_thread(
    request: Request,
    thread_id: int,
    payload: ThreadUpdate,
    db: AsyncSession = Depends(get_db),
    auth_user: AuthUser = Depends(get_current_auth_user),
):
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    # Fetch role from auth service for accurate role check
    role = await get_user_role(auth_user.id)

    if thread.user_id != auth_user.id and role not in ('admin', 'moderator'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own thread",
        )

    if payload.title is not None:
        thread.title = payload.title

    if payload.description is not None:
        thread.description = payload.description

    await db.commit()
    await db.refresh(thread)

    user_map = await get_user_map([thread.user_id])
    return serialize_thread_with_username(thread, user_map)


@router.delete("/{thread_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def delete_thread(
    request: Request,
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    auth_user: AuthUser = Depends(get_current_auth_user),
):
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    role = await get_user_role(auth_user.id)

    if thread.user_id != auth_user.id and role not in ('admin', 'moderator'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own thread",
        )

    # Just delete the thread — PostgreSQL FK CASCADE automatically removes:
    #   • All thread_likes for this thread
    #   • All comments on this thread
    #   • All comment_likes on those comments
    #   • All nested replies (comments with parent_id pointing to deleted comments)
    await db.delete(thread)
    await db.commit()

    return {"message": "Thread deleted successfully"}