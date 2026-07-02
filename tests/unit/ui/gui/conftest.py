from __future__ import annotations

import tkinter as tk
from collections.abc import Generator

import pytest


@pytest.fixture
def tk_root() -> Generator[tk.Tk]:
    """Create a headless `tk.Tk` root window and destroy it after each test.

    Yields:
        tk.Tk: A withdrawn root window with no visible UI.
    """

    root = tk.Tk()

    root.withdraw()

    yield root

    root.destroy()
