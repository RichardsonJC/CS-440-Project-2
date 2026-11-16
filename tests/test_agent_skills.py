import io
from pathlib import Path

import pytest

from agent_skills import (
    SimilarityChecker,
    SkillLogger,
    SkillRegistry,
    parse_skill_file,
    split_front_matter,
    tokenize,
)
from mini_coding_agent import (
    FakeModelClient,
    MiniAgent,
    SessionStore,
    WorkspaceContext,
    build_arg_parser,
)
from mini_coding_agent import (
    build_agent as build_cli_agent,
)

REPO_SKILLS = Path(__file__).resolve().parents[1] / "skill"


def write_skill(root, folder, name=None, description="", triggers="", enabled=True, body="Do the thing."):
    path = root / folder / "skill.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = ["---"]
    if name:
        meta.append(f"name: {name}")
    if description:
        meta.append(f"description: {description}")
    if triggers:
        meta.append(f"triggers: {triggers}")
    meta.append(f"enabled: {'true' if enabled else 'false'}")
    meta.append("---")
    path.write_text("\n".join(meta) + "\n\n" + body + "\n", encoding="utf-8")
    return path


def make_skills(tmp_path):
    root = tmp_path / "skill"
    write_skill(
        root,
        "pr-review",
        name="pr-review",
        description="Review a pull request or diff for bugs and risks.",
        triggers="pull request, PR, code review, review diff, review changes",
        body="# PR Review\n\nPR-REVIEW-INSTRUCTIONS: run git diff and report findings.",
    )
    write_skill(
        root,
        "unit-tests",
        name="unit-tests",
        description="Write pytest unit tests for existing code.",
        triggers="unit test, pytest, write tests, test coverage",
        body="UNIT-TEST-INSTRUCTIONS",
    )
    write_skill(root, "lab5-skill", name="lab5-skill", description="placeholder review", enabled=False)
    write_skill(root, "_template", name="template", description="template review")
    return root


def build_skill_agent(tmp_path, outputs, threshold=0.2, **kwargs):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    workspace = WorkspaceContext.build(tmp_path)
    registry = SkillRegistry([make_skills(tmp_path)]).discover()
    logger = SkillLogger(tmp_path / "logs" / "skill_execution.log", console=False, base_dir=tmp_path)
    return MiniAgent(
        model_client=FakeModelClient(outputs),
        workspace=workspace,
        session_store=SessionStore(tmp_path / ".mini-coding-agent" / "sessions"),
        approval_policy="auto",
        skill_checker=SimilarityChecker(registry, threshold=threshold),
        skill_logger=logger,
        **kwargs,
    )


def read_log(tmp_path):
    return (tmp_path / "logs" / "skill_execution.log").read_text(encoding="utf-8")


#### Discovery ####

def test_discovery_finds_skills_and_skips_templates(tmp_path):
    registry = SkillRegistry([make_skills(tmp_path)]).discover()

    assert sorted(skill.name for skill in registry.all()) == ["lab5-skill", "pr-review", "unit-tests"]
    assert sorted(skill.name for skill in registry.enabled()) == ["pr-review", "unit-tests"]
    assert registry.get("pr-review").triggers[:2] == ["pull request", "PR"]


def test_discovery_scans_skill_and_skills_roots_and_ignores_missing(tmp_path):
    write_skill(tmp_path / "skill", "a", name="alpha")
    write_skill(tmp_path / "skills", "b", name="beta")
    (tmp_path / "skill" / "no-skill-file").mkdir()

    registry = SkillRegistry([tmp_path / "skill", tmp_path / "skills", tmp_path / "missing"]).discover()

    assert sorted(skill.name for skill in registry.all()) == ["alpha", "beta"]


def test_skill_md_is_matched_case_insensitively(tmp_path):
    folder = tmp_path / "skill" / "upper"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("Uppercase skill file.\n", encoding="utf-8")

    skill = SkillRegistry([tmp_path / "skill"]).discover().get("upper")

    assert skill is not None
    assert skill.description == "Uppercase skill file."


