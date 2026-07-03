## Git Sentinel {{TAG}}

**Channel:** {{CHANNEL}}

### Install

Installation and uninstallation both use the same self-contained binary. Below
you will find instructions for each platform:

#### Linux

> [!NOTE]
> Make sure you are running under a desktop environment! TUI support will come
> in later releases.

**Installation:**
1. Download the pre-compiled self-contained binary below from packages - make
sure to choose the one marked as "Linux x86_64";
    ```bash
    curl -fL -o git-sentinel "https://gitlab.com/api/v4/projects/83160866/packages/generic/git-sentinel/{{TAG}}/git-sentinel"
    # or
    wget -O git-sentinel "https://gitlab.com/api/v4/projects/83160866/packages/generic/git-sentinel/{{TAG}}/git-sentinel"
    ```
2. Mark it as executable;
    ```bash
    chmod +x git-sentinel
    ```
3. Run it directly from any terminal (even a TTY). This will install the
application on your system.
    ```bash
    ./git-sentinel
    ```

**Uninstallation:**
1. Run the installed binary with the `--uninstall` flag. If you don't remember
the install path, re-download the binary and run it with `--uninstall` instead -
it uninstalls the software either way.
    ```bash
    ~/.local/bin/git-sentinel --uninstall # could be different!
    # or
    chmod +x git-sentinel
    ./git-sentinel --uninstall
    ```

#### Windows

> [!WARNING]
> The Windows binary registers itself in the registry as uninstallable
> software and creates a scheduled task on install. Simply deleting the
> binary will **not** remove either of these - you must uninstall it through
> the Windows apps manager or by running the binary with `--uninstall` flag,
> otherwise the registry keys and scheduled task will be left behind.

**Installation:**
1. Download the pre-compiled self-contained executable below from packages -
make sure to choose the one marked as "Windows x86_64";
    ```powershell
    curl.exe -fL -o git-sentinel.exe "https://gitlab.com/api/v4/projects/83160866/packages/generic/git-sentinel/{{TAG}}/git-sentinel.exe"
    ```
2. Execute the binary like any other program - a terminal window will briefly
open and install it automatically. You can also run it from PowerShell or
Command Prompt, though it isn't necessary.
    ```powershell
    .\git-sentinel.exe
    ```

**Uninstallation:**
1. Run the installed binary with the `--uninstall` flag. By default it lives
here:
    ```powershell
    & "$env:LOCALAPPDATA\Programs\git-sentinel\git-sentinel.exe" --uninstall
    ```
2. If you don't remember the install path, re-download the executable and run
it with `--uninstall` instead:
    ```powershell
    curl.exe -fL -o git-sentinel.exe "https://gitlab.com/api/v4/projects/83160866/packages/generic/git-sentinel/{{TAG}}/git-sentinel.exe"
    .\git-sentinel.exe --uninstall
    ```
3. Or uninstall it the usual Windows way: via **Settings → Apps → Installed Apps** or
**Control Panel → Programs and Features**.

On first run the binary detects it is not installed and sets itself up
automatically. To force a reinstall or update, run it with `--install`:
`git-sentinel --install` (Linux) or `git-sentinel.exe --install` (Windows). To
uninstall, use the same approach: `git-sentinel --uninstall` or
`git-sentinel.exe --uninstall`.
