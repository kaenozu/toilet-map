"""
tests/test_docker_exec.py
docker_exec.py のユニットテスト（Docker 非依存の純粋関数のみ）
"""
from docker_exec import to_docker_path


class TestToDockerPath:
    def test_windows_drive_path(self):
        assert to_docker_path("C:\\Users\\test\\file.txt") == "/c/Users/test/file.txt"

    def test_windows_drive_path_with_forward_slashes(self):
        assert to_docker_path("C:/Users/test/file.txt") == "/c/Users/test/file.txt"

    def test_lowercase_drive(self):
        assert to_docker_path("d:\\data\\out.json") == "/d/data/out.json"

    def test_unix_path_stays_unchanged(self):
        result = to_docker_path("/home/user/file.txt")
        assert result == "/home/user/file.txt"

    def test_relative_path(self):
        result = to_docker_path("relative/path/file.txt")
        assert result == "relative/path/file.txt"

    def test_relative_path_with_backslashes(self):
        result = to_docker_path("relative\\path\\file.txt")
        assert result == "relative/path/file.txt"

    def test_empty_string_becomes_dot(self):
        assert to_docker_path("") == "."
