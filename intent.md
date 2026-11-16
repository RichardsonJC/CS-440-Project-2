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

## Course Context (CS 440 Labs 4 and 5)

- **Lab 4:** this component, the SDLC documents (`intent.md`, `spec.md`,
  `plan.md`), and a working example skill (`skill/pr-review`).
- **Lab 5:** a placeholder skill folder (`skill/lab5-skill/`) is ready to be
  filled in. It is disabled until its `skill.md` is written.
