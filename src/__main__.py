from __future__ import annotations

import argparse
import sys

from . import APP_NAME

# ────────────────────────────────────────────────────────────────────| Main |──


def main() -> None:
    """Application Entrypoint"""
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
        # TODO: Add Install Logic
        print("Install Software")
        sys.exit(0)

    if args.uninstall:
        # TODO: Add Uninstall Logic
        print("Uninstall Software")
        sys.exit(0)

    # TODO: Detect First Run
    print("Detect first run")

    # TODO: Load Configs
    print("Load Configs")

    # TODO: Lock Test - early exit
    print("Check if software already run today, early exit if so")

    # TODO: App init/GUI loop
    print("Start Check/GUI loop")


if __name__ == "__main__":
    main()
