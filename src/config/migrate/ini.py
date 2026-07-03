from __future__ import annotations

import configparser
import re
from pathlib import Path
from typing import Iterator

# ─────────────────────────────────────────────────────────────| INI adapter |──

_SECTION_RE = re.compile(r"^\[([^\]]+)\]")


def _iter_sections(
    lines: list[str],
) -> Iterator[tuple[int, str, str | None]]:
    """Yield `(index, line, current_section)` for every line.

    The section name is updated when a header line is encountered, so the header
    line itself is yielded under the new section name - callers can insert
    content immediately after it.
    """

    current: str | None = None

    for idx, line in enumerate(lines):
        sec_match = _SECTION_RE.match(line.strip())

        if sec_match:
            current = sec_match.group(1)

        yield idx, line, current


def _is_active_key(line: str, key: str) -> bool:
    """Return True if *line* is an uncommented `key = ...` assignment.

    Skips lines that start with `;` or `#` (INI comment markers) so that
    commented-out keys are never treated as active configuration.

    Args:
        line (str): Raw line from the INI file, including any leading
                    whitespace.
        key (str): Key name to match.

    Returns:
        bool: True if the line is an active assignment for *key*.
    """

    stripped = line.lstrip()

    if stripped.startswith((";", "#")):
        return False

    return bool(re.match(r"^\s*" + re.escape(key) + r"\s*=", line))


