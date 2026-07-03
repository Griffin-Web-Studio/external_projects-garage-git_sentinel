from __future__ import annotations

import configparser
import sys
from datetime import datetime
from pathlib import Path

from src import APP_NAME, APP_VERSION
from src.config import get_export_path
from src.services.git_ops import (
    analyse_branches_and_tags,
    check_local_state,
    check_stale,
    fetch_remote_refs,
    find_git_repos,
    get_local_branches,
    get_local_tags,
    get_remotes,
    is_ssh_url,
    ssh_host_key,
)
from src.models import AppProtocol, RemoteCheck, RemoteSkipReason, RepoResult
from src.services.reports import (
    collect_issue_keys,
    format_report,
    load_previous_issue_keys,
    manage_reports,
)
from src.services.ssh import build_ssh_env, close_ssh_sockets

# ─────────────────────────────────────────────────────────────| Scan worker |──


def _gate_ssh(
    app: AppProtocol,
    rname: str,
    rurl: str,
    short: str,
    host_key: str,
    ssh_approved: set[str],
    ssh_declined: set[str],
    use_cm: bool,
) -> bool:
    """Prompt for SSH approval on first encounter; honour prior decisions.

    Mutates *ssh_approved* / *ssh_declined* so that subsequent remotes on the
    same host skip the prompt.

    Args:
        app (AppProtocol): UI front-end for log and gate calls.
        rname (str): Remote name, used only for log messages.
        rurl (str): Remote fetch URL.
        short (str): Tilde-prefixed repo path shown in the SSH prompt.
        host_key (str): Canonical host key from ssh_host_key().
        ssh_approved (set[str]): Hosts approved this session.
        ssh_declined (set[str]): Hosts declined this session.
        use_cm (bool): Whether ControlMaster is active.

    Returns:
        bool: True if the connection should proceed, False if declined.
    """

    host = host_key.split("@")[-1]

    if host_key in ssh_declined:
        app.log(
            f"  -> {rname}: skipped "
            f"(SSH to {host} was declined this session)",
            tag="warning",
        )

        return False

    if host_key in ssh_approved:
        return True

    app.log(f"  -> {rname}: SSH remote - awaiting approval for {host}src..")

    if not app.request_ssh(rurl, short):
        ssh_declined.add(host_key)
        app.log(f"  -> {rname}: skipped by user", tag="warning")

        return False

    ssh_approved.add(host_key)

    if use_cm:
        app.log(
            f"  -> {rname}: approved - FIDO key may be "
            f"prompted for {host} on first connection"
        )

    else:
        app.log(f"  -> {rname}: approved (ControlMaster disabled)")

    return True


def _check_remotes(
    app: AppProtocol,
    repo: Path,
    result: RepoResult,
    short: str,
    ssh_approved: set[str],
    ssh_declined: set[str],
    ssh_env_dict: dict[str, str] | None,
    use_cm: bool,
) -> tuple[dict[str, dict[str, str]], dict[str, set[str]]]:
    """Fetch refs from every remote and return the combined head / tag maps.

    For each remote: gates SSH connections, attempts ls-remote, offers one
    HTTP retry on failure, and appends a RemoteCheck to result.remote_checks.

    Args:
        app (AppProtocol): UI front-end for log and gate calls.
        repo (Path): Repository root passed through to fetch_remote_refs.
        result (RepoResult): Accumulator; remote_checks is mutated in-place.
        short (str): Tilde-prefixed repo path shown in gate prompts.
        ssh_approved (set[str]): Session-wide approved SSH host keys.
        ssh_declined (set[str]): Session-wide declined SSH host keys.
        ssh_env_dict (dict[str, str] | None): GIT_SSH_COMMAND env dict when
            ControlMaster is enabled, or None.
        use_cm (bool): Whether ControlMaster is active.

    Returns:
        tuple[dict[str, dict[str, str]], dict[str, set[str]]]: Mapping of
            remote name to branch-SHA dict, and remote name to tag-name set.
    """
    remote_heads_map: dict[str, dict[str, str]] = {}
    remote_tags_map: dict[str, set[str]] = {}

    for rname, rurl in result.remotes.items():
        rc_obj = RemoteCheck(name=rname, url=rurl)
        result.remote_checks.append(rc_obj)

        ssh = is_ssh_url(rurl)
        env: dict[str, str] | None = None

        if ssh:
            if not _gate_ssh(
                app,
                rname,
                rurl,
                short,
                ssh_host_key(rurl),
                ssh_approved,
                ssh_declined,
                use_cm,
            ):
                rc_obj.skip_reason = RemoteSkipReason.SSH_DECLINED
                continue

            env = ssh_env_dict

        success, heads, tags, err = fetch_remote_refs(repo, rname, env=env)

        if not success and not ssh:
            app.log(
                f"  -> {rname}: HTTP failed ({err}) - prompting for retry",
                tag="warning",
            )

            if app.request_http_retry(rurl, short, err):
                success, heads, tags, err = fetch_remote_refs(
                    repo, rname, env=env
                )

        if success:
            remote_heads_map[rname] = heads
            remote_tags_map[rname] = tags
            rc_obj.reachable = True

            app.log(
                f"  -> {rname}: "
                f"{len(heads)} branch(es), {len(tags)} tag(s) in remote"
            )

        else:
            rc_obj.skip_reason = RemoteSkipReason.FETCH_FAILED
            rc_obj.skip_error = err[:80]
            app.log(f"  -> {rname}: unreachable - {err[:80]}", tag="error")

    return remote_heads_map, remote_tags_map


