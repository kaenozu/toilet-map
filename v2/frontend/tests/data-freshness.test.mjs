import assert from "node:assert/strict";
import test from "node:test";

import {
  buildDatasetFreshness,
  FRESH_DATA_MAX_AGE_DAYS,
  STALE_DATA_MIN_AGE_DAYS,
} from "../app/data-freshness.ts";

const now = new Date("2026-07-25T03:00:00.000Z");

function publishedDaysAgo(days) {
  return new Date(now.getTime() - days * 24 * 60 * 60 * 1000).toISOString();
}

test("marks publication dates through seven days old as current", () => {
  assert.deepEqual(buildDatasetFreshness(publishedDaysAgo(FRESH_DATA_MAX_AGE_DAYS), now), {
    state: "current",
    text: "🟢 公開データは最新です（7日前・2026/07/18公開）。",
  });
});

test("marks publication dates from eight through thirty days old as aging", () => {
  assert.deepEqual(buildDatasetFreshness(publishedDaysAgo(FRESH_DATA_MAX_AGE_DAYS + 1), now), {
    state: "aging",
    text: "🟡 公開データは8日前です（2026/07/17公開）。施設ごとの信頼度も確認してください。",
  });
});

test("marks publication dates at least thirty-one days old as stale", () => {
  assert.deepEqual(buildDatasetFreshness(publishedDaysAgo(STALE_DATA_MIN_AGE_DAYS), now), {
    state: "stale",
    text: "🔴 公開データは31日前です（2026/06/24公開）。現地状況が変わっている可能性があります。",
  });
});

test("uses a same-day label in Japan even across UTC dates", () => {
  assert.deepEqual(
    buildDatasetFreshness("2026-07-24T15:30:00.000Z", new Date("2026-07-25T00:30:00.000Z")),
    {
      state: "current",
      text: "🟢 公開データは最新です（本日・2026/07/25公開）。",
    },
  );
});

test("does not present missing, invalid, or future timestamps as fresh", () => {
  for (const value of [
    null,
    "",
    "not-a-date",
    "2026-07-25T04:00:00.000Z",
    "2026-07-26T00:00:00+09:00",
  ]) {
    assert.deepEqual(buildDatasetFreshness(value, now), {
      state: "unknown",
      text: "⚪ 公開データの更新日を確認できません。",
    });
  }
});
