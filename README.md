# herdr-mods

Extras for Herdr (the app + herdr-core) that set up a workflow with Claude Code
agents:

- **Admin**: a console space that opens one space per project or environment.
- **Top-level and child spaces**: each top-level space has a *coordinator*; each
  feature or ticket goes in a child space (with an optional git worktree), which
  the sidebar draws nested under its top-level space (label `herdr-mods.parent`).
- **Worker sessions** per space, with consistent names and tabs.
- **Pause and resume** sessions without closing their tab (`hc-session`,
  `hc-pause`, `hc-resume`), also from the right-click menu.
- **UI mods**: a menu with Pause/Resume, nested spaces with a status dot, the
  Agents section as an accordion, and a ✕ button on notifications.

> **Before you start**: this does **not** install Herdr or Claude Code. It goes
> on top of a setup that already works. Before running `install.sh` you need the
> **Herdr** app, **herdr-core** (`hc`), **Claude Code** (logged in), **python3**
> and **git** installed and working, and ideally **gh** logged in (see
> [Requirements](#requirements)). Open Herdr at least once before installing, so
> it creates `~/.config/herdr-app`.

`MODS.md`, `base/` and `CLAUDE.md` are for maintaining the mods when Herdr
updates (what changed in each clone and against which original). They are not
needed to install.

## What it installs

| Piece | Source in the repo | Destination |
|---|---|---|
| `herdr-sessions` skill (the workflow rules) | `skills/herdr-sessions/` | `~/.claude/skills/herdr-sessions/` |
| `herdr` skill (the `hc` manual) | generated with `hc --skill` | `~/.claude/skills/herdr/` |
| `coordinator` template | `templates/coordinator.md` | `~/.config/herdr-core/templates/` |
| `admin` template | `templates/admin.md` | `~/.config/herdr-core/templates/` |
| Pause: script + `hc-session`, `hc-pause`, `hc-resume` | `pause/herdr_pause.py` | `~/.local/share/herdr-pause/` + symlinks in `~/.local/bin/` |
| Mods `pause-menu`, `pause-tabs`, `pause-spaces`, `pause-agents`, `toast-close` | `mods/` | `~/.config/herdr-app/mods/` |
| `main-pause` layout (uses those mods) | `layouts/main-pause.json` | `~/.config/herdr-app/layouts/` |

If `CLAUDE_CONFIG_DIR` is set, the skills go there instead of `~/.claude`.

## Requirements

- macOS.
- **Herdr** (the app) and **herdr-core** (`hc`), with `herdr-app` and `hc` in
  `~/.local/bin`, as their installer leaves them. The mods are clones of Herdr
  **0.1.16** (see `MODS.md`). They work with other versions, but may lag behind
  the originals (see "When Herdr updates" in `CLAUDE.md`).
- **Claude Code** from the native installer (`~/.local/bin/claude`). Herdr starts
  processes with its own `PATH` (`~/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:…`),
  not your shell's. If `claude` lives somewhere else (e.g. npm with its own
  prefix), link it to `~/.local/bin/claude` or export `HERDR_CLAUDE=<path>`
  somewhere Herdr inherits it.
- **python3** (Homebrew's or the Command Line Tools') and **git**.
- **gh** (optional, for PRs from the sessions), logged in with the machine's account.

## Install

With everything in [Requirements](#requirements) installed and Herdr open:

```sh
git clone https://github.com/GaetanoDiRusso/herdr-mods.git ~/herdr-mods   # or wherever you like
cd ~/herdr-mods
./install.sh --dry-run               # see what it would do
./install.sh --admin                 # install + create the Admin space (with Herdr open)
```

Options:

- `--dry-run`: lists what it would create (`+`) or replace (`~`), without touching anything.
- `--admin`: creates the `Admin` space with its agent (template `admin`,
  pausable) if it does not exist. Needs the app open.
- `--admin-dir <folder>`: Admin's folder (default: `~`; created if missing).
  Claude Code does not remember trust for the home folder, so in `~` the "trust
  this folder?" dialog comes back on every start. A folder of its own (e.g.
  `~/herdr-admin`) asks only once.
- `--no-app`: does not talk to the app (no layout switch, no Admin).

It is idempotent: whatever is already identical is skipped, and anything
different is replaced, leaving `<file>.bak-<date>` next to it. Nothing is
deleted. With the app open, it also runs `herdr-app check` on each mod and
switches the window to the `main-pause` layout. If it was closed, open it and run:

```sh
herdr-app do layout.switch '{"name":"main-pause"}'
```

## After installing

1. If you did not use `--admin`, create Admin: run `./install.sh --admin` again
   with the app open.
2. In the Admin tab: "open project X in <folder>". Admin creates the top-level
   space with its coordinator. To the coordinator: "start ticket PAY-123", and it
   opens the child space. The full rules are in the `herdr-sessions` skill.
3. The first time in each folder, Claude Code asks for trust: accept it in the
   tab. The agents have a rule not to accept it themselves.

## Manual adjustments

- **Pausing a Claude opened by hand** (a "Claude Code" tab from the UI, or
  `claude` typed in a shell): not possible, because it does not run under the
  supervisor. Open it with `hc-session` instead of `claude` (same arguments).
  Coordinators, worker sessions and Admin already start with `hc-session`.
- **Back to the original UI**: `herdr-app do layout.switch '{"name":"main"}'`,
  or `ctrl-alt-shift-escape`, Herdr's emergency escape.
- **Update**: `git pull && ./install.sh`. If the `herdr` skill changed (with a
  new `hc` version), it is regenerated automatically.

## Uninstall

There is no script. Switch back to the `main` layout and delete the files in the
table above.
