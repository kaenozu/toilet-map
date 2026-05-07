# 🚽 トイレきれい度マップ

Google Maps のレビューからトイレのきれい度を自動判定して、地図と一覧で確認できる Streamlit アプリ。

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

アプリは [data/toilets.db](data/toilets.db) を参照します。JSON を更新しただけでは画面に反映されず、SQLite 変換まで完了している必要があります。

## 機能

- **インタラクティブマップ**: Folium のクラスタ表示で現在ページの施設を地図に表示
- **都道府県フィルター**: 都道府県ごとに絞り込み、件数が十分あれば都道府県中心へ移動
- **カテゴリフィルター**: すべて / 公共トイレ / カフェ・飲食 / コンビニ・店舗 / ホテル・旅館 / 道の駅 / SA・PA
- **全文検索**: 名前・住所の部分一致検索
- **ページネーション**: 一覧と地図は 20 件単位で同期表示し、描画負荷を抑制
- **簡易パフォーマンス表示**: 絞り込み時間と地図生成時間を画面下に表示
- **低信頼データの注記**: トイレ関連レビューが少ない施設はポップアップで参考値として表示

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

**注意点：**
- トイレ関連レビューが 1〜2 件程度しかない施設は、信頼度が低く参考値寄りになります。
- スコアはレビュー由来の自動推定であり、現地状態を保証しません。

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

## 更新フロー

標準の更新は [batch/update_data.bat](batch/update_data.bat) を使います。

```bash
cd batch
update_data.bat
```

内部では次の順で実行されます。

1. `nationwide_runner.py` が全国クエリを再生成し、全 batch ファイルを順にスクレイプ
2. 各 batch ごとに `process_data.py` と `to_sqlite.py` で JSON / SQLite を更新
3. `verify_data.py` で品質ゲートを実行

品質ゲートでは主に以下を確認します。

- スコア欠損率
- 住所・都道府県欠損率
- 重複率
- 想定都道府県に 0 件の偏りがないか

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

主要な回帰テストは以下です。

- [tests/test_process_data.py](tests/test_process_data.py): スコアリング、重複レビュー、境界値
- [tests/test_batch_regressions.py](tests/test_batch_regressions.py): 経度キー回帰、後処理パイプライン、品質ゲート
- [tests/test_popups.py](tests/test_popups.py): ポップアップの安全性と低信頼注記

## ライセンス

MIT