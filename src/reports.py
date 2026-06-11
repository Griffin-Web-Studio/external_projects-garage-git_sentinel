from __future__ import annotations

import configparser
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from . import APP_NAME, APP_VERSION
from .models import (
    BranchIssue,
    BranchIssueReason,
    RemoteCheck,
    RemoteSkipReason,
    RepoResult,
)

# ─────────────────────────────────────────────────────────────────| Reports |──


def _fmt_branch_issue(bi: BranchIssue) -> str:
    """Return a single indented line describing one branch issue.

    Args:
        bi (BranchIssue): The branch issue to format.

    Returns:
        str: A four-space-indented description of the issue.
    """
    if bi.reason == BranchIssueReason.NOT_IN_ORIGIN:
        return f"    {bi.branch} → not in origin ({bi.commits} commit(s))"
    if bi.reason in (
        BranchIssueReason.AHEAD_OF_ORIGIN,
        BranchIssueReason.AHEAD_OF_REMOTE,
    ):
        return (
            f"    {bi.branch} → {bi.remote or '?'} (+{bi.ahead} unpushed "
            "commit(s))"
        )
    if bi.reason == BranchIssueReason.NOT_IN_ANY_REMOTE:
        return f"    {bi.branch} → not in any remote ({bi.commits} commit(s))"
    return f"    {bi.branch} → {bi.remote or '?'} ({bi.reason.value})"


def _fmt_skip_reason(rc: RemoteCheck) -> str:
    """Return a display string for a skipped remote check.

    Args:
        rc (RemoteCheck): A remote check whose skip_reason is not None.

    Returns:
        str: Human-readable skip reason, including the error detail for
            FETCH_FAILED entries.
    """
    reason = rc.skip_reason
    if reason is None:
        return ""
    if reason == RemoteSkipReason.FETCH_FAILED and rc.skip_error:
        return f"fetch_failed: {rc.skip_error}"
    return reason.value


def _fmt_stale_entry(r: RepoResult) -> str:
    """Return a single indented line describing a stale repository.

    Args:
        r (RepoResult): A repository result where is_stale is True.

    Returns:
        str: Two-space-indented repo path followed by last-commit information.
    """
    if r.last_commit_date:
        days = (datetime.now() - r.last_commit_date).days
        return (
            f"  {r.short_path()}"
            f"  (last commit: {r.last_commit_date.strftime('%Y-%m-%d')}"
            f", {days} day(s) ago)"
        )
    return f"  {r.short_path()}  (no commits found)"


def collect_issue_keys(results: list[RepoResult]) -> set[str]:
    """Build a flat set of canonical key strings for persistence comparison.

    Keys are used to detect which issues are new versus persistent across
    successive runs. The key format is pipe-separated and includes the repo
    path, issue type, and any distinguishing detail.

    Args:
        results (list[RepoResult]): Scan results from all repositories.

    Returns:
        set[str]: Canonical issue keys for this run.
    """
    keys: set[str] = set()
    for r in results:
        sp = r.short_path()
        if not r.has_remote:
            keys.add(f"{sp}|no_remote")
        keys.update(f"{sp}|uncommitted|{f}" for f in r.uncommitted)
        keys.update(f"{sp}|untracked|{f}" for f in r.untracked)
        keys.update(f"{sp}|stash|{s}" for s in r.stashes)
        keys.update(
            f"{sp}|branch|{bi.branch}|{bi.remote or 'none'}|{bi.reason.value}"
            for bi in r.branch_issues
        )
        keys.update(f"{sp}|tag|{ti.tag}|{ti.remote}" for ti in r.tag_issues)
    return keys


def load_previous_issue_keys(desktop: Path, archive: Path) -> set[str]:
    """Return issue keys from the most recent previous report, if any.

    Searches the desktop first, then the archive, taking the
    lexicographically latest .issues sidecar file.

    Args:
        desktop (Path): Desktop directory where live reports are written.
        archive (Path): Archive directory where old reports are moved.

    Returns:
        set[str]: Issue keys from the previous run, or an empty set if no
            prior report exists or the file cannot be read.
    """
    candidates = [
        *sorted(desktop.glob("*-git-status-report.issues"), reverse=True),
        *sorted(archive.glob("*-git-status-report.issues"), reverse=True),
    ]
    if not candidates:
        return set()
    try:
        return set(candidates[0].read_text().splitlines())
    except OSError:
        return set()


