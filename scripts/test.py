#!/usr/bin/env python3
"""Run mypy strict + pytest with the platform-appropriate coverage config.

Mirrors the Linux/Windows `test` jobs in .gitlab-ci.yml as a single
cross-platform command: `uv run scripts/test.py` (any extra arguments are
forwarded to pytest).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

if sys.platform == "win32":
    IGNORE = ["tests/platform/linux", "tests/unit/ui/gui"]
    COVERAGERC = ".coveragerc.windows"

else:
    IGNORE = ["tests/platform/windows"]
    COVERAGERC = ".coveragerc.linux"


def _needs_xvfb() -> bool:
    """True on a headless Linux CI runner with xvfb-run available.

    Local dev machines have a real X/Wayland display, so this only kicks in
    when DISPLAY is unset - e.g. the GitLab CI runner.
    """

    return (
        sys.platform not in ("win32", "darwin")
        and not os.environ.get("DISPLAY")
        and shutil.which("xvfb-run") is not None
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--no-mypy", action="store_true", help="Skip the mypy strict check."
    )
    parser.add_argument(
        "--no-cov", action="store_true", help="Run pytest without coverage."
    )
    args, pytest_args = parser.parse_known_args()

    if not args.no_mypy:
        result = subprocess.call(
            ["mypy", "--strict", "src/", "git-sentinel"], cwd=ROOT
        )

        if result != 0:
            return result

    cmd = ["pytest", "-q", *[f"--ignore={p}" for p in IGNORE]]

    if not args.no_cov:
        cmd += [
            "--cov=src",
            f"--cov-config={COVERAGERC}",
            "--cov-report=term-missing",
        ]

    cmd += pytest_args

    if _needs_xvfb():
        cmd = ["xvfb-run", "--auto-servernum", *cmd]

    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
