from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import TypedDict

import git

from .models import BranchIssue, BranchIssueReason, TagIssue

# ──────────────────────────────────────────────────────────| Repo discovery |──


def find_git_repos(root: Path) -> list[Path]:
    """Return all git repository roots found recursively under *root*.

    Traverses the directory tree looking for `.git` directories and returns
    the parent of each one. The result is sorted so callers get a stable,
    predictable order regardless of filesystem traversal order.

    Args:
        root (Path): Directory to search. Returns an empty list if the path
            does not exist or is not a directory.

    Returns:
        list[Path]: Sorted list of repository root paths.
    """
    if not root.is_dir():
        return []

    return sorted(p.parent for p in root.rglob(".git") if p.is_dir())


# ─────────────────────────────────────────────────────────| SSH URL helpers |──


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
        str: 'user@host' for default-port remotes, 'user@host:port' when the
             URL specifies a custom port. For example:
             'git@github.com', or 'git@gitlab.example.com:2222'.
    """
    if url.startswith("ssh://"):
        body = url[6:]  # discard protocol from string
        user_host = body.split("/")[0]  # get possible user with host

        return user_host if "@" in user_host else f"git@{user_host}"

    return url.split(":")[0]  # git@host:path/repo.git -> git@host


# ───────────────────────────────────────────────────| Local repo inspection |──


class BranchInfo(TypedDict):
    """Fields needed to identify and compare a local branch against its remote.

    Attributes:
        name: Local branch name.
        sha: Full 40-character commit SHA at the branch tip.
        upstream: Configured tracking branch name, or empty string if none.
        ahead: Reserved; fine-grained ahead count is computed later by
            analyse_branches_and_tags as needed.
    """

    name: str
    sha: str
    upstream: str
    ahead: int


def get_remotes(repo: Path) -> dict[str, str]:
    """Return a mapping of remote name to fetch URL for a repository.

    Args:
        repo (Path): Repository root directory.

    Returns:
        dict[str, str]: Mapping of remote name to fetch URL, e.g.
            {'origin': 'git@github.com:user/repo.git'}. Empty dict if the
            path is not a valid git repository.
    """
    try:
        r = git.Repo(repo)
        return {remote.name: remote.url for remote in r.remotes}
    except git.InvalidGitRepositoryError, git.NoSuchPathError:
        return {}


def check_local_state(repo: Path) -> tuple[list[str], list[str], list[str]]:
    """Return (uncommitted, untracked, stashes) for a repository.

    Uses GitPython's subprocess layer for status and stash output so that
    non-ASCII file names are decoded correctly by git's own encoding logic.

    Args:
        repo (Path): Repository root directory.

    Returns:
        tuple[list[str], list[str], list[str]]: Three lists of human-readable
            strings: staged/modified tracked files, untracked file paths, and
            stash entries.
    """
    try:
        r = git.Repo(repo)
    except git.InvalidGitRepositoryError, git.NoSuchPathError:
        return [], [], []

    uncommitted: list[str] = []
    untracked: list[str] = []

    status = r.git.status("--porcelain")
    for line in (status.splitlines() if status else []):
        xy = line[:2]
        path = line[3:].strip()
        if xy == "??":
            untracked.append(path)
        elif xy.strip():
            uncommitted.append(f"{xy}  {path}")

    try:
        stash_text = r.git.stash("list")
        stashes = stash_text.splitlines() if stash_text else []
    except git.GitCommandError:
        stashes = []

    return uncommitted, untracked, stashes


def check_stale(
    repo: Path, threshold_days: int
) -> tuple[bool, datetime | None]:
    """Return whether the most recent commit across all branches is old.

    Args:
        repo (Path): Repository root directory.
        threshold_days (int): Number of days after which a repo is stale.

    Returns:
        tuple[bool, datetime | None]: (is_stale, last_commit_datetime).
            last_commit_datetime is None if the repository has no commits.
    """
    try:
        r = git.Repo(repo)
        out = r.git.log("--all", "--format=%ct", "-1")
        if not out:
            return False, None
        last = datetime.fromtimestamp(int(out.strip()))
        return (datetime.now() - last).days >= threshold_days, last
    except (
        git.InvalidGitRepositoryError,
        git.NoSuchPathError,
        git.GitCommandError,
        ValueError,
        OSError,
    ):
        return False, None


def get_local_branches(repo: Path) -> list[BranchInfo]:
    """Return metadata for all local branches.

    Args:
        repo (Path): Repository root directory.

    Returns:
        list[BranchInfo]: One entry per local branch with name, full SHA,
            tracking branch name, and a zero ahead placeholder.
    """
    try:
        r = git.Repo(repo)
    except git.InvalidGitRepositoryError, git.NoSuchPathError:
        return []

    branches: list[BranchInfo] = []
    for head in r.heads:
        tracking = head.tracking_branch()
        branches.append(
            {
                "name": head.name,
                "sha": head.commit.hexsha,
                "upstream": tracking.name if tracking else "",
                "ahead": 0,
            }
        )
    return branches


def get_local_tags(repo: Path) -> list[str]:
    """Return all local tag names for a repository.

    Args:
        repo (Path): Repository root directory.

    Returns:
        list[str]: Tag names. Empty list if the path is not a valid
            git repository or no tags exist.
    """
    try:
        r = git.Repo(repo)
        return [tag.name for tag in r.tags]
    except git.InvalidGitRepositoryError, git.NoSuchPathError:
        return []


def _count_commits(repo: Path, spec: str) -> int:
    """Count commits reachable by *spec* (a branch name or a range like a..b).

    Args:
        repo (Path): Repository root directory.
        spec (str): Rev-spec passed to git rev-list --count.

    Returns:
        int: Number of matching commits, or 0 on any error.
    """
    try:
        r = git.Repo(repo)
        out = r.git.rev_list("--count", spec)
        return max(0, int(out.strip()))
    except (
        git.InvalidGitRepositoryError,
        git.NoSuchPathError,
        git.GitCommandError,
        ValueError,
    ):
        return 0


# ─────────────────────────────────────────────| Remote inspection (network) |──


def _run_git(
    repo: Path,
    *args: str,
    env: dict[str, str] | None = None,
    timeout: int = 30,
) -> tuple[int, str, str]:
    """Run a git command in *repo* and return (returncode, stdout, stderr).

    Raw subprocess call kept here so the SSH env dict (ControlMaster socket
    path) can be injected for ls-remote without affecting the GitPython
    Repo object used for local operations.

    Args:
        repo (Path): Repository root passed as -C argument.
        *args (str): Git sub-command and its arguments.
        env (dict[str, str] | None): Full environment dict, or None to
            inherit the current process environment.
        timeout (int): Maximum seconds to wait before treating as failure.

    Returns:
        tuple[int, str, str]: (returncode, stdout stripped, stderr stripped).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "timed out"
    except Exception as exc:
        return 1, "", str(exc)


