#!/bin/bash
# Installs the herdr-mods extras on a machine that already has Herdr:
# Claude Code skills, herdr-core templates, session pause/resume (hc-session,
# hc-pause, hc-resume), mods and the `main-pause` layout. Optional: the Admin space.
#
# Idempotent: whatever is already identical is skipped; anything different is
# replaced, leaving a <file>.bak-<date> backup next to it. Nothing is deleted.
#
# Usage: ./install.sh [--dry-run] [--admin] [--admin-dir <folder>] [--no-app]
#   --dry-run          show what it would do, without touching anything
#   --admin            create the Admin space with its agent (if missing)
#   --admin-dir <dir>  folder of the Admin space (default: $HOME)
#   --no-app           do not talk to the running app (no layout switch, no Admin)
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
DRY=0 ADMIN=0 NOAPP=0 ADMIN_DIR="$HOME"
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --admin) ADMIN=1 ;;
    --admin-dir) ADMIN_DIR="${2:?missing folder}"; shift ;;
    --no-app) NOAPP=1 ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
  shift
done

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
APP_HOME="${HERDR_APP_HOME:-$HOME/.config/herdr-app}"
CORE_TEMPLATES="$HOME/.config/herdr-core/templates"
PAUSE_DIR="$HOME/.local/share/herdr-pause"
BIN="$HOME/.local/bin"
STAMP="$(date +%Y%m%d-%H%M%S)"
LAYOUT=main-pause
WARN=0

say()  { printf '%s\n' "$*"; }
warn() { printf '! %s\n' "$*"; WARN=1; }
run()  { [ $DRY = 1 ] || "$@"; }  # in dry-run, the + / ~ lines already say what it would do

# Find a binary on PATH or in ~/.local/bin (where each installer puts it).
find_bin() {
  local p
  p="$(command -v "$1" 2>/dev/null || true)"
  [ -z "$p" ] && [ -x "$BIN/$1" ] && p="$BIN/$1"
  printf '%s' "$p"
}

# install_file <source> <destination> [mode]
install_file() {
  local src="$1" dst="$2" mode="${3:-}"
  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
    say "  = ${dst/#$HOME/~}"
    return
  fi
  if [ -e "$dst" ]; then
    say "  ~ ${dst/#$HOME/~} (backup: $(basename "$dst").bak-$STAMP)"
    run cp -p "$dst" "$dst.bak-$STAMP"
  else
    say "  + ${dst/#$HOME/~}"
  fi
  run mkdir -p "$(dirname "$dst")"
  run cp "$src" "$dst"
  [ -n "$mode" ] && run chmod "$mode" "$dst"
  return 0
}

# install_link <link target> <link>
install_link() {
  local target="$1" link="$2"
  if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
    say "  = ${link/#$HOME/~} -> ${target/#$HOME/~}"
    return
  fi
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    say "  ~ ${link/#$HOME/~} was a file (backup: $(basename "$link").bak-$STAMP)"
    run mv "$link" "$link.bak-$STAMP"
  else
    say "  + ${link/#$HOME/~} -> ${target/#$HOME/~}"
  fi
  run mkdir -p "$(dirname "$link")"
  run ln -sfn "$target" "$link"
}

# ------------------------------------------------------------ requirements
say "Requirements"
HERDR_APP="$(find_bin herdr-app)"; HC="$(find_bin hc)"
CLAUDE="$(find_bin claude)"; PY="$(find_bin python3)"
[ -n "$HERDR_APP" ] && say "  herdr-app: $HERDR_APP ($("$HERDR_APP" --version 2>/dev/null))" \
  || { say "✗ herdr-app (the Herdr app) is missing: install it first"; exit 1; }
[ -n "$HC" ] && say "  hc: $HC ($("$HC" --version 2>/dev/null | head -1))" \
  || { say "✗ hc (herdr-core) is missing: install it first"; exit 1; }
