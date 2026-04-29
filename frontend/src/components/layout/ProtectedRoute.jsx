// Guard for logged-in-only pages (profile, create thread, dashboard).
// Redirects to /login if the user isn't authenticated.
import { Navigate } from "react-router-dom";
import useAuthStore from "../../features/auth/store/authStore";

export default function ProtectedRoute({ children }) {
  const user = useAuthStore((state) => state.user);
  const authChecked = useAuthStore((state) => state.authChecked);

  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-600 dark:text-gray-400">Checking authentication...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}