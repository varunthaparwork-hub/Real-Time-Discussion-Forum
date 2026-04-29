// Public profile page — shows another user's profile (avatar, bio, role).
// Accessible at /user/:username without login.
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getPublicProfile } from "../../../api/authApi";

export default function UserProfilePage() {
  const { username } = useParams();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const data = await getPublicProfile(username);
        setProfile(data);
      } catch (err) {
        setError("User not found");
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, [username]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-200 border-t-indigo-600" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
        <p className="text-4xl">😕</p>
        <p className="text-lg font-medium text-gray-500 dark:text-gray-400">
          {error || "User not found"}
        </p>
        <Link
          to="/"
          className="mt-2 text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400"
        >
          ← Back to threads
        </Link>
      </div>
    );
  }

  const roleBadge = {
    admin: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400",
    moderator: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    member: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400",
  };

  const joined = profile.date_joined
    ? new Date(profile.date_joined).toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : null;

  return (
    <div className="mx-auto max-w-lg p-6">
      <div className="rounded-lg border border-gray-200 bg-white p-8 text-center dark:border-gray-700 dark:bg-gray-800">
        {/* Avatar */}
        {profile.avatar ? (
          <img
            src={profile.avatar}
            alt=""
            className="mx-auto h-24 w-24 rounded-full object-cover"
          />
        ) : (
          <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-indigo-600 text-4xl font-bold text-white">
            {profile.username?.charAt(0).toUpperCase()}
          </div>
        )}

        {/* Name & Role */}
        <h1 className="mt-4 text-2xl font-bold text-gray-900 dark:text-white">
          {profile.username}
        </h1>

        <div className="mt-2 flex items-center justify-center gap-3">
          <span
            className={`rounded-full px-3 py-0.5 text-xs font-semibold ${roleBadge[profile.role] || roleBadge.member}`}
          >
            {profile.role}
          </span>
          {joined && (
            <span className="text-xs text-gray-400 dark:text-gray-500">
              Joined {joined}
            </span>
          )}
        </div>

        {/* Bio */}
        {profile.bio && (
          <p className="mx-auto mt-5 max-w-sm text-sm leading-relaxed text-gray-600 dark:text-gray-300">
            {profile.bio}
          </p>
        )}

        {!profile.bio && (
          <p className="mt-5 text-sm italic text-gray-400 dark:text-gray-500">
            This user hasn't added a bio yet.
          </p>
        )}
      </div>
    </div>
  );
}
