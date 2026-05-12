# AGENTS.md

トイレきれい度マップ - プロジェクト固有の指示

## プロジェクト概要

Google Maps のレビューからトイレのきれい度を自動判定して Streamlit マップ上に表示するアプリ。

## 技術スタック

- **アプリ**: Python 3.11+ / Streamlit / Folium / streamlit-folium / Pandas
- **スクレイピング**: Docker / Google Maps Scraper
- **データ処理**: JSON / JSONL
- **テスト**: pytest

## コマンド

```bash
# アプリ起動
pip install -r requirements.txt
streamlit run app.py

# テスト実行
pytest tests/ -v

# スクレイプ実行
cd batch && kanto_phase1.bat

# データ処理
cd batch && python process_data.py raw_data.json ../data/toilets.json.gz --full
python process_data.py raw_data.json ../data/toilets.json.gz --incremental
python to_sqlite.py ../data/toilets.json.gz --incremental
python sync_db.py ../data/toilets.json.gz
```

## 設計方針

- `app.py`: Streamlit UI・地図構築のみ（ロジックは app_config, ui/*, batch/* に分離）
- `app_config.py`: 定数定義のみ（スコア範囲、フィルタ定義、都道府県中心座標）
- `ui/`: UI 表示専用（styles.py, components.py, popups.py）
- `batch/`: スクレイピング・データ処理パイプライン
- `data/toilets.json.gz`: 処理済みデータ（コミット対象）

## スコアリング

| スコア | 表示 | 判定 |
|---|---|---|
| 80-100 | ✨ | とてもきれい |
| 65-79 | 😊 | きれい |
| 50-64 | 😐 | 普通 |
| 35-49 | 😨 | 少し気になる |
| 0-34 | 💩 | 要注意 |

スコア = (raw_score + 5) × 10（-5〜+5 → 0〜100 変換）

## ファイル設計ルール

- 1ファイル1責務、300行以内
- 全ファイルにヘッダーコメント必須
- 複雑なロジックには必ずコメント
- シンプル最優先（不要の抽象化禁止）

## DB制約

なし（JSONファイルベース）

## API

なし（Streamlit は Web アプリのみ）

## バージョン管理

- Git 使用
- ブランチ戦略: feature ブランチ → main
- データは data/toilets.json を直接コミット（large file tracking 不要なサイズ）
- batch/data/ は .gitignore で除外（スクレイプ中間ファイル）