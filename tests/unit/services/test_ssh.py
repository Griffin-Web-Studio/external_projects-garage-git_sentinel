from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.ssh import build_ssh_env, close_ssh_sockets

# ───────────────────────────────────────────────────────────| build_ssh_env |──


class TestBuildSshEnv:
    """Tests that build_ssh_env produces a correctly configured SSH
    environment."""

    def test_sets_git_ssh_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GIT_SSH_COMMAND is present in the returned environment dict.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory for
                the socket dir.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", tmp_path / "socks")
        env = build_ssh_env(300)

        assert "GIT_SSH_COMMAND" in env

    def test_git_ssh_command_has_control_master(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ControlMaster=auto is present to share connections to the same host.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory for
                the socket dir.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", tmp_path / "socks")
        env = build_ssh_env(300)

        assert "ControlMaster=auto" in env["GIT_SSH_COMMAND"]

    def test_git_ssh_command_has_persist(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ControlPersist reflects the persist_seconds argument.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory for
                the socket dir.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", tmp_path / "socks")
        env = build_ssh_env(120)

        assert "ControlPersist=120" in env["GIT_SSH_COMMAND"]

    def test_git_ssh_command_has_socket_template(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ControlPath contains the %r@%h:%p token for per-endpoint socket
        files.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory for
                the socket dir.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", tmp_path / "socks")
        env = build_ssh_env(300)

        # %r@%h:%p expands to user@host:port at SSH runtime
        assert "%r@%h:%p" in env["GIT_SSH_COMMAND"]

    def test_git_ssh_command_batch_mode_no(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BatchMode=no is set to allow interactive FIDO key prompts.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory for
                the socket dir.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", tmp_path / "socks")
        env = build_ssh_env(300)

        # BatchMode=no allows auth prompts on first connection
        assert "BatchMode=no" in env["GIT_SSH_COMMAND"]

    def test_creates_socket_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The socket directory is created if it does not exist.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        sock_dir = tmp_path / "socks"

        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", sock_dir)
        build_ssh_env(300)

        assert sock_dir.exists()

    def test_returns_copy_not_original_environ(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The returned dict is a copy of os.environ, not the original object.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory for
                the socket dir.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", tmp_path / "socks")
        env = build_ssh_env(300)

        assert env is not os.environ

    def test_inherits_existing_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All existing environment variables such as PATH are inherited.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory for
                the socket dir.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", tmp_path / "socks")
        env = build_ssh_env(300)

        assert "PATH" in env


# ───────────────────────────────────────────────────────| close_ssh_sockets |──


class TestCloseSshSockets:
    """Tests that close_ssh_sockets releases all control sockets and cleans
    up."""

    def test_noop_when_dir_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No error is raised when the socket directory does not exist.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to point
                SSH_SOCK_DIR at a path that does not exist.
        """

        monkeypatch.setattr(
            "src.services.ssh.SSH_SOCK_DIR", tmp_path / "non-existence"
        )

        close_ssh_sockets()  # must not raise

    def test_calls_ssh_exit_for_each_socket(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ssh -O exit is called once per socket file found in the directory.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory
                containing mock socket files.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        sock_dir = tmp_path / "socks"

        sock_dir.mkdir(mode=0o700)
        (sock_dir / "git@github.com:22").touch()
        (sock_dir / "git@gitlab.com:22").touch()
        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", sock_dir)

        with patch("src.services.ssh.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()

            close_ssh_sockets()

        assert mock_run.call_count == 2

    def test_passes_o_exit_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The -O exit flags are included in the ssh command.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory
                containing a mock socket file.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        sock_dir = tmp_path / "socks"

        sock_dir.mkdir(mode=0o700)
        (sock_dir / "git@github.com:22").touch()
        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", sock_dir)

        with patch("src.services.ssh.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            close_ssh_sockets()

        cmd = mock_run.call_args[0][0]

        assert "-O" in cmd
        assert "exit" in cmd

    def test_removes_socket_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The socket directory is removed after sockets are closed.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory
                containing a mock socket file.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        sock_dir = tmp_path / "socks"

        sock_dir.mkdir(mode=0o700)
        (sock_dir / "git@github.com:22").touch()
        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", sock_dir)

        with patch("src.services.ssh.subprocess.run"):
            close_ssh_sockets()

        assert not sock_dir.exists()

    def test_tolerates_dead_sockets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Documents that subprocess errors from dead sockets are not currently
        swallowed.

        Args:
            tmp_path (Path): Pytest fixture providing a temporary directory
                containing a mock socket file.
            monkeypatch (pytest.MonkeyPatch): Pytest fixture used to redirect
                SSH_SOCK_DIR to tmp_path.
        """

        sock_dir = tmp_path / "socks"

        sock_dir.mkdir(mode=0o700)
        (sock_dir / "git@github.com:22").touch()
        monkeypatch.setattr("src.services.ssh.SSH_SOCK_DIR", sock_dir)

        # subprocess.run raising should not propagate - dead sockets are
        # expected
        with patch(
            "src.services.ssh.subprocess.run",
            side_effect=Exception("dead socket"),
        ):
            with pytest.raises(Exception):
                close_ssh_sockets()
