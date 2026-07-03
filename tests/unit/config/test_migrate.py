from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import pytest

from src.config.migrate import MigrationChain
from src.config.migrate.ini import IniAdapter, _is_active_key, _iter_sections

# ─────────────────────────────────────────────────────────| Shared fixtures |──

_SIMPLE_INI = """\
[paths]
git_root = ~/git
export_path = ~/Desktop

[reports]
retention_days = 14
"""

_VERSIONED_INI = """\
[paths]
git_root = ~/git

[meta]
version = 3
"""


@pytest.fixture
def fake_pkg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[tuple[str, Path], None, None]:
    """Create a temporary importable migration package for chain tests.

    Args:
        tmp_path (Path): Unique temporary directory provided by pytest.
        monkeypatch (pytest.MonkeyPatch): Used to prepend tmp_path to sys.path.

    Yields:
        tuple[str, Path]: (package_name, package_directory) ready to populate.
    """

    pkg_name = f"_migtest_{id(tmp_path) & 0xFFFFFFFF:08x}"
    pkg_dir = tmp_path / pkg_name

    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))

    yield pkg_name, pkg_dir

    for key in list(sys.modules):
        if key == pkg_name or key.startswith(f"{pkg_name}."):
            del sys.modules[key]


# ──────────────────────────────────────────────────────────| _iter_sections |──


class TestIterSections:
    """Tests the _iter_sections helper yields (idx, line, section) correctly."""

    def test_section_is_none_before_first_header(self) -> None:
        """Lines before any section header are yielded with section=None."""

        lines = ["# top comment\n"]

        _, _, sec = list(_iter_sections(lines))[0]

        assert sec is None

    def test_header_line_yielded_under_its_own_section(self) -> None:
        """The header line itself is already attributed to the new section."""

        lines = ["[paths]\n", "key = val\n"]
        result = list(_iter_sections(lines))

        assert result[0][2] == "paths"
        assert result[1][2] == "paths"

    def test_section_changes_on_new_header(self) -> None:
        """All lines under a header are attributed to that section until the
        next."""

        lines = ["[a]\n", "x = 1\n", "[b]\n", "y = 2\n"]
        secs = [sec for _, _, sec in _iter_sections(lines)]

        assert secs == ["a", "a", "b", "b"]

    def test_indices_are_sequential(self) -> None:
        """Yielded index values match the position in the input list."""

        lines = ["[a]\n", "x = 1\n", "y = 2\n"]
        indices = [idx for idx, _, _ in _iter_sections(lines)]

        assert indices == [0, 1, 2]


# ──────────────────────────────────────────────────────────| _is_active_key |──


class TestIsActiveKey:
    """Tests _is_active_key distinguishes active assignments from comments."""

    def test_active_assignment_matches(self) -> None:
        """A plain key = value line is active."""

        assert _is_active_key("key = value\n", "key") is True

    def test_spaces_around_equals_still_match(self) -> None:
        """Extra whitespace around = does not prevent a match."""

        assert _is_active_key("key  =  value\n", "key") is True

    def test_semicolon_comment_is_inactive(self) -> None:
        """A line starting with ; is not an active key."""

        assert _is_active_key("; key = value\n", "key") is False

    def test_hash_comment_is_inactive(self) -> None:
        """A line starting with # is not an active key."""

        assert _is_active_key("# key = value\n", "key") is False

    def test_different_key_does_not_match(self) -> None:
        """A line for a different key does not match the requested key."""

        assert _is_active_key("other_key = value\n", "key") is False


# ──────────────────────────────────────────────────────────────| IniAdapter |──


