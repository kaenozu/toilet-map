// Public dataset freshness labels derived from the immutable publication timestamp.

const DAY_IN_MS = 24 * 60 * 60 * 1000;
const JAPAN_UTC_OFFSET_MS = 9 * 60 * 60 * 1000;

export const FRESH_DATA_MAX_AGE_DAYS = 7;
export const STALE_DATA_MIN_AGE_DAYS = 31;

export type DatasetFreshnessState = "current" | "aging" | "stale" | "unknown";

export type DatasetFreshness = {
  state: DatasetFreshnessState;
  text: string;
};

function parseTimestamp(value: string | null | undefined): Date | null {
  if (!value?.trim()) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function japanCalendarDay(date: Date): number {
  const shifted = new Date(date.getTime() + JAPAN_UTC_OFFSET_MS);
  return Date.UTC(shifted.getUTCFullYear(), shifted.getUTCMonth(), shifted.getUTCDate()) / DAY_IN_MS;
}

function formatJapanDate(date: Date): string {
  const shifted = new Date(date.getTime() + JAPAN_UTC_OFFSET_MS);
  const year = shifted.getUTCFullYear();
  const month = String(shifted.getUTCMonth() + 1).padStart(2, "0");
  const day = String(shifted.getUTCDate()).padStart(2, "0");
  return `${year}/${month}/${day}`;
}

export function buildDatasetFreshness(
  publishedAt: string | null | undefined,
  now: Date = new Date(),
): DatasetFreshness {
  const published = parseTimestamp(publishedAt);
  if (!published || Number.isNaN(now.getTime())) {
    return { state: "unknown", text: "⚪ 公開データの更新日を確認できません。" };
  }

  const ageDays = japanCalendarDay(now) - japanCalendarDay(published);
  if (ageDays < 0) {
    return { state: "unknown", text: "⚪ 公開データの更新日を確認できません。" };
  }

  const ageLabel = ageDays === 0 ? "本日" : `${ageDays}日前`;
  const publishedDate = formatJapanDate(published);
  if (ageDays <= FRESH_DATA_MAX_AGE_DAYS) {
    return {
      state: "current",
      text: `🟢 公開データは最新です（${ageLabel}・${publishedDate}公開）。`,
    };
  }
  if (ageDays < STALE_DATA_MIN_AGE_DAYS) {
    return {
      state: "aging",
      text: `🟡 公開データは${ageLabel}です（${publishedDate}公開）。施設ごとの信頼度も確認してください。`,
    };
  }
  return {
    state: "stale",
    text: `🔴 公開データは${ageLabel}です（${publishedDate}公開）。現地状況が変わっている可能性があります。`,
  };
}
