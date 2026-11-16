# Specification: Agent Skills Component

Implementation module: `agent_skills.py` (stdlib only).
Integration point: `mini_coding_agent.py` (`MiniAgent`, CLI).

---

## 1. Skill Discovery

### 1.1 Search roots

Skills are discovered from these roots, in order. Duplicate folders
(same resolved path) are loaded once.

| Order | Root | Purpose |
|------:|------|---------|
| 1 | `<workspace repo root>/skill/` | project-specific skills |
| 2 | `<workspace repo root>/skills/` | alternate folder name |
| 3 | `<agent install dir>/skill/` | skills bundled with the agent, so they work when `--cwd` points at another repo |
| 4 | each `--skills-dir PATH` | extra roots from the CLI |

### 1.2 Skill folder rules

- A skill is any **direct subdirectory** of a root that contains a file named
  `skill.md` (matched case-insensitively, so `SKILL.md` also works).
- Subdirectories whose name starts with `_` or `.` are skipped (for templates
  and scratch folders).
- If two roots define a skill with the same `name`, the first one found wins and
  the duplicate is logged as `SKILL_DUPLICATE_SKIPPED`.

### 1.3 `skill.md` format

An optional YAML-style front-matter block, then a Markdown body:

```markdown
---
name: pr-review
description: Review a pull request or diff for bugs, risks, and style issues.
triggers: pull request, PR, code review, review diff, review changes
enabled: true
---

# PR Review Skill
...instructions for the agent...
```

| Field | Required | Default | Meaning |
|-------|----------|---------|---------|
| `name` | no | folder name | unique skill id |
| `description` | no | first non-heading paragraph of the body | one-line summary, used for matching and shown to the model |
| `triggers` | no | empty | comma-separated keywords/phrases, used for matching |
| `enabled` | no | `true` | `false` keeps the skill listed but excludes it from matching |

The front-matter parser handles only `key: value` lines (no nested YAML), so no
third-party YAML library is needed. A malformed file is logged as
`SKILL_LOAD_ERROR` and skipped; it never crashes the agent.

### 1.4 Data model

```python
@dataclass
class Skill:
    name: str
    description: str
    triggers: list[str]
    instructions: str      # Markdown body (front matter removed)
    path: Path             # absolute path to skill.md
    enabled: bool
```

`SkillRegistry` holds the skills and exposes `discover()`, `enabled()`, `get(name)`.

---

## 2. Similarity & Triggering Engine

### 2.1 Method: TF-IDF + cosine similarity (stdlib)

1. **Skill document** = `name` (hyphens/underscores → spaces) + `description` +
   `triggers`. The instruction body is *not* used, because long bodies would dilute the score.
2. **Tokenizer:** lowercase, split on non-alphanumerics, drop a small built-in
   English stop-word list and 1-character tokens, apply a light suffix
   stemmer (`-ing`, `-ed`, `-s`, trailing `-e`), so that
   *review / reviews / reviewing* and *change / changes / changed* each collapse to one form.
3. **IDF** (smoothed): `idf(t) = ln((1 + N) / (1 + df(t))) + 1`, where `N` is the
   number of enabled skills. Query terms that are not in the vocabulary get
   `idf = ln(1 + N) + 1`. They still count toward the query vector's norm, so a
   long, unrelated prompt that shares one word with a skill scores low.
4. **Vectors:** `tf(t) = count(t)` (raw count), weight = `tf * idf`.
5. **Score:** `cos(q, s) = (q · s) / (|q| |s|)`, in `[0, 1]`.

### 2.2 Exact-name override

If the query (after normalization) equals a skill name, or contains the
skill name as a whole phrase (`pr-review`, `pr review`), that skill's score is
set to `1.0` and its method is labelled `name-match`. This gives a deterministic
way to call a skill by name.

### 2.3 Triggering rule

- `threshold` default **0.20**, configurable with `--skill-threshold`.
- Select the top-scoring enabled skill. It triggers iff `score >= threshold`.
- Ties are broken by name (alphabetical) for determinism.
- At most one skill is activated per similarity check (`top_k = 1`).

### 2.4 Trigger points

| Source | When | Label in log |
|--------|------|--------------|
| User prompt | start of every `MiniAgent.ask()` call (top-level agent only, `depth == 0`) | `user_prompt` |
| Agent mid-execution | the model calls the `use_skill` tool with a `query` describing what it needs | `agent_request` |

---

## 3. Execution Pipeline

1. **Startup:** `build_agent()` builds a `SkillRegistry` and `SkillLogger`, runs
   discovery (logged), and passes them to `MiniAgent`.
2. **Stable prefix:** `build_prefix()` adds an `Available skills:` section listing
   each enabled skill's name and description, plus a rule telling the model it may
   call `use_skill`. This section changes only when the skill set changes, so
   prompt-prefix caching still works.
