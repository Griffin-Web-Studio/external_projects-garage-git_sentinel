from __future__ import annotations

import pytest

from src.config.template import render_config, wrap_comment
from src.models import ConfigEntry, ConfigSection

# ──────────────────────────────────────────────────────────| wrap_comment() |──


class TestWrapComment:
    """Tests wrap_comment() word-wraps prose into '; '-prefixed lines."""

    def test_short_text_fits_on_one_line(self) -> None:
        """Text shorter than the content width is returned as a single line."""
        result = wrap_comment("Hello world.")

        assert result == "; Hello world."

    def test_wraps_at_word_boundary(self) -> None:
        """Long text is broken at a space so no line exceeds the width."""
        # 78 chars of content: fill with words that force a second line
        text = "word " * 20  # well over 80 chars total
        lines = wrap_comment(text).splitlines()

        assert all(len(line) <= 80 for line in lines)
        assert all(line.startswith("; ") for line in lines)

    def test_punctuation_carried_with_preceding_word(self) -> None:
        """When 'word,' would overflow a line, the entire token moves to the
        next line - the comma is never left stranded on the previous line.

        25 "xx" words -> 74 content chars. "end" alone (3) would fit (78),
        but "end," (4) overflows (79), so the algorithm must carry "end,"
        atomically to the next line.
        """
        filler = "xx " * 25  # 25 words of len 2 -> content length 74
        text = filler.rstrip() + " end, next"
        lines = wrap_comment(text).splitlines()

        # The line that contains "end," must START with it (after "; "),
        # proving the token was not split from its attached comma.
        line_with_end = next((ln for ln in lines if "end," in ln), None)

        assert line_with_end is not None, "'end,' not found in output"
        assert line_with_end[2:].startswith(
            "end,"
        ), f"'end,' should begin its line but got: {line_with_end!r}"

    def test_long_single_word_gets_own_line(self) -> None:
        """A word longer than the content width is placed on its own line."""
        long_word = "a" * 90  # exceeds 78-char content limit
        result = wrap_comment(long_word)

        assert result == f"; {long_word}"

    def test_custom_width(self) -> None:
        """The width parameter is respected."""
        text = "one two three four five six seven eight nine ten"
        lines = wrap_comment(text, width=20).splitlines()

        assert all(len(line) <= 20 for line in lines)

    def test_empty_string_returns_empty(self) -> None:
        """An empty input string produces an empty output string."""
        assert wrap_comment("") == ""


# ─────────────────────────────────────────────────────────| render_config() |──


class TestRenderConfig:
    """Tests render_config() produces correctly structured ini content."""

    def _simple_section(self) -> ConfigSection:
        return ConfigSection(
            "paths",
            [
                ConfigEntry("git_root", "git", "Scan root."),
            ],
        )

    def test_header_appears_first(self) -> None:
        """The header string is the first content in the output."""
        header = "; my header"
        result = render_config(header, [self._simple_section()])

        assert result.startswith(header)

    def test_two_blank_lines_before_first_section(self) -> None:
        """Two blank lines separate the header from the first [section]."""
        result = render_config("; hdr", [self._simple_section()])

        assert "; hdr\n\n\n[paths]" in result

    def test_two_blank_lines_between_sections(self) -> None:
        """Two blank lines separate consecutive sections."""
        sections = [
            ConfigSection("a", [ConfigEntry("k1", "v1", "d1")]),
            ConfigSection("b", [ConfigEntry("k2", "v2", "d2")]),
        ]
        result = render_config("; hdr", sections)

        assert "\n\n\n[b]" in result

    def test_one_blank_line_before_each_entry(self) -> None:
        """One blank line appears between the section header and the first
        entry, and between consecutive entries."""
        result = render_config("; hdr", [self._simple_section()])

        assert "[paths]\n\n; Scan root." in result

    def test_enabled_entry_written_as_plain_key(self) -> None:
        """enabled=True (default) writes 'key = value' without a comment
        prefix."""
        section = ConfigSection("s", [ConfigEntry("k", "v", "d")])
        result = render_config("; h", [section])

        assert "\nk = v\n" in result

    def test_disabled_entry_is_commented_out(self) -> None:
        """enabled=False writes '; key = value'."""
        section = ConfigSection(
            "s",
            [
                ConfigEntry("k", "v", "d", enabled=False),
            ],
        )
        result = render_config("; h", [section])

        assert "\n; k = v\n" in result

    def test_multiline_description_has_semicolon_separator(self) -> None:
        r"""A '\n' in description renders as a lone ';' line between
        paragraphs."""
        section = ConfigSection(
            "s",
            [
                ConfigEntry("k", "v", "Para one.\nPara two."),
            ],
        )
        result = render_config("; h", [section])

        assert "; Para one.\n;\n; Para two." in result

    def test_output_ends_with_single_newline(self) -> None:
        """The rendered string ends with exactly one trailing newline."""
        result = render_config("; h", [self._simple_section()])

        assert result.endswith("\n")
        assert not result.endswith("\n\n")
