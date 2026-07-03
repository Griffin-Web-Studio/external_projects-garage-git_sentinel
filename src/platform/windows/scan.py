from __future__ import annotations

from collections.abc import Callable

# ───────────────────────────────────────────────────────| SSH ControlMaster |──


def resolve_control_master(use_cm: bool, log: Callable[..., None]) -> bool:
    """Resolve whether SSH ControlMaster multiplexing should be used.

    Args:
        use_cm (bool): Value of the `use_control_master` config setting.
        log (Callable[..., None]): App log callback used to warn the user.

    Returns:
        bool: Always False - ControlMaster is not supported on Windows.
    """

    if use_cm:
        log(
            "NOTE: SSH ControlMaster is not supported on Windows"
            " — using per-connection SSH."
        )

    return False
