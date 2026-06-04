<div align="center">

# 🔔 mac-notify

**A macOS menu bar notification queue.**

*Send messages from anywhere. See them at a glance.*

</div>

A lightweight CLI that puts notification messages in your macOS menu bar. Messages queue up with a badge count, and you can dismiss them individually or all at once. Optionally triggers native macOS notification banners too.

- **Simple CLI** — `mac-notify send "deploy finished"` and it's in your menu bar
- **Message queue** — multiple messages stack up with a count badge
- **Click to dismiss** — click any message in the dropdown to remove it
- **Upsert by ID** — update an existing message in-place with `--id`
- **Source tagging** — `--source ci` to know where it came from
- **Native notifications** — macOS banner alerts with sound (configurable)
- **Daemon auto-start** — installs as a launchd service, runs on login

---

## Install

Requires Go 1.21+ and macOS.

```sh
git clone https://github.com/nickhudkins/mac-notify
cd mac-notify
make install
```

This builds the binary, creates an `.app` bundle at `~/Applications/mac-notify.app`, installs the launchd daemon, and symlinks the CLI to your `$GOPATH/bin`.

## Uninstall

```sh
make uninstall
```

## Quick Start

```sh
mac-notify send "hello world"
mac-notify send "build passed" --source ci
mac-notify send "deploying v2" --source deploy --id deploy-status
mac-notify list
mac-notify clear
```

## Commands

```sh
mac-notify send [message]      # send a notification
mac-notify send "msg" --source ci   # tag with source
mac-notify send "msg" --id build    # upsert by ID
mac-notify list                # show current messages
mac-notify clear               # clear all messages
mac-notify status              # check if daemon is running
mac-notify install             # install launchd service
mac-notify uninstall           # remove launchd service and stop daemon
mac-notify daemon              # run daemon in foreground (for debugging)
```

### Flags

| Flag | Command | Description |
|------|---------|-------------|
| `--source` | `send` | Origin label (e.g. `ci`, `build`, `deploy`) |
| `--id` | `send` | Message ID for upsert — replaces existing message with same ID |

## Menu Bar

The menu bar icon shows 🔔 when empty and 🔔 N when messages are queued.

Click to open the dropdown:

```
🔔 2
├─ [ci] build passed
├─ [deploy] deploying v2
├─ ──────────
└─ Clear All
```

Click a message to dismiss it. Click **Clear All** to reset.

## Native Notifications

When enabled, each `send` also triggers a macOS notification banner with sound. The app appears in **System Settings → Notifications** as `mac-notify` with its own icon.

## Config

`~/.config/mac-notify/config.yaml`:

```yaml
system_notifications: true
mute_patterns:
  - "^Codex · .*chatcli"   # drop a chatty background Codex runner
```

| Key | Default | Description |
|-----|---------|-------------|
| `system_notifications` | `true` | Show native macOS notification banners |
| `mute_patterns` | `[]` | Regexes; a notification whose **source or body** matches any is silently dropped |

### Muting noisy notifications

Add Go-flavored (RE2) regular expressions to `mute_patterns` to silence senders
you don't care about — e.g. a tool that fires Codex on a timer. Each pattern is
tested against the **source** (the `[Codex · …]` label) and the **body**
independently, so anchors apply per field:

```yaml
mute_patterns:
  - "^Codex · .*chatcli"    # mute one source
  - "screenshot|recording"  # mute by body keyword
```

- **Live reload** — edits apply on the next notification; no restart needed.
- **Future-only** — muting doesn't touch messages already in the queue.
- **Fail-safe** — an invalid regex is skipped, never silencing everything or
  crashing the daemon.

## Agent integration (Claude Code + Codex)

The `hooks/` directory turns coding-agent events into rich notifications that
answer two questions at a glance:

- **WHERE** — a precise PARA-style tmux breadcrumb derived from the *exact* pane
  the agent runs in (`$TMUX_PANE`), so it's right even after you switch windows.
  Mirrors the `tl` / tmux-para-picker tree: `parent › sub-session · window`.
- **WHAT** — a one-liner. For a finished turn it's the agent's final message
  ("what's ready"); for a Claude prompt it's what Claude wants (input/permission).

```
🔔  Claude · SELF_IMPROVE › MAC_NOTIFY · w1
    ✅ Done — wired the notify hook and the build passes.

🔔  Codex · @browseros › agent · w3
    🔐 Needs your permission to run a command
```

Status glyphs: `✅` turn complete · `⌛` waiting for input · `🔐` needs permission.

### Files

| File | Role |
|------|------|
| `hooks/agent-notify.py` | Core — parses the event, builds the breadcrumb + one-liner, calls `mac-notify send`. Shared by both agents. |
| `hooks/claude-hook.sh` | Claude Code Stop/Notification hook. Reads the hook JSON on stdin. |
| `hooks/codex-hook.sh` | Codex `notify` program. Also **chains** to the original Codex Computer Use client so that feature keeps working (Codex allows only one `notify`). |
| `hooks/install.sh` | Symlinks the three scripts into `~/.claude/hooks` (idempotent). |

### Setup

```sh
./hooks/install.sh        # or: make install-hooks
```

Then point your agents at the shims:

**Claude Code** — `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [{ "hooks": [{ "type": "command", "command": "~/.claude/hooks/claude-hook.sh", "timeout": 10 }] }],
    "Notification": [
      { "matcher": "idle_prompt",       "hooks": [{ "type": "command", "command": "~/.claude/hooks/claude-hook.sh", "timeout": 10 }] },
      { "matcher": "permission_prompt", "hooks": [{ "type": "command", "command": "~/.claude/hooks/claude-hook.sh", "timeout": 10 }] }
    ]
  }
}
```

**Codex** — `~/.codex/config.toml`:

```toml
notify = ["/Users/<you>/.claude/hooks/codex-hook.sh"]
```

Each pane gets one notification slot (keyed by `pane_id`) that updates in place,
so repeated turns refresh rather than pile up. Out of tmux, it falls back to the
project directory name (`📁 my-project`). Every script exits 0 on any error so a
notifier bug can never block the agent.

## Architecture

```
mac-notify send "msg"  ──→  Unix socket IPC  ──→  daemon (menu bar app)
                            ~/.mac-notify.sock       ├─ menuet menu bar
                                                     └─ UNUserNotificationCenter
```

The daemon runs as a `.app` bundle (required for macOS notification permissions) with `LSUIElement=true` to stay out of the Dock. A LaunchAgent keeps it alive and starts it on login.

---

> Personal tool built for my own workflow. Feel free to fork and adapt.
