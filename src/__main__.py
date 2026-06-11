from __future__ import annotations

import argparse
import configparser
import sys
import threading

from src.config import load_config
from src.installer import install, is_installed, uninstall
from src.schedule import should_run_today
from .gui.app import GitSentinelApp
from .models import AppProtocol

from . import APP_NAME

# ───────────────────────────────────────────────────────────────| Scan stub |──
# TODO: Replace this temp _run_scan with the real implementation.


def _run_scan(app: AppProtocol, _cfg: configparser.ConfigParser) -> None:
    """Placeholder worker - swap for scan.py once ported."""
    app.set_status("Scanning repositories...")
    app.set_progress(0.0)
    app.log("scan.py not yet ported - stub worker running")
    app.set_progress(100.0)
    app.finish(0, None)


# ────────────────────────────────────────────────────────────────────| Main |──


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
        sys.exit(0)

    if args.uninstall:
        uninstall()
        sys.exit(0)

    if getattr(sys, "frozen", False) and not is_installed():
        print(f"{APP_NAME}: first run detected - installing...")
        print()
        install()
        sys.exit(0)

    cfg = load_config()

    if not should_run_today(cfg, force=args.force):
        sys.exit(0)

    app = GitSentinelApp(cfg)
    worker = threading.Thread(target=_run_scan, args=(app, cfg), daemon=True)
    worker.start()
    app.mainloop()


if __name__ == "__main__":
    main()
