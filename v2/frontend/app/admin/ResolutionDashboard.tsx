// Minimal administrator workflow for pending source records and reports.
"use client";

import { useEffect, useState } from "react";

type Candidate = {
  facility_id: number;
  name: string;
  address: string;
  distance_m: number;
  candidate_score: number;
};
type PendingSource = {
  id: number;
  provider: string;
  external_id: string;
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  candidates: Candidate[];
};
type PendingReport = {
  id: number;
  facility_id: number;
  name: string;
  address: string;
  report_type: string;
  note: string;
};

export default function ResolutionDashboard() {
  const [adminKey, setAdminKey] = useState("");
  const [sources, setSources] = useState<PendingSource[]>([]);
  const [reports, setReports] = useState<PendingReport[]>([]);
  const [status, setStatus] = useState("管理キーを入力してください。");

  useEffect(() => {
    setAdminKey(sessionStorage.getItem("toilet-map-admin-key") ?? "");
  }, []);

  async function load() {
    sessionStorage.setItem("toilet-map-admin-key", adminKey);
    setStatus("読み込み中...");
    const headers = { "x-admin-key": adminKey };
    const [sourceResponse, reportResponse] = await Promise.all([
      fetch("/api/v2/admin/source-records/pending", { headers }),
      fetch("/api/v2/admin/reports/pending", { headers }),
    ]);
    if (!sourceResponse.ok || !reportResponse.ok) {
      setStatus("管理キーまたはバックエンド接続を確認してください。");
      return;
    }
    const sourceBody = await sourceResponse.json();
    const reportBody = await reportResponse.json();
    setSources(sourceBody.items ?? []);
    setReports(reportBody.items ?? []);
    setStatus(`未解決ソース${sourceBody.total ?? 0}件・未処理報告${reportBody.total ?? 0}件`);
  }

  async function decideSource(sourceId: number, action: string, facilityId?: number) {
    const reason = window.prompt("判断理由を入力してください", "管理画面で確認") ?? "";
    if (!reason) return;
    const response = await fetch(`/api/v2/admin/source-records/${sourceId}/decision`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-admin-key": adminKey },
      body: JSON.stringify({ action, facility_id: facilityId, reason, decided_by: "web-admin" }),
    });
    if (!response.ok) {
      setStatus("統合判断を保存できませんでした。");
      return;
    }
    await load();
  }

  async function decideReport(reportId: number, accepted: boolean) {
    const reason = window.prompt("判断理由を入力してください", accepted ? "内容を確認" : "根拠不足") ?? "";
    if (!reason) return;
    const response = await fetch(`/api/v2/admin/reports/${reportId}/decision`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-admin-key": adminKey },
      body: JSON.stringify({ accepted, reason, decided_by: "web-admin" }),
    });
    if (!response.ok) {
      setStatus("報告判断を保存できませんでした。");
      return;
    }
    await load();
  }

  return (
    <main className="admin-shell">
      <header className="admin-header">
        <div><h1>データ品質管理</h1><p>類似候補は自動統合せず、管理者判断で確定します。</p></div>
        <a href="/">公開マップへ戻る</a>
      </header>
      <section className="admin-auth">
        <input
          type="password"
          aria-label="管理APIキー"
          placeholder="管理APIキー"
          value={adminKey}
          onChange={(event) => setAdminKey(event.target.value)}
        />
        <button type="button" onClick={load}>データを読み込む</button>
        <span>{status}</span>
      </section>
      <section>
        <h2>未解決ソース</h2>
        <div className="admin-grid">
          {sources.map((source) => (
            <article className="admin-card" key={source.id}>
              <h3>{source.name || "名称未設定"}</h3>
              <p>{source.address}</p>
              <p className="meta">{source.provider} / {source.external_id}</p>
              <a
                href={`https://www.openstreetmap.org/?mlat=${source.latitude}&mlon=${source.longitude}#map=19/${source.latitude}/${source.longitude}`}
                target="_blank"
                rel="noreferrer"
              >地図で確認</a>
              <div className="candidate-list">
                {source.candidates.map((candidate) => (
                  <div className="candidate" key={candidate.facility_id}>
                    <strong>{candidate.name}</strong>
                    <span>約{Math.round(candidate.distance_m)}m・候補度{Math.round(candidate.candidate_score * 100)}%</span>
                    <button type="button" onClick={() => decideSource(source.id, "match", candidate.facility_id)}>この施設に統合</button>
                  </div>
                ))}
              </div>
              <div className="admin-actions">
                <button type="button" onClick={() => decideSource(source.id, "new_facility")}>新規施設</button>
                <button type="button" className="danger" onClick={() => decideSource(source.id, "reject")}>却下</button>
              </div>
            </article>
          ))}
          {sources.length === 0 && <p className="empty">未解決ソースはありません。</p>}
        </div>
      </section>
      <section>
        <h2>ユーザー報告</h2>
        <div className="admin-grid">
          {reports.map((report) => (
            <article className="admin-card" key={report.id}>
              <h3>{report.name}</h3>
              <p>{report.address}</p>
              <p><strong>{report.report_type}</strong> {report.note}</p>
              <div className="admin-actions">
                <button type="button" onClick={() => decideReport(report.id, true)}>承認</button>
                <button type="button" className="danger" onClick={() => decideReport(report.id, false)}>却下</button>
              </div>
            </article>
          ))}
          {reports.length === 0 && <p className="empty">未処理報告はありません。</p>}
        </div>
      </section>
    </main>
  );
}
