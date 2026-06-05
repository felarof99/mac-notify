#!/usr/bin/env python3
"""agent-notify — turn Claude Code / Codex hook events into rich mac-notify messages.

Two things make a notification useful at a glance:

  WHERE it came from  →  a precise PARA-style tmux breadcrumb, derived from the
                         *exact* pane the agent runs in ($TMUX_PANE), e.g.
                             SELF_IMPROVE › MAC_NOTIFY · w1
                         (parent › sub-session · window), matching the user's
                         `tl` / tmux-para-picker tree.

  WHAT happened       →  a one-liner. For a finished turn that's the agent's
                         final message ("what's ready"); for a Claude
                         notification it's what Claude is asking for ("what it
                         wants" — input or permission).

Usage:
    agent-notify claude            # reads the Claude hook JSON from stdin
    agent-notify codex '<json>'    # reads the Codex notify JSON from argv

Designed to never break the agent: any failure exits 0 silently.
"""

import json
import os
import re
import subprocess
import sys

# ----- tmux PARA breadcrumb ------------------------------------------------

PANE_FIELDS = [
    "session_name",
    "window_index",
    "window_name",
    "pane_index",
    "pane_id",
    "pane_current_path",
]


def _tmux(args):
    try:
        out = subprocess.run(
            ["tmux", *args], capture_output=True, text=True, timeout=3
        )
        if out.returncode != 0:
            return None
        return out.stdout
    except Exception:
        return None


def pane_info():
    """Info for the pane the agent runs in.

    Prefers $TMUX_PANE (the agent's own pane, even if the user has since
    switched windows) and falls back to the active pane.
    """
    if not os.environ.get("TMUX"):
        return None
    fmt = "\t".join("#{%s}" % f for f in PANE_FIELDS)
    target = os.environ.get("TMUX_PANE")
    raw = None
    if target:
        raw = _tmux(["display-message", "-p", "-t", target, "-F", fmt])
    if not raw:
        raw = _tmux(["display-message", "-p", "-F", fmt])
    if not raw:
        return None
    parts = raw.rstrip("\n").split("\t")
    if len(parts) != len(PANE_FIELDS):
        return None
    return dict(zip(PANE_FIELDS, parts))


def split_para(session):
    """(prefix, parent, sub) for a PARA session name.

    @proj-sub  -> ("@",  "proj", "sub")
    AREA-SUB   -> ("",   "AREA", "SUB")
    >>side-sub -> (">>", "side", "sub")
    foo        -> ("",   "foo",  None)
    Split is on the FIRST dash, matching the user's rename helpers.
    """
    prefix = ""
    body = session
    if session.startswith(">>"):
        prefix, body = ">>", session[2:]
    elif session.startswith("@"):
        prefix, body = "@", session[1:]
    if "-" in body:
        parent, sub = body.split("-", 1)
    else:
        parent, sub = body, None
    return prefix, parent, sub


def breadcrumb(pane):
    """Render the tree-style location, e.g. 'SELF_IMPROVE › MAC_NOTIFY · w1'."""
    if not pane:
        return None
    prefix, parent, sub = split_para(pane["session_name"])
    loc = prefix + parent
    if sub:
        loc += f" › {sub}"

    # Window label: prefer a meaningful manual window name, else the index.
    widx = pane.get("window_index", "")
    wname = (pane.get("window_name") or "").strip()
    if wname and wname != pane["session_name"]:
        wlabel = f"{widx}:{wname}"
    else:
        wlabel = f"w{widx}"
    loc += f" · {wlabel}"

    # Disambiguate split panes only when there's more than one.
    pidx = pane.get("pane_index", "0")
    if pidx and pidx != "0":
        loc += f".{pidx}"
    return loc


def project_from_path(path):
    if not path:
        return None
    return os.path.basename(path.rstrip("/")) or None


# ----- one-liner extraction ------------------------------------------------

_MD_PATTERNS = [
    (re.compile(r"```.*?```", re.S), " "),          # fenced code blocks
    (re.compile(r"`([^`]*)`"), r"\1"),               # inline code
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),      # images
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),   # links -> text
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),         # bold
    (re.compile(r"(?<!\w)[*_]([^*_]+)[*_](?!\w)"), r"\1"),  # italic
]


def _strip_md_inline(text):
    for pat, repl in _MD_PATTERNS:
        text = pat.sub(repl, text)
    return text


def _is_bare_heading(line):
    s = line.strip()
    return s.startswith("#") or bool(re.match(r"^[-*_]{3,}$", s))


def clean_oneliner(text, limit=150):
    """Markdown -> a single clean sentence/line, truncated for a banner."""
    if not text:
        return ""
    text = _strip_md_inline(text)

    # First substantial paragraph: skip blank lines and bare headings.
    picked = []
    started = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if started:
                break
            continue
        if _is_bare_heading(raw):
            continue
        # strip leading list / quote markers
        line = re.sub(r"^([-*+]|\d+[.)]|>)\s+", "", line)
        if not line:
            continue
        picked.append(line)
        started = True
        if len(" ".join(picked)) > 220:
            break
    para = re.sub(r"\s+", " ", " ".join(picked)).strip()
    if not para:
        return ""

    # Trim to the first sentence; grow if the opener is terse ("Done!").
    sentences = re.split(r"(?<=[.!?])\s+", para)
    out = sentences[0] if sentences else para
    i = 1
    while len(out) < 40 and i < len(sentences):
        out = (out + " " + sentences[i]).strip()
        i += 1

    if len(out) > limit:
        out = out[: limit - 1].rstrip(" ,;:-") + "…"
    return out


