# Applied mods

Herdr version at the last change: `herdr-app 0.1.16`.

Active layout: `main-pause` (a clone of `main`). Back to the original:
`herdr-app do layout.switch '{"name":"main"}'` (or `ctrl-alt-shift-escape`).

| Mod / layout (clone) | Original | Base version | What it does | State |
|---|---|---|---|---|
| `pause-menu` | `menu` | 0.1.16 | Adds Pause / Resume (tab) and Pause space / Resume space to the right-click menu | applied |
| `pause-tabs` | `tabs` | 0.1.16 | Opens `pause-menu`; runs the pause requests and shows the result in a toast | applied |
| `pause-spaces` | `spaces` | 0.1.16 | Opens `pause-menu` instead of `menu`; nested spaces (child under parent, foldable) via the `herdr-mods.parent` label; done/blocked dot on each row | applied |
| `toast-close` | `toast` | 0.1.16 | ✕ button to close a notification without running its action | applied |
| `pause-agents` | `agents` | 0.1.16 | Agents section as an accordion: folded it is an "Agents ›" bar with how many need you; click unfolds / folds | applied |
| `main-pause` (layout) | `main` | 0.1.16 | Uses `pause-spaces`, `pause-tabs`, `pause-agents` (folded, 30 px) and `"toast": "toast-close"` | applied |

## Pause/resume from the menu

How it works:

- `pause-menu` looks at `terminals()`: a terminal of the tab (or of any tab of the
  space) with the label `herdr.paused=1` can be resumed; with `herdr.pausable=1` (and
  not paused), paused. It shows "Pause" / "Resume" (tab) or "Pause space" /
  "Resume space" only when there is one. Only in spaces of this computer (`machine` null).
- When picked, the menu leaves the request in `shared("herdr-mods.pause")` =
  `{ id, at, cmd, args, what }` and closes. A closed popup cancels its tasks, so
  `pause-tabs`, which is always in the layout, runs the command:
  `~/.local/bin/hc-pause --wait <tN...>` or `~/.local/bin/hc-resume <tN...>`
  (10 min timeout). One toast says it started and another shows the output when it
  ends (a warning if any line starts with `✗` or `?`). A request older than 15 s is ignored.
- For a space, the explicit terminals are passed instead of `--space <id>`. That way
  only the pausable or paused ones go, and the script still orders the coordinator
  (last when pausing, first when resuming).
- `--wait`: if the session is working, the pause waits for the turn to finish.

Changes (search for `herdr-mods` in the code):

- `pause-menu/main.js`: import `setShared`; new functions `sessions()` and
  `pauseItems()`; items in `case "tab"` and `case "space"` (before Close);
  `menuIcon(command, args)` with the new icons; `choose()` handles `"pause"`.
  New icons: `pause-menu/pause.svg`, `pause-menu/play.svg`.
- `pause-tabs/main.js`: import `setShared, notify, exec, home, checking`;
  `pauseRequest()` function before the class; `render(cx)` calls it; right click
  opens `pause-menu`.
- `pause-spaces/main.js`: `menu(w)` opens `pause-menu`.
- `layouts/main-pause.json`: `content.mod` of the `spaces` and `tabs` blocks →
  `pause-spaces` and `pause-tabs` (JSON: no comments).

## Close notifications with ✕

The original `toast` only closes with a click anywhere (which also runs its action,
e.g. going to the agent) or when it times out. Changes:

- `toast-close/main.js`: import `svg`; the root `h_flex` becomes `.relative().pr(36)`
  and adds, at the end, a `#toast-close` button in the top right corner
  (`.absolute().top(6).right(6)`) with `mods/pane/close.svg`, which calls
  `closeOverlay` and stops propagation (it does not run the action).
- `layouts/main-pause.json`: at the root, `"toast": "toast-close"`.

## Nested spaces (parent / children)

Contract (shared with the `herdr-sessions` skill, which makes the coordinators
follow it): a space is a **child** of space X if one of its terminals (label
`herdr.space=<child's id>`, or in a pane of its tabs) has the label
`herdr-mods.parent=<id of space X>`. Without that label it is top-level (root).
Generic: no fixed paths. Remote ids: labels use ids local to their machine and the
mod adds the terminal's `<machine>/` prefix (if the value already has a `/`, it is
used as is).

How it looks and behaves:

- The child goes under the parent, shifted 20 px per level, with `├─` / `└─` lines
  drawn (divs, not text). It nests at any depth. Worktrees still nest under their
  main checkout; if a space has a parent by label, the label wins.
- If the parent does not exist (it closed), or is on another machine, the child is
  root. Cycles are cut (one of the two becomes root).
- The relationship is remembered in the mod's localStorage (`spaces.parents`,
  child → parent) as soon as the label is seen, so the child does not un-nest if its
  coordinator restarts. It is forgotten when the child or the parent no longer exists
  (only if its machine's layout is `ready`, so nothing is deleted while a remote
  machine is loading).
- The parent has an arrow on the right to fold/unfold (`spaces.folded`,
  remembered). Folded it shows `● N ›`: how many spaces are inside and a dot with
  their most urgent status (blocked > done > working; no dot if they are idle). An
  active child is still shown while the parent is folded (for scrolling to the
  active space).
- Actual order: `ordered()` builds the list with the children after the parent and
  applies it with the same simulated `space.move` as always (no loops). Moving a
  child elsewhere puts it back under the parent; moving the parent drags its children.
- Rail (sidebar < 160 px): a child gets a small bar on the left; a folded parent
  shows the most urgent status among itself and its children, a small bar below and
  the count in the tooltip. The rail has no arrow (fold from the wide sidebar).

