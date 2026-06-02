import { defineConfig } from "@playwright/test";

// Dev-only E2E config. baseURL points at the nginx-served frontend inside the
// e2e compose network. Artifacts (screenshots, traces, HTML report) land in
// ./artifacts, which is bind-mounted to the host for manual review.
export default defineConfig({
  testDir: "./tests",
  outputDir: "./artifacts/test-results",
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  reporter: [
    ["list"],
    ["html", { outputFolder: "./artifacts/report", open: "never" }],
    ["junit", { outputFile: "./artifacts/junit.xml" }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://frontend:80",
    screenshot: "only-on-failure",
    trace: "on",
  },
});
