"""
batch/generate_queries.py
日本全国的クエリファイル自動生成
prefecture_cities.json からデータを読み込む
"""
import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_DIR = os.path.join(SCRIPT_DIR, "queries.d")
DATA_FILE = os.path.join(SCRIPT_DIR, "prefecture_cities.json")
BATCH_SIZE = 12

QUERY_TEMPLATES = [
    "公共トイレ in {city}",
    "トイレ in {city}",
    "道の駅 in {city}",
    "カフェ in {city}",
    "コンビニ in {city}",
    "レストラン in {city}",
    "スーパー in {city}",
    "駅 トイレ in {city}",
    "公園 トイレ in {city}",
    "ホテル in {city}",
    "ショッピングモール in {city}",
    "ドラッグストア in {city}",
    "病院 in {city}",
    "図書館 in {city}",
    "温泉 in {city}",
    "レストラン トイレ in {city}",
    "デパート in {city}",
    "百円ショップ in {city}",
    "ファミレス in {city}",
    "書店 in {city}",
    "公共施設 トイレ in {city}",
    "学校 トイレ in {city}",
]


def load_prefectures() -> dict:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_queries(cities: list[str]) -> list[str]:
    return [tmpl.format(city=city) for city in cities for tmpl in QUERY_TEMPLATES]


def write_batches(
    queries: list[str],
    output_dir: str,
    city: str = "",
    prefecture: str = "",
    start_index: int = 1,
) -> int:
    os.makedirs(output_dir, exist_ok=True)
    file_count = 0
    for i in range(0, len(queries), BATCH_SIZE):
        file_count += 1
        batch = queries[i : i + BATCH_SIZE]
        filepath = os.path.join(output_dir, f"batch_{start_index + file_count - 1:03d}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            if city:
                f.write(f"# city: {city}\n")
            if prefecture:
                f.write(f"# prefecture: {prefecture}\n")
            f.write("\n".join(batch) + "\n")
    return file_count


def main():
    os.makedirs(QUERIES_DIR, exist_ok=True)
    prefectures = load_prefectures()

    total_queries = 0
    total_files = 0

    print(f"Generating queries for {len(prefectures)} prefectures...\n")

    for pref, cities in sorted(prefectures.items()):
        pref_dir = os.path.join(QUERIES_DIR, pref)
        file_count = 0
        pref_query_count = 0
        next_batch_index = 1
        for city in cities:
            city_queries = build_queries([city])
            n_files = write_batches(
                city_queries,
                pref_dir,
                city=city,
                prefecture=pref,
                start_index=next_batch_index,
            )
            file_count += n_files
            next_batch_index += n_files
            pref_query_count += len(city_queries)

        total_queries += pref_query_count
        total_files += file_count
        est_hours = pref_query_count * 5 / 3600
        print(f"  {pref:6s}: {len(cities):3d} cities, "
              f"{pref_query_count:5d} queries, "
              f"{file_count:3d} files, ~{est_hours:.0f}h")

    print(f"\nTotal: {total_queries} queries in {total_files} files")
    print(f"Est. time: {total_queries * 5 / 3600 / 24:.0f} days (continuous)")
    print(f"\nOutput: {QUERIES_DIR}/")
    print("\nUsage:")
    print("  set QUERIES=queries.d/埼玉県/batch_001.txt")
    print("  scrape.bat")
    print("  python scrape_runner.py --city 羽生市 --prefecture 埼玉県")


if __name__ == "__main__":
    main()
