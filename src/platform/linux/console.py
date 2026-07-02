from __future__ import annotations

# ─────────────────────────────────────────────────────────────────| Console |──


def pause() -> None:
    """No-op on Linux; a terminal window doesn't close on process exit."""
