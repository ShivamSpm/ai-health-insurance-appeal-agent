import os from "node:os";
import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

// The smoke test runs its own API on a fresh database with the scripted model
// (no LLM calls), and a production build of the UI pointed at it. Ports differ
// from the dev servers, so both can run at once.
const API_PORT = 8001;
const WEB_PORT = 3001;
const tmp = path.join(os.tmpdir(), `appeal-e2e-${Date.now()}`);

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: `uv run --project ../backend appeal-agent serve --port ${API_PORT} --fake-model --db "${path.join(tmp, "runs.db")}"`,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      env: {
        APPEAL_CORS_ORIGINS: `http://localhost:${WEB_PORT}`,
        APPEAL_USER_CASES_DIR: path.join(tmp, "user_cases"),
      },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npm run build && npm run start -- -p ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      env: { NEXT_PUBLIC_API_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 240_000,
    },
  ],
});
