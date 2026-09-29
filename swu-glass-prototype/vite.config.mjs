import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  build: {
    outDir: "dist/client",
  },
  optimizeDeps: {
    include: ["react", "react-dom/client"],
  },
  server: {
    host: "127.0.0.1",
    proxy: {"/api": {target: process.env.SWU_API_TARGET || "http://127.0.0.1:8765", changeOrigin: true,
      configure(proxy) { proxy.on("proxyReq", (outgoing, incoming) => {
        const origin=incoming.headers.origin;
        if (!origin || ["http://127.0.0.1:5180","http://localhost:5180"].includes(origin)) outgoing.removeHeader("origin");
      }); }
    }},
    allowedHosts: ["terminal.local"],
    warmup: {
      clientFiles: ["./src/main.jsx"],
    },
  },
  plugins: [react()],
});
