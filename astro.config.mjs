import tailwind from "@tailwindcss/vite";
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://alguimo.github.io",
  base: process.env.GITHUB_ACTIONS ? "/howlongwithoutraids" : "/",
  output: "static",
  vite: {
    plugins: [tailwind()],
    build: {
      chunkSizeWarningLimit: 700,
    },
  },
});
