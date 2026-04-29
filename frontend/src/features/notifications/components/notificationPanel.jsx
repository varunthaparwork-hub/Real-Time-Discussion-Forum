// Dropdown panel that shows all notifications (new comment, like, mention).
// Opens from the bell icon in the navbar.
import { useNavigate } from "react-router-dom";
import useNotificationStore from "../store/notificationStore";

// Backend stores UTC without timezone suffix — append 'Z' so JS treats it as UTC
function parseUTC(dateString) {
  if (!dateString) return new Date();
  // If no timezone info, treat as UTC
  if (!dateString.endsWith("Z") && !dateString.includes("+") && !dateString.includes("-", 10)) {
    return new Date(dateString + "Z");
  }
  return new Date(dateString);
}

function timeAgo(dateString) {
  const now = new Date();
  const date = parseUTC(dateString);
  const seconds = Math.floor((now - date) / 1000);

  if (seconds < 0) return "just now"; // clock skew safety
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 4) return `${weeks}w ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatFullDate(dateString) {
  const date = parseUTC(dateString);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

const NOTIF_CONFIG = {
  like: {
    icon: (
      <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
        <path d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" />
      </svg>
    ),
    color: "text-rose-500",
    bg: "bg-rose-50 dark:bg-rose-500/10",
    border: "border-rose-200/60 dark:border-rose-500/20",
  },
  comment: {
    icon: (
      <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clipRule="evenodd" />
      </svg>
    ),
    color: "text-blue-500",
    bg: "bg-blue-50 dark:bg-blue-500/10",
    border: "border-blue-200/60 dark:border-blue-500/20",
  },
  mention: {
    icon: (
      <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M14.243 5.757a6 6 0 10-.986 9.284 1 1 0 111.087 1.678A8 8 0 1118 10a3 3 0 01-4.8 2.401A4 4 0 1114 10a1 1 0 102 0c0-4.418-3.582-8-8-8zm-2.243 6a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
      </svg>
    ),
    color: "text-indigo-500",
    bg: "bg-indigo-50 dark:bg-indigo-500/10",
    border: "border-indigo-200/60 dark:border-indigo-500/20",
  },
  default: {
    icon: (
      <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
        <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
      </svg>
    ),
    color: "text-gray-500",
    bg: "bg-gray-50 dark:bg-gray-500/10",
    border: "border-gray-200 dark:border-gray-500/20",
  },
};

function getNotifType(title) {
  const t = title?.toLowerCase() || "";
  if (t.includes("like")) return "like";
  if (t.includes("reply") || t.includes("comment")) return "comment";
  if (t.includes("mention")) return "mention";
  return "default";
}

export default function NotificationPanel() {
  const navigate = useNavigate();

  const notifications = useNotificationStore((state) => state.notifications);
  const loading = useNotificationStore((state) => state.loading);
  const panelOpen = useNotificationStore((state) => state.panelOpen);
  const setPanelOpen = useNotificationStore((state) => state.setPanelOpen);
  const markAsRead = useNotificationStore((state) => state.markAsRead);
  const markAllRead = useNotificationStore((state) => state.markAllRead);

  if (!panelOpen) return null;

  const handleNotificationClick = async (notification) => {
    if (!notification.is_read) {
      await markAsRead(notification.id);
    }
    setPanelOpen(false);
    if (notification.thread_id) {
      navigate(`/thread/${notification.thread_id}`);
    }
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <>
      {/* Dark backdrop overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/40"
        onClick={() => setPanelOpen(false)}
      />
      <div className="absolute right-0 top-14 z-50 w-[24rem] overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-800">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <svg className="h-4.5 w-4.5 text-gray-600 dark:text-gray-300" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
          </svg>
          <h3 className="text-sm font-bold text-gray-900 dark:text-white">Notifications</h3>
        </div>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <>
              <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[11px] font-bold text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">
                {unreadCount} new
              </span>
              <button
                onClick={markAllRead}
                className="rounded-md bg-gray-100 px-2 py-0.5 text-[10px] font-semibold text-gray-600 transition hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
              >
                Read all
              </button>
            </>
          )}
        </div>
      </div>

      {/* List */}
      <div className="max-h-[420px] overflow-y-auto overscroll-contain" style={{ scrollbarWidth: "thin" }}>
        {loading ? (
          <div className="flex flex-col items-center justify-center py-14">
            <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-gray-200 border-t-indigo-600 dark:border-gray-600 dark:border-t-indigo-400" />
            <p className="mt-3 text-xs text-gray-400">Loading notifications…</p>
          </div>
        ) : notifications.length === 0 ? (
          <div className="flex flex-col items-center py-16">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gray-100 dark:bg-gray-700">
              <svg className="h-8 w-8 text-gray-300 dark:text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
              </svg>
            </div>
            <p className="mt-3 text-sm font-medium text-gray-400 dark:text-gray-500">
              All caught up!
            </p>
            <p className="mt-1 text-xs text-gray-300 dark:text-gray-600">
              No new notifications
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {notifications.map((notification) => {
              const type = getNotifType(notification.title);
              const config = NOTIF_CONFIG[type];

              return (
                <button
                  key={notification.id}
                  onClick={() => handleNotificationClick(notification)}
                  className={`group flex w-full gap-3 px-4 py-3.5 text-left transition-all duration-150 hover:bg-gray-50 dark:hover:bg-gray-700/50 ${
                    !notification.is_read
                      ? "bg-indigo-50/50 dark:bg-indigo-900/10"
                      : ""
                  }`}
                >
                  {/* Icon bubble */}
                  <div
                    className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${config.bg} ${config.border} ${config.color} transition-transform group-hover:scale-105`}
                  >
                    {config.icon}
                  </div>

                  {/* Content */}
                  <div className="min-w-0 flex-1">
                    <p
                      className={`text-[13px] leading-relaxed ${
                        !notification.is_read
                          ? "font-semibold text-gray-900 dark:text-gray-100"
                          : "text-gray-600 dark:text-gray-400"
                      }`}
                    >
                      {notification.message}
                    </p>
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <svg className="h-3 w-3 text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span
                        className="text-[11px] font-medium text-gray-400 dark:text-gray-500"
                        title={formatFullDate(notification.created_at)}
                      >
                        {timeAgo(notification.created_at)}
                      </span>
                    </div>
                  </div>

                  {/* Unread indicator */}
                  {!notification.is_read && (
                    <div className="mt-2 flex shrink-0 items-start">
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-50" />
                        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-indigo-500" />
                      </span>
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      {notifications.length > 0 && (
        <div className="border-t border-gray-100 px-4 py-2.5 dark:border-gray-700">
          <p className="text-center text-[10px] font-medium uppercase tracking-widest text-gray-300 dark:text-gray-600">
            {notifications.length} notification{notifications.length !== 1 ? "s" : ""}
          </p>
        </div>
      )}
    </div>
    </>
  );
}