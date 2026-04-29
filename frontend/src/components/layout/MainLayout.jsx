// Wraps every page with the top navigation bar.
// <Outlet /> is where the current page content renders.
import { Outlet } from "react-router-dom";
import Navbar from "./navbar";

export default function MainLayout() {
  return (
    <div className="min-h-screen bg-gray-50 transition-colors dark:bg-gray-900">
      <Navbar />
      <Outlet />
    </div>
  );
}