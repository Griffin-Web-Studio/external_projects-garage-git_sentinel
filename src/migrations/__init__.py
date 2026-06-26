from __future__ import annotations

import shutil
import warnings
from pathlib import Path

from .. import CONF_DIR, CONF_FILE
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
    return IniAdapter(CONF_FILE)


def apply_migrations() -> OSError | None:
    """Apply all pending migrations and refresh the example config.

    After config keys are migrated, any report files sitting in the old desktop
    location are moved to the new export_path so history is preserved.

    Returns:
        OSError | None: The OSError on failure, None on success.
    """
    try:
        from ..config import get_export_path, load_config

        # Resolve the pre-migration export path (desktop) before any keys
        # change. Suppress DeprecationWarning that fires when desktop_override
        # is present.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            old_export = get_export_path(load_config())

        chain.apply(make_adapter())

        # Resolve the post-migration export path and move legacy reports.
        new_export = get_export_path(load_config())
        _move_legacy_reports(old_export, new_export)

        from ..installer import _render_example_config

        (CONF_DIR / "settings.example.ini").write_text(
            _render_example_config(), encoding="utf-8"
        )

    except OSError as exc:
        return exc

    return None


def _move_legacy_reports(src: Path, dst: Path) -> None:
    """Move report files from src to dst, skipping files that already exist.

    Args:
        src (Path): Directory that held reports before migration (old desktop).
        dst (Path): Directory that will hold reports going forward
            (export_path).
    """
    if src == dst or not src.exists():
        return

    dst.mkdir(parents=True, exist_ok=True)

    for pattern in ("*-git-status-report.log", "*-git-status-report.issues"):
        for report in src.glob(pattern):
            target = dst / report.name
            if not target.exists():
                shutil.move(str(report), target)
