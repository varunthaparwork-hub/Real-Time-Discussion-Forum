// Auth state — holds the logged-in user, JWT tokens, and auth actions.
// Tokens are saved in localStorage so the user stays logged in on refresh.
import { create } from "zustand";
import { getProfile, loginUser, registerUser } from "../../../api/authApi";

const useAuthStore = create((set, get) => ({
  user: null,
  accessToken: localStorage.getItem("accessToken") || null,
  refreshToken: localStorage.getItem("refreshToken") || null,
  loading: false,
  authChecked: false,

  register: async (payload) => {
    set({ loading: true });
    try {
      await registerUser(payload);
      set({ loading: false });
      return { success: true };
    } catch (error) {
      set({ loading: false });
      return {
        success: false,
        error: error.response?.data || "Registration failed",
      };
    }
  },

  login: async (payload) => {
    set({ loading: true });
    try {
      const data = await loginUser(payload);

      localStorage.setItem("accessToken", data.access);
      localStorage.setItem("refreshToken", data.refresh);

      set({
        accessToken: data.access,
        refreshToken: data.refresh,
        loading: false,
      });

      return { success: true };
    } catch (error) {
      set({ loading: false });
      return {
        success: false,
        error: error.response?.data || "Login failed",
      };
    }
  },

  loadUser: async () => {
    const token = get().accessToken;

    if (!token) {
      set({ user: null, authChecked: true });
      return;
    }

    try {
      const user = await getProfile();
      set({ user, authChecked: true });
    } catch (error) {
      localStorage.removeItem("accessToken");
      localStorage.removeItem("refreshToken");
      set({
        user: null,
        accessToken: null,
        refreshToken: null,
        authChecked: true,
      });
    }
  },

  logout: () => {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      authChecked: true,
    });
  },
}));

export default useAuthStore;