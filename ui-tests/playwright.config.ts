import { defineConfig } from '@playwright/test';
import 'dotenv/config';
export default defineConfig({
  testDir: './tests',
  timeout: 10 * 60_000,            // AI builder + runs are slow; we wait on conditions, never fixed sleeps
  expect: { timeout: 60_000 },
  workers: 1,                      // tests share one pipeline, so they run serially
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: process.env.RHOMBUS_URL ?? 'https://rhombusai.com', trace: 'retain-on-failure', screenshot: 'only-on-failure', video: 'retain-on-failure' },
  projects: [{ name: 'setup', testMatch: /auth\.setup\.ts/ }, { name: 'e2e', dependencies: ['setup'], use: { storageState: '.auth/user.json' }, testMatch: /pipeline\.spec\.ts/ }],
});
