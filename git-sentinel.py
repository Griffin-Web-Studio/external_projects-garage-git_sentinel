#!/usr/bin/env python3
"""Entry-point script for git-sentinel.

This file is intentionally thin - its only job is to make the `src` package
importable and hand off to `src/__main__.py`.

When run directly (`python git-sentinel.py` or as a PyInstaller binary) this
script is executed as `__main__`, which would create a naming conflict if we
tried to import `src/__main__` via the `__main__` alias.  Importing by the
full package path (`src.__main__`) avoids that collision entirely.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on the path so `src` is importable as a package.
# Python normally adds the *script's directory* to sys.path automatically, but
# being explicit here also covers the PyInstaller bundle, where the extracted
# directory is sys._MEIPASS rather than the script's original location.
sys.path.insert(0, str(Path(__file__).parent))

from src.__main__ import main

if __name__ == "__main__":
    main()