Changes in `pause-spaces/main.js` (search for `herdr-mods`):

- import `terminals`; constants and helpers at the top: `PARENT`, `INDENT`,
  `URGENT`, `urgent()`, `machineOf()`, `readObject()`.
- `rowHeight` takes `depth` (children get a 28 px row).
- `init`: `this.parents` and `this.foldedSpaces` from localStorage.
- New methods `parentsOf(sp, ps)` (labels → memory → valid parents without cycles)
  and `toggleFold(id)`.
- `ordered()`: the worktree loop becomes a recursive `emit()` function that adds
  children (with `depth`, `kid`, `kids`, `hidden`, `folded`) and worktrees; a safety
  net so no space is left out; the `return` filters out the ones hidden by a fold.
- New methods `foldToggle()` (arrow + summary; its `mouse_down` stops propagation so
  it neither selects nor drags the row) and `branchLines()`.
- `row()`: indentation by `depth` (worktrees and children), the child's lines and the arrow.
- `compact()`: the child's bar, combined status and the folded parent's tooltip.

### "Needs you" dot on the expanded row

Each expanded row shows, at the far right (after git and the fold arrow), the same
dot as the Agents section: `div().size(7).mx(3).rounded(4)`, in `t.blocked` if
`w.status === "blocked"` and in `t.done` if it is `"done"`; nothing for
working/idle. `w.status` is the space's own (its agents), so on a folded parent they
coexist without duplicating: the arrow's `● N` summarizes the children and the row's
dot is the parent's. The rail does not change (it already had its glyph).
Change: `row()`, a `.when(...)` at the end of the `h_flex` (marked `herdr-mods`).
Tested with test spaces: one blocked, one done, and a done parent with a blocked
child, expanded and folded. For a space to be `done` it has to go through `working`
and then `idle` while nobody is looking at it: a direct `state=done` shows as idle.

Tested in the app (0.1.16) with a parent and two children in a test space: nested,
folded (with a `blocked` child → red dot), rail expanded and folded, `space.move` of
a child to the very top (it comes back) and of the parent (the children follow), a
child without the label (still nested thanks to the memory) and a closed parent (the
children become root and the memory is cleared). The real click on the arrow could
not be tested from an agent (no desktop control): the fold was forced in `init` for
the screenshot.

## Agents section as an accordion

The section used to be hidden (`"hidden": true`). Now it is always there, as an accordion:

- **Folded** (default): a 30 px "Agents ›" bar sits at the bottom of the sidebar and
  Spaces takes the rest. On the right, how many need you: `! N` (blocked, the mod's
  same compact "!") and `● N` (done, the dot); nothing if none. It counts **every**
  agent from `agents()` in blocked/done, sub-agents with a pane included (the mod's
  list shows them idle because `kidStatus` turns done→idle, but tabs and spaces mark
  them), and sub-agents without a pane in blocked/error. Tooltip: "Show agents: 1 need you, 2 done".
- **Click on the bar**: it unfolds to the size it had when folded (weight, or px if a
  drag had fixed it); if nothing was saved, `weight: 1` (half and half with Spaces,
  like the original `main`).
- **Unfolded**: the header is "Agents ⌄" + the sort button. A click on the header
  folds it; the sort button stops propagation (does not fold) and opens its popup as before.
- **Rail** (sidebar < 160 px): folded it shows the most urgent status (`!` or `●`, or
  `›` if none) and the usual `»` to go back to the wide sidebar (on macOS it is the
  only button for that; the `»` stops propagation). Unfolded, a 24 px strip with `⌄`
  at the top folds it; the rest is the original rail (numbers + `»`).
- **Dragging the divider** still works (`sidebar-lists` is resizable). The state is
  derived from the block's real height (`on_size_change`; before the first layout,
  from `layout()`): under 56 px = folded, so dragging it almost to the bottom also
  shows the bar.

How: folding = `layout.resize {id:"spaces", weight:1}` + `layout.resize {id:"agents", px:30}`
(saves the previous size in the mod's localStorage, `accordion.open`); unfolding =
`layout.resize {id:"agents", ...}` with what was saved. They are layout clicks: they
are kept in `layouts/.state/` and survive restarts. To force them from the terminal:
`herdr-app do layout.resize '{"id":"agents","weight":1}'` (unfold) or
`'{"id":"agents","px":30}'` (fold).

Changes (search for `herdr-mods`):

- `pause-agents/main.js`: constants `BAR`, `FOLDED_BELOW` and `agentsSize()` at the
  top; new methods `accordionFolded()`, `toggleAccordion()`, `sized(el)` (id `root` +
  `on_size_change`) and `accordionBar(t, collapsed, needs)`; in `render`, when folded
  it returns the bar before building the rows; the root goes through `sized()`; on the
  rail, an `#ag-head` strip with `⌄`; on the wide sidebar, the header becomes a
  clickable `#ag-head` with the chevron, and `#ag-sort` calls `stop_propagation`. (The
  `mod.clone` had already changed the sort popup to `mod: "pause-agents"`.)
- `layouts/main-pause.json`: the `agents` block → `content.mod: "pause-agents"`, no
  `hidden`, `size: {px: 30}` (folded), `min: 30`.

Tested in the app (0.1.16) forcing the states with `layout.resize`: folded (`● 2` with
two done sub-agents), unfolded, folded with a test blocked agent (`! 1 ● 2`), rail
unfolded and folded (`! »`). `herdr-app check` passes and `status` has no errors. The
real mouse click (bar, header, sort button, `»`) could not be tested from an agent.

Pending: the other mods that open `menu` (`terminals-bar`, in the `terminals` layout)
were not cloned; in that layout the menu is still the original.
