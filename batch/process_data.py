"""
トイレきれい度マップ - データ処理スクリプト
Google Maps Scraperの出力(JSONL)からトイレ情報を抽出・スコアリング

使い方: python process_data.py <input.json> <output.json>
"""
import json
import sys
import re
from collections import Counter

# ============================================================
# 定数
# ============================================================

# スコアリング範囲
SCORE_CLAMP_MIN = -5.0
SCORE_CLAMP_MAX = 5.0
DISPLAY_SCORE_OFFSET = 5       # -5..5 → 0..100 変換用
DISPLAY_SCORE_MULTIPLIER = 10

# 信頼度
CONFIDENCE_MAX_REVIEWS = 5.0   # 5件で信頼度MAX
CONFIDENCE_LOW = 0.1           # 店舗評価のみの場合

# レビュー評価によるスコア補正
RATING_THRESHOLD_HIGH = 4
RATING_THRESHOLD_LOW = 2
POSITIVE_BOOST_HIGH = 1.2
NEGATIVE_DAMPEN_HIGH = 0.4
POSITIVE_DAMPEN_LOW = 0.4
NEGATIVE_BOOST_LOW = 1.2

# 否定文脈検知
NEGATION_WINDOW = 30  # キーワードと否定語の近傍文字数

# 否定語リスト
NEGATION_WORDS = [
    "ない", "なし", "なく", "ません", "無い",
    "残念", "ひどい", "酷い", "最悪", "問題", "不満",
    "がっかり", "だらけ", "されてない", "されていない",
]

# キーワード辞書
POSITIVE_KEYWORDS = {
    "きれい": 3, "綺麗": 3, "キレイ": 3, "清潔": 4, "クリーン": 3,
    "ピカピカ": 4, "新品": 3, "清潔感": 3,
    "バリアフリー": 2, "多目的トイレ": 2, "オストメ": 1,
    "ウォシュレット付き": 2, "温水洗浄": 2, "暖房便座": 1,
    "ベビー": 2, "オムツ": 2, "車椅子": 2,
    "完備": 2, "充実": 1,
    "使いやすい": 2, "広い": 2, "ゆったり": 2,
    "いい匂い": 2, "良い匂い": 2, "よい匂い": 2, "匂いがしない": 2,
    "明るい": 1, "嬉しい": 1, "気兼ねなく": 1,
}

NEGATIVE_KEYWORDS = {
    "汚い": -4, "汚れてる": -3, "汚れていた": -3, "汚れています": -3,
    "こびりつき": -4, "こびり付い": -4, "カビ": -3, "汚物": -4,
    "臭い": -3, "悪臭": -4, "異臭": -4,
    "臭い匂い": -3, "変な匂い": -3, "匂いがきつい": -3,
    "びしょびしょ": -3, "詰まって": -3, "詰まり": -3,
    "狭い": -2, "暗い": -2,
    "故障": -3, "壊れて": -3, "壊れ": -2,
    "使えない": -4, "使用不可": -4,
    "紙がない": -3, "ペーパーがな": -3,
    "ウォシュレット無": -2, "ウォシュレットなく": -2, "ウォシュレットない": -2,
    "ウォシュレットではない": -2, "和式": -1,
    "ホコリ": -3, "埃": -3, "だらけ": -3,
    "掃除されてない": -4, "掃除されていない": -4,
    "掃除してない": -4, "掃除が行き届いてない": -4, "掃除ができてない": -4,
    "溜まって": -2, "溜まっていた": -3,
    "残念": -2, "ひどい": -4, "酷い": -4, "最悪": -4,
    "がっかり": -3, "ガッカリ": -3, "不潔": -4,
}

# トイレ言及検出キーワード
TOILET_MENTION_KEYWORDS = [
    "トイレ", "お手洗い", "おてあらい", "化粧室", "洗面所",
    " restroom", " washroom", " bathroom",
    "ウォシュレット", "シャワートイレ",
]

# カテゴリ判定
TOILET_CATEGORIES = ["公共トイレ", "トイレ", "restroom"]

