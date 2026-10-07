import { test, expect } from '@playwright/test';

/**
 * Journey: S3 source -> AI-built pipeline -> GCS destination -> schedule.
 * IMPORTANT: Selectors below are role/text based GUESSES. I have not seen the Rhombus UI.
 * Record the real flow with `npm run codegen`, then fix each `// TODO(selectors)` line.
 * Rules kept: no waitForTimeout; every wait is on a visible condition or a polled backend value.
 */
const env = (k: string) => { const v = process.env[k]; if (!v) throw new Error(`missing env ${k}`); return v; };

test.describe.serial('S3 -> AI pipeline -> GCS -> schedule', () => {
  test('connect S3 as a source', async ({ page }) => {
    await page.goto('/');                                                         // TODO(selectors)
    await page.getByRole('button', { name: /connect|add (data )?source|integrations/i }).first().click();
    await page.getByText(/amazon s3|\bs3\b/i).first().click();
    await page.getByLabel(/access key id/i).fill(env('AWS_ACCESS_KEY_ID'));
    await page.getByLabel(/secret/i).fill(env('AWS_SECRET_ACCESS_KEY'));
    await page.getByLabel(/bucket/i).fill(env('S3_BUCKET'));
    await page.getByRole('button', { name: /connect|save|test/i }).click();
    await expect(page.getByText(/connected|success/i).first()).toBeVisible();      // real outcome
    await expect(page.getByText(env('S3_KEY'))).toBeVisible();                     // our file is listed
  });

  test('negative: bad S3 credentials are rejected with a clear message', async ({ page }) => {
    await page.goto('/');                                                         // TODO(selectors)
    await page.getByRole('button', { name: /connect|add (data )?source|integrations/i }).first().click();
    await page.getByText(/amazon s3|\bs3\b/i).first().click();
    await page.getByLabel(/access key id/i).fill('AKIAINVALIDINVALID00');
    await page.getByLabel(/secret/i).fill('invalid-secret');
    await page.getByLabel(/bucket/i).fill(env('S3_BUCKET'));
    await page.getByRole('button', { name: /connect|save|test/i }).click();
    await expect(page.getByText(/invalid|denied|failed|unauthori[sz]ed|error/i).first()).toBeVisible();
    await expect(page.getByText(/connected successfully/i)).toHaveCount(0);
  });

  test('AI builder creates a cleaning pipeline (prompt only, no manual transforms)', async ({ page }) => {
    await page.goto('/');                                                         // TODO(selectors)
    await page.getByRole('button', { name: /new (pipeline|project)|create/i }).first().click();
    await page.getByText(env('S3_KEY')).first().click();
    const chat = page.getByRole('textbox', { name: /message|prompt|ask/i });
    await chat.fill(env('PIPELINE_PROMPT'));
    await chat.press('Enter');
    // wait for the builder to finish: a pipeline step list / preview appears, and the busy indicator is gone
    await expect(page.getByTestId?.('pipeline-steps') ?? page.getByText(/step|transform/i).first()).toBeVisible({ timeout: 5 * 60_000 });
    await expect(page.getByRole('progressbar')).toHaveCount(0, { timeout: 5 * 60_000 });
    // outcome assertion: the preview contains no duplicate order_id values
    const ids = await page.locator('table tbody tr td:first-child').allInnerTexts();   // TODO(selectors)
    expect(ids.length).toBeGreaterThan(0);
    expect(new Set(ids).size).toBe(ids.length);
  });

  test('set Google Cloud Storage as destination', async ({ page }) => {
    await page.goto('/');                                                         // TODO(selectors)
    await page.getByRole('button', { name: /destination|export|output/i }).first().click();
    await page.getByText(/google cloud storage|\bgcs\b/i).first().click();
    await page.getByLabel(/bucket/i).fill(env('GCS_BUCKET'));
    await page.getByLabel(/service account|credentials|json/i)
      .setInputFiles(env('GCS_SERVICE_ACCOUNT_JSON_PATH'));
    await page.getByRole('button', { name: /save|connect|test/i }).click();
    await expect(page.getByText(/connected|saved|success/i).first()).toBeVisible();
  });

  test('schedule the pipeline and see it listed as active', async ({ page }) => {
    await page.goto('/');                                                         // TODO(selectors)
    await page.getByRole('button', { name: /schedule/i }).first().click();
    await page.getByLabel(/name/i).fill(env('SCHEDULE_NAME'));
    await page.getByLabel(/frequency|interval|repeat/i).selectOption({ label: /hour/i } as any);
    await page.getByRole('button', { name: /save|create|enable/i }).click();
    const row = page.getByRole('row', { name: new RegExp(env('SCHEDULE_NAME')) });
    await expect(row).toBeVisible();
    await expect(row.getByText(/active|enabled|scheduled/i)).toBeVisible();
  });

  test('a scheduled run completes successfully (baseline)', async ({ page }) => {
    await page.goto('/');                                                         // TODO(selectors)
    await page.getByRole('link', { name: /runs|history|schedules/i }).first().click();
    // poll the UI instead of sleeping; reload until the newest run reaches a terminal state
    await expect.poll(async () => {
      await page.reload();
      return (await page.getByRole('row').nth(1).innerText()).toLowerCase();
    }, { timeout: 90 * 60_000, intervals: [30_000] }).toMatch(/success|completed|failed|error/);
    await expect(page.getByRole('row').nth(1)).toContainText(/success|completed/i);
  });
});
