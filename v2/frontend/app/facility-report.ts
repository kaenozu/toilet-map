export type FacilityReportRequest = {
  facilityId: number;
  reportType: string;
  note: string;
};

export type FacilityReportResult =
  | { ok: true }
  | { ok: false; message: string };

type ReportResponse = {
  ok: boolean;
  json(): Promise<unknown>;
};

type ReportFetcher = (
  input: string,
  init: {
    method: string;
    headers: Record<string, string>;
    body: string;
    signal: AbortSignal;
  },
) => Promise<ReportResponse>;

const REPORT_TIMEOUT_MS = 15_000;
const DEFAULT_FAILURE_MESSAGE =
  "報告を送信できませんでした。しばらくしてから再試行してください。";
const NETWORK_FAILURE_MESSAGE =
  "通信エラーのため報告を送信できませんでした。接続を確認して再試行してください。";
const TIMEOUT_FAILURE_MESSAGE =
  "通信がタイムアウトしたため報告を送信できませんでした。接続を確認して再試行してください。";

function errorDetail(body: unknown): string | null {
  if (typeof body !== "object" || body == null || !("detail" in body)) return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail !== "string") return null;
  const normalized = detail.trim();
  return normalized || null;
}

export async function submitFacilityReport(
  request: FacilityReportRequest,
  fetcher: ReportFetcher = fetch,
  timeoutMs = REPORT_TIMEOUT_MS,
): Promise<FacilityReportResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetcher(`/api/v2/facilities/${request.facilityId}/reports`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ report_type: request.reportType, note: request.note }),
      signal: controller.signal,
    });

    if (response.ok) return { ok: true };

    const body = await response.json().catch(() => null);
    return { ok: false, message: errorDetail(body) ?? DEFAULT_FAILURE_MESSAGE };
  } catch {
    return {
      ok: false,
      message: controller.signal.aborted ? TIMEOUT_FAILURE_MESSAGE : NETWORK_FAILURE_MESSAGE,
    };
  } finally {
    clearTimeout(timeout);
  }
}
