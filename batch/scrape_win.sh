#!/bin/bash
# ============================================
# トイレきれい度マップ - 熊谷市スクレイパー
# ============================================
# 特徴:
#   - エラーで中断しても途中から再開可能
#   - クエリ間スリープでアクセス制限対策
#   - 失敗クエリはリトライ
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QUERIES_FILE="$SCRIPT_DIR/queries.txt"
RAW_DIR="$SCRIPT_DIR/raw_parts"
RAW_OUTPUT="$SCRIPT_DIR/raw_data.json"
PROCESSED="$(cygpath -w "$SCRIPT_DIR/../data/toilets.json.gz")"
PROGRESS_FILE="$SCRIPT_DIR/.progress"

SLEEP_BETWEEN=120
MAX_RETRIES=2
RETRY_SLEEP=300

# 引数: --reset で進捗クリアして最初から
if [ "$1" = "--reset" ]; then
    rm -f "$PROGRESS_FILE"
    rm -rf "$RAW_DIR"
    echo "進捗をクリアしました。最初から開始します。"
    echo ""
fi

echo "============================================"
echo "  トイレきれい度マップ - 熊谷市スクレイプ"
echo "============================================"
echo ""

# Docker確認
docker version >nul 2>&1 || { echo "[ERROR] Dockerが起動していません"; exit 1; }

# クエリ読み込み（空行・コメント除外）
QUERIES=()
while IFS= read -r line || [ -n "$line" ]; do
    line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -z "$line" ] && continue
    [[ "$line" =~ ^# ]] && continue
    QUERIES+=("$line")
done < "$QUERIES_FILE"

TOTAL=${#QUERIES[@]}
echo "クエリ数: $TOTAL件"
echo "クエリ間スリープ: ${SLEEP_BETWEEN}秒"
echo "推定所要時間: ~$(( TOTAL * (180 + SLEEP_BETWEEN) / 60 ))分"
echo ""

# ── 進捗ファイルから再開位置を取得 ──
mkdir -p "$RAW_DIR"
COMPLETED=()

if [ -f "$PROGRESS_FILE" ]; then
    while IFS= read -r done_idx; do
        [ -n "$done_idx" ] && COMPLETED+=("$done_idx")
    done < "$PROGRESS_FILE"
    echo "前回の進捗: ${#COMPLETED[@]}/$TOTAL 完了済み"
    echo "途中から再開します"
    echo ""
else
    # 新規開始: 前回のrawデータをバックアップ
    if [ -f "$RAW_OUTPUT" ]; then
        cp "$RAW_OUTPUT" "${RAW_OUTPUT}.bak"
        echo "前回データをバックアップしました"
    fi
    rm -f "$RAW_DIR"/*.json
    > "$PROGRESS_FILE"
fi

# ── 完了済みかチェック ──
is_completed() {
    local idx="$1"
    for c in "${COMPLETED[@]}"; do
        [ "$c" = "$idx" ] && return 0
    done
    return 1
}

# ── メインループ ──
INDEX=0
SUCCESS=0
SKIPPED=0
FAILED=0

for query in "${QUERIES[@]}"; do
    INDEX=$((INDEX + 1))
    PART_FILE="$RAW_DIR/part_$(printf '%03d' $INDEX).json"

    # 完了済みならスキップ
    if is_completed "$INDEX"; then
        echo "[$INDEX/$TOTAL] (完了済み) $query"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    echo ""
    echo "──────────────────────────────────"
    echo "[$INDEX/$TOTAL] $query"
    echo "──────────────────────────────────"

    QUERY_FILE="$SCRIPT_DIR/.tmp_query.txt"
    echo "$query" > "$QUERY_FILE"
    QUERY_WIN="$(cygpath -w "$QUERY_FILE")"
    PART_WIN="$(cygpath -w "$PART_FILE")"

    RETRY=0
    OK=false

    while [ $RETRY -le $MAX_RETRIES ]; do
        if [ $RETRY -gt 0 ]; then
            echo "  リトライ #$RETRY ... (${RETRY_SLEEP}秒待機)"
            sleep $RETRY_SLEEP
        fi

        > "$PART_FILE"

        if MSYS_NO_PATHCONV=1 docker run --rm \
            -v "${QUERY_WIN}:C:/query.txt" \
            -v "${PART_WIN}:C:/results.json" \
            gosom/google-maps-scraper \
            -depth 1 \
            -input /query.txt \
            -results /results.json \
            -json \
            --extra-reviews \
            -lang ja \
            -exit-on-inactivity 5m 2>&1; then

            LINES=$(wc -l < "$PART_FILE" 2>/dev/null || echo 0)
            if [ "$LINES" -gt 0 ]; then
                echo "  ✓ 成功 (${LINES}件取得)"
                OK=true
                break
            else
                echo "  ✗ 結果なし"
            fi
        else
            echo "  ✗ Dockerエラー"
        fi

        RETRY=$((RETRY + 1))
    done

    rm -f "$QUERY_FILE"

    if $OK; then
        SUCCESS=$((SUCCESS + 1))
        # 進捗保存
        echo "$INDEX" >> "$PROGRESS_FILE"
        COMPLETED+=("$INDEX")
    else
        FAILED=$((FAILED + 1))
        echo "  !! 失敗: $query"
        echo "  進捗は保存済み。再実行でここから再開できます。"
    fi

    # 最後のクエリ以外はスリープ
    if [ $INDEX -lt $TOTAL ]; then
        echo "  スリープ ${SLEEP_BETWEEN}秒 ..."
        sleep $SLEEP_BETWEEN
    fi

done

# ── 結果マージ ──
echo ""
echo "============================================"
echo "  スクレイプ完了"
echo "  成功: $SUCCESS / スキップ: $SKIPPED / 失敗: $FAILED / 全$TOTAL"
echo "============================================"
echo ""
echo "結果をマージ中..."

> "$RAW_OUTPUT"
for f in "$RAW_DIR"/*.json; do
    [ -f "$f" ] && cat "$f" >> "$RAW_OUTPUT"
done

TOTAL_LINES=$(wc -l < "$RAW_OUTPUT" 2>/dev/null || echo 0)
echo "合計: ${TOTAL_LINES}件のrawデータ"
echo ""

# ── データ処理（差分更新）──
echo "データ処理中（差分マージ）..."
python "$SCRIPT_DIR/process_data.py" "$RAW_OUTPUT" "$PROCESSED" --incremental

# 成功なら進捗ファイルをクリア
if [ $FAILED -eq 0 ]; then
    rm -f "$PROGRESS_FILE"
    echo "進捗ファイルをクリアしました"
fi

# クリーンアップ
rm -rf "$RAW_DIR"

echo ""
echo "============================================"
echo "  全完了! → $PROCESSED"
echo "============================================"
