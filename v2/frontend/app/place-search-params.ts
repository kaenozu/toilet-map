import type { UserLocation } from "./types";

export type PlaceSearchFilters = {
  query: string;
  prefecture: string;
  category: string;
  minScore: string;
  minTrust: string;
  wheelchair: boolean;
  changingTable: boolean;
  freeOnly: boolean;
  open24h: boolean;
  userLocation: UserLocation | null;
};

export function buildPlaceSearchParams(filters: PlaceSearchFilters): string {
  const value = new URLSearchParams({ limit: "2000" });
  if (filters.query.trim()) value.set("q", filters.query.trim());
  if (filters.prefecture) value.set("prefecture", filters.prefecture);
  if (filters.category) value.set("category", filters.category);
  if (filters.minScore) value.set("min_score", filters.minScore);
  if (filters.minTrust) value.set("min_trust", filters.minTrust);
  if (filters.wheelchair) value.set("wheelchair", "true");
  if (filters.changingTable) value.set("changing_table", "true");
  if (filters.freeOnly) value.set("fee", "false");
  if (filters.open24h) value.set("open_24h", "true");
  if (filters.userLocation) {
    value.set("latitude", String(filters.userLocation.latitude));
    value.set("longitude", String(filters.userLocation.longitude));
    value.set("radius_m", "10000");
  }
  return value.toString();
}
