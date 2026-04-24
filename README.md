# 🚽 トイレきれい度マップ

Google Maps のレビューからトイレのきれい度を自動判定して、マップ上に表示するアプリ。

## フォルダ構成

```
toilet-map/
├── app.py                  # Streamlit メインアプリ
├── app_config.py           # 共有設定定数
├── data/
│   └── toilets.json      # 処理済みデータ
├── ui/
│   ├── styles.py        # Mobile CSS
│   ├── components.py    # Streamlit UIコンポーネント
│   └── popups.py        # ポップアップHTML生成
├── batch/
│   ├── scrape.bat          # Windows用スクレイプ
│   ├── scrape_runner.py    # スクレイプ実行エンジン
│   ├── process_data.py     # データ処理・スコアリング
│   ├── generate_queries.py # 全国クエリ生成
│   └── city_bounds.py      # 地理バウンディング取得
├── tests/
│   ├── test_app.py
│   ├── test_app_config.py
│   ├── test_popups.py
│   ├── test_ui_components.py
│   ├── test_batch.py
│   └── test_process_data.py
├── requirements.txt
├── .streamlit/config.toml
├── .gitignore
└── README.md
```

## ローカル実行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 機能

- **インタラクティブマップ**: トイレマーカーをマップに表示（ кластер化対応）
- **都道府県フィルター**: 47都道府県で絞り込み可能（データ範囲に応じてマップ中心が自動移動）
- **スコアフィルター**: すべて / 公共トイレ / カフェ・飲食 / コンビニ・店舗
- **全文検索**: 名前・住所で部分一致検索
- **ページネーション**: ランキングは20件ずつページ表示（マップは全件表示を維持）
- **ダークモード**: OS設定に応じて自動切替（`prefers-color-scheme: dark`）
- **地図スタイル切替**: OpenStreetMap / 航空写真 / CartoDB から選択
- **動的ズーム**: データ範囲に応じてマップズームを自動調整

## スコアリング仕様

| スコア | 表示 | 判定 |
|---|---|---|
| 80-100 | ✨ | とてもきれい |
| 65-79 | 😊 | きれい |
| 50-64 | 😐 | 普通 |
| 35-49 | 😨 | 少し気になる |
| 0-34 | 💩 | 要注意 |

**補正ロジック：**
- トイレ言及周辺の文だけをスコアリング（店舗全体の評価と分離）
- レビュー★5のネガティブは軽減、★1のポジティブは軽減
- 否定文脈検知（「清潔さが残念」等の誤検出防止）

## スクレイプ実行

```bash
cd batch

# 熊谷市（デフォルト）
scrape.bat

# さいたま市
set QUERIES=queries_saitama_city.txt
scrape.bat

# 最初からやり直し
scrape.bat --reset
```

エラーで中断しても `.progress` ファイルで途中から再開されます。

## Streamlit Cloud デプロイ

```bash
cd toilet-map
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/<user>/toilet-map.git
git push -u origin main
```

→ https://share.streamlit.io/ で New app → Deploy

## データ拡充（関東広域）

県庁所在地7市（さいたま・新宿・千葉・横浜・水戸・宇都宮・前橋）を順次スクレイピング。

### 実行

```bash
cd batch

# Phase 1 のみ実行（約7時間、84クエリ）
kanto_phase1.bat
```

### 中断・再開

各都市ごとに独立した進捗ファイル（`.progress_<都道府県>_phase1`）を使用しているため、途中で中断しても再実行で続きから自動再開されます。

### 個別実行（任意）

```bash
set QUERIES=queries.d\埼玉県\batch_001.txt
python scrape_runner.py --city さいたま市 --prefecture 埼玉県 --progress-file .progress_saitama_phase1
```

## テスト

```bash
pytest tests/ -v
```

## ライセンス

MIT