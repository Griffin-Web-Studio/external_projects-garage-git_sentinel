<img align="right" width="200" src="src/data/git-sentinel.svg" alt="Project Icon">

# Local Git Sentinel

Lost work due to corrupted drive, or dead SSD/HDD? Cry no more, data is gone, but you've learned your lesson about not pushing your work for days on end. Now you need a daily local git repository audit tool.

On each login it scans every git repository under `~/git/` or your preferred location and reports anything that could be lost due to a storage failure: uncommitted changes, untracked files, stashes, unpushed branches, unpushed tags, and repositories with no remote configured. Results are written as a dated report to your Desktop - annoying I know, but on purpose! If nothing is wrong, no report file is created and any previous clean-run reports are moved to an archive.

## Requirements

<!-- TODO: determine requirements -->

## Installation

<!-- TODO: add installation instructions -->

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

<!-- TODO: add locations -->

## Uninstalling

```bash
# TODO: add instructions
```

Reports in `~/git/reports/` and on the Desktop are left in place.
