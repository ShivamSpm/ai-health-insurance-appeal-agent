import { expect, test } from "@playwright/test";

// The main review flow, against the scripted model: open a case, run the agent,
// watch the timeline, follow a citation into the plan, edit and save the draft.
test("open a case, run it, follow a citation, edit and save the draft", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "case-031" })).toBeVisible();
  await page.getByRole("link", { name: "case-031" }).click();

  // Fresh database: no runs yet.
  await expect(page.getByText("No runs yet for this case.")).toBeVisible();
  await page.getByRole("button", { name: "Run live" }).click();

  // The timeline streams in, then the findings and the letter appear.
  const steps = page.getByRole("list", { name: "Agent steps" });
  await expect(steps.getByText("submit_findings", { exact: true })).toBeVisible();
  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
  await expect(page.getByText("Prior authorization", { exact: true })).toBeVisible();
  await expect(page.getByText("Worth appealing")).toBeVisible();

  // A citation in the letter opens that section of the plan.
  await page.getByRole("button", { name: "ppo-6.4" }).last().click();
  await expect(page.getByRole("tab", { name: "Plan" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator('[data-chunk="ppo-6.4"]')).toBeInViewport();

  // Edit, save as a version, and see the change against the agent's draft.
  await page.getByRole("tab", { name: "Edit" }).click();
  const editor = page.getByRole("textbox", { name: "Appeal letter" });
  await editor.fill(`${await editor.inputValue()}\n\nReviewed by the member.`);
  await expect(page.getByText("Unsaved changes.")).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved as edit 1.")).toBeVisible();

  await page.getByRole("tab", { name: "Changes" }).click();
  await expect(page.locator("ins")).toContainText("Reviewed by the member.");
});
