// My profile page — lets the user view and edit their profile info,
// change their avatar, and update their password.
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import useAuthStore from "../store/authStore";
import { getProfile, updateProfile } from "../../../api/authApi";

export default function ProfilePage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const loadUser = useAuthStore((state) => state.loadUser);
  const fileInputRef = useRef(null);

  const [formData, setFormData] = useState({
    username: "",
    email: "",
    bio: "",
    avatar: "",
  });
  const [avatarPreview, setAvatarPreview] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (user) {
      setFormData({
        username: user.username || "",
        email: user.email || "",
        bio: user.bio || "",
        avatar: user.avatar || "",
      });
      setAvatarPreview(user.avatar || null);
    }
  }, [user]);

  const handleChange = (e) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    if (e.target.name === "avatar") {
      setAvatarPreview(e.target.value || null);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
      setMessage("File too large. Max 2MB.");
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = reader.result;
      setFormData((prev) => ({ ...prev, avatar: base64 }));
      setAvatarPreview(base64);
    };
    reader.readAsDataURL(file);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMessage("");

    try {
      await updateProfile({
        bio: formData.bio,
        avatar: formData.avatar || null,
      });
      await loadUser();
      setMessage("Profile updated successfully!");
    } catch (error) {
      setMessage("Failed to update profile.");
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  if (!user) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-gray-500 dark:text-gray-400">Loading profile...</p>
      </div>
    );
  }

  const roleBadge = {
    admin: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400",
    moderator: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    member: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400",
  };

  const joined = user.date_joined
    ? new Date(user.date_joined).toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "Unknown";

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-8 text-2xl font-bold text-gray-900 dark:text-white">
        My Profile
      </h1>

      {/* Profile Card */}
      <div className="rounded-lg border border-gray-200 bg-white p-8 shadow-sm dark:border-gray-700 dark:bg-gray-800">
        {/* Avatar + Name Header */}
        <div className="mb-8 flex items-center gap-5">
          {avatarPreview ? (
            <img
              src={avatarPreview}
              alt="Avatar"
              className="h-20 w-20 rounded-full border-2 border-gray-200 object-cover dark:border-gray-700"
            />
          ) : (
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-indigo-600 text-3xl font-bold text-white">
              {user.username?.charAt(0).toUpperCase()}
            </div>
          )}

          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              {user.username}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {user.email}
            </p>
            <div className="mt-2 flex items-center gap-3">
              <span
                className={`rounded-full px-3 py-0.5 text-xs font-semibold ${roleBadge[user.role] || roleBadge.member}`}
              >
                {user.role}
              </span>
              <span className="text-xs text-gray-400 dark:text-gray-500">
                Joined {joined}
              </span>
            </div>
          </div>
        </div>

        {/* Edit Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Username
            </label>
            <input
              type="text"
              value={formData.username}
              disabled
              className="w-full rounded-md border border-gray-200 bg-gray-50 p-2.5 text-sm text-gray-400 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-500"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Email
            </label>
            <input
              type="email"
              value={formData.email}
              disabled
              className="w-full rounded-md border border-gray-200 bg-gray-50 p-2.5 text-sm text-gray-400 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-500"
            />
          </div>

          {/* Avatar Section */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Avatar
            </label>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="rounded-md border border-dashed border-gray-300 bg-gray-50 px-4 py-2.5 text-sm font-medium text-gray-600 transition hover:border-indigo-400 hover:bg-indigo-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:border-indigo-500"
              >
                Upload File
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileUpload}
                className="hidden"
              />
              <span className="self-center text-xs text-gray-400">or</span>
              <input
                type="text"
                name="avatar"
                placeholder="Paste image URL"
                value={formData.avatar?.startsWith("data:") ? "" : formData.avatar}
                onChange={handleChange}
                className="flex-1 rounded-md border border-gray-300 bg-white p-2.5 text-sm transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              />
            </div>
            <p className="mt-1.5 text-xs text-gray-400">Max file size: 2MB. Supports JPG, PNG, GIF.</p>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Bio
            </label>
            <textarea
              name="bio"
              rows={4}
              placeholder="Tell us about yourself..."
              value={formData.bio}
              onChange={handleChange}
              className="w-full rounded-md border border-gray-300 bg-white p-2.5 text-sm transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>

          {message && (
            <p
              className={`rounded-md p-3 text-sm ${
                message.includes("success")
                  ? "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400"
                  : "bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400"
              }`}
            >
              {message}
            </p>
          )}

          <button
            type="submit"
            disabled={saving}
            className="w-full rounded-md bg-indigo-600 px-6 py-2.5 font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Update Profile"}
          </button>
        </form>
      </div>
    </div>
  );
}