def fetch_remote_refs(
    repo: Path,
    remote: str,
    env: dict[str, str] | None = None,
) -> tuple[bool, dict[str, str], set[str], str]:
    """Call git ls-remote --heads --tags for *remote*.

    Kept as a subprocess call (not GitPython Repo.remote.fetch) so that
    the SSH ControlMaster env dict can be passed through, and because
    ls-remote is read-only - it does not write to the local repository.

    Args:
        repo (Path): Repository root directory.
        remote (str): Remote name (e.g. 'origin') or URL.
        env (dict[str, str] | None): Environment dict for the subprocess,
            typically containing GIT_SSH_COMMAND for ControlMaster.

    Returns:
        tuple[bool, dict[str, str], set[str], str]:
            (success, {branch: sha}, {tag_name}, error_str).
    """
    rc, out, err = _run_git(
        repo,
        "ls-remote",
        "--heads",
        "--tags",
        remote,
        env=env,
        timeout=30,
    )
    if rc != 0:
        return False, {}, set(), err

    heads: dict[str, str] = {}
    tags: set[str] = set()
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        sha, ref = parts
        if ref.startswith("refs/heads/"):
            heads[ref[11:]] = sha
        elif ref.startswith("refs/tags/") and not ref.endswith("^{}"):
            tags.add(ref[10:])

    return True, heads, tags, ""


# ───────────────────────────────────────────────────| Branch / tag analysis |──


def _check_branch_against_origin(
    repo: Path,
    name: str,
    sha: str,
    origin_heads: dict[str, str],
) -> BranchIssue | None:
    """Check one branch against origin when an origin remote is configured.

    Args:
        repo (Path): Repository root, used for commit counting.
        name (str): Local branch name.
        sha (str): Full commit SHA at the local branch tip.
        origin_heads (dict[str, str]): Branch-to-SHA map fetched from origin.

    Returns:
        BranchIssue | None: An issue if the branch is absent from or ahead of
            origin, otherwise None.
    """
    if name not in origin_heads:
        n = _count_commits(repo, name)
        if n > 0:
            return BranchIssue(
                branch=name,
                remote="origin",
                commits=n,
                reason=BranchIssueReason.NOT_IN_ORIGIN,
            )
    elif sha != origin_heads[name]:
        ahead = _count_commits(repo, f"{origin_heads[name]}..{sha}")
        if ahead > 0:
            return BranchIssue(
                branch=name,
                remote="origin",
                ahead=ahead,
                reason=BranchIssueReason.AHEAD_OF_ORIGIN,
            )
    return None


