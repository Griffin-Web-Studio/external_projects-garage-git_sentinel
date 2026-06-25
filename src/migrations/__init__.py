from __future__ import annotations

from .. import CONFIG_DIR, CONFIG_FILE
from ..configmigrate import MigrationChain
from ..configmigrate.ini import IniAdapter

# ──────────────────────────────────────────────────────────────────| Chain |──

# Migration files live alongside this __init__.py.
# Files without a [meta] version key are treated as version 0 (the 0.1.0 stable
# release config layout).
chain: MigrationChain = MigrationChain(
    package_path=__path__,
    package_name=__name__,
    initial_version=0,
)


def make_adapter() -> IniAdapter:
    return IniAdapter(CONFIG_FILE)


def apply_migrations() -> OSError | None:
    """Apply all pending migrations and refresh the example config.

    Returns the OSError on failure, None on success.
    """
    try:
        chain.apply(make_adapter())
        from ..installer import _render_example_config

        (CONFIG_DIR / "settings.example.ini").write_text(
            _render_example_config(), encoding="utf-8"
        )

    except OSError as exc:
        return exc

    return None
