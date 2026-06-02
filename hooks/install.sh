#!/bin/bash
# Symlink the agent-notify hooks into ~/.claude/hooks so Claude Code and Codex
# can reference a stable path while this repo stays the source of truth.
# Idempotent: safe to re-run after moving/updating the repo.
set -euo pipefail

HOOK_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.claude/hooks"
mkdir -p "$DEST"

for f in agent-notify.py claude-hook.sh codex-hook.sh; do
  chmod +x "$HOOK_DIR/$f"
  ln -sfn "$HOOK_DIR/$f" "$DEST/$f"
  echo "linked $DEST/$f -> $HOOK_DIR/$f"
done

# Retire the old single-purpose hook if present.
if [ -e "$DEST/tmux-notify.sh" ] && [ ! -L "$DEST/tmux-notify.sh" ]; then
  mv "$DEST/tmux-notify.sh" "$DEST/tmux-notify.sh.bak"
  echo "backed up old $DEST/tmux-notify.sh -> tmux-notify.sh.bak"
fi

cat <<EOF

Done. Now make sure these reference the shims:

  Claude  ~/.claude/settings.json  Stop + Notification hooks ->
            $DEST/claude-hook.sh
  Codex   ~/.codex/config.toml ->
            notify = ["$DEST/codex-hook.sh"]
EOF
