from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config.migrate import ConfigAdapter

description = (
    "Rename 'desktop_override' to 'export_path' and "
    "'desktop_retention_days' to 'retention_days'; "
    "carry 'reports_archive' value to 'export_path'"
)


def upgrade(cfg: ConfigAdapter) -> None:
    cfg.rename_key("paths", "desktop_override", "export_path")
    cfg.rename_key("reports", "desktop_retention_days", "retention_days")
    cfg.carry_key("paths", "reports_archive", "paths", "export_path")
