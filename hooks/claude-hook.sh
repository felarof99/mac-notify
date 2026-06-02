#!/bin/bash
# Claude Code Stop/Notification hook -> mac-notify.
# Reads the hook JSON on stdin and hands it to agent-notify.
# Never fails in a way that blocks Claude.

# Resolve this script's real directory, even when invoked via a symlink.
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/go/bin:$HOME/opt/anaconda3/bin:$PATH"

python3 "$DIR/agent-notify.py" claude || true
exit 0
