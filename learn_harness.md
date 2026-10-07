# Learn Harness Engineering — a beginner's guide, using this repo

This project doesn't just *ask* an AI agent to build a meeting-capture app. It
**engineers the environment around the agent** so the agent almost can't go
wrong. That practice is called **harness engineering**, and this repo is a
small, complete, working example of it. Every file mentioned below actually
exists here — open them as you read.

---

## 1. What is a "harness"?

Think of the AI model as an engine. An engine on a workbench is impressive but
useless — it needs a chassis, brakes, gauges, and a driver's seat before it can
do work safely. The **harness** is all of that:

| Engine (the model) | Harness (what you engineer) |
|---|---|
| Writes code when prompted | **Context files** that tell it where things are (`CLAUDE.md`) |
| Believes its work is done | **Hooks** that mechanically verify it (`.claude/hooks/pytest_stop.py`) |
| Burns context reading noise | **Subagents** that absorb the noise (`.claude/agents/test-triage.md`) |
| Forgets everything next session | **Knowledge files** that persist (`LESSONS.md`, auto-memory) |
| Improvises when unsure | **Plans and specs** that remove the guessing (`docs/superpowers/`) |
| Can run anything | **Permissions** that scope what it may run (`.claude/settings.local.json`) |

Prompting is what you say to the agent once. Harness engineering is what you
build so that *every* session, with *any* prompt, tends toward a good outcome.

---

## 2. Tour of this project's harness, piece by piece

### 2.1 `CLAUDE.md` — the map (the only file loaded automatically)

Claude Code auto-loads exactly one project file into every conversation:
`CLAUDE.md`. Context space is expensive, so this repo keeps it tiny and treats
it as a **map, not a manual**:

```
## Map (this file is the only one loaded automatically — everything else is below)
- Design spec: docs/superpowers/specs/...
- Implementation plan, task-by-task: docs/superpowers/plans/...
- Backend code: backend/app/ — tests: backend/tests/
- Test lessons: LESSONS.md
```

**The principle:** don't paste knowledge into the auto-loaded file; paste
*pointers* to knowledge. The agent reads the big documents only when it needs
them. `CLAUDE.md` also carries the two non-negotiable rules of this repo:
backend commands run from `backend/`, and **the user does all git** — the agent
must never commit.

### 2.2 `.claude/settings.local.json` — permissions and hook wiring

This file does two jobs. First, a **permission allowlist** so routine commands
don't interrupt you with prompts:

```json
"permissions": {
  "allow": ["Read", "Write", "Edit", "Bash(python *)", "Bash(python -m pytest *)", ...]
}
```

Note what's *not* on the list: `git`. That's least-privilege thinking — allow
the loop the agent needs (edit files, run tests), and leave the irreversible
action (committing) with the human.

Second, it registers the **Stop hook**:

```json
"hooks": {
  "Stop": [{ "hooks": [{ "type": "command",
    "command": "python .../.claude/hooks/pytest_stop.py" }] }]
}
```

A *Stop hook* is a program that runs automatically **every time the agent tries
to end its turn**. The agent cannot skip it, forget it, or talk its way past
it. That's the whole point: verification by machine, not by the agent's
self-assessment.

### 2.3 `.claude/hooks/pytest_stop.py` — the quality gate

This is the heart of the harness. Read the file; it's ~80 lines. What it does:

1. When the agent finishes a turn, the hook runs pytest on the backend.
2. If tests pass → exit code `0` → the turn ends normally.
3. If tests fail → exit code `2` → **the turn is blocked**, and the pytest
   output is fed back to the agent, which must keep working until green.

It also contains this repo's cleverest trick. All test files were committed
**up front** (commit "Add tests"), before their implementations exist — so the
full suite would be red for weeks. The hook solves that with a mapping:

```python
TEST_REQUIRES = {
    "test_storage.py": "app/storage.py",
    "test_pipeline.py": "app/pipeline.py",
    ...
}
```

A test file is only run **once the module it tests exists**. So tests for
unbuilt modules are *silently skipped*, not failed — but the moment the agent
creates `app/storage.py`, `test_storage.py` becomes part of the gate forever.
The bar rises automatically as the project grows.

One more detail worth studying — the failure message *teaches the agent what
to do next*:

