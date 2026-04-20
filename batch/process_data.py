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
# トイレきれい度スコアリング
# ============================================================

POSITIVE_KEYWORDS = {
    # 清潔系（フレーズ単位で正確にマッチ）
    "きれい": 3, "綺麗": 3, "キレイ": 3, "清潔": 4, "クリーン": 3,
    "ピカピカ": 4, "新品": 3,
    "清潔感": 3,
    # 設備系（トイレ固有のものに限定）
    "バリアフリー": 2, "多目的トイレ": 2, "オストメ": 1,
    "ウォシュレット付き": 2, "温水洗浄": 2, "暖房便座": 1,
    "ベビー": 2, "オムツ": 2, "車椅子": 2,
    "完備": 2, "充実": 1,
    # 快適系（フレーズ単位）
    "使いやすい": 2,
    "広い": 2, "ゆったり": 2,
    "いい匂い": 2, "良い匂い": 2, "よい匂い": 2, "匂いがしない": 2,
    "明るい": 1,
    "嬉しい": 1,
    "気兼ねなく": 1,
}

NEGATIVE_KEYWORDS = {
    # 汚れ系
    "汚い": -4, "汚れてる": -3, "汚れていた": -3, "汚れています": -3,
    "こびりつき": -4, "こびり付い": -4,
    "カビ": -3, "汚物": -4,
    # 不快系
    "臭い": -3, "悪臭": -4, "異臭": -4,
    "臭い匂い": -3, "変な匂い": -3, "匂いがきつい": -3,
    "びしょびしょ": -3,
    "詰まって": -3, "詰まり": -3,
    # 設備問題系
    "狭い": -2, "暗い": -2,
    "故障": -3, "壊れて": -3, "壊れ": -2,
    "使えない": -4, "使用不可": -4,
    "紙がない": -3, "ペーパーがな": -3,
    "ウォシュレット無": -2, "ウォシュレットなく": -2, "ウォシュレットない": -2,
    "ウォシュレットではない": -2,
    "和式": -1,
    # 不潔系
    "ホコリ": -3, "埃": -3,
    "だらけ": -3,
    "掃除されてない": -4, "掃除されていない": -4,
    "掃除してない": -4, "掃除が行き届いてない": -4,
    "掃除ができてない": -4,
    "溜まって": -2, "溜まっていた": -3,
    # 不満系
    "残念": -2,
    "ひどい": -4, "酷い": -4, "最悪": -4,
    "がっかり": -3, "ガッカリ": -3,
    "不潔": -4,
}

# トイレ言及を検出するキーワード
TOILET_MENTION_KEYWORDS = [
    "トイレ", "お手洗い", "おてあらい", "化粧室", "洗面所",
    " restroom", " washroom", " bathroom",
    "ウォシュレット", "シャワートイレ",
]

# カテゴリでトイレ関連を判定
TOILET_CATEGORIES = [
    "公共トイレ", "トイレ", "restroom",
]


def mentions_toilet(text: str) -> bool:
    """テキストがトイレに言及しているか"""
    text_lower = text.lower()
    return any(k in text_lower for k in TOILET_MENTION_KEYWORDS)


