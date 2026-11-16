#!/usr/bin/env python3
"""Pause and resume Claude Code sessions in Herdr without closing their tab.

Three commands (symlinks to this file in ~/.local/bin):

  hc-session [claude flags] [task]
      Supervisor: runs Claude Code as a child inside the terminal. When the
      session is paused it stays in the tab as a lightweight placeholder (no
      Claude in memory), and on resume it runs `claude --resume <id>`.
      Launch with: hc run --bg --name X --cwd C --label herdr.space=S hc-session "task"

  hc-pause <t|name> [...] [--space <id|name>] [--wait] [--list]
      Pause sessions (or every session in a space). Only quiet ones
      (idle/done); with --wait it waits for the current turn to finish.

  hc-resume <t|name> [...] [--space <id|name>]
      Resume. In a space, the coordinator first and then the rest.

While paused, anything sent with `hc send` is queued and delivered on
resume. In the tab: `r` + Enter resumes; text + Enter is queued.
"""
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import termios
import threading
import time
import tty

HOME = os.path.expanduser("~")
STATE = os.path.join(HOME, ".local/state/herdr-pause")
# Where Claude Code keeps its sessions (sessions/<pid>.json).
CONFIG_DIRS = list(dict.fromkeys(
    d for d in (os.environ.get("CLAUDE_CONFIG_DIR"), os.path.join(HOME, ".claude")) if d))


