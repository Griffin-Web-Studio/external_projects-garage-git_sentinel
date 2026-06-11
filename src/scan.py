from __future__ import annotations

import configparser
from pathlib import Path

from . import APP_NAME, APP_VERSION
from .config import get_desktop_path
from .git_ops import find_git_repos
from .models import AppProtocol

# ─────────────────────────────────────────────────────────────| Scan worker |──


def scan(app: AppProtocol, cfg: configparser.ConfigParser) -> None:
    """Full scan pipeline. Runs in a background daemon thread.

    All UI updates go through the typed AppProtocol methods on *app*.
    Gate requests (SSH approval, HTTP retry) block this thread until the
    user responds via the GUI.

    Args:
        app (AppProtocol): UI front-end; satisfies AppProtocol structurally.
        cfg (configparser.ConfigParser): Loaded application configuration.
    """
    home = Path.home()
    git_root = home / cfg.get("paths", "git_root")
    desktop = get_desktop_path(cfg)

    app.log(f"{APP_NAME}  v{APP_VERSION}")
    app.log(f"Scan root : {git_root}")
    app.log(f"Desktop   : {desktop}")
    app.log("")

    # ── Stage 1: Discovery ────────────────────────────────────────────────────

    app.set_status("Stage 1 / 3 - Discovering repositories...")
    app.log("=== Stage 1: Repository discovery ===")

    if not git_root.is_dir():
        app.log(
            f"ERROR: scan root '{git_root}' does not exist - nothing to do."
        )
        app.set_progress(100.0)
        app.finish(0, None)
        return

    repos = find_git_repos(git_root)
    total = len(repos)
    app.log(f"Found {total} repositor{'y' if total == 1 else 'ies'}.")
    app.log("")
    app.set_progress(5.0)

    # ── Stage 2: Per-repo local + remote checks (not yet implemented) ─────────

    app.set_status(
        f"Stage 2 / 3 - Scanning {total} "
        f"repositor{'y' if total == 1 else 'ies'}..."
    )
    app.log("=== Stage 2: Local and remote checks ===")
    app.log("(not yet implemented)")
    app.log("")
    app.set_progress(85.0)

    # ── Stage 3: Report (not yet implemented) ─────────────────────────────────

    app.set_status("Stage 3 / 3 - Generating report...")
    app.set_progress(90.0)
    app.log("=== Stage 3: Report ===")
    app.log("(not yet implemented)")

    app.set_progress(100.0)
    app.finish(0, None)
