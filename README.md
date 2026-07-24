# トイレきれい度マップ

トイレ情報の収集・統合・きれい度評価・地図表示を行うプロジェクトです。

現在は次の2系統を併存させながら v2 へ移行しています。

- **v2（新構成）**: Next.js + FastAPI + PostgreSQL/PostGIS。出典付き観測データ、施設同定、公開スナップショット、管理画面を備えた本番置換版
- **v1（既存構成）**: Streamlit + SQLite。既存サービスとデータ処理を維持する互換系

v2 の詳細な設計、マイグレーション、インポート、公開、ロールバック手順は [`v2/README.md`](v2/README.md) を参照してください。

## v2 の概要

```text
provider discovery
  -> source_records
  -> facility_source_links / facility_match_candidates
  -> facilities
  -> dimension_observations / facility_scores
  -> published_place_snapshots
  -> FastAPI / Next.js map
```

主な特徴:

- 長期存続する `facilities` と、出典ごとの `source_records` を分離
- `pending` / `matched` / `rejected` の明示的な施設同定
- 旧IDを保持した不変の公開スナップショット
- 清潔さ、におい、混雑、鮮度、設備、アクセシビリティ、子ども向け評価
- 信頼度・鮮度・設備・現在地距離による検索
- `/admin` での候補確認、施設作成、紐付け、却下
- PostgreSQL のリース付き・冪等なジョブキュー
- 順序付き・チェックサム付き SQL マイグレーション
- 旧 Streamlit / SQLite API と互換テーブルを移行期間中維持

## v2 クイックスタート

### Docker Compose で統合起動

```bash
cd v2
cp .env.example .env
docker compose up --build
```

起動先:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- PostgreSQL/PostGIS: `localhost:5432`
- 管理画面: `http://localhost:3000/admin`

### Frontend のみローカル検証

Docker を使えない環境でも、Frontend の型検査と本番ビルドは実行できます。

```bash
cd v2/frontend
npm install --no-audit --no-fund
npm run typecheck
npm run build
```

Frontend は Node.js 22 系を CI で使用します。依存関係の更新は `.github/dependabot.yml` の npm 設定でも監視します。

### Backend のローカル検証

PostgreSQL/PostGIS が利用できる環境で実行してください。

```bash
cd v2/backend
pip install '.[dev]'
python -m app.cli init-db
python -m app.cli migration-status
pytest -q
```

## v2 の主要運用コマンド

```bash
cd v2/backend

# 旧JSON/SQLite系データの取り込み
python -m app.cli import-legacy ../../data/toilets.json.gz --source legacy-json

# データセット検証・公開
python -m app.cli validate DATASET_ID
python -m app.cli publish DATASET_ID

# データ品質・マイグレーション状態
python -m app.cli data-quality
python -m app.cli migration-status

# OSM観測の取り込みと候補生成
python -m app.cli ingest-osm --region kumagaya
python -m app.cli generate-candidates

# ワーカー
python -m app.worker
```

本番適用前に Preview で空DBからマイグレーション、旧データ取り込み、検証、公開、API/UI確認まで通してください。公開に失敗した場合は既存公開データを維持し、一時的な読み取りロールバックには `PUBLIC_READ_MODEL=places` を使用します。

## v1（既存 Streamlit アプリ）

### 機能

- 地域別・カテゴリ別フィルタリング
- 現在地からの距離順ソート
- スコア分布の統計表示
- データ鮮度表示
- 日本語・英語対応

### 技術スタック

- **アプリ**: Python 3.11+ / Streamlit / Folium / streamlit-folium / Pandas
- **スクレイピング**: Docker / Google Maps Scraper
- **データ処理**: JSON / JSONL / SQLite
- **API**: FastAPI / Pydantic
- **テスト**: pytest

### 起動

```bash
pip install -r requirements.txt
streamlit run app.py
```

Streamlit Cloud では次を使用します。

```bash
streamlit run streamlit_app.py
```

### データ処理

```bash
cd batch

# スクレイピング
python scrape_runner.py --city さいたま市 --prefecture 埼玉県

# canonical JSON の更新
python process_data.py raw_data.json ../data/toilets.json.gz --incremental

# SQLite 配信用スナップショットの更新
python to_sqlite.py ../data/toilets.json.gz --incremental
```

`batch/update_data.bat` は JSON と SQLite を一時領域で構築し、両方の生成成功後に公開します。`batch/verify_data.py` は件数、都道府県分布、更新日時を突き合わせます。

## プロジェクト構造

```text
toilet-map/
├── app.py                    # v1 Streamlit アプリ
├── streamlit_app.py          # Streamlit Cloud エントリポイント
├── ui/                       # v1 UI
├── batch/                    # v1 データ処理・互換 API
├── data/                     # canonical JSON / SQLite
├── tests/                    # v1 回帰テスト
└── v2/
    ├── backend/              # FastAPI、PostgreSQL、マイグレーション、ワーカー
    ├── frontend/             # Next.js、Leaflet、管理画面
    ├── docker-compose.yml
    └── README.md
```

## 品質チェック

### v1

```bash
ruff check . --no-fix
mypy .
pytest tests/ -v
python batch/verify_data.py
```

### v2

```bash
ruff check v2/backend --no-fix
cd v2/backend && pytest -q
cd ../frontend && npm run typecheck && npm run build
docker compose -f v2/docker-compose.yml config
docker compose -f v2/docker-compose.yml build
```

CI では既存アプリと v2 を分離して検証し、v2 Compose smoke では空DB、マイグレーション、旧データ取り込み、API、Frontend まで確認します。

## スコアリング（v1互換）

| スコア | 表示 | 判定 |
|--------|------|------|
| 80-100 | ✨ | とてもきれい |
| 65-79  | 😊 | きれい |
| 50-64  | 😐 | 普通 |
| 35-49  | 😨 | 少し気になる |
| 0-34   | 💩 | 要注意 |

スコア = `(raw_score + 5) × 10`（-5〜+5 を 0〜100 に変換）

## 注意事項

- `data/toilets.json.gz` と `data/toilets.db` は v1 の配信用データとしてコミット対象です。
- 旧SQLiteスキーマは起動時に canonical JSON から再構築されます。
- `batch/raw_data.json` や `batch/raw_parts_*/` は `.gitignore` で除外されます。
- 本番DBマイグレーション、実データ公開、外部プロバイダー取り込みは Preview 検証とバックアップ後に実行してください。
