from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import git
import pytest

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
from src.models import BranchIssueReason, TagIssueReason

# ────────────────────────────────────────────────────────────────| Fixtures |──


@pytest.fixture
def repo(tmp_path: Path) -> git.Repo:
    """A git repository with one commit, ready for local-inspection tests."""
    r = git.Repo.init(tmp_path / "repo")
    with r.config_writer() as cfg:
        cfg.set_value("user", "name", "Test User")
        cfg.set_value("user", "email", "test@example.com")
    p = Path(r.working_dir)
    (p / "file.txt").write_text("hello")
    r.index.add(["file.txt"])
    r.index.commit("initial commit")
    return r


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


# ─────────────────────────────────────────────────────────────| get_remotes |──


class TestGetRemotes:
    """Tests get_remotes returns the correct remote name → URL mapping."""

    def test_no_remotes_returns_empty(self, repo: git.Repo) -> None:
        """A freshly initialised repo with no remotes returns an empty dict.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        assert get_remotes(Path(repo.working_dir)) == {}

    def test_returns_remote_url(self, repo: git.Repo) -> None:
        """A configured remote is returned with the correct name and URL.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        url = "https://github.com/test/repo.git"
        repo.create_remote("origin", url)

        assert get_remotes(Path(repo.working_dir)) == {"origin": url}

    def test_returns_multiple_remotes(self, repo: git.Repo) -> None:
        """All configured remotes are returned when more than one exists.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        repo.create_remote("origin", "https://github.com/test/repo.git")
        repo.create_remote("upstream", "https://github.com/upstream/repo.git")
        result = get_remotes(Path(repo.working_dir))

        assert set(result.keys()) == {"origin", "upstream"}

    def test_invalid_path_returns_empty(self, tmp_path: Path) -> None:
        """A path that is not a git repository returns an empty dict.

        Args:
            tmp_path (Path): An empty directory that is not a git repository.
        """
        assert get_remotes(tmp_path / "not-a-repo") == {}


# ───────────────────────────────────────────────────────| check_local_state |──


class TestCheckLocalState:
    """Tests check_local_state correctly classifies working tree changes."""

    def test_clean_repo_returns_empty(self, repo: git.Repo) -> None:
        """A clean working tree returns three empty lists.

        Args:
            repo (git.Repo): Fixture providing a clean repo with one commit.
        """
        uncommitted, untracked, stashes = check_local_state(
            Path(repo.working_dir)
        )

        assert uncommitted == []
        assert untracked == []
        assert stashes == []

    def test_unstaged_modification_in_uncommitted(self, repo: git.Repo) -> None:
        """A modified tracked file that is not yet staged appears in
        uncommitted.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        (Path(repo.working_dir) / "file.txt").write_text("modified")
        uncommitted, _, _ = check_local_state(Path(repo.working_dir))

        assert any("file.txt" in entry for entry in uncommitted)

    def test_staged_file_in_uncommitted(self, repo: git.Repo) -> None:
        """A newly staged file appears in uncommitted.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        new = Path(repo.working_dir) / "new.txt"
        new.write_text("new")
        repo.index.add(["new.txt"])
        uncommitted, _, _ = check_local_state(Path(repo.working_dir))

        assert any("new.txt" in entry for entry in uncommitted)

    def test_untracked_file_in_untracked(self, repo: git.Repo) -> None:
        """A file that has never been staged appears in the untracked list.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        (Path(repo.working_dir) / "untracked.txt").write_text("new")
        _, untracked, _ = check_local_state(Path(repo.working_dir))

        assert "untracked.txt" in untracked

    def test_invalid_path_returns_empty(self, tmp_path: Path) -> None:
        """A path that is not a git repo returns three empty lists.

        Args:
            tmp_path (Path): An empty directory with no .git subdirectory.
        """
        uncommitted, untracked, stashes = check_local_state(tmp_path)

        assert uncommitted == []
        assert untracked == []
        assert stashes == []

    def test_stash_command_error_returns_empty_stashes(
        self, repo: git.Repo
    ) -> None:
        """A GitCommandError from git stash list is swallowed and returns [].

        Args:
            repo (git.Repo): Fixture providing a repo (path used only).
        """
        mock_repo = MagicMock()
        mock_repo.git.status.return_value = ""
        mock_repo.git.stash.side_effect = git.GitCommandError("stash", 128)
        with patch("src.services.git_ops.git.Repo", return_value=mock_repo):
            _, _, stashes = check_local_state(Path(repo.working_dir))

        assert stashes == []


# ─────────────────────────────────────────────────────────────| check_stale |──


