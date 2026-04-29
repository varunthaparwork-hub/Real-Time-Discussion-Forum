// App entry point — mounts the React app into the HTML page.
// AppInitializer loads the logged-in user and theme before anything renders.
import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { router } from "./app/router";
import AppInitializer from "./AppInitializer";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AppInitializer>
      <RouterProvider router={router} />
    </AppInitializer>
  </React.StrictMode>
);