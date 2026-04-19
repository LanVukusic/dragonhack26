import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./global.css";
import { createBrowserRouter, RouterProvider } from "react-router";
import { Device } from "./components/device/Dev.tsx";

const router = createBrowserRouter([
  {
    path: "/",
    Component: App,
  },
  {
    path: "/device/:id",
    Component: Device,
  },
]);

createRoot(document.getElementById("root")!).render(<RouterProvider router={router} />);
