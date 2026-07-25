import assert from "node:assert/strict";
import test from "node:test";

import { buildFacilityEvidence } from "../app/facility-evidence.ts";

const now = new Date("2026-07-25T12:00:00.000Z");

test("explains cleanliness and trust as separate values", () => {
  assert.deepEqual(
    buildFacilityEvidence(
      {
        toilet_score: 82.5,
        trust_score: 88,
        source_count: 3,
        verification_status: "human_verified",
        last_verified_at: "2026-07-24T15:30:00.000Z",
      },
      now,
    ),
    {
      cleanliness: "82.5点",
      trust: "高 (88)",
      sources: "3件",
      verification: "人が確認済み",
      verifiedAt: "2026/07/25確認",
      caution: null,
    },
  );
});

test("does not fabricate a source count when the API reports zero", () => {
  const evidence = buildFacilityEvidence(
    {
      toilet_score: null,
      trust_score: null,
      source_count: 0,
      verification_status: "unverified",
      last_verified_at: null,
    },
    now,
  );

  assert.equal(evidence.sources, "不明");
  assert.equal(evidence.cleanliness, "未評価");
  assert.equal(evidence.trust, "未計算");
  assert.equal(evidence.caution, "未確認の情報です。利用前に現地状況を確認してください。");
});

test("warns about stale or disputed information", () => {
  assert.equal(
    buildFacilityEvidence(
      {
        toilet_score: 60,
        trust_score: 30,
        source_count: 1,
        verification_status: "stale",
        last_verified_at: "2025-01-01T00:00:00.000Z",
      },
      now,
    ).caution,
    "確認から時間が経っているため、現地状況が変わっている可能性があります。",
  );

  assert.equal(
    buildFacilityEvidence(
      {
        toilet_score: 60,
        trust_score: 20,
        source_count: 1,
        verification_status: "disputed",
        last_verified_at: "2026-07-01T00:00:00.000Z",
      },
      now,
    ).verification,
    "内容に異議あり",
  );
});

test("does not present invalid or future verification dates as confirmed", () => {
  for (const lastVerifiedAt of ["not-a-date", "2026-07-26T00:00:00.000Z"]) {
    assert.equal(
      buildFacilityEvidence(
        {
          toilet_score: 70,
          trust_score: 70,
          source_count: 2,
          verification_status: "automatically_verified",
          last_verified_at: lastVerifiedAt,
        },
        now,
      ).verifiedAt,
      "確認日不明",
    );
  }
});
