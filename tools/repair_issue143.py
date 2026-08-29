from pathlib import Path

path = Path("v2/backend/app/public_api.py")
text = path.read_text(encoding="utf-8")
marker = """def _boolean_attribute(conditions: list[str], key: str, value: bool | None, params: list[object]) -> None:
    if value is None:
        return
    truthy = "lower(COALESCE(p.attributes->>%s, '')) IN ('yes', 'true', 'designated', '1')"
    conditions.append(truthy if value else f"NOT ({truthy})")
    params.append(key)


"""
helpers = marker + """def _minimum_score_condition(include_unscored: bool | None) -> str:
    clause = "p.toilet_score >= %s"
    if include_unscored is True:
        return f"({clause} OR p.toilet_score IS NULL)"
    return clause


def _fee_condition(value: bool) -> str:
    explicit_values = "('yes', 'true', '1', 'paid')" if value else "('no', 'false', '0', 'free')"
    return f"lower(p.attributes->>'fee') IN {explicit_values}"


"""
if text.count(marker) != 1:
    raise SystemExit(f"helper marker count={text.count(marker)}")
text = text.replace(marker, helpers, 1)
old_default = "    include_unscored: bool = True,\n"
if text.count(old_default) != 1:
    raise SystemExit(f"include_unscored default count={text.count(old_default)}")
text = text.replace(old_default, "    include_unscored: bool | None = None,\n", 1)
old_score = """    if min_score is not None:
        clause = "p.toilet_score >= %s"
        if include_unscored:
            clause = f"({clause} OR p.toilet_score IS NULL)"
        conditions.append(clause)
        params.append(min_score)
    elif not include_unscored:
        conditions.append("p.toilet_score IS NOT NULL")
"""
new_score = """    if min_score is not None:
        conditions.append(_minimum_score_condition(include_unscored))
        params.append(min_score)
    elif include_unscored is False:
        conditions.append("p.toilet_score IS NOT NULL")
"""
if text.count(old_score) != 1:
    raise SystemExit(f"score block count={text.count(old_score)}")
text = text.replace(old_score, new_score, 1)
old_fee = """    if fee is not None:
        conditions.append(
            "lower(COALESCE(p.attributes->>'fee', 'no')) IN ('yes', 'true', '1')"
            if fee
            else "lower(COALESCE(p.attributes->>'fee', 'no')) NOT IN ('yes', 'true', '1')"
        )
"""
new_fee = """    if fee is not None:
        conditions.append(_fee_condition(fee))
"""
if text.count(old_fee) != 1:
    raise SystemExit(f"fee block count={text.count(old_fee)}")
path.write_text(text.replace(old_fee, new_fee, 1), encoding="utf-8")
Path("tools/repair_issue143.py").unlink()
Path(".github/workflows/repair-issue143-filter-semantics.yml").unlink()
