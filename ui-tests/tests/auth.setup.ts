import { test as setup, expect } from '@playwright/test';
// TODO(selectors): verify against the real login page with `npm run codegen`.
setup('log in once and save session', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: /log ?in|sign ?in/i }).first().click();
  await page.getByLabel(/email/i).fill(process.env.RHOMBUS_EMAIL!);
  await page.getByLabel(/password/i).fill(process.env.RHOMBUS_PASSWORD!);
  await page.getByRole('button', { name: /log ?in|sign ?in|continue/i }).click();
  await expect(page).not.toHaveURL(/login|signin/i);          // real outcome: we left the login page
  await page.context().storageState({ path: '.auth/user.json' });
});
