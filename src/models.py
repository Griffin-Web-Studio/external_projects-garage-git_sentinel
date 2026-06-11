from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import NamedTuple, Protocol

# ───────────────────────────────────────────────────────────| Domain models |──


class BranchIssueReason(Enum):
    """Classifies why a local branch is considered at risk.

    Used by BranchIssue.reason to distinguish between the four scenarios
    the branch analyser can detect.
    """

    # Branch absent from origin; local commits present
    NOT_IN_ORIGIN = "not_in_origin"
    # Local branch is ahead of origin/branch
    AHEAD_OF_ORIGIN = "ahead_of_origin"
    # No origin configured; branch absent from all remotes
    NOT_IN_ANY_REMOTE = "not_in_any_remote"
    # No origin configured; local is ahead of some other remote
    AHEAD_OF_REMOTE = "ahead_of_remote"


class TagIssueReason(Enum):
    """Classifies why a local tag is considered at risk."""

    NOT_IN_REMOTE = "not_in_remote"


class RemoteSkipReason(Enum):
    """Classifies why a remote reachability check was skipped.

    Used by RemoteCheck.skip_reason to distinguish between categorical
    skip causes. Kept separate from any error detail, which is carried
    in RemoteCheck.skip_error.
    """

    # User declined the SSH connection prompt for this host
    SSH_DECLINED = "ssh_declined"
    # ls-remote failed; see RemoteCheck.skip_error for the error detail
    FETCH_FAILED = "fetch_failed"


@dataclass
class RemoteCheck:
    """Result of a single remote reachability check for one repository.

    Attributes:
        name: Remote name as returned by git (e.g. 'origin', 'upstream').
        url: Fetch URL of the remote.
        reachable: True if ls-remote succeeded.
        skip_reason: Categorical reason the check was skipped, or None if
            the check was not skipped; see RemoteSkipReason.
        skip_error: Raw error string from a failed fetch. Only populated
            when skip_reason is RemoteSkipReason.FETCH_FAILED.
    """

    name: str
    url: str
    reachable: bool = False
    skip_reason: RemoteSkipReason | None = None
    skip_error: str = ""


@dataclass
class BranchIssue:
    """Describes a local branch that is not safely backed up remotely.

    Attributes:
        branch: Local branch name.
        remote: Remote the branch was measured against, or None when no
            origin is configured and the issue spans all remotes.
        reason: Categorised cause; see BranchIssueReason.
        ahead: Number of commits the local branch is ahead of the remote.
        commits: Total local commits when the branch is entirely absent
            from the remote.
    """

    branch: str
    remote: str | None
    reason: BranchIssueReason
    ahead: int = 0
    commits: int = 0


@dataclass
class TagIssue:
    """Describes a local tag that is absent from a remote.

    Attributes:
        tag: Local tag name.
        remote: Remote the tag was measured against.
        reason: Categorised cause; see TagIssueReason.
    """

    tag: str
    remote: str
    reason: TagIssueReason = TagIssueReason.NOT_IN_REMOTE


@dataclass
class RepoResult:
    """Aggregated scan result for a single git repository.

    Attributes:
        path: Absolute path to the repository root.
        has_remote: True if at least one remote is configured.
        remotes: Mapping of remote name to fetch URL.
        uncommitted: Porcelain status lines for staged/modified tracked
            files.
        untracked: Paths of non-ignored untracked files.
        stashes: Lines from git stash list.
        branch_issues: Branches not safely backed up; see BranchIssue.
        tag_issues: Tags absent from their expected remote; see TagIssue.
        remote_checks: Per-remote reachability results; see RemoteCheck.
        is_stale: True if the last commit across all branches exceeds the
            configured stale threshold.
        last_commit_date: Timestamp of the most recent commit, or None if
            the repository has no commits.
    """

    path: Path
    has_remote: bool = False
    remotes: dict[str, str] = field(default_factory=dict)
    uncommitted: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    stashes: list[str] = field(default_factory=list)
    branch_issues: list[BranchIssue] = field(default_factory=list)
    tag_issues: list[TagIssue] = field(default_factory=list)
    remote_checks: list[RemoteCheck] = field(default_factory=list)
    is_stale: bool = False
    last_commit_date: datetime | None = None

    def has_issues(self) -> bool:
        """Return True if the repository has any actionable issues.

        Returns:
            bool: True if any of uncommitted changes, untracked files,
                stashes, branch issues, tag issues, or missing remote
                are present.
        """
        return bool(
            not self.has_remote
            or self.uncommitted
            or self.untracked
            or self.stashes
            or self.branch_issues
            or self.tag_issues
        )

    def short_path(self) -> str:
        """Return the repository path with the home directory replaced by ~.

        Returns:
            str: Tilde-prefixed relative path, or the absolute path if the
                repository is outside the home directory.
        """
        try:
            return "~/" + str(self.path.relative_to(Path.home()))
        except ValueError:
            return str(self.path)