```python
sys.stderr.write(
    "Backend pytest is RED for created modules — the turn is blocked until it passes.\n"
    "If tracebacks are large or confusing, dispatch the test-triage subagent...\n"
    "Durable, hard-won test facts are in LESSONS.md.\n\n" + proc.stdout + proc.stderr
)
```

Error messages in a harness are prompts. Don't just say "failed" — say what
the recovery procedure is.

### 2.4 `.claude/agents/test-triage.md` — a specialist subagent

A subagent is a separate, fresh agent the main agent can dispatch for a
sub-task. This one exists for a single reason: **context protection**. A
failing test suite can produce thousands of lines of tracebacks; if the main
agent reads all of that, it pollutes its working memory. Instead:

- The subagent (running a cheaper model — see `model: sonnet` in its
  frontmatter) reads the tracebacks in *its own* context.
- It has read-only-ish tools (`Read, Grep, Glob, Bash`) and an explicit rule:
  **"You diagnose; you do not fix."**
- It reports back four compact bullets: root cause with `file:line`, failing
  test ids, smallest fix, and whether this deserves a `LESSONS.md` entry.

The design lesson: give a subagent one job, the minimum tools for that job,
and a fixed report format so its output is cheap to consume.

### 2.5 `LESSONS.md` — the knowledge loop

Agents forget between sessions. `LESSONS.md` is where **durable, non-obvious
test facts** get written down so the *next* session doesn't rediscover them
the hard way. The rule (from the file itself): append an entry whenever a fix
turned on something you wouldn't guess from the traceback.

Notice how the loop closes: the Stop hook's error message points to
`LESSONS.md`, the test-triage agent is instructed to read it *and* to suggest
new entries, and `CLAUDE.md` points to it too. Knowledge files only work if
the rest of the harness keeps steering the agent into them.

### 2.6 The plan and spec — determinism instead of improvisation

- `docs/superpowers/specs/2026-06-15-meeting-capturer-v1-design.md` — *what*
  to build and why.
- `docs/superpowers/plans/2026-06-15-meeting-capturer-v1.md` — *how*, as 20
  bite-sized tasks. Every task contains the complete test code, complete
  implementation code, exact commands, and expected output ("Expected: 9
  passed"). Each task declares an **Interfaces: Consumes/Produces** block so a
  fresh agent that sees only one task still knows the exact signatures its
  neighbors use.

A plan this explicit turns "generate code and hope" into "transcribe and
verify". The agent's judgment is spent where it's valuable (diagnosis, edge
cases), not on re-deciding what a function should be called.

Every task ends with a **checkpoint, not a `git commit`** — the plan itself
enforces the "user handles git" rule, so even an agent that only reads its one
task can't violate it.

### 2.7 Auto-memory — cross-session facts about *you*

Outside the repo, Claude Code keeps a per-project memory directory
(`~/.claude/projects/<this-project>/memory/`). This project has one memory:
*"user does all git themselves; skip git steps."* Repo files teach the agent
about the project; memory teaches it about the person. Same idea, different
scope.

### 2.8 Skills (the superpowers plugin) — reusable procedures

Skills are step-by-step procedures the agent must load before certain work
(brainstorming before designing, writing-plans before planning, TDD before
implementing). The plan in this repo was produced *by* those skills — you can
see their fingerprints in its structure. Skills are the harness answer to
"the agent knows the concept but doesn't follow the discipline."

---

## 3. One turn through the whole machine

Here is what actually happens when you ask the agent to "do Task 4":

```
you: "Implement Task 4"
        │
        ▼
CLAUDE.md (auto-loaded) ──► points agent to the plan
        │
        ▼
Plan Task 4 ──► exact test code → run → red → exact impl → run → green
        │
        ▼
agent tries to end its turn
        │
        ▼
Stop hook fires: pytest runs on every test whose module now exists
        │
   ┌────┴─────┐
 green        red ──► turn BLOCKED, output fed back
   │           │
   │           ▼
   │     tracebacks huge? ──► dispatch test-triage subagent
   │           │                    │
   │           │              compact diagnosis + maybe a LESSONS.md entry
   │           ▼                    │
   │     agent fixes ◄──────────────┘
   │           │
   │           └──► Stop hook fires again ... until green
   ▼
turn ends → checkpoint → YOU review and YOU commit
```

