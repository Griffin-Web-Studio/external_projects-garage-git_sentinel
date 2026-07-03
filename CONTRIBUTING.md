# Contributing to git-sentinel

Thank you for considering a contribution! This document covers the local dev
setup, commit conventions, release process, and CI pipeline.

## How to contribute

- **Bug reports** - open an issue on GitLab describing what you expected, what
  happened, and how to reproduce it. Include your OS/desktop environment and the
  git-sentinel version (shown in the window title bar).
- **Feature requests** - open an issue first to discuss the idea before investing
  time in an MR.
- **Merge requests** - fork the repository, branch from `main`, and open an MR.
  CI must be green (mypy strict + all tests pass) and commits must follow the
  [Conventional Commits](#commit-messages) format below.

## Dev environment

Requires: `uv`, `git`, and Python 3. Linux also requires `python3-tk` for the
GUI; on Windows and macOS `tkinter` is bundled with Python. The devcontainer
has everything pre-installed and is the easiest way to get started.

```bash
git clone https://gitlab.com/griffin-web-studio/garage/git-sentinel.git
cd git-sentinel
```

Then either open in the devcontainer, or set up manually:

### Linux / macOS

```bash
# Install/update dependencies and activate the venv
uv sync --group dev

# Install pre-commit hooks (commit linting + mypy + formatters)
pre-commit install
pre-commit install --hook-type commit-msg
```

`scripts/setup.sh` automates the above steps. If you don't have `uv` yet,
install it via the [official installer](https://docs.astral.sh/uv/getting-started/installation/)
or through `pipx install uv`.

### Windows

```powershell
# Install/update dependencies and activate the venv
uv sync --group dev

# Install pre-commit hooks (commit linting + mypy + formatters)
pre-commit install
pre-commit install --hook-type commit-msg
```

`scripts/setup.ps1` automates the above steps. If you don't have `uv` yet,
install it via the [official installer](https://docs.astral.sh/uv/getting-started/installation/)
(the recommended path on Windows - no `pipx` required).

## Running tests

Same command on every platform - `scripts/test.py` detects the OS and runs
mypy strict + pytest with the matching coverage config:

```bash
uv run scripts/test.py
```

Extra arguments are forwarded to pytest, e.g. `uv run scripts/test.py -k scan`.
Use `--no-mypy` to skip the type-check or `--no-cov` to run pytest without
coverage.

Coverage is tracked separately per platform via `.coveragerc.linux` and
`.coveragerc.windows`. Linux-only code (`src/platform/linux/`) is excluded
from the Windows coverage run and vice versa. GUI tests only run on Linux -
Tkinter under `uv`'s venv on Windows intermittently fails to find `tk`, so
`src/ui/gui/` is excluded from the Windows coverage run entirely rather than
run flaky. The CI pipeline enforces a 75 % coverage floor (per platform) and
mypy strict on every push.

## Commit messages

This project follows [Conventional Commits](https://www.conventionalcommits.org/).
The `commitlint` pre-commit hook enforces this on every commit.

```
<type>(<scope>): <subject>

feat(scan):     add stale-repo detection
fix(installer): handle SameFileError on reinstall
perf(git_ops):  batch ls-remote calls
refactor(app):  extract queue helpers
docs:           update README installation steps
chore:          bump black to 26.3.0
ci:             add nightly schedule trigger
test:           add git_ops unit tests
```

Types that appear in `CHANGELOG.md`: `feat`, `fix`, `perf`, `refactor`.
Types excluded from the changelog (`chore`, `ci`, `docs`, `style`, `test`) still
trigger a build but are not user-facing.

Breaking changes - append `!` to the type or add a `BREAKING CHANGE:` footer:

```
feat!: redesign settings file format

BREAKING CHANGE: settings.ini keys renamed from snake_case to kebab-case
```

## Cutting a release

Releases are driven by `cz bump`, which reads commits since the last tag,
determines the next version, updates version files, and creates a signed tag.

### Stable release

```bash
cz bump
git push origin main --follow-tags
```

`cz bump` will:
1. Determine the next version from commits (`feat` to minor, `fix`/`perf` to patch,
   `BREAKING CHANGE` to major)
2. Update `version` in `pyproject.toml` and `APP_VERSION` in `src/__init__.py`
3. Prepend an entry to `CHANGELOG.md`
4. Commit and tag as `vX.Y.Z`

### Pre-release

Accepted pre-release types: `alpha`, `beta`, `rc`.

```bash
cz bump --prerelease alpha   # to v1.0.0-alpha.0
cz bump --prerelease alpha   # to v1.0.0-alpha.1  (subsequent alpha)
cz bump --prerelease beta    # to v1.0.0-beta.0
cz bump --prerelease rc      # to v1.0.0-rc.0
cz bump                      # to v1.0.0           (promote to stable)
git push origin main --follow-tags
```

### Manual override (if needed)

```bash
cz bump --increment MAJOR     # force a major bump regardless of commits
cz bump --increment MINOR
cz bump --increment PATCH
```

## CI pipeline

| Stage   | Job                | Trigger           | What it does                                      |
|---------|--------------------|-------------------|---------------------------------------------------|
| test    | `test`             | all pipelines     | mypy strict + pytest (75 % coverage gate)         |
| build   | `build`            | commit / MR / tag | PyInstaller binary to `dist/git-sentinel`          |
| build   | `build:nightly`    | schedule          | PyInstaller binary (rolling nightly build)        |
| publish | `publish:release`  | versioned tag     | Uploads binary to Generic Package Registry        |
| publish | `publish:nightly`  | schedule          | Overwrites the rolling `nightly` package entry    |
| release | `release`          | versioned tag     | Creates a GitLab Release with binary asset linked |

Scheduled pipelines (set up under CI/CD to Schedules in GitLab) produce a rolling
nightly build uploaded under the fixed version `nightly` - the download URL never
changes.

### Tag format

| Tag                 | Channel | Notes                            |
|---------------------|---------|----------------------------------|
| `v1.0.0-alpha.0`   | alpha   | early testing, may be unstable   |
| `v1.0.0-beta.0`    | beta    | feature-complete, bugfixes only  |
| `v1.0.0-rc.0`      | rc      | release candidate                |
| `v1.0.0`           | stable  | full release                     |

## Building locally

**Linux / macOS**

```bash
bash scripts/build.sh        # produces dist/git-sentinel
./dist/git-sentinel --help   # smoke-test the binary
```

**Windows**

```powershell
pwsh scripts/build.ps1              # produces dist\git-sentinel.exe
.\dist\git-sentinel.exe --help      # smoke-test the binary
```
