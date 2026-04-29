# Comment endpoints — post replies on threads, edit, delete.
# Supports nested replies (parent_id) and @mentions.
from typing import List

from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, get_current_auth_user, AuthUser
from app.core.rate_limiter import limiter
from app.db.database import get_db
from app.models.comment import Comment
from app.models.thread import Thread
from app.schemas.comment import CommentCreate, CommentResponse, CommentUpdate
from app.services.auth_client import get_user_map, get_user_role, get_users_by_usernames
from app.services.response_builder import serialize_comment_with_username
from app.services.event_publisher import publish_event
from app.services.mention_parser import extract_usernames
from app.models.like import CommentLike

router = APIRouter(prefix="/comments", tags=["Comments"])


@router.post("/", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("15/minute")
async def create_comment(request: Request, payload: CommentCreate,db: AsyncSession = Depends(get_db),user_id: int = Depends(get_current_user),):
    thread_result = await db.execute(
        select(Thread).where(Thread.id == payload.thread_id)
    )
    thread = thread_result.scalar_one_or_none()

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread Not Found",
        )

    parent_comment = None  # Will be set if this is a reply

    if payload.parent_id is not None:
        parent_result = await db.execute(
            select(Comment).where(Comment.id == payload.parent_id)
        )
        parent_comment = parent_result.scalar_one_or_none()

        if not parent_comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent Comment Not Found"
            )

        if parent_comment.thread_id != payload.thread_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent Comment does not belong to this thread"
            )

    new_comment = Comment(
        content=payload.content,
        user_id=user_id,
        thread_id=payload.thread_id,
        parent_id=payload.parent_id,
    )

    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)

    user_map = await get_user_map([new_comment.user_id])
    actor_username = user_map.get(new_comment.user_id, {}).get("username", "Unknown User")

    # Live Thread event for everyone viewing this thread
    await publish_event({
        "event_type": "comment.created",
        "thread_id" : new_comment.thread_id,
        "comment_id": new_comment.id , 
        "action_user_id": new_comment.user_id,
        "actor_username": actor_username,
        "title": "New Comment",
        "message" : f"{actor_username} added a comment",
    })

    # Notification for the thread owner (skip if commenter owns the thread)
    if thread.user_id != new_comment.user_id:
        await publish_event({
            "event_type": "comment.created",
            "target_user_id": thread.user_id,
            "thread_id": new_comment.thread_id,
            "comment_id": new_comment.id,
            "action_user_id": new_comment.user_id,
            "title": "New comment",
            "message": f"{actor_username} commented on your thread",
        })
    # Reply Notification for parent comment owner (reuse parent_comment from validation above)
    if new_comment.parent_id is not None and parent_comment and parent_comment.user_id != new_comment.user_id:
        await publish_event({
            "event_type": "comment.replied",
            "target_user_id": parent_comment.user_id,
            "thread_id": new_comment.thread_id,
            "comment_id": new_comment.id,
            "action_user_id": new_comment.user_id,
            "title": "New reply",
            "message": f"{actor_username} replied to your comment",
        })

    mentioned_usernames = extract_usernames(new_comment.content)
    mentioned_users = await get_users_by_usernames(mentioned_usernames)

    for mentioned_user in mentioned_users:
        target_user_id = mentioned_user["id"]

        if target_user_id != new_comment.user_id:
            await publish_event({
                "event_type": "comment.mentioned",
                "target_user_id": target_user_id,
                "thread_id": new_comment.thread_id,
                "comment_id": new_comment.id,
                "action_user_id": new_comment.user_id,
                "title": "You were mentioned",
                "message": f"{actor_username} mentioned you in a comment",
            })

    return serialize_comment_with_username(new_comment, user_map)


@router.get("/thread/{thread_id}", response_model=List[CommentResponse])
@limiter.limit("60/minute")
async def get_comments_by_thread(request: Request, thread_id: int, db: AsyncSession = Depends(get_db)):
    thread_result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = thread_result.scalar_one_or_none()

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread Not Found"
        )

    result = await db.execute(
        select(Comment)
        .where(Comment.thread_id == thread_id)
        .order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()

    user_ids = [comment.user_id for comment in comments]
    user_map = await get_user_map(user_ids)

    return [serialize_comment_with_username(comment, user_map) for comment in comments]


@router.get("/{comment_id}", response_model=CommentResponse)
@limiter.limit("60/minute")
async def get_single_comment(request: Request, comment_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment Not Found"
        )

    user_map = await get_user_map([comment.user_id])
    return serialize_comment_with_username(comment, user_map)


@router.put("/{comment_id}", response_model=CommentResponse)
@limiter.limit("10/minute")
async def update_comment(
    request: Request,
    comment_id: int,
    payload: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    auth_user: AuthUser = Depends(get_current_auth_user),
):
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    role = await get_user_role(auth_user.id)

    if comment.user_id != auth_user.id and role not in ('admin', 'moderator'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own comment",
        )

    comment.content = payload.content
    await db.commit()
    await db.refresh(comment)

    user_map = await get_user_map([comment.user_id])
    return serialize_comment_with_username(comment, user_map)


@router.delete("/{comment_id}", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def delete_comment(
    request: Request,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    auth_user: AuthUser = Depends(get_current_auth_user),
):
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment Not Found"
        )

    role = await get_user_role(auth_user.id)

    if comment.user_id != auth_user.id and role not in ('admin', 'moderator'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comment"
        )

    # Collect all descendant comment IDs (recursive tree walk)
    all_ids = []
    queue = [comment_id]
    while queue:
        parent_ids = queue
        child_result = await db.execute(
            select(Comment.id).where(Comment.parent_id.in_(parent_ids))
        )
        child_ids = [row[0] for row in child_result.fetchall()]
        all_ids.extend(parent_ids)
        queue = child_ids

    # Delete likes on all comments in the tree, then the comments themselves
    await db.execute(sql_delete(CommentLike).where(CommentLike.comment_id.in_(all_ids)))
    await db.execute(sql_delete(Comment).where(Comment.id.in_(all_ids)))
    await db.commit()

    return {"message": "Comment deleted successfully"}