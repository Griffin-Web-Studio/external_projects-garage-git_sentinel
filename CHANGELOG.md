## v0.1.0 (2026-06-21)

### Bug Fixes

- **installer**: rename and than remove the binary
- **scripts/build.os1**: set icon path as absolute
- force utf8 encoding in more text handling
- **installer**: add permission exception handler and force utf8 encoding
- **models**: force interprit paths as posix
- **installer**: couple some installer methods only to linux
- add issue templates with corrected labels
- **modules**: require GateHTTP str value to be present

### Features

- **installer**: add uninstaller shortcut for Windows
- add ico gen from svg for Windows executable
- **installer**: add windows installation options
- **main**: prevent console from closing prematurely
- **scripts/setup**: add windows script for setup
- **config_template**: create automated config generator
- **installer**: generate settings file programmatically
- **window**: ensure opening report is cross platform
- **installer**: add Winslop support
- **reports**: add reports generation phase
- **scan**: implement git operations into scanner stage 2
- **git_ops**: add more git operations
- **scan**: add scan orchestrator
- **git_ops**: add recursive git dirs search
- introduce remote ssh ControlMaster
- **GUI**: implement app GUI
- **GUI**: add initial App GUI
- **models**: Create App protocol
- add ssh parsing helpers
- **config**: add desktop location detection logic
- **modules**: block out modules
- implement schedule run checker
- implement config parser wrapper
- implement uninstaller in main
- implement uninstaller
- implement installer
- add helper build script
- create application skeleton
- write draft config file

### Refactoring

- **scan**: add white space after each scan result
- remove setup of settings file from setup script
- **installer**: implement config generator into settings renderer
- **scripts/build**: remove settings example from installer data
- **scan**: add notice that ControlMaster is missing on Windows
- **config**: add windows desktop path detection
- **init**: add windows paths support
- **scan**: implement reports generation phase into scan
- introduce real scan orchestrator
- update version number to correct 0.0.0 release
- **modules**: remove home attribute from RepoResult
- rename git-sentinel.py into git-sentinel and make executable
