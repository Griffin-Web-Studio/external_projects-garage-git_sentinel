from __future__ import annotations

import os
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────| Helpers |──


def open_file(path: Path) -> None:  # pragma: no cover - no custom logic
    """Open *path* with the default MIME application.

    Args:
        path (Path): file (like report) path
    """

    if sys.platform == "win32":
        os.startfile(path)
