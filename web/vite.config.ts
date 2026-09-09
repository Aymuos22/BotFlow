import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget =
    (env.BOTFLOW_PROXY_TARGET || "http://127.0.0.1:8000").replace(/\/$/, "");

  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        // Used when VITE_API_BASE_URL=/api/botflow (same-origin). Strips prefix; target must be running API.
        "/api/botflow": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          rewrite: (p) => p.replace(/^\/api\/botflow/, "") || "/",
        },
      },
    },
  };
});