def extract_toilet_contexts(text: str, window: int = 80) -> list[str]:
    """トイレ言及箇所の前後を抽出する。
    "トイレ"などのキーワードを含む文の前後window文字を切り出す。
    改行・句点で文を分割し、トイレ言及を含む文＋その前後1文を返す。
    """
    # 文単位で分割（句点・改行基準）
    sentences = re.split(r'[。\n]', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    toilet_sentences = set()
    for i, sent in enumerate(sentences):
        if mentions_toilet(sent):
            # トイレ言及を含む文＋前後1文
            for j in range(max(0, i - 1), min(len(sentences), i + 2)):
                toilet_sentences.add(j)

    if not toilet_sentences:
        return []

    contexts = [sentences[i] for i in sorted(toilet_sentences)]
    return contexts


def score_toilet_from_review(text: str) -> tuple[float, list[str]]:
    """レビューテキストからトイレきれい度スコアを算出 (-5〜+5)
    トイレ言及周辺の文だけをスコアリング対象にする。
    """
    contexts = extract_toilet_contexts(text)
    if not contexts:
        # フォールバック: 全文をスコアリング
        contexts = [text]

    target_text = "。".join(contexts)

    score = 0.0
    matched = []

    for keyword, value in POSITIVE_KEYWORDS.items():
        count = target_text.count(keyword)
        if count > 0:
            score += value * count
            matched.append(f"+{keyword}")

    for keyword, value in NEGATIVE_KEYWORDS.items():
        count = target_text.count(keyword)
        if count > 0:
            score += value * count
            matched.append(f"-{keyword}")

    # 否定文脈補正: ポジティブキーワードが否定形で使われていないか
    NEGATION_WORDS = ["ない", "なし", "なく", "ません", "無い",
                      "残念", "ひどい", "酷い", "最悪", "問題", "不満",
                      "がっかり", "だらけ", "されてない", "されていない"]
    for neg_word in NEGATION_WORDS:
        if neg_word in target_text:
            # ポジティブキーワードが近傍（20文字以内）にあれば、そのスコアを打ち消す
            for keyword, value in POSITIVE_KEYWORDS.items():
                if keyword in target_text:
                    # キーワード出現位置と否定語出現位置の距離をチェック
                    for m in re.finditer(re.escape(keyword), target_text):
                        for nm in re.finditer(re.escape(neg_word), target_text):
                            if abs(m.start() - nm.start()) < 30:
                                score -= value  # ポジティブスコアを相殺
                                if f"+{keyword}" in matched:
                                    matched.remove(f"+{keyword}")
                                break

    # -5〜+5にクランプ
    score = max(-5.0, min(5.0, score))

    return score, matched


def compute_toilet_score(place: dict) -> dict:
    """
    1地点のトイレスコアを計算
    戻り値: {score, confidence, toilet_reviews, highlights}
    """
    reviews = (place.get("user_reviews") or []) + (place.get("user_reviews_extended") or [])

    toilet_reviews = []
    total_score = 0.0
    all_highlights = []
    seen_descs = set()

    for r in reviews:
        desc = r.get("Description", "")
        if not desc or not desc.strip():
            continue
        if not mentions_toilet(desc):
            continue
        # 重複レビューをスキップ
        desc_key = desc.strip()[:100]
        if desc_key in seen_descs:
            continue
        seen_descs.add(desc_key)

        s, matched = score_toilet_from_review(desc)

        # レビュー星数による補正
        review_rating = r.get("Rating")
        if review_rating:
            review_rating = float(review_rating)
        else:
            review_rating = 0

        # ★5でネガティブキーワード → スコアを軽くする（大幅な不満でない限り）
        # ★1でポジティブキーワード → スコアを軽くする
        if review_rating >= 4:
            # 高評価レビュー: ネガティブスコアを半減
            if s < 0:
                s = s * 0.4
                matched = [m for m in matched if not m.startswith("-")] + [f"~{m[1:]}" for m in matched if m.startswith("-")]
            # 高評価レビュー: ポジティブスコアを少し増
            elif s > 0:
                s = s * 1.2
        elif review_rating <= 2:
            # 低評価レビュー: ポジティブスコアを半減
            if s > 0:
                s = s * 0.4
                matched = [m for m in matched if not m.startswith("+")] + [f"~{m[1:]}" for m in matched if m.startswith("+")]
            # 低評価レビュー: ネガティブスコアを少し増
            elif s < 0:
                s = s * 1.2

        s = max(-5.0, min(5.0, s))

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

    # 総合スコア
    if toilet_reviews:
        avg_score = total_score / len(toilet_reviews)
        # 店舗の総合評価も考慮（重み0.3）
        place_rating = float(place.get("review_rating") or 0)
        final_score = avg_score * 0.7 + (place_rating - 3.0) * 0.3  # rating 3を中性に
        confidence = min(1.0, len(toilet_reviews) / 5.0)  # 5件で信頼度MAX
    else:
        # レビューにトイレ言及がない場合
        place_rating = float(place.get("review_rating") or 0)
        if place_rating > 0:
            # 店舗評価から推定（信頼度低）
            final_score = (place_rating - 3.0) * 0.5
            confidence = 0.1
        else:
            final_score = 0.0
            confidence = 0.0

    # -5〜+5にクランプ
    final_score = max(-5.0, min(5.0, final_score))

    # ハイライト集計
    highlight_counts = Counter(all_highlights)

    return {
        "score": round(final_score, 2),
        "confidence": round(confidence, 2),
        "toilet_review_count": len(toilet_reviews),
        "toilet_reviews": toilet_reviews[:20],  # 最大20件保存
        "top_keywords": highlight_counts.most_common(5),
    }


def is_toilet_place(place: dict) -> bool:
    """施設自体がトイレ（公共トイレ等）かどうか"""
    cat = (place.get("category") or "").lower()
    title = (place.get("title") or "").lower()
    for tc in TOILET_CATEGORIES:
        if tc.lower() in cat or tc.lower() in title:
            return True
    return False


def process_place(place: dict) -> dict | None:
    """1地点を処理してUI用データに変換"""
    lat = place.get("latitude")
    lon = place.get("longtitude")
    if not lat or not lon:
        return None

    title = place.get("title", "")
    if not title:
        return None

    toilet_info = compute_toilet_score(place)
    is_public_toilet = is_toilet_place(place)

    # スコアを0〜100に変換（-5→0, 0→50, +5→100）
    display_score = (toilet_info["score"] + 5) * 10

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
        "is_public_toilet": is_public_toilet,
        "toilet_score": round(display_score, 1),  # 0-100
        "confidence": toilet_info["confidence"],
        "toilet_review_count": toilet_info["toilet_review_count"],
        "top_keywords": toilet_info["top_keywords"],
        "sample_reviews": toilet_info["toilet_reviews"][:5],
    }


