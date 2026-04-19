import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./global.css";
import { createBrowserRouter, RouterProvider } from "react-router";
import { Device } from "./components/device/Dev.tsx";
import { Game } from "./Game.tsx";

const router = createBrowserRouter([
  {
    path: "/",
    Component: App,
  },
  {
    path: "/device/:id",
    Component: Device,
  },
  {
    path: "/game",
    Component: Game,
  },
]);

createRoot(document.getElementById("root")!).render(<RouterProvider router={router} />);
