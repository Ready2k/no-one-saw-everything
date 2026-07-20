/**
 * The golden path, end to end, against the production build:
 * rewind → pin → inspect → interview → observe → challenge → board → accuse → reveal.
 *
 * Plus the invariant that shapes the whole codebase, asserted at the DOM:
 * before the accusation, nothing solution-shaped may appear anywhere in the
 * page — not the explanation, not an epilogue, not the guilt sentence. Suspect
 * NAMES are public (Clara is on the suspect board); what must never leak is
 * the text that says she did it.
 */
import { expect, Page, test } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const here = path.dirname(fileURLToPath(import.meta.url));
const solution = JSON.parse(
  fs.readFileSync(path.join(here, "../../backend/app/data/case_001/solution.json"), "utf-8")
);

// Distinctive solution-only strings: if any of these render before the reveal,
// the truth has leaked to the client.
const SOLUTION_MARKERS: string[] = [
  (solution.explanation as string).slice(0, 60),
  ...Object.values(solution.epilogues ?? {}).map((t) => (t as string).slice(0, 60)),
  "killed Marcus Bell",
];

async function expectNoTruthInDom(page: Page) {
  const html = await page.content();
  for (const marker of SOLUTION_MARKERS) {
    expect(html, `solution text leaked into the DOM before reveal: "${marker}"`).not.toContain(
      marker
    );
  }
}

test("golden path: investigate case_001 and convict Clara", async ({ page }) => {
  // Fresh detective every run; skip the one-time cinematic intro.
  const token = `e2e_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
  await page.addInitScript(
    ([t]) => {
      localStorage.setItem("mystery_session_id", t);
      localStorage.setItem("mystery_intro_seen_case_001", "1");
      // Skip cinematic overlays (rewind briefing, transitions) — E2E tests the
      // investigation loop, not the cutscenes.
      localStorage.setItem("mystery_cinematics", "off");
      localStorage.setItem("mystery_rewind_briefing_case_001", "1");
    },
    [token]
  );

  await page.goto("/");
  await page
    .getByRole("button", { name: /Start Investigation|Continue Investigation/ })
    .click();

  // --- Case File (overview) -----------------------------------------------
  await expect(page.getByRole("button", { name: "Rewind" })).toBeVisible();
  await expectNoTruthInDom(page);

  // --- Rewind: pin the rear-door sighting (discovers clue_rear_door) ------
  await page.getByRole("button", { name: "Rewind" }).click();
  const rearDoorRow = page
    .locator("li, tr, .event-row, .rewind-event, div")
    .filter({ hasText: "rear door opens briefly" })
    .filter({ has: page.getByRole("button", { name: /^Pin/ }) })
    .last();
  await rearDoorRow.getByRole("button", { name: /^Pin/ }).click();
  await expect(page.getByRole("button", { name: "Pinned" }).first()).toBeVisible();
  await expectNoTruthInDom(page);

  // --- Places: search the storage room with the magnifier -----------------
  await page.getByRole("button", { name: "Places" }).click();
  await page.getByRole("button", { name: /Cafe Storage Room/ }).click();
  const scene = page.locator(".magnifying-container");
  await expect(scene).toBeVisible();

  // Sweep the scene until the lens sits over a hotspot, then click it.
  const box = await scene.boundingBox();
  expect(box).toBeTruthy();
  let discovered = false;
  outer: for (let gy = 1; gy <= 8; gy++) {
    for (let gx = 1; gx <= 8; gx++) {
      await page.mouse.move(box!.x + (box!.width * gx) / 9, box!.y + (box!.height * gy) / 9);
      if (await scene.evaluate((el) => el.classList.contains("hotspot-active"))) {
        await page.mouse.down();
        await page.mouse.up();
        discovered = true;
        break outer;
      }
    }
  }
  expect(discovered, "no evidence hotspot found in the storage room sweep").toBe(true);
  await expectNoTruthInDom(page);

  // --- Suspects: interview Clara, observe her, then challenge her ---------
  await page.getByRole("button", { name: "Suspects" }).click();
  await page.getByText("Clara Wells").first().click();

  await page.getByRole("button", { name: /^Ask alibi/ }).click();
  // Her alibi claim (the fountain) lands in the challenge builder.
  const fountainClaim = page
    .locator(".confront-option")
    .filter({ hasText: /fountain/i })
    .first();
  await expect(fountainClaim).toBeVisible();
  await expectNoTruthInDom(page);

  await page.getByRole("button", { name: /Observe/ }).click();
  await expectNoTruthInDom(page);

  // Challenge: her fountain story against the rear-door sighting.
  await fountainClaim.locator('input[type="radio"]').check();
  await page
    .locator(".confront-option")
    .filter({ hasText: "Figure leaving by the rear door" })
    .locator('input[type="checkbox"]')
    .check();
  await page.getByRole("button", { name: "Put it to Clara" }).first().click();
  await expect(page.locator(".challenge-response")).toBeVisible();
  await expectNoTruthInDom(page);

  // --- Case board: her claim and the evidence are filed together ----------
  await page.getByRole("button", { name: "Case Board" }).click();
  await expect(page.getByText("Clara Wells").first()).toBeVisible();
  await expectNoTruthInDom(page);

  // --- Accuse and reveal ---------------------------------------------------
  await page.getByRole("button", { name: "Accuse", exact: false }).first().click();
  await page.locator(".custom-select-trigger").click();
  await page.locator(".custom-select-option").filter({ hasText: "Clara Wells" }).click();
  await page.getByRole("button", { name: "Submit accusation" }).click();

  // Submitting only waits for the click itself, not for the accusation POST to
  // resolve and the ceremony to mount — wait for it explicitly (auto-retrying)
  // before touching its controls, or an immediate, unretried isVisible() check
  // races the mount and finds nothing.
  const nextBtn = page.getByRole("button", { name: "Next", exact: true });
  await expect(nextBtn).toBeVisible({ timeout: 15_000 });

  // The ceremony plays and auto-advances; step through it with Next until the
  // breakdown's verdict card appears. (A blind force-click on Skip can land on
  // the breakdown's own "Play again" button after a re-render, resetting the
  // whole session — so this walks Next instead of skipping.)
  for (let i = 0; i < 12; i++) {
    if (await page.locator(".verdict-card h1").isVisible().catch(() => false)) break;
    if (!(await nextBtn.isVisible().catch(() => false))) break;
    await nextBtn.click();
    await page.waitForTimeout(400);
  }

  // Only NOW may the truth appear.
  await expect(page.locator(".verdict-card h1")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".verdict-card h1")).toHaveText(
    /Case closed|Right killer|Partly there|right name/
  );
  const finalHtml = await page.content();
  expect(finalHtml).toContain("killed Marcus Bell");
});
