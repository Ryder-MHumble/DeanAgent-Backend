import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const proxyTarget = process.env.CONSOLE_API_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  base: "./",
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 5174,
    proxy: {
      "/console-api": {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
});
