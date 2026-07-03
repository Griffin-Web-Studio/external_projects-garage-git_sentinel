from __future__ import annotations

from collections.abc import Callable

# ─────────────────────────────────────────────────────────| SSH ControlMaster |──


def resolve_control_master(use_cm: bool, log: Callable[..., None]) -> bool:
    """Resolve whether SSH ControlMaster multiplexing should be used.

    Args:
        use_cm (bool): Value of the `use_control_master` config setting.
        log (Callable[..., None]): App log callback (unused on Linux).

    Returns:
        bool: ControlMaster is fully supported on Linux, so the setting is
              honoured unchanged.
    """

    return use_cm
