# Intent: Agent Skills Component for Mini-Coding-Agent

## Problem

`mini-coding-agent` has one fixed system prompt. Every request, whether it is
"review this pull request" or "write unit tests", gets the same generic
instructions. Workflows that need specialized, repeatable instructions (a review
checklist, a lab-specific procedure) must be pasted into the prompt by hand each
time, and nothing records which instructions influenced a given run.

## Goal

Add a seventh component, **Agent Skills**, that lets the agent:

1. **Discover skills** stored as folders on disk, one folder per skill, each
   holding a `skill.md` file (for example `skill/pr-review/skill.md`).
2. **Evaluate similarity** between an incoming user prompt (or a need the agent
   raises in the middle of a task) and every available skill, producing a
   numeric score per skill.
3. **Trigger and execute** the best-matching skill when its score passes a
   threshold, by loading that skill's `skill.md` instructions into the agent's
   prompt for the rest of the request.
4. **Log the execution trace** of every decision: the prompt received, the
   similarity scores for each candidate skill, and which skill (name and path)
   was triggered, or that none was.

## Success Criteria

- Dropping a new folder with a `skill.md` into `skill/` makes it available on the
  next start, with no code changes.
- A prompt such as "Review the changes in my pull request" triggers
  `skill/pr-review/skill.md`; an unrelated prompt triggers nothing.
- The model can also request a skill mid-task through a `use_skill` tool.
- `logs/skill_execution.log` and the terminal both show, per request:
  prompt → similarity scores → triggered skill.
- The component uses only the Python standard library, matching the project's
  zero-runtime-dependency design.
- Existing behaviour and tests are unchanged when no skill matches or when
  skills are disabled.

## Non-Goals

- Neural embeddings or remote embedding APIs (they would add dependencies and
  network calls; TF-IDF is enough for a small skill library).
- Executing arbitrary code shipped inside a skill folder. A skill is
  instructions only; any actions still go through the existing approval-gated tools.
- Running several skills at once for one prompt (top-1 by default; configurable later).
- MCP (the fourth Lab 5 feature): not needed to meet 3 of 4.
- Full Q-learning training (Lab 4 only prepares for it).

## Course Context (CS 440 Labs 4 and 5)

- **Project 2 (this repo):** the skills component, the SDLC documents (`intent.md`,
  `spec.md`, `plan.md`), and a working example skill (`skill/pr-review`).
- **Lab 4:** the vacuum robot task: a model-free 4x4 grid world prepared for Q-learning.
- **Lab 5:** use the agent to solve Lab 4 (vacuum robot RL grid world) with
  3 of 4 agentic features. We use **skills** (`skill/lab5-skill/`), **hooks**
  (component 8, `agent_hooks.py` + `hooks.json`), and **sub-agents** (the existing
  `delegate` tool), with chosen RL parameters (living reward -0.04,
  gamma 0.9, alpha 0.1, epsilon 0.2). Success: the agent writes
  `lab4/vacuum_rl.py`, it passes `skill/lab5-skill/check_lab4.py` (10/10),
  and the whole run is visible in `logs/skill_execution.log`.
