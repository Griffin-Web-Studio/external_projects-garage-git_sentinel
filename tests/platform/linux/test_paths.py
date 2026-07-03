from __future__ import annotations

from pathlib import Path

import pytest

from src.platform.linux.paths import conf_dir, ssh_sock_dir, state_dir

# ───────────────────────────────────────────────────────────────| conf_dir |──


class TestConfDir:
    """Tests conf_dir builds the XDG config path."""

    def test_returns_dot_config_subdir(self, tmp_path: Path) -> None:
        """conf_dir resolves to <home>/.config/<app_name>.

        Args:
            tmp_path (Path): Stand-in home directory.
        """

        result = conf_dir(tmp_path, "git-sentinel")

        assert result == tmp_path / ".config" / "git-sentinel"


# ──────────────────────────────────────────────────────────────| state_dir |──


class TestStateDir:
    """Tests state_dir builds the XDG state path."""

    def test_returns_local_share_subdir(self, tmp_path: Path) -> None:
        """state_dir resolves to <home>/.local/share/<app_name>.

        Args:
            tmp_path (Path): Stand-in home directory.
        """

        result = state_dir(tmp_path, "git-sentinel")

        assert result == tmp_path / ".local" / "share" / "git-sentinel"


# ──────────────────────────────────────────────────────────| ssh_sock_dir |──


class TestSshSockDir:
    """Tests ssh_sock_dir's UID-suffixing behaviour across platforms."""

    def test_linux_appends_uid_suffix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Linux, the socket dir name is suffixed with the caller's UID to
        avoid collisions on a shared /tmp.

        Args:
            tmp_path (Path): Stand-in temp directory.
            monkeypatch (pytest.MonkeyPatch): Pins sys.platform to 'linux' and
                os.getuid() to a known value.
        """

        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("os.getuid", lambda: 1234)

        result = ssh_sock_dir(tmp_path, "git-sentinel")

        assert result == tmp_path / "git-sentinel-1234"

    def test_non_linux_has_no_uid_suffix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On non-Linux platforms, no UID suffix is appended since those temp
        dirs are already per-user.

        Args:
            tmp_path (Path): Stand-in temp directory.
            monkeypatch (pytest.MonkeyPatch): Pins sys.platform to a non-linux
                value.
        """

        monkeypatch.setattr("sys.platform", "darwin")

        result = ssh_sock_dir(tmp_path, "git-sentinel")

        assert result == tmp_path / "git-sentinel"