def last_assistant_text(transcript_path):
    """Final assistant text block from a Claude transcript JSONL (scan from end)."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return ""
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except Exception:
        return ""
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if obj.get("type") != "assistant":
            continue
        content = (obj.get("message") or {}).get("content")
        texts = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    t = (block.get("text") or "").strip()
                    if t:
                        texts.append(t)
        elif isinstance(content, str):
            texts.append(content)
        if texts:
            return "\n".join(texts)
    return ""


# ----- mac-notify dispatch -------------------------------------------------

def send(message, source, notif_id):
    exe = None
    for cand in (
        os.path.expanduser("~/go/bin/mac-notify"),
        "/usr/local/bin/mac-notify",
        "/opt/homebrew/bin/mac-notify",
    ):
        if os.path.exists(cand):
            exe = cand
            break
    if exe is None:
        exe = "mac-notify"  # rely on PATH
    args = [exe, "send", message, "--source", source]
    if notif_id:
        args += ["--id", notif_id]
    try:
        subprocess.run(args, capture_output=True, text=True, timeout=5)
    except Exception:
        pass


# ----- event handling ------------------------------------------------------

GLYPH = {"done": "✅", "waiting": "⌛", "permission": "🔐", "question": "❓", "info": "🔔"}
TOOL_LABEL = {"claude": "Claude", "codex": "Codex"}

# Notification types that fire *after* the user has already engaged (or are
# purely informational) — not worth a ping.
NOISY_NOTIFICATIONS = {"auth_success", "elicitation_complete", "elicitation_response"}


def classify_notification(message, ntype):
    nt = (ntype or "").lower()
    if nt == "elicitation_dialog":
        return "question"
    if nt == "permission_prompt":
        return "permission"
    if nt == "idle_prompt":
        return "waiting"
    blob = f"{ntype} {message}".lower()
    if "permission" in blob or "approve" in blob or "allow" in blob:
        return "permission"
    if "waiting" in blob or "idle" in blob or "input" in blob:
        return "waiting"
    return "info"


def pretool_question(payload):
    """Map an interactive tool call to (status, oneliner); (None, None) to skip.

    Fires the instant Claude asks — independent of the 60s idle_prompt — and
    carries the actual question text so the notification says what it wants.
    """
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input") or {}
    if tool == "AskUserQuestion":
        questions = ti.get("questions") or []
        first = ""
        if questions and isinstance(questions[0], dict):
            first = questions[0].get("question") or questions[0].get("header") or ""
        oneliner = clean_oneliner(first) or "Claude is asking you a question"
        if len(questions) > 1:
            oneliner += f" (+{len(questions) - 1} more)"
        return "question", oneliner
    if tool == "ExitPlanMode":
        return "question", "Plan ready for your review"
    return None, None


def handle_claude():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    event = payload.get("hook_event_name", "")
    pane = pane_info()
    crumb = breadcrumb(pane)
    proj = project_from_path(
        (pane or {}).get("pane_current_path") or payload.get("cwd")
    )

    if event == "Stop":
        # Don't fire while Claude is auto-continuing via another Stop hook.
        if payload.get("stop_hook_active"):
            return
        status = "done"
        oneliner = clean_oneliner(last_assistant_text(payload.get("transcript_path")))
        if not oneliner:
            oneliner = "Turn complete"
    elif event == "PreToolUse":
        # Interactive question/plan tools — notify the moment they're invoked.
        status, oneliner = pretool_question(payload)
        if status is None:
            return
    elif event == "Notification":
        ntype = payload.get("notification_type", "")
        if ntype in NOISY_NOTIFICATIONS:
            return
        msg = (payload.get("message") or "").strip()
        status = classify_notification(msg, ntype)
        oneliner = clean_oneliner(msg) if msg else {
            "permission": "Needs your permission",
            "waiting": "Waiting for your input",
            "question": "Claude is asking you something",
            "info": "Needs your attention",
        }[status]
    else:
        return

    dispatch("claude", status, oneliner, crumb, proj, pane, payload.get("session_id"))


def handle_codex(arg):
    try:
        payload = json.loads(arg)
    except Exception:
        return
    if payload.get("type") != "agent-turn-complete":
        return
    pane = pane_info()
    crumb = breadcrumb(pane)
    proj = project_from_path(
        (pane or {}).get("pane_current_path") or payload.get("cwd")
    )
    oneliner = clean_oneliner(payload.get("last-assistant-message", "")) or "Turn complete"
    stable = payload.get("turn-id") or payload.get("thread-id")
    dispatch("codex", "done", oneliner, crumb, proj, pane, stable)


def dispatch(tool, status, oneliner, crumb, proj, pane, stable_id):
    # WHERE: tool · breadcrumb (falls back to project dir when not in tmux)
    where = crumb or (f"📁 {proj}" if proj else "no-tmux")
    source = f"{TOOL_LABEL.get(tool, tool)} · {where}"

    # WHAT: status glyph + one-liner
    message = f"{GLYPH[status]} {oneliner}".strip()

    # Stable per-pane id so repeated turns update in place instead of stacking.
    if pane and pane.get("pane_id"):
        notif_id = f"{tool}-{pane['pane_id']}"
    elif stable_id:
        notif_id = f"{tool}-{stable_id}"
    else:
        notif_id = f"{tool}-{proj or 'misc'}"

    send(message, source, notif_id)


def main():
    if len(sys.argv) < 2:
        return
    tool = sys.argv[1]
    if tool == "claude":
        handle_claude()
    elif tool == "codex":
        arg = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
        handle_codex(arg)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never let a notifier bug block the agent.
        pass
    sys.exit(0)
