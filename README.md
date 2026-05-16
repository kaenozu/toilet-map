# トイレきれい度マップ

Google Mapsのレビューからトイレのきれい度を自動判定して地図上に表示するStreamlitアプリケーション。

## プロジェクト概要
- **目的**: 日本全国のトイレ情報を収集し、レビューのテキスト分析から「きれい度」をスコア化して可視化
- **機能**:
  - 地域別・カテゴリ別フィルタリング
  - 現在地からの距離順ソート
  - スコア分布の統計表示
  - データ鮮度表示（生成日時 / SQLite同期日時）
  - 多言語対応（日本語・英語）

## 技術スタック
- **アプリ**: Python 3.11+ / Streamlit / Folium / streamlit-folium / Pandas
- **スクレイピング**: Docker / Google Maps Scraper
- **データ処理**: JSON / JSONL / SQLite
- **テスト**: pytest

## クイックスタート

### アプリ起動
```bash
pip install -r requirements.txt
streamlit run app.py
```

**Streamlit Cloud でデプロイする場合:**
```bash
streamlit run streamlit_app.py
```
`streamlit_app.py` は `app.py` の薄いラッパーで、Streamlit Cloud のエントリポイントとして使います。

### データ処理フロー
1. **スクレイピング**:
   ```bash
   cd batch
   # 関東地方のスクレイピング（例）
   python scrape_runner.py --city さいたま市 --prefecture 埼玉県
   ```

2. **データ処理**:
   ```bash
   cd batch
   python process_data.py raw_data.json ../data/toilets.json.gz --incremental
   ```
   - 同一クエリの重複は自動で除外されます。

3. **SQLite変換**:
   ```bash
   cd batch
   python to_sqlite.py ../data/toilets.json.gz --incremental
   ```

4. **まとめて更新**:
   ```bash
   batch/update_data.bat
   ```
   - スクレイプ → SQLite同期 → 検証を順に実行します。
   - `batch/verify_data.py` は JSON と SQLite の件数、都道府県分布、更新日時を突き合わせます。

## プロジェクト構造
```
toilet-map/
├── app.py                  # Streamlitメインアプリ
├── streamlit_app.py        # Streamlit Cloud エントリポイント
├── app_config.py           # 定数定義（都道府県座標含む）
├── static/                 # 静的アセット
│   ├── mobile.css         # モバイル最適化CSS
│   └── popup_fix.js       # Leafletポップアップ位置修正
├── ui/                    # UIコンポーネント
│   ├── components.py      # 凡例などの共通表示
│   ├── data_loader.py     # データ読み込み
│   ├── filters.py         # フィルタリング・検索
│   ├── i18n.py           # 多言語対応
│   ├── map_builder.py     # Folium地図構築
│   ├── pagination.py      # ページネーション
│   ├── popups.py         # ポップアップHTML生成
│   ├── query_params.py   # URLクエリパラメータ操作
│   ├── stats.py          # 統計表示
│   ├── styles.py         # モバイルCSS読み込み
│   └── types.py          # TypedDict型定義
├── batch/                 # バッチ処理
│   ├── api_server.py     # FastAPI REST API
│   ├── auto_expand.py    # データ不足エリア自動拡張
│   ├── city_bounds.py    # Nominatim市区町村境界
│   ├── cli_parser.py     # CLI引数解析
│   ├── db_utils.py       # SQLite共通ユーティリティ
│   ├── docker_exec.py    # Dockerスクレイパー実行
│   ├── expansion_query.py # 拡張クエリ管理
│   ├── gap_analyzer.py   # 統計的ギャップ検出
│   ├── generate_queries.py # クエリ自動生成
│   ├── kanto_phase1.py   # 関東Phase1スクレイパー
│   ├── merge_to_db.py    # JSON→SQLiteマージ
│   ├── nationwide_runner.py # 47都道府県スクレイパー
│   ├── pipeline.py       # スクレイプ後処理パイプライン
│   ├── process_data.py   # スクレイピングデータ処理
│   ├── progress_tracker.py # 進行状況追跡
│   ├── quality_metrics.py # データ品質メトリクス
│   ├── scrape_runner.py  # スクレイピング実行エンジン
│   ├── scoring.py        # スコアリングロジック
│   ├── scoring_config.py # スコアリング設定定数
│   ├── sync_db.py        # JSON→SQLite同期ラッパー
│   ├── to_sqlite.py      # JSON→SQLite変換
│   ├── update_data.bat   # 一括更新バッチ
│   ├── utils.py          # 共通ユーティリティ
│   └── verify_data.py    # データ品質検証
├── data/                  # データファイル
│   ├── toilets.json.gz   # 処理済みデータ（コミット対象）
│   └── toilets.db        # SQLiteデータベース
└── tests/                # テストコード
```

## スコアリング手法
| スコア | 表示 | 判定 |
|--------|------|------|
| 80-100 | ✨ | とてもきれい |
| 65-79  | 😊 | きれい |
| 50-64  | 😐 | 普通 |
| 35-49  | 😨 | 少し気になる |
| 0-34   | 💩 | 要注意 |

スコア = (raw_score + 5) × 10（-5〜+5 → 0〜100 変換）

## バッチ処理コマンド例
```bash
# 全国クエリ生成
python batch/generate_queries.py

# 関東Phase1実行
python batch/kanto_phase1.py

# データ検証
python batch/verify_data.py
```

## API サーバー

FastAPI ベースの REST API を独立して起動できます:

```bash
# 依存関係のインストール
pip install -r requirements-api.txt

# API サーバー起動
cd batch
uvicorn api_server:app --reload --port 8000
```

エンドポイント一覧:
- `GET /api/toilets` — トイレ一覧（prefecture, min_score, q でフィルタ可能）
- `GET /api/toilets/{id}` — 個別トイレ情報
- `GET /api/stats` — 全体統計
- `GET /api/stats/distribution` — スコア分布

## 品質チェック
- `batch/generate_queries.py` は重複クエリを除外して batch を生成します
- `batch/verify_data.py` は JSON と SQLite の差分を都道府県単位まで確認します
- CI では `pytest` に加えて `batch/verify_data.py` も実行します

## テスト実行
```bash
# 全テスト実行
pytest tests/ -v

# カバレッジ計測
pytest tests/ --cov=. --cov-report=term-missing
```

## プロジェクト設定
- `pyproject.toml` で pytest / coverage / ruff を一元管理
- coverage `fail_under = 80`（現在 **90%**）
- 全テストパス
- lint: ruff 0 errors

## 注意事項
- `data/toilets.json.gz` と `data/toilets.db` はコミット対象です
- `batch/raw_data.json` や `batch/raw_parts_*/` は `.gitignore` で除外されています
- Docker Desktopが起動している状態でスクレイピングを実行してください
