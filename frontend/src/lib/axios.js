// HTTP clients for each backend service.
// authClient   → Django auth service (port 8001)
// forumClient  → FastAPI forum service (port 8000)
// notificationClient → FastAPI notification service (port 8003)
// The interceptor auto-attaches the JWT token to every request.
import axios from "axios";

export const authClient = axios.create({
  baseURL: "http://localhost:8001/api/auth",
});

export const forumClient = axios.create({
  baseURL: "http://localhost:8000",
});

export const notificationClient = axios.create({
  baseURL: "http://localhost:8003",
});

const attachToken = (config) => {
  const token = localStorage.getItem("accessToken");

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
};

forumClient.interceptors.request.use(attachToken);
notificationClient.interceptors.request.use(attachToken);