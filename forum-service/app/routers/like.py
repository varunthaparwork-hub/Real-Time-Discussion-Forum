# Like / unlike endpoints for threads and comments.
# Each user can only like something once (enforced by DB unique constraint).
from fastapi import APIRouter, status, HTTPException, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.rate_limiter import limiter
from app.db.database import get_db
from app.models.thread import Thread
from app.models.comment import Comment
from app.models.like import ThreadLike, CommentLike
from app.schemas.like import LikeCountResponse, LikeResponse, LikeStatusResponse

from app.services.event_publisher import publish_event
from app.services.auth_client import get_user_map

router = APIRouter(prefix="/likes", tags=["Likes"])


@router.post("/thread/{thread_id}", response_model=LikeResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def like_thread(request: Request, thread_id: int , db: AsyncSession = Depends(get_db) , user_id: int = Depends(get_current_user)):

    thread_result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = thread_result.scalar_one_or_none()

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread Not Found"
        )

    existing_like_result = await db.execute(
        select(ThreadLike).where(
            ThreadLike.thread_id == thread_id,
            ThreadLike.user_id == user_id
        )
    )
    existing_like = existing_like_result.scalar_one_or_none()

    if existing_like:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already liked this thread"
        )

    new_like = ThreadLike(
        user_id=user_id,
        thread_id=thread_id
    )

    db.add(new_like)
    await db.commit()

    # Events are best-effort — don't let failures crash the like response
    try:
        actor_map = await get_user_map([user_id])
        actor_username = actor_map.get(user_id, {}).get("username", "unknown")

        await publish_event({
            "event_type": "thread.liked",
            "thread_id": thread_id,
            "action_user_id": user_id,
            "title": "Thread liked",
            "message": f"{actor_username} liked a thread",
        })

        if thread.user_id != user_id:
            await publish_event({
                "event_type": "thread.like_notification",
                "target_user_id": thread.user_id,
                "thread_id": thread_id,
                "action_user_id": user_id,
                "title": "Your thread was liked",
                "message": f"{actor_username} liked your thread",
            })
    except Exception as e:
        print(f"Like event publish failed (non-critical): {e}")

    return {"message": "Thread liked successfully"}


@router.delete("/thread/{thread_id}", response_model=LikeResponse)
@limiter.limit("20/minute")
async def unlike_thread(
    request: Request,
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    like_result = await db.execute(
        select(ThreadLike).where(
            ThreadLike.thread_id == thread_id,
            ThreadLike.user_id == user_id
        )
    )
    like = like_result.scalar_one_or_none()

    if not like:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Like not found for this thread"
        )

    await db.delete(like)
    await db.commit()

    # Publish unlike event for real-time update
    try:
        await publish_event({
            "event_type": "thread.unliked",
            "thread_id": thread_id,
            "action_user_id": user_id,
        })
    except Exception:
        pass  # Non-critical: DB change succeeded, event is best-effort

    return {"message": "Thread unliked successfully"}


@router.get("/thread/{thread_id}/count", response_model=LikeCountResponse)
@limiter.limit("60/minute")
async def get_thread_like_count(request: Request, thread_id: int, db: AsyncSession = Depends(get_db)):
    thread_result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = thread_result.scalar_one_or_none()

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread Not Found"
        )

    count_result = await db.execute(
        select(func.count(ThreadLike.id)).where(ThreadLike.thread_id == thread_id)
    )
    like_count = count_result.scalar() or 0

    return {
        "target_id": thread_id,
        "like_count": like_count
    }


