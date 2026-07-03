from __future__ import annotations

from src.models import ConfigEntry, ConfigSection  # noqa: F401

# ────────────────────────────────────────────────────────| Comment wrapping |──

_PREFIX = "; "
_WIDTH = 80


def wrap_comment(text: str, width: int = _WIDTH) -> str:
    """Wrap *text* into '; '-prefixed comment lines of at most *width* chars.

    Splits on whitespace. A word with punctuation directly attached (no space
    between word and mark) is treated as one atomic token - it moves to the next
    line as a unit rather than leaving the mark behind. A word longer than the
    available content width is placed on its own line.
    """
    prefix = _PREFIX
    max_content = width - len(prefix)
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    current_len = 0

    for word in words:
        needed = len(word) if not current else current_len + 1 + len(word)

        if needed <= max_content:
            current.append(word)
            current_len = needed

        else:
            if current:
                lines.append(prefix + " ".join(current))

            current = [word]
            current_len = len(word)

    if current:
        lines.append(prefix + " ".join(current))

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────| Renderer |──


def render_config(header: str, sections: list[ConfigSection]) -> str:
    """Render a complete settings file from a header string and sections.

    Layout rules:
    - Two blank lines separate the header from the first section and each
      section from the next.
    - One blank line separates consecutive entries within a section.
    - Multi-paragraph descriptions (paragraphs split by ``\\n``) are rendered
      as separate wrapped comment blocks divided by a lone ``;`` line.

    Args:
        header: Pre-formatted block placed before the first section (typically
                separator lines and file metadata built with wrap_comment).
        sections: Ordered list of ConfigSection objects to render.

    Returns:
        str: Complete file content ending with a single trailing newline.
    """
    parts: list[str] = [header]

    for section in sections:
        parts += ["", ""]  # two blank lines before each [section]
        parts.append(f"[{section.name}]")

        for entry in section.entries:
            parts.append("")  # one blank line before each entry

            for i, para in enumerate(entry.description.split("\n")):
                if i > 0:
                    parts.append(";")  # blank comment line between paragraphs

                parts.append(wrap_comment(para.strip()))

            key_line = f"{entry.label} = {entry.default}"
            parts.append(key_line if entry.enabled else f"; {key_line}")

    parts.append("")  # trailing newline
    return "\n".join(parts)