def _check_branch_against_remotes(
    repo: Path,
    name: str,
    sha: str,
    remote_heads_map: dict[str, dict[str, str]],
) -> BranchIssue | None:
    """Check one branch against all remotes when no origin is configured.

    Args:
        repo (Path): Repository root, used for commit counting.
        name (str): Local branch name.
        sha (str): Full commit SHA at the local branch tip.
        remote_heads_map (dict[str, dict[str, str]]): All fetched remote heads.

    Returns:
        BranchIssue | None: An issue if the branch is absent from or ahead of
            every remote, otherwise None.
    """
    present_in = {rname for rname, h in remote_heads_map.items() if name in h}

    if not present_in:
        n = _count_commits(repo, name)
        if n > 0:
            return BranchIssue(
                branch=name,
                remote=None,
                commits=n,
                reason=BranchIssueReason.NOT_IN_ANY_REMOTE,
            )
        return None

    for rname in present_in:
        if sha != remote_heads_map[rname][name]:
            ahead = _count_commits(
                repo, f"{remote_heads_map[rname][name]}..{sha}"
            )
            if ahead > 0:
                return BranchIssue(
                    branch=name,
                    remote=rname,
                    ahead=ahead,
                    reason=BranchIssueReason.AHEAD_OF_REMOTE,
                )
    return None


def _check_tags(
    local_tags: list[str],
    remote_tags_map: dict[str, set[str]],
    has_origin: bool,
) -> list[TagIssue]:
    """Return tag issues for all local tags not present in the expected remote.

    Args:
        local_tags (list[str]): Output of get_local_tags.
        remote_tags_map (dict[str, set[str]]): All fetched remote tag sets.
        has_origin (bool): True when a remote named 'origin' is configured.

    Returns:
        list[TagIssue]: Tags absent from origin (or all remotes when no
            origin is configured).
    """
    all_remote_tags = (
        set().union(*remote_tags_map.values()) if remote_tags_map else set()
    )
    origin_tags = remote_tags_map.get("origin", set())
    first_remote = next(iter(remote_tags_map), "unknown")

    issues: list[TagIssue] = []
    for tag in local_tags:
        if has_origin:
            if tag not in origin_tags:
                issues.append(TagIssue(tag=tag, remote="origin"))
        elif tag not in all_remote_tags:
            issues.append(TagIssue(tag=tag, remote=first_remote))
    return issues


def analyse_branches_and_tags(
    repo: Path,
    local_branches: list[BranchInfo],
    local_tags: list[str],
    remote_heads_map: dict[str, dict[str, str]],
    remote_tags_map: dict[str, set[str]],
    has_origin: bool,
) -> tuple[list[BranchIssue], list[TagIssue]]:
    """Determine which local branches and tags are not safely backed up.

    Fork rule: work present in 'origin' is considered safe regardless of
    whether it has been merged into an upstream remote.

    Args:
        repo (Path): Repository root, used for commit counting.
        local_branches (list[BranchInfo]): Output of get_local_branches.
        local_tags (list[str]): Output of get_local_tags.
        remote_heads_map (dict[str, dict[str, str]]): Mapping of remote name
            to {branch_name: sha} from fetch_remote_refs.
        remote_tags_map (dict[str, set[str]]): Mapping of remote name to
            {tag_name} from fetch_remote_refs.
        has_origin (bool): True when a remote named 'origin' is configured.

    Returns:
        tuple[list[BranchIssue], list[TagIssue]]: Issues found.
    """
    origin_heads = remote_heads_map.get("origin", {})
    branch_issues: list[BranchIssue] = []

    for b in local_branches:
        name, sha = b["name"], b["sha"]
        if has_origin:
            issue = _check_branch_against_origin(repo, name, sha, origin_heads)
        else:
            issue = _check_branch_against_remotes(
                repo, name, sha, remote_heads_map
            )
        if issue:
            branch_issues.append(issue)

    return branch_issues, _check_tags(local_tags, remote_tags_map, has_origin)
