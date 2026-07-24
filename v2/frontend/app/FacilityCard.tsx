// Facility card with trust, navigation, and operational report actions.
"use client";

import { useState } from "react";
import type { Place } from "./types";

function trustLabel(place: Place): string {
  if (place.trust_score == null) return "信頼度未計算";
  if (place.trust_score >= 80) return `信頼度 高 (${place.trust_score.toFixed(0)})`;
  if (place.trust_score >= 55) return `信頼度 中 (${place.trust_score.toFixed(0)})`;
  return `信頼度 低 (${place.trust_score.toFixed(0)})`;
}

export default function FacilityCard({ place }: { place: Place }) {
  const [reporting, setReporting] = useState(false);
  const [reportType, setReportType] = useState("broken");
  const [note, setNote] = useState("");
  const [status, setStatus] = useState("");

  async function submitReport() {
    setStatus("送信中...");
    const response = await fetch(`/api/v2/facilities/${place.facility_id}/reports`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ report_type: reportType, note }),
    });
    if (response.ok) {
      setStatus("報告を受け付けました。確認後に反映します。");
      setNote("");
      return;
    }
    const body = await response.json().catch(() => ({}));
    setStatus(body.detail ?? "報告を送信できませんでした。");
  }

  const directions = `https://www.google.com/maps/dir/?api=1&destination=${place.latitude},${place.longitude}`;
  return (
    <article className="card" role="listitem">
      <h2>{place.name}</h2>
      <p>{place.address || place.prefecture}</p>
      <div className="badges">
        <span className="badge score-badge">
          きれい度 {place.toilet_score == null ? "未評価" : `${place.toilet_score}点`}
        </span>
        <span className="badge trust-badge">{trustLabel(place)}</span>
      </div>
      <p className="meta">
        情報源 {place.source_count || 1}件
        {place.distance_m == null ? "" : `・約${Math.round(place.distance_m)}m`}
      </p>
      <div className="card-actions">
        <a href={directions} target="_blank" rel="noreferrer">ここへ案内</a>
        <button type="button" onClick={() => setReporting((value) => !value)}>
          情報を報告
        </button>
      </div>
      {reporting && (
        <div className="report-form">
          <select value={reportType} onChange={(event) => setReportType(event.target.value)}>
            <option value="closed">閉鎖している</option>
            <option value="temporarily_closed">一時利用不能</option>
            <option value="broken">故障している</option>
            <option value="wrong_location">場所が違う</option>
            <option value="accessibility">バリアフリー情報が違う</option>
            <option value="cleanliness">清潔度情報が違う</option>
            <option value="other">その他</option>
          </select>
          <textarea
            aria-label="報告内容"
            placeholder="状況を入力してください"
            value={note}
            maxLength={1000}
            onChange={(event) => setNote(event.target.value)}
          />
          <button type="button" onClick={submitReport}>報告を送信</button>
          {status && <p className="form-status">{status}</p>}
        </div>
      )}
    </article>
  );
}
