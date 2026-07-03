from __future__ import annotations

import sys

import pytest

# Skip the entire windows platform directory when not running on Windows —
# winreg is unavailable and the modules can't even be imported.
collect_ignore_glob: list[str] = []

if sys.platform != "win32":
    pytest.skip(
        "windows platform tests require win32",
        allow_module_level=True,
    )
