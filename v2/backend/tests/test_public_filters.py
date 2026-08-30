from app.public_api import _fee_condition, _minimum_score_condition


def test_score_threshold_excludes_unknown_by_default() -> None:
    assert _minimum_score_condition(None) == "p.toilet_score >= %s"
    assert "IS NULL" not in _minimum_score_condition(None)


def test_score_threshold_can_explicitly_include_unknown() -> None:
    condition = _minimum_score_condition(True)
    assert "p.toilet_score >= %s" in condition
    assert "p.toilet_score IS NULL" in condition


def test_free_filter_matches_only_explicit_free_values() -> None:
    condition = _fee_condition(False)
    assert "COALESCE" not in condition
    for value in ("'no'", "'false'", "'0'", "'free'"):
        assert value in condition


def test_paid_filter_matches_only_explicit_paid_values() -> None:
    condition = _fee_condition(True)
    assert "COALESCE" not in condition
    for value in ("'yes'", "'true'", "'1'", "'paid'"):
        assert value in condition
