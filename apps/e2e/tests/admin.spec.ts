import { expect, test } from "@playwright/test";

const SHOT = "artifacts";

test("admin dashboard renders metrics and refund audit", async ({ page }) => {
  await page.goto("/admin");

  await expect(page.getByText("Reasoning Dashboard")).toBeVisible();
  // Metrics strip loads via the API (seeded data guarantees refunds exist).
  await expect(page.getByText("Approval rate")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Refund audit")).toBeVisible();

  await page.screenshot({ path: `${SHOT}/04-admin-dashboard.png`, fullPage: true });
});
