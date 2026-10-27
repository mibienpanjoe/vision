import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "packaged-restore.spec.ts",
  workers: 1,
  use: { baseURL: process.env.VISION_TEST_RESTORE_ORIGIN, browserName: "chromium" },
});