[ -n "$PY" ] && say "  python3: $PY" || { say "✗ python3 is missing"; exit 1; }
[ -n "$CLAUDE" ] && say "  claude: $CLAUDE" || warn "claude (Claude Code) not found: hc-session will not be able to launch it"
case "$CLAUDE" in ""|"$BIN/claude"|/opt/homebrew/bin/*|/usr/local/bin/*|/usr/bin/*) ;;
  *) warn "claude is at $CLAUDE, outside Herdr's PATH (~/.local/bin, /opt/homebrew/bin, /usr/local/bin, /usr/bin). Set HERDR_CLAUDE=$CLAUDE or link it to $BIN/claude" ;;
esac
command -v git >/dev/null || warn "git is missing (worktrees for child spaces)"
command -v gh  >/dev/null || warn "gh is missing (optional: PRs from sessions)"

WANT="$(sed -n 's/.*`herdr-app \([0-9][0-9.]*\)`.*/\1/p' "$REPO/MODS.md" | head -1)"
HAVE="$("$HERDR_APP" --version 2>/dev/null | awk '{print $NF}')"
if [ -n "$WANT" ] && [ "$WANT" != "$HAVE" ]; then
  warn "the mods are clones of Herdr $WANT and this is $HAVE: they work, but may lag"
  warn "behind the originals. See \"When Herdr updates\" in CLAUDE.md."
fi

# ------------------------------------------------------------ skills
say ""; say "Claude Code skills (${CLAUDE_DIR/#$HOME/~}/skills)"
install_file "$REPO/skills/herdr-sessions/SKILL.md" "$CLAUDE_DIR/skills/herdr-sessions/SKILL.md"

# The `herdr` skill is the hc manual: generated from the installed version.
TMP="$(mktemp -d "${TMPDIR:-/tmp}/herdr-mods-install.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
{
  printf '%s\n' '---' 'name: herdr' \
    'description: Control terminals, tabs and agent sessions in Herdr with the hc CLI. Use it when the user asks to open tabs or panes, or to launch other agents in parallel.' \
    '---' ''
  "$HC" --skill
} > "$TMP/herdr-SKILL.md"
install_file "$TMP/herdr-SKILL.md" "$CLAUDE_DIR/skills/herdr/SKILL.md"

# ------------------------------------------------------------ templates
say ""; say "herdr-core templates (${CORE_TEMPLATES/#$HOME/~})"
install_file "$REPO/templates/coordinator.md" "$CORE_TEMPLATES/coordinator.md"
install_file "$REPO/templates/admin.md" "$CORE_TEMPLATES/admin.md"

# ------------------------------------------------------------ pause
say ""; say "Pause and resume"
install_file "$REPO/pause/herdr_pause.py" "$PAUSE_DIR/herdr_pause.py" 755
for c in hc-session hc-pause hc-resume; do
  install_link "$PAUSE_DIR/herdr_pause.py" "$BIN/$c"
done

