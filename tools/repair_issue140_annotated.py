from pathlib import Path

path = Path("v2/backend/app/public_api.py")
text = path.read_text(encoding="utf-8")
text = text.replace("from typing import Any\n", "from typing import Annotated, Any\n", 1)
replacements = {
    "    q: str | None = Query(None, max_length=200),\n": "    q: Annotated[str | None, Query(max_length=200)] = None,\n",
    "    min_score: float | None = Query(None, ge=0, le=100),\n": "    min_score: Annotated[float | None, Query(ge=0, le=100)] = None,\n",
    "    min_trust: float | None = Query(None, ge=0, le=100),\n": "    min_trust: Annotated[float | None, Query(ge=0, le=100)] = None,\n",
    "    north: float | None = Query(None, ge=-90, le=90),\n": "    north: Annotated[float | None, Query(ge=-90, le=90)] = None,\n",
    "    south: float | None = Query(None, ge=-90, le=90),\n": "    south: Annotated[float | None, Query(ge=-90, le=90)] = None,\n",
    "    east: float | None = Query(None, ge=-180, le=180),\n": "    east: Annotated[float | None, Query(ge=-180, le=180)] = None,\n",
    "    west: float | None = Query(None, ge=-180, le=180),\n": "    west: Annotated[float | None, Query(ge=-180, le=180)] = None,\n",
    "    latitude: float | None = Query(None, ge=-90, le=90),\n": "    latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,\n",
    "    longitude: float | None = Query(None, ge=-180, le=180),\n": "    longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,\n",
    "    radius_m: int = Query(5000, ge=100, le=50000),\n": "    radius_m: Annotated[int, Query(ge=100, le=50000)] = 5000,\n",
    "    limit: int = Query(500, ge=1, le=2000),\n": "    limit: Annotated[int, Query(ge=1, le=2000)] = 500,\n",
    "    offset: int = Query(0, ge=0),\n": "    offset: Annotated[int, Query(ge=0)] = 0,\n",
}
for old, new in replacements.items():
    if text.count(old) != 1:
        raise SystemExit(f"expected one match for {old!r}, got {text.count(old)}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
Path("tools/repair_issue140_annotated.py").unlink()
Path(".github/workflows/repair-issue140-annotated.yml").unlink()
