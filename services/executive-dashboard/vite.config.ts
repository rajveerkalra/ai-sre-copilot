import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 8050,
    proxy: {
      "/proxy/incident": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/proxy\/incident/, ""),
      },
      "/proxy/context": {
        target: "http://localhost:8020",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/proxy\/context/, ""),
      },
      "/proxy/investigation": {
        target: "http://localhost:8031",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/proxy\/investigation/, ""),
      },
      "/proxy/remediation": {
        target: "http://localhost:8032",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/proxy\/remediation/, ""),
      },
      "/proxy/auth": {
        target: "http://localhost:8060",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/proxy\/auth/, ""),
      },
    },
  },
});
