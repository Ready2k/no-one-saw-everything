import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.MYSTERY_FRONTEND_PORT ?? 5179),
    proxy: {
      "/api": `http://127.0.0.1:${process.env.MYSTERY_API_PORT ?? 8010}`,
    },
  },
  // `vite preview` serves the production build for E2E; it needs the same
  // API proxy as the dev server or the built app cannot reach the backend.
  preview: {
    port: 4173,
    proxy: {
      "/api": `http://localhost:${process.env.MYSTERY_API_PORT ?? 8010}`,
    },
  },
});
