# AGENTS.md

トイレきれい度マップ - プロジェクト固有の実装・検証ルール

## 現在の構成

このリポジトリは v2 への移行期間中で、2系統を同時に保守する。

- **v2**: `v2/` 配下。Next.js + FastAPI + PostgreSQL/PostGIS の本番置換版
- **v1**: ルート、`ui/`、`batch/`、`data/`。Streamlit + SQLite の既存互換系

v2 の変更で v1 の公開API、安定ID、SQLite配信データ、Streamlit動作を壊さないこと。v1 の変更で v2 の移行・公開手順を壊さないこと。

## 最優先の参照順

1. この `AGENTS.md`
2. `v2/README.md`
3. `README.md` / `README.en.md`
4. `.github/workflows/*.yml`
5. 既存実装と回帰テスト

## 技術スタック

### v2

- Frontend: Node.js 22 / Next.js 16.2.11 / React 19.2.8 / TypeScript / Leaflet / react-leaflet
- Backend: Python 3.12 / FastAPI / psycopg / PostgreSQL 17 / PostGIS / pg_trgm
- Schema: `v2/backend/migrations/*.sql` の順序付き・チェックサム付きマイグレーション
- Runtime: Frontend、Backend、Worker、PostgreSQL/PostGIS を Docker Compose で統合
- Tests: pytest、Ruff、TypeScript typecheck、Next.js production build、Compose smoke

### v1

- App: Python 3.11+ / Streamlit / Folium / streamlit-folium / Pandas
- Data: JSON / JSONL / SQLite
- API: FastAPI / Pydantic
- Tests: pytest / mypy / Ruff / data verification / Streamlit smoke

## v2 設計原則

```text
provider discovery
  -> source_records
  -> facility_source_links / facility_match_candidates
  -> facilities
  -> dimension_observations / facility_scores
  -> published_place_snapshots
  -> public API / Next.js
```

- `facilities` は長期存続する正規施設。
- `source_records` は出典ごとの観測。正規施設と同一視しない。
- 自動再利用を許可するのは原則として既存の完全一致 `provider + external_id` 決定のみ。
- 名称、住所、距離の一致は候補生成に使い、自動マージしない。
- 施設紐付けは `pending` / `matched` / `rejected` を明示する。
- 公開APIは原則 `published_place_snapshots` を読む。
- 公開処理はトランザクション内で再検証し、失敗時は既存公開データを維持する。
- `PUBLIC_READ_MODEL=places` は一時的なロールバック用途に限定する。
- 旧 `places`、`provider_records`、`reviews`、`score_history` と旧IDの互換性を維持する。
- ユーザー報告は `user_submission` の source record として保留し、自動で施設状態を変更しない。
- OSM 取り込みは境界付きで行い、出典・ライセンス情報を保持する。

## マイグレーション・DBルール

- 正式なスキーマ操作は `python -m app.cli init-db`。
- `v2/backend/schema.sql` は同じマイグレーションを読み込む薄い `psql` ブートストラップ。
- 適用済みマイグレーションの内容やチェックサムを変更しない。変更が必要なら新規番号を追加する。
- 本番DB適用前にバックアップ、migration status、Preview適用、データ品質、公開、API確認を行う。
- DB migration、既存データ、公開API、安定IDに破壊的変更を入れない。
- SQL はトランザクション、ロック、再実行性、外部キー、境界値、NULL、競合を確認する。

## ジョブキュー

- ジョブは冪等性キー、依存関係、リース、heartbeat、retry wait、cancel、エラー分類、実行統計を維持する。
- リース期限切れから回復可能にし、永久 `running` を作らない。
- 例外の握りつぶし、無条件成功、無制限リトライを禁止する。
- 同じ副作用を複数回実行しても破損しない設計を優先する。

## Frontend ルール

- APIアクセスは `v2/frontend/app/api/v2/[...path]/route.ts` のプロキシと既存型を優先する。
- 公開UIと `/admin` の権限境界を混同しない。
- 現在地、地図、検索条件、設備フィルタ、信頼度、レポート送信のUXを維持する。
- client component の範囲を必要最小限にする。
- 依存関係は正確なバージョンを維持し、Next.js のセキュリティ修正版を優先する。
- npm の更新後は必ず typecheck と production build を実行する。
- `package-lock.json` は現状使用せず、`v2/frontend/package-lock.json` を `.gitignore` で除外する。Docker と CI は `npm install --no-audit --no-fund` を使用する。

## v1 互換ルール

- `app.py` は Streamlit UI、ロジックは `app_config.py`、`ui/`、`batch/` に分離する。
- `data/toilets.json.gz` は canonical JSON、`data/toilets.db` はSQLite配信スナップショット。
- `place_id` / `data_id` / `source_id` の安定性を壊さない。
- 同一座標の別施設を誤って統合しない。
- JSON と SQLite は一時領域で構築し、両方成功後に公開する。
- `batch/verify_data.py` で件数、都道府県分布、更新日時を照合する。

## コマンド

### v2 Frontend

```bash
cd v2/frontend
npm install --no-audit --no-fund
npm run typecheck
npm run build
npm run dev
```

### v2 Backend

```bash
cd v2/backend
pip install '.[dev]'
ruff check . --no-fix
pytest -q
python -m app.cli init-db
python -m app.cli migration-status
python -m app.cli data-quality
python -m app.worker
```

### v2 Compose

```bash
cd v2
cp .env.example .env
docker compose config
docker compose build
docker compose up
```

### v1

```bash
pip install -r requirements.txt
ruff check . --no-fix
mypy .
pytest tests/ -v
python batch/verify_data.py
streamlit run app.py
```

## 変更時の必須検証

変更範囲に応じて、最低限次を実行する。

- v2 Frontend: `npm run typecheck`, `npm run build`
- v2 Backend: `ruff check v2/backend --no-fix`, `pytest -q`（working directory: `v2/backend`）
- migration: 空DB適用、2回目適用、migration status、`schema.sql` 2回適用
- import/publication: 旧データ取り込み、validate、publish、snapshot件数、互換ID、失敗時の既存公開維持
- v2 integration: `docker compose -f v2/docker-compose.yml config`, build, Compose smoke
- v1: Ruff、mypy、pytest、data verification、Streamlit smoke
- 依存関係更新: 脆弱性対象の解消確認、typecheck、build、関連 smoke

実行できない検証は成功扱いにせず、理由と代替CIを明記する。

## ファイル設計ルール

- 1ファイル1責務を基本とし、巨大化時は責務境界で分割する。
- 既存の公開API、DB、保存データ、CLI、ユーザー操作との互換性を守る。
- 複雑なロジックには「何を」ではなく「なぜ」のコメントを付ける。
- 型安全性を下げる回避、テストskip、エラー握りつぶしで問題を隠さない。
- セキュリティ、データ損失、競合状態、例外処理、境界値を確認する。
- 依頼範囲外の大規模リファクタや技術変更を混在させない。
- 既存の未関連変更を削除・上書き・巻き戻ししない。

## Git / PR

- feature branch から `main` へPRを作成する。
- 1PRの目的を明確にし、無関係な変更を混在させない。
- commit / push 前に branch、差分、対象ファイル、秘密情報混入を確認する。
- PR本文に変更理由、影響、検証結果、未確認事項、ロールバック方法を記載する。
- GitHub Actions の全必須チェックが成功するまでマージしない。