3. **Per request:** `ask()` clears `self.active_skills`, runs the similarity
   check on the user message, and if a skill triggers:
   - appends it to `self.active_skills`
   - records a transcript entry `{"role": "skill", "name": ..., "content": "activated ..."}`
   - logs `SKILL_TRIGGERED`
4. **Injection:** `prompt()` inserts, between `Memory:` and `Transcript:`:

   ```text
   Active skill: pr-review (skill/pr-review/skill.md)
   Follow these skill instructions for the current request:
   <skill.md body, clipped to 6000 chars>
   ```

   This block is rebuilt for every model call in the request, so the
   instructions are never lost to transcript compression.
5. **Mid-execution:** the `use_skill(query: str)` tool (non-risky) runs the same
   similarity check. If a skill triggers, the tool adds it to `active_skills`
   (from the next model call on, it is injected as in step 4) and returns
   the scores. If nothing triggers, it returns the scores and says no skill matched.
6. **Completion:** when `ask()` returns, each skill that was active is logged
   as `SKILL_EXECUTION_COMPLETE` with the step count and a clipped final answer.
7. **Child agents** (`delegate`) do not run skills. They are read-only helpers
   and inherit the parent's context through notes.
8. **Disabled mode:** `--no-skills` builds no registry. The agent then behaves
   exactly as before.

---

## 4. Audit & Logging

### 4.1 Destinations

| Destination | Default | Override |
|-------------|---------|----------|
| File (append, UTF-8) | `<workspace repo root>/logs/skill_execution.log` | `--skill-log PATH` |
| Console (stderr, so stdout answers stay clean) | on | `--quiet-skills` |

The `logs/` directory is created on demand.

### 4.2 Line format

Each event is one header line followed by zero or more indented detail lines:

```text
<ISO-8601 UTC timestamp> | session=<id> | <EVENT> | key=value ...
    <detail line>
```

### 4.3 Events

| Event | Header fields | Detail lines |
|-------|---------------|--------------|
| `SKILL_DISCOVERY` | `roots=<n> found=<n> enabled=<n>` | one per skill: `name  [enabled/disabled]  path` |
| `SKILL_LOAD_ERROR` | `path=...` | error message |
| `SKILL_DUPLICATE_SKIPPED` | `name=... path=...` | none |
| `PROMPT_RECEIVED` | `source=user_prompt\|agent_request` | `prompt: "<text, clipped to 500 chars>"` |
| `SIMILARITY_CHECK` | `method=tfidf-cosine threshold=0.20 candidates=<n>` | one row per enabled skill, sorted by score: `rank  name  score=0.4312  method  MATCH\|below-threshold  path` |
| `SKILL_TRIGGERED` | `skill=<name> score=<s> source=... path=<path>` | `injected <n> chars of instructions into the prompt` |
| `NO_SKILL_TRIGGERED` | `best=<name\|none> best_score=<s> threshold=<t>` | none |
| `SKILL_EXECUTION_COMPLETE` | `skill=<name> steps=<n>` | `final: "<answer, clipped to 300 chars>"` |

### 4.4 Example

```text
2026-11-16T21:04:11+00:00 | session=20261116-160411-a1b2c3 | PROMPT_RECEIVED | source=user_prompt
    prompt: "Please review the changes in my pull request"
2026-11-16T21:04:11+00:00 | session=20261116-160411-a1b2c3 | SIMILARITY_CHECK | method=tfidf-cosine threshold=0.20 candidates=2
    1. pr-review    score=0.7310  tfidf-cosine  MATCH            skill/pr-review/skill.md
    2. unit-tests   score=0.0000  tfidf-cosine  below-threshold  skill/unit-tests/skill.md
2026-11-16T21:04:11+00:00 | session=20261116-160411-a1b2c3 | SKILL_TRIGGERED | skill=pr-review score=0.7310 source=user_prompt path=skill/pr-review/skill.md
    injected 1496 chars of instructions into the prompt
```

Paths are written relative to the workspace root when possible, and absolute otherwise.

---

## 5. CLI & REPL Additions

| Flag | Default | Effect |
|------|---------|--------|
| `--skills-dir PATH` (repeatable) | none | extra discovery root |
| `--skill-threshold FLOAT` | `0.20` | trigger threshold |
| `--skill-log PATH` | `logs/skill_execution.log` | log file |
| `--quiet-skills` | off | no console skill logging |
| `--no-skills` | off | disable the component |

REPL command `/skills` lists discovered skills with their status and path.

## 6. Testing

New tests in `tests/test_agent_skills.py` (no network; `FakeModelClient`):
discovery and front-matter parsing, disabled and `_template` skipping,
similarity ranking and threshold behaviour, name-match override, prompt
injection, the `use_skill` tool path, log file contents, and `--no-skills` parity.
