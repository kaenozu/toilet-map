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
├── app_config.py           # 定数定義
├── ui/                    # UIコンポーネント
│   ├── components.py      # 凡例などの共通表示
│   ├── data_loader.py     # データ読み込み
│   ├── filters.py         # フィルタリング・検索
│   ├── map_builder.py     # Folium地図構築
│   ├── popups.py         # ポップアップHTML生成
│   ├── stats.py          # 統計表示
│   ├── pagination.py      # ページネーション
│   └── i18n.py          # 多言語対応
├── batch/                 # バッチ処理
│   ├── process_data.py    # スクレイピングデータ処理
│   ├── scrape_runner.py  # スクレイピング実行エンジン
│   ├── to_sqlite.py      # JSON→SQLite変換
│   ├── sync_db.py        # JSON→SQLite同期ラッパー
│   ├── update_data.bat    # 一括更新バッチ
│   ├── generate_queries.py # クエリ自動生成
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

## 品質チェック
- `batch/generate_queries.py` は重複クエリを除外して batch を生成します
- `batch/verify_data.py` は JSON と SQLite の差分を都道府県単位まで確認します
- CI では `pytest` に加えて `batch/verify_data.py` も実行します
- `tests/test_batch_regressions.py` と `tests/test_map_builder.py` が主要回帰をカバーします

## テスト実行
```bash
pytest tests/ -v
```

## 注意事項
- `data/toilets.json.gz` と `data/toilets.db` はコミット対象です
- `batch/raw_data.json` や `batch/raw_parts_*/` は `.gitignore` で除外されています
- Docker Desktopが起動している状態でスクレイピングを実行してください