def find_claude():
    """The Claude Code binary: $HERDR_CLAUDE, the one on PATH, or the usual places.
    Herdr starts processes with its own PATH (~/.local/bin first)."""
    if os.environ.get("HERDR_CLAUDE"):
        return os.environ["HERDR_CLAUDE"]
    for p in (shutil.which("claude"), os.path.join(HOME, ".local/bin/claude"),
              "/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if p and os.access(p, os.X_OK):
            return p
    return "claude"


LAUNCHER = find_claude()
# claude flags kept on resume (the rest, e.g. the task, are not).
KEEP_FLAGS_WITH_VALUE = {"--settings", "--model", "--permission-mode", "--add-dir", "--agent", "--effort"}
KEEP_FLAGS_BOOL = {"--dangerously-skip-permissions", "--verbose"}


# ---------------------------------------------------------------- helpers hc

def hc(*args, check=False):
    r = subprocess.run(["hc", *args, "--json"], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"hc {' '.join(args)}: {r.stderr.strip() or r.stdout.strip()}")
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except json.JSONDecodeError:
        return {}


def hc_get(t):
    d = hc("get", t)
    return d if isinstance(d, dict) and d.get("address") else None


def hc_label(t, **kv):
    subprocess.run(["hc", "label", t, *[f"{k}={v}" for k, v in kv.items()]],
                   capture_output=True)


def hc_live_terminals():
    d = hc("ls")
    items = d.get("terminals", []) if isinstance(d, dict) else d
    out = []
    for it in items or []:
        addr = it.get("address") if isinstance(it, dict) else it
        g = hc_get(addr)
        if g:
            out.append(g)
    return out


def state_dir(t):
    p = os.path.join(STATE, t)
    os.makedirs(p, exist_ok=True)
    return p


def read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def session_of_pid(pid):
    for d in CONFIG_DIRS:
        info = read_json(os.path.join(d, "sessions", f"{pid}.json"))
        if info and info.get("sessionId"):
            info["configDir"] = d
            return info
    return None


def herdr_tab_of(t):
    try:
        d = json.loads(subprocess.run(["herdr-app", "ls"], capture_output=True, text=True).stdout)
    except Exception:
        return None, None
    for s in d.get("spaces", []):
        for tab in s.get("tabs", []):
            if any(x.get("terminal") == t for x in tab.get("terminals", [])):
                return tab.get("id"), tab.get("name")
    return None, None


def herdr_rename_tab(tab_id, name):
    if tab_id:
        subprocess.run(["herdr-app", "do", "tab.rename", "--id", tab_id, "--name", name],
                       capture_output=True)


# ------------------------------------------------------------- supervisor

def resume_flags(args):
    keep, i = [], 0
    while i < len(args):
        a = args[i]
        name = a.split("=", 1)[0]
        if name in KEEP_FLAGS_WITH_VALUE:
            if "=" in a:
                keep.append(a)
            elif i + 1 < len(args):
                keep += [a, args[i + 1]]
                i += 1
        elif a in KEEP_FLAGS_BOOL:
            keep.append(a)
        i += 1
    return keep


def wait_claude_ready(pid, timeout=180):
    """Wait until the Claude with that pid has registered its session and is quiet."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = session_of_pid(pid)
        if info and info.get("status") in ("idle", "done"):
            return info
        time.sleep(1)
    return None


def deliver_queue_when_ready(t, queue, pid):
    """Thread: once the resumed Claude is quiet, deliver the queued messages."""
    if not queue:
        return
    wait_claude_ready(pid)
    time.sleep(1)
    parts = [f"[Messages that arrived while this session was paused ({len(queue)})]"]
    for q in queue:
        parts.append(f"--- {q['at']} ({q['via']}):\n{q['text']}")
    subprocess.run(["hc", "send", t, "\n\n".join(parts)], capture_output=True)


def supervisor(args):
    t = os.environ.get("HC_TERMINAL_ID")
    if not t:
        os.execvp(LAUNCHER, [LAUNCHER, *args])  # outside hc: plain claude
    # Marks "already running under hc-session", in case whatever launches claude
    # redirects to hc-session: no loop. It is this terminal's tN; another terminal has another.
    os.environ["HC_SESSION_CHILD"] = t
    sd = state_dir(t)
    hc_label(t, **{"herdr.pausable": "1"})
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # ctrl+c is for Claude
    base_flags = resume_flags(args)
    run_args = list(args)
    pending_queue = []
    while True:
        child = subprocess.Popen([LAUNCHER, *run_args])
        write_json(os.path.join(sd, "child.json"), {"pid": child.pid})
        if pending_queue:
            threading.Thread(target=deliver_queue_when_ready,
                             args=(t, pending_queue, child.pid), daemon=True).start()
            pending_queue = []

        def fwd(sig, _frm, c=child):
            try:
                c.send_signal(sig)
            except Exception:
                pass
        signal.signal(signal.SIGTERM, fwd)
        signal.signal(signal.SIGHUP, fwd)
        code = child.wait()
        req = read_json(os.path.join(sd, "pause.json"))
        if not req:
            hc_label(t, **{"herdr.pausable": ""})
            try:
                os.remove(os.path.join(sd, "child.json"))
            except FileNotFoundError:
                pass
            sys.exit(code)  # normal exit: as usual (in a manual tab, back to the shell)
        os.remove(os.path.join(sd, "pause.json"))
        pending_queue = placeholder(t, req)  # returns on resume
        run_args = [*base_flags, "--resume", req["sessionId"]]


# ------------------------------------------------------------ placeholder

PASTE_START, PASTE_END = b"\x1b[200~", b"\x1b[201~"


def placeholder(t, req):
    sd = state_dir(t)
    qpath = os.path.join(sd, "queue.json")
    queue = read_json(qpath, []) or []
    since = time.strftime("%Y-%m-%d %H:%M")
    tab_id, tab_name = herdr_tab_of(t)
    orig_tab = req.get("tabName") or tab_name
    if orig_tab and not orig_tab.startswith("⏸"):
        herdr_rename_tab(tab_id, f"⏸ {orig_tab}")
    hc_label(t, **{"herdr.paused": "1", "herdr.paused_sid": req["sessionId"],
                   "herdr.paused_since": since})
    write_json(os.path.join(sd, "paused.json"), {**req, "since": since, "tabName": orig_tab})

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    out = sys.stdout

    def w(s):
        out.write(s.replace("\n", "\r\n"))
        out.flush()

    def banner(msg=""):
        w("\x1b[?2004h\x1b[2J\x1b[H")
        w(f"  \x1b[1m⏸  Session paused\x1b[0m   (Claude Code is not running)\n\n")
        w(f"  terminal : {t}   {req.get('name') or ''}\n")
        w(f"  session  : {req['sessionId']}\n")
        w(f"  folder   : {req.get('cwd')}\n")
        w(f"  since    : {since}\n")
        w(f"  queued   : {len(queue)} message(s) to deliver on resume\n\n")
        w("  \x1b[1mr\x1b[0m + Enter → resume     ·     text + Enter → queue a message\n")
        w("  (or from another session: hc-resume " + t + ")\n\n")
        if msg:
            w(f"  {msg}\n")
        w("  > ")

    signal.signal(signal.SIGWINCH, lambda *_: banner())
    banner()
    buf, typed, in_paste, paste = b"", b"", False, b""
    try:
        while True:
            r, _, _ = select.select([fd], [], [], 1.0)
            if not r:
                continue
            data = os.read(fd, 4096)
            if not data:
                continue
            buf += data
            while buf:
                if in_paste:
                    i = buf.find(PASTE_END)
                    if i < 0:
                        paste += buf
                        buf = b""
                        break
                    paste += buf[:i]
                    buf = buf[i + len(PASTE_END):]
                    in_paste = False
                    text = paste.decode("utf-8", "replace").strip()
                    paste = b""
                    if text:
                        queue.append({"at": time.strftime("%Y-%m-%d %H:%M"), "via": "hc send", "text": text})
                        write_json(qpath, queue)
                        banner("✓ message queued")
                    # the Enter hc sends after the paste is dropped below
                    continue
                if buf.startswith(PASTE_START):
                    in_paste, buf = True, buf[len(PASTE_START):]
                    continue
                if PASTE_START.startswith(buf):  # incomplete sequence
                    break
                c, buf = buf[:1], buf[1:]
                if c in (b"\r", b"\n"):
                    line = typed.decode("utf-8", "replace").strip()
                    typed = b""
                    if line.lower() in ("r", "resume"):
                        w("\n  ▶ resuming…\n")
                        return queue_and_clear(t, sd, qpath, queue, tab_id, orig_tab)
                    if line:
                        queue.append({"at": time.strftime("%Y-%m-%d %H:%M"), "via": "typed", "text": line})
                        write_json(qpath, queue)
                        banner("✓ message queued")
                elif c in (b"\x7f", b"\x08"):
                    if typed:
                        typed = typed[:-1]
                        w("\b \b")
                elif c == b"\x03":
                    typed = b""
                    banner("(ctrl+c does not end this pause; r + Enter to resume)")
                elif c == b"\x1b":
                    buf = b""  # ignore other escape sequences
                elif c >= b" ":
                    typed += c
                    w(c.decode("utf-8", "replace"))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        w("\x1b[?2004l")
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)


def queue_and_clear(t, sd, qpath, queue, tab_id, orig_tab):
    for f in ("queue.json", "paused.json"):
        try:
            os.remove(os.path.join(sd, f))
        except FileNotFoundError:
            pass
    hc_label(t, **{"herdr.paused": "", "herdr.paused_sid": "", "herdr.paused_since": ""})
    if orig_tab:
        herdr_rename_tab(tab_id, orig_tab)
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()
    return queue


# ------------------------------------------------------- pause / resume CLI

def resolve_targets(argv):
    names, space, wait, i = [], None, False, 0
    while i < len(argv):
        a = argv[i]
        if a == "--space":
            space, i = argv[i + 1], i + 1
        elif a == "--wait":
            wait = True
        else:
            names.append(a)
        i += 1
    terms = []
    for n in names:
        g = hc_get(n)
        if not g:
            print(f"✗ {n}: no such terminal")
        else:
            terms.append(g)
    if space:
        for g in hc_live_terminals():
            lab = g.get("labels") or {}
            where = lab.get("where", "")
            if lab.get("herdr.space") == space or where.startswith(space + " / "):
                terms.append(g)
    return terms, wait, bool(space)


def is_coordinator(g):
    return (g.get("name") or "").endswith("-coordinator") or \
        (g.get("labels", {}).get("where", "").endswith("/ coordinator"))


def pause_one(g, wait):
    t, name = g["address"], g.get("name") or g["address"]
    lab = g.get("labels") or {}
    if lab.get("herdr.paused") == "1":
        return print(f"· {name}: already paused")
    st = g.get("status") or {}
    if st.get("app") != "claude-code":
        return print(f"· {name}: not running Claude Code, skipping")
    if lab.get("herdr.pausable") != "1":
        return print(f"✗ {name}: not launched with hc-session, cannot pause it without closing the tab "
                     f"(relaunch it with hc-session --resume <id>)")
    if st.get("state") not in ("idle", "done"):
        if not wait:
            return print(f"✗ {name}: it is '{st.get('state')}'. Wait for it to finish or use --wait")
        print(f"… {name}: waiting for the turn to finish")
        subprocess.run(["hc", "wait", t, "--timeout", "1800"], capture_output=True)
        g = hc_get(t) or g
    child = read_json(os.path.join(state_dir(t), "child.json")) or {}
    pid = child.get("pid") or (g.get("foreground") or {}).get("pid")
    info = session_of_pid(pid) if pid else None
    if not info:
        return print(f"✗ {name}: could not find the sessionId of process {pid}")
    _, tab_name = herdr_tab_of(t)
    write_json(os.path.join(state_dir(t), "pause.json"), {
        "sessionId": info["sessionId"], "cwd": info.get("cwd"), "configDir": info["configDir"],
        "name": g.get("name"), "tabName": tab_name, "requestedAt": time.time()})
    # SIGTERM to the Claude child: it exits cleanly (saves everything) and the
    # supervisor, seeing pause.json, switches to the placeholder without closing the terminal.
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return print(f"✗ {name}: process {pid} no longer exists")
    for _ in range(40):
        time.sleep(0.5)
        if ((hc_get(t) or {}).get("labels") or {}).get("herdr.paused") == "1":
            return print(f"⏸ {name}: paused (session {info['sessionId']})")
    print(f"? {name}: sent SIGTERM but the pause was not confirmed; check with hc read {t}")


def resume_one(g):
    t, name = g["address"], g.get("name") or g["address"]
    if (g.get("labels") or {}).get("herdr.paused") != "1":
        return print(f"· {name}: not paused")
    old_pid = (read_json(os.path.join(STATE, t, "child.json")) or {}).get("pid")
    subprocess.run(["hc", "keys", t, "r", "enter"], capture_output=True)
    for _ in range(40):
        time.sleep(0.5)
        pid = (read_json(os.path.join(STATE, t, "child.json")) or {}).get("pid")
        if pid and pid != old_pid:
            info = wait_claude_ready(pid, 90)
            if info:
                return print(f"▶ {name}: resumed (session {info['sessionId']})")
            return print(f"? {name}: Claude started (pid {pid}) but did not become ready; check with hc read {t}")
    print(f"? {name}: the placeholder did not respond; check with hc read {t}")


def list_paused():
    rows = [g for g in hc_live_terminals() if (g.get("labels") or {}).get("herdr.paused") == "1"]
    if not rows:
        return print("No paused sessions.")
    for g in rows:
        lab = g["labels"]
        q = read_json(os.path.join(STATE, g["address"], "queue.json"), []) or []
        print(f"⏸ {g['address']:5} {g.get('name') or '':32} {lab.get('where','')}  "
              f"since {lab.get('herdr.paused_since')}  session {lab.get('herdr.paused_sid')}  queued {len(q)}")


def main():
    prog = os.path.basename(sys.argv[0])
    argv = sys.argv[1:]
    if prog == "hc-session":
        return supervisor(argv)
    if not argv or argv[0] in ("-h", "--help"):
        return print(__doc__)
    if prog == "hc-pause":
        if argv == ["--list"]:
            return list_paused()
        terms, wait, by_space = resolve_targets(argv)
        # coordinator last: its children can still report to it
        for g in sorted(terms, key=is_coordinator):
            pause_one(g, wait)
    elif prog == "hc-resume":
        terms, _, _ = resolve_targets(argv)
        for g in sorted(terms, key=lambda g: not is_coordinator(g)):
            resume_one(g)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
