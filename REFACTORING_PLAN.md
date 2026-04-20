# リファクタリング完了報告

## 実施日: 2026-04-20

## 変更概要

### app.py (230行 → 290行)
| 変更項目 | 内容 |
|---------|------|
| **定数抽出** | `SCORE_RANGES`, `FILTER_CONFIG`, `POPUP_BASE_STYLE` などをモジュールトップに集約 |
| **スコア関数統合** | `score_to_color()` / `score_to_emoji()` / `score_label()` → `get_score_style()` に統一 |
| **HTMLエスケープ** | 自作 `esc()` → 標準ライブラリ `html.escape()` に置換 |
| **ポップアップ分割** | `build_map()` 内の巨大HTML生成を `build_popup_html()` / `_build_keyword_tags()` / `_build_review_html()` / `_build_link_html()` / `_build_public_badge()` に分離 |
| **マーカー定数** | `PUBLIC_MARKER_RADIUS=14`, `NORMAL_MARKER_RADIUS=10` を定数化 |
| **フィルタ設定** | `FILTER_CONFIG` 辞書でフィルタ定義を一元管理 |
| **検索関数分離** | `search_toilets()` を独立関数化 |
| **凡例表示** | `render_score_legend()` に分離 |

### batch/process_data.py (474行 → 380行)
| 変更項目 | 内容 |
|---------|------|
| **定数化** | マジックナンバーを全て名前付き定数に（`SCORE_CLAMP_*`, `CONFIDENCE_*`, `NEGATION_WINDOW` 等） |
| **プリコンパイル正規表現** | `SENTENCE_SPLIT_RE`, `TOILET_MENTION_RE`, `AREA_NAME_RE` をモジュールトップでコンパイル |
| **スコアリング分割** | `score_toilet_from_review()` → `_apply_keyword_scoring()` + `_apply_negation_correction()` に分離 |
| **レビュー補正分離** | `_adjust_by_rating()` に独立関数化 |
| **I/O関数化** | `load_jsonl()`, `deduplicate()`, `count_lines()`, `merge_part_files()` を追加 |
| **メタデータ生成** | `build_metadata()` に独立関数化、`import re` の局所使用を排除 |
| **メイン処理** | `process_file()` にロジックを分離、`main()` は引数解析のみに |

### batch/scrape_runner.py (260行 → 220行)
| 変更項目 | 内容 |
|---------|------|
| **設定の環境変数化** | `SLEEP_BETWEEN`, `MAX_RETRIES`, `RETRY_SLEEP` を環境変数で上書き可能に |
| **Docker設定定数化** | `DOCKER_IMAGE`, `SCRAPER_DEPTH`, `SCRAPER_LANG` 等を定数化 |
| **I/O関数化** | `load_queries()`, `load_progress()`, `save_progress()`, `merge_part_files()`, `count_lines()` に分離 |
| **パス変換** | `win_to_docker_path()` → `to_docker_path()` にリネーム |
| **メイン処理** | `run_batch()` にロジックを分離 |
| **進捗チェック** | 欠落partファイル検出をセット内包表記で簡潔化 |

### batch/generate_queries.py (346行 → 320行)
| 変更項目 | 内容 |
|---------|------|
| **クエリ生成分離** | `build_queries()` / `write_batches()` に分離 |
| **定数化** | `BATCH_SIZE`, `QUERY_TEMPLATES` を明示的に定義 |
| **重複エントリ除去** | 熊本県から "阿苏市" (中国語表記) を削除、佐賀県から重複 "嬉野市" を削除 |
| **福井県重複除去** | 重複していた "敦賀市" を削除 |
| **鹿児島県修正** | "萨摩町" (中国語表記) → "さつま町" に修正 |
| **大阪府修正** | "廿日町市" を正しい "廿日町市" に修正 |
