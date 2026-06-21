#!/usr/bin/env python3
"""Generate build/git-sentinel.ico from src/data/git-sentinel.jpg.

Uses Pillow (no native library dependencies) to produce a multi-size ICO
(16, 32, 48, 256 px). Run before PyInstaller on Windows.
"""

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent.parent
JPG = ROOT / "src" / "data" / "git-sentinel.jpg"
ICO = ROOT / "build" / "git-sentinel.ico"
SIZES = [(16, 16), (32, 32), (48, 48), (256, 256)]


def main() -> None:
    if not JPG.exists():
        print(f"ERROR: {JPG} not found", file=sys.stderr)
        sys.exit(1)

    ICO.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(JPG).convert("RGBA")
    img.save(ICO, format="ICO", sizes=SIZES)

    print(f"Generated {ICO}")


if __name__ == "__main__":
    main()