class TestIniAdapterReading:
    """Tests IniAdapter read operations: has, get, get_version."""

    def test_has_returns_true_for_existing_key(self, tmp_path: Path) -> None:
        """has() returns True when the key exists in the section.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text(_SIMPLE_INI, encoding="utf-8")

        assert IniAdapter(ini).has("paths", "export_path") is True

    def test_has_returns_false_for_missing_key(self, tmp_path: Path) -> None:
        """has() returns False when the key is absent from the section.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text(_SIMPLE_INI, encoding="utf-8")

        assert IniAdapter(ini).has("paths", "nonexistent") is False

    def test_get_returns_value(self, tmp_path: Path) -> None:
        """get() returns the raw string value for an existing key.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text(_SIMPLE_INI, encoding="utf-8")

        assert IniAdapter(ini).get("paths", "git_root") == "~/git"

    def test_get_version_returns_int_when_set(self, tmp_path: Path) -> None:
        """get_version() returns the integer from [meta] version.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text(_VERSIONED_INI, encoding="utf-8")

        assert IniAdapter(ini).get_version() == 3

    def test_get_version_returns_none_when_absent(self, tmp_path: Path) -> None:
        """get_version() returns None when no [meta] version key exists.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text(_SIMPLE_INI, encoding="utf-8")

        assert IniAdapter(ini).get_version() is None


class TestIniAdapterRenameKey:
    """Tests IniAdapter.rename_key preserves values and comments."""

    def test_new_key_is_readable(self, tmp_path: Path) -> None:
        """After rename, the new key is accessible via has() and get().

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text("[paths]\nold = ~/Desktop\n", encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.rename_key("paths", "old", "new")

        assert adapter.has("paths", "new") is True
        assert adapter.get("paths", "new") == "~/Desktop"

    def test_old_key_is_gone(self, tmp_path: Path) -> None:
        """After rename, the old key name no longer exists.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text("[paths]\nold = ~/Desktop\n", encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.rename_key("paths", "old", "new")

        assert adapter.has("paths", "old") is False

    def test_noop_when_key_absent(self, tmp_path: Path) -> None:
        """rename_key is a no-op when the source key does not exist.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text(_SIMPLE_INI, encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.rename_key("paths", "nonexistent", "new")

        assert adapter.has("paths", "new") is False

    def test_surrounding_comments_are_preserved(self, tmp_path: Path) -> None:
        """Comments adjacent to the renamed key survive the rewrite.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text(
            "[paths]\n# above\nold = val\n# below\n", encoding="utf-8"
        )
        adapter = IniAdapter(ini)
        adapter.rename_key("paths", "old", "new")
        adapter.save()
        content = ini.read_text(encoding="utf-8")

        assert "# above" in content
        assert "# below" in content


class TestIniAdapterRemoveKey:
    """Tests IniAdapter.remove_key comments out the line rather than deleting it."""

    def test_key_is_no_longer_active(self, tmp_path: Path) -> None:
        """After remove_key, has() returns False for that key.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text("[paths]\nkey = val\n", encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.remove_key("paths", "key")

        assert adapter.has("paths", "key") is False

    def test_line_is_commented_out_on_disk(self, tmp_path: Path) -> None:
        """save() writes a ; prefixed line instead of deleting it.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text("[paths]\nkey = val\n", encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.remove_key("paths", "key")
        adapter.save()
        content = ini.read_text(encoding="utf-8")

        assert "; key" in content

    def test_noop_when_key_absent(self, tmp_path: Path) -> None:
        """remove_key is a no-op when the key does not exist.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text(_SIMPLE_INI, encoding="utf-8")
        original = ini.read_text(encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.remove_key("paths", "nonexistent")

        assert "".join(adapter._lines) == original


class TestIniAdapterCarryKey:
    """Tests IniAdapter.carry_key copies value to dst then removes src."""

    def test_copies_value_to_destination(self, tmp_path: Path) -> None:
        """carry_key writes the source value to the destination key.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text("[paths]\nsrc = old_val\n", encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.carry_key("paths", "src", "paths", "dst")

        assert adapter.has("paths", "dst") is True
        assert adapter.get("paths", "dst") == "old_val"

    def test_removes_source_key(self, tmp_path: Path) -> None:
        """carry_key removes the source key after copying.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text("[paths]\nsrc = old_val\n", encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.carry_key("paths", "src", "paths", "dst")

        assert adapter.has("paths", "src") is False

    def test_does_not_overwrite_existing_dst(self, tmp_path: Path) -> None:
        """carry_key leaves dst unchanged when it already has a value.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text(
            "[paths]\nsrc = from_src\ndst = existing\n", encoding="utf-8"
        )
        adapter = IniAdapter(ini)
        adapter.carry_key("paths", "src", "paths", "dst")

        assert adapter.get("paths", "dst") == "existing"

    def test_noop_when_src_absent(self, tmp_path: Path) -> None:
        """carry_key is a no-op when the source key does not exist.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text(_SIMPLE_INI, encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.carry_key("paths", "nonexistent", "paths", "dst")

        assert adapter.has("paths", "dst") is False


class TestIniAdapterSetKey:
    """Tests IniAdapter.set_key creates or overwrites keys."""

    def test_overwrites_existing_value(self, tmp_path: Path) -> None:
        """set_key replaces the value of an existing key.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text("[paths]\nkey = old\n", encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.set_key("paths", "key", "new")

        assert adapter.get("paths", "key") == "new"

    def test_inserts_new_key_into_existing_section(
        self, tmp_path: Path
    ) -> None:
        """set_key adds a new key to a section that already exists.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text("[paths]\nexisting = x\n", encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.set_key("paths", "fresh", "value")

        assert adapter.has("paths", "fresh") is True
        assert adapter.get("paths", "fresh") == "value"

    def test_creates_new_section_when_absent(self, tmp_path: Path) -> None:
        """set_key appends a new section and key when the section does not exist.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text("[paths]\nexisting = x\n", encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.set_key("meta", "version", "5")

        assert adapter.has("meta", "version") is True
        assert adapter.get("meta", "version") == "5"

    def test_set_version_writes_to_meta_section(self, tmp_path: Path) -> None:
        """set_version stores an integer under [meta] version.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text(_SIMPLE_INI, encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.set_version(7)

        assert adapter.get_version() == 7

    def test_save_persists_all_changes_to_disk(self, tmp_path: Path) -> None:
        """save() writes the full in-memory line list back to the file.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text("[paths]\nkey = old\n", encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.set_key("paths", "key", "saved")
        adapter.save()

        assert "key = saved" in ini.read_text(encoding="utf-8")

    def test_rename_key_only_affects_correct_section(
        self, tmp_path: Path
    ) -> None:
        """rename_key in section A does not affect the same key name in section B.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        content = "[a]\nkey = from_a\n\n[b]\nkey = from_b\n"
        ini = tmp_path / "s.ini"

        ini.write_text(content, encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.rename_key("a", "key", "renamed")

        assert adapter.has("a", "renamed") is True
        assert adapter.has("b", "key") is True

    def test_get_version_returns_none_for_non_integer_value(
        self, tmp_path: Path
    ) -> None:
        """get_version() returns None when the version value is not a valid int.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text("[meta]\nversion = not_a_number\n", encoding="utf-8")

        assert IniAdapter(ini).get_version() is None

    def test_set_key_new_key_appears_immediately_after_section_header(
        self, tmp_path: Path
    ) -> None:
        """A new key is inserted on the line directly after the section header.

        Args:
            tmp_path (Path): Temporary directory for the INI file.
        """

        ini = tmp_path / "s.ini"

        ini.write_text("[paths]\nexisting = x\n", encoding="utf-8")
        adapter = IniAdapter(ini)
        adapter.set_key("paths", "fresh", "value")
        adapter.save()
        lines = ini.read_text(encoding="utf-8").splitlines()
        header_idx = next(i for i, ln in enumerate(lines) if "[paths]" in ln)

        assert "fresh = value" in lines[header_idx + 1]


# ──────────────────────────────────────────────────────────| MigrationChain |──


class TestMigrationChain:
    """Tests MigrationChain discovery, pending detection, and apply."""

    def test_discovers_versioned_module(
        self, fake_pkg: tuple[str, Path]
    ) -> None:
        """_discover finds a vNNNN_ module and registers it as a step.

        Args:
            fake_pkg (tuple[str, Path]): Temporary package name and directory.
        """

        pkg_name, pkg_dir = fake_pkg

        (pkg_dir / "v0001_first.py").write_text(
            'description = "first"\ndef upgrade(cfg): pass\n'
        )
        chain = MigrationChain(
            package_path=[str(pkg_dir)],
            package_name=pkg_name,
            initial_version=0,
        )

        assert 0 in chain._steps
        assert chain._steps[0].to_version == 1
        assert chain._steps[0].description == "first"

    def test_ignores_modules_without_upgrade_fn(
        self, fake_pkg: tuple[str, Path]
    ) -> None:
        """A vNNNN_ module with no upgrade() function is discovered but not
        registered as a step.

        Args:
            fake_pkg (tuple[str, Path]): Temporary package name and directory.
        """

        pkg_name, pkg_dir = fake_pkg
        (pkg_dir / "v0001_no_upgrade.py").write_text('description = "nope"\n')
        chain = MigrationChain(
            package_path=[str(pkg_dir)],
            package_name=pkg_name,
            initial_version=0,
        )

        assert len(chain._steps) == 0

    def test_ignores_modules_without_v_prefix(
        self, fake_pkg: tuple[str, Path]
    ) -> None:
        """A file named 0001_... (no v prefix) is not picked up by pkgutil.

        Args:
            fake_pkg (tuple[str, Path]): Temporary package name and directory.
        """

        pkg_name, pkg_dir = fake_pkg

        (pkg_dir / "0001_no_prefix.py").write_text(
            'description = "nope"\ndef upgrade(cfg): pass\n'
        )
        chain = MigrationChain(
            package_path=[str(pkg_dir)],
            package_name=pkg_name,
            initial_version=0,
        )

        assert len(chain._steps) == 0

    def test_pending_returns_empty_when_version_is_current(
        self, fake_pkg: tuple[str, Path], tmp_path: Path
    ) -> None:
        """pending() returns an empty list when the config version matches.

        Args:
            fake_pkg (tuple[str, Path]): Temporary package name and directory.
            tmp_path (Path): Temporary directory for the INI file.
        """

        pkg_name, pkg_dir = fake_pkg

        (pkg_dir / "v0001_first.py").write_text(
            'description = ""\ndef upgrade(cfg): pass\n'
        )
        ini = tmp_path / "s.ini"
        ini.write_text("[meta]\nversion = 1\n", encoding="utf-8")
        chain = MigrationChain([str(pkg_dir)], pkg_name, initial_version=0)

        assert chain.pending(IniAdapter(ini)) == []

    def test_pending_returns_step_when_behind(
        self, fake_pkg: tuple[str, Path], tmp_path: Path
    ) -> None:
        """pending() returns steps when the config version is behind.

        Args:
            fake_pkg (tuple[str, Path]): Temporary package name and directory.
            tmp_path (Path): Temporary directory for the INI file.
        """

        pkg_name, pkg_dir = fake_pkg

        (pkg_dir / "v0001_first.py").write_text(
            'description = ""\ndef upgrade(cfg): pass\n'
        )
        ini = tmp_path / "s.ini"
        ini.write_text("[paths]\nkey = val\n", encoding="utf-8")
        chain = MigrationChain([str(pkg_dir)], pkg_name, initial_version=0)
        steps = chain.pending(IniAdapter(ini))

        assert len(steps) == 1
        assert steps[0].to_version == 1

    def test_apply_runs_upgrade_and_bumps_version(
        self, fake_pkg: tuple[str, Path], tmp_path: Path
    ) -> None:
        """apply() calls upgrade(), sets version to the last step's to_version.

        Args:
            fake_pkg (tuple[str, Path]): Temporary package name and directory.
            tmp_path (Path): Temporary directory for the INI file.
        """

        pkg_name, pkg_dir = fake_pkg

        (pkg_dir / "v0001_first.py").write_text(
            'description = ""\n'
            'def upgrade(cfg): cfg.set_key("paths", "migrated", "yes")\n'
        )
        ini = tmp_path / "s.ini"
        ini.write_text("[paths]\noriginal = yes\n", encoding="utf-8")
        chain = MigrationChain([str(pkg_dir)], pkg_name, initial_version=0)
        adapter = IniAdapter(ini)
        chain.apply(adapter)

        assert adapter.get_version() == 1
        assert adapter.has("paths", "migrated") is True

    def test_apply_saves_to_disk(
        self, fake_pkg: tuple[str, Path], tmp_path: Path
    ) -> None:
        """apply() flushes all changes to disk via adapter.save().

        Args:
            fake_pkg (tuple[str, Path]): Temporary package name and directory.
            tmp_path (Path): Temporary directory for the INI file.
        """

        pkg_name, pkg_dir = fake_pkg

        (pkg_dir / "v0001_first.py").write_text(
            'description = ""\ndef upgrade(cfg): pass\n'
        )
        ini = tmp_path / "s.ini"
        ini.write_text("[paths]\nkey = val\n", encoding="utf-8")
        chain = MigrationChain([str(pkg_dir)], pkg_name, initial_version=0)
        chain.apply(IniAdapter(ini))

        assert "version = 1" in ini.read_text(encoding="utf-8")

    def test_apply_is_noop_when_already_current(
        self, fake_pkg: tuple[str, Path], tmp_path: Path
    ) -> None:
        """apply() does not run any upgrade when the version is already current.

        Args:
            fake_pkg (tuple[str, Path]): Temporary package name and directory.
            tmp_path (Path): Temporary directory for the INI file.
        """

        pkg_name, pkg_dir = fake_pkg

        (pkg_dir / "v0001_first.py").write_text(
            'description = ""\n'
            'def upgrade(cfg): cfg.set_key("paths", "should_not_appear", "1")\n'
        )
        ini = tmp_path / "s.ini"
        ini.write_text(
            "[paths]\nkey = val\n\n[meta]\nversion = 1\n", encoding="utf-8"
        )
        chain = MigrationChain([str(pkg_dir)], pkg_name, initial_version=0)
        adapter = IniAdapter(ini)
        chain.apply(adapter)

        assert adapter.has("paths", "should_not_appear") is False
