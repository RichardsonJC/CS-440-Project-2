# Implementation Plan: Agent Skills Component

Each step is small enough to review on its own in the VS Code Source Control diff.

## Files

| # | File | Action | Purpose |
|---|------|--------|---------|
| 1 | `intent.md` | create | goal, success criteria, non-goals |
| 2 | `spec.md` | create | technical specification |
| 3 | `plan.md` | create | this plan |
| 4 | `agent_skills.py` | create | `Skill`, `SkillRegistry`, `SimilarityChecker`, `SkillLogger`, front-matter parser |
| 5 | `mini_coding_agent.py` | modify | wire skills into `MiniAgent` and the CLI |
| 6 | `skill/pr-review/skill.md` | create | working example skill (Lab 4) |
| 7 | `skill/unit-tests/skill.md` | create | second example, so similarity rankings have more than one candidate |
| 8 | `skill/lab5-skill/skill.md` | create | Lab 5 placeholder (`enabled: false`) |
| 9 | `skill/_template/skill.md` | create | copy-me template (skipped by discovery) |
| 10 | `tests/test_agent_skills.py` | create | unit and integration tests |
| 11 | `pyproject.toml` | modify | add `agent_skills` to `py-modules`; pin the ruff rule set (`[tool.ruff.lint]`) so CI lint is stable |
| 12 | `README.md` | modify | structure, usage, log locations |
| 13 | `scripts/demo_skills.py` | create | end-to-end demo with a scripted model (no Ollama) |
| 14 | `tests/test_mini_coding_agent.py` | modify | import order only (ruff `I001`) |

## Steps

1. **SDLC docs**: write `intent.md`, `spec.md`, `plan.md`.
2. **`agent_skills.py`**
   1. `parse_skill_file(path)`: split front matter from body, read `key: value`, apply defaults.
   2. `Skill` dataclass.
   3. `SkillRegistry(roots)`: `discover()` returns load errors and duplicates for logging; `enabled()`; `get()`.
   4. `tokenize()` / `stem()` / `STOP_WORDS`.
   5. `SimilarityChecker(registry, threshold)`: `score(query)` returns a ranked list of `SkillMatch(skill, score, method)`; `best(matches)` returns the triggered match or `None`.
   6. `SkillLogger(path, console, base_dir, session_id, stream)`: one method per event in spec §4.3.
   7. `to_path()`: accept `/` or `\` in path arguments on every OS.
3. **`mini_coding_agent.py` integration**
   1. `MiniAgent.__init__`: new optional args `skill_checker=None` (it holds the registry) and `skill_logger=None`; `self.active_skills = []`.
   2. `build_tools()`: register `use_skill` when a registry exists.
   3. `build_prefix()`: add the `Available skills:` section and a `use_skill` rule.
   4. `prompt()`: insert the active-skill block between Memory and Transcript.
   5. `ask()`: reset active skills, run `trigger_skills(user_message, "user_prompt")`, log completion before every return.
   6. `tool_use_skill()`, `validate_tool` branch, `tool_example` entry.
   7. `build_agent()`: build the registry, checker, and logger from CLI args; log discovery.
   8. `build_arg_parser()`: `--skills-dir`, `--skill-threshold`, `--skill-log`, `--quiet-skills`, `--no-skills`.
   9. `main()` / help: `/skills` command; add `/skills` to `HELP_TEXT` and `HELP_DETAILS`.
   10. Update the component banner comment (7: Agent Skills).
4. **Skill folders**: steps 6–9 in the table.
5. **Tests**: write `tests/test_agent_skills.py`; run the full suite (`python -m pytest -q`) and `ruff check .`.
6. **Calibrate the threshold**: score a set of matching and non-matching prompts against the bundled skills, confirm `0.20` separates them, and record the numbers in the README.
7. **README**: project structure tree, the Skills section (how it works, how to add a skill, flags, `/skills`), and the logs section with sample output.
8. **Manual end-to-end check**: `python scripts/demo_skills.py` (scripted model) and
   `python mini_coding_agent.py --skill-check "<prompt>"` (dry run), then inspect `logs/skill_execution.log`.
9. **QA audit**: add `--skill-check`, per-skill `model_calls_with_instructions` counting, and
   forward-slash path normalization (`to_path`, `display_path`).

## Phase 2: Lab 5 (solve Lab 4 with 3 agentic features)

| # | File | Action | Purpose |
|---|------|--------|---------|
| 15 | `skill/lab5-skill/skill.md` | replace placeholder | `lab5-vacuum-rl` skill: grid, parameters, API, six steps |
| 16 | `skill/lab5-skill/check_lab4.py` | create | 10-check grader for `lab4/vacuum_rl.py` |
| 17 | `agent_hooks.py` | create | `load_hooks`, `HookRunner` (pre_tool/post_tool, exit 2 = block) |
| 18 | `hooks.json`, `hooks/*.py` | create | shell guard (pre_tool) and Python syntax check (post_tool) |
| 19 | `mini_coding_agent.py` | modify | hooks in `run_tool`, `TOOL_CALL` logging, `--num-ctx`, `--hooks-file`, `--no-hooks`, `/hooks`, hooks passed to children |
| 20 | `agent_skills.py` | modify | `SkillLogger.tool_call` |
| 21 | `tests/test_agent_hooks.py` | create | hook tests |
| 22 | `pyproject.toml` | modify | add `agent_hooks` to `py-modules` |
| 23 | `README.md`, `intent.md`, `spec.md` | modify | Lab 5 section: features table, parameters, run commands |

Verification:
1. Validate the grader with a reference solution (kept outside the repo) and a deliberately broken one.
2. Rehearse the full run with a scripted model: skill trigger → write → syntax hook → grader 10/10 → demo → blocked `git push` → delegate → final.
3. Measure prompt size to choose `--num-ctx`.
4. Do the real Ollama run for the video.

## Out of Scope / Guardrails

- No branch switching, merging, or commits; all changes stay in the working tree for review.
- No new runtime dependencies.
