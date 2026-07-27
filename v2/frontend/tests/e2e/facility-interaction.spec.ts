import { expect, test, type Page } from "@playwright/test";

const PLACE = {
  id: 1,
  facility_id: 1001,
  source_record_id: null,
  name: "永田町公共施設トイレ",
  address: "東京都千代田区永田町一丁目7番1号",
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
};

const PLACES_RESPONSE = { items: [PLACE] };
const STATS_RESPONSE = {
  record_count: 1,
  scored_count: 1,
  average_score: 85,
  published_at: "2026-07-20T00:00:00+09:00",
};
const FACETS_RESPONSE = {
  prefectures: [{ value: "東京都", count: 1 }],
  categories: [{ value: "公共施設", count: 1 }],
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

async function waitForInitialResults(page: Page) {
  await expect(page.getByRole("list", { name: "検索結果" })).toHaveAttribute("aria-busy", "false");
  await expect(page.getByRole("listitem")).toHaveCount(1);
}

test.describe("facility card interaction", () => {
  test("shows score rationale on click and hides on re-click", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await waitForInitialResults(page);

    const summary = page.getByText("評価の根拠を見る");
    const rationaleBody = page.locator(".score-rationale-body");

    await expect(rationaleBody).not.toBeVisible();
    await summary.click();
    await expect(rationaleBody).toBeVisible();
    await summary.click();
    await expect(rationaleBody).not.toBeVisible();
  });

  test("displays evidence fields in score rationale", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await waitForInitialResults(page);

    await page.getByText("評価の根拠を見る").click();
    const dl = page.locator(".score-rationale-body dl");

    const dlFirst = dl.first();
    await expect(dlFirst.getByText("きれい度")).toBeVisible();
    await expect(dlFirst.getByText("信頼度")).toBeVisible();
    await expect(dlFirst.getByText("確認状態")).toBeVisible();
    await expect(dlFirst.getByText("最終確認")).toBeVisible();
    await expect(dlFirst.getByText("情報源")).toBeVisible();
  });
});

test.describe("facility report submission", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await waitForInitialResults(page);
    await page.getByRole("button", { name: "情報を報告" }).click();
    await expect(page.locator(".report-form")).toBeVisible();
  });

  test("opens report form and sends a report", async ({ page }) => {
    await page.route("**/api/v2/facilities/1001/reports", async (route) => {
      await route.fulfill({ status: 200, json: { ok: true } });
    });

    await page.getByLabel("報告の種類").selectOption("broken");
    await page.getByLabel("報告内容").fill("便器が故障していました");
    await page.getByRole("button", { name: "報告を送信" }).click();

    await expect(page.locator(".form-status")).toHaveText(
      "報告を受け付けました。確認後に反映します。",
    );
  });

  test("shows error message on API failure", async ({ page }) => {
    await page.route("**/api/v2/facilities/1001/reports", async (route) => {
      await route.fulfill({
        status: 429,
        json: { detail: "短期間に同じ施設への報告が多すぎます" },
      });
    });

    await page.getByLabel("報告の種類").selectOption("closed");
    await page.getByLabel("報告内容").fill("閉鎖していました");
    await page.getByRole("button", { name: "報告を送信" }).click();

    await expect(page.locator(".form-status")).toHaveText(
      "短期間に同じ施設への報告が多すぎます",
    );
  });
});
