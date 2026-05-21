"""
ui/styles.py
Mobile CSS styles for Streamlit app
CSS inlined directly; no file I/O at import time.
"""

import streamlit as st

from ui.analytics import inject_analytics


def inject_theme_styles() -> None:
    """Font/theme customization CSS based on session state (B8)."""
    font_size_map = {"small": "14px", "medium": "16px", "large": "18px"}
    size = st.session_state.get("font_size", "medium")
    family = st.session_state.get("font_family", "sans-serif")
    px = font_size_map.get(size, "16px")
    st.markdown(
        f"<style>"
        f":root {{ font-size: {px}; --font-family: {family}; }}"
        f"body, .stApp {{ font-family: {family} !important; }}"
        f"</style>",
        unsafe_allow_html=True,
    )


MOBILE_CSS = """<style>
/* ===== モバイル / サイドバー最適化 ===== */

/* サイドバー幅（デスクトップ・展開時） */
section[data-testid="stSidebar"]:not([aria-expanded="false"]) {
    min-width: 280px !important;
    max-width: 360px !important;
}
section[data-testid="stSidebar"] > div:first-child {
    padding-left: 0 !important;
}

/* サイドバー格納時：サイドバーをゼロ幅に */
section[data-testid="stSidebar"][aria-expanded="false"] {
    width: 0 !important;
    min-width: 0 !important;
    max-width: 0 !important;
    overflow: hidden !important;
    flex-shrink: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}
/* サイドバー格納時：メインコンテンツを全幅に */
section[data-testid="stSidebar"][aria-expanded="false"] + div .block-container {
    max-width: 100% !important;
}

/* Streamlitの余分な余白を削減 */
@media (max-width: 768px) {
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0 !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100% !important;
    }

    /* タイトル縮小 */
    h1 { font-size: 1.3rem !important; margin-bottom: 0.3rem !important; }

    /* キャプション縮小 */
    .stCaption { font-size: 0.75rem !important; }

    /* 地図コンテナの上下マージン削減 */
    .stFolium > div { margin-top: 0 !important; }

    /* selectboxとtext_inputのフォントサイズ調整（iOSズーム防止） */
    .stSelectbox label, .stTextInput label {
        font-size: 16px !important;
    }

    /* 凡例を小さく */
    .score-legend-mobile { font-size: 0.7rem !important; }
    .score-legend-mobile .bar { width: 120px !important; height: 10px !important; }

    /* 統計expander コンパクト化 */
    .streamlit-expanderHeader {
        font-size: 14px !important;
        padding: 4px 8px !important;
    }

    /* ページネーションボタン タップ領域拡大 */
    .stButton > button {
        min-height: 44px !important;
        font-size: 14px !important;
    }

    /* トイレカードのタッチ操作改善 */
    .toilet-card {
        -webkit-tap-highlight-color: transparent !important;
        transition: opacity 0.3s ease, transform 0.3s ease, background 0.15s !important;
    }
    .toilet-card.entering {
        opacity: 0;
        transform: translateY(10px);
    }
    .toilet-card:active {
        background: #f5f5f5 !important;
    }

    /* ラジオボタンをコンパクトに */
    .stRadio > label {
        font-size: 13px !important;
    }
    .stRadio > div {
        gap: 4px !important;
    }

    /* ダウンロードボタン */
    .stDownloadButton > button {
        min-height: 44px !important;
    }
}

/* スマホではポップアップ幅を画面幅に合わせる */
@media (max-width: 768px) {
    .leaflet-popup-content-wrapper {
        max-width: calc(100vw - 40px) !important;
        min-width: 0 !important;
    }
    .leaflet-popup-content {
        min-width: 0 !important;
        max-width: calc(100vw - 60px) !important;
        font-size: 13px !important;
    }
}

/* ===== 文字コントラスト改善（テーマ問わず） ===== */
.stButton > button {
    color: #ffffff !important;
    background-color: #1a73e8 !important;
    border-color: #1a73e8 !important;
    font-weight: 600 !important;
}
.stButton > button:disabled {
    background-color: #999 !important;
    color: #fff !important;
    border-color: #999 !important;
}
.stButton > button[kind="secondary"] {
    background-color: #555 !important;
    color: #ffffff !important;
    border-color: #555 !important;
}

/* ===== ダークモード対応 ===== */
@media (prefers-color-scheme: dark) {
    .toilet-card {
        background: #1e1e1e !important;
        color: #e0e0e0 !important;
        border-color: #333 !important;
    }
    .toilet-card .toilet-card-title,
    .toilet-card .toilet-card-subtitle,
    .toilet-card .toilet-card-arrow,
    .toilet-card .toilet-card-meta {
        color: inherit !important;
    }
}
</style>"""


def inject_pwa_assets() -> None:
    """Inject PWA assets, manifest, service worker, CSS, offline support, and install prompts."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] {
            display: none !important;
        }
        </style>
        <link rel="manifest" href="/static/manifest.json">
        <meta name="theme-color" content="#1a73e8">
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <script>
        document.addEventListener('keydown', function(e) {
          if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
          if (e.key === 'g' && !e.ctrlKey && !e.metaKey) {
            var gps = document.querySelector('input[aria-label*="GPS" i]');
            if (gps) { gps.click(); e.preventDefault(); }
          }
          if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
            var search = document.querySelector('input[aria-label*="検索" i]');
            if (search) { search.focus(); e.preventDefault(); }
          }
        });
        </script>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)

    inject_analytics()

    # PWA: Service Worker registration
    st.markdown(
        """<script>
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/sw.js');
}
</script>""",
        unsafe_allow_html=True,
    )

    # PWA: Install prompt handler
    st.markdown('<script src="/static/install.js"></script>', unsafe_allow_html=True)
    # PWA: Offline IndexedDB cache
    st.markdown('<script src="/static/offline.js"></script>', unsafe_allow_html=True)

    # PWA install button (shown via JS when beforeinstallprompt fires)
    st.markdown(
        """<div id="pwa-install-container" style="display:none;position:fixed;bottom:16px;right:16px;z-index:9999;">
<button onclick="window.installPwa()" style="padding:10px 20px;background:#1a73e8;color:#fff;border:none;border-radius:8px;font-size:14px;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.2);">
📲 インストール
</button>
</div>
<script>
(function(){
  var checkInstall = function(){
    var c = document.getElementById('pwa-install-container');
    if(c && document.body.dataset.installAvailable === 'true'){
      c.style.display = 'block';
    }
  };
  checkInstall();
  setInterval(checkInstall, 2000);
})();
</script>""",
        unsafe_allow_html=True,
    )
