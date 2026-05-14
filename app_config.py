"""
app_config.py
Shared configuration constants for toilet map app
"""
import html
import os
from urllib.parse import urlparse

DATA_PATH = "data/toilets.json.gz"
DB_PATH = "data/toilets.db"

ERROR_METADATA = {
    "total": 0, "scored": 0, "public_toilets": 0,
    "center_lat": 36.2231, "center_lng": 139.3772,
    "zoom": 13, "area_name": "エラー",
}

SCORE_RANGES = [
    (80, "#27ae60", "✨", "とてもきれい"),
    (65, "#2ecc71", "😊", "きれい"),
    (50, "#f1c40f", "😐", "普通"),
    (35, "#f39c12", "😨", "少し気になる"),
    (0, "#e74c3c", "💩", "要注意"),
]

SCORE_DISTRIBUTION_RANGES = [
    (80, 101, "✨ 80-100", "#27ae60"),
    (65, 80, "😊 65-79", "#2ecc71"),
    (50, 65, "😐 50-64", "#f1c40f"),
    (35, 50, "😨 35-49", "#f39c12"),
    (0, 35, "💩 0-34", "#e74c3c"),
]

# フィルタ設定（ui/filters.py からも使用）
FILTER_CONFIG = {
    "すべて": None,
    "公共トイレ": "__public__",
    "多目的トイレ": "__keyword__multi",
    "おむつ替え": "__keyword__diaper",
    "車椅子対応": "__keyword__wheelchair",
    "バリアフリー": "__keyword__barrier_free",
    "カフェ・飲食": "カフェ|喫茶|レストラン|食堂|ダイニング|コーヒー|パン|ケーキ",
    "コンビニ・店舗": "コンビニ|スーパー|ドラッグ|ストア|マート|商店",
    "ホテル・旅館": "ホテル|旅馨|民宿|ビジネスホテル",
    "道の駅": "道の駅",
    "SA・PA": "サービスエリア|パーキングエリア",
}

FILTER_I18N_KEYS = {
    "すべて": "filter_all",
    "公共トイレ": "filter_public",
    "多目的トイレ": "filter_multi",
    "おむつ替え": "filter_diaper",
    "車椅子対応": "filter_wheelchair",
    "バリアフリー": "filter_barrier_free",
    "カフェ・飲食": "filter_cafe",
    "コンビニ・店舗": "filter_convenience",
    "ホテル・旅館": "filter_hotel",
    "道の駅": "filter_roadstation",
    "SA・PA": "filter_sapa",
}

PUBLIC_FILTER_VALUE = "__public__"

EQUIPMENT_KEYWORDS = {
    "multi": {"多目的トイレ", "多目的", "多機能"},
    "diaper": {"おむつ", "オムツ", "おむつ替え", "おむつ交換"},
    "wheelchair": {"車椅子", "車いす", "バリアフリー"},
}

PUBLIC_MARKER_RADIUS = 14
NORMAL_MARKER_RADIUS = 10

TILE_OPTIONS = {
    "OpenStreetMap（標準）": "OpenStreetMap",
    "モノクロ（Cartodb）": "CartoDB positron",
}

THRESHOLD = 10

MAX_SAMPLE_REVIEWS = 2
REVIEW_TEXT_MAX_LENGTH = 120
MAX_KEYWORD_TAGS = 5


def esc(text):
    """HTMLエスケープ"""
    return html.escape(str(text or ""), quote=True) if text else ""


def safe_href(url):
    """安全な外部リンクだけを href に使える文字列に変換する"""
    if not url:
        return ""
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.netloc:
        return ""
    return html.escape(parsed.geturl(), quote=True)


def get_score_style(score: float) -> tuple[str, str, str]:
    """スコアに基づいて (色, 絵文字, ラベル) を返す"""
    for threshold, color, emoji, label in SCORE_RANGES:
        if score >= threshold:
            return color, emoji, label
    return SCORE_RANGES[-1][1:]


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
POPUP_FIX_PATH = os.path.join(_SCRIPT_DIR, "static", "popup_fix.js")


def _load_popup_fix_js() -> str:
    try:
        with open(POPUP_FIX_PATH, "r", encoding="utf-8") as f:
            return "<script>\n" + f.read() + "\n</script>"
    except FileNotFoundError:
        return ""


POPUP_FIX_JS = _load_popup_fix_js()
