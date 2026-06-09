from __future__ import annotations

# ──────────────────────────────────────────────────────────| SSH URL helpers |──


def is_ssh_url(url: str) -> bool:
    """Return True if the remote URL uses the SSH transport.

    Args:
        url (str): Git remote fetch URL.

    Returns:
        bool: True for git@ and ssh:// URLs, False for everything else.
    """
    return url.startswith(("git@", "ssh://"))


def ssh_host_key(url: str) -> str:
    """Extract the connection key from an SSH git remote URL.

    Used to key the per-host approve/decline sets so that all remotes on the
    same host share a single ControlMaster socket and a single prompt.
    When a custom port is present it is included in the key so that the same
    host on different ports gets a separate socket and a separate prompt.

    Args:
        url (str): SSH remote fetch URL in either git@ or ssh:// form.

    Returns:
        str: 'user@host' for default-port remotes, 'user@host:port' when the URL
             specifies a custom port. For example:
             'git@github.com', or 'git@gitlab.example.com:2222'.
    """
    if url.startswith("ssh://"):
        body = url[6:]  # discard protocol from string
        user_host = body.split("/")[0]  # get possible user with host

        return user_host if "@" in user_host else f"git@{user_host}"

    return url.split(":")[0]  # git@host:path/repo.git -> git@host
