import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { buildPlaceSearchParams } from "../app/place-search-params.ts";

const dashboardSource = readFileSync(new URL("../app/Dashboard.tsx", import.meta.url), "utf8");

const defaults = {
  query: "",
  prefecture: "",
  category: "",
  minScore: "",
  minTrust: "",
  wheelchair: false,
  changingTable: false,
  freeOnly: false,
  open24h: false,
  userLocation: null,
};

test("keeps the default public query bounded", () => {
  assert.equal(buildPlaceSearchParams(defaults), "limit=2000");
});

test("sends the selected category with the existing public filters", () => {
  const params = new URLSearchParams(
    buildPlaceSearchParams({
      ...defaults,
      query: "  熊谷駅  ",
      prefecture: "埼玉県",
      category: "駅",
      minScore: "65",
      minTrust: "55",
      wheelchair: true,
      changingTable: true,
      freeOnly: true,
      open24h: true,
      userLocation: { latitude: 36.1473, longitude: 139.3886 },
    }),
  );

  assert.deepEqual(Object.fromEntries(params), {
    limit: "2000",
    q: "熊谷駅",
    prefecture: "埼玉県",
    category: "駅",
    min_score: "65",
    include_unscored: "false",
    min_trust: "55",
    wheelchair: "true",
    changing_table: "true",
    fee: "false",
    open_24h: "true",
    latitude: "36.1473",
    longitude: "139.3886",
    radius_m: "10000",
  });
});

test("renders category facet values as an accessible filter", () => {
  assert.match(dashboardSource, /const \[category, setCategory\] = useState\(""\);/);
  assert.match(
    dashboardSource,
    /<select aria-label="施設カテゴリ" value=\{category\} onChange=\{\(event\) => setCategory\(event\.target\.value\)\}>/,
  );
  assert.match(dashboardSource, /facets\.categories\.map\(\(item\) =>/);
  assert.match(dashboardSource, /buildPlaceSearchParams\(\{[\s\S]*?category,[\s\S]*?userLocation,/);
});
