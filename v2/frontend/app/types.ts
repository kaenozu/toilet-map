// Shared frontend API types for the published toilet read model.
export type Place = {
  id: number;
  facility_id: number;
  source_record_id: number | null;
  name: string;
  address: string;
  prefecture: string;
  category: string;
  toilet_score: number | null;
  confidence: number | null;
  trust_score: number | null;
  source_count: number;
  verification_status: string;
  last_verified_at: string | null;
  distance_m: number | null;
  latitude: number;
  longitude: number;
  attributes: Record<string, unknown>;
};

export type UserLocation = { latitude: number; longitude: number };
