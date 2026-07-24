import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const dashboardSource = readFileSync(new URL("../app/Dashboard.tsx", import.meta.url), "utf8");
const globalStyles = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

test("explains how filters and current-location search affect results", () => {
  assert.match(
    dashboardSource,
    /条件を組み合わせて絞り込めます。現在地を使うと10km以内の施設を近い順に表示します。/,
  );
});

test("associates the guidance with the search field and location action", () => {
  assert.match(dashboardSource, /id="search-guidance" className="filter-help"/);
  assert.match(
    dashboardSource,
    /aria-label="施設を検索"\s+aria-describedby="search-guidance"/,
  );
  assert.match(
    dashboardSource,
    /<button type="button" aria-describedby="search-guidance" onClick=\{locateUser\}>/,
  );
});

test("keeps the guidance visually compact", () => {
  assert.match(globalStyles, /\.filter-help \{/);
  assert.match(globalStyles, /font-size: \.84rem/);
  assert.match(globalStyles, /line-height: 1\.45/);
});
