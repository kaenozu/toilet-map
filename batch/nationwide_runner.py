"""
batch/nationwide_runner.py
全国47都道府県の主要都市を自動スクレイピングする
"""
import os
import sys
import subprocess
from utils import logger

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
]

def run_prefecture(pref: str):
    logger.info(f"=== Starting Prefecture: {pref} ===")
    query_file = os.path.join("queries.d", pref, "batch_001.txt")
    if not os.path.exists(query_file):
        logger.warning(f"Query file not found: {query_file}")
        return

    # scrape_runner を呼び出し
    # 環境変数 QUERIES を設定して、その都道府県のクエリファイルを読み込ませる
    env = os.environ.copy()
    env["QUERIES"] = query_file
    env["PROGRESS_FILE"] = f".progress_{pref}"
    
    cmd = [sys.executable, "scrape_runner.py", "--prefecture", pref]
    subprocess.run(cmd, env=env)

def main():
    for pref in PREFECTURES:
        run_prefecture(pref)

if __name__ == "__main__":
    main()
