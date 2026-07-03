#!/usr/bin/env python3
"""Patch APP_VERSION in src/__init__.py with a nightly build suffix.

Run by the GitLab CI nightly build jobs (before PyInstaller runs) so the
compiled binary reports a distinct, traceable version - e.g.
"0.2.0-nightly.a1b2c3d" - instead of the stable release version committed to
the repo. Only mutates the checked-out worktree used for that CI job; never
committed anywhere.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INIT_FILE = ROOT / "src" / "__init__.py"


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1]:
        print("usage: patch_nightly_version.py <suffix>", file=sys.stderr)

        return 1

    suffix = sys.argv[1]
    content = INIT_FILE.read_text(encoding="utf-8")
    new_content, count = re.subn(
        r'^APP_VERSION = "([^"]*)"',
        lambda m: f'APP_VERSION = "{m.group(1)}-nightly.{suffix}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )

    if count == 0:
        print(
            f"ERROR: APP_VERSION assignment not found in {INIT_FILE}",
            file=sys.stderr,
        )
        return 1

    INIT_FILE.write_text(new_content, encoding="utf-8")
    print(f"Patched {INIT_FILE}: APP_VERSION suffixed with -nightly.{suffix}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