# プリコンパイル正規表現
SENTENCE_SPLIT_RE = re.compile(r'[。\n]')
TOILET_MENTION_RE = re.compile(
    '|'.join(re.escape(k) for k in TOILET_MENTION_KEYWORDS),
    re.IGNORECASE,
)
AREA_NAME_RE = re.compile(r"(\S+県\S+[市区町村])")


# ============================================================
# トイレ言及検出
# ============================================================
def mentions_toilet(text: str) -> bool:
    """テキストがトイレに言及しているか（大文字小文字無視）"""
    return bool(TOILET_MENTION_RE.search(text))


def extract_toilet_contexts(text: str) -> list[str]:
    """トイレ言及箇所の前後文を抽出。
    句点・改行で文分割し、トイレ言及を含む文＋前後1文を返す。
    """
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]

    toilet_indices = set()
    for i, sent in enumerate(sentences):
        if mentions_toilet(sent):
            for j in range(max(0, i - 1), min(len(sentences), i + 2)):
                toilet_indices.add(j)

    return [sentences[i] for i in sorted(toilet_indices)] if toilet_indices else []


# ============================================================
# スコアリング
# ============================================================
def _apply_keyword_scoring(target_text: str) -> tuple[float, list[str]]:
    """キーワードマッチングでスコアとマッチリストを返す"""
    score = 0.0
    matched = []

    for kw, val in POSITIVE_KEYWORDS.items():
        cnt = target_text.count(kw)
        if cnt > 0:
            score += val * cnt
            matched.append(f"+{kw}")

    for kw, val in NEGATIVE_KEYWORDS.items():
        cnt = target_text.count(kw)
        if cnt > 0:
            score += val * cnt
            matched.append(f"-{kw}")

    return score, matched


def _apply_negation_correction(target_text: str, score: float, matched: list[str]) -> tuple[float, list[str]]:
    """否定語が近傍にあるポジティブキーワードのスコアを打ち消す"""
    for neg_word in NEGATION_WORDS:
        if neg_word not in target_text:
            continue
        neg_positions = [m.start() for m in re.finditer(re.escape(neg_word), target_text)]

        for kw, val in POSITIVE_KEYWORDS.items():
            if kw not in target_text:
                continue
            kw_positions = [m.start() for m in re.finditer(re.escape(kw), target_text)]

            cancelled = False
            for kp in kw_positions:
                for np in neg_positions:
                    if abs(kp - np) < NEGATION_WINDOW:
                        score -= val
                        tag = f"+{kw}"
                        if tag in matched:
                            matched.remove(tag)
                        cancelled = True
                        break
                if cancelled:
                    break

    return score, matched


def score_toilet_from_review(text: str) -> tuple[float, list[str]]:
    """レビューテキストからトイレきれい度スコアを算出 (-5〜+5)"""
    contexts = extract_toilet_contexts(text) or [text]
    target_text = "。".join(contexts)

    score, matched = _apply_keyword_scoring(target_text)
    score, matched = _apply_negation_correction(target_text, score, matched)

    return max(SCORE_CLAMP_MIN, min(SCORE_CLAMP_MAX, score)), matched


# ============================================================
# 住所から都道府県を抽出
# ============================================================
# 日本の都道府県リスト（便宜上用いる順序）
PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]


def extract_prefecture(address: str) -> str:
    """住所から都道府県名を抽出（部分一致）"""
    if not address:
        return ""
    for pref in PREFECTURES:
        if pref in address:
            return pref
    return ""


# ============================================================
# レビュー評価による補正
# ============================================================
def _adjust_by_rating(score: float, matched: list[str], rating: float) -> tuple[float, list[str]]:
    """レビュー星数に基づいてスコアを補正"""
    if rating >= RATING_THRESHOLD_HIGH:
        if score < 0:
            score *= NEGATIVE_DAMPEN_HIGH
            matched = [m for m in matched if not m.startswith("-")] + \
                       [f"~{m[1:]}" for m in matched if m.startswith("-")]
        elif score > 0:
            score *= POSITIVE_BOOST_HIGH
    elif rating <= RATING_THRESHOLD_LOW:
        if score > 0:
            score *= POSITIVE_DAMPEN_LOW
            matched = [m for m in matched if not m.startswith("+")] + \
                       [f"~{m[1:]}" for m in matched if m.startswith("+")]
        elif score < 0:
            score *= NEGATIVE_BOOST_LOW
    return score, matched


