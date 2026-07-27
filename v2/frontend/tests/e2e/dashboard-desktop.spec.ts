import { expect, test, type Page } from "@playwright/test";

const PLACES_RESPONSE = {
  items: [
    {
      id: 1,
      facility_id: 1001,
      source_record_id: null,
      name: "東京駅中央トイレ",
      address: "東京都千代田区丸の内一丁目9番1号",
      prefecture: "東京都",
      category: "駅",
      toilet_score: 92,
      confidence: 95,
      trust_score: 94,
      source_count: 8,
      verification_status: "confirmed",
      last_verified_at: "2026-07-20T00:00:00Z",
      distance_m: null,
      latitude: 35.6812,
      longitude: 139.7671,
      attributes: { wheelchair: "yes", changing_table: "yes", fee: "no", open_24h: "yes" },
    },
    {
      id: 2,
      facility_id: 1002,
      source_record_id: null,
      name: "新宿西口公衆トイレ",
      address: "東京都新宿区西新宿一丁目",
      prefecture: "東京都",
      category: "公共施設",
      toilet_score: 65,
      confidence: 80,
      trust_score: 72,
      source_count: 2,
      verification_status: "confirmed",
      last_verified_at: "2026-06-15T00:00:00Z",
      distance_m: 3200,
      latitude: 35.6896,
      longitude: 139.7006,
      attributes: { wheelchair: "yes" },
    },
    {
      id: 3,
      facility_id: 1003,
      source_record_id: null,
      name: "上野公園公衆トイレ",
      address: "東京都台東区上野公園",
      prefecture: "東京都",
      category: "公園",
      toilet_score: 45,
      confidence: 60,
      trust_score: 52,
      source_count: 1,
      verification_status: "stale",
      last_verified_at: "2025-01-10T00:00:00Z",
      distance_m: 5000,
      latitude: 35.7148,
      longitude: 139.7732,
      attributes: {},
    },
  ],
};

const STATS_RESPONSE = {
  record_count: 1349,
  scored_count: 1178,
  average_score: 58.4,
  published_at: "2026-07-20T00:00:00+09:00",
};

const FACETS_RESPONSE = {
  prefectures: [
    { value: "東京都", count: 126 },
    { value: "埼玉県", count: 124 },
    { value: "神奈川県", count: 110 },
  ],
  categories: [
    { value: "駅", count: 180 },
    { value: "公園", count: 95 },
    { value: "公共施設", count: 72 },
  ],
};

async function mockApi(page: Page) {
  await page.route("**/api/v2/places**", async (route) => {
    await route.fulfill({ json: PLACES_RESPONSE });
  });
  await page.route("**/api/v2/stats", async (route) => {
    await route.fulfill({ json: STATS_RESPONSE });
  });
  await page.route("**/api/v2/facets", async (route) => {
    await route.fulfill({ json: FACETS_RESPONSE });
  });
  await page.route("**/tile.openstreetmap.org/**", async (route) => {
    await route.abort();
  });
  await page.route("**/unpkg.com/**", async (route) => {
    await route.abort();
  });
}

test.describe("desktop layout at 1280px width", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await page.waitForFunction(() => {
      const el = document.querySelector('[role="list"]');
      return el && el.querySelectorAll('[role="listitem"]').length === 3;
    });
  });

  test("no horizontal scroll on the full page", async ({ page }) => {
    const hasNoScroll = await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    );
    expect(hasNoScroll).toBe(true);
  });

  test("filter controls are laid out in multi-column grid", async ({ page }) => {
    const filterRow = page.locator(".filter-row");
    const gridCols = await filterRow.evaluate(
      (el) => getComputedStyle(el).gridTemplateColumns,
    );
    expect(gridCols).toContain(" ");
  });

  test("checkboxes are laid out in multi-column grid", async ({ page }) => {
    const checks = page.locator(".checks");
    const gridCols = await checks.evaluate(
      (el) => getComputedStyle(el).gridTemplateColumns,
    );
    expect(gridCols).toContain(" ");
  });

  test("map occupies visible area without breaking layout", async ({ page }) => {
    const mapRegion = page.locator('[role="region"][aria-label="地図"]');
    await expect(mapRegion).toBeVisible();
    const box = await mapRegion.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThan(300);
  });
});

test.describe("desktop facility cards at 1280px", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await page.waitForFunction(() => {
      const el = document.querySelector('[role="list"]');
      return el && el.querySelectorAll('[role="listitem"]').length === 3;
    });
  });

  test("facility card content fits card width", async ({ page }) => {
    const cards = page.locator(".card");
    const count = await cards.count();
    expect(count).toBe(3);
    for (let i = 0; i < count; i++) {
      const card = cards.nth(i);
      const cardBox = await card.boundingBox();
      expect(cardBox).not.toBeNull();
      const cardWidth = cardBox!.width;
      const nameWidth = await card
        .locator("h2")
        .evaluate((el) => el.scrollWidth);
      expect(nameWidth).toBeLessThanOrEqual(cardWidth);
    }
  });

  test("badges are visible for scored and unscored facilities", async ({ page }) => {
    const cards = page.locator(".card");
    const firstBadges = cards.nth(0).locator(".badges");
    await expect(firstBadges.locator(".badge").first()).toBeVisible();

    const lastBadges = cards.nth(2).locator(".badges");
    await expect(lastBadges.locator(".badge").first()).toBeVisible();
  });

  test("score rationale disclosure works for all cards", async ({ page }) => {
    const cards = page.locator(".card");
    const count = await cards.count();
    for (let i = 0; i < count; i++) {
      const summary = cards.nth(i).locator("summary");
      await summary.click();
      const body = cards.nth(i).locator(".score-rationale-body");
      await expect(body).toBeVisible();
      await summary.click();
      await expect(body).not.toBeVisible();
    }
  });

  test("report form fits in viewport when open", async ({ page }) => {
    const firstCard = page.locator(".card").first();
    await firstCard.locator('button:has-text("情報を報告")').click();
    await expect(firstCard.locator(".report-form")).toBeVisible();
    const hasNoScroll = await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    );
    expect(hasNoScroll).toBe(true);
  });

  test("all card action links are accessible", async ({ page }) => {
    const firstCard = page.locator(".card").first();
    await expect(firstCard.locator('a[href*="google.com/maps"]')).toBeVisible();
    await expect(firstCard.locator('button:has-text("情報を報告")')).toBeVisible();
  });

  test("distance is shown when available", async ({ page }) => {
    const secondCard = page.locator(".card").nth(1);
    await expect(secondCard).toContainText("約3200m");
  });

  test("stats display fits viewport", async ({ page }) => {
    const stats = page.locator(".stats");
    await expect(stats).toBeVisible();
    const box = await stats.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x + box!.width).toBeLessThanOrEqual(1280);
  });

  test("search results have correct ARIA semantics", async ({ page }) => {
    const list = page.locator('[role="list"]');
    await expect(list).toHaveAttribute("aria-label", "検索結果");
    await expect(list).toHaveAttribute("aria-busy", "false");
    const items = list.locator('[role="listitem"]');
    await expect(items).toHaveCount(3);
  });
});
