from __future__ import annotations

import argparse
import sys

from src.config import load_config
from src.installer import install, is_installed, uninstall
from src.services.schedule import should_run_today
from .ui.gui.app import GitSentinelApp

from . import APP_NAME

# ────────────────────────────────────────────────────────────────────| Main |──


def _pause_if_windows() -> None:
    if sys.platform == "win32":
        from src.platform.windows.console import pause

    else:
        from src.platform.linux.console import pause

    pause()


def main() -> None:
    """Application entry point."""

    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description=(
            "Daily git repository audit - reports uncommitted, unpushed, "
            "stashed, or stale work."
        ),
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Run even if the script has already run today.",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "-i",
        "--install",
        action="store_true",
        help="Install (or reinstall) the binary, config, and autostart entry, "
        "then exit.",
    )
    action.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove the binary, autostart entry, and optionally config/state, "
        "then exit.",
    )

    args = parser.parse_args()

    if args.install:
        install(force=True)
        _pause_if_windows()
        sys.exit(0)

    if args.uninstall:
        uninstall()
        _pause_if_windows()
        sys.exit(0)

    if getattr(sys, "frozen", False) and not is_installed():
        print(f"{APP_NAME}: first run detected - installing...")
        print()
        install()
        _pause_if_windows()
        sys.exit(0)

    cfg = load_config()

    if not should_run_today(cfg, force=args.force):
        sys.exit(0)

    app = GitSentinelApp(cfg)
    app.mainloop()


if __name__ == "__main__":
    main()
