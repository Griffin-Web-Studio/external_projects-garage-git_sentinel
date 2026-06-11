from __future__ import annotations

from pathlib import Path

import pytest

from src.git_ops import find_git_repos, is_ssh_url, ssh_host_key

# ──────────────────────────────────────────────────────────| find_git_repos |──


class TestFindGitRepos:
    """Tests find_git_repos locates all git repositories under a root
    directory."""

    def test_returns_empty_for_nonexistent_root(self, tmp_path: Path) -> None:
        """A root path that does not exist returns an empty list.

        Args:
            tmp_path (Path): Temporary directory; the target path is a
                             missing subdirectory of it.
        """
        assert find_git_repos(tmp_path / "missing") == []

    def test_returns_empty_for_root_with_no_repos(self, tmp_path: Path) -> None:
        """A directory tree with no .git subdirectories returns an empty list.

        Args:
            tmp_path (Path): Temporary directory with no git repos.
        """
        (tmp_path / "project").mkdir()

        assert find_git_repos(tmp_path) == []

    def test_finds_single_repo(self, tmp_path: Path) -> None:
        """A single .git directory is found and its parent is returned.

        Args:
            tmp_path (Path): Temporary directory containing one git repo.
        """
        repo = tmp_path / "myrepo"
        (repo / ".git").mkdir(parents=True)

        assert find_git_repos(tmp_path) == [repo]

    def test_finds_multiple_repos(self, tmp_path: Path) -> None:
        """All repositories in a flat directory are returned.

        Args:
            tmp_path (Path): Temporary directory containing multiple git repos.
        """
        for name in ("alpha", "beta", "gamma"):
            (tmp_path / name / ".git").mkdir(parents=True)

        result = find_git_repos(tmp_path)

        assert result == sorted(
            [tmp_path / n for n in ("alpha", "beta", "gamma")]
        )

    def test_finds_nested_repo(self, tmp_path: Path) -> None:
        """Repositories nested several levels deep are discovered.

        Args:
            tmp_path (Path): Temporary directory containing a deeply nested
                             repo.
        """
        nested = tmp_path / "a" / "b" / "repo"
        (nested / ".git").mkdir(parents=True)

        assert find_git_repos(tmp_path) == [nested]

    def test_results_are_sorted(self, tmp_path: Path) -> None:
        """The returned list is always in sorted path order.

        Args:
            tmp_path (Path): Temporary directory containing repos created in
                             reverse alphabetical order.
        """
        for name in ("zebra", "apple", "mango"):
            (tmp_path / name / ".git").mkdir(parents=True)

        result = find_git_repos(tmp_path)

        assert result == sorted(result)

    def test_ignores_git_files(self, tmp_path: Path) -> None:
        """A .git file (used by submodules/worktrees) is not treated as a repo
        root.

        Args:
            tmp_path (Path): Temporary directory containing a .git file rather
                             than a .git directory.
        """
        repo = tmp_path / "submodule"
        repo.mkdir()
        (repo / ".git").write_text("gitdir: ../.git/modules/submodule")

        assert find_git_repos(tmp_path) == []


# ──────────────────────────────────────────────────────────────| is_ssh_url |──


class TestIsSshUrl:
    """Tests is_ssh_url correctly classifies git remote URL transports."""

    def test_git_at_format(self) -> None:
        """SCP-style git@ URLs are identified as SSH."""
        assert is_ssh_url("git@github.com:user/repo.git") is True

    def test_ssh_scheme(self) -> None:
        """ssh:// scheme URLs are identified as SSH."""
        assert is_ssh_url("ssh://git@github.com/user/repo.git") is True

    def test_https_is_not_ssh(self) -> None:
        """https:// URLs are not SSH."""
        assert is_ssh_url("https://github.com/user/repo.git") is False

    def test_git_scheme_is_not_ssh(self) -> None:
        """git:// protocol is not SSH."""
        assert is_ssh_url("git://github.com/user/repo.git") is False

    def test_empty_string(self) -> None:
        """Empty string returns False without raising."""
        assert is_ssh_url("") is False


# ────────────────────────────────────────────────────────────| ssh_host_key |──


class TestSshHostKey:
    """Tests ssh_host_key extracts the correct connection identifier from remote
    URLs."""

    def test_git_at_standard(self) -> None:
        """Standard git@ URL returns user@host with no port."""
        assert ssh_host_key("git@github.com:user/repo.git") == "git@github.com"

    def test_ssh_scheme_no_port(self) -> None:
        """ssh:// without a port returns user@host."""
        assert (
            ssh_host_key("ssh://git@github.com/user/repo.git")
            == "git@github.com"
        )

    def test_ssh_scheme_custom_port(self) -> None:
        """Port is preserved so hosts on different ports produce distinct
        keys."""
        # port must be preserved so that host:22 and host:2222 get separate
        # ControlMaster sockets and separate approval prompts
        assert (
            ssh_host_key("ssh://git@github.com:2222/user/repo.git")
            == "git@github.com:2222"
        )

    def test_ssh_scheme_no_user_prefixes_git(self) -> None:
        """User-less ssh:// URLs are normalised to git@host."""
        # user-less ssh:// URLs are normalised to git@host
        assert (
            ssh_host_key("ssh://github.com/user/repo.git") == "git@github.com"
        )

    def test_ssh_scheme_no_user_with_port(self) -> None:
        """User-less ssh:// with port normalises to git@host:port."""
        assert (
            ssh_host_key("ssh://github.com:2222/user/repo.git")
            == "git@github.com:2222"
        )

    def test_real_world_custom_port(self) -> None:
        """A real self-hosted GitLab URL with a custom port is parsed
        correctly."""
        url = (
            "ssh://git@gws-uk-server-gitlab.node.griffin-web.services:34122/"
            "repo.git"
        )

        assert (
            ssh_host_key(url)
            == "git@gws-uk-server-gitlab.node.griffin-web.services:34122"
        )
