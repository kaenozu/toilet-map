# AGENTS.md

トイレきれい度マップ - プロジェクト固有の指示

## プロジェクト概要

Google Maps のレビューからトイレのきれい度を自動判定して Streamlit マップ上に表示するアプリ。

## 技術スタック

- **アプリ**: Python 3.11+ / Streamlit / Folium / streamlit-folium / Pandas
- **スクレイピング**: Docker / Google Maps Scraper
- **データ処理**: JSON / JSONL / SQLite
- **テスト**: pytest (589 tests)
- **Lint**: ruff

## コマンド

```bash
# アプリ起動
pip install -r requirements.txt
streamlit run app.py

# テスト実行
pytest tests/ -v

# Lint
ruff check . --no-fix

# スクレイプ＆データパイプライン（自動化）
cd batch && auto_expand_pipeline.bat

# データ処理（手動）
cd batch && python process_data.py raw_data.json ../data/toilets.json.gz --full
python process_data.py raw_data.json ../data/toilets.json.gz --incremental
python to_sqlite.py ../data/toilets.json.gz --incremental
python sync_db.py ../data/toilets.json.gz
```

## 設計方針

- `app.py`: Streamlit UI・地図構築のみ（ロジックは app_config, ui/*, batch/* に分離）
- `app_config.py`: 定数定義のみ（スコア範囲、フィルタ定義、都道府県中心座標）
- `ui/`: UI 表示専用（sidebar.py, components.py, styles.py, popups.py, data_loader.py, filters.py, map_builder.py, pagination.py, stats.py, i18n.py, query_params.py, types.py）
- `batch/`: スクレイピング・データ処理パイプライン（auto_expand.py, process_data.py, to_sqlite.py, scoring.py, db_utils.py 等）
- `static/mobile.css`: モバイル・サイドバー用CSS（レスポンシブ対応、`aria-expanded` フックで格納時レイアウト制御）
- `data/toilets.json.gz`: canonical JSON（変更時コミット対象）
- `data/toilets.db`: SQLite 読み取り高速化キャッシュ（JSON → to_sqlite で生成）

## サイドバー

- すべてのフィルタ系コントロールは `with st.sidebar` で実装
- `ui/sidebar.py` の `render_sidebar()` が描画を担当
- 格納時（`aria-expanded="false"`）は CSS でサイドバーをゼロ幅にし、メインコンテンツが全幅になる
- 言語・GPS・都道府県・フィルタ・検索・ソート controls

## スコアリング（詳細は README.md 参照）

スコア = (raw_score + 5) × 10（-5〜+5 → 0〜100 変換）

## データパイプライン

```
スクレイパー (Docker/gosom) → raw JSONL → process_data.py → data/toilets.json.gz (canonical) → to_sqlite.py → data/toilets.db (SQLite 高速キャッシュ)
```

自動化パイプライン: `batch/auto_expand_pipeline.bat`
- 1/5: データギャップ分析
- 2/5: auto_expand.py (Docker scraping)
- 3/5: process_data + to_sqlite (マージ・同期)
- 4/5: verify_data.py (品質チェック)
- 5/5: 中間ファイル削除

## ファイル設計ルール

- 1ファイル1責務、300行以内
- 全ファイルにヘッダーコメント必須
- 複雑なロジックには必ずコメント
- シンプル最優先（不要の抽象化禁止）

## DB制約

なし（JSONファイルベース＋SQLiteキャッシュ）

## API

なし（Streamlit は Web アプリのみ）

## バージョン管理

- Git 使用
- ブランチ戦略: feature ブランチ → main → PR
- データは data/toilets.json.gz を直接コミット（large file tracking 不要なサイズ）
- batch/data/, batch/*.json, batch/*.json.gz は .gitignore で除外（スクレイプ中間ファイル）