def format_report(
    results: list[RepoResult],
    prev_keys: set[str],
    curr_keys: set[str],
    cfg: configparser.ConfigParser,
    now: datetime,
) -> str:
    """Render the full scan report as a multi-section INI-style string.

    Sections are emitted only when the corresponding data is non-empty.
    Issue keys from the previous run are compared to classify findings as
    persistent or new.

    Args:
        results (list[RepoResult]): Scan results for all repositories.
        prev_keys (set[str]): Issue keys loaded from the previous report.
        curr_keys (set[str]): Issue keys collected from this run.
        cfg (configparser.ConfigParser): Loaded configuration (provides
            stale_threshold_days).
        now (datetime): Timestamp used for report header and stale age.

    Returns:
        str: The complete report text ready to write to a .log file.
    """
    stale_days = cfg.getint("staleness", "stale_threshold_days")
    issues_list = [r for r in results if r.has_issues()]
    stale_list = [r for r in results if r.is_stale]
    passed_list = [r for r in results if not r.has_issues() and not r.is_stale]
    persistent = prev_keys & curr_keys
    new_issues = curr_keys - prev_keys

    L: list[str] = []
    sec: Callable[[str], None] = lambda s: L.append(f"[{s}]")  # noqa: E731
    blank: Callable[[], None] = lambda: L.append("")  # noqa: E731

    sec("report")
    L += [
        f"date              = {now.strftime('%Y-%m-%d')}",
        f"time              = {now.strftime('%H:%M:%S')}",
        f"generated_by      = {APP_NAME} v{APP_VERSION}",
        f"total_repos       = {len(results)}",
        f"repos_with_issues = {len(issues_list)}",
        f"repos_passed      = {len(passed_list)}",
        f"stale_repos       = {len(stale_list)}",
    ]
    blank()

    if persistent:
        sec("persistent_issues")
        L.append("; Issues from the previous report still unresolved today")
        L.extend(f"  {k}" for k in sorted(persistent))
        blank()

    if new_issues:
        sec("new_issues")
        L.append("; Issues not present in the previous report")
        L.extend(f"  {k}" for k in sorted(new_issues))
        blank()

    no_remote = [r for r in results if not r.has_remote]
    if no_remote:
        sec("no_remote")
        L.append(
            "; Repositories with no remote URL"
            " — work cannot be backed up remotely"
        )
        L.extend(f"  {r.short_path()}" for r in no_remote)
        blank()

    uncommitted_repos = [r for r in results if r.uncommitted]
    if uncommitted_repos:
        sec("uncommitted")
        L.append("; Staged or modified tracked files not yet committed")
        L.extend(
            line
            for r in uncommitted_repos
            for line in (
                f"  {r.short_path()}",
                *(f"    {f}" for f in r.uncommitted),
            )
        )
        blank()

    untracked_repos = [r for r in results if r.untracked]
    if untracked_repos:
        sec("untracked")
        L.append("; Non-ignored files not yet added and committed")
        L.extend(
            line
            for r in untracked_repos
            for line in (
                f"  {r.short_path()}",
                *(f"    {f}" for f in r.untracked),
            )
        )
        blank()

    stash_repos = [r for r in results if r.stashes]
    if stash_repos:
        sec("stashes")
        L.extend(
            line
            for r in stash_repos
            for line in (
                f"  {r.short_path()}",
                *(f"    {s}" for s in r.stashes),
            )
        )
        blank()

    branch_repos = [r for r in results if r.branch_issues]
    if branch_repos:
        sec("unpushed_branches")
        L.extend(
            line
            for r in branch_repos
            for line in (
                f"  {r.short_path()}",
                *map(_fmt_branch_issue, r.branch_issues),
            )
        )
        blank()

    tag_repos = [r for r in results if r.tag_issues]
    if tag_repos:
        sec("unpushed_tags")
        L.extend(
            line
            for r in tag_repos
            for line in (
                f"  {r.short_path()}",
                *(
                    f"    {ti.tag} → {ti.remote} (not in remote)"
                    for ti in r.tag_issues
                ),
            )
        )
        blank()

    skipped = [
        (r, rc) for r in results for rc in r.remote_checks if rc.skip_reason
    ]
    if skipped:
        sec("remote_checks_skipped")
        L.append(
            "; Remote checks skipped"
            " — results may be incomplete for these repos"
        )
        L.extend(
            f"  {r.short_path()} → {rc.name}: {_fmt_skip_reason(rc)}"
            for r, rc in skipped
        )
        blank()

    if stale_list:
        sec("stale")
        L.append(
            f"; Repositories with no commits in the last {stale_days} day(s)"
        )
        L.extend(_fmt_stale_entry(r) for r in stale_list)
        blank()

    if passed_list:
        sec("passed")
        L.append("; Repositories with no issues detected this run")
        L.extend(f"  {r.short_path()}" for r in passed_list)
        blank()

    return "\n".join(L)


def manage_reports(
    desktop: Path,
    archive: Path,
    retention: int,
    clean_run: bool,
) -> None:
    """Move old report files between the desktop and the archive directory.

    On a clean run (no issues), all live reports on the desktop are moved
    to the archive. Otherwise, only reports beyond the retention window are
    moved, keeping the most recent *retention* reports on the desktop.

    Args:
        desktop (Path): Desktop directory where live reports are written.
        archive (Path): Archive directory; created if it does not exist.
        retention (int): Maximum number of report files to keep on the
            desktop. Older ones are moved to the archive.
        clean_run (bool): True if no issues were found this run.
    """
    archive.mkdir(parents=True, exist_ok=True)

    def _move(src: Path) -> None:
        shutil.move(str(src), archive / src.name)
        sidecar = src.with_suffix(".issues")
        if sidecar.exists():
            shutil.move(str(sidecar), archive / sidecar.name)

    if clean_run:
        for f in desktop.glob("*-git-status-report.log"):
            _move(f)
        return

    for old in sorted(desktop.glob("*-git-status-report.log"), reverse=True)[
        retention:
    ]:
        _move(old)
