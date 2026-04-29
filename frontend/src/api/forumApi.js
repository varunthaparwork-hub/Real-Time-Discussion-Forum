// API calls for threads, comments, and likes.
// All requests go to the FastAPI forum-service.
import { forumClient } from "../lib/axios";

export const getThreads = async (page = 1, limit = 10) => {
  const response = await forumClient.get(`/threads/?page=${page}&limit=${limit}`);
  return response.data;
};

export const searchThreads = async (query) => {
  const response = await forumClient.get(`/threads/search?q=${encodeURIComponent(query)}`);
  return response.data;
};

export const createThread = async (payload) => {
  const response = await forumClient.post("/threads/", payload);
  return response.data;
};

export const getThreadById = async (threadId) => {
  const response = await forumClient.get(`/threads/${threadId}`);
  return response.data;
};

export const updateThread = async (threadId, payload) => {
  const response = await forumClient.put(`/threads/${threadId}`, payload);
  return response.data;
};

export const deleteThread = async (threadId) => {
  const response = await forumClient.delete(`/threads/${threadId}`);
  return response.data;
};

export const getCommentsByThread = async (threadId) => {
  const response = await forumClient.get(`/comments/thread/${threadId}`);
  return response.data;
};

export const createComment = async (payload) => {
  const response = await forumClient.post("/comments/", payload);
  return response.data;
};

export const updateComment = async (commentId, payload) => {
  const response = await forumClient.put(`/comments/${commentId}`, payload);
  return response.data;
};

export const deleteComment = async (commentId) => {
  const response = await forumClient.delete(`/comments/${commentId}`);
  return response.data;
};

export const likeThread = async (threadId) => {
  const response = await forumClient.post(`/likes/thread/${threadId}`);
  return response.data;
};

export const unlikeThread = async (threadId) => {
  const response = await forumClient.delete(`/likes/thread/${threadId}`);
  return response.data;
};

export const getThreadLikeCount = async (threadId) => {
  const response = await forumClient.get(`/likes/thread/${threadId}/count`);
  return response.data;
};

export const getThreadLikeStatus = async (threadId) => {
  const response = await forumClient.get(`/likes/thread/${threadId}/status`);
  return response.data;
};

export const likeComment = async (commentId) => {
  const response = await forumClient.post(`/likes/comment/${commentId}`);
  return response.data;
};

export const unlikeComment = async (commentId) => {
  const response = await forumClient.delete(`/likes/comment/${commentId}`);
  return response.data;
};

export const getCommentLikeCount = async (commentId) => {
  const response = await forumClient.get(`/likes/comment/${commentId}/count`);
  return response.data;
};

// Batch: get like counts for many comments in one call
export const getBatchCommentLikeCounts = async (commentIds) => {
  if (!commentIds.length) return { counts: {} };
  const ids = commentIds.join(",");
  const response = await forumClient.get(`/likes/comments/counts?ids=${ids}`);
  return response.data;
};

// Batch: get per-user like status for many comments in one call
export const getBatchCommentLikeStatuses = async (commentIds) => {
  if (!commentIds.length) return { statuses: {} };
  const ids = commentIds.join(",");
  const response = await forumClient.get(`/likes/comments/statuses?ids=${ids}`);
  return response.data;
};