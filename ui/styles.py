"""CSS constants injected directly by Streamlit."""

MOBILE_CSS = """<style>
section[data-testid="stSidebar"]:not([aria-expanded="false"]) { min-width:280px!important; max-width:360px!important; }
section[data-testid="stSidebar"] > div:first-child { padding-left:0!important; }
section[data-testid="stSidebar"][aria-expanded="false"] { width:0!important; min-width:0!important; max-width:0!important; overflow:hidden!important; flex-shrink:0!important; padding:0!important; margin:0!important; }
section[data-testid="stSidebar"][aria-expanded="false"] + div .block-container { max-width:100%!important; }
@media (max-width:768px) {
  .block-container { padding:1rem .5rem 0!important; max-width:100%!important; }
  h1 { font-size:1.3rem!important; margin-bottom:.3rem!important; }
  .stCaption { font-size:.75rem!important; }
  .stFolium > div { margin-top:0!important; }
  .stSelectbox label,.stTextInput label { font-size:16px!important; }
  .score-legend-mobile { font-size:.7rem!important; }
  .score-legend-mobile .bar { width:120px!important; height:10px!important; }
  .streamlit-expanderHeader { font-size:14px!important; padding:4px 8px!important; }
  .stButton > button,.stDownloadButton > button { min-height:44px!important; }
  .toilet-card { -webkit-tap-highlight-color:transparent!important; transition:background .15s!important; }
  .toilet-card:active { background:#f5f5f5!important; }
  .stRadio > label { font-size:13px!important; }
  .stRadio > div { gap:4px!important; }
  .leaflet-popup-content-wrapper { max-width:calc(100vw - 40px)!important; min-width:0!important; }
  .leaflet-popup-content { min-width:0!important; max-width:calc(100vw - 60px)!important; font-size:13px!important; }
}
.stButton > button { color:#fff!important; background-color:#1a73e8!important; border-color:#1a73e8!important; font-weight:600!important; }
.stButton > button:disabled { background-color:#999!important; color:#fff!important; border-color:#999!important; }
.stButton > button[kind="secondary"] { background-color:#555!important; color:#fff!important; border-color:#555!important; }
@media (prefers-color-scheme:dark) {
  .toilet-card { background:#1e1e1e!important; color:#e0e0e0!important; border-color:#333!important; }
  .toilet-card .toilet-card-title,.toilet-card .toilet-card-subtitle,.toilet-card .toilet-card-arrow,.toilet-card .toilet-card-meta { color:inherit!important; }
}
</style>"""

DARK_MODE_CSS = """<style>
.toilet-card { background:#1e1e1e!important; color:#e0e0e0!important; border-color:#333!important; }
.toilet-card .toilet-card-title,
.toilet-card .toilet-card-subtitle,
.toilet-card .toilet-card-meta,
.toilet-card .toilet-card-arrow { color:inherit!important; }
</style>"""
