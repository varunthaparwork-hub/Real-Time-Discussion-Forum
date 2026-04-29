// Theme state — toggles dark/light mode and saves the preference to localStorage.
import { create } from "zustand";

const useThemeStore = create((set) => ({
  darkMode: localStorage.getItem("theme") === "dark",

  initTheme: () => {
    const isDark = localStorage.getItem("theme") === "dark";
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    set({ darkMode: isDark });
  },

  toggleTheme: () =>
    set((state) => {
      const newMode = !state.darkMode;
      localStorage.setItem("theme", newMode ? "dark" : "light");
      if (newMode) {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
      return { darkMode: newMode };
    }),
}));

export default useThemeStore;
