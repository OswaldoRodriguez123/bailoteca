import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  reporter: "list",
  workers: 1,
  use: {
    baseURL: "http://localhost:4100",
  },
  webServer: {
    // El build prerenderiza (outputMode: "static"); el servidor estático
    // propio (scripts/serve-dist.mjs, stdlib de Node) sirve esa salida.
    command: "npm run build && node scripts/serve-dist.mjs",
    url: "http://localhost:4100",
    reuseExistingServer: !process.env.CI,
    timeout: 600_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
