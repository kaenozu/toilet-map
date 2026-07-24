# Preview migration rehearsal preflight

`v2` の Preview migration rehearsal を実DBへ接続する前に、Windowsローカルで入力条件を固定するための読み取り専用チェックです。DockerやPostgreSQLは不要です。

## 実行

リポジトリ直下で、Previewに適用する承認済みのブランチ名と完全なコミットSHAを指定します。

```powershell
python scripts/preview_rehearsal_preflight.py `
  --expected-branch main `
  --expected-sha <approved-full-commit-sha>
```

結果は `artifacts/preview-rehearsal/preview-preflight-*.json` に保存されます。このディレクトリはGit管理対象外です。

## 検査内容

- 作業ツリーがcleanであること
- 現在のブランチと完全なコミットSHAが承認値と一致すること
- `data/toilets.json.gz` が存在し、サイズとSHA-256を記録できること
- `v2/backend/migrations/*.sql` の命名・バージョン重複・順序を検査できること
- `v2/backend/schema.sql` の `\ir` が実際のマイグレーション列と完全一致すること
- `DATABASE_URL` が設定されている場合、パスワードを出力せず接続先を記録すること

このスクリプトはデータベースへ接続せず、マイグレーションやデータ公開も実行しません。

## Preview接続先も事前照合する場合

接続URLはローカル環境変数だけに設定し、チャット・ログ・コミットへ貼り付けないでください。

```powershell
$env:DATABASE_URL = "<Preview PostgreSQL/PostGIS connection string>"
$env:TOILET_MAP_EXPECTED_DB_HOST = "<exact Preview DB host>"
$env:TOILET_MAP_EXPECTED_DB_NAME = "<exact Preview DB name>"

python scripts/preview_rehearsal_preflight.py `
  --expected-branch main `
  --expected-sha <approved-full-commit-sha>
```

`DATABASE_URL` のホスト名・DB名が期待値と異なる場合は失敗します。レポートにはscheme、host、port、database、userのみを記録し、パスワードは含めません。

## preflight通過後

Preview環境で、バックアップ取得後に次の順で実施します。

```powershell
cd v2/backend
python -m app.cli migration-status
python -m app.cli init-db
python -m app.cli migration-status
python -m app.cli import-legacy ../../data/toilets.json.gz --source legacy-json
python -m app.cli validate <dataset-id>
python -m app.cli publish <dataset-id>
python -m app.cli data-quality
```

公開後はsnapshot件数、互換ID、`/health`、`/api/v2/places`、`/api/v2/stats`、Frontend表示を確認し、ロールバック時だけ `PUBLIC_READ_MODEL=places` を使用します。