The key property: **there is no path out of the turn that skips verification.**
That's what makes it a harness rather than a suggestion.

---

## 4. The principles (what to remember when you build your own)

1. **Gate, don't hope.** An agent saying "all tests pass" is a claim; a Stop
   hook exit code is a fact. Put verification in machinery the agent can't
   bypass.
2. **Make the gate grow with the project.** The `TEST_REQUIRES` trick means
   the bar rises automatically as modules appear. A gate that's red for weeks
   gets disabled; a gate that's always fair gets kept.
3. **Error messages are prompts.** When the gate fails, tell the agent the
   recovery procedure (dispatch triage, read LESSONS), not just that it failed.
4. **Protect the main context.** Noisy work (giant tracebacks, broad searches)
   goes to a subagent with one job, minimal tools, and a fixed report format.
5. **Auto-loaded context is a map, not a manual.** Keep `CLAUDE.md` tiny;
   point to everything else.
6. **Close the knowledge loop.** A lessons file nobody is steered into is a
   dead file. Every part of this harness points at `LESSONS.md`.
7. **Plans remove improvisation.** Complete code, exact commands, expected
   output, explicit interfaces per task. Judgment is for problems, not naming.
8. **Least privilege; humans keep the irreversible.** Allow the edit-test loop
   freely; keep `git` (and anything hard to undo) in human hands — enforced in
   *both* the permissions file and the plan's checkpoint steps, so no single
   miss breaks the rule.

---

## 5. The steps — how to do harness engineering, in order

This is the actual working procedure. Each step says **what you do** and
**what it's for** — because every harness piece exists to fix one specific
failure mode of an unharnessed agent. The steps are in dependency order: each
one builds on the previous, and this repo was built in roughly this sequence.

### Step 1 — Write the map and the house rules (`CLAUDE.md`)

