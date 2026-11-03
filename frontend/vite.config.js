import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, las llamadas a /api y /ws se envían al backend de FastAPI.
const backend = process.env.BACKEND_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    // 127.0.0.1 en lugar de "localhost": en Windows "localhost" puede quedar solo en IPv6 (::1)
    // y entonces http://127.0.0.1:5173 no abre. Así funcionan las dos direcciones.
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": backend,
      "/ws": { target: backend.replace(/^http/, "ws"), ws: true },
    },
  },
});