def _scan_repo(
    app: AppProtocol,
    repo: Path,
    idx: int,
    total: int,
    ssh_approved: set[str],
    ssh_declined: set[str],
    ssh_env_dict: dict[str, str] | None,
    use_cm: bool,
    stale_days: int,
) -> RepoResult:
    """Run all checks for a single repository and return the result.

    Args:
        app (AppProtocol): UI front-end for log, progress, and gate calls.
        repo (Path): Repository root to scan.
        idx (int): Zero-based position in the repo list, used for progress.
        total (int): Total number of repositories being scanned.
        ssh_approved (set[str]): Session-wide approved SSH host keys.
        ssh_declined (set[str]): Session-wide declined SSH host keys.
        ssh_env_dict (dict[str, str] | None): GIT_SSH_COMMAND env dict when
            ControlMaster is enabled, or None.
        use_cm (bool): Whether ControlMaster is active.
        stale_days (int): Commit-age threshold for staleness check.

    Returns:
        RepoResult: Fully populated result for this repository.
    """

    result = RepoResult(path=repo)
    short = result.short_path()

    app.set_progress(5.0 + (idx / total) * 80.0)
    app.log(f"[{idx + 1}/{total}] {short}")

    result.remotes = get_remotes(repo)
    result.has_remote = bool(result.remotes)
    result.uncommitted, result.untracked, result.stashes = check_local_state(
        repo
    )
    result.is_stale, result.last_commit_date = check_stale(repo, stale_days)

    if not result.has_remote:
        app.log("  ! No remote configured", tag="error")
        app.log("")

        return result

    local_branches = get_local_branches(repo)
    local_tags = get_local_tags(repo)
    has_origin = "origin" in result.remotes

    remote_heads_map, remote_tags_map = _check_remotes(
        app,
        repo,
        result,
        short,
        ssh_approved,
        ssh_declined,
        ssh_env_dict,
        use_cm,
    )

    result.branch_issues, result.tag_issues = analyse_branches_and_tags(
        repo,
        local_branches,
        local_tags,
        remote_heads_map,
        remote_tags_map,
        has_origin,
    )

    parts: list[str] = []

    if result.uncommitted:
        parts.append(f"{len(result.uncommitted)} uncommitted")

    if result.untracked:
        parts.append(f"{len(result.untracked)} untracked")

    if result.stashes:
        parts.append(f"{len(result.stashes)} stash(es)")

    if result.branch_issues:
        parts.append(f"{len(result.branch_issues)} branch issue(s)")

    if result.tag_issues:
        parts.append(f"{len(result.tag_issues)} tag issue(s)")

    if parts:
        app.log(f"  !  {'; '.join(parts)}", tag="warning")

    else:
        app.log("  OK  clean")

    app.log("")

    return result


