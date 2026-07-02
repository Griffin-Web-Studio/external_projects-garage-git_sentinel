from __future__ import annotations

import subprocess
from pathlib import Path

# ─────────────────────────────────────────────────────────────────| Helpers |──


def open_file(path: Path) -> None:  # pragma: no cover - no custom logic
    """Open *path* with the default MIME application.

    Args:
        path (Path): file (like report) path
    """

    subprocess.Popen(["xdg-open", str(path)])
