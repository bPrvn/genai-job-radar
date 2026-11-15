import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" makes the build work at any path, e.g. https://<user>.github.io/genai-job-radar/
export default defineConfig({ base: "./", plugins: [react()] });
