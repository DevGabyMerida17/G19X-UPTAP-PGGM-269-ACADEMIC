import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { ProveedorAvisos } from "./ui.jsx";
import "./estilos.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ProveedorAvisos>
      <App />
    </ProveedorAvisos>
  </StrictMode>,
);
