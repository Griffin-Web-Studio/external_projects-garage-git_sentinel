from __future__ import annotations

import importlib
import pkgutil
import re
from dataclasses import dataclass, field
from typing import Callable, Protocol

# ──────────────────────────────────────────────────────────────| Public API |──

# Matches migration module names of the form `vNNNN_description`. The `v` prefix
# is required so the name is a valid Python identifier - pkgutil.iter_modules
# silently skips files whose names start with a digit.
_MODULE_RE = re.compile(r"^v(\d+)_.+$")


class ConfigAdapter(Protocol):
    """Format-agnostic interface for reading and modifying a config file."""

    def has(self, section: str, key: str) -> bool:
        """Check whether a key is an active (non-commented) entry in a section.

        Args:
            section (str): INI section name.
            key (str): Key name to look up.

        Returns:
            bool: True if the key exists and is not commented out.
        """
        ...

    def get(self, section: str, key: str) -> str:
        """Return the raw string value of a key in a section.

        Args:
            section (str): INI section name.
            key (str): Key name to read.

        Returns:
            str: The raw string value.
        """
        ...

    def rename_key(self, section: str, old_key: str, new_key: str) -> None:
        """Rename a key within a section, preserving its value.

        No-op if old_key is not present.

        Args:
            section (str): INI section containing the key.
            old_key (str): Existing key name.
            new_key (str): Replacement key name.
        """
        ...

    def remove_key(self, section: str, key: str) -> None:
        """Remove a key from a section, typically by commenting it out.

        No-op if key is not present.

        Args:
            section (str): INI section containing the key.
            key (str): Key name to remove.
        """
        ...

    def carry_key(
        self, src_section: str, src_key: str, dst_section: str, dst_key: str
    ) -> None:
        """Copy a key's value to another key, then remove the source key.

        The value is only copied when dst_key is not already set, so an
        explicit user value is never overwritten. No-op if src_key is absent.

        Args:
            src_section (str): Section containing the source key.
            src_key (str): Key whose value is carried over.
            dst_section (str): Section to write the value into.
            dst_key (str): Key to receive the value.
        """
        ...

    def set_key(self, section: str, key: str, value: str) -> None:
        """Set a key to a value, creating the key or section if absent.

        Args:
            section (str): INI section name.
            key (str): Key name to set.
            value (str): Value to write.
        """
        ...

    def get_version(self) -> int | None:
        """Return the current config version number.

        Returns:
            int | None: The recorded version, or None if no version is stored
            yet.
        """
        ...

    def set_version(self, version: int) -> None:
        """Write the config version number.

        Args:
            version (int): Version integer to record.
        """
        ...

    def save(self) -> None:
        """Persist all in-memory changes back to the underlying file."""
        ...


MigrationFn = Callable[[ConfigAdapter], None]


@dataclass
class MigrationStep:
    from_version: int
    to_version: int
    description: str
    fn: MigrationFn = field(repr=False)


class MigrationChain:
    """Discovers and replays numbered migration modules against a ConfigAdapter.

    Files without a version key are treated as *initial_version* (default 0).

    Each migration module must live in the given package, be named
    `vNNNN_description` (where NNNN is the *target* version), and expose:

        description: str          # human-readable summary
        def upgrade(cfg) -> None  # mutates the adapter

    Discovery uses :func:`pkgutil.iter_modules` so the chain works in both
    development and PyInstaller binaries (where `.py` source files are absent
    at runtime).

    Args:
        package_path (list[str]): The `__path__` of the migrations package.
        package_name (str): The `__name__` of the migrations package.
        initial_version (int): Version assumed when the config has no version
            key yet.
    """

    def __init__(
        self,
        package_path: list[str],
        package_name: str,
        initial_version: int = 0,
    ) -> None:
        self._initial = initial_version
        self._steps: dict[int, MigrationStep] = self._discover(
            package_path, package_name
        )

    # ── Discovery ─────────────────────────────────────────────────────────────

    @staticmethod
    def _discover(
        package_path: list[str], package_name: str
    ) -> dict[int, MigrationStep]:
        """Collect and sort migration steps from the package, ordered by
        version.

        Args:
            package_path (list[str]): ``__path__`` of the migrations package.
            package_name (str): ``__name__`` of the migrations package.

        Returns:
            dict[int, MigrationStep]: Mapping of from-version to migration step.
        """

        entries: list[tuple[int, str]] = []

        for info in pkgutil.iter_modules(package_path):
            num_match = _MODULE_RE.match(info.name)

            if num_match:
                entries.append((int(num_match.group(1)), info.name))

        entries.sort()

        steps: dict[int, MigrationStep] = {}

        for to_ver, name in entries:
            mod = importlib.import_module(f"{package_name}.{name}")
            upgrade: MigrationFn | None = getattr(mod, "upgrade", None)

            if upgrade is None:
                continue

            steps[to_ver - 1] = MigrationStep(
                from_version=to_ver - 1,
                to_version=to_ver,
                description=getattr(mod, "description", ""),
                fn=upgrade,
            )

        return steps

    # ── Runtime ───────────────────────────────────────────────────────────────

    def pending(self, adapter: ConfigAdapter) -> list[MigrationStep]:
        """Return every step not yet applied to the adapter, in ascending order.

        Args:
            adapter (ConfigAdapter): Adapter representing the config to inspect.

        Returns:
            list[MigrationStep]: Pending steps ordered by version.
        """
        current = adapter.get_version()

        if current is None:
            current = self._initial

        steps: list[MigrationStep] = []

        while current in self._steps:
            step = self._steps[current]
            steps.append(step)
            current = step.to_version

        return steps

    def apply(self, adapter: ConfigAdapter) -> None:
        """Replay all pending migrations, bump the version, and save.

        Args:
            adapter (ConfigAdapter): Adapter representing the config to migrate.
        """
        steps = self.pending(adapter)

        if not steps:
            return

        for step in steps:
            step.fn(adapter)

        adapter.set_version(steps[-1].to_version)
        adapter.save()