def scan(app: AppProtocol, cfg: configparser.ConfigParser) -> None:
    """Full scan pipeline. Runs in a background daemon thread.

    All UI updates go through the typed AppProtocol methods on *app*.
    Gate requests (SSH approval, HTTP retry) block this thread until the
    user responds via the GUI.

    Args:
        app (AppProtocol): UI front-end; satisfies AppProtocol structurally.
        cfg (configparser.ConfigParser): Loaded application configuration.
    """
    home = Path.home()
    git_root = home / cfg.get("paths", "git_root")

    try:
        if cfg.get("paths", "desktop_override").strip():
            app.log(
                "DEPRECATED: settings.ini uses 'desktop_override';"
                " rename it to 'export_path' to silence this warning.",
                tag="warning",
            )

    except configparser.NoOptionError, configparser.NoSectionError:
        pass

    export_path = get_export_path(cfg)
    persist_s = cfg.getint("ssh", "control_persist_seconds")

    if sys.platform == "win32":
        from src.platform.windows.scan import resolve_control_master

    else:
        from src.platform.linux.scan import resolve_control_master

    use_cm = resolve_control_master(
        cfg.getboolean("ssh", "use_control_master"), app.log
    )
    stale_days = cfg.getint("staleness", "stale_threshold_days")

    app.log(f"{APP_NAME}  v{APP_VERSION}", tag="info")
    app.log(f"Scan root     : {git_root}")
    app.log(f"Reports Path  : {export_path}")
    app.log("")

    # ── Stage 1: Discovery ────────────────────────────────────────────────────

    app.set_status("Stage 1 / 3 - Discovering repositoriessrc..")
    app.log("=== Stage 1: Repository discovery ===", tag="info")

    if not git_root.is_dir():
        app.log(
            f"ERROR: scan root '{git_root}' does not exist - nothing to do.",
            tag="error",
        )
        app.set_progress(100.0)
        app.finish(0, None)

        return

    repos = find_git_repos(git_root)
    total = len(repos)

    app.log(f"Found {total} repositor{'y' if total == 1 else 'ies'}.")
    app.log("")
    app.set_progress(5.0)

    # ── Stage 2: Per-repo local + remote checks ───────────────────────────────

    app.set_status(
        f"Stage 2 / 3 - Scanning {total} "
        f"repositor{'y' if total == 1 else 'ies'}src.."
    )
    app.log("=== Stage 2: Local and remote checks ===", tag="info")

    ssh_approved: set[str] = set()
    ssh_declined: set[str] = set()
    ssh_env_dict = build_ssh_env(persist_s) if use_cm else None

    results = [
        _scan_repo(
            app,
            repo,
            idx,
            total,
            ssh_approved,
            ssh_declined,
            ssh_env_dict,
            use_cm,
            stale_days,
        )
        for idx, repo in enumerate(repos)
    ]

    app.log("")

    # ── Stage 3: Report ───────────────────────────────────────────────────────

    app.set_status("Stage 3 / 3 - Generating reportsrc..")
    app.set_progress(90.0)
    app.log("=== Stage 3: Report ===", tag="info")

    if cfg.has_option("paths", "reports_archive"):
        app.log(
            "DEPRECATED: settings.ini uses 'reports_archive' which is no"
            " longer needed. See the deprecation notice at startup.",
            tag="warning",
        )

    prev_keys = load_previous_issue_keys(export_path)
    curr_keys = collect_issue_keys(results)
    now = datetime.now()
    any_issues = bool(curr_keys) or any(r.is_stale for r in results)
    report_path: Path | None = None

    if any_issues:
        ext = cfg.get("reports", "report_extension")
        fname = now.strftime(f"%Y%m%d-%H-%M-%S-git-status-report.{ext}")
        export_path.mkdir(parents=True, exist_ok=True)
        report_path = export_path / fname
        report_path.write_text(
            format_report(results, prev_keys, curr_keys, cfg, now),
            encoding="utf-8",
        )
        report_path.with_suffix(".issues").write_text(
            "\n".join(sorted(curr_keys)), encoding="utf-8"
        )
        app.log(f"Report written -> {report_path}")

    else:
        app.log("No issues found - no report generated.")

    if cfg.has_option("reports", "desktop_retention_days"):
        app.log(
            "DEPRECATED: settings.ini uses 'desktop_retention_days';"
            " rename it to 'retention_days' to silence this warning.",
            tag="warning",
        )
        retention = cfg.getint("reports", "desktop_retention_days")

    else:
        retention = cfg.getint("reports", "retention_days")

    manage_reports(export_path, retention)

    close_ssh_sockets()

    issue_count = len([r for r in results if r.has_issues()])
    app.log(f"Done. {issue_count}/{total} repo(s) with issues.")
    app.set_progress(100.0)
    app.finish(issue_count, report_path)
