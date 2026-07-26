// Main public search dashboard for the immutable published read model.
"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { buildDatasetFreshness } from "./data-freshness";
import FacilityCard from "./FacilityCard";
import { buildPlaceSearchParams } from "./place-search-params";
import { buildResultStatus } from "./result-status";
import type { Place, UserLocation } from "./types";

const MapView = dynamic(() => import("./MapView"), { ssr: false });

type Stats = {
  record_count: number;
  scored_count: number;
  average_score: number | null;
  published_at?: string | null;
};
type Facets = {
  prefectures: { value: string; count: number }[];
  categories: { value: string; count: number }[];
};

export default function Dashboard() {
  const [places, setPlaces] = useState<Place[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [facets, setFacets] = useState<Facets>({ prefectures: [], categories: [] });
  const [query, setQuery] = useState("");
  const [prefecture, setPrefecture] = useState("");
  const [category, setCategory] = useState("");
  const [minScore, setMinScore] = useState("");
  const [minTrust, setMinTrust] = useState("");
  const [wheelchair, setWheelchair] = useState(false);
  const [changingTable, setChangingTable] = useState(false);
  const [freeOnly, setFreeOnly] = useState(false);
  const [open24h, setOpen24h] = useState(false);
  const [userLocation, setUserLocation] = useState<UserLocation | null>(null);
  const [locationStatus, setLocationStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  const params = useMemo(
    () =>
      buildPlaceSearchParams({
        query,
        prefecture,
        category,
        minScore,
        minTrust,
        wheelchair,
        changingTable,
        freeOnly,
        open24h,
        userLocation,
      }),
    [query, prefecture, category, minScore, minTrust, wheelchair, changingTable, freeOnly, open24h, userLocation],
  );

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      setLoadFailed(false);
      try {
        const response = await fetch(`/api/v2/places?${params}`, { signal: controller.signal });
        if (!response.ok) throw new Error(`API ${response.status}`);
        const body = await response.json();
        setPlaces(body.items ?? []);
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setPlaces([]);
          setLoadFailed(true);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [params]);

  useEffect(() => {
    Promise.all([
      fetch("/api/v2/stats").then((response) => response.json()),
      fetch("/api/v2/facets").then((response) => response.json()),
    ])
      .then(([statsBody, facetsBody]) => {
        setStats(statsBody);
        setFacets(facetsBody);
      })
      .catch(() => undefined);
  }, []);

  function locateUser() {
    if (!navigator.geolocation) {
      setUserLocation(null);
      setLocationStatus("このブラウザでは現在地を取得できません。");
      return;
    }
    setLocationStatus("現在地を取得中...");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setUserLocation({ latitude: position.coords.latitude, longitude: position.coords.longitude });
        setLocationStatus("現在地から10km以内を近い順に表示しています。");
      },
      () => {
        setUserLocation(null);
        setLocationStatus("現在地を取得できませんでした。ブラウザの権限を確認してください。");
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  }

  const resultStatus = buildResultStatus({ loading, failed: loadFailed, count: places.length });
  const resultStatusClass = loading || loadFailed || places.length === 0 ? "empty" : "sr-only";
  const datasetFreshness = stats ? buildDatasetFreshness(stats.published_at) : null;

  return (
    <div className="shell">
      <header className="header">
        <div>
          <h1>トイレきれい度マップ</h1>
          <p>清潔度だけでなく、情報の新しさと信頼度を確認できます。</p>
        </div>
        <nav aria-label="管理"><a className="admin-link" href="/admin">データ管理</a></nav>
      </header>
      <div className="content">
        <aside className="sidebar">
          <div className="filters">
            <p id="search-guidance" className="filter-help">
              条件を組み合わせて絞り込めます。現在地を使うと10km以内の施設を近い順に表示します。
            </p>
            <input
              aria-label="施設を検索"
              aria-describedby="search-guidance"
              placeholder="施設名・住所で検索"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <select aria-label="都道府県" value={prefecture} onChange={(event) => setPrefecture(event.target.value)}>
              <option value="">すべての都道府県</option>
              {facets.prefectures.map((item) => (
                <option key={item.value} value={item.value}>{item.value} ({item.count})</option>
              ))}
            </select>
            <select aria-label="施設カテゴリ" value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">すべての施設カテゴリ</option>
              {facets.categories.map((item) => (
                <option key={item.value} value={item.value}>{item.value} ({item.count})</option>
              ))}
            </select>
            <div className="filter-row">
              <select aria-label="最低スコア" value={minScore} onChange={(event) => setMinScore(event.target.value)}>
                <option value="">清潔度指定なし</option>
                <option value="80">80点以上</option>
                <option value="65">65点以上</option>
                <option value="50">50点以上</option>
              </select>
              <select aria-label="最低信頼度" value={minTrust} onChange={(event) => setMinTrust(event.target.value)}>
                <option value="">信頼度指定なし</option>
                <option value="80">信頼度 高</option>
                <option value="55">信頼度 中以上</option>
              </select>
            </div>
            <div className="checks">
              <label><input type="checkbox" checked={wheelchair} onChange={(event) => setWheelchair(event.target.checked)} />車椅子対応</label>
              <label><input type="checkbox" checked={changingTable} onChange={(event) => setChangingTable(event.target.checked)} />おむつ交換台</label>
              <label><input type="checkbox" checked={freeOnly} onChange={(event) => setFreeOnly(event.target.checked)} />無料</label>
              <label><input type="checkbox" checked={open24h} onChange={(event) => setOpen24h(event.target.checked)} />24時間</label>
            </div>
            <div className="location-row">
              <button type="button" aria-describedby="search-guidance" onClick={locateUser}>現在地から探す</button>
              {userLocation && <button type="button" className="secondary" onClick={() => setUserLocation(null)}>解除</button>}
            </div>
            {locationStatus && (
              <p className="location-status" role="status" aria-live="polite">
                {locationStatus}
              </p>
            )}
          </div>
          <div className="stats">
            <div>
              {stats
                ? `全${stats.record_count}件・評価済み${stats.scored_count}件${
                    stats.average_score == null ? "" : `・平均${stats.average_score.toFixed(1)}点`
                  }`
                : "統計を読み込み中"}
            </div>
            {datasetFreshness && (
              <div className={`data-freshness data-freshness-${datasetFreshness.state}`}>
                {datasetFreshness.text}
              </div>
            )}
          </div>
          <p className={resultStatusClass} role="status" aria-live="polite" aria-atomic="true">
            {resultStatus}
          </p>
          <div className="cards" role="list" aria-label="検索結果" aria-busy={loading}>
            {!loading && !loadFailed && places.map((place) => <FacilityCard place={place} key={place.id} />)}
          </div>
        </aside>
        <MapView places={places} userLocation={userLocation} />
      </div>
    </div>
  );
}
