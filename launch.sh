#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
case "$(uname -s)" in
  Darwin) entry=keyboard_lock_macos.py ;;
  Linux) entry=keyboard_lock_linux.py ;;
  *) echo 'Use KeyboardLock.exe on Windows.' >&2; exit 1 ;;
esac
if [[ ! -x .venv/bin/python ]]; then
  echo 'Run bash setup.sh first.' >&2
  exit 1
fi
exec .venv/bin/python "$entry" "$@"
