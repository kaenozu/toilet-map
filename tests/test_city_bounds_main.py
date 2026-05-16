"""
tests/test_city_bounds_main.py
batch/city_bounds.py の main() CLI エントリポイントテスト
"""
import pytest


class TestCityBoundsMain:
    def test_exits_with_usage_when_no_args(self, monkeypatch):
        import city_bounds
        monkeypatch.setattr("sys.argv", ["city_bounds.py"])
        monkeypatch.setattr(city_bounds, "get_city_bounds", lambda c, p="": None)
        with pytest.raises(SystemExit):
            city_bounds.main()

    def test_found_prints_json(self, monkeypatch, capsys):
        import city_bounds
        monkeypatch.setattr("sys.argv", ["city_bounds.py", "渋谷区", "東京都"])
        monkeypatch.setattr(city_bounds, "get_city_bounds",
                            lambda c, p="": {"south": 35.6, "north": 35.7, "west": 139.6, "east": 139.7})
        city_bounds.main()
        captured = capsys.readouterr()
        assert "35.6" in captured.out

    def test_not_found_exits(self, monkeypatch, capsys):
        import city_bounds
        monkeypatch.setattr("sys.argv", ["city_bounds.py", "存在しない市"])
        monkeypatch.setattr(city_bounds, "get_city_bounds", lambda c, p="": None)
        with pytest.raises(SystemExit):
            city_bounds.main()

    def test_with_only_city_arg(self, monkeypatch):
        import city_bounds
        monkeypatch.setattr("sys.argv", ["city_bounds.py", "渋谷区"])
        calls = []
        monkeypatch.setattr(city_bounds, "get_city_bounds",
                            lambda c, p="": calls.append((c, p)) or {})
        with pytest.raises(SystemExit):
            city_bounds.main()
        assert calls == [("渋谷区", "")]