def test_duplicate_names_and_bad_files_are_reported_not_raised(tmp_path):
    write_skill(tmp_path / "one", "x", name="same")
    write_skill(tmp_path / "two", "y", name="same")
    bad = tmp_path / "one" / "broken" / "skill.md"
    bad.parent.mkdir()
    bad.write_text("---\nname: broken\n", encoding="utf-8")

    registry = SkillRegistry([tmp_path / "one", tmp_path / "two"]).discover()

    assert [skill.name for skill in registry.all()] == ["same"]
    assert registry.duplicates and registry.duplicates[0][0] == "same"
    assert registry.errors and "never closed" in registry.errors[0][1]


def test_front_matter_defaults_to_folder_name_and_first_paragraph(tmp_path):
    path = tmp_path / "my-skill" / "skill.md"
    path.parent.mkdir()
    path.write_text("# Title\n\nFirst paragraph\nspans lines.\n\nSecond.\n", encoding="utf-8")

    skill = parse_skill_file(path)

    assert skill.name == "my-skill"
    assert skill.description == "First paragraph spans lines."
    assert skill.enabled is True
    assert split_front_matter("no front matter") == ({}, "no front matter")


#### Similarity ####

def test_tokenize_stems_and_drops_stop_words():
    assert tokenize("Reviewing the reviews") == ["review", "review"]
    assert tokenize("changes changed change") == ["chang", "chang", "chang"]


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("Please review the changes in my pull request", "pr-review"),
        ("Can you do a code review of my diff?", "pr-review"),
        ("Write pytest tests for binary_search.py", "unit-tests"),
        ("Implement binary search in binary_search.py", None),
        ("What does this repository do?", None),
    ],
)
def test_bundled_skills_trigger_on_matching_prompts_only(prompt, expected):
    checker = SimilarityChecker(SkillRegistry([REPO_SKILLS]).discover(), threshold=0.2)

    best = checker.best(checker.score(prompt))

    assert (best.skill.name if best else None) == expected


def test_scores_are_ranked_and_disabled_skills_excluded(tmp_path):
    checker = SimilarityChecker(SkillRegistry([make_skills(tmp_path)]).discover(), threshold=0.2)

    matches = checker.score("review my pull request")

    assert [match.skill.name for match in matches] == ["pr-review", "unit-tests"]
    assert matches[0].score > matches[1].score
    assert matches[0].triggered and not matches[1].triggered
    assert all(0.0 <= match.score <= 1.0 for match in matches)


def test_threshold_blocks_weak_matches(tmp_path):
    checker = SimilarityChecker(SkillRegistry([make_skills(tmp_path)]).discover(), threshold=0.99)

    assert checker.best(checker.score("review my pull request")) is None


def test_skill_name_in_prompt_forces_name_match(tmp_path):
    checker = SimilarityChecker(SkillRegistry([make_skills(tmp_path)]).discover(), threshold=0.2)

    best = checker.best(checker.score("please use pr-review on this branch"))

    assert best.skill.name == "pr-review"
    assert best.score == 1.0
    assert best.method == "name-match"


#### Agent integration ####

def test_matching_prompt_injects_skill_and_logs_trace(tmp_path):
    agent = build_skill_agent(tmp_path, ["<final>Reviewed.</final>"])

    answer = agent.ask("Please review the changes in my pull request")

    assert answer == "Reviewed."
    prompt = agent.model_client.prompts[0]
    assert "Active skill: pr-review (skill/pr-review/skill.md)" in prompt
    assert "PR-REVIEW-INSTRUCTIONS" in prompt
    assert prompt.index("Memory:") < prompt.index("Active skill:") < prompt.index("Transcript:")
    assert any(item["role"] == "skill" and item["name"] == "pr-review" for item in agent.session["history"])

    log = read_log(tmp_path)
    order = ["PROMPT_RECEIVED", "SIMILARITY_CHECK", "SKILL_TRIGGERED", "SKILL_EXECUTION_COMPLETE"]
    positions = [log.index(event) for event in order]
    assert positions == sorted(positions)
    assert f"session={agent.session['id']}" in log
    assert 'prompt: "Please review the changes in my pull request"' in log
    assert "source=user_prompt" in log
    assert "path=skill/pr-review/skill.md" in log
    assert "1. pr-review" in log and "MATCH" in log
    assert 'final: "Reviewed."' in log


