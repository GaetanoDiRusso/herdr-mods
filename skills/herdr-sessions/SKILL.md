---
name: herdr-sessions
description: Rules for working with Herdr - top-level spaces (a project or environment, opened by Admin) and child spaces (a feature/ticket/epic, opened by the top-level coordinator, with an optional git worktree); creating, naming and messaging agent sessions as tabs; talking between spaces; pausing/resuming; and closing everything when a feature is done. Use when asked to open a project or environment in a space; when a coordinator is told "let's work on / start the feature, ticket or epic X"; when creating/recreating sessions or tabs, messaging a session by name, listing the active features, or closing/finishing a feature. Complements the `herdr` skill (the hc manual), which stays the command reference.
---

# Herdr: conventions

## Concepts

- Herdr levels: **space → tab → pane** (pane = a split of a tab). Herdr has no
  level to group spaces; we build one with a label (see below).
- Two kinds of space:
  - **Top-level**: a project or environment (e.g. `Acme`, the folder that holds
    several of a company's repos, or a single repo). Opened by Admin. No label.
  - **Child**: a feature, ticket or epic inside a top-level space. Opened by the
    top-level coordinator. Its coordinator carries the label
    `herdr-mods.parent=<top-level space id>`; with it, the sidebar (mod
    `pause-spaces`) draws it nested under the top-level space.
- **One child space = one feature.** That way each coordinator has a single
  task and does not fill up with context. When it is done, the child closes; the
  top-level space stays.
- Every space has a **coordinator** that owns its lifecycle.
- A single nesting level: a child does not open children. If another feature
  comes up in a child, ask the top-level coordinator for it.

## Hierarchy: Admin → top-level → children → worker sessions

```
Admin                                         ← the user's console: opens top-level spaces
 └─ space "Acme"                              (top-level, no label)
     ├─ coordinator (acme-coordinator)        ← created by Admin, --no-parent
     │
     ├─ child space "PAY-1234"                (label herdr-mods.parent=<Acme's id>)
     │   ├─ coordinator (pay-1234-coordinator) ← created by acme-coordinator, --no-parent
     │   ├─ backend     (pay-1234-backend)     ← created by pay-1234-coordinator,
     │   └─ frontend    (pay-1234-frontend)       --outlive-parent
     └─ child space "PAY-1300"
         └─ coordinator (pay-1300-coordinator)
```

- **Admin**: a space with an agent that acts as a console (template `admin`,
  `~/.config/herdr-core/templates/admin.md`). It only opens top-level spaces
  (each with its coordinator). From Admin, "this space" does not apply.
- **Top-level coordinator**: the point of contact for the project/environment.
  Opens a child for each feature, keeps the list of active children and gets
  their reports. It may have its own worker sessions for tasks that are not a
  feature (exploring, one-off questions).
- **Child coordinator**: creates and watches the worker sessions of that
  feature, reports to the top-level coordinator and closes its space when done.
- Every coordinator is launched with the `coordinator` template
  (`~/.config/herdr-core/templates/coordinator.md`, which holds its role).
- Flags:
  - Admin → top-level coordinator: `--no-parent` (Admin does not need its notes).
  - Top-level coordinator → child coordinator: **`--no-parent`** (see
    "Why `--no-parent`" in the child section).
  - Coordinator → worker sessions: `--outlive-parent`: they survive if the
    coordinator ends, but while it lives it gets their notes.
- Verified: if the coordinator dies, its sessions stay alive but their `parent`
  still points at the old ID. A recreated coordinator has another `tN`, so it
  does **not** get their automatic notes: find them with `hc ls` / label
  `herdr.space` and ask them to report to `hc send <new tN>`.
- Internal helpers (tests, a one-off review): no `herdr.space` label, hidden,
  killed and removed when done (`hc kill <t>; hc rm <t>`). Never create tabs for these.

## Naming

`<id>` = the space's identifier:
- Top-level: the project or environment in lowercase (`Acme` → `acme`).
- Child with a ticket: the code in lowercase (`PAY-1234` → `pay-1234`).
- Child without a ticket: a short `<project>-<feature>` (`my-api-login`).

| What | Format | Example |
|---|---|---|
| Top-level space name | `<project or environment>` | `Acme`, `my-api` |
| Child space name | `<TICKET or feature>` (prefixed with `<repo> · ` if the top-level space has several repos and it is not obvious which) | `PAY-1234`, `web · PAY-1300` |
| `hc` name | `<id>-<role>` | `acme-coordinator`, `pay-1234-backend` |
| Tab name | `<role>` | `coordinator`, `backend` |
| Branch / worktree (children only) | `<TICKET or feature>` | `PAY-1234` → `<repo>-worktrees/PAY-1234` |

- `hc` name: only `a-z 0-9 - _`, **at most 32 characters**, unique among all
  live terminals. If it does not fit, shorten the project/feature.
- If the user uses another branch format (e.g. `feature/PAY-1234`), follow it.

## Folders: always the project's, never home

- Claude Code **does not remember** trust for the home folder: every new
  session there asks "Is this a project you trust?" again. In a project folder
  it is accepted once and remembered. (In testing, a new worktree in
  `<repo's parent>/<repo>-worktrees/` started without asking; still, if it shows
  up, handle it as in the `first_message.sent` step.)
- Where projects live: if the request has no folder, look for candidates (e.g.
  `find ~ -maxdepth 4 -type d -name '<project>' -not -path '*/.*'`, or where the
  other spaces are in `herdr-app ls`). If nothing turns up or there are several, ask.
- Top-level: the project folder, or the environment root if it spans several
  repos (the folder that holds them). No worktree.
- Child: the repo the feature belongs to, or a worktree of that repo.
- A space has no fixed folder: new tabs start in the focused pane's folder. When
  creating sessions, always pass an explicit `--cwd`. There is no command to
  change an existing space's folder.

## Open a top-level space (Admin does this)

Expected result: a new space with a single `coordinator` tab, in the project or
environment folder.

1. If the request does not say, ask which project/environment and, if it is not
   obvious, the folder (see above).
2. Check `herdr-app ls` and `hc ls`: if there already is a space or an
   `<id>-coordinator` for it, say so instead of duplicating.
3. If the user asks Admin for a feature or ticket: do not open a loose space.
   Open (or find) the matching top-level space and pass the request to its
   coordinator with `hc send <id>-coordinator "..."` (it opens the child).
4. Create the space (its first tab is a temporary shell):
   ```sh
   herdr-app do space.new --name "<project or environment>" --folder <folder>
   ```
   It returns `{space, tab, terminal}`: keep all three.
5. Launch the coordinator with the template:
   ```sh
   hc run --bg --no-parent --name <id>-coordinator --cwd <folder> \
     --label herdr.space=<space> coordinator \
     "Type: top-level. Project/environment: <name>. Folder: <folder>. Space id: <space>. Name prefix: <id>."
   ```
6. Rename its tab to `coordinator` (see "Create a session", step 3).
7. Only now close the initial shell tab (before this, the space would be empty)
   and remove its terminal, which is left `finished`:
   ```sh
   herdr-app do tab.close --id <tab from step 4> --confirmed true
   hc rm <terminal from step 4>
   ```
8. Check `first_message.sent` in the output of step 5:
   - `true`: done.
   - `false` (typically the trust dialog the first time in that folder):
     `hc read <id>-coordinator --lines 0`, ask the user to accept the dialog in
     the tab and, once they confirm, send the message from step 5 with
     `hc send` (read first: do not resend blindly).
9. Check with `herdr-app ls` that the space has only the `coordinator` tab.

## Open a feature in a child space (the top-level coordinator does this)

Trigger: the top-level coordinator is told "let's work on / start the feature,
ticket or epic X". Expected result: a child space with a single `coordinator`
tab, in the repo or a worktree, nested under the top-level space.

1. **Basic questions** (all together in one message, skipping the ones the
   request already answers):
   - Is there a ticket? Send me the code (or the link).
   - If the top-level space has several repos: which one (or ones)?
   - New worktree or the repo's main folder? Mention whether another active
     space works on the same repo (step 2; then a worktree avoids stepping on
     each other) and the worktree's cost (reinstalling dependencies, the trust
     dialog the first time).
