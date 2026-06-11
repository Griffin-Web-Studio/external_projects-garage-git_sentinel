from __future__ import annotations

from src.git_ops import is_ssh_url, ssh_host_key

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
