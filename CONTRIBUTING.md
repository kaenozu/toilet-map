# Contributing to Toilet Map

## 開発の流れ

1. Issue で提案 / 既存 Issue を確認
2. `main` から feature ブランチを作成 (`git checkout -b feat/your-feature`)
3. 変更を加える
4. テストを実行: `pytest tests/ -v --tb=short`
5. Lint: `ruff check .`
6. PR を作成（テンプレートに従う）

## コード規約

- **1ファイル1責務、300行以内**
- 全ファイルにヘッダーコメント必須（パス、目的、存在理由、関連ファイル）
- 複雑なロジックにはコメントを入れる
- Type hints を書く
- シンプル最優先、不要な抽象化禁止

## テスト

- 新機能にはテストを追加（カバレッジ90%以上維持）
- `pytest tests/ -v` ですべてパスすること
- E2E テストは `tests/e2e/` に Playwright で記述

## データ

- `data/toilets.json.gz` が canonical データ
- スクレイピング結果は `batch/auto_expand_pipeline.bat` で自動処理
- DB変更は提案のみ、実行は人間が行う

## PR 作成前に確認

- [ ] 既存テストがすべてパスする (`pytest tests/ -v`)
- [ ] Lint が通る (`ruff check .`)
- [ ] 必要ならテストを追加した
- [ ] ヘッダーコメントを書いた
- [ ] 変更理由をPRに書いた
