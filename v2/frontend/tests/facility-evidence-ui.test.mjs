import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const cardSource = readFileSync(new URL("../app/FacilityCard.tsx", import.meta.url), "utf8");
const globalStyles = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

test("keeps score rationale collapsed until the user asks for it", () => {
  assert.match(cardSource, /<details className="score-rationale">/);
  assert.match(cardSource, /<summary>評価の根拠を見る<\/summary>/);
  assert.doesNotMatch(cardSource, /<details className="score-rationale" open>/);
});

test("explains that cleanliness and trust measure different things", () => {
  assert.match(
    cardSource,
    /きれい度は清潔さの評価、信頼度は情報源の確度・確認状態・更新時期をもとにした情報の確からしさです。/,
  );
});

test("does not replace an unknown source count with a fabricated one", () => {
  assert.match(cardSource, /情報源 \{evidence\.sources\}/);
  assert.doesNotMatch(cardSource, /source_count \|\| 1/);
});

test("uses a compact mobile-safe disclosure layout", () => {
  assert.match(globalStyles, /\.score-rationale \{/);
  assert.match(globalStyles, /\.score-rationale dl div \{ display: grid;/);
  assert.match(globalStyles, /grid-template-columns: minmax\(72px, auto\) 1fr/);
});
