import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { buildResultStatus } from "../app/result-status.ts";

test("announces loading before stale result counts", () => {
  assert.equal(
    buildResultStatus({ loading: true, failed: false, count: 12 }),
    "施設を読み込み中です。",
  );
});

test("distinguishes an API failure from an empty result", () => {
  assert.equal(
    buildResultStatus({ loading: false, failed: true, count: 0 }),
    "施設情報を読み込めませんでした。しばらくしてから再試行してください。",
  );
});

test("announces an empty successful search", () => {
  assert.equal(
    buildResultStatus({ loading: false, failed: false, count: 0 }),
    "条件に一致する施設がありません。",
  );
});

test("announces the number of displayed facilities", () => {
  assert.equal(
    buildResultStatus({ loading: false, failed: false, count: 23 }),
    "23件の施設を表示しています。",
  );
});

test("normalizes invalid or negative result counts", () => {
  assert.equal(
    buildResultStatus({ loading: false, failed: false, count: Number.NaN }),
    "条件に一致する施設がありません。",
  );
  assert.equal(
    buildResultStatus({ loading: false, failed: false, count: -2 }),
    "条件に一致する施設がありません。",
  );
  assert.equal(
    buildResultStatus({ loading: false, failed: false, count: 2.9 }),
    "2件の施設を表示しています。",
  );
});

const dashboardSource = readFileSync(new URL("../app/Dashboard.tsx", import.meta.url), "utf8");
const facilityCardSource = readFileSync(new URL("../app/FacilityCard.tsx", import.meta.url), "utf8");

test("wires result updates to one polite live region and busy list", () => {
  assert.match(dashboardSource, /role="status" aria-live="polite" aria-atomic="true"/);
  assert.match(dashboardSource, /role="list" aria-label="検索結果" aria-busy=\{loading\}/);
  assert.match(dashboardSource, /failed: loadFailed/);
});

test("clears a previous location when geolocation is unavailable or fails", () => {
  assert.match(
    dashboardSource,
    /if \(!navigator\.geolocation\) \{\s*setUserLocation\(null\);/,
  );
  assert.match(
    dashboardSource,
    /\(\) => \{\s*setUserLocation\(null\);\s*setLocationStatus\("現在地を取得できませんでした。/,
  );
});

test("marks each facility card as a result list item", () => {
  assert.match(facilityCardSource, /<article className="card" role="listitem">/);
});