class IniAdapter:
    """Line-preserving INI adapter using only the standard library.

    Maintains two parallel views of the file:

    * `_lines` - the raw line list used for all writes, preserving comments,
      blank lines, and indentation exactly as the user left them.
    * `_cfg` - a :class:`configparser.ConfigParser` used for fast reads
      (`has`, `get`, `get_version`).

    Every write method must update **both** so they stay in sync. Call
    :meth:`save` to flush the line list back to disk.

    Args:
        path (Path): Path to the INI file to read and (eventually) write.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lines: list[str] = path.read_text(encoding="utf-8").splitlines(
            keepends=True
        )
        self._cfg = configparser.ConfigParser()

        self._cfg.read(path)

    # ── Reading ───────────────────────────────────────────────────────────────

    def has(self, section: str, key: str) -> bool:
        """Return True if *key* is an active entry in *section*.

        Args:
            section (str): INI section name.
            key (str): Key name to look up.

        Returns:
            bool: True if the key exists and is not commented out.
        """

        return self._cfg.has_option(section, key)

    def get(self, section: str, key: str) -> str:
        """Return the raw string value of *key* in *section*.

        Args:
            section (str): INI section name.
            key (str): Key name to read.

        Returns:
            str: The raw string value.
        """

        return self._cfg.get(section, key)

    def get_version(self) -> int | None:
        """Return the integer stored at `[meta] version`, or None if absent.

        Returns:
            int | None: The recorded version, or None if no version is stored
                        yet.
        """

        try:
            return self._cfg.getint("meta", "version")

        except (
            configparser.NoSectionError,
            configparser.NoOptionError,
            ValueError,
        ):
            return None

    # ── Writing ───────────────────────────────────────────────────────────────

    def rename_key(self, section: str, old_key: str, new_key: str) -> None:
        """Rename *old_key* to *new_key* in *section*, preserving its value.

        No-op if *old_key* is not present.

        Args:
            section (str): INI section containing the key.
            old_key (str): Existing key name.
            new_key (str): Replacement key name.
        """

        if not self._cfg.has_option(section, old_key):
            return

        def _rename(match: re.Match[str]) -> str:
            # Preserve any leading whitespace and the spacing around `=`.
            return match.group(1) + new_key + match.group(2)

        # Phase 1: rewrite the matching line in-place to keep comments intact.
        for idx, line, sec in _iter_sections(self._lines):
            if sec == section and _is_active_key(line, old_key):
                self._lines[idx] = re.sub(
                    r"(\s*)" + re.escape(old_key) + r"(\s*=)",
                    _rename,
                    line,
                    count=1,
                )

                break

        # Phase 2: sync configparser so subsequent has()/get() calls reflect
        # the rename without re-reading the file.
        value = self._cfg.get(section, old_key)
        self._cfg.remove_option(section, old_key)

        if not self._cfg.has_section(section):
            # Defensive: has_option() above already implies has_section() is
            # True for every section except DEFAULT, and configparser itself
            # forbids re-adding DEFAULT via add_section().
            self._cfg.add_section(section)  # pragma: no cover

        self._cfg.set(section, new_key, value)

    def remove_key(self, section: str, key: str) -> None:
        """Comment out *key* in *section* rather than deleting it.

        Commenting out preserves the user's value as a reference, and avoids
        leaving a gap in the file that would confuse a human reader.
        No-op if *key* is not present.

        Args:
            section (str): INI section containing the key.
            key (str): Key name to remove.
        """

        if not self._cfg.has_option(section, key):
            return

        for idx, line, sec in _iter_sections(self._lines):
            if sec == section and _is_active_key(line, key):
                self._lines[idx] = "; " + line

                break

        self._cfg.remove_option(section, key)

    def carry_key(
        self, src_section: str, src_key: str, dst_section: str, dst_key: str
    ) -> None:
        """Copy *src_key*'s value to *dst_key*, then remove *src_key*.

        The value is only copied when *dst_key* is not already set, so an
        explicit user value is never overwritten. No-op if *src_key* is absent.

        Args:
            src_section (str): Section containing the source key.
            src_key (str): Key whose value is carried over.
            dst_section (str): Section to write the value into.
            dst_key (str): Key to receive the value.
        """

        if not self.has(src_section, src_key):
            return

        value = self.get(src_section, src_key)

        # Only write the destination when it has not already been set - an
        # explicit user value always wins.
        if not self.has(dst_section, dst_key):
            self.set_key(dst_section, dst_key, value)

        self.remove_key(src_section, src_key)

    def set_key(self, section: str, key: str, value: str) -> None:
        """Set *key* to *value* in *section*, creating the key or section if
        absent.

        Args:
            section (str): INI section name.
            key (str): Key name to set.
            value (str): Value to write.
        """

        if self.has(section, key):
            self._overwrite_line(section, key, value)

        else:
            self._lines = self._insert_after_section(
                section, f"{key} = {value}\n"
            )

        if not self._cfg.has_section(section):
            self._cfg.add_section(section)

        self._cfg.set(section, key, value)

    def set_version(self, version: int) -> None:
        """Write *version* to `[meta] version`, creating the section if needed.

        Args:
            version (int): Version integer to record.
        """

        self.set_key("meta", "version", str(version))

    def save(self) -> None:
        """Persist all in-memory changes back to the file on disk."""

        self._path.write_text("".join(self._lines), encoding="utf-8")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _overwrite_line(self, section: str, key: str, value: str) -> None:
        """Find the active *key* line in *section* and replace its value.

        Args:
            section (str): INI section containing the key.
            key (str): Key whose value should be updated.
            value (str): New value to write.
        """

        def _set(match: re.Match[str]) -> str:
            # Keep the original `key =` prefix (including its whitespace)
            # and replace only the value that follows.
            return match.group(1) + value

        for idx, line, sec in _iter_sections(self._lines):
            # Skip lines that belong to a different section or are not the
            # target key; the guard-continue keeps the happy path un-indented.
            if sec != section or not _is_active_key(line, key):
                continue

            self._lines[idx] = (
                re.sub(
                    r"(\s*" + re.escape(key) + r"\s*=\s*).*",
                    _set,
                    line,
                ).rstrip("\n")
                + "\n"
            )

            return

    def _insert_after_section(self, section: str, new_line: str) -> list[str]:
        """Return a new line list with *new_line* inserted after *section*'s
        header.

        Builds a fresh list rather than splicing in-place so the caller can
        replace `self._lines` atomically. Creates the section at the end of
        the file if it does not already exist.

        Args:
            section (str): INI section to insert into.
            new_line (str): Fully-formed `key = value\\n` line to insert.

        Returns:
            list[str]: Updated line list.
        """

        result: list[str] = []
        inserted = False

        for line in self._lines:
            sec_match = _SECTION_RE.match(line.strip())

            if sec_match and sec_match.group(1) == section and not inserted:
                result.append(line)
                result.append(new_line)
                inserted = True

                continue

            result.append(line)

        if not inserted:
            # Section not found - append it at the end of the file.
            result.append(f"\n[{section}]\n{new_line}")

        return result
