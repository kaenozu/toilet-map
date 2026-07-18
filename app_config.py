"""Shared application configuration."""

from __future__ import annotations

import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "toilets.json.gz")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "toilets.db")

ERROR_METADATA = {
    "total": 0,
    "scored": 0,
    "public_toilets": 0,
    "center_lat": 36.2231,
    "center_lng": 139.3772,
    "zoom": 13,
    "area_name": "エラー",
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

FILTER_CONFIG = {
    "すべて": None,
    "公共トイレ": "__public__",
    "多目的トイレ": "__keyword__multi",
    "おむつ替え": "__keyword__diaper",
    "車椅子対応": "__keyword__wheelchair",
    "バリアフリー": "__keyword__barrier_free",
    "カフェ・飲食": "カフェ|喫茶|レストラン|食堂|ダイニング|コーヒー|パン|ケーキ",
    "コンビニ・店舗": "コンビニ|スーパー|ドラッグ|ストア|マート|商店",
    "ホテル・旅館": "ホテル|旅館|民宿|ビジネスホテル",
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
    "ナビゲーション（CartoDB）": "CartoDB voyager",
    "地形図（OpenTopoMap）": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
}
TILE_ATTRIBUTIONS = {
    "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png": (
        'Map data: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, '
        '<a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)'
    ),
}
THRESHOLD = 10
MAX_SAMPLE_REVIEWS = 2
REVIEW_TEXT_MAX_LENGTH = 120
MAX_KEYWORD_TAGS = 5
POTENTIAL_CATEGORIES = [
    "公園", "駅", "道の駅", "サービスエリア", "パーキングエリア",
    "カフェ", "喫茶", "レストラン", "食堂", "ダイニング", "コーヒー", "パン", "ケーキ",
    "コンビニ", "スーパー", "ドラッグ", "ストア", "マート", "商店",
    "ホテル", "旅館", "民宿", "ビジネスホテル", "役場", "市役所", "図書館",
]

POPUP_FIX_PATH = os.path.join(PROJECT_ROOT, "static", "popup_fix.js")


def _load_popup_fix_js() -> str:
    try:
        with open(POPUP_FIX_PATH, encoding="utf-8") as file:
            return "<script>\n" + file.read() + "\n</script>"
    except FileNotFoundError:
        return ""


POPUP_FIX_JS = _load_popup_fix_js()
PREFECTURE_CENTERS = {
    "北海道": (43.0642, 141.3469), "青森県": (40.8226, 140.6379), "岩手県": (39.7186, 141.1364),
    "宮城県": (38.2688, 140.8756), "秋田県": (39.7186, 140.1034), "山形県": (38.2404, 140.3636),
    "福島県": (37.7500, 140.4678), "茨城県": (36.3414, 140.4468), "栃木県": (36.5657, 139.8836),
    "群馬県": (36.3907, 139.0604), "埼玉県": (35.8574, 139.6489), "千葉県": (35.6050, 140.1233),
    "東京都": (35.6762, 139.6503), "神奈川県": (35.4475, 139.6423), "新潟県": (37.9162, 139.0363),
    "富山県": (36.6959, 137.2117), "石川県": (36.5947, 136.6256), "福井県": (36.0652, 136.2216),
    "山梨県": (35.6642, 138.5684), "長野県": (36.6513, 138.1810), "岐阜県": (35.6642, 136.9064),
    "静岡県": (34.9769, 138.3831), "愛知県": (35.1802, 136.9066), "三重県": (34.7303, 136.5086),
    "滋賀県": (35.0046, 135.8687), "京都府": (35.0212, 135.7556), "大阪府": (34.6863, 135.5197),
    "兵庫県": (34.6913, 135.1830), "奈良県": (34.6853, 135.8327), "和歌山県": (34.2260, 135.1675),
    "鳥取県": (35.5037, 134.2377), "島根県": (35.4723, 133.0504), "岡山県": (34.6618, 133.9347),
    "広島県": (34.3966, 132.4596), "山口県": (34.1861, 131.4705), "徳島県": (34.0658, 134.5593),
    "香川県": (34.3401, 134.0434), "愛媛県": (33.8417, 132.7653), "高知県": (33.5597, 133.5311),
    "福岡県": (33.6067, 130.4183), "佐賀県": (33.2494, 130.2998), "長崎県": (32.7448, 129.8734),
    "熊本県": (32.7898, 130.7416), "大分県": (33.2382, 131.6126), "宮崎県": (31.9111, 131.4238),
    "鹿児島県": (31.5601, 130.5580), "沖縄県": (26.2124, 127.6809),
}
