from __future__ import annotations

from pathlib import Path

import pytest

from src.services.ssh import build_ssh_env

# ───────────────────────────────────────────────────────────| build_ssh_env |──


class TestBuildSshEnv:
    """Tests build_ssh_env's Linux-specific filesystem behaviour."""

    def test_socket_dir_mode_700(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Socket directory is created with mode 0o700 to prevent other-user
        access.

        POSIX file-mode bits aren't meaningful on Windows, so this check only
        runs on Linux even though src/services/ssh.py itself isn't
        platform-gated.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        sock_dir = tmp_path / "socks"

        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", sock_dir)
        build_ssh_env(300)

        assert sock_dir.stat().st_mode & 0o777 == 0o700