@router.get("/thread/{thread_id}/status", response_model=LikeStatusResponse)
@limiter.limit("60/minute")
async def get_thread_like_status(
    request: Request,
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    result = await db.execute(
        select(ThreadLike).where(
            ThreadLike.thread_id == thread_id,
            ThreadLike.user_id == user_id
        )
    )
    like = result.scalar_one_or_none()
    return {"has_liked": like is not None}


@router.post("/comment/{comment_id}", response_model=LikeResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def like_comment(
    request: Request,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    comment_result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = comment_result.scalar_one_or_none()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment Not Found"
        )

    existing_like_result = await db.execute(
        select(CommentLike).where(
            CommentLike.comment_id == comment_id,
            CommentLike.user_id == user_id
        )
    )
    existing_like = existing_like_result.scalar_one_or_none()

    if existing_like:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already liked this comment"
        )

    new_like = CommentLike(
        user_id=user_id,
        comment_id=comment_id
    )

    db.add(new_like)
    await db.commit()

    actor_map = await get_user_map([user_id])
    actor_username = actor_map.get(user_id, {}).get("username", "unknown")

    await publish_event({
        "event_type": "comment.liked",
        "thread_id": comment.thread_id,
        "comment_id": comment_id,
        "action_user_id": user_id,
        "title": "Comment liked",
        "message": f"{actor_username} liked a comment",
    })

    if comment.user_id != user_id:
        await publish_event({
            "event_type": "comment.like_notification",
            "target_user_id": comment.user_id,
            "thread_id": comment.thread_id,
            "comment_id": comment_id,
            "action_user_id": user_id,
            "title": "Your comment was liked",
            "message": f"{actor_username} liked your comment",
        })

    return {"message": "Comment liked successfully"}


@router.delete("/comment/{comment_id}", response_model=LikeResponse)
@limiter.limit("20/minute")
async def unlike_comment(
    request: Request,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    like_result = await db.execute(
        select(CommentLike).where(
            CommentLike.comment_id == comment_id,
            CommentLike.user_id == user_id
        )
    )
    like = like_result.scalar_one_or_none()

    if not like:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Like not found for this comment"
        )

    # Fetch the comment to get thread_id for the real-time event
    comment_result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = comment_result.scalar_one_or_none()

    await db.delete(like)
    await db.commit()

    # Publish unlike event for real-time update
    try:
        await publish_event({
            "event_type": "comment.unliked",
            "thread_id": comment.thread_id,
            "comment_id": comment_id,
            "action_user_id": user_id,
        })
    except Exception:
        pass  # Non-critical: DB change succeeded, event is best-effort

    return {"message": "Comment unliked successfully"}


@router.get("/comments/counts", response_model=dict)
@limiter.limit("60/minute")
async def get_batch_comment_like_counts(
    request: Request,
    ids: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Batch endpoint: get like counts for multiple comments in a single query.
    Usage: GET /likes/comments/counts?ids=1,2,3,4
    Returns: { "counts": { "1": 5, "2": 0, ... } }
    """
    if not ids.strip():
        return {"counts": {}}

    try:
        comment_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="ids must be comma-separated integers")

    if not comment_ids:
        return {"counts": {}}

    result = await db.execute(
        select(CommentLike.comment_id, func.count(CommentLike.id))
        .where(CommentLike.comment_id.in_(comment_ids))
        .group_by(CommentLike.comment_id)
    )
    rows = result.all()
    counts = {str(cid): cnt for cid, cnt in rows}

    # Fill zeros for comment_ids with no likes
    for cid in comment_ids:
        counts.setdefault(str(cid), 0)

    return {"counts": counts}


@router.get("/comment/{comment_id}/count", response_model=LikeCountResponse)
@limiter.limit("60/minute")
async def get_comment_like_count(request: Request, comment_id: int, db: AsyncSession = Depends(get_db)):
    comment_result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = comment_result.scalar_one_or_none()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment Not Found"
        )

    count_result = await db.execute(
        select(func.count(CommentLike.id)).where(CommentLike.comment_id == comment_id)
    )
    like_count = count_result.scalar() or 0

    return {
        "target_id": comment_id,
        "like_count": like_count
    }


@router.get("/comment/{comment_id}/status", response_model=LikeStatusResponse)
@limiter.limit("60/minute")
async def get_comment_like_status(
    request: Request,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    result = await db.execute(
        select(CommentLike).where(
            CommentLike.comment_id == comment_id,
            CommentLike.user_id == user_id
        )
    )
    like = result.scalar_one_or_none()
    return {"has_liked": like is not None}


@router.get("/comments/statuses", response_model=dict)
@limiter.limit("60/minute")
async def get_batch_comment_like_statuses(
    request: Request,
    ids: str = "",
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Batch endpoint: get per-user like status for multiple comments.
    Usage: GET /likes/comments/statuses?ids=1,2,3
    Returns: { "statuses": { "1": true, "2": false, ... } }
    """
    if not ids.strip():
        return {"statuses": {}}

    try:
        comment_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="ids must be comma-separated integers")

    if not comment_ids:
        return {"statuses": {}}

    result = await db.execute(
        select(CommentLike.comment_id)
        .where(CommentLike.comment_id.in_(comment_ids), CommentLike.user_id == user_id)
    )
    liked_ids = {row[0] for row in result.fetchall()}

    statuses = {str(cid): cid in liked_ids for cid in comment_ids}
    return {"statuses": statuses}