// API calls for user authentication and profile management.
// All requests go to the Django auth-service at port 8001.
import { authClient } from "../lib/axios";

export const registerUser = async (payload) => {
  const response = await authClient.post("/register/", payload);
  return response.data;
};

export const loginUser = async (payload) => {
  const response = await authClient.post("/login/", payload);
  return response.data;
};

export const getProfile = async () => {
  const token = localStorage.getItem("accessToken");

  const response = await authClient.get("/profile/", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  return response.data;
};

export const updateProfile = async (payload) => {
  const token = localStorage.getItem("accessToken");

  const response = await authClient.put("/profile/", payload, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  return response.data;
};

export const getAllUsers = async (page = 1, limit = 10) => {
  const token = localStorage.getItem("accessToken");

  const response = await authClient.get(`/users/all/?page=${page}&limit=${limit}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  return response.data;
};

export const changePassword = async (payload) => {
  const token = localStorage.getItem("accessToken");

  const response = await authClient.post("/change-password/", payload, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  return response.data;
};

export const forgotPassword = async (payload) => {
  const response = await authClient.post("/forgot-password/", payload);
  return response.data;
};

export const resetPassword = async (payload) => {
  const response = await authClient.post("/reset-password/", payload);
  return response.data;
};

export const getPublicProfile = async (username) => {
  const response = await authClient.get(`/profile/${username}/`);
  return response.data;
};

export const updateUserRole = async (userId, role) => {
  const token = localStorage.getItem("accessToken");

  const response = await authClient.put(`/users/${userId}/role/`, { role }, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  return response.data;
};