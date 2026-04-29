// Notification state — manages the WebSocket connection, live notifications,
// unread count, and thread-specific event subscriptions.
// One WebSocket connects to the notification-service and handles both
// user notifications and real-time thread updates (comments, likes).
import { create } from "zustand";
import {
  getMyNotifications,
  markNotificationRead,
  markAllNotificationsRead,
} from "../../../api/notificationApi";

// ── Reconnect settings ──────────────────────────────────────────────
const WS_INITIAL_DELAY = 1000;   // 1s
const WS_MAX_DELAY = 30000;      // 30s cap
const WS_BACKOFF_FACTOR = 2;

const useNotificationStore = create((set, get) => ({
  notifications: [],
  loading: false,
  panelOpen: false,
  socket: null,
  _reconnectTimer: null,
  _reconnectDelay: WS_INITIAL_DELAY,
  _threadListeners: {},  // { threadId: callback }

  unreadCount: 0,

  setPanelOpen: (value) => set({ panelOpen: value }),

  fetchNotifications: async () => {
    set({ loading: true });
    try {
      const data = await getMyNotifications();

      set({
        notifications: data,
        unreadCount: data.filter((item) => !item.is_read).length,
        loading: false,
      });
    } catch (error) {
      console.error("Fetch notifications error:", error);
      set({ loading: false });
    }
  },

  addLiveNotification: (notification) => {
    const current = get().notifications;
    const updated = [notification, ...current];

    set({
      notifications: updated,
      unreadCount: updated.filter((item) => !item.is_read).length,
    });
  },

  markAsRead: async (notificationId) => {
    try {
      await markNotificationRead(notificationId);

      const updated = get().notifications.map((item) =>
        item.id === notificationId ? { ...item, is_read: true } : item
      );

      set({
        notifications: updated,
        unreadCount: updated.filter((item) => !item.is_read).length,
      });
    } catch (error) {
      console.error("Mark notification read error:", error);
    }
  },

  markAllRead: async () => {
    try {
      await markAllNotificationsRead();
      const updated = get().notifications.map((n) => ({ ...n, is_read: true }));
      set({ notifications: updated, unreadCount: 0 });
    } catch (error) {
      console.error("Mark all read error:", error);
    }
  },

  connectSocket: (token) => {
    const existingSocket = get().socket;
    if (existingSocket && existingSocket.readyState <= 1) return;

    // Clear any pending reconnect
    const timer = get()._reconnectTimer;
    if (timer) clearTimeout(timer);

    const ws = new WebSocket(
      `ws://localhost:8003/ws?token=${token}`
    );

    ws.onopen = () => {
      console.log("WebSocket connected (unified)");
      set({ _reconnectDelay: WS_INITIAL_DELAY }); // reset backoff
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Handle subscription confirmations
        if (data.action === "subscribed" || data.action === "unsubscribed") {
          return;
        }

        // Personal notification events (check FIRST so thread-event
        // matching doesn't swallow notifications with the same event_type)
        if (data.notification_id) {
          get().addLiveNotification({
            id: data.notification_id,
            user_id: null,
            type: data.event_type,
            title: data.title,
            message: data.message,
            thread_id: data.thread_id,
            comment_id: data.comment_id,
            action_user_id: data.action_user_id,
            is_read: data.is_read,
            created_at: data.created_at,
          });
          return;
        }

        // Thread-level events — dispatch to registered listener
        const threadEvents = new Set([
          "comment.created",
          "thread.liked",
          "thread.unliked",
          "comment.liked",
          "comment.unliked",
        ]);

        if (data.event_type && threadEvents.has(data.event_type) && data.thread_id) {
          const listener = get()._threadListeners[data.thread_id];
          if (listener) {
            listener(data);
          }
          return;
        }
      } catch (error) {
        console.error("WebSocket parse error:", error);
      }
    };

    ws.onclose = (e) => {
      console.log(`WS closed (code=${e.code})`);
      set({ socket: null });

      // Don't reconnect if closed deliberately (code 4003 = auth failure)
      if (e.code === 4003) {
        console.warn("WS auth failed, not reconnecting");
        return;
      }

      // Exponential backoff reconnect
      const delay = get()._reconnectDelay;
      console.log(`Reconnecting WS in ${delay}ms ...`);
      const reconnectTimer = setTimeout(() => {
        const currentToken = localStorage.getItem("accessToken");
        if (currentToken) {
          get().connectSocket(currentToken);
        }
      }, delay);

      set({
        _reconnectTimer: reconnectTimer,
        _reconnectDelay: Math.min(delay * WS_BACKOFF_FACTOR, WS_MAX_DELAY),
      });
    };

    ws.onerror = () => {
      // onclose will fire after onerror — reconnect logic lives there
    };

    set({ socket: ws });
  },

  disconnectSocket: () => {
    const timer = get()._reconnectTimer;
    if (timer) clearTimeout(timer);

    const socket = get().socket;
    if (socket) {
      socket.onclose = null; // prevent auto-reconnect on intentional close
      socket.close();
    }
    set({ socket: null, _reconnectTimer: null, _reconnectDelay: WS_INITIAL_DELAY, _threadListeners: {} });
  },

  // ── Thread subscription methods ───────────────────────────────────
  subscribeThread: (threadId, onEvent) => {
    const socket = get().socket;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ action: "subscribe_thread", thread_id: threadId }));
    }
    set((state) => ({
      _threadListeners: { ...state._threadListeners, [threadId]: onEvent },
    }));
  },

  unsubscribeThread: (threadId) => {
    const socket = get().socket;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ action: "unsubscribe_thread", thread_id: threadId }));
    }
    set((state) => {
      const updated = { ...state._threadListeners };
      delete updated[threadId];
      return { _threadListeners: updated };
    });
  },
}));

export default useNotificationStore;