# ────────────────────────────────────────────────────────| UI message types |──


class MsgLog(NamedTuple):
    """Appends a line of text to the scrollable log pane.

    Attributes:
        text: Line to append; a newline is added automatically.
    """

    text: str


class MsgStatus(NamedTuple):
    """Updates the bold status label at the top of the window.

    Attributes:
        text: New status string to display.
    """

    text: str


class MsgProgress(NamedTuple):
    """Sets the progress bar to a specific percentage.

    Attributes:
        pct: Value between 0.0 and 100.0.
    """

    pct: float


class MsgFinish(NamedTuple):
    """Signals that the scan worker has completed.

    Attributes:
        issue_count: Number of repositories with at least one issue.
        report_path: Path to the written report file, or None if the
            run was clean and no report was generated.
    """

    issue_count: int
    report_path: Path | None


# ───────────────────────────────────────────────────────────────────| Gates |──


@dataclass
class Gate:
    """Base class for blocking worker-to-UI requests.

    The worker puts a Gate subclass on the gate queue then calls
    event.wait(), blocking until the UI resolves the request and
    calls event.set().

    Attributes:
        url: Remote URL that triggered this gate.
        repo: Short display path of the repository being scanned.
        event: Synchronisation primitive; set by the UI when the user
            responds. Not included in __init__ or repr.
    """

    url: str
    repo: str
    event: threading.Event = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.event = threading.Event()


@dataclass
class GateSSH(Gate):
    """Gate raised when a repository has an SSH remote awaiting approval.

    Attributes:
        approved: Set to True by the UI if the user approves the
            connection; False if skipped.
    """

    approved: bool = False


@dataclass
class GateHTTP(Gate):
    """Gate raised when an HTTP remote fetch fails and a retry is offered.

    Attributes:
        error: Error string from the failed fetch, shown to the user.
            Always set at construction time; never empty.
        retry: Set to True by the UI if the user requests a retry.
    """

    error: str
    retry: bool = False


# ────────────────────────────────────────────────────────────| App protocol |──


class AppProtocol(Protocol):
    """Interface the scan worker depends on.

    GitSentinelApp satisfies this structurally - no explicit declaration needed.
    A future TUIApp would implement the same six methods to run the scan in a
    terminal environment without touching scan.py.
    """

    def log(self, text: str) -> None:
        """Append a line to the output log.

        Args:
            text (str): Log text
        """
        ...

    def set_status(self, text: str) -> None:
        """Update the top-level status indicator.

        Args:
            text (str): Status text
        """
        ...

    def set_progress(self, pct: float) -> None:
        """Set progress to *pct* (0.0-100.0).

        Args:
            pct (float): Progress percentage
        """
        ...

    def finish(self, issue_count: int, report_path: Path | None) -> None:
        """Signal that the scan has completed.

        Args:
            issue_count (int): Number of issues
            report_path (Path | None): Path to a report
        """
        ...

    def request_ssh(self, url: str, repo_short: str) -> bool:
        """Block until the user approves or declines an SSH connection.

        Args:
            url (str): Repo SSH URL
            repo_short (str): A short name for repo

        Returns:
            bool: True if approved, False if declined.
        """
        ...

    def request_http_retry(self, url: str, repo_short: str, error: str) -> bool:
        """Block until the user chooses to retry or skip a failed HTTP remote.

        Args:
            url (str): Repo HTTP URL
            repo_short (str): A short name for repo
            error (str): Connection error text

        Returns:
            bool: True if the user requested a retry, False to skip.
        """
        ...
