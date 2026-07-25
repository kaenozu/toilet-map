import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { submitFacilityReport } from "../app/facility-report.ts";

const facilityCardSource = readFileSync(new URL("../app/FacilityCard.tsx", import.meta.url), "utf8");
const globalStyles = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

test("submits the selected report type and note to the facility endpoint", async () => {
  let captured;
  const result = await submitFacilityReport(
    { facilityId: 42, reportType: "broken", note: "水が止まりません" },
    async (input, init) => {
      captured = { input, init };
      return { ok: true, json: async () => ({}) };
    },
  );

  assert.deepEqual(result, { ok: true });
  assert.equal(captured.input, "/api/v2/facilities/42/reports");
  assert.equal(captured.init.method, "POST");
  assert.ok(captured.init.signal instanceof AbortSignal);
  assert.deepEqual(JSON.parse(captured.init.body), {
    report_type: "broken",
    note: "水が止まりません",
  });
});

test("surfaces a structured API error such as duplicate-report feedback", async () => {
  const result = await submitFacilityReport(
    { facilityId: 42, reportType: "closed", note: "" },
    async () => ({
      ok: false,
      json: async () => ({ detail: "同じ内容の報告はすでに受け付けています" }),
    }),
  );

  assert.deepEqual(result, {
    ok: false,
    message: "同じ内容の報告はすでに受け付けています",
  });
});

test("uses a safe fallback when an error response is not valid JSON", async () => {
  const result = await submitFacilityReport(
    { facilityId: 42, reportType: "other", note: "" },
    async () => ({
      ok: false,
      json: async () => {
        throw new SyntaxError("invalid JSON");
      },
    }),
  );

  assert.deepEqual(result, {
    ok: false,
    message: "報告を送信できませんでした。しばらくしてから再試行してください。",
  });
});

test("converts network failures into retryable user feedback", async () => {
  const result = await submitFacilityReport(
    { facilityId: 42, reportType: "wrong_location", note: "" },
    async () => {
      throw new TypeError("Failed to fetch");
    },
  );

  assert.deepEqual(result, {
    ok: false,
    message: "通信エラーのため報告を送信できませんでした。接続を確認して再試行してください。",
  });
});

test("aborts stalled requests and returns retryable timeout feedback", async () => {
  const result = await submitFacilityReport(
    { facilityId: 42, reportType: "broken", note: "応答がありません" },
    async (_input, init) => new Promise((resolve, reject) => {
      init.signal.addEventListener("abort", () => reject(init.signal.reason), { once: true });
    }),
    5,
  );

  assert.deepEqual(result, {
    ok: false,
    message: "通信がタイムアウトしたため報告を送信できませんでした。接続を確認して再試行してください。",
  });
});

test("prevents duplicate report submissions and exposes progress accessibly", () => {
  assert.match(facilityCardSource, /if \(submitting\) return;/);
  assert.match(facilityCardSource, /disabled=\{submitting\} onClick=\{submitReport\}/);
  assert.match(facilityCardSource, /role="status" aria-live="polite" aria-atomic="true"/);
  assert.match(globalStyles, /\.report-form :disabled \{ cursor: not-allowed; opacity: \.65; \}/);
});

test("connects the report disclosure with its controlled form", () => {
  assert.match(facilityCardSource, /aria-expanded=\{reporting\}/);
  assert.match(facilityCardSource, /aria-controls=\{reportFormId\}/);
  assert.match(facilityCardSource, /className="report-form" id=\{reportFormId\}/);
  assert.match(facilityCardSource, /aria-label="報告の種類"/);
});