2. Check the active children (see "List the active features") and
   `herdr-app ls` / `hc ls`: if there already is a space or an `<id>-coordinator`
   for that feature, say so instead of duplicating. Note whether other spaces
   work on the same repo.
3. If a worktree was chosen:
   ```sh
   git -C <repo> fetch
   git -C <repo> worktree add <repo>-worktrees/<BRANCH> -b <BRANCH> <base>
   ```
   (`<base>`: the repo's main branch unless the user says otherwise; if the
   branch already exists, `worktree add <path> <BRANCH>` without `-b`. Always
   next to the repo, never in `/tmp`.) The `<folder>` in the next steps is the
   worktree. Do not install dependencies without asking.
4. Create the child space (its first tab is a temporary shell):
   ```sh
   herdr-app do space.new --name "<TICKET or feature>" --folder <folder>
   ```
   It returns `{space, tab, terminal}`: keep all three. `<child>` = that `space`.
5. Launch the child coordinator with the template and **both labels**
   (`<parent>` = my own space's id, the one in my initial message):
   ```sh
   hc run --bg --no-parent --name <id>-coordinator --cwd <folder> \
     --label herdr.space=<child> --label herdr-mods.parent=<parent> coordinator \
     "Type: child. Project: <project>. Feature: <TICKET or feature>. Folder: <folder>. Main repo: <repo>. Worktree: <yes (branch <BRANCH>) | no>. Space id: <child>. Name prefix: <id>. Parent space: <parent> (coordinator <my hc name>)."
   ```
6. Rename its tab to `coordinator` (see "Create a session", step 3).
7. Close the initial shell tab and remove its terminal:
   ```sh
   herdr-app do tab.close --id <tab from step 4> --confirmed true
   hc rm <terminal from step 4>
   ```
8. Check `first_message.sent` in the output of step 5 (as for the top-level
   space: if it is `false`, read the tab, ask the user to accept the trust
   dialog and only then `hc send` the message).
9. Check with `herdr-app ls` that the child has only the `coordinator` tab, and
   with `hc get <id>-coordinator --json` that `labels` has `herdr.space` and
   `herdr-mods.parent`. Tell the user the new space's name.

**Why `--no-parent`** (and not `--outlive-parent`) for the child coordinator:
- With `parent` set, `hc` writes the parent a note every time the child ends a
  turn, blocks or exits. A coordinator is conversational and lives for days: it
  would flood the top-level coordinator. `--no-notify` silences the notes, but
  the child would still count in the parent's `hc wait --children` (which it
  uses to wait for *its* worker sessions) and would block those waits.