def test_unrelated_prompt_triggers_nothing_and_logs_it(tmp_path):
    agent = build_skill_agent(tmp_path, ["<final>Done.</final>"])

    agent.ask("Implement binary search")

    assert "Active skill:" not in agent.model_client.prompts[0]
    log = read_log(tmp_path)
    assert "NO_SKILL_TRIGGERED" in log
    assert "| SKILL_TRIGGERED |" not in log
    assert "SKILL_EXECUTION_COMPLETE" not in log


def test_active_skills_reset_between_requests(tmp_path):
    agent = build_skill_agent(tmp_path, ["<final>One.</final>", "<final>Two.</final>"])

    agent.ask("review my pull request")
    agent.ask("Implement binary search")

    assert "Active skill:" in agent.model_client.prompts[0]
    assert "Active skill:" not in agent.model_client.prompts[1]


def test_agent_can_request_skill_mid_execution(tmp_path):
    agent = build_skill_agent(
        tmp_path,
        [
            '<tool>{"name":"use_skill","args":{"query":"unit-tests"}}</tool>',
            "<final>Tests written.</final>",
        ],
    )

    answer = agent.ask("Implement binary search")

    assert answer == "Tests written."
    assert "Active skill:" not in agent.model_client.prompts[0]
    assert "UNIT-TEST-INSTRUCTIONS" in agent.model_client.prompts[1]
    tool_event = next(item for item in agent.session["history"] if item["role"] == "tool")
    assert tool_event["content"].startswith("activated skill unit-tests")
    log = read_log(tmp_path)
    assert "source=agent_request" in log
    assert "SKILL_EXECUTION_COMPLETE | skill=unit-tests steps=1" in log


def test_use_skill_reports_no_match(tmp_path):
    agent = build_skill_agent(tmp_path, [])

    result = agent.run_tool("use_skill", {"query": "bake a cake"})

    assert result.startswith("no skill matched")
    assert agent.active_skills == []
    assert "error: invalid arguments" in agent.run_tool("use_skill", {"query": ""})


def test_prefix_lists_enabled_skills_only(tmp_path):
    agent = build_skill_agent(tmp_path, [])

    assert "Available skills (load with use_skill):" in agent.prefix
    assert "- pr-review: Review a pull request" in agent.prefix
    assert "lab5-skill" not in agent.prefix
    assert "use_skill(query: str)" in agent.prefix


def test_child_agents_do_not_run_skills(tmp_path):
    agent = build_skill_agent(
        tmp_path,
        [
            '<tool>{"name":"delegate","args":{"task":"review the pull request","max_steps":1}}</tool>',
            "<final>child done</final>",
            "<final>parent done</final>",
        ],
    )

    agent.ask("Implement binary search")

    assert "Active skill:" not in agent.model_client.prompts[1]
    assert read_log(tmp_path).count("PROMPT_RECEIVED") == 1


def test_logger_echoes_to_console_stream(tmp_path):
    stream = io.StringIO()
    logger = SkillLogger(tmp_path / "x.log", console=True, stream=stream, session_id="s1")

    logger.prompt_received("hello", "user_prompt")

    assert "[skills]" in stream.getvalue()
    assert "session=s1 | PROMPT_RECEIVED | source=user_prompt" in stream.getvalue()
    assert (tmp_path / "x.log").read_text(encoding="utf-8").count("PROMPT_RECEIVED") == 1


#### CLI ####

def test_cli_builds_agent_with_skills_and_logs_discovery(tmp_path):
    write_skill(tmp_path / "skill", "local", name="local-skill", description="local only")
    args = build_arg_parser().parse_args(["--cwd", str(tmp_path), "--quiet-skills"])

    agent = build_cli_agent(args)

    names = {skill.name for skill in agent.skill_checker.registry.all()}
    assert {"local-skill", "pr-review"} <= names
    log = (tmp_path / "logs" / "skill_execution.log").read_text(encoding="utf-8")
    assert "SKILL_DISCOVERY" in log and "local-skill" in log


def test_cli_no_skills_restores_original_behaviour(tmp_path):
    args = build_arg_parser().parse_args(["--cwd", str(tmp_path), "--no-skills"])

    agent = build_cli_agent(args)

    assert agent.skill_checker is None
    assert "use_skill" not in agent.tools
    assert "Available skills" not in agent.prefix
    assert not (tmp_path / "logs").exists()
