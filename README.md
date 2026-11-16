&nbsp;
# Mini-Coding-Agent

This folder contains a small standalone coding agent:

- code: `mini_coding_agent.py`
- CLI: `mini-coding-agent`

It is a minimal local agent loop with:

- workspace snapshot collection
- stable prompt plus turn state
- structured tools
- approval handling for risky tools
- transcript and memory persistence
- bounded delegation

The model backend is currently based on Ollama.

<a href="https://magazine.sebastianraschka.com/p/components-of-a-coding-agent">
  <img src="https://substack-post-media.s3.amazonaws.com/public/images/49b97718-57f4-4977-99c8-8ad5c4d32af3_1548x862.png" width="500px">
</a>

<br>

**[The detailed tutorial: Components of a Coding Agent](https://magazine.sebastianraschka.com/p/components-of-a-coding-agent)**


&nbsp;
## Six Core Components

<a href="https://magazine.sebastianraschka.com/p/components-of-a-coding-agent">
  <img alt="Six core components of a coding agent" src="https://sebastianraschka.com/images/github/mini-coding-agent/six-components.webp" width="500px">
</a>

This coding harness is organized around six practical building blocks:

1. **Live repo context**  
   The agent collects stable workspace facts upfront, such as repo layout, instructions, and git state.
2. **Prompt shape and cache reuse**  
   A stable prompt prefix, which is separate from the changing request, transcript, and memory so repeated model calls can reuse the static parts efficiently.
3. **Structured tools, validation, and permissions**  
   The model works through named tools with checked inputs, workspace path validation, and approval gates instead of free-form arbitrary actions.
4. **Context reduction and output management**  
   Long outputs are clipped, repeated reads are deduplicated, and older transcript entries are compressed to keep prompt size under control.
5. **Transcripts, memory, and resumption**  
   The runtime keeps both a full durable transcript and a smaller working memory so sessions can be resumed while preserving important state via working memory.
6. **Delegation and bounded subagents**  
   Scoped subtasks can be delegated to helper agents that inherit enough context to help (but operate within limits).

This fork adds a seventh component (CS 440 Lab 4):

7. **Agent skills**  
   Skill folders (`skill/<name>/skill.md`) are discovered at startup. Each prompt is scored against every skill with TF-IDF cosine similarity. The best match above a threshold has its `skill.md` instructions injected into the prompt, and every step is logged to `logs/skill_execution.log`. See [Agent Skills](#agent-skills).

&nbsp;
## Project Structure

```text
CS-440-Project-2/
├── mini_coding_agent.py        # the agent: components 1-6 plus skill wiring (component 7)
├── agent_skills.py             # component 7: skill discovery, similarity checker, audit logger
├── skill/                      # skill library: one folder per skill, each with a skill.md
│   ├── pr-review/skill.md      # working example: pull-request / diff review (Lab 4)
│   ├── unit-tests/skill.md     # second example: write and run pytest tests
│   ├── lab5-skill/skill.md     # Lab 5 placeholder (enabled: false until filled in)
│   └── _template/skill.md      # copy-me template (folders starting with "_" are ignored)
├── logs/
│   └── skill_execution.log     # created on first run: prompt -> similarity scores -> triggered skill
├── tests/
│   ├── test_mini_coding_agent.py
│   └── test_agent_skills.py    # tests for the skills component
├── intent.md                   # SDLC: goal and success criteria
├── spec.md                     # SDLC: technical specification
├── plan.md                     # SDLC: implementation plan
├── EXAMPLE.md
├── pyproject.toml
└── README.md
```

Sessions are stored separately under `<workspace>/.mini-coding-agent/sessions/` (git-ignored).

&nbsp;
## Requirements

You need:

- Python 3.10+
- Ollama installed
- an Ollama model pulled locally

Optional:

- `uv` for environment management and the `mini-coding-agent` CLI entry point

This project has no Python runtime dependency beyond the standard library, so you can run it directly with `python mini_coding_agent.py` if you do not want to use `uv`.

&nbsp;
## Install Ollama

Install Ollama on your machine so the `ollama` command is available in your shell.

Official installation link: [ollama.com/download](https://ollama.com/download)

Then verify:

```bash
ollama --help
```

Start the server:

```bash
ollama serve
```

In another terminal, pull a model. Example:

```bash
ollama pull qwen3.5:4b
```

Qwen 3.5 model library:

- [ollama.com/library/qwen3.5](https://ollama.com/library/qwen3.5)

The default in this project is `qwen3.5:4b`. If you have sufficient memory, it is worth trying a larger model such as `qwen3.5:9b` or another larger Qwen 3.5 variant. The agent just sends prompts to Ollama's `/api/generate` endpoint.

&nbsp;
## Project Setup

Clone the repo or your fork and change into it:

```bash
git clone https://github.com/rasbt/mini-coding-agent.git
cd mini-coding-agent
```

If you forked it first, use your fork URL instead:

```bash
git clone https://github.com/<your-github-user>/mini-coding-agent.git
cd mini-coding-agent
```



&nbsp;
## Basic Usage

Start the agent:

```bash
cd mini-coding-agent
uv run mini-coding-agent
```

Without `uv`, run the script directly:

```bash
cd mini-coding-agent
python mini_coding_agent.py
```

By default it uses:

- model: `qwen3.5:4b`
- approval: `ask`

For a concrete usage example, see [EXAMPLE.md](EXAMPLE.md).

&nbsp;
## Approval Modes

Risky tools such as shell commands and file writes are gated by approval.

- `--approval ask`
  prompts before risky actions (default and recommended)
- `--approval auto`
  allows risky actions automatically, including arbitrary command execution and file writes by the model; use only with trusted prompts and trusted repositories
- `--approval never`
  denies risky actions

Example:

```bash
uv run mini-coding-agent --approval auto
```



&nbsp;
## Resume Sessions

The agent saves sessions under the target workspace root in:

```text
.mini-coding-agent/sessions/
```

Resume the latest session:

```bash
uv run mini-coding-agent --resume latest
```


Resume a specific session:

```bash
uv run mini-coding-agent --resume 20260401-144025-2dd0aa
```


&nbsp;
## Interactive Commands

Inside the REPL, slash commands are handled directly by the agent instead of
being sent to the model as a normal task.

- `/help`
  shows the list of available interactive commands
- `/memory`
  prints the distilled session memory, including the current task, tracked files, and notes
- `/session`
  prints the path to the current saved session JSON file
- `/skills`
  lists discovered skills (enabled/disabled), their paths, the threshold, and the skill log path
- `/reset`
  clears the current session history and distilled memory but keeps you in the REPL
- `/exit`
  exits the interactive session
- `/quit`
  exits the interactive session; alias for `/exit`

&nbsp;
## Main CLI Flags

```bash
uv run mini-coding-agent --help
```

Without `uv`:

```bash
python mini_coding_agent.py --help
```

CLI flags are passed before the agent starts. Use them to choose the workspace,
model connection, resume behavior, approval mode, and generation limits.

Important flags:

- `--cwd`
  sets the workspace directory the agent should inspect and modify; default: `.`
- `--model`
  selects the Ollama model name, such as `qwen3.5:4b`; default: `qwen3.5:4b`
- `--host`
  points the agent at the Ollama server URL (usually not needed); default: `http://127.0.0.1:11434`
- `--ollama-timeout`
  controls how long the client waits for an Ollama response (usually not needed); default: `300` seconds
- `--resume`
  resumes a saved session by id or uses `latest`; default: start a new session
- `--approval`
  controls how risky tools are handled: `ask`, `auto`, or `never`; default: `ask`
- `--max-steps`
  limits how many model and tool turns are allowed for one user request; default: `6`
- `--max-new-tokens`
  caps the model output length for each step; default: `512`
- `--temperature`
  controls sampling randomness; default: `0.2`
- `--top-p`
  controls nucleus sampling for generation; default: `0.9`

Agent skills flags:

- `--skills-dir PATH`
  adds another directory of `<name>/skill.md` folders; repeatable
- `--skill-threshold FLOAT`
  minimum similarity score needed to trigger a skill; default: `0.20`
- `--skill-log PATH`
  skill audit log file, relative to the workspace root; default: `logs/skill_execution.log`
- `--quiet-skills`
  stops echoing skill log events to the terminal (the log file is still written)
- `--no-skills`
  turns the skills component off completely, restoring the original agent behaviour

&nbsp;
## Agent Skills

### How it works

1. **Discovery.** At startup the agent scans `<workspace>/skill/`, `<workspace>/skills/`, the `skill/` folder bundled next to `mini_coding_agent.py`, and any `--skills-dir`. Every subfolder that contains a `skill.md` becomes a skill. Folders starting with `_` or `.` are skipped.
2. **Similarity check.** For every user prompt, `agent_skills.SimilarityChecker` computes a **TF-IDF cosine similarity** (standard library only) between the prompt and each enabled skill's `name + description + triggers`. If the prompt contains a skill's name (for example `pr-review`), that skill gets a score of `1.0` (`name-match`).
3. **Trigger.** The top-scoring skill triggers if its score is at least the threshold (`0.20` by default).
4. **Execution.** The triggered `skill.md` body is injected into the prompt as an `Active skill:` section, between `Memory:` and `Transcript:`, for every model call in that request. The available skills are also listed in the stable prompt prefix.
5. **Mid-task skills.** The model can call the `use_skill` tool (`{"query": "<skill name or need>"}`) during a task. It runs the same similarity check and, on a match, activates that skill for the rest of the request.
6. **Logging.** Each step is written to `logs/skill_execution.log` and echoed to the terminal (stderr).

Full details: [spec.md](spec.md). Design rationale: [intent.md](intent.md). Build steps: [plan.md](plan.md).

### Writing a skill

```markdown
---
name: pr-review
description: Review a pull request, diff, or set of code changes for bugs, risks, missing tests, and style issues.
triggers: pull request, PR, code review, review diff, review changes, git diff
enabled: true
---

# PR Review Skill
Step-by-step instructions for the agent...
```

Matching uses only `name`, `description`, and `triggers`, so make those specific. The body is what the agent follows once the skill triggers. To add a skill, copy `skill/_template/` to `skill/<your-skill>/`, edit it, and restart the agent. Run `/skills` to confirm it loaded.

**Lab 5:** fill in `skill/lab5-skill/skill.md` (it explains what to change) and set `enabled: true`.

### Try it

```bash
# triggers skill/pr-review
python mini_coding_agent.py "Please review the changes in my pull request"

# triggers nothing (logged as NO_SKILL_TRIGGERED)
python mini_coding_agent.py "Implement binary search in binary_search.py"

# stricter matching
python mini_coding_agent.py --skill-threshold 0.5 "review this PR for bugs"
```

Approximate scores against the bundled skills with the default threshold of `0.20`:

| Prompt | pr-review | unit-tests | Triggered |
|--------|----------:|-----------:|-----------|
| Please review the changes in my pull request | 0.731 | 0.000 | pr-review |
| Can you do a code review of my diff? | 0.747 | 0.042 | pr-review |
| Write pytest tests for binary_search.py | 0.019 | 0.349 | unit-tests |
| my test is failing, fix it | 0.029 | 0.343 | unit-tests |
| Implement binary search in binary_search.py | 0.000 | 0.000 | none |
| Look over my recent git changes and tell me if anything is risky | 0.086 | 0.000 | none (paraphrase; the model can still call `use_skill`) |

TF-IDF matches words, not meaning. A paraphrase that shares few words with a skill's triggers will not match, so add likely phrasings to `triggers:`.

&nbsp;
## Inspecting Skill Logs

The skill audit log is written to:

```text
<workspace>/logs/skill_execution.log
```

The same events are printed to the terminal with a `[skills]` prefix (turn this off with `--quiet-skills`). Each request produces a trace like this:

```text
2026-11-16T21:04:11+00:00 | session=20261116-160411-a1b2c3 | PROMPT_RECEIVED | source=user_prompt
    prompt: "Please review the changes in my pull request"
2026-11-16T21:04:11+00:00 | session=20261116-160411-a1b2c3 | SIMILARITY_CHECK | method=tfidf-cosine threshold=0.20 candidates=2
    1. pr-review        score=0.7310  tfidf-cosine  MATCH            skill/pr-review/skill.md
    2. unit-tests       score=0.0000  tfidf-cosine  below-threshold  skill/unit-tests/skill.md
2026-11-16T21:04:11+00:00 | session=20261116-160411-a1b2c3 | SKILL_TRIGGERED | skill=pr-review score=0.7310 source=user_prompt path=skill/pr-review/skill.md
    injected 1496 chars of instructions into the prompt
2026-11-16T21:04:30+00:00 | session=20261116-160411-a1b2c3 | SKILL_EXECUTION_COMPLETE | skill=pr-review steps=3
    final: "Summary: ... Verdict: COMMENT ..."
```

| Event | Meaning |
|-------|---------|
| `SKILL_DISCOVERY` | skills found at startup, with enabled/disabled status and paths |
| `PROMPT_RECEIVED` | the prompt being matched (`source=user_prompt`, or `agent_request` for `use_skill`) |
| `SIMILARITY_CHECK` | every candidate skill's score, ranked, with MATCH / below-threshold |
| `SKILL_TRIGGERED` | the skill that was executed: name, score, and `skill.md` path |
| `NO_SKILL_TRIGGERED` | the best score was under the threshold |
| `SKILL_EXECUTION_COMPLETE` | the request finished with that skill active: tool steps used and the final answer |
| `SKILL_LOAD_ERROR` / `SKILL_DUPLICATE_SKIPPED` | a malformed `skill.md`, or a second skill with the same name |

The session JSON in `.mini-coding-agent/sessions/` also gets a `{"role": "skill", ...}` entry each time a skill activates, and the session id in each log line identifies that file.

&nbsp;
## Example

See [EXAMPLE.md](EXAMPLE.md)

&nbsp;
## Notes & Tips

- The agent expects the model to emit either `<tool>...</tool>` or `<final>...</final>`.
- Different Ollama models will follow those instructions with different reliability.
- If the model does not follow the format well, use a stronger instruction-following model.
- The agent is intentionally small and optimized for readability, not robustness.
