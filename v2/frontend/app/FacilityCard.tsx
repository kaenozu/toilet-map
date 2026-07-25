// Facility card with trust, navigation, and operational report actions.
"use client";

import { useState } from "react";
import { buildFacilityEvidence } from "./facility-evidence";
import { submitFacilityReport } from "./facility-report";
import type { Place } from "./types";

function trustLabel(place: Place): string {
  if (place.trust_score == null) return "信頼度未計算";
  if (place.trust_score >= 80) return `信頼度 高 (${place.trust_score.toFixed(0)})`;
  if (place.trust_score >= 55) return `信頼度 中 (${place.trust_score.toFixed(0)})`;
  return `信頼度 低 (${place.trust_score.toFixed(0)})`;
}

export default function FacilityCard({ place }: { place: Place }) {
  const [reporting, setReporting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reportType, setReportType] = useState("broken");
  const [note, setNote] = useState("");
  const [status, setStatus] = useState("");

  async function submitReport() {
    if (submitting) return;

    setSubmitting(true);
    setStatus("送信中...");
    try {
      const result = await submitFacilityReport({
        facilityId: place.facility_id,
        reportType,
        note,
      });
      if (result.ok) {
        setStatus("報告を受け付けました。確認後に反映します。");
        setNote("");
        return;
      }
      setStatus(result.message);
    } finally {
      setSubmitting(false);
    }
  }

  const directions = `https://www.google.com/maps/dir/?api=1&destination=${place.latitude},${place.longitude}`;
  const evidence = buildFacilityEvidence(place);
  const reportFormId = `report-form-${place.facility_id}`;

  return (
    <article className="card" role="listitem">
      <h2>{place.name}</h2>
      <p>{place.address || place.prefecture}</p>
      <div className="badges">
        <span className="badge score-badge">
          きれい度 {evidence.cleanliness}
        </span>
        <span className="badge trust-badge">{trustLabel(place)}</span>
      </div>
      <p className="meta">
        情報源 {evidence.sources}
        {place.distance_m == null ? "" : `・約${Math.round(place.distance_m)}m`}
      </p>
      <details className="score-rationale">
        <summary>評価の根拠を見る</summary>
        <div className="score-rationale-body">
          <p>
            きれい度は清潔さの評価、信頼度は情報源の確度・確認状態・更新時期をもとにした情報の確からしさです。
          </p>
          <dl>
            <div>
              <dt>きれい度</dt>
              <dd>{evidence.cleanliness}</dd>
            </div>
            <div>
              <dt>信頼度</dt>
              <dd>{evidence.trust}</dd>
            </div>
            <div>
              <dt>確認状態</dt>
              <dd>{evidence.verification}</dd>
            </div>
            <div>
              <dt>最終確認</dt>
              <dd>{evidence.verifiedAt}</dd>
            </div>
            <div>
              <dt>情報源</dt>
              <dd>{evidence.sources}</dd>
            </div>
          </dl>
          {evidence.caution && <p className="evidence-caution">{evidence.caution}</p>}
        </div>
      </details>
      <div className="card-actions">
        <a href={directions} target="_blank" rel="noreferrer">ここへ案内</a>
        <button
          type="button"
          aria-expanded={reporting}
          aria-controls={reportFormId}
          onClick={() => setReporting((value) => !value)}
        >
          情報を報告
        </button>
      </div>
      {reporting && (
        <div className="report-form" id={reportFormId}>
          <select
            aria-label="報告の種類"
            value={reportType}
            disabled={submitting}
            onChange={(event) => setReportType(event.target.value)}
          >
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
            disabled={submitting}
            onChange={(event) => setNote(event.target.value)}
          />
          <button type="button" disabled={submitting} onClick={submitReport}>
            {submitting ? "送信中..." : "報告を送信"}
          </button>
          <p className="form-status" role="status" aria-live="polite" aria-atomic="true">
            {status}
          </p>
        </div>
      )}
    </article>
  );
}
