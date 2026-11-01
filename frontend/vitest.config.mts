import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } },
  oxc: { jsx: { runtime: "automatic" } },
  test: {
    environment: "jsdom",
    include: ["services/**/*.test.ts", "features/**/*.test.{ts,tsx}", "components/**/*.test.tsx"],
    restoreMocks: true,
    unstubGlobals: true,
    unstubEnvs: true,
  },
});
