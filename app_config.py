"""
app_config.py
Shared configuration constants for toilet map app
"""
import html

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

FILTER_CONFIG = {
    "すべて": None,
    "公共トイレ": "__public__",
    "カフェ・飲食": "カフェ|喫茶|レストラン|食堂|ダイニング|コーヒー|パン|ケーキ",
    "コンビニ・店舗": "コンビニ|スーパー|ドラッグ|ストア|マート|商店",
    "ホテル・旅館": "ホテル|旅馆|民宿|ビジネスホテル",
    "道の駅": "道の駅",
    "SA・PA": "サービスエリア|パーキングエリア",
}

PUBLIC_MARKER_RADIUS = 14
NORMAL_MARKER_RADIUS = 10

TILE_OPTIONS = {
    "OpenStreetMap（標準）": "OpenStreetMap",
    "モノクロ（Cartodb）": "CartoDB positron",
}


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
    "北海道": (43.0642, 141.3469),
    "青森県": (40.8226, 140.6379),
    "岩手県": (39.7186, 141.1364),
    "宮城県": (38.2688, 140.8756),
    "秋田県": (39.7186, 140.1034),
    "山形県": (38.2404, 140.3636),
    "福島県": (37.7500, 140.4678),
    "茨城県": (36.3414, 140.4468),
    "栃木県": (36.5657, 139.8836),
    "群馬県": (36.3907, 139.0604),
    "埼玉県": (35.8574, 139.6489),
    "千葉県": (35.6050, 140.1233),
    "東京都": (35.6762, 139.6503),
    "神奈川県": (35.4475, 139.6423),
    "新潟県": (37.9162, 139.0363),
    "富山県": (36.6959, 137.2117),
    "石川県": (36.5947, 136.6256),
    "福井県": (36.0652, 136.2216),
    "山梨県": (35.6642, 138.5684),
    "長野県": (36.6513, 138.1810),
    "岐阜県": (35.6642, 136.9064),
    "静岡県": (34.9769, 138.3831),
    "愛知県": (35.1802, 136.9066),
    "三重県": (34.7303, 136.5086),
    "滋賀県": (35.0046, 135.8687),
    "京都府": (35.0212, 135.7556),
    "大阪府": (34.6863, 135.5197),
    "兵庫県": (34.6913, 135.1830),
    "奈良県": (34.6853, 135.8327),
    "和歌山県": (34.2260, 135.1675),
    "鳥取県": (35.5037, 134.2377),
    "島根県": (35.4723, 133.0504),
    "岡山県": (34.6618, 133.9347),
    "広島県": (34.3966, 132.4596),
    "山口県": (34.1861, 131.4705),
    "徳島県": (34.0658, 134.5593),
    "香川県": (34.3401, 134.0434),
    "愛媛県": (33.8417, 132.7653),
    "高知県": (33.5597, 133.5311),
    "福岡県": (33.6067, 130.4183),
    "佐賀県": (33.2494, 130.2998),
    "長崎県": (32.7448, 129.8734),
    "熊本県": (32.7898, 130.7416),
    "大分県": (33.2382, 131.6126),
    "宮崎県": (31.9111, 131.4238),
    "鹿児島県": (31.5601, 130.5580),
    "沖縄県": (26.2124, 127.6809),
}

POPUP_FIX_JS = """
<script>
(function(){
  function fixPopups(){
    var mapEl = document.getElementById('map');
    if(!mapEl) { setTimeout(fixPopups, 500); return; }
    var lmap = null;
    for(var k in window){
      try{ if(window[k] && window[k].getContainer && window[k].getContainer()===mapEl){ lmap=window[k]; break; } }catch(e){}
    }
    if(!lmap){ setTimeout(fixPopups, 500); return; }

    lmap.on('popupopen', function(e){
      setTimeout(function(){
        var popup = e.popup._container;
        if(!popup) return;
        var mapRect = lmap.getContainer().getBoundingClientRect();
        var popRect = popup.getBoundingClientRect();
        if(popRect.left < mapRect.left + 8){
          popup.style.left = (mapRect.left + 8 - popRect.left + parseFloat(popup.style.left||0)) + 'px';
        }
        if(popRect.right > mapRect.right - 8){
          popup.style.left = (parseFloat(popup.style.left||0) - (popRect.right - mapRect.right + 8)) + 'px';
        }
        if(popRect.top < mapRect.top + 8){
          var dy = mapRect.top + 8 - popRect.top;
          lmap.panBy([0, -dy], {animate: true, duration: 0.2});
        }
        if(popRect.bottom > mapRect.bottom - 8){
          var dy = popRect.bottom - mapRect.bottom + 8;
          lmap.panBy([0, dy], {animate: true, duration: 0.2});
        }
      }, 50);
    });
  }
  fixPopups();
})();
</script>
"""