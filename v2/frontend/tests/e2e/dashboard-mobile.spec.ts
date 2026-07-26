import { expect, test, type Page } from "@playwright/test";

const PLACES_RESPONSE = {
  items: [
    {
      id: 1,
      facility_id: 1001,
      source_record_id: null,
      name: "とても長い名前の公共施設トイレ（サンプル）",
      address: "東京都千代田区永田町一丁目7番1号 とても長い住所のビルディング名が入る場合",
      prefecture: "東京都",
      category: "公共施設",
      toilet_score: 85,
      confidence: 90,
      trust_score: 88,
      source_count: 3,
      verification_status: "confirmed",
      last_verified_at: "2026-07-01T00:00:00Z",
      distance_m: null,
      latitude: 35.6762,
      longitude: 139.6503,
      attributes: { wheelchair: "yes", changing_table: "yes" },
    },
    {
      id: 2,
      facility_id: 1002,
      source_record_id: null,
      name: "未評価トイレ",
      address: "埼玉県さいたま市",
      prefecture: "埼玉県",
      category: "公園",
      toilet_score: null,
      confidence: null,
      trust_score: null,
      source_count: 1,
      verification_status: "pending",
      last_verified_at: null,
      distance_m: 2500,
      latitude: 35.8617,
      longitude: 139.6455,
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
    { value: "埼玉県", count: 124 },
    { value: "東京都", count: 126 },
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

test.describe("mobile layout at 390px width", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await page.waitForFunction(() => {
      const el = document.querySelector('[role="list"]');
      return el && el.querySelectorAll('[role="listitem"]').length === 2;
    });
  });

  test("no horizontal scroll on the full page", async ({ page }) => {
    const hasNoScroll = await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    );
    expect(hasNoScroll).toBe(true);
  });

  test("header content fits within viewport", async ({ page }) => {
    const header = page.locator(".header");
    await expect(header.locator("h1")).toBeVisible();
    await expect(header.locator('a[href="/admin"]')).toBeVisible();
    const headerBox = await header.boundingBox();
    expect(headerBox).not.toBeNull();
    expect(headerBox!.x + headerBox!.width).toBeLessThanOrEqual(390);
  });

  test("filter controls are visible and laid out", async ({ page }) => {
    await expect(page.locator('input[aria-label="施設を検索"]')).toBeVisible();
    await expect(page.locator('select[aria-label="都道府県"]')).toBeVisible();
    await expect(page.locator('select[aria-label="施設カテゴリ"]')).toBeVisible();
    await expect(page.locator('select[aria-label="最低スコア"]')).toBeVisible();
    await expect(page.locator('select[aria-label="最低信頼度"]')).toBeVisible();
    await expect(page.locator('label:has-text("車椅子対応")')).toBeVisible();
    await expect(page.locator('label:has-text("おむつ交換台")')).toBeVisible();
    await expect(page.locator('label:has-text("無料")')).toBeVisible();
    await expect(page.locator('label:has-text("24時間")')).toBeVisible();
    await expect(page.locator('button:has-text("現在地から探す")')).toBeVisible();
  });

  test("filter rows stack into single column", async ({ page }) => {
    const filterRow = page.locator(".filter-row");
    const checks = page.locator(".checks");
    const filterRowColumns = await filterRow.evaluate(
      (el) => getComputedStyle(el).gridTemplateColumns,
    );
    const checksColumns = await checks.evaluate(
      (el) => getComputedStyle(el).gridTemplateColumns,
    );
    expect(filterRowColumns).not.toContain(" ");
  });

  test("guidance text wraps without overflow", async ({ page }) => {
    const guidance = page.locator("#search-guidance");
    await expect(guidance).toBeVisible();
    const box = await guidance.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  });

  test("facility card content fits card width", async ({ page }) => {
    const cards = page.locator(".card");
    const count = await cards.count();
    expect(count).toBe(2);
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

  test("badges wrap inside card", async ({ page }) => {
    const firstCardBadges = page.locator(".card").first().locator(".badges");
    const badgeBox = await firstCardBadges.boundingBox();
    expect(badgeBox).not.toBeNull();
    const firstBadge = firstCardBadges.locator(".badge").first();
    await expect(firstBadge).toBeVisible();
  });

  test("score rationale disclosure does not cause overflow", async ({ page }) => {
    const summary = page.locator("summary:has-text('評価の根拠を見る')").first();
    await summary.click();
    await page.waitForTimeout(300);
    const hasNoScroll = await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    );
    expect(hasNoScroll).toBe(true);
  });

  test("report form stays within viewport", async ({ page }) => {
    const reportBtn = page.locator('button:has-text("情報を報告")').first();
    await reportBtn.click();
    await expect(page.locator(".report-form select")).toBeVisible();
    await expect(page.locator(".report-form textarea")).toBeVisible();
    await expect(page.locator('.report-form button:has-text("報告を送信")')).toBeVisible();
    const hasNoScroll = await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    );
    expect(hasNoScroll).toBe(true);
  });

  test("search results have correct ARIA semantics", async ({ page }) => {
    const list = page.locator('[role="list"]');
    await expect(list).toHaveAttribute("aria-label", "検索結果");
    await expect(list).toHaveAttribute("aria-busy", "false");
    const items = list.locator('[role="listitem"]');
    await expect(items).toHaveCount(2);
    await expect(page.locator('[role="status"][aria-live="polite"]')).toBeVisible();
  });

  test("stats display fits viewport", async ({ page }) => {
    const stats = page.locator(".stats");
    await expect(stats).toBeVisible();
    const box = await stats.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  });

  test("data freshness label is rendered", async ({ page }) => {
    await expect(page.locator(".data-freshness")).toBeVisible();
  });
});

test.describe("accessibility landmarks and keyboard navigation", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await page.waitForFunction(() => {
      const el = document.querySelector('[role="list"]');
      return el && el.querySelectorAll('[role="listitem"]').length === 2;
    });
  });

  test("skip link is first focusable element on Tab", async ({ page }) => {
    await page.keyboard.press("Tab");
    const skipLink = page.locator(".skip-link");
    await expect(skipLink).toBeFocused();
  });

  test("skip link points to main content", async ({ page }) => {
    const skipLink = page.locator(".skip-link");
    await expect(skipLink).toHaveAttribute("href", "#main");
  });

  test("exactly one main landmark exists on public page", async ({ page }) => {
    const mains = page.locator("main");
    await expect(mains).toHaveCount(1);
  });

  test("map region has accessible label", async ({ page }) => {
    const mapRegion = page.locator('[role="region"][aria-label="地図"]');
    await expect(mapRegion).toBeVisible();
  });

  test("focus-visible outline is applied to interactive elements", async ({ page }) => {
    const filterInput = page.locator('input[aria-label="施設を検索"]');
    await filterInput.focus();
    const outline = await filterInput.evaluate(
      (el) => getComputedStyle(el).outline,
    );
    expect(outline).toBeTruthy();
  });
});
