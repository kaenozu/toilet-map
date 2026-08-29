import { describe, expect, it } from "vitest";
import { buildPlaceSearchParams } from "./place-search-params";

describe("buildPlaceSearchParams", () => {
  it("excludes unscored rows when a score threshold is selected", () => {
    const params = new URLSearchParams(buildPlaceSearchParams({ query: "", prefecture: "", category: "", minScore: "70", minTrust: "", wheelchair: false, changingTable: false, freeOnly: false, open24h: false, userLocation: null }));
    expect(params.get("min_score")).toBe("70");
    expect(params.get("include_unscored")).toBe("false");
  });
});