# ============================================================
# 地点スコア計算
# ============================================================
def compute_toilet_score(place: dict) -> dict:
    """1地点のトイレスコアを計算"""
    reviews = (place.get("user_reviews") or []) + (place.get("user_reviews_extended") or [])

    toilet_reviews = []
    total_score = 0.0
    all_highlights = []
    seen_descs = set()

    for r in reviews:
        desc = r.get("Description", "")
        if not desc or not desc.strip() or not mentions_toilet(desc):
            continue

        desc_key = desc.strip()[:100]
        if desc_key in seen_descs:
            continue
        seen_descs.add(desc_key)

        s, matched = score_toilet_from_review(desc)

        # レビュー星数補正
        rating = float(r.get("Rating") or 0)
        s, matched = _adjust_by_rating(s, matched, rating)
        s = max(SCORE_CLAMP_MIN, min(SCORE_CLAMP_MAX, s))

        toilet_reviews.append({
            "text": desc,
            "rating": r.get("Rating"),
            "when": r.get("When"),
            "name": r.get("Name"),
            "score": round(s, 2),
            "matched_keywords": matched,
            "toilet_context": "。".join(extract_toilet_contexts(desc)),
        })
        total_score += s
        all_highlights.extend(matched)

    # 総合スコア算出
    if toilet_reviews:
        avg_score = total_score / len(toilet_reviews)
        place_rating = float(place.get("review_rating") or 0)
        final_score = avg_score * 0.7 + (place_rating - 3.0) * 0.3
        confidence = min(1.0, len(toilet_reviews) / CONFIDENCE_MAX_REVIEWS)
    else:
        place_rating = float(place.get("review_rating") or 0)
        if place_rating > 0:
            final_score = (place_rating - 3.0) * 0.5
            confidence = CONFIDENCE_LOW
        else:
            final_score = 0.0
            confidence = 0.0

    final_score = max(SCORE_CLAMP_MIN, min(SCORE_CLAMP_MAX, final_score))
    highlight_counts = Counter(all_highlights)

    return {
        "score": round(final_score, 2),
        "confidence": round(confidence, 2),
        "toilet_review_count": len(toilet_reviews),
        "toilet_reviews": toilet_reviews[:20],
        "top_keywords": highlight_counts.most_common(5),
    }


# ============================================================
# 施設判定
# ============================================================
def is_toilet_place(place: dict) -> bool:
    """施設自体がトイレ（公共トイレ等）かどうか"""
    cat = (place.get("category") or "").lower()
    title = (place.get("title") or "").lower()
    return any(tc.lower() in cat or tc.lower() in title for tc in TOILET_CATEGORIES)


# ============================================================
# データ変換
# ============================================================
def process_place(place: dict) -> dict | None:
    """1地点を処理してUI用データに変換"""
    lat = place.get("latitude")
    lon = place.get("longitude") or place.get("longtitude")  # 古いキー互換
    if not lat or not lon:
        return None

    title = place.get("title", "")
    if not title:
        return None

    info = compute_toilet_score(place)
    display_score = (info["score"] + DISPLAY_SCORE_OFFSET) * DISPLAY_SCORE_MULTIPLIER

    return {
        "title": title,
        "category": place.get("category", ""),
        "address": place.get("address", ""),
        "lat": float(lat),
        "lng": float(lon),
        "phone": place.get("phone", ""),
        "rating": float(place.get("review_rating") or 0),
        "review_count": int(place.get("review_count") or 0),
        "link": place.get("link", ""),
        "is_public_toilet": is_toilet_place(place),
        "toilet_score": round(display_score, 1),
        "confidence": info["confidence"],
        "toilet_review_count": info["toilet_review_count"],
        "top_keywords": info["top_keywords"],
        "sample_reviews": info["toilet_reviews"][:5],
        "prefecture": extract_prefecture(place.get("address", "")),
    }


