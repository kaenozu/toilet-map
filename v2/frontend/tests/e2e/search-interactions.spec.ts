import { expect, test, type Page } from "@playwright/test";

const PLACES_RESPONSE = {
  items: [
    {
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
  prefectures: [{ value: "東京都", count: 126 }],
  categories: [{ value: "公共施設", count: 72 }],
};

async function mockApi(page: Page, observedPlaceRequests: URL[]) {
  await page.route("**/api/v2/places**", async (route) => {
    observedPlaceRequests.push(new URL(route.request().url()));
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

test("filter interactions are serialized into the places API request", async ({ page }) => {
  const observedPlaceRequests: URL[] = [];
  await mockApi(page, observedPlaceRequests);
  await page.goto("/");
  await waitForInitialResults(page);

  await page.getByLabel("施設を検索").fill(" 千代田 ");
  await page.getByLabel("都道府県").selectOption("東京都");
  await page.getByLabel("施設カテゴリ").selectOption("公共施設");
  await page.getByLabel("最低スコア").selectOption("80");
  await page.getByLabel("最低信頼度").selectOption("80");
  await page.getByRole("checkbox", { name: "車椅子対応" }).check();
  await page.getByRole("checkbox", { name: "おむつ交換台" }).check();
  await page.getByRole("checkbox", { name: "無料" }).check();
  await page.getByRole("checkbox", { name: "24時間" }).check();

  await expect.poll(() =>
    observedPlaceRequests.some(({ searchParams }) =>
      searchParams.get("limit") === "2000" &&
      searchParams.get("q") === "千代田" &&
      searchParams.get("prefecture") === "東京都" &&
      searchParams.get("category") === "公共施設" &&
      searchParams.get("min_score") === "80" &&
      searchParams.get("min_trust") === "80" &&
      searchParams.get("wheelchair") === "true" &&
      searchParams.get("changing_table") === "true" &&
      searchParams.get("fee") === "false" &&
      searchParams.get("open_24h") === "true",
    ),
  ).toBe(true);
});

test("GPS search can be enabled and reset without stale status", async ({ context, page }) => {
  const observedPlaceRequests: URL[] = [];
  await context.grantPermissions(["geolocation"], { origin: "http://127.0.0.1:3000" });
  await context.setGeolocation({ latitude: 35.8617, longitude: 139.6455 });
  await mockApi(page, observedPlaceRequests);
  await page.goto("/");
  await waitForInitialResults(page);

  await page.getByRole("button", { name: "現在地から探す" }).click();
  await expect(page.locator(".location-status")).toHaveText(
    "現在地から10km以内を近い順に表示しています。",
  );
  const resetButton = page.getByRole("button", { name: "解除" });
  await expect(resetButton).toBeVisible();

  await expect.poll(() =>
    observedPlaceRequests.some(({ searchParams }) =>
      searchParams.get("latitude") === "35.8617" &&
      searchParams.get("longitude") === "139.6455" &&
      searchParams.get("radius_m") === "10000",
    ),
  ).toBe(true);

  const requestsBeforeReset = observedPlaceRequests.length;
  await resetButton.click();

  await expect(resetButton).toHaveCount(0);
  await expect(page.locator(".location-status")).toHaveCount(0);
  await expect.poll(() =>
    observedPlaceRequests.slice(requestsBeforeReset).some(({ searchParams }) =>
      !searchParams.has("latitude") &&
      !searchParams.has("longitude") &&
      !searchParams.has("radius_m"),
    ),
  ).toBe(true);
});