**What you do:** Create the one file that is auto-loaded into every session.
Put in it: a short description of the project, *pointers* to every important
document (spec, plan, lessons, code layout), and the few rules that must never
be broken (here: "backend commands run from `backend/`" and "the user handles
all git").

**What it's for:** The agent starts every session with total amnesia about
your project. This file is the only context you are *guaranteed* it has. If a
rule isn't reachable from here, it effectively doesn't exist. Keeping it a map
(pointers) instead of a manual (contents) is deliberate: context space is
scarce, and a bloated auto-loaded file crowds out the actual work.

### Step 2 — Decide what the agent may do unattended (permissions)

**What you do:** In `.claude/settings.local.json`, allowlist the commands the
agent needs for its core loop (read, write, edit, `python -m pytest ...`) and
*deliberately leave out* anything irreversible or outward-facing (here: `git`,
so every commit passes through you).

**What it's for:** Two failure modes at once. Without an allowlist, you get
prompted for approval on every harmless test run — so you start rubber-stamping,
which defeats the review. With too broad an allowlist, the agent can take
actions you can't undo. The allowlist draws the line once, thoughtfully,
instead of fifty times, tiredly.

### Step 3 — Define "done" as something a machine can check (tests first)

**What you do:** Before implementation starts, write the tests and commit
them (this repo's "Add tests" commit created all 14 backend test files up
front, matching the plan).

**What it's for:** Every later step depends on this one. A gate (Step 4) can
only enforce a definition of done that is *mechanical*. "The code looks right"
is an opinion; "9 passed" is a fact. Committing tests up front also means the
agent can't quietly weaken them to make its own work pass — any test edit
shows up in *your* diff review.

### Step 4 — Build the gate (a Stop hook that runs the check)

**What you do:** Write a script that runs your check and register it as a
`Stop` hook (`.claude/hooks/pytest_stop.py`, wired in
`settings.local.json`). Exit `0` lets the turn end; exit `2` **blocks the
turn** and feeds the output back to the agent.

**What it's for:** This converts "please make sure tests pass" from a request
into a law of physics. An agent can forget an instruction, rationalize
skipping it, or sincerely believe it's done when it isn't. It cannot end its
turn past a hook. The gate is what makes the whole harness *load-bearing*
instead of advisory.

### Step 5 — Make the gate fair (scope it to what can pass today)

**What you do:** Scope the check so it only enforces what is currently
achievable. Here that's the `TEST_REQUIRES` mapping: a test file runs only
once the module it tests exists, so tests for unbuilt modules are skipped,
not failed.

**What it's for:** A gate that is red for reasons the agent can't fix *right
now* (the module is three tasks away) teaches everyone to ignore or disable
the gate — and a disabled gate is worse than none, because you still trust it.
A fair gate is always green-able, so red always means "a real regression you
must fix before stopping." The bonus: the bar rises automatically as modules
appear, with zero maintenance.

### Step 6 — Make failure output teach the recovery procedure

**What you do:** When the gate fails, don't just dump the error. This repo's
hook prepends: *the turn is blocked until green → if tracebacks are large,
dispatch the test-triage subagent → known gotchas are in LESSONS.md* — and
only then the pytest output.

**What it's for:** Whatever the hook prints becomes the agent's next prompt.
A bare traceback leaves the agent to improvise its response; a message that
names the procedure makes the *right* response the obvious one. This is the
cheapest step in the whole list and one of the highest-leverage: you are
prompt-engineering the failure path, which is exactly where agents go off the
rails.

### Step 7 — Add specialists for noisy work (subagents)

**What you do:** For any recurring sub-task that floods context (reading
2,000-line tracebacks, broad codebase searches), define a subagent in
`.claude/agents/` with three properties, all visible in `test-triage.md`: one
narrow job ("you diagnose; you do not fix"), minimum tools for that job
(`Read, Grep, Glob, Bash` — no `Edit`), and a fixed, compact report format.

**What it's for:** Context protection. The main agent's working memory is
where your task lives; every screenful of traceback it reads in-line evicts
something you care about. The subagent absorbs the noise in a disposable
context and returns four bullets. The narrow job and missing tools aren't
stinginess — they make the subagent *predictable*, so the main agent can trust
its report without re-verifying.

### Step 8 — Build the knowledge loop (`LESSONS.md` + memory)

**What you do:** Create a file for durable, non-obvious facts learned the
hard way (`LESSONS.md`), with a strict entry format (what bit, and the rule
that prevents it). Then — the part people forget — **point everything at it**:
this repo's hook mentions it on every failure, the triage agent must read it
and propose entries to it, and `CLAUDE.md` maps to it. Facts about *you*
rather than the code go to auto-memory instead.

**What it's for:** Sessions forget; files don't. Without this loop the agent
re-pays the same debugging cost every session. But a knowledge file nobody is
steered into is a dead file — the loop only works because the *failure path*
(Step 6) and the *diagnosis path* (Step 7) both route through it. Write once,
never re-discover.

### Step 9 — Remove improvisation with a spec and a plan

**What you do:** Before implementation, produce a design spec (the *what and
why*) and an implementation plan (the *how*) — here under `docs/superpowers/`.
Hold the plan to a hard standard: complete test code and implementation code
in every task, exact commands with expected output, and an
**Interfaces: Consumes/Produces** block per task. End every task with a
human checkpoint instead of a `git commit`.

**What it's for:** Model judgment is a budget. Every signature the agent has
to invent is a chance for two tasks to disagree (`clearLayers()` in Task 3,
`clearFullLayers()` in Task 7 — and nothing compiles). A placeholder like
"add error handling" is a decision deferred to the least-informed moment.
Spending the judgment budget at *planning* time — once, reviewed by you —
means execution time is spent on real problems: diagnosis, edge cases, the
things plans can't foresee. The Interfaces blocks exist because a fresh
executor may see only its own task; the checkpoint exists so the plan itself
enforces your Step 2 rule even for an agent that never read `CLAUDE.md`.

### Step 10 — Run it, watch it fail, tighten

**What you do:** Use the harness for real work and treat every surprise as a
bug report *against the harness*. Each surprising failure becomes exactly one
of: a new `LESSONS.md` entry (knowledge gap), a new or wider gate (verification
gap), a better failure message (procedure gap), or a plan/`CLAUDE.md` fix
(context gap). This session did exactly that: a review found the plan let an
import-time `create_app()` break the keyless test suite, so the *plan* was
fixed before the bug was ever built.

**What it's for:** A harness is a hypothesis about how the agent will fail;
reality falsifies parts of it. Steps 1–9 give you the machine; Step 10 is the
maintenance loop that keeps it matched to the failures you actually observe.
The discipline of "every surprise lands in exactly one bucket" stops the
harness from decaying into folklore.

**The order matters.** Steps 1–2 are the ground rules (cheap, do them day
one). Step 3 must precede Step 4 — a gate with nothing mechanical to check is
theater. Steps 5–6 make the gate livable; without them it gets disabled.
Steps 7–8 pay off in proportion to project size. Step 9 is the expensive one —
reserve full plans for multi-task builds. Step 10 never ends.

---

## 6. Exercises — modify the harness yourself

Do these in order; each takes a few minutes.

1. **Watch the gate work.** Break an assertion in
   `backend/tests/test_config.py`, then ask the agent to do anything trivial.
   Watch its turn get blocked and watch it fix the test before it can stop.
   (Undo your change after.)
2. **Extend the gate.** Add a new module to the app (say `app/health.py`) with
   a test file, then add one line to `TEST_REQUIRES` in
   `.claude/hooks/pytest_stop.py`. You've just raised the bar.
3. **Write a lesson.** Next time a test fails for a surprising reason, append
   a two-line entry to `LESSONS.md`: what bit you, and the rule that prevents
   it. That entry now works for every future session.
4. **Create a subagent.** Copy `.claude/agents/test-triage.md` to
   `frontend-triage.md` and adapt it for Vitest failures (`cd frontend`,
   `npm test`). Same shape: one job, minimal tools, fixed report format.
5. **Think about the next gate.** When the frontend exists, the Stop hook only
   covers pytest. What would a fair Vitest gate look like — and what is the
   frontend equivalent of `TEST_REQUIRES` that keeps it from being red before
   the frontend is built? Designing that gate *is* harness engineering.

---

## 7. Quick reference

| File | Role | One-line summary |
|---|---|---|
| `CLAUDE.md` | Context | Auto-loaded map + house rules (git is yours) |
| `.claude/settings.local.json` | Config | Permission allowlist + registers the Stop hook |
| `.claude/hooks/pytest_stop.py` | Gate | Runs pytest at end of turn; red = turn blocked |
| `.claude/agents/test-triage.md` | Subagent | Diagnoses red suites off-context; never fixes |
| `LESSONS.md` | Knowledge | Durable test gotchas, appended as discovered |
| `docs/superpowers/specs/…-design.md` | Spec | What v1 is and why |
| `docs/superpowers/plans/…-v1.md` | Plan | 20 tasks with full code, commands, interfaces |
| `~/.claude/projects/…/memory/` | Memory | Cross-session facts about you, not the code |

---

## 8. How to run everything

### 8.1 Run the harness itself

Nothing to start manually — the harness *is* the session:

```bash
cd C:/Users/DavinDewanto/Desktop/advasolutions/meeting_capturer
claude
```

Opening Claude Code in the repo root auto-loads `CLAUDE.md`, applies the
permission allowlist, and arms the Stop hook. You'll know the hook is alive
the first time a turn ends with failing tests: the agent visibly gets blocked
and keeps working instead of stopping.

### 8.2 Run the gate by hand (see what the agent sees)

```bash
python .claude/hooks/pytest_stop.py ; echo "exit code: $?"
```

Exit code `0` = the turn would end normally; `2` = the turn would be blocked,
and everything printed to stderr is what the agent would read next. Useful
whenever you change the hook — test the gate the way you'd test any code.

The plain-pytest equivalent (what the hook runs under the hood, minus the
module-existence filtering):

```bash
cd backend
python -m pytest -q
```

Current expected state: only Tasks 1–2 are built, so the hook selects
`test_config.py` + `test_models.py` → **7 passed**.

### 8.3 Run the app

Not yet possible — the API arrives in Task 14. Once the plan reaches there:

```bash
# Backend (from backend/, once per machine)
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env       # fill in OPENAI_API_KEY and ANTHROPIC_API_KEY
uvicorn --factory app.main:create_app --reload --port 8000

# Frontend (from frontend/, exists after Task 16)
npm install
npm run dev                # proxies /meetings to localhost:8000
```

Note the `--factory` flag — it exists *because of* the harness: the app is
built lazily so that importing `app.main` never demands real API keys, which
is what keeps the test suite keyless (Step 3).

### 8.4 Continue the build

Tell the agent, in a fresh session:

> Execute the implementation plan at
> `docs/superpowers/plans/2026-06-15-meeting-capturer-v1.md`, starting from
> Task 3, using subagent-driven development.

Then your job is the checkpoints: after each task the agent stops, reports,
and suggests a commit message — you review the diff and commit. The Stop hook
guards every turn in between; the test-triage agent gets dispatched
automatically when a red suite is confusing.

---

## 9. What's missing — an honest audit

A harness tutorial that pretends its harness is finished would be teaching
the wrong lesson. Step 10 said every gap lands in a bucket; here is this
repo's current gap list, each tagged with the step it belongs to. This
doubles as the to-do list for your own practice.

1. **The harness isn't committed.** `CLAUDE.md`, `LESSONS.md`, and `.claude/`
   are all untracked (`git status` shows them as `??`). A fresh clone — or a
   teammate — gets *no map, no gate, no rules*. The highest-value commit you
   can make right now is the harness itself. *(Step 1: context that isn't in
   the repo doesn't exist.)*

2. **The hook is registered with a machine-specific absolute path** in
   `settings.local.json` (`C:/Users/DavinDewanto/...`), and `local` settings
   are personal by convention. Anyone else opening this repo gets no gate.
   Fix: move the hook into a shared `.claude/settings.json` using the
   `$CLAUDE_PROJECT_DIR` variable instead of an absolute path. *(Step 4: a
   gate only one machine has is a gate the project doesn't have.)*

3. **The map points at a file that doesn't exist.** `CLAUDE.md` references a
   progress ledger at `.superpowers/sdd/progress.md` — which was never
   created, and whose parent directory is *gitignored*, so it could never be
   committed anyway. A map that lies erodes the agent's trust in the map.
   Fix: either create the ledger somewhere tracked (e.g. `docs/progress.md`)
   and update both `CLAUDE.md` and `.gitignore` thinking, or delete the
   reference. *(Step 1 hygiene.)*

4. **No frontend gate.** The Stop hook runs backend pytest only. From Task 16
   onward there will be Vitest suites that can rot without blocking a single
   turn. Fix: extend `pytest_stop.py` (or add a second hook) with a frontend
   equivalent of `TEST_REQUIRES` — exercise 5 in section 6 is exactly this
   design problem. *(Steps 4–5.)*

5. **Green can silently mean "less was tested."** The ffmpeg-guarded tests
   *skip* when ffmpeg is missing, and the hook treats skips as success. A
   machine without ffmpeg passes the gate while testing less. Fix: make the
   hook detect skips (or check `shutil.which("ffmpeg")`) and say so loudly in
   its output. *(Step 6: the gate's output should never let you misread what
   was actually verified.)*

6. **No style or type gate.** Nothing runs `ruff`, `mypy`, or `tsc` at the
   gate, so drift accumulates invisibly until it's a cleanup project. These
   are cheap to add to the same Stop hook once the codebase grows. *(Step 4:
   anything you'd manually nag about is a candidate for the gate.)*

7. **The gate only exists locally — no CI.** Push to a remote and nothing
   re-verifies anything. The same pytest selection running in GitHub Actions
   would make the gate hold even for changes that never went through a Claude
   session. *(Step 4, extended: hooks gate the agent; CI gates the repo.)*

8. **The knowledge loop is unproven.** `LESSONS.md` has zero entries. That's
   expected this early, but watch for the failure mode: the first confusing
   test failure comes and goes *without* producing entry #1. The loop only
   becomes real the first time it's used. *(Step 8.)*

9. **Housekeeping:** the permission allowlist still pins superpowers
   `5.1.0` script paths while the installed plugin is `6.1.1` — dead entries
   that do nothing but confuse the next reader. *(Step 2: an allowlist is
   documentation too; keep it true.)*

None of these are embarrassing — they're what Step 10 looks like in real
life. A harness is never finished; it's kept honest.

---

If you remember one sentence: **prompting tells the agent what to do once;
harness engineering builds the machine that makes it do the right thing every
time.**
