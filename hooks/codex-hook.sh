#!/bin/bash
# Codex `notify` program -> mac-notify.
# Codex invokes this as:  codex-hook.sh '<notify-json>'
#
# It does two things:
#   1. Forwards the event to the original Codex Computer Use client so that
#      feature keeps working (chaining — Codex only allows ONE notify program).
#   2. Sends a rich mac-notify message via agent-notify.
# Never fails in a way that blocks Codex.

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/go/bin:$HOME/opt/anaconda3/bin:$PATH"

JSON="$1"

# 1. Preserve the original Codex Computer Use notify (fire-and-forget).
SKY="$HOME/.codex/computer-use/Codex Computer Use.app/Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient"
if [ -x "$SKY" ]; then
  "$SKY" turn-ended "$JSON" >/dev/null 2>&1 &
fi

# 2. Our notification.
python3 "$DIR/agent-notify.py" codex "$JSON" >/dev/null 2>&1 || true
exit 0
