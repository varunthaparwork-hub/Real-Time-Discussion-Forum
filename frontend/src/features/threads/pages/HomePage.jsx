// Homepage — shows a paginated list of discussion threads.
// Includes a search bar that filters threads in real-time.
import { useEffect, useState } from "react";
import { getThreads, searchThreads } from "../../../api/forumApi";
import { Link } from "react-router-dom";

export default function HomePage() {
  const [allThreads, setAllThreads] = useState([]);
  const [displayThreads, setDisplayThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const fetchThreads = async (p = page) => {
    try {
      const data = await getThreads(p, 10);
      setAllThreads(data.threads);
      setDisplayThreads(data.threads);
      setTotalPages(data.total_pages);
    } catch (error) {
      console.error("Error fetching threads", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchThreads(page);
  }, [page]);

  useEffect(() => {
    if (!searchQuery.trim()) {
      setDisplayThreads(allThreads);
      return;
    }

    setSearching(true);
    const timeout = setTimeout(async () => {
      try {
        const data = await searchThreads(searchQuery);
        setDisplayThreads(data);
      } catch (error) {
        console.error("Search error:", error);
      } finally {
        setSearching(false);
      }
    }, 300);

    return () => clearTimeout(timeout);
  }, [searchQuery, allThreads]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-gray-500 dark:text-gray-400">Loading threads...</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Discussion Threads
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Browse and join conversations
          </p>
        </div>
        <Link
          to="/create-thread"
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
        >
          + New Thread
        </Link>
      </div>

      {/* Search Bar */}
      <div className="relative mb-6">
        <div className="pointer-events-none absolute inset-y-0 left-0 z-10 flex items-center pl-3">
          <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <input
          type="text"
          placeholder="Search threads by title or description..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-4 text-sm text-gray-900 transition placeholder:text-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:placeholder:text-gray-500 dark:focus:border-indigo-400 dark:focus:ring-indigo-400"
        />
        {searching && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-4">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-indigo-600" />
          </div>
        )}
      </div>

      {displayThreads.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-12 text-center dark:border-gray-700 dark:bg-gray-800">
          <p className="text-lg text-gray-500 dark:text-gray-400">
            {searchQuery
              ? `No threads found for "${searchQuery}"`
              : "No threads yet. Be the first to start a discussion!"}
          </p>
          {!searchQuery && (
            <Link
              to="/create-thread"
              className="mt-4 inline-block rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
            >
              Create Thread
            </Link>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {displayThreads.map((thread) => (
            <Link
              key={thread.id}
              to={`/thread/${thread.id}`}
              className="group flex items-center justify-between gap-4 rounded-lg border border-gray-200 bg-white p-5 transition-all hover:border-indigo-300 hover:shadow-sm dark:border-gray-700 dark:bg-gray-800 dark:hover:border-indigo-600"
            >
              <div className="min-w-0 flex-1">
                <h2 className="text-base font-semibold text-gray-900 transition-colors group-hover:text-indigo-600 dark:text-white dark:group-hover:text-indigo-400">
                  {thread.title}
                </h2>
                <p className="mt-1 line-clamp-2 text-sm text-gray-500 dark:text-gray-400">
                  {thread.description}
                </p>
              </div>

              <div className="flex shrink-0 flex-col items-end gap-2 text-right">
                <div className="flex items-center gap-2">
                  {thread.avatar ? (
                    <img
                      src={thread.avatar}
                      alt=""
                      className="h-6 w-6 rounded-full object-cover"
                    />
                  ) : (
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-bold text-white">
                      {thread.username?.charAt(0).toUpperCase()}
                    </span>
                  )}
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-300">
                    {thread.username}
                  </span>
                </div>
                <span className="text-xs text-gray-400 dark:text-gray-500">
                  {new Date(thread.created_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      {!searchQuery && totalPages > 1 && (
        <div className="mt-8 flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-md border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            ← Prev
          </button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button
              key={p}
              onClick={() => setPage(p)}
              className={`h-9 w-9 rounded-md text-sm font-semibold transition ${
                p === page
                  ? "bg-indigo-600 text-white"
                  : "border border-gray-200 text-gray-600 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
              }`}
            >
              {p}
            </button>
          ))}
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded-md border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}