// App routes — maps URLs to pages.
// ProtectedRoute = must be logged in.  GuestRoute = must NOT be logged in.
import { createBrowserRouter } from "react-router-dom";
import MainLayout from "../components/layout/MainLayout";
import ProtectedRoute from "../components/layout/ProtectedRoute";
import GuestRoute from "../components/layout/GuestRoute";
import LoginPage from "../features/auth/pages/LoginPage";
import RegisterPage from "../features/auth/pages/RegisterPage";
import ForgotPasswordPage from "../features/auth/pages/ForgotPasswordPage";
import ResetPasswordPage from "../features/auth/pages/ResetPasswordPage";
import ProfilePage from "../features/auth/pages/ProfilePage";
import UserProfilePage from "../features/auth/pages/UserProfilePage";
import HomePage from "../features/threads/pages/HomePage";
import ThreadDetailPage from "../features/threads/pages/ThreadDetailPage";
import CreateThreadPage from "../features/threads/pages/CreateThreadPage";
import DashboardPage from "../features/dashboard/DashboardPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <MainLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "thread/:threadId", element: <ThreadDetailPage /> },
      { path: "user/:username", element: <UserProfilePage /> },
      {
        path: "create-thread",
        element: (
          <ProtectedRoute>
            <CreateThreadPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "profile",
        element: (
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        ),
      },
      {
        path: "dashboard",
        element: (
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        ),
      },
    ],
  },
  {
    path: "/login",
    element: (
      <GuestRoute>
        <LoginPage />
      </GuestRoute>
    ),
  },
  {
    path: "/register",
    element: (
      <GuestRoute>
        <RegisterPage />
      </GuestRoute>
    ),
  },
  {
    path: "/forgot-password",
    element: (
      <GuestRoute>
        <ForgotPasswordPage />
      </GuestRoute>
    ),
  },
  {
    path: "/reset-password",
    element: <ResetPasswordPage />,
  },
]);