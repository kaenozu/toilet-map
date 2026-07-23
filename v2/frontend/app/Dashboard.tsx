"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import type { Place } from "./MapView";

const MapView = dynamic(() => import("./MapView"), { ssr: false });

type Stats = {
  record_count: number;
  scored_count: number;
  average_score: number | null;
  published_at?: string | null;
};

type Facets = { prefectures: { value: string; count: number }[] };

export default function Dashboard() {
  const [places, setPlaces] = useState<Place[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [facets, setFacets] = useState<Facets>({ prefectures: [] });
  const [query, setQuery] = useState("");
  const [prefecture, setPrefecture] = useState("");
  const [minScore, setMinScore] = useState("");
  const [loading, setLoading] = useState(true);

  const params = useMemo(() => {
    const value = new URLSearchParams({ limit: "2000" });
    if (query.trim()) value.set("q", query.trim());
    if (prefecture) value.set("prefecture", prefecture);
    if (minScore) value.set("min_score", minScore);
    return value.toString();
  }, [query, prefecture, minScore]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const response = await fetch(`/api/v2/places?${params}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(`API ${response.status}`);
        const body = await response.json();
        setPlaces(body.items ?? []);
      } catch (error) {
        if ((error as Error).name !== "AbortError") setPlaces([]);
      } finally {
        setLoading(false);
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

  return (
    <div className="shell">
      <header className="header">
        <h1>トイレきれい度マップ</h1>
        <p>公開済みデータセットから、近くの清潔なトイレを探せます。</p>
      </header>
      <div className="content">
        <aside className="sidebar">
          <div className="filters">
            <input
              aria-label="施設を検索"
              placeholder="施設名・住所で検索"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <select
              aria-label="都道府県"
              value={prefecture}
              onChange={(event) => setPrefecture(event.target.value)}
            >
              <option value="">すべての都道府県</option>
              {facets.prefectures.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.value} ({item.count})
                </option>
              ))}
            </select>
            <select
              aria-label="最低スコア"
              value={minScore}
              onChange={(event) => setMinScore(event.target.value)}
            >
              <option value="">スコア指定なし</option>
              <option value="80">80点以上</option>
              <option value="65">65点以上</option>
              <option value="50">50点以上</option>
            </select>
          </div>
          <div className="stats">
            {stats
              ? `全${stats.record_count}件・評価済み${stats.scored_count}件${
                  stats.average_score == null ? "" : `・平均${stats.average_score.toFixed(1)}点`
                }`
              : "統計を読み込み中"}
          </div>
          <div className="cards">
            {loading && <p className="empty">読み込み中...</p>}
            {!loading &&
              places.map((place) => (
                <article className="card" key={place.id}>
                  <h2>{place.name}</h2>
                  <p>{place.address || place.prefecture}</p>
                  <p className="score">
                    きれい度: {place.toilet_score == null ? "未評価" : `${place.toilet_score}点`}
                  </p>
                </article>
              ))}
            {!loading && places.length === 0 && (
              <p className="empty">条件に一致する施設がありません。</p>
            )}
          </div>
        </aside>
        <MapView places={places} />
      </div>
    </div>
  );
}
