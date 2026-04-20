import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

const backendTarget = process.env.VITE_BACKEND_URL || "http://127.0.0.1:8040";

export default defineConfig({
  base: "/",
  plugins: [react(), tsconfigPaths()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": backendTarget,
      "/health": backendTarget
    }
  },
  build: {
    outDir: "dist",
    sourcemap: true
  }
});
