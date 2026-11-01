import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    channel: process.env.E2E_BROWSER_CHANNEL || "chrome",
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:3010",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: process.env.E2E_BASE_URL ? undefined : {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3010",
    url: "http://127.0.0.1:3010",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: { NEXT_PUBLIC_API_BASE_URL: process.env.COGNIFLOW_INTEGRATION_URL || "http://127.0.0.1:8000" },
  },
});
