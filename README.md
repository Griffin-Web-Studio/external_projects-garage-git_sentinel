<img align="right" width="200" src="src/data/git-sentinel.svg" alt="Project Icon">

# Local Git Sentinel

Lost work due to corrupted drive, or dead SSD/HDD? Cry no more, data is gone, but you've learned your lesson about not pushing your work for days on end. Now you need a daily local git repository audit tool.

On each login it scans every git repository under `~/git/` or your preferred location and reports anything that could be lost due to a storage failure: uncommitted changes, untracked files, stashes, unpushed branches, unpushed tags, and repositories with no remote configured. Results are written as a dated report to your Desktop - annoying I know, but on purpose! If nothing is wrong, no report file is created and any previous clean-run reports are moved to an archive.

## Requirements (end user)

- Any Linux desktop (X11 or Wayland)
- `git` in `PATH`

That's it! no Python, no system packages. The binary is self-contained.

## Installation

Download the latest binary from the [Releases page](https://gitlab.griffin-studio.dev/external-projects/garage/git-sentinel/-/releases) and run it:

```bash
./git-sentinel
```

On the first run the binary detects it is not yet installed and sets itself up automatically:

1. Copies itself to `~/.local/bin/git-sentinel`
2. Seeds `~/.config/git-sentinel/` with a default `settings.ini` (if not already there)
3. Registers an XDG autostart entry so it runs on every login
4. Adds an app launcher entry so it can be opened manually from your app menu

Then exits. From that point `git-sentinel` is on your PATH and will run at login.

**To reinstall or upgrade** - download the new binary and run it with `--install`:

```bash
./git-sentinel --install
```

## First run

<!-- TODO: add first run instructions -->

## Configuration

<!-- TODO: add config instructions -->

## How it works

### Scan stages

#### Stage 1) Discovery
Finds all directories containing a `.git` folder under `git_root`.

#### Stage 2) Local and remote checks
For each repository:
- Checks for uncommitted changes and untracked (non-ignored) files via `git status --porcelain`
- Lists stashes via `git stash list`
- Checks staleness via `git log --all`
- For each remote, calls `git ls-remote --heads --tags` and compares the results against local branches and tags

#### Stage 3) Report
Compares today's findings against the previous report to split issues into
`[persistent_issues]` and `[new_issues]`. Writes the report to the Desktop
if any issues are found, or moves all Desktop reports to the archive if the
run is clean.

### Fork/upstream repos

For repositories with both `origin` and `upstream` remotes (e.g. a FOSS fork where `origin` is your personal fork), work is considered safe as long as it is present in `origin`. Missing from `upstream` alone will not raise a flag.

### Report format

<!-- TODO: add format -->

### Report retention

- Up to `desktop_retention_days` (default 14) reports are kept on the Desktop.
- Older reports are moved to `reports_archive` automatically.
- If the current run finds no issues, all Desktop reports are moved to the archive (the Desktop stays empty, which is the visual signal that everything is fine).

## File locations

| Path | Purpose |
|---|---|
| `~/.local/bin/git-sentinel` | Binary |
| `~/.config/git-sentinel/settings.ini` | Active configuration |
| `~/.config/git-sentinel/settings.example.ini` | Reference copy |
| `~/.config/autostart/git-sentinel.desktop` | XDG autostart entry |
| `~/.local/share/applications/git-sentinel.desktop` | App launcher entry |
| `~/.local/share/icons/hicolor/scalable/apps/git-sentinel.svg` | App icon |
| `~/.local/share/git-sentinel/` | State directory (daily lock file, etc.) |
| `~/Desktop/*-git-status-report.log` | Current reports |
| `~/git/reports/` | Report archive |

## Uninstalling

```bash
git-sentinel --uninstall
```

Reports in `~/git/reports/` and on the Desktop are left in place.