- The `parent` link is by `tN`: it breaks if the parent coordinator is
  recreated. The `herdr-mods.parent=<space id>` label is stable (a space keeps
  its id) and is what the sidebar uses.
- How the parent finds out: the child reports with an explicit `hc send` at the
  milestones that matter (PR opened, blocked waiting for a decision, done) and
  always when closing. Do not report every turn.

**Recreating a child coordinator** (it died, was converted to `hc-session`,
etc.): the new one must carry **both labels** and the same name, and its
initial message the same "Parent space: ...". If it was already created without
the label: `hc label <t> herdr-mods.parent=<parent>`. The child's other
terminals do not need `herdr-mods.parent` (only `herdr.space`).

### List the active features (top-level coordinator)

The labels are the source of truth, not the coordinator's memory:
```sh
hc ls --label herdr-mods.parent=<my space> --json
```
It returns the live coordinators of my children (`address`, `name`, `where` =
`<child space> / <tab>`). With `--all` the `finished` ones show up too (children
already closed, to clean up with `hc rm`). To get each one's space id:
`hc get <t> --json` → `labels["herdr.space"]`. A paused coordinator is still
alive and shows up.

### Report to the parent (child coordinator)

- Send to the name given in "Parent space" (`hc send <parent coordinator> "<id>: ..."`).
  If that name does not exist (the parent was recreated with another one), find
  it by label: `hc ls --label herdr.space=<parent> --json` and take the `*-coordinator`.
- Before sending, check that it is not `blocked` (see "Resolve "session X"").

## Create a session (coordinator, or when the user asks)

1. Identify the space: the one the user names or, if they say "this space", my
   terminal's (`$HC_TERMINAL_ID`). Find it with `herdr-app ls`. If it is
   ambiguous, ask.
