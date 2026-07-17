import json, sqlite3
from toilet_map_v2.migration import migrate

def count(db_path, table):
    db=sqlite3.connect(db_path)
    try: return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally: db.close()

def test_idempotent_and_distinct_same_coordinates(tmp_path):
    src=tmp_path/"legacy.json"; db=tmp_path/"v2.db"
    src.write_text(json.dumps([
        {"place_id":"a","title":"A","latitude":35,"longitude":139,"toilet_score":88,"toilet_reviews_count":3,"reviews":[{"text":"clean"}]},
        {"place_id":"b","title":"B","latitude":35,"longitude":139,"toilet_score":70,"toilet_reviews_count":1,"reviews":[{"text":"ok"}]}
    ]),encoding="utf-8")
    assert migrate(src,db).reviews_inserted==2
    assert [count(db,x) for x in ("places","toilets","reviews")]==[2,2,2]
    second=migrate(src,db)
    assert [count(db,x) for x in ("places","toilets","reviews")]==[2,2,2]
    assert second.duplicate_reviews==2

def test_unrated_null_and_rejections(tmp_path):
    src=tmp_path/"legacy.json"; db=tmp_path/"v2.db"; report=tmp_path/"report.json"
    src.write_text(json.dumps([
        {"title":"park","lat":36.1,"lng":139.4,"score":50,"review_count":0},
        {"title":"bad","lat":"NaN","lng":139.4},{"lat":36.1,"lng":139.4}
    ]),encoding="utf-8")
    result=migrate(src,db,report)
    conn=sqlite3.connect(db); score,status=conn.execute("SELECT score,score_status FROM toilets").fetchone(); conn.close()
    assert score is None and status=="unrated"
    assert result.rejection_reasons=={"invalid_coordinates":1,"missing_title":1}
    assert json.loads(report.read_text())["rejected_count"]==2
