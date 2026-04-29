"""
Response builder — enriches raw database rows with user info.
The database only stores user_id (a number). This module attaches
the actual username and avatar so the frontend can display
"Posted by varun" instead of "Posted by user #5".
"""
from app.models.thread import Thread
from app.models.comment import Comment


# Takes a thread from the database and adds the author's name + avatar
def serialize_thread_with_username(thread: Thread , user_map: dict[int , dict]) -> dict:
    user_data = user_map.get(thread.user_id , {})
    return {
        "id" : thread.id,
        "title" : thread.title,
        "description" : thread.description,
        "username" : user_data.get("username", "unknown") if isinstance(user_data, dict) else user_data,
        "avatar" : user_data.get("avatar") if isinstance(user_data, dict) else None,
        "created_at" : thread.created_at
    }

def serialize_comment_with_username(comment: Comment , user_map: dict[int , dict]) -> dict:
    user_data = user_map.get(comment.user_id , {})
    return {
        "id" : comment.id,
        "content" : comment.content,
        "username" : user_data.get("username", "unknown") if isinstance(user_data, dict) else user_data,
        "avatar" : user_data.get("avatar") if isinstance(user_data, dict) else None,
        "thread_id" : comment.thread_id,
        "parent_id" : comment.parent_id,
        "created_at" : comment.created_at
    }