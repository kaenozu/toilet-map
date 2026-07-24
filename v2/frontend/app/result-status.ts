// Accessible status text for asynchronous public facility search results.

export type ResultStatusInput = {
  loading: boolean;
  failed: boolean;
  count: number;
};

function normalizeCount(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.trunc(value));
}

export function buildResultStatus({ loading, failed, count }: ResultStatusInput): string {
  if (loading) return "施設を読み込み中です。";
  if (failed) {
    return "施設情報を読み込めませんでした。しばらくしてから再試行してください。";
  }

  const resultCount = normalizeCount(count);
  if (resultCount === 0) return "条件に一致する施設がありません。";
  return `${resultCount}件の施設を表示しています。`;
}
