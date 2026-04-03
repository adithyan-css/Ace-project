import React from "react";
import { createRoot } from "react-dom/client";
import MissionControl from "./pages/MissionControl";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <MissionControl />
  </React.StrictMode>
);
