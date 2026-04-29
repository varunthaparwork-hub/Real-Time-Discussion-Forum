// Thread detail page — shows a full thread with all its comments.
// Connects to the WebSocket for real-time updates (new comments, likes).
// Users can post comments, reply to comments, and like/unlike.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  createComment,
  getCommentsByThread,
  getThreadById,
  likeThread,
  unlikeThread,
  getThreadLikeCount,
  getThreadLikeStatus,
  updateThread,
  deleteThread,
  getBatchCommentLikeCounts,
  getBatchCommentLikeStatuses,
} from "../../../api/forumApi";
import CommentItem from "../components/CommentItem";
import useAuthStore from "../../auth/store/authStore";
import useNotificationStore from "../../notifications/store/notificationStore";

export default function ThreadDetailPage() {
  const { threadId } = useParams();
  const navigate = useNavigate();

  const user = useAuthStore((state) => state.user);

  const [thread, setThread] = useState(null);
  const [comments, setComments] = useState([]);
  const [newComment, setNewComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [likeCount, setLikeCount] = useState(0);
  const [hasLiked, setHasLiked] = useState(false);
  const [commentLikeCounts, setCommentLikeCounts] = useState({});  // { commentId: count }
  const [commentLikeStatuses, setCommentLikeStatuses] = useState({});  // { commentId: true/false }

  // Edit thread state
  const [editingThread, setEditingThread] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");

  const subscribeThread = useNotificationStore((state) => state.subscribeThread);
  const unsubscribeThread = useNotificationStore((state) => state.unsubscribeThread);

  const isOwner = user && thread && thread.username === user.username;
  const canModerate = user && (user.role === "admin" || user.role === "moderator");

  const fetchThreadData = async () => {
    try {
      const token = localStorage.getItem("accessToken");
      const promises = [
        getThreadById(threadId),
        getCommentsByThread(threadId),
        getThreadLikeCount(threadId),
      ];

      if (token) {
        promises.push(getThreadLikeStatus(threadId));
      }

      const results = await Promise.all(promises);

      setThread(results[0]);
      setComments(results[1]);
      setLikeCount(results[2].like_count);

      if (token && results[3]) {
        setHasLiked(results[3].has_liked);
      }

      // Batch-fetch all comment like counts in ONE request
      const commentIds = results[1].map((c) => c.id);
      if (commentIds.length > 0) {
        try {
          const likeData = await getBatchCommentLikeCounts(commentIds);
          setCommentLikeCounts(likeData.counts || {});
        } catch {
          // non-critical
        }

        // Batch-fetch per-user like statuses (only if logged in)
        if (token) {
          try {
            const statusData = await getBatchCommentLikeStatuses(commentIds);
            setCommentLikeStatuses(statusData.statuses || {});
          } catch {
            // non-critical
          }
        }
      }
    } catch (error) {
      console.error("Error loading thread details:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchThreadData();
  }, [threadId]);

  // Subscribe to thread updates via the shared WebSocket
  useEffect(() => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;

    const handleThreadEvent = (data) => {
      if (data.event_type === "comment.created") {
        fetchThreadData();
      }
      if (data.event_type === "thread.liked" || data.event_type === "thread.unliked") {
        getThreadLikeCount(threadId).then((res) => {
          setLikeCount(res.like_count);
        }).catch(() => {});
      }
      if (data.event_type === "comment.liked" || data.event_type === "comment.unliked") {
        // Re-fetch all comment like counts so every viewer sees the update
        const commentIds = comments.map((c) => c.id);
        if (commentIds.length > 0) {
          getBatchCommentLikeCounts(commentIds).then((res) => {
            setCommentLikeCounts(res.counts || {});
          }).catch(() => {});
        }
      }
    };

    subscribeThread(Number(threadId), handleThreadEvent);

    return () => {
      unsubscribeThread(Number(threadId));
    };
  }, [threadId, comments, subscribeThread, unsubscribeThread]);

  const rootComments = useMemo(() => {
    return comments.filter((c) => c.parent_id === null);
  }, [comments]);

  const repliesMap = useMemo(() => {
    const map = {};
    comments.forEach((c) => {
      if (c.parent_id !== null) {
        if (!map[c.parent_id]) map[c.parent_id] = [];
        map[c.parent_id].push(c);
      }
    });
    return map;
  }, [comments]);

  const handleAddComment = async (e) => {
    e.preventDefault();

    if (!user) {
      navigate("/login");
      return;
    }

    if (!newComment.trim()) return;

    try {
      await createComment({
        content: newComment,
        thread_id: Number(threadId),
        parent_id: null,
      });

      setNewComment("");
      fetchThreadData();
    } catch (error) {
      console.error(error);
    }
  };

  const handleLike = async () => {
    if (!user) {
      navigate("/login");
      return;
    }

    try {
      if (hasLiked) {
        await unlikeThread(threadId);
        setHasLiked(false);
        setLikeCount((prev) => Math.max(0, prev - 1));
      } else {
        await likeThread(threadId);
        setHasLiked(true);
        setLikeCount((prev) => prev + 1);
      }
    } catch (error) {
      console.error("Like error:", error);
    }
  };

  const handleReply = async (parentId, content) => {
    if (!user) {
      navigate("/login");
      return;
    }

    try {
      await createComment({
        content,
        thread_id: Number(threadId),
        parent_id: parentId,
      });

      fetchThreadData();
    } catch (error) {
      console.error(error);
    }
  };

  const handleEditThread = () => {
    setEditTitle(thread.title);
    setEditDescription(thread.description);
    setEditingThread(true);
  };

  const handleSaveThread = async () => {
    try {
      const updated = await updateThread(threadId, {
        title: editTitle,
        description: editDescription,
      });
      setThread(updated);
      setEditingThread(false);
    } catch (error) {
      console.error("Edit thread error:", error);
    }
  };

  const handleDeleteThread = async () => {
    if (!window.confirm("Are you sure you want to delete this thread?")) return;
    try {
      await deleteThread(threadId);
      navigate("/");
    } catch (error) {
      console.error("Delete thread error:", error);
    }
  };

  const handleCommentChanged = useCallback(() => {
    fetchThreadData();
  }, [threadId]);

  const handleReplyStable = useCallback(handleReply, [threadId, user]);

  // Recursive comment renderer — unlimited depth
  const renderComments = (commentList, depth = 0) => {
    return commentList.map((c) => (
      <div key={c.id}>
        <CommentItem
          comment={c}
          onReply={handleReplyStable}
          onChanged={handleCommentChanged}
          canModerate={canModerate}
          initialLikeCount={commentLikeCounts[String(c.id)] ?? 0}
          initialHasLiked={commentLikeStatuses[String(c.id)] ?? false}
        />
        {repliesMap[c.id] && repliesMap[c.id].length > 0 && (
          <div
            className="mt-3 border-l-2 border-gray-200 pl-4 space-y-3 dark:border-gray-700"
            style={{ marginLeft: Math.min(depth * 8 + 32, 64) }}
          >
            {renderComments(repliesMap[c.id], depth + 1)}
          </div>
        )}
      </div>
    ));
  };

  if (loading) return <div className="flex min-h-[60vh] items-center justify-center text-gray-500 dark:text-gray-400">Loading...</div>;
  if (!thread) return <div className="flex min-h-[60vh] items-center justify-center text-gray-500 dark:text-gray-400">Thread not found</div>;

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* THREAD */}
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 mb-6 dark:bg-gray-800 dark:border-gray-700">
        {editingThread ? (
          <div className="space-y-3">
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              className="w-full rounded-md border border-gray-300 p-3 text-lg font-bold transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
            <textarea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              rows={4}
              className="w-full rounded-md border border-gray-300 p-3 transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
            <div className="flex gap-2">
              <button onClick={handleSaveThread} className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500">
                Save
              </button>
              <button onClick={() => setEditingThread(false)} className="rounded-md border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{thread.title}</h1>
              {(isOwner || canModerate) && (
                <div className="flex gap-1.5 shrink-0 ml-4">
                  <button
                    onClick={handleEditThread}
                    className="rounded-md border border-gray-200 p-1.5 text-gray-400 transition hover:bg-indigo-50 hover:text-indigo-600 dark:border-gray-600 dark:hover:bg-indigo-900/20 dark:hover:text-indigo-400"
                    title="Edit thread"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                  <button
                    onClick={handleDeleteThread}
                    className="rounded-md border border-gray-200 p-1.5 text-gray-400 transition hover:bg-red-50 hover:text-red-600 dark:border-gray-600 dark:hover:bg-red-900/20 dark:hover:text-red-400"
                    title="Delete thread"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              )}
            </div>
            <p className="mt-3 text-gray-600 leading-relaxed dark:text-gray-300">{thread.description}</p>
            <div className="mt-3 flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              {thread.avatar ? (
                <img src={thread.avatar} alt="" className="h-7 w-7 rounded-full object-cover" />
              ) : (
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-bold text-white">
                  {thread.username?.charAt(0).toUpperCase()}
                </span>
              )}
              <span className="font-medium">{thread.username}</span>
            </div>
          </>
        )}
      </div>

      {/* COMMENT BOX */}
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 mb-6 dark:bg-gray-800 dark:border-gray-700">
        <h2 className="font-semibold mb-3 text-gray-900 dark:text-white">Add Comment</h2>

        {!user ? (
          <div className="text-center">
            <p className="mb-2 text-gray-500 dark:text-gray-400">Login to add a comment</p>
            <button onClick={() => navigate("/login")} className="bg-indigo-600 text-white px-4 py-2 rounded-md font-medium transition hover:bg-indigo-500">
              Login
            </button>
          </div>
        ) : (
          <form onSubmit={handleAddComment}>
            <textarea
              className="w-full border border-gray-300 p-3 rounded-md transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder="Write your comment... Use @username to mention someone"
            />
            <button className="mt-3 bg-indigo-600 text-white px-4 py-2 rounded-md font-medium hover:bg-indigo-500 transition">
              Post
            </button>
          </form>
        )}
      </div>

      <div className="mt-4 mb-6 flex items-center gap-4">
        <button
          onClick={handleLike}
          className={`rounded-md border px-5 py-2 font-medium transition ${
            hasLiked
              ? "bg-rose-50 border-rose-200 text-rose-600 dark:bg-rose-900/20 dark:border-rose-700 dark:text-rose-400"
              : "border-gray-200 hover:bg-gray-100 text-gray-600 dark:border-gray-600 dark:hover:bg-gray-700 dark:text-gray-300"
          }`}
        >
          {hasLiked ? "❤️ Liked" : "🤍 Like"}
        </button>

        <span className="text-sm text-gray-600 dark:text-gray-400">
          {likeCount} {likeCount === 1 ? "like" : "likes"}
        </span>
      </div>

      {/* COMMENTS — recursive rendering for unlimited nesting */}
      <div className="space-y-4">
        {rootComments.length === 0 && (
          <p className="text-center text-sm text-gray-500 dark:text-gray-400 py-8">
            No comments yet. Be the first to comment!
          </p>
        )}
        {renderComments(rootComments)}
      </div>
    </div>
  );
}
