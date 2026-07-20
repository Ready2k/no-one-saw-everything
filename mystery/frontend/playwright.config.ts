import { defineConfig } from "@playwright/test";

// E2E runs against the PRODUCTION build (vite preview), not the dev server —
// what ships is what is tested. The backend runs with session persistence off
// so E2E state never leaks into (or out of) real investigation saves.
const PYTHON = process.env.MYSTERY_E2E_PYTHON ?? ".venv/bin/python";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // one player at a time; the golden path is a single narrative
  use: {
    baseURL: "http://localhost:4173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `cd ../backend && ${PYTHON} -m uvicorn app.main:app --port 8010`,
      url: "http://localhost:8010/api/config",
      reuseExistingServer: false,
      env: { MYSTERY_SESSION_PERSIST: "0" },
      timeout: 30_000,
    },
    {
      command: "npm run preview",
      url: "http://localhost:4173",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
