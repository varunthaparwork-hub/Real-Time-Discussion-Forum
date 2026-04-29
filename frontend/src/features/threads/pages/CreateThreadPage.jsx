// New thread page — lets a logged-in user create a new discussion thread
// with a title and description.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createThread } from "../../../api/forumApi";

export default function CreateThreadPage() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    title: "",
    description: "",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (e) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!formData.title.trim() || !formData.description.trim()) {
      setError("Both title and description are required.");
      return;
    }

    setLoading(true);
    try {
      const thread = await createThread(formData);

      // redirect to thread detail
      navigate(`/thread/${thread.id}`);
    } catch (error) {
      console.error("Create thread error:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-900 dark:text-white">Create Thread</h1>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
        {error && (
          <p className="rounded-md bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
            {error}
          </p>
        )}

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
            Title <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            name="title"
            placeholder="Enter thread title"
            value={formData.title}
            onChange={handleChange}
            required
            className="w-full rounded-md border border-gray-300 bg-white p-2.5 text-sm transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
            Description <span className="text-red-500">*</span>
          </label>
          <textarea
            name="description"
            placeholder="Describe your topic..."
            rows={5}
            value={formData.description}
            onChange={handleChange}
            required
            className="w-full rounded-md border border-gray-300 bg-white p-2.5 text-sm transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
          />
        </div>

        <button
          type="submit"
          disabled={loading || !formData.title.trim() || !formData.description.trim()}
            className="w-full rounded-md bg-indigo-600 px-4 py-2.5 font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading ? "Creating..." : "Create Thread"}
        </button>
      </form>
    </div>
  );
}