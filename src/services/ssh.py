from __future__ import annotations

import os
import shutil
import subprocess

from src import SSH_SOCK_DIR

# ───────────────────────────────────────────────────────| SSH ControlMaster |──


def build_ssh_env(persist_seconds: int) -> dict[str, str]:
    """Return a copy of os.environ with GIT_SSH_COMMAND set for ControlMaster.

    Creates the socket directory on first call. SSH expands %-tokens in
    ControlPath at runtime so each (user, host, port) triple gets its own socket
    file. With BatchMode=no the first connection to a host may prompt for a FIDO
    key PIN; all subsequent connections reuse the socket without asking again.

    Args:
        persist_seconds (int): How long a control socket stays alive after the
                               last connection closes. Set to 0 to close
                               immediately.

    Returns:
        dict[str, str]: Modified copy of os.environ ready to pass as the `env`
                        argument to subprocess calls.
    """
    SSH_SOCK_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)

    # %r@%h:%p expands to user@host:port - one socket file per remote endpoint
    sock_tpl = str(SSH_SOCK_DIR / "%r@%h:%p")
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = (
        f"ssh -o ControlMaster=auto"
        f" -o 'ControlPath={sock_tpl}'"
        f" -o ControlPersist={persist_seconds}"
        f" -o BatchMode=no"
    )

    return env


def close_ssh_sockets() -> None:
    """Send ``-O exit`` to every open control socket and remove the directory.

    Called at end-of-scan to release all SSH connections. Errors from
    individual sockets are suppressed - a socket may already be dead or
    have timed out by the time cleanup runs.
    """
    if not SSH_SOCK_DIR.exists():
        return

    for sock in SSH_SOCK_DIR.iterdir():
        # derive the hostname from the socket filename (user@host:port)
        host = sock.name.split("@")[-1].split(":")[0]
        subprocess.run(
            ["ssh", "-o", f"ControlPath={sock}", "-O", "exit", host],
            # suppress output; errors are expected for dead sockets
            capture_output=True,
            timeout=5,
        )

    shutil.rmtree(SSH_SOCK_DIR, ignore_errors=True)
