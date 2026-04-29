// API calls for the notification service — fetch notifications, mark as read.
import { notificationClient } from "../lib/axios";

export const getMyNotifications = async () => {
  const response = await notificationClient.get("/notifications/");
  return response.data;
};

export const markNotificationRead = async (notificationId) => {
  const response = await notificationClient.patch(
    `/notifications/${notificationId}/read`
  );
  return response.data;
};

export const markAllNotificationsRead = async () => {
  const response = await notificationClient.patch("/notifications/read-all");
  return response.data;
};