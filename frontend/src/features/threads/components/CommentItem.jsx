// A single comment on a thread — handles editing, deleting, liking, and replying.
// Renders nested replies recursively (comment within a comment).
import { useState, memo } from "react";
import { useNavigate } from "react-router-dom";
import useAuthStore from "../../auth/store/authStore";
import {
  updateComment,
  deleteComment,
  likeComment,
  unlikeComment,
} from "../../../api/forumApi";

function RenderContent({ content }) {
  const navigate = useNavigate();
  if (!content) return null;

  const parts = content.split(/(@\w+)/g);
  return parts.map((part, i) => {
    if (part.startsWith("@")) {
      const username = part.slice(1);
      return (
        <span
          key={i}
          className="inline-block cursor-pointer rounded bg-indigo-50 px-1.5 py-0.5 text-sm font-semibold text-indigo-700 transition hover:bg-indigo-100 dark:bg-indigo-900/30 dark:text-indigo-400 dark:hover:bg-indigo-800/40"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            navigate(`/user/${username}`);
          }}
        >
          {part}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function CommentItem({ comment, onReply, onChanged, canModerate, initialLikeCount = 0, initialHasLiked = false }) {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);

  const [replyText, setReplyText] = useState("");
  const [showReplyBox, setShowReplyBox] = useState(false);

  // Edit state
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(comment.content);

  // Like state — initialized from batch data fetched by parent
  const [commentLikeCount, setCommentLikeCount] = useState(initialLikeCount);
  const [hasLikedComment, setHasLikedComment] = useState(initialHasLiked);

  const isOwner = user && comment.username === user.username;

  const handleReplySubmit = (e) => {
    e.preventDefault();
    if (!replyText.trim()) return;
    onReply(comment.id, replyText);
    setReplyText("");
    setShowReplyBox(false);
  };

  const handleEdit = async () => {
    if (!editText.trim()) return;
    try {
      await updateComment(comment.id, { content: editText });
      setEditing(false);
      onChanged?.();
    } catch (error) {
      console.error("Edit comment error:", error);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("Delete this comment?")) return;
    try {
      await deleteComment(comment.id);
      onChanged?.();
    } catch (error) {
      console.error("Delete comment error:", error);
    }
  };

  const handleLikeComment = async () => {
    if (!user) {
      navigate("/login");
      return;
    }
    try {
      if (hasLikedComment) {
        await unlikeComment(comment.id);
        setCommentLikeCount((p) => Math.max(0, p - 1));
        setHasLikedComment(false);
      } else {
        await likeComment(comment.id);
        setCommentLikeCount((p) => p + 1);
        setHasLikedComment(true);
      }
    } catch {
      // may already be liked/unliked
    }
  };

  return (
    <div className="group rounded-lg border border-gray-200 bg-white p-4 transition-all duration-200 hover:border-gray-300 hover:shadow-sm dark:border-gray-700 dark:bg-gray-800 dark:hover:border-gray-600">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          {comment.avatar ? (
            <img
              src={comment.avatar}
              alt=""
              className="h-8 w-8 shrink-0 rounded-full object-cover dark:ring-gray-700"
            />
          ) : (
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
              {comment.username?.charAt(0).toUpperCase()}
            </div>
          )}
          <div className="flex items-center gap-2">
            <span className="font-semibold text-gray-900 dark:text-white">{comment.username}</span>
            {comment.created_at && (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                · {new Date(comment.created_at).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>

        {/* Edit/Delete buttons */}
        {(isOwner || canModerate) && !editing && (
          <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            {(isOwner || canModerate) && (
              <button
                onClick={() => { setEditText(comment.content); setEditing(true); }}
                className="rounded-md p-1 text-gray-400 transition hover:bg-indigo-50 hover:text-indigo-600 dark:hover:bg-indigo-900/20 dark:hover:text-indigo-400"
                title="Edit"
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </button>
            )}
            <button
              onClick={handleDelete}
              className="rounded-md p-1 text-gray-400 transition hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20 dark:hover:text-red-400"
              title="Delete"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        )}
      </div>

      {/* Content or Edit form */}
      {editing ? (
        <div className="mt-2 pl-10">
          <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            className="w-full border border-gray-300 p-2.5 rounded-md text-sm transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            rows={2}
          />
          <div className="mt-2 flex gap-2">
            <button onClick={handleEdit} className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-500">
              Save
            </button>
            <button onClick={() => setEditing(false)} className="rounded-md border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-500 transition hover:bg-gray-100 dark:border-gray-600 dark:text-gray-400 dark:hover:bg-gray-700">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-2 pl-10 text-sm text-gray-600 dark:text-gray-300">
          <RenderContent content={comment.content} />
        </div>
      )}

      {/* Actions row — like + reply */}
      <div className="mt-2 pl-10 flex items-center gap-3">
        <button
          onClick={handleLikeComment}
          className={`flex items-center gap-1 text-xs font-medium transition ${
            hasLikedComment
              ? "text-rose-500"
              : "text-gray-400 hover:text-rose-500 dark:text-gray-500 dark:hover:text-rose-400"
          }`}
        >
          {hasLikedComment ? "❤️" : "🤍"} {commentLikeCount > 0 && commentLikeCount}
        </button>

        <button
          onClick={() => {
            if (!user) { navigate("/login"); return; }
            setShowReplyBox(!showReplyBox);
          }}
          className="text-indigo-600 dark:text-indigo-400 text-xs font-medium opacity-0 transition-opacity group-hover:opacity-100 hover:underline"
        >
          ↩ Reply
        </button>
      </div>

      {showReplyBox && user && (
        <form onSubmit={handleReplySubmit} className="mt-3 pl-10">
          <textarea
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            className="w-full border border-gray-300 p-2.5 rounded-md text-sm transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            placeholder="Write a reply... Use @username to mention someone"
            rows={2}
          />
          <div className="mt-2 flex items-center gap-2">
            <button type="submit" className="bg-indigo-600 text-white px-4 py-1.5 rounded-md text-sm font-medium hover:bg-indigo-500 transition">
              Reply
            </button>
            <button type="button" onClick={() => setShowReplyBox(false)} className="px-3 py-1.5 rounded-md text-sm font-medium text-gray-500 hover:bg-gray-100 transition dark:text-gray-400 dark:hover:bg-gray-700">
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default memo(CommentItem);