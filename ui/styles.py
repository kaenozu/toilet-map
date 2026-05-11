"""
ui/styles.py
Mobile CSS styles for Streamlit app
"""
MOBILE_CSS = """
<style>
/* ===== モバイル最適化 ===== */

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

    /* フィルタ行を折り返し表示 */
    .stHorizontalBlock {
        flex-wrap: wrap !important;
    }
    .stHorizontalBlock > div {
        min-width: 140px !important;
        flex: 1 1 45% !important;
    }

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
        transition: background 0.15s !important;
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

/* タップしやすいフィルタボタン */
.filter-btn {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid #ddd;
    font-size: 13px;
    cursor: pointer;
    margin: 2px;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
    transition: all 0.15s;
}
.filter-btn:hover { background: #f0f0f0; }
.filter-btn.active {
    background: #1a73e8;
    color: white;
    border-color: #1a73e8;
}

/* 現在地ボタン */
.locate-btn {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 10000;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: white;
    border: 2px solid #1a73e8;
    font-size: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    -webkit-tap-highlight-color: transparent;
}
.locate-btn:active { transform: scale(0.9); }

 /* トイレ詳細カード（モバイル用オーバーレイ） */
 .detail-overlay {
     display: none;
     position: fixed;
     bottom: 0; left: 0; right: 0;
     z-index: 10001;
     background: white;
     border-top-left-radius: 16px;
     border-top-right-radius: 16px;
     box-shadow: 0 -4px 20px rgba(0,0,0,0.15);
     max-height: 60vh;
     overflow-y: auto;
     padding: 16px;
     animation: slideUp 0.25s ease-out;
 }
 .detail-overlay.show { display: block; }
 @keyframes slideUp {
     from { transform: translateY(100%); }
     to { transform: translateY(0); }
 }
 .detail-overlay .close-btn {
     position: absolute;
     top: 8px; right: 12px;
     font-size: 24px;
     cursor: pointer;
     color: #999;
     border: none;
     background: none;
 }

 /* 戻るボタン（モバイル用） */
 .back-to-top {
     position: fixed;
     bottom: 20px;
     left: 20px;
     z-index: 10000;
 }
 .back-btn {
     width: 48px;
     height: 48px;
     border-radius: 50%;
     background: white;
     border: 2px solid #666;
     font-size: 20px;
     display: flex;
     align-items: center;
     justify-content: center;
     box-shadow: 0 2px 8px rgba(0,0,0,0.25);
     cursor: pointer;
     -webkit-tap-highlight-color: transparent;
 }
 .back-btn:active { transform: scale(0.9); }

/* フィルター行の垂直方向アライメント修正 */
[data-testid="stHorizontalBlock"] {
    align-items: flex-start !important;
}
[data-testid="stHorizontalBlock"] [data-testid="stColumn"] {
    display: flex !important;
    flex-direction: column !important;
    justify-content: flex-start !important;
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
</style>
"""
