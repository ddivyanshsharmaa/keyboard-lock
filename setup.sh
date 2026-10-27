#!/usr/bin/env bash
# Installs only the current platform's bridge, into this repository.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
case "$(uname -s)" in
  Darwin) packages=(pyobjc-framework-Cocoa pyobjc-framework-Quartz) ;;
  Linux) packages=(evdev) ;;
  *) echo 'Use the README C# build command on Windows.' >&2; exit 1 ;;
esac
command -v python3 >/dev/null || { echo 'Install Python 3.9+ first.' >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || {
  echo 'Python 3.9+ is required.' >&2; exit 1;
}
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir "${packages[@]}"
echo 'Setup complete. Run: bash launch.sh [--minutes 30]'