2. Create the session with a name, tied to the space:
   ```sh
   hc run --bg --outlive-parent --name <id>-<role> --cwd <folder> \
     --label herdr.space=<space-id> hc-session "<task, if any>"
   ```
   - **`hc-session` instead of `claude`**: it runs Claude Code under the pause
     supervisor, so the session can be paused and resumed (see "Pause and
     resume"). It takes the same arguments as `claude`. Herdr starts processes
     with its own `PATH` (`~/.local/bin` first), where both live.
   - Coordinator → `--outlive-parent`. If I am not a coordinator (e.g. Admin or
     another loose session), `--no-parent` so it does not die with me. (This is
     for worker sessions; a child coordinator is created with "Open a feature in
     a child space".)
   - `--cwd`: the space's folder (repo or worktree), never `~`.
   - If it has a task, include: "report with `hc send <my name or tN>` when
     done or if you get stuck".
3. Herdr creates the tab with a number as its name. Rename it:
   ```sh
   TAB=$(herdr-app ls | python3 -c 'import json,sys;d=json.load(sys.stdin);print([t["id"] for s in d["spaces"] for t in s["tabs"] if any(x["terminal"]=="<tN>" for x in t["terminals"])][0])')
   herdr-app do tab.rename --id $TAB --name <role>
   ```
   (If the tab does not show up yet, `hc wait <name> --timeout 10` and look again.)
4. Optional: reorder with `herdr-app do tab.move --id <tab> --index <n>`.
5. Check with `herdr-app ls` and `hc read <name> --lines 0`.

Limitations:
- `herdr-app do tab.new` does **not** take an `hc` name: do not use it for this.
- `hc` has no rename: the name is only set at creation. To change it, recreate.
- Sessions created by hand from the UI have no `hc` name (only the `tN` ID).

## Tab name vs. `hc` name vs. ID

- **Tab name**: what the window shows. The user changes it from the UI at will.
  It is not an `hc` address.
- **`hc` name**: an alias for commands (`hc send pay-1234-backend "..."`). Only
  set at creation with `hc run --name`.
- **ID (`tN`)**: always exists, unique across the whole core. The safe address.

## Resolve "session X" (of space Y)

1. `herdr-app ls` and look for the tab with that name **inside the given space**.
   A matching `hc` name works too.
2. Get its `tN` and confirm with `hc get tN` that `where` is `<space> / <tab>`.
3. If no space was given and there is more than one match, **ask which one**.
4. Before `hc send`, check what is running (`hc get tN`, `hc read tN --lines 0`):
   `send` pastes text and presses Enter; in a shell it would run as a command.
   If it is `blocked`, tell the user instead of forcing it.
5. Always send to the ID or the `hc` name, never to the tab name.

## Talking between spaces

- `hc` knows nothing about spaces: any session can `hc send` / `hc wait` /
  `hc read` any other by name or ID, wherever it is.
- Automatic notes only go from child to parent. Between spaces they have to be
  asked for explicitly: "when you finish X, tell `hc send pay-1200-coordinator`".
- Dependencies: the waiting coordinator can `hc wait <name in another space>` or
  ask the other coordinator to tell it. Coordinate between coordinators; do not
  give tasks directly to another space's worker sessions.
- Top-level ↔ child: the child reports to the top-level coordinator with
  `hc send` at milestones and when closing (there are no automatic notes: it
  runs with `--no-parent`). The top-level space talks to the child's
  coordinator, never to its worker sessions. Between children of the same
  top-level space, the same as between spaces.

## Close a feature (the child coordinator does this)

When the user says the feature is done (each coordinator closes **its own**
space; the steps also work for closing a top-level space):

1. **Survey** everything in the space:
   - Sessions: `hc ls` filtered by label `herdr.space=<space>` (includes ones
     created by others) and my children.
   - Git (if there is a worktree): `git -C <worktree> status --porcelain` and
     `git -C <worktree> log @{u}..` (or without an upstream: commits that are on
     no remote branch). Uncommitted or unpushed changes would be lost.
   - Loose processes whose folder is inside the space's (dev servers, watchers):
     `lsof -a -d cwd -Fpn 2>/dev/null` and filter the paths under `<folder>`;
     also `lsof -nP -iTCP -sTCP:LISTEN` for ports. Leave out sessions of other
     spaces and processes that are not the project's.
2. **Show the plan and ask for confirmation**: which sessions it kills, which
   processes, whether it removes the worktree, whether there is unpushed work.
   Without explicit confirmation, do not go on. The branch is not deleted unless
   explicitly asked.
3. With confirmation:
   - Worker sessions: `hc kill <t>`, `hc wait <t>`, `hc rm <t>`.
   - Confirmed loose processes: `kill <pid>` (no `-9` unless they do not respond).
   - Worktree: `git -C <main repo> worktree remove <worktree>` (without
     `--force`: if it fails because of changes, say so). Then `git -C <repo> worktree prune`.
4. If I am a child: tell the top-level coordinator (see "Report to the parent")
   in a single message: what was done, the state (PR, branch, anything left
   pending) and that the space is closing.
5. Last step: say goodbye in one line with the summary and close the space,
   which ends me too:
   `herdr-app do space.close --id <space> --confirmed true`

On the top-level coordinator's side:
- **It never closes a child without the user's explicit confirmation.** If the
  user asks it to close a feature, it passes that to the child's coordinator
  (`hc send <id>-coordinator "The user asked to close the feature: follow
  'Close a feature'"`), which knows its worktree and sessions. Only if that
  coordinator no longer exists does it follow steps 1-3 and 5 itself on the
  child's space (with `--id <child>`), with confirmation.
- When a child reports it closed: the child coordinator is left `finished`;
  remove it with `hc rm <id>-coordinator` (it shows up in
  `hc ls --all --label herdr-mods.parent=<my space>`).
- When closing a top-level space with live children: list them and ask what to
  do with each. They do not close on their own; if they stay alive, their label
  points at a space that no longer exists.

## Pause and resume sessions (without closing the tab)

Pause = kill the Claude Code process (frees ~300 MB per session) but keep the
tab, the `hc` name and the `tN`. The tab shows a placeholder (~15 MB) with the
session's details that queues whatever arrives. Resume = `claude --resume <id>`
in the same tab and folder, and the queued messages are delivered.

- Code: `~/.local/share/herdr-pause/herdr_pause.py` (symlinks `hc-session`,
  `hc-pause`, `hc-resume` in `~/.local/bin`). State in
  `~/.local/state/herdr-pause/<tN>/`.
- **Only sessions launched with the `hc-session` supervisor can be paused**
  (label `herdr.pausable=1`). Launch with `hc-session` instead of `claude`:
  ```sh
  hc run --bg --outlive-parent --name <id>-<role> --cwd <folder> \
    --label herdr.space=<space> hc-session "<task>"
  ```
  `hc-session` runs `claude` (the one on `PATH`, or `$HERDR_CLAUDE` if set) and
  passes it the same arguments. Coordinators already start with `hc-session`
  (it is the template's `command`), and so does Admin if the installer created it.
- A `claude` opened by hand in a tab (from the UI or typed in a shell) is
  **not** pausable. To make it pausable, open it with `hc-session` instead of
  `claude`, or convert it (below).
- **Convert a session without the supervisor** (empty `herdr.pausable` label):
  with the session `idle`/`done`, get the `sessionId` from
  `~/.claude/sessions/<pid>.json` (or `$CLAUDE_CONFIG_DIR/sessions/`), do
  `hc kill` + `hc rm` and relaunch with the same name:
  `hc run --bg --name <name> --cwd <folder> --label herdr.space=<space> hc-session --resume <sessionId>`.
  If it was a child coordinator, also add `--label herdr-mods.parent=<parent>`
  (copy every label from `hc get <t> --json` except `where`, `herdr.pausable`
  and `herdr.seen`, which are set automatically).
  Then rename the tab and reorder it. If it is the space's only tab, first open
  a temporary one (`hc run ... "sleep 900"` with the same label) so the space
  does not close. The `tN` changes: tell the coordinator (the children point at
  the old `parent`).
- Commands:
  - `hc-pause <t|name>...` / `hc-pause --space <space-id|name>`: only pauses
    `idle`/`done` sessions; with `--wait` it waits for the turn to finish. In a
    space, the coordinator is paused last.
  - `hc-resume <t|name>...` / `hc-resume --space <...>`: the coordinator first.
  - `hc-pause --list`: paused sessions, since when, and how many queued messages.
  - In the paused tab: `r` + Enter resumes; text + Enter is queued.
- The paused tab is renamed to `⏸ <role>` and gets its name back on resume.
- How it works: `hc-pause` gets the `sessionId` from
  `~/.claude/sessions/<pid>.json`, writes `pause.json` and sends SIGTERM to the
  Claude child (it exits cleanly). The supervisor sees the marker and switches
  to the placeholder. Do not use `hc send /exit`: it arrives wrapped in
  `<hc from>` and Claude does not run it. Nor `hc keep` + a normal exit: the tab
  closes anyway.
- On resume the conversation reloads with a cold cache (the first turn costs
  more). Whatever is not in the conversation (dev servers, background tasks)
  does not survive the pause.

## Auto mode and permissions

- The auto mode classifier may deny an `hc run` if the task looks like it hides
  processes or evades supervision (it happened with a task that asked to leave
  a server "detached"). Do not reword it to get around that: tell the user so
  they approve it in the tab or adjust the task.
- After a space closes, its coordinator is left `finished` in `hc ls --all` (it
  cannot remove itself). It is harmless; Admin (top-level) or the top-level
  coordinator (child) cleans it up with `hc rm <id>-coordinator`.

## Claude Code trust dialog

If a session is stuck on "Is this a project you trust?", **do not accept it**:
tell the user so they confirm it themselves in the tab.
