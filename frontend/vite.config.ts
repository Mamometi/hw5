import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dashboard talks to FastAPI on localhost:8000 directly (CORS is allowed
// for http://localhost:5173 in backend/main.py). Override with VITE_API_URL.
//
// React Compiler memoizes components and hooks automatically, so the code
// doesn't need hand-written useMemo/useCallback.
export default defineConfig({
  plugins: [react({ babel: { plugins: [["babel-plugin-react-compiler", { target: "19" }]] } })],
  server: { port: 5173, strictPort: true },
});
