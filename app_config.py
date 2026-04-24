"""
app_config.py
Shared configuration constants for toilet map app
"""
import html

DATA_PATH = "data/toilets.json"

SCORE_RANGES = [
    (80, "#27ae60", "✨", "とてもきれい"),
    (65, "#2ecc71", "😊", "きれい"),
    (50, "#f1c40f", "😐", "普通"),
    (35, "#f39c12", "😨", "少し気になる"),
    (0, "#e74c3c", "💩", "要注意"),
]

FILTER_CONFIG = {
    "すべて": None,
    "公共トイレ": "__public__",
    "カフェ・飲食": "カフェ|喫茶|レストラン|食堂|ダイニング|コーヒー|パン|ケーキ",
    "コンビニ・店舗": "コンビニ|スーパー|ドラッグ|ストア|マート|商店",
}

PUBLIC_MARKER_RADIUS = 14
NORMAL_MARKER_RADIUS = 10
MAX_SAMPLE_REVIEWS = 5
MOBILE_BREAKPOINT = 768
MAP_HEIGHT = 500


def esc(text):
    """HTMLエスケープ"""
    return html.escape(str(text or ""), quote=True) if text else ""


def get_score_style(score: float) -> tuple[str, str, str]:
    """スコアに基づいて (色, 絵文字, ラベル) を返す"""
    for threshold, color, emoji, label in SCORE_RANGES:
        if score >= threshold:
            return color, emoji, label
    return SCORE_RANGES[-1][1:]


PREFECTURE_CENTERS = {
    "東京都": (35.6762, 139.6503),
    "神奈川県": (35.4475, 139.6423),
    "埼玉県": (35.8574, 139.6489),
    "千葉県": (35.6050, 140.1233),
    "茨城県": (36.3414, 140.4468),
    "栃木県": (36.5657, 139.8836),
    "群馬県": (36.3907, 139.0604),
}