# herdr-mods

This repo manages our **own modifications to the Herdr app** (mods, layouts,
keys), the skills and templates that define the workflow around them, and keeps
them up to date when Herdr updates. Everything in it is in English and generic:
no personal data, employers or machine-specific paths (use `~` or `${home()}`).

## How Herdr works (what matters for modifying it)

- Herdr's whole UI is configurable from files in `~/.config/herdr-app/`:
  `layouts/*.json`, `keys.json`, `settings.json`, `mods/<name>/` (JS with
  gpui-kit). Changes apply live.
- **Source of truth for the API**: `~/.config/herdr-app/AGENTS.md`,
  `herdr.d.ts` and `gpui-kit.d.ts`. Herdr rewrites them on every start to match
  the installed version. Read them before touching anything.
- **The mods and layouts that ship with Herdr are read-only.** If one is edited,
  on the next start Herdr moves it to `<name>-edited` and restores the original.
  So **never edit the originals: clone them**:
  ```sh
  herdr-app do mod.clone '{"name":"menu","as":"pause-menu"}'
  herdr-app do layout.clone '{"name":"main","as":"main-pause"}'   # switches the window to the clone
  ```
  The clone records `cloned_from: {name, version}`.
- **The cost of cloning**: clones get no updates. If Herdr changes the original,
  the clone keeps the old version until it is redone.
- Some mods name others in their code (e.g. `tabs` and `spaces` open
  `mod: "menu"`). To replace one, also clone the ones that call it and the
  layout that uses them.
- Always validate: `herdr-app check ~/.config/herdr-app/mods/<mod>` (must pass)
  and check `*.error` after editing layouts/keys/settings. To see the window:
  `herdr-app shot <file.png>`.
- Emergency escape: `ctrl-alt-shift-escape` goes back to the original `main`
  layout (sets the current layout and `keys.json` aside).
- In a mod's `exec(...)`, use absolute paths to binaries (e.g.
  `` `${home()}/.local/bin/hc-pause` ``): do not assume the `PATH`.

## Repo layout

```
README.md                what it installs and how (for users)
install.sh               idempotent installer (see the README)
MODS.md                  registry: which mods are applied, from which original and version
mods/<clone>/            our version of each cloned mod
layouts/<clone>.json     our version of each cloned layout
base/<original>@<ver>/   copy of the original exactly as it was when cloned
skills/herdr-sessions/   Claude Code skill with the rules for spaces and sessions
templates/               herdr-core templates: coordinator.md and admin.md
pause/herdr_pause.py     pause/resume (hc-session, hc-pause, hc-resume)
```

- The skill, the templates and the pause script are not Herdr's: they are ours
  and define the contract the mods rely on (e.g. the `herdr-mods.parent` label
  of child spaces, `herdr.pausable` / `herdr.paused` for pausing). What runs
  lives in `~/.claude/skills/herdr-sessions/`, `~/.config/herdr-core/templates/`
  and `~/.local/share/herdr-pause/` (see the README's table).
- The `herdr` skill (the `hc` manual) is not versioned: it is `hc --skill` with
  frontmatter, and the installer generates it.
- `base/` keeps the untouched original, so it can be compared with the new
  original on update for a 3-way merge:
  `base` → new original (what Herdr changed) and `base` → clone (what we changed).
- What lives in `~/.config/herdr-app/` (and the other destinations) is what
  runs. This repo is the versioned copy. After each change, sync both ways and
  record it in `MODS.md`.
- Test the installer without touching the machine: `HOME=<temp folder> ./install.sh --no-app`.
- Machine-specific notes go in `CLAUDE.local.md` (ignored by git).

## Applying a new mod

1. Clone the original(s) with `mod.clone` / `layout.clone`.
2. Copy the original to `base/<name>@<version>/` (version: `herdr-app --version`).
3. Make the change in the clone. Changes must be minimal and marked with
   `// herdr-mods: ...` comments so they can be found when redoing them.
4. `herdr-app check` and try it in the app.
5. Copy the clone into this repo and record it in `MODS.md`: what it does, which
   clones it touches, from which original and version, and which lines change.

## When Herdr updates

1. `herdr-app --version` and compare with the version in `MODS.md`.
2. For each clone: diff `base/<name>@<old>` against the new original in
   `~/.config/herdr-app/mods/<name>`. If it did not change, there is nothing to do.
3. If it changed: clone the original again, reapply our changes (the
   `// herdr-mods:` ones), check, try it, update `base/` and `MODS.md`.
4. Tell the user what was updated and whether anything could not be reapplied.

## Related

- Session pause/resume: `pause/herdr_pause.py`, installed in
  `~/.local/share/herdr-pause/` (`hc-pause`, `hc-resume`, `hc-session`). See
  the `herdr-sessions` skill.
