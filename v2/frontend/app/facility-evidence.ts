// Presentation helpers for explaining cleanliness and information trust without expanding cards by default.
export type FacilityEvidenceInput = {
  toilet_score: number | null;
  trust_score: number | null;
  source_count: number;
  verification_status: string;
  last_verified_at: string | null;
};

export type FacilityEvidence = {
  cleanliness: string;
  trust: string;
  sources: string;
  verification: string;
  verifiedAt: string;
  caution: string | null;
};

const VERIFICATION_LABELS: Record<string, string> = {
  human_verified: "人が確認済み",
  automatically_verified: "自動確認済み",
  unverified: "未確認",
  disputed: "内容に異議あり",
  stale: "情報が古い可能性あり",
  rejected: "掲載対象外",
};

function formatScore(value: number): string {
  return Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1);
}

function formatTrust(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "未計算";
  const band = value >= 80 ? "高" : value >= 55 ? "中" : "低";
  return `${band} (${value.toFixed(0)})`;
}

function formatVerifiedAt(value: string | null, now: Date): string {
  if (!value) return "確認日不明";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime()) || parsed.getTime() > now.getTime()) return "確認日不明";
  return `${new Intl.DateTimeFormat("ja-JP", {
    timeZone: "Asia/Tokyo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(parsed)}確認`;
}

function buildCaution(status: string, trustScore: number | null): string | null {
  if (status === "disputed") return "内容に異議があるため、現地状況を確認してください。";
  if (status === "stale") return "確認から時間が経っているため、現地状況が変わっている可能性があります。";
  if (status === "unverified") return "未確認の情報です。利用前に現地状況を確認してください。";
  if (trustScore != null && trustScore < 55) return "信頼度が低いため、現地状況を確認してください。";
  return null;
}

export function buildFacilityEvidence(
  input: FacilityEvidenceInput,
  now: Date = new Date(),
): FacilityEvidence {
  const sourceCount = Number.isFinite(input.source_count)
    ? Math.max(0, Math.trunc(input.source_count))
    : 0;

  return {
    cleanliness:
      input.toilet_score == null || !Number.isFinite(input.toilet_score)
        ? "未評価"
        : `${formatScore(input.toilet_score)}点`,
    trust: formatTrust(input.trust_score),
    sources: sourceCount > 0 ? `${sourceCount}件` : "不明",
    verification: VERIFICATION_LABELS[input.verification_status] ?? "確認状態不明",
    verifiedAt: formatVerifiedAt(input.last_verified_at, now),
    caution: buildCaution(input.verification_status, input.trust_score),
  };
}
