import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { ProveedorAvisos } from "./ui.jsx";
import "./estilos.css";
import { esRespuestaDeMicrosoft, reenviarRespuesta } from "./microsoft.js";

const iniciar = () => createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ProveedorAvisos>
      <App />
    </ProveedorAvisos>
  </StrictMode>,
);

// La ventana de Microsoft regresa a esta misma dirección: solo entrega la respuesta y se cierra.
if (esRespuestaDeMicrosoft()) reenviarRespuesta().catch(iniciar);
else iniciar();