# ------------------------------------------------------------ mods and layout
say ""; say "Mods and layout (${APP_HOME/#$HOME/~})"
MODS=""
for d in "$REPO"/mods/*/; do
  m="$(basename "$d")"; MODS="$MODS $m"
  for f in "$d"*; do
    install_file "$f" "$APP_HOME/mods/$m/$(basename "$f")"
  done
done
install_file "$REPO/layouts/$LAYOUT.json" "$APP_HOME/layouts/$LAYOUT.json"

if [ $DRY = 0 ]; then
  for m in $MODS; do
    if out="$("$HERDR_APP" check "$APP_HOME/mods/$m" 2>&1)"; then
      say "  ✓ check $m"
    else
      warn "check $m failed:"; printf '%s\n' "$out" | sed 's/^/    /'
    fi
  done
fi

# ------------------------------------------------------------ running app
APP_UP=0
if [ $NOAPP = 0 ] && [ -S "$APP_HOME/herdr-app.sock" ] && "$HERDR_APP" status >/dev/null 2>&1; then
  APP_UP=1
fi

say ""; say "Active layout"
if [ $APP_UP = 1 ]; then
  CUR="$("$HERDR_APP" status | "$PY" -c 'import json,sys;print(json.load(sys.stdin).get("layout",""))')"
  if [ "$CUR" = "$LAYOUT" ]; then
    say "  = already $LAYOUT"
  else
    say "  $CUR -> $LAYOUT"
    run "$HERDR_APP" do layout.switch "{\"name\":\"$LAYOUT\"}" >/dev/null
  fi
  ERRS="$("$HERDR_APP" status | "$PY" -c 'import json,sys;print("\n".join(map(str,json.load(sys.stdin).get("errors",[]))))')"
  [ -n "$ERRS" ] && { warn "the app reports errors:"; printf '%s\n' "$ERRS" | sed 's/^/    /'; }
else
  say "  The app is not open (or --no-app). With Herdr open, run:"
  say "    herdr-app do layout.switch '{\"name\":\"$LAYOUT\"}'"
fi

# ------------------------------------------------------------ Admin
if [ $ADMIN = 1 ]; then
  say ""; say "Admin space"
  if [ $APP_UP = 0 ]; then
    warn "to create Admin, Herdr has to be open (and no --no-app)"
  elif "$HERDR_APP" ls | "$PY" -c 'import json,sys;sys.exit(0 if any(s.get("name")=="Admin" for s in json.load(sys.stdin)["spaces"]) else 1)'; then
    say "  = an Admin space already exists"
  elif "$HC" get admin >/dev/null 2>&1; then
    warn "there is an 'admin' terminal in hc but no Admin space: check with 'hc get admin'"
  elif [ $DRY = 1 ]; then
    say "  (dry-run) space.new Admin in $ADMIN_DIR + hc run admin (template admin) + Admin tab"
  else
    NEW="$("$HERDR_APP" do space.new --name Admin --folder "$ADMIN_DIR")"
    SP="$(printf '%s' "$NEW" | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["space"])')"
    TAB0="$(printf '%s' "$NEW" | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["tab"])')"
    T0="$(printf '%s' "$NEW" | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["terminal"])')"
    OUT="$("$HC" run --bg --no-parent --name admin --cwd "$ADMIN_DIR" --label herdr.space="$SP" \
      admin "Space id: $SP. Folder: $ADMIN_DIR.")"
    T="$(printf '%s' "$OUT" | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["address"])')"
    "$HC" wait "$T" --timeout 10 >/dev/null 2>&1 || true
    TAB="$("$HERDR_APP" ls | "$PY" -c 'import json,sys
d=json.load(sys.stdin);t=sys.argv[1]
print(next((x["id"] for s in d["spaces"] for x in s["tabs"] if any(y["terminal"]==t for y in x["terminals"])),""))' "$T")"
    [ -n "$TAB" ] && "$HERDR_APP" do tab.rename --id "$TAB" --name Admin >/dev/null
    "$HERDR_APP" do tab.close --id "$TAB0" --confirmed true >/dev/null || true
    "$HC" rm "$T0" >/dev/null 2>&1 || true
    say "  + Admin space ($SP), admin agent ($T) in $ADMIN_DIR"
    if printf '%s' "$OUT" | grep -q '"sent": *false'; then
      # Typical in ~: Claude Code's trust dialog. Once the user accepts it,
      # Claude sits idle without the message: send it the role (the template
      # body) and the details, which is what hc run was going to send.
      say "  Claude Code asks to trust $ADMIN_DIR: accept it in the Admin tab (waiting up to 5 min)."
      READY=0
      for _ in $(seq 1 150); do
        if "$HC" get "$T" --json 2>/dev/null | "$PY" -c 'import json,sys
s=json.load(sys.stdin).get("status") or {}
sys.exit(0 if s.get("app")=="claude-code" and s.get("state") in ("idle","done") else 1)'; then READY=1; break; fi
        sleep 2
      done
      MSG="$(awk 'BEGIN{n=0} /^---$/ && n<2 {n++; next} n>=2' "$CORE_TEMPLATES/admin.md")

Space id: $SP. Folder: $ADMIN_DIR."
      if [ $READY = 1 ]; then
        "$HC" send "$T" "$MSG" >/dev/null && say "  ✓ initial message sent to Admin"
      else
        warn "Admin did not become ready. Once you accept the dialog, send it the role and details:"
        warn "  hc send admin \"\$(awk 'BEGIN{n=0} /^---\$/ && n<2 {n++; next} n>=2' ~/.config/herdr-core/templates/admin.md)"
        warn ""
        warn "  Space id: $SP. Folder: $ADMIN_DIR.\""
      fi
    fi
  fi
fi

say ""
[ $WARN = 1 ] && say "Done, with warnings (the '!' lines above)." || say "Done."
[ $DRY = 1 ] && say "(dry-run: nothing was changed)"
exit 0
