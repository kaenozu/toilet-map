"""
tests/test_gap_summary.py
batch/gap_summary.py のユニットテスト
"""
from gap_summary import print_gap_summary


def test_print_gap_summary_with_data(monkeypatch, capsys):
    monkeypatch.setattr("gap_summary.load_json", lambda _: {
        "toilets": [
            {"toilet_score": 80, "address": "東京都渋谷区", "prefecture": "東京都"},
            {"toilet_score": 60, "address": "大阪府大阪市", "prefecture": "大阪府"},
        ]
    })
    print_gap_summary()
    captured = capsys.readouterr()
    assert "Total toilets: 2" in captured.out
    assert "Scored: 2" in captured.out


def test_print_gap_summary_with_gaps(monkeypatch, capsys):
    monkeypatch.setattr("gap_summary.load_json", lambda _: {
        "toilets": [
            {"toilet_score": 80, "address": "東京都渋谷区", "prefecture": "東京都"},
        ]
    })
    print_gap_summary()
    captured = capsys.readouterr()
    assert "Top underserved" in captured.out or "Underserved" in captured.out


def test_print_gap_summary_empty(monkeypatch, capsys):
    monkeypatch.setattr("gap_summary.load_json", lambda _: {"toilets": []})
    print_gap_summary()
    captured = capsys.readouterr()
    assert "Total toilets: 0" in captured.out


def test_print_gap_summary_non_dict_data(monkeypatch, capsys):
    monkeypatch.setattr("gap_summary.load_json", lambda _: [])
    print_gap_summary()
    captured = capsys.readouterr()
    assert "Total toilets: 0" in captured.out
