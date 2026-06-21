#!/bin/sh
# Generates release notes for a git-sentinel GitLab Release.
# Usage: gen-release-notes.sh <tag> <channel>
set -eu

TAG=$1
CHANNEL=$2

cat <<EOF
## git-sentinel $TAG

**Channel:** $CHANNEL

### Install

**Linux**
\`\`\`bash
chmod +x git-sentinel
./git-sentinel
\`\`\`

**Windows** - download \`git-sentinel.exe\` and run it from PowerShell or Command Prompt:
\`\`\`powershell
.\git-sentinel.exe
\`\`\`

On first run the binary detects it is not installed and sets itself up automatically.
To force a reinstall or update: \`git-sentinel --install\`
To uninstall: \`git-sentinel --uninstall\`
EOF
