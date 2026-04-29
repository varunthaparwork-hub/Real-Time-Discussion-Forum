// Admin dashboard — lets admins/moderators manage threads and user roles.
// Regular users see just their own threads here.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import useAuthStore from "../auth/store/authStore";
import { getThreads, deleteThread } from "../../api/forumApi";
import { getAllUsers, updateUserRole } from "../../api/authApi";

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const [threads, setThreads] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  // Pagination state for the user management table
  const [userPage, setUserPage] = useState(1);
  const [userTotalPages, setUserTotalPages] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);

  const isAdmin = user?.role === "admin";
  const isModerator = user?.role === "moderator";

  // Fetch threads once on mount
  const fetchThreads = async () => {
    try {
      const threadData = await getThreads(1, 100);
      setThreads(threadData.threads || []);
    } catch (error) {
      console.error("Dashboard load error:", error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch users for the current page (10 per page)
  const fetchUsers = async (page = 1) => {
    if (!isAdmin && !isModerator) return;
    try {
      const data = await getAllUsers(page, 10);
      setUsers(data.users || []);
      setUserPage(data.page);
      setUserTotalPages(data.total_pages);
      setTotalUsers(data.total_users);
    } catch {
      // user might not have permission
    }
  };

  useEffect(() => {
    fetchThreads();
    fetchUsers(1);
  }, [isAdmin, isModerator]);

  const handleRoleChange = async (userId, newRole) => {
    try {
      await updateUserRole(userId, newRole);
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u))
      );
    } catch (error) {
      console.error("Role update error:", error);
      alert(error.response?.data?.detail || "Failed to update role");
    }
  };

  const handleDeleteThread = async (threadId) => {
    if (!window.confirm("Are you sure you want to delete this thread?")) return;
    try {
      await deleteThread(threadId);
      setThreads((prev) => prev.filter((t) => t.id !== threadId));
    } catch (error) {
      console.error("Delete thread error:", error);
      alert(error.response?.data?.detail || "Failed to delete thread");
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-gray-500 dark:text-gray-400">Loading dashboard...</div>
      </div>
    );
  }

  const myThreads = threads.filter((t) => t.username === user?.username);

  const roleBadge = {
    admin: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400",
    moderator: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    member: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400",
  };

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Dashboard
          </h1>
          <p className="mt-1 text-gray-500 dark:text-gray-400">
            Welcome back, {user?.username}
          </p>
        </div>
        <span
          className={`rounded-full px-4 py-1 text-sm font-semibold ${roleBadge[user?.role] || roleBadge.member}`}
        >
          {user?.role}
        </span>
      </div>

      {/* Stats Cards */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard icon="✍️" label="My Threads" value={myThreads.length} />
        {(isAdmin || isModerator) && (
          <StatCard icon="📋" label="Total Threads" value={threads.length} />
        )}
        {(isAdmin || isModerator) && (
          <StatCard icon="👥" label="Total Users" value={totalUsers} />
        )}
      </div>

      {/* My Threads Section */}
      <div className="mb-8">
        <h2 className="mb-4 text-xl font-bold text-gray-900 dark:text-white">
          My Threads
        </h2>
        {myThreads.length === 0 ? (
          <div className="rounded-lg border border-gray-200 bg-white p-8 text-center dark:border-gray-700 dark:bg-gray-800">
            <p className="text-gray-500 dark:text-gray-400">
              You haven't created any threads yet.
            </p>
            <Link
              to="/create-thread"
              className="mt-3 inline-block rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
            >
              Create your first thread
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {myThreads.map((thread) => (
              <Link
                key={thread.id}
                to={`/thread/${thread.id}`}
                className="block rounded-lg border border-gray-200 bg-white p-4 transition hover:border-indigo-300 hover:shadow-sm dark:border-gray-700 dark:bg-gray-800 dark:hover:border-indigo-600"
              >
                <h3 className="font-semibold text-gray-900 dark:text-white">
                  {thread.title}
                </h3>
                <p className="mt-1 line-clamp-2 text-sm text-gray-500 dark:text-gray-400">
                  {thread.description}
                </p>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Admin/Moderator: All Threads with moderation tools */}
      {(isAdmin || isModerator) && (
        <div className="mb-8">
          <h2 className="mb-4 text-xl font-bold text-gray-900 dark:text-white">
            All Threads {isModerator && "(Moderator View)"} {isAdmin && "(Admin View)"}
          </h2>
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/50">
                <tr>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">ID</th>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Title</th>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Author</th>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Created</th>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {threads.map((thread) => (
                  <tr key={thread.id} className="transition hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">#{thread.id}</td>
                    <td className="px-4 py-3">
                      <Link to={`/thread/${thread.id}`} className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">
                        {thread.title}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{thread.username}</td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                      {new Date(thread.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleDeleteThread(thread.id)}
                        className="rounded-md border border-red-200 px-2.5 py-1 text-xs font-medium text-red-600 transition hover:bg-red-50 dark:border-red-700 dark:text-red-400 dark:hover:bg-red-900/20"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Admin: User Management with Role Controls */}
      {isAdmin && users.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 text-xl font-bold text-gray-900 dark:text-white">
            User Management
          </h2>
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/50">
                <tr>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">ID</th>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Username</th>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Email</th>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Role</th>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Joined</th>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {users.map((u) => (
                  <tr key={u.id} className="transition hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">#{u.id}</td>
                    <td className="px-4 py-3">
                      <Link to={`/user/${u.username}`} className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">
                        {u.username}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{u.email}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${roleBadge[u.role] || roleBadge.member}`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                      {new Date(u.date_joined).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      {u.id !== user?.id ? (
                        <select
                          value={u.role}
                          onChange={(e) => handleRoleChange(u.id, e.target.value)}
                          className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-700 transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-200 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
                        >
                          <option value="member">Member</option>
                          <option value="moderator">Moderator</option>
                          <option value="admin">Admin</option>
                        </select>
                      ) : (
                        <span className="text-xs text-gray-400 italic">You</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination controls */}
          {userTotalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Page {userPage} of {userTotalPages} ({totalUsers} users)
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => fetchUsers(userPage - 1)}
                  disabled={userPage <= 1}
                  className="rounded-md border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
                >
                  ← Previous
                </button>
                <button
                  onClick={() => fetchUsers(userPage + 1)}
                  disabled={userPage >= userTotalPages}
                  className="rounded-md border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Moderator: Users (read-only) */}
      {isModerator && !isAdmin && users.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 text-xl font-bold text-gray-900 dark:text-white">
            User Activity
          </h2>
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/50">
                <tr>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Username</th>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Email</th>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Role</th>
                  <th className="px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">Joined</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {users.map((u) => (
                  <tr key={u.id} className="transition hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="px-4 py-3">
                      <Link to={`/user/${u.username}`} className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">
                        {u.username}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{u.email}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${roleBadge[u.role] || roleBadge.member}`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                      {new Date(u.date_joined).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination controls */}
          {userTotalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Page {userPage} of {userTotalPages} ({totalUsers} users)
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => fetchUsers(userPage - 1)}
                  disabled={userPage <= 1}
                  className="rounded-md border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
                >
                  ← Previous
                </button>
                <button
                  onClick={() => fetchUsers(userPage + 1)}
                  disabled={userPage >= userTotalPages}
                  className="rounded-md border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, isText }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-700 text-lg">
          {icon}
        </div>
        <div>
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{label}</p>
          <p className={`font-bold text-gray-900 dark:text-white ${isText ? "text-sm capitalize" : "text-xl"}`}>
            {value}
          </p>
        </div>
      </div>
    </div>
  );
}