class TestCheckStale:
    """Tests check_stale correctly identifies repositories with old commits."""

    def test_recent_commit_is_not_stale(self, repo: git.Repo) -> None:
        """A repo with a commit made moments ago is not stale at 365 days.

        Args:
            repo (git.Repo): Fixture providing a repo whose commit was just
                             made.
        """
        stale, last = check_stale(Path(repo.working_dir), threshold_days=365)

        assert stale is False
        assert last is not None

    def test_zero_threshold_is_stale(self, repo: git.Repo) -> None:
        """Any commit satisfies a threshold of 0 days, so the repo is stale.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        stale, _ = check_stale(Path(repo.working_dir), threshold_days=0)

        assert stale is True

    def test_returns_last_commit_datetime(self, repo: git.Repo) -> None:
        """The returned datetime is a valid datetime instance.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        from datetime import datetime

        _, last = check_stale(Path(repo.working_dir), threshold_days=365)

        assert isinstance(last, datetime)

    def test_invalid_path_returns_false(self, tmp_path: Path) -> None:
        """A path that is not a git repository returns (False, None).

        Args:
            tmp_path (Path): An empty directory that is not a git repository.
        """
        stale, last = check_stale(tmp_path / "not-a-repo", threshold_days=30)

        assert stale is False
        assert last is None

    def test_empty_log_output_returns_false_none(self, repo: git.Repo) -> None:
        """When git log returns an empty string the repo is treated as
        commit-free.

        Args:
            repo (git.Repo): Fixture providing a repo (path used only).
        """
        mock_repo = MagicMock()
        mock_repo.git.log.return_value = ""
        with patch("src.services.git_ops.git.Repo", return_value=mock_repo):
            stale, last = check_stale(Path(repo.working_dir), threshold_days=30)

        assert stale is False
        assert last is None


# ──────────────────────────────────────────────────────| get_local_branches |──