def make_place_key(place: dict) -> str:
    """物件の一意キーを生成（title + 座標の丸め）"""
    title = place.get("title", "")
    lat = float(place.get("latitude") or 0)
    lng = float(place.get("longtitude") or 0)
    # 座標を小数4桁で丸めて微小差を吸収
    return f"{title}@{lat:.4f},{lng:.4f}"


def make_result_key(result: dict) -> str:
    """処理済み物件の一意キー"""
    title = result.get("title", "")
    lat = float(result.get("lat") or 0)
    lng = float(result.get("lng") or 0)
    return f"{title}@{lat:.4f},{lng:.4f}"


def load_existing(output_path: str) -> dict:
    """既存のtoilets.jsonを読み込む。なければ空構造を返す"""
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"metadata": None, "toilets": []}


def main():
    if len(sys.argv) < 3:
        print("Usage: python process_data.py <input.json> <output.json>")
        print("")
        print("  --full       既存データを無視して全件再生成（デフォルト）")
        print("  --incremental 既存データに差分マージ")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "--full"

    # ── 新規スクレイプデータ読み込み ──
    places = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                places.append(json.loads(line))

    print(f"スクレイプデータ: {len(places)}件")

    # 新規データ内の重複除去
    seen_raw = set()
    unique_places = []
    for p in places:
        key = make_place_key(p)
        if key not in seen_raw:
            seen_raw.add(key)
            unique_places.append(p)

    print(f"重複除去後: {len(unique_places)}件")

    # ── 新規データを処理 ──
    new_results = {}
    for place in unique_places:
        processed = process_place(place)
        if processed:
            new_results[make_result_key(processed)] = processed

    print(f"新規処理済み: {len(new_results)}件")

    # ── 差分マージ or フル再生成 ──
    if mode == "--incremental":
        existing = load_existing(output_path)
        existing_toilets = existing.get("toilets", [])
        existing_meta = existing.get("metadata")

        # 既存データをキーで索引
        merged = {}
        for t in existing_toilets:
            merged[make_result_key(t)] = t

        new_count = 0
        updated_count = 0
        for key, new_item in new_results.items():
            if key in merged:
                updated_count += 1
            else:
                new_count += 1
            merged[key] = new_item  # 新データで上書き

        results = list(merged.values())
        kept_count = len(merged) - new_count - updated_count

        print(f"差分マージ:")
        print(f"  新規追加: {new_count}件")
        print(f"  更新: {updated_count}件")
        print(f"  既存維持: {kept_count}件")

        # metadata は既存を継承（なければ新規生成）
        if existing_meta:
            metadata = existing_meta
        else:
            metadata = _build_metadata(results)
    else:
        results = list(new_results.values())
        metadata = _build_metadata(results)
        print(f"フル再生成: {len(results)}件")

    # スコア順でソート
    results.sort(key=lambda x: x["toilet_score"], reverse=True)

    # 統計
    scored = [r for r in results if r["confidence"] > 0]
    public = [r for r in results if r["is_public_toilet"]]

    print(f"出力: {len(results)}件")
    print(f"  スコアあり: {len(scored)}件")
    print(f"  公共トイレ: {len(public)}件")

    metadata["total"] = len(results)
    metadata["scored"] = len(scored)
    metadata["public_toilets"] = len(public)

    output = {
        "metadata": metadata,
        "toilets": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"出力完了: {output_path}")


def _build_metadata(results: list) -> dict:
    """metadata を結果から自動生成"""
    scored = [r for r in results if r["confidence"] > 0]
    public = [r for r in results if r["is_public_toilet"]]

    # 座標の中心を自動計算
    if results:
        center_lat = sum(r["lat"] for r in results) / len(results)
        center_lng = sum(r["lng"] for r in results) / len(results)
    else:
        center_lat = 36.2231
        center_lng = 139.3772

    # エリア名を住所から推定
    area_name = ""
    if results:
        addrs = [r.get("address", "") for r in results if r.get("address")]
        if addrs:
            # 共通部分（都道府県＋市区）を抽出
            import re
            match = re.search(r"(\S+県\S+[市区町村])", addrs[0])
            if match:
                area_name = match.group(1)
    if not area_name:
        area_name = "検索エリア"

    return {
        "total": len(results),
        "scored": len(scored),
        "public_toilets": len(public),
        "center_lat": round(center_lat, 4),
        "center_lng": round(center_lng, 4),
        "zoom": 13,
        "area_name": area_name,
    }


if __name__ == "__main__":
    main()
