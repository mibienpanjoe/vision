import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: { baseURL: "http://127.0.0.1:13000", browserName: "chromium" },
  webServer: {
    command: "pnpm exec next start --hostname 127.0.0.1 --port 13000",
    url: "http://127.0.0.1:13000",
    reuseExistingServer: false,
    timeout: 15000,
  },
});
