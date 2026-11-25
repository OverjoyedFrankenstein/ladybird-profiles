#!/bin/bash
# Ladybird Profiles: one-line installer.
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/OverjoyedFrankenstein/ladybird-profiles/main/install.sh)"
#
# Downloads the latest version of this add-on to a temporary folder and runs install.py from it. Options for
# install.py go after the command, for example:
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/OverjoyedFrankenstein/ladybird-profiles/main/install.sh)" - --restore
#   curl -fsSL https://raw.githubusercontent.com/OverjoyedFrankenstein/ladybird-profiles/main/install.sh | bash -s -- --restore

set -euo pipefail

ARCHIVE="https://github.com/OverjoyedFrankenstein/ladybird-profiles/archive/refs/heads/main.tar.gz"

# On a Mac without the command line tools, python3 is only a stand-in that asks to install them.
if [ "$(uname -s)" = "Darwin" ] && ! xcode-select -p >/dev/null 2>&1; then
    echo "Ladybird Profiles needs Apple's command line tools. A window will ask to install them."
    echo "When that has finished, run this command again."
    xcode-select --install || true
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Ladybird Profiles needs Python 3. Install it with your package manager, then run this command again."
    exit 1
fi

dir="$(mktemp -d)"
trap 'rm -rf "$dir"' EXIT

echo "Downloading Ladybird Profiles..."
curl -fsSL "$ARCHIVE" | tar -xz -C "$dir" --strip-components=1

# When this script is piped into bash, its input is the script, not the keyboard. The installer asks questions, so it
# reads from the terminal instead.
if [ -t 0 ] || ! { : </dev/tty; } 2>/dev/null; then
    python3 "$dir/install.py" "$@"
else
    python3 "$dir/install.py" "$@" </dev/tty
fi
