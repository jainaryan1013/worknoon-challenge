import { expect, test } from "@playwright/test";

// Milestone screenshots are written after a STABLE state is reached (badge /
// selector visible), never mid-stream, so they aren't half-rendered frames.
const SHOT = "artifacts";

test("verify and refund a single item end to end", async ({ page }) => {
  await page.goto("/chat");

  await page.getByLabel("Message").fill(
    "Verify ORD-1001 ada@example.com and refund my Wireless Mouse",
  );
  await page.getByRole("button", { name: "Send" }).click();

  // exact:true → just the badge label <span>Approved</span>, not the reason text.
  const badge = page.getByText("Approved", { exact: true });
  await expect(badge).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: `${SHOT}/01-refund-approved.png`, fullPage: true });
});

test("return selector flow: present options, confirm, approve", async ({ page }) => {
  await page.goto("/chat");

  await page.getByLabel("Message").fill(
    "Verify ORD-1005 eve@example.com — I'd like to return an item",
  );
  await page.getByRole("button", { name: "Send" }).click();

  const confirm = page.getByRole("button", { name: "Confirm return" });
  await expect(confirm).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: `${SHOT}/02-return-selector.png`, fullPage: true });

  // Pick the first (eligible) row, then confirm.
  await page.getByRole("checkbox").first().check();
  await confirm.click();

  await expect(page.getByText("Approved", { exact: true })).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: `${SHOT}/03-return-approved.png`, fullPage: true });
});
