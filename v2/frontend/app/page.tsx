type Place = {
  id: number;
  name: string;
  address: string;
  prefecture: string;
  toilet_score: number | null;
  latitude: number;
  longitude: number;
};

async function loadPlaces(): Promise<Place[]> {
  const base = process.env.API_BASE_URL ?? "http://localhost:8000";
  const response = await fetch(`${base}/api/v2/places?limit=100`, { cache: "no-store" });
  if (!response.ok) return [];
  const body = await response.json();
  return body.items ?? [];
}

export default async function Home() {
  const places = await loadPlaces();
  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: 24, fontFamily: "sans-serif" }}>
      <h1>トイレきれい度マップ v2</h1>
      <p>PostgreSQLで公開された最新データセットを表示しています。</p>
      <div style={{ display: "grid", gap: 12 }}>
        {places.map((place) => (
          <article key={place.id} style={{ border: "1px solid #ddd", borderRadius: 12, padding: 16 }}>
            <strong>{place.name}</strong>
            <div>{place.address}</div>
            <div>きれい度: {place.toilet_score == null ? "未評価" : `${place.toilet_score}点`}</div>
          </article>
        ))}
        {places.length === 0 && <p>公開済みデータセットはまだありません。</p>}
      </div>
    </main>
  );
}
