import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    // e2e/ holds Playwright specs, not vitest unit tests — vitest's default
    // include glob (**/*.test.ts) doesn't match them, but its default EXCLUDE
    // doesn't skip them either, and Playwright's test() throws when called
    // outside its own runner. Scope vitest to src/ explicitly.
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
