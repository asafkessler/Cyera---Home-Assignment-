import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the UI is served by Vite on :5173 and the API by uvicorn on
// :8000. Proxying /api keeps everything same-origin from the browser's point
// of view, so the session cookie just works and no CORS setup is needed.
// In the Docker image nginx plays the same role (see nginx.conf).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
