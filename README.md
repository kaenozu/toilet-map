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
│   ├── components.py  # Streamlit UIコンポーネント
│   └── popups.py      # ポップアップHTML生成
├── batch/
│   ├── scrape.bat          # Windows用スクレイプ
│   ├── scrape_runner.py    # スクレイプ実行エンジン
│   ├── process_data.py   # データ処理・スコアリング
│   ├── generate_queries.py  # 全国クエリ生成
│   └── city_bounds.py   # 地理バウンディング取得
├── tests/
│   ├── test_app.py       # app.pyテスト
│   ├── test_batch.py    # batchモジュールテスト
│   └── test_process_data.py  # スコアリングテスト
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

## ライセンス

MIT