# ============================================================
# 重複除去キー
# ============================================================
def make_place_key(place: dict) -> str:
    """未処理データの一意キー（title + 座標丸め）"""
    title = place.get("title", "")
    lat = float(place.get("latitude") or 0)
    lng = float(place.get("longitude") or place.get("longtitude") or 0)
    return f"{title}@{lat:.4f},{lng:.4f}"


def make_result_key(result: dict) -> str:
    """処理済みデータの一意キー"""
    return f"{result['title']}@{result['lat']:.4f},{result['lng']:.4f}"


# ============================================================
# ファイルI/O
# ============================================================
def load_jsonl(path: str) -> list[dict]:
    """JSONLファイルを読み込む"""
    places = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                places.append(json.loads(line))
    return places


def load_existing(path: str) -> dict:
    """既存のtoilets.jsonを読み込む"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"metadata": None, "toilets": []}


def deduplicate(places: list[dict]) -> list[dict]:
    """title+座標ベースで重複除去"""
    seen = set()
    unique = []
    for p in places:
        key = make_place_key(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


# ============================================================
# メタデータ生成
# ============================================================
def build_metadata(results: list[dict]) -> dict:
    """結果リストからメタデータを自動生成"""
    if results:
        center_lat = sum(r["lat"] for r in results) / len(results)
        center_lng = sum(r["lng"] for r in results) / len(results)
    else:
        center_lat, center_lng = 36.2231, 139.3772

    area_name = "検索エリア"
    if results:
        addrs = [r.get("address", "") for r in results if r.get("address")]
        if addrs:
            m = AREA_NAME_RE.search(addrs[0])
            if m:
                area_name = m.group(1)

    return {
        "total": len(results),
        "scored": sum(1 for r in results if r["confidence"] > 0),
        "public_toilets": sum(1 for r in results if r["is_public_toilet"]),
        "center_lat": round(center_lat, 4),
        "center_lng": round(center_lng, 4),
        "zoom": 13,
        "area_name": area_name,
    }


# ============================================================
# メイン処理
# ============================================================
def process_file(input_path: str, output_path: str, mode: str = "--full"):
    """スクレイプデータを処理して出力"""
    # 読み込み・重複除去
    places = load_jsonl(input_path)
    print(f"スクレイプデータ: {len(places)}件")

    unique_places = deduplicate(places)
    print(f"重複除去後: {len(unique_places)}件")

    # 処理
    new_results = {}
    for place in unique_places:
        processed = process_place(place)
        if processed:
            new_results[make_result_key(processed)] = processed
    print(f"新規処理済み: {len(new_results)}件")

    # マージ or フル再生成
    if mode == "--incremental":
        existing = load_existing(output_path)
        merged = {make_result_key(t): t for t in existing.get("toilets", [])}

        new_count = sum(1 for k in new_results if k not in merged)
        updated_count = sum(1 for k in new_results if k in merged)
        merged.update(new_results)

        results = list(merged.values())
        print(f"差分マージ: 新規追加 {new_count}件 / 更新 {updated_count}件 / 既存維持 {len(merged) - new_count - updated_count}件")

        metadata = existing.get("metadata") or build_metadata(results)
    else:
        results = list(new_results.values())
        metadata = build_metadata(results)
        print(f"フル再生成: {len(results)}件")

    # ソート・統計
    results.sort(key=lambda x: x["toilet_score"], reverse=True)
    metadata["total"] = len(results)
    metadata["scored"] = sum(1 for r in results if r["confidence"] > 0)
    metadata["public_toilets"] = sum(1 for r in results if r["is_public_toilet"])

    print(f"出力: {len(results)}件 (スコアあり {metadata['scored']}件 / 公共トイレ {metadata['public_toilets']}件)")

    # 書き出し
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "toilets": results}, f, ensure_ascii=False, indent=2)
    print(f"出力完了: {output_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python process_data.py <input.json> <output.json>")
        print("  --full        既存データを無視して全件再生成（デフォルト）")
        print("  --incremental 既存データに差分マージ")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "--full"
    process_file(input_path, output_path, mode)


if __name__ == "__main__":
    main()
