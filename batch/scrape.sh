#!/bin/bash
# ============================================
# トイレきれい度マップ - 熊谷市スクレイパー
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QUERIES_FILE="$SCRIPT_DIR/queries.txt"
RAW_DIR="$SCRIPT_DIR/raw_parts"
RAW_OUTPUT="$SCRIPT_DIR/raw_data.json"
PROCESSED="$SCRIPT_DIR/../data/toilets.json.gz"
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

TOTAL=$(grep -cve '^\s*$' "$QUERIES_FILE" | head -1)
echo "クエリ数: $TOTAL件"
echo "推定所要時間: ~$(( TOTAL * (180 + SLEEP_BETWEEN) / 60 ))分"
echo ""

mkdir -p "$RAW_DIR"
COMPLETED=()

if [ -f "$PROGRESS_FILE" ]; then
    while IFS= read -r done_idx; do
        [ -n "$done_idx" ] && COMPLETED+=("$done_idx")
    done < "$PROGRESS_FILE"
    echo "前回の進捗: ${#COMPLETED[@]}/$TOTAL 完了済み - 途中から再開"
    echo ""
else
    [ -f "$RAW_OUTPUT" ] && cp "$RAW_OUTPUT" "${RAW_OUTPUT}.bak"
    rm -f "$RAW_DIR"/*.json
    > "$PROGRESS_FILE"
fi

is_completed() {
    for c in "${COMPLETED[@]}"; do
        [ "$c" = "$1" ] && return 0
    done
    return 1
}

INDEX=0
SUCCESS=0
SKIPPED=0
FAILED=0

while IFS= read -r query || [ -n "$query" ]; do
    query=$(echo "$query" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -z "$query" ] && continue
    [[ "$query" =~ ^# ]] && continue

    INDEX=$((INDEX + 1))
    PART_FILE="$RAW_DIR/part_$(printf '%03d' $INDEX).json"

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

    RETRY=0
    OK=false

    while [ $RETRY -le $MAX_RETRIES ]; do
        [ $RETRY -gt 0 ] && { echo "  リトライ #$RETRY ... (${RETRY_SLEEP}秒待機)"; sleep $RETRY_SLEEP; }
        > "$PART_FILE"

        if docker run --rm \
            -v "$QUERY_FILE":/query.txt \
            -v "$PART_FILE":/results.json \
            gosom/google-maps-scraper \
            -depth 1 -input /query.txt -results /results.json \
            -json --extra-reviews -lang ja -exit-on-inactivity 5m 2>&1; then

            LINES=$(wc -l < "$PART_FILE" 2>/dev/null || echo 0)
            if [ "$LINES" -gt 0 ]; then
                echo "  ✓ 成功 (${LINES}件取得)"
                OK=true
                break
            fi
        fi
        RETRY=$((RETRY + 1))
    done

    rm -f "$QUERY_FILE"

    if $OK; then
        SUCCESS=$((SUCCESS + 1))
        echo "$INDEX" >> "$PROGRESS_FILE"
        COMPLETED+=("$INDEX")
    else
        FAILED=$((FAILED + 1))
        echo "  !! 失敗: $query - 再実行でここから再開可能"
    fi

    [ $INDEX -lt $TOTAL ] && { echo "  スリープ ${SLEEP_BETWEEN}秒 ..."; sleep $SLEEP_BETWEEN; }

done < "$QUERIES_FILE"

echo ""
echo "マージ中..."
> "$RAW_OUTPUT"
for f in "$RAW_DIR"/*.json; do
    [ -f "$f" ] && cat "$f" >> "$RAW_OUTPUT"
done

echo "データ処理中（差分マージ）..."
python "$SCRIPT_DIR/process_data.py" "$RAW_OUTPUT" "$PROCESSED" --incremental

[ $FAILED -eq 0 ] && rm -f "$PROGRESS_FILE"
rm -rf "$RAW_DIR"

echo ""
echo "============================================"
echo "  全完了!  成功: $SUCCESS / スキップ: $SKIPPED / 失敗: $FAILED"
echo "============================================"
