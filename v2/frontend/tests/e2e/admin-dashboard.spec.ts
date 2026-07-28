import { expect, test, type Page } from "@playwright/test";

const SOURCES_URL = "**/api/v2/admin/source-records/pending";
const REPORTS_URL = "**/api/v2/admin/reports/pending";

const PENDING_SOURCES_RESPONSE = {
  total: 2,
  items: [
    {
      id: 1,
      provider: "oshiete",
      external_id: "tokyo-station-01",
      name: "東京駅便器詳細",
      address: "東京都千代田区丸の内1-9-1",
      latitude: 35.6812,
      longitude: 139.7671,
      candidates: [
        {
          facility_id: 1001,
          name: "東京駅構内トイレ",
          address: "東京都千代田区丸の内",
          distance_m: 50,
          candidate_score: 0.92,
        },
        {
          facility_id: 1002,
          name: "東京駅八重洲口トイレ",
          address: "東京都中央区八重洲",
          distance_m: 200,
          candidate_score: 0.45,
        },
      ],
    },
    {
      id: 2,
      provider: "google",
      external_id: "ginza-washlet-99",
      name: "銀座モダントイレ",
      address: "東京都中央区銀座4-2-1",
      latitude: 35.6712,
      longitude: 139.7651,
      candidates: [
        {
          facility_id: 1003,
          name: "銀座四丁目公衆トイレ",
          address: "東京都中央区銀座",
          distance_m: 30,
          candidate_score: 0.88,
        },
      ],
    },
  ],
};

const PENDING_REPORTS_RESPONSE = {
  total: 1,
  items: [
    {
      id: 101,
      facility_id: 1001,
      name: "東京駅構内トイレ",
      address: "東京都千代田区丸の内",
      report_type: "broken",
      note: "3番線ホームのトイレが故障しています",
    },
  ],
};

async function mockPendingApi(
  page: Page,
  sources = PENDING_SOURCES_RESPONSE,
  reports = PENDING_REPORTS_RESPONSE,
) {
  await page.route(SOURCES_URL, async (route) => {
    await route.fulfill({ json: sources });
  });
  await page.route(REPORTS_URL, async (route) => {
    await route.fulfill({ json: reports });
  });
}

async function replacePendingApi(
  page: Page,
  sourceHandler: Parameters<Page["route"]>[1],
  reportHandler: Parameters<Page["route"]>[1],
) {
  await page.unroute(SOURCES_URL);
  await page.unroute(REPORTS_URL);
  await page.route(SOURCES_URL, sourceHandler);
  await page.route(REPORTS_URL, reportHandler);
}

function reportCard(page: Page) {
  return page.locator(".admin-card").filter({
    hasText: "3番線ホームのトイレが故障しています",
  });
}

test.describe("admin dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await mockPendingApi(page);
    await page.goto("/admin");
  });

  test("loads admin page shell", async ({ page }) => {
    await expect(page.locator("h1")).toHaveText("データ品質管理");
    await expect(page.locator('a[href="/"]')).toHaveText("公開マップへ戻る");
  });

  test("prompts for admin key", async ({ page }) => {
    await expect(page.locator('input[aria-label="管理APIキー"]')).toBeVisible();
    await expect(page.locator('button:has-text("データを読み込む")')).toBeVisible();
    await expect(page.getByText("管理キーを入力してください。")).toBeVisible();
  });

  test("loads and displays pending sources after key entry", async ({ page }) => {
    await page.locator('input[aria-label="管理APIキー"]').fill("test-admin-key");
    await page.locator('button:has-text("データを読み込む")').click();
    await expect(page.getByText("未解決ソース2件")).toBeVisible();
    await expect(page.getByText("東京駅便器詳細")).toBeVisible();
    await expect(page.getByText("銀座モダントイレ")).toBeVisible();
  });

  test("shows candidate matching options for each source", async ({ page }) => {
    await page.locator('input[aria-label="管理APIキー"]').fill("test-admin-key");
    await page.locator('button:has-text("データを読み込む")').click();
    const firstCandidate = page.locator(".candidate").first();
    await expect(firstCandidate.locator("strong")).toHaveText("東京駅構内トイレ");
    await expect(firstCandidate).toContainText("候補度92%");
    await expect(firstCandidate.locator('button:has-text("この施設に統合")')).toBeVisible();
  });

  test("shows new facility and reject buttons", async ({ page }) => {
    await page.locator('input[aria-label="管理APIキー"]').fill("test-admin-key");
    await page.locator('button:has-text("データを読み込む")').click();
    const firstCard = page.locator(".admin-card").first();
    await expect(firstCard.locator('button:has-text("新規施設")')).toBeVisible();
    await expect(firstCard.locator('button:has-text("却下")')).toBeVisible();
  });

  test("displays pending reports section", async ({ page }) => {
    await page.locator('input[aria-label="管理APIキー"]').fill("test-admin-key");
    await page.locator('button:has-text("データを読み込む")').click();
    await expect(page.getByText("ユーザー報告")).toBeVisible();
    await expect(page.getByText("未処理報告1件")).toBeVisible();
    await expect(reportCard(page).getByText("東京駅構内トイレ")).toBeVisible();
    await expect(page.getByText("3番線ホームのトイレが故障しています")).toBeVisible();
  });

  test("shows accept and reject buttons for each report", async ({ page }) => {
    await page.locator('input[aria-label="管理APIキー"]').fill("test-admin-key");
    await page.locator('button:has-text("データを読み込む")').click();
    await expect(reportCard(page).locator('button:has-text("承認")')).toBeVisible();
    await expect(reportCard(page).locator('button:has-text("却下")')).toBeVisible();
  });

  test("shows empty state when no sources or reports", async ({ page }) => {
    await replacePendingApi(
      page,
      async (route) => route.fulfill({ json: { total: 0, items: [] } }),
      async (route) => route.fulfill({ json: { total: 0, items: [] } }),
    );
    await page.locator('input[aria-label="管理APIキー"]').fill("test-admin-key");
    await page.locator('button:has-text("データを読み込む")').click();
    await expect(page.getByText("未解決ソースはありません。")).toBeVisible();
    await expect(page.getByText("未処理報告はありません。")).toBeVisible();
  });

  test("shows error when API key is invalid", async ({ page }) => {
    await replacePendingApi(
      page,
      async (route) => route.fulfill({ status: 403 }),
      async (route) => route.fulfill({ status: 403 }),
    );
    await page.locator('input[aria-label="管理APIキー"]').fill("wrong-key");
    await page.locator('button:has-text("データを読み込む")').click();
    await expect(page.getByText("管理キーまたはバックエンド接続を確認してください。")).toBeVisible();
  });
});
