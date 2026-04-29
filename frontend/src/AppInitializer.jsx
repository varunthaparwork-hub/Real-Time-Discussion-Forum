// Runs once on app load — restores the theme (dark/light) and
// checks if the user is already logged in (from a saved token).
import { useEffect } from "react";
import useAuthStore from "./features/auth/store/authStore";
import useThemeStore from "./stores/themeStore";

export default function AppInitializer({ children }) {
  const loadUser = useAuthStore((state) => state.loadUser);
  const initTheme = useThemeStore((state) => state.initTheme);

  useEffect(() => {
    initTheme();
    loadUser();
  }, [loadUser, initTheme]);

  return children;
}