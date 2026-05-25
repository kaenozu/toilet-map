"""
scripts/update_screenshot_baselines.py
Regenerate Playwright screenshot baselines.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/e2e/test_screenshots.py",
        "-q",
        "--update-screenshots",
    ]
    result = subprocess.run(command, cwd=repo_root)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
