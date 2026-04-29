// Forgot password page — user enters their email and receives a reset link.
import { useState } from "react";
import { Link } from "react-router-dom";
import { forgotPassword } from "../../../api/authApi";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [resetLink, setResetLink] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    setError("");
    setResetLink("");

    try {
      const data = await forgotPassword({ email });
      setMessage(data.message);
      if (data.reset_link) {
        setResetLink(data.reset_link);
      }
    } catch (err) {
      setError("Something went wrong. Please try again.");
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
            🔑
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Forgot Password
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Enter your email to get a reset link
          </p>
        </div>

        {error && (
          <p className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
            {error}
          </p>
        )}

        {message && !resetLink && (
          <div className="mb-4 rounded-md border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-900/20">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-xl">📧</span>
              <p className="font-semibold text-green-800 dark:text-green-300">
                Email Sent!
              </p>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {message} Check your inbox (and spam folder) for the password reset link.
            </p>
          </div>
        )}

        {resetLink && (
          <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-900/20">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-xl">⚠️</span>
              <p className="font-semibold text-amber-800 dark:text-amber-300">
                Dev Mode — No Email Configured
              </p>
            </div>
            <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
              Email service is not configured yet. Use the button below to reset
              your password directly:
            </p>
            <a
              href={resetLink}
              className="inline-block rounded-md bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-500"
            >
              Reset My Password Now →
            </a>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Email Address
            </label>
            <input
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded-md border border-gray-300 bg-white p-2.5 text-sm transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-indigo-600 px-4 py-2.5 font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
          >
            {loading ? "Sending..." : "Send Reset Link"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
          Remember your password?{" "}
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
