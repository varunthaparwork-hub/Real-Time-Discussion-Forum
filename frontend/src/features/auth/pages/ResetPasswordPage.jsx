// Reset password page — user sets a new password using the link from their email.
import { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { resetPassword } from "../../../api/authApi";

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const uid = searchParams.get("uid") || "";
  const token = searchParams.get("token") || "";

  const [formData, setFormData] = useState({
    new_password: "",
    new_password2: "",
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleChange = (e) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    setError("");

    if (formData.new_password !== formData.new_password2) {
      setError("Passwords do not match");
      setLoading(false);
      return;
    }

    if (!uid || !token) {
      setError("Invalid reset link. Please request a new one.");
      setLoading(false);
      return;
    }

    try {
      const data = await resetPassword({
        uid,
        token,
        new_password: formData.new_password,
        new_password2: formData.new_password2,
      });
      setMessage(data.message);
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      const detail =
        err.response?.data?.detail ||
        err.response?.data?.new_password?.[0] ||
        "Reset failed. The link may have expired.";
      setError(detail);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-gray-900">
      <div className="w-full max-w-md rounded-lg border border-gray-200 bg-white p-8 shadow-sm dark:border-gray-700 dark:bg-gray-800">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-indigo-100 text-xl dark:bg-indigo-900/30">
            🔒
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Reset Password
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Enter your new password below
          </p>
        </div>

        {error && (
          <p className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
            {error}
          </p>
        )}

        {message && (
          <div className="mb-4 rounded-md bg-green-50 p-3 dark:bg-green-900/20">
            <p className="text-sm text-green-700 dark:text-green-400">
              {message} Redirecting to login...
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
              New Password
            </label>
            <input
              type="password"
              name="new_password"
              placeholder="Enter new password"
              value={formData.new_password}
              onChange={handleChange}
              required
              className="w-full rounded-md border border-gray-300 bg-white p-2.5 text-sm transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Confirm New Password
            </label>
            <input
              type="password"
              name="new_password2"
              placeholder="Confirm new password"
              value={formData.new_password2}
              onChange={handleChange}
              required
              className="w-full rounded-md border border-gray-300 bg-white p-2.5 text-sm transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-indigo-600 px-4 py-2.5 font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
          >
            {loading ? "Resetting..." : "Reset Password"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
          <Link
            to="/login"
            className="font-medium text-indigo-600 hover:underline dark:text-indigo-400"
          >
            Back to Login
          </Link>
        </p>
      </div>
    </div>
  );
}
