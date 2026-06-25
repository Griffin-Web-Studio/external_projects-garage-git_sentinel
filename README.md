<img align="right" width="200" src="src/data/git-sentinel.svg" alt="Project Icon">

> [!NOTE]
> GitHub users - this project is maintained on GitLab:
> https://gitlab.com/griffin-web-studio/garage/git-sentinel

[![pipeline status](https://gitlab.com/griffin-web-studio/garage/git-sentinel/badges/main/pipeline.svg)](https://gitlab.com/griffin-web-studio/garage/git-sentinel/-/pipelines)
[![coverage: linux](https://img.shields.io/gitlab/pipeline-coverage/griffin-web-studio/garage/git-sentinel?branch=main&job_name=test&label=coverage%3A+linux)](https://gitlab.com/griffin-web-studio/garage/git-sentinel/-/jobs?name=test)
[![coverage: windows](https://img.shields.io/gitlab/pipeline-coverage/griffin-web-studio/garage/git-sentinel?branch=main&job_name=test%3Awindows&label=coverage%3A+windows)](https://gitlab.com/griffin-web-studio/garage/git-sentinel/-/jobs?name=test%3Awindows)

# Local Git Sentinel (v0.2.0)

Lost work due to a corrupted drive or dead SSD/HDD? Cry no more - the data is
gone, but you've learned your lesson about not pushing for days on end. Now you
need a daily local git repository audit tool.

On each login it scans every git repository under `~/git/` (or your preferred
location) and reports anything that could be lost in a storage failure:
uncommitted changes, untracked files, stashes, unpushed branches, unpushed
tags, and repositories with no remote configured. Results are written as a
dated report to your Desktop - annoying on purpose! If nothing is wrong, no
report is created and any previous reports are moved to an archive.

## Requirements

- Any Windows, and Linux desktop (X11 or Wayland)
- `git` in `PATH`

No Python, no system packages. The binary is self-contained.

## Installation

Download the latest binary from the
[Releases page](https://gitlab.com/griffin-web-studio/garage/git-sentinel/-/releases/v0.2.0)
and run it:

```bash
./git-sentinel
```

On the first run the binary detects it is not yet installed and sets itself up:

1. Copies itself to `~/.local/bin/git-sentinel`
2. Seeds `~/.config/git-sentinel/` with a default `settings.ini`
3. Registers an XDG autostart entry so it runs on every login
4. Adds an app launcher entry so it can be opened from your app menu

Then exits. From that point `git-sentinel` is on your PATH and will run at
every login automatically.

**To reinstall or upgrade** - download the new binary and run it with `--install`:

```bash
./git-sentinel --install
```

## First run

After installation, the next login opens a small desktop window:

- A **status bar** and **progress bar** show the current scan stage.
- A **log pane** shows real-time output as each repository is checked.
- For **SSH remotes**, a prompt appears asking whether to approve an SSH
  connection to that host. Approving once per host is enough for the session -
  subsequent remotes on the same host reuse an SSH ControlMaster socket so you
  are not prompted (or asked for your FIDO key) again.

When the scan finishes:

| Result | Status message | Button |
|--------|---------------|--------|
| Issues found | ⚠️ N repo(s) with issues - report saved to Desktop | Acknowledge & Close + Open Report |
| All clear | ✔️ All clear - no issues found. | Close |

On a clean run, any existing reports on the Desktop are moved to the archive
automatically, so the Desktop stays empty - the visual signal that all is well.

If `once_per_day` is enabled (the default), subsequent logins on the same
calendar day exit silently without opening a window.

## Configuration

The active config lives at `~/.config/git-sentinel/settings.ini`. A commented
reference copy is kept at `~/.config/git-sentinel/settings.example.ini`.
Edit the active file with any text editor; changes take effect on the next run.

All path values are relative to your home directory unless they begin with `/`.

### `[paths]`

| Key | Default | Description |
|-----|---------|-------------|
| `git_root` | `git` | Root directory scanned recursively for git repositories (`~/git/`) |
| `export_path` | *(unset)* | Directory where reports are written. Leave unset to use `XDG_DESKTOP_DIR`. *(Replaces deprecated `desktop_override`)* |
| ~~`reports_archive`~~ | - | **Deprecated** - no longer used. Carry any custom value over to `export_path`. |

### `[reports]`

| Key | Default | Description |
|-----|---------|-------------|
| `retention_days` | `14` | Number of days to keep report files locally before they are removed. *(Replaces deprecated `desktop_retention_days`)* |
| `report_extension` | `log` | File extension for report files (`.log` opens well in most editors) |

### `[staleness]`

| Key | Default | Description |
|-----|---------|-------------|
| `stale_threshold_days` | `90` | A repo with no commits newer than this many days is flagged as stale |

### `[schedule]`

| Key | Default | Description |
|-----|---------|-------------|
| `once_per_day` | `true` | When true, only one scan runs per calendar day; use `--force` to bypass |

### `[ssh]`

| Key | Default | Description |
|-----|---------|-------------|
| `use_control_master` | `true` | Multiplex SSH so each host needs only one FIDO key tap per session |
| `control_persist_seconds` | `300` | How long (seconds) to keep an idle ControlMaster socket alive |

## How it works

### Scan stages

#### Stage 1 - Discovery

Finds all directories containing a `.git` folder under `git_root`, sorted
alphabetically.

#### Stage 2 - Local and remote checks

For each repository:

- Checks for uncommitted changes and untracked files via `git status --porcelain`
- Lists stashes via `git stash list`
- Checks staleness via `git log --all`
- For each remote, calls `git ls-remote --heads --tags` and compares the results
  against local branches and tags

SSH remotes prompt for approval in the GUI (once per host per session).
HTTP remotes that fail offer a one-time retry prompt.

#### Stage 3 - Report

Compares today's findings against the previous report to split issues into
`[persistent_issues]` (seen before) and `[new_issues]` (first occurrence).
Writes the report to the Desktop if any issues are found, or moves all Desktop
reports to the archive if the run is clean.

### Fork/upstream repos

For repositories with both `origin` and `upstream` remotes (e.g. a FOSS fork
where `origin` is your personal fork), work is considered safe as long as it is
present in `origin`. Missing from `upstream` alone does not raise a flag.

### Report format

Reports are plain-text INI-style files. A typical report looks like:

```ini
[report]
date              = 2026-06-11
time              = 08:30:15
generated_by      = git-sentinel v1.1.0
total_repos       = 8
repos_with_issues = 2
repos_passed      = 5
stale_repos       = 1

[new_issues]
; Issues not present in the previous report
  ~/git/work-project|uncommitted|M  src/auth.py
  ~/git/work-project|branch|fix/login|origin|not_in_origin

[persistent_issues]
; Issues from the previous report still unresolved today
  ~/git/work-project|untracked|scratch.py

[uncommitted]
; Staged or modified tracked files not yet committed
  ~/git/work-project
    M  src/auth.py

[untracked]
; Non-ignored files not yet added and committed
  ~/git/work-project
    scratch.py

[unpushed_branches]
  ~/git/work-project
    fix/login → not in origin (2 commit(s))

[stale]
; Repositories with no commits in the last 90 day(s)
  ~/git/old-experiment  (last commit: 2025-12-01, 192 day(s) ago)

[passed]
; Repositories with no issues detected this run
  ~/git/main-project
  ~/git/dotfiles
  ~/git/scripts
  ~/git/notes
  ~/git/personal-site
```

Alongside the `.log` file a `.issues` sidecar is written containing the raw
issue keys used to classify findings as new or persistent on the next run.

### Report retention

- Reports are written to `export_path` and kept for `retention_days` (default 14) days, after which they are removed.

## File locations

| Path | Purpose |
|------|---------|
| `~/.local/bin/git-sentinel` | Binary |
| `~/.config/git-sentinel/settings.ini` | Active configuration |
| `~/.config/git-sentinel/settings.example.ini` | Reference copy (do not edit) |
| `~/.config/autostart/git-sentinel.desktop` | XDG autostart entry |
| `~/.local/share/applications/git-sentinel.desktop` | App launcher entry |
| `~/.local/share/icons/hicolor/scalable/apps/git-sentinel.svg` | App icon |
| `~/.local/share/git-sentinel/` | State directory (daily lock file) |
| `~/Desktop/*-git-status-report.log` | Current reports |
| `~/Desktop/*-git-status-report.issues` | Issue key sidecars |
| `~/git/reports/` | Report archive |

## Uninstalling

```bash
git-sentinel --uninstall
```

You will be asked whether to also remove `~/.config/git-sentinel/` and the
state directory. Reports on the Desktop and in `~/git/reports/` are always left
in place.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev setup, commit conventions,
test suite, and release process.