class TestGetLocalBranches:
    """Tests get_local_branches returns accurate branch metadata."""

    def test_returns_current_branch(self, repo: git.Repo) -> None:
        """The current branch is present in the returned list.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        branches = get_local_branches(Path(repo.working_dir))

        assert len(branches) >= 1

    def test_sha_is_full_40_chars(self, repo: git.Repo) -> None:
        """Each branch SHA is the full 40-character hexadecimal hash.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        for b in get_local_branches(Path(repo.working_dir)):
            assert len(b["sha"]) == 40

    def test_sha_matches_repo_head(self, repo: git.Repo) -> None:
        """The branch SHA matches the HEAD commit of that branch.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        head_sha = repo.head.commit.hexsha
        branches = get_local_branches(Path(repo.working_dir))

        assert any(b["sha"] == head_sha for b in branches)

    def test_invalid_path_returns_empty(self, tmp_path: Path) -> None:
        """A path that is not a git repository returns an empty list.

        Args:
            tmp_path (Path): An empty directory that is not a git repository.
        """
        assert get_local_branches(tmp_path / "not-a-repo") == []


# ──────────────────────────────────────────────────────────| get_local_tags |──


class TestGetLocalTags:
    """Tests get_local_tags returns the correct set of tag names."""

    def test_no_tags_returns_empty(self, repo: git.Repo) -> None:
        """A repo with no tags returns an empty list.

        Args:
            repo (git.Repo): Fixture providing a repo with no tags.
        """
        assert get_local_tags(Path(repo.working_dir)) == []

    def test_lightweight_tag_returned(self, repo: git.Repo) -> None:
        """A lightweight tag is included in the returned list.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        repo.create_tag("v1.0.0")

        assert "v1.0.0" in get_local_tags(Path(repo.working_dir))

    def test_multiple_tags_returned(self, repo: git.Repo) -> None:
        """All tags are returned when more than one exists.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        repo.create_tag("v1.0.0")
        repo.create_tag("v1.1.0")
        tags = get_local_tags(Path(repo.working_dir))

        assert "v1.0.0" in tags
        assert "v1.1.0" in tags

    def test_invalid_path_returns_empty(self, tmp_path: Path) -> None:
        """A path that is not a git repository returns an empty list.

        Args:
            tmp_path (Path): An empty directory that is not a git repository.
        """
        assert get_local_tags(tmp_path / "not-a-repo") == []


# ───────────────────────────────────────────────────────| fetch_remote_refs |──


class TestFetchRemoteRefs:
    """Tests fetch_remote_refs correctly parses ls-remote output."""

    def test_parses_branches_and_tags(self, repo: git.Repo) -> None:
        """Branch and tag refs are extracted; peeled tags (^{}) are ignored.

        Args:
            repo (git.Repo): Fixture providing a repo (path used only).
        """
        ls_output = (
            "abc123\trefs/heads/main\n"
            "def456\trefs/tags/v1.0.0\n"
            "ghi789\trefs/tags/v1.0.0^{}\n"
        )
        with patch("src.services.git_ops.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=ls_output, stderr=""
            )
            success, heads, tags, err = fetch_remote_refs(
                Path(repo.working_dir), "origin"
            )

        assert success is True
        assert heads == {"main": "abc123"}
        assert tags == {"v1.0.0"}
        assert err == ""

    def test_returns_failure_on_nonzero_exit(self, repo: git.Repo) -> None:
        """Returns (False, {}, set(), error) when git exits with a non-zero
        code.

        Args:
            repo (git.Repo): Fixture providing a repo (path used only).
        """
        with patch("src.services.git_ops.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=128, stdout="", stderr="not found"
            )
            success, heads, tags, err = fetch_remote_refs(
                Path(repo.working_dir), "origin"
            )

        assert success is False
        assert heads == {}
        assert tags == set()
        assert "not found" in err

    def test_env_passed_to_subprocess(self, repo: git.Repo) -> None:
        """The env dict is forwarded to subprocess.run for SSH ControlMaster
        use.

        Args:
            repo (git.Repo): Fixture providing a repo (path used only).
        """
        custom_env = {"GIT_SSH_COMMAND": "ssh -o ControlMaster=auto"}
        with patch("src.services.git_ops.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            fetch_remote_refs(Path(repo.working_dir), "origin", env=custom_env)

        _, kwargs = mock_run.call_args
        assert kwargs.get("env") == custom_env

    def test_timeout_returns_failure(self, repo: git.Repo) -> None:
        """A subprocess timeout returns (False, {}, set(), 'timed out').

        Args:
            repo (git.Repo): Fixture providing a repo (path used only).
        """
        with patch(
            "src.services.git_ops.subprocess.run",
            side_effect=subprocess.TimeoutExpired("git", 30),
        ):
            success, heads, tags, err = fetch_remote_refs(
                Path(repo.working_dir), "origin"
            )

        assert success is False
        assert heads == {}
        assert tags == set()
        assert err == "timed out"

    def test_subprocess_exception_returns_failure(self, repo: git.Repo) -> None:
        """Any unexpected subprocess error returns (False, {}, set(), message).

        Args:
            repo (git.Repo): Fixture providing a repo (path used only).
        """
        with patch(
            "src.services.git_ops.subprocess.run",
            side_effect=OSError("connection refused"),
        ):
            success, _, _, err = fetch_remote_refs(
                Path(repo.working_dir), "origin"
            )

        assert success is False
        assert "connection refused" in err

    def test_malformed_ls_remote_line_skipped(self, repo: git.Repo) -> None:
        """Lines in ls-remote output without a tab separator are skipped.

        Args:
            repo (git.Repo): Fixture providing a repo (path used only).
        """
        ls_output = "malformed-line\nabc123\trefs/heads/main\n"
        with patch("src.services.git_ops.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=ls_output, stderr=""
            )
            success, heads, _, _ = fetch_remote_refs(
                Path(repo.working_dir), "origin"
            )

        assert success is True
        assert heads == {"main": "abc123"}


# ───────────────────────────────────────────────| analyse_branches_and_tags |──


class TestAnalyseBranchesAndTags:
    """Tests analyse_branches_and_tags identifies branch and tag issues
    correctly."""

    def test_branch_in_sync_with_origin_no_issues(self, repo: git.Repo) -> None:
        """A branch whose SHA matches origin produces no branch issues.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        branches = get_local_branches(Path(repo.working_dir))
        b = branches[0]
        remote_heads = {"origin": {b["name"]: b["sha"]}}
        bi, ti = analyse_branches_and_tags(
            Path(repo.working_dir), branches, [], remote_heads, {}, True
        )

        assert bi == []
        assert ti == []

    def test_branch_not_in_origin_flagged(self, repo: git.Repo) -> None:
        """A local branch absent from origin is reported as NOT_IN_ORIGIN.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        branches = get_local_branches(Path(repo.working_dir))
        bi, _ = analyse_branches_and_tags(
            Path(repo.working_dir), branches, [], {"origin": {}}, {}, True
        )

        assert len(bi) == 1
        assert bi[0].reason is BranchIssueReason.NOT_IN_ORIGIN

    def test_branch_ahead_of_origin_flagged(self, repo: git.Repo) -> None:
        """A branch whose SHA differs from origin is reported as
        AHEAD_OF_ORIGIN.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit; a second
                             commit is added so origin can be set to the first.
        """
        # Record the first commit SHA before adding a second
        first_sha = repo.head.commit.hexsha
        p = Path(repo.working_dir)
        (p / "file2.txt").write_text("extra")
        repo.index.add(["file2.txt"])
        repo.index.commit("second commit")

        branches = get_local_branches(Path(repo.working_dir))
        b = branches[0]
        # Origin is stuck at the first commit; local is one ahead
        remote_heads = {"origin": {b["name"]: first_sha}}
        bi, _ = analyse_branches_and_tags(
            Path(repo.working_dir), branches, [], remote_heads, {}, True
        )

        assert len(bi) == 1
        assert bi[0].reason is BranchIssueReason.AHEAD_OF_ORIGIN

    def test_branch_not_in_any_remote_flagged(self, repo: git.Repo) -> None:
        """Without origin, a branch absent from all remotes is flagged.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        branches = get_local_branches(Path(repo.working_dir))
        bi, _ = analyse_branches_and_tags(
            Path(repo.working_dir), branches, [], {}, {}, False
        )

        assert len(bi) == 1
        assert bi[0].reason is BranchIssueReason.NOT_IN_ANY_REMOTE

    def test_tag_not_in_origin_flagged(self, repo: git.Repo) -> None:
        """A local tag absent from origin is reported as NOT_IN_REMOTE.

        Args:
            repo (git.Repo): Fixture providing a repo with one tag.
        """
        repo.create_tag("v1.0.0")
        tags = get_local_tags(Path(repo.working_dir))
        _, ti = analyse_branches_and_tags(
            Path(repo.working_dir),
            [],
            tags,
            {"origin": {}},
            {"origin": set()},
            True,
        )

        assert len(ti) == 1
        assert ti[0].tag == "v1.0.0"
        assert ti[0].reason is TagIssueReason.NOT_IN_REMOTE

    def test_tag_in_origin_no_issue(self, repo: git.Repo) -> None:
        """A local tag that is also present in origin produces no tag issues.

        Args:
            repo (git.Repo): Fixture providing a repo with one tag.
        """
        repo.create_tag("v1.0.0")
        tags = get_local_tags(Path(repo.working_dir))
        _, ti = analyse_branches_and_tags(
            Path(repo.working_dir),
            [],
            tags,
            {"origin": {}},
            {"origin": {"v1.0.0"}},
            True,
        )

        assert ti == []

    def test_branch_ahead_of_non_origin_remote_flagged(
        self, repo: git.Repo
    ) -> None:
        """Without origin, a branch ahead of a non-origin remote is
        AHEAD_OF_REMOTE.

        Args:
            repo (git.Repo): Fixture; a second commit is added so the remote
                             can be set to the first SHA.
        """
        first_sha = repo.head.commit.hexsha
        p = Path(repo.working_dir)
        (p / "extra.txt").write_text("extra")
        repo.index.add(["extra.txt"])
        repo.index.commit("second commit")

        branches = get_local_branches(Path(repo.working_dir))
        b = branches[0]
        bi, _ = analyse_branches_and_tags(
            Path(repo.working_dir),
            branches,
            [],
            {"upstream": {b["name"]: first_sha}},
            {},
            False,
        )

        assert len(bi) == 1
        assert bi[0].reason is BranchIssueReason.AHEAD_OF_REMOTE
        assert bi[0].remote == "upstream"

    def test_branch_in_sync_with_non_origin_remote_no_issue(
        self, repo: git.Repo
    ) -> None:
        """Without origin, a branch whose SHA matches the non-origin remote
        produces no issues.

        Args:
            repo (git.Repo): Fixture providing a repo with one commit.
        """
        branches = get_local_branches(Path(repo.working_dir))
        b = branches[0]
        bi, _ = analyse_branches_and_tags(
            Path(repo.working_dir),
            branches,
            [],
            {"upstream": {b["name"]: b["sha"]}},
            {},
            False,
        )

        assert bi == []

    def test_branch_not_in_any_remote_count_zero_no_issue(
        self, repo: git.Repo, tmp_path: Path
    ) -> None:
        """Without origin, a branch absent from all remotes but with no
        countable commits produces no issue.

        Uses tmp_path as the counting repo so _count_commits returns 0 via
        exception handling.

        Args:
            repo (git.Repo): Fixture providing real BranchInfo objects.
            tmp_path (Path): Parent of the repo dir; not itself a git repo.
        """
        branches = get_local_branches(Path(repo.working_dir))
        # tmp_path has no .git → _count_commits raises → returns 0
        bi, _ = analyse_branches_and_tags(tmp_path, branches, [], {}, {}, False)

        assert bi == []

    def test_tag_not_in_non_origin_remote_flagged(self, repo: git.Repo) -> None:
        """Without origin, a local tag absent from the non-origin remote is
        reported with that remote's name.

        Args:
            repo (git.Repo): Fixture providing a repo with one tag.
        """
        repo.create_tag("v2.0.0")
        tags = get_local_tags(Path(repo.working_dir))
        _, ti = analyse_branches_and_tags(
            Path(repo.working_dir),
            [],
            tags,
            {"upstream": {}},
            {"upstream": set()},
            False,
        )

        assert len(ti) == 1
        assert ti[0].tag == "v2.0.0"
        assert ti[0].remote == "upstream"
