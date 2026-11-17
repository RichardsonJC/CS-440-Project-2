"""End-to-end demo of the agent skills component, no Ollama required.

Runs the real agent pipeline (discovery -> similarity check -> skill.md injection ->
logging) with a scripted model in place of Ollama, so the output is identical on
every machine. Three scenarios:

  1. prompt-level trigger      user prompt matches skill/pr-review
  2. no trigger                unrelated prompt, logged as NO_SKILL_TRIGGERED
  3. mid-execution trigger     model calls use_skill during the task

Usage (from the repo root):
    python scripts/demo_skills.py
    python scripts/demo_skills.py --cwd path/to/other/workspace

Then inspect logs/skill_execution.log in the workspace.
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SCENARIOS = [
    (
        "1. Prompt-level trigger",
        "Please review the changes in my pull request",
        ["<final>Summary: scripted review. Verdict: COMMENT</final>"],
    ),
    (
        "2. No trigger",
        "Implement binary search in binary_search.py",
        ["<final>Scripted: implemented binary search.</final>"],
    ),
    (
        "3. Mid-execution trigger (model calls use_skill)",
        "Implement binary search and then make sure it is covered",
        [
            '<tool>{"name":"use_skill","args":{"query":"I need to write pytest tests for this code"}}</tool>',
            "<final>Scripted: tests written following the unit-tests skill.</final>",
        ],
    ),
]


def main(argv=None):
    sys.path.insert(0, str(REPO_ROOT))
    from mini_coding_agent import FakeModelClient, build_agent, build_arg_parser

    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--cwd", default=str(REPO_ROOT), help="Workspace to run in (logs are written there).")
    options = cli.parse_args(argv)

    for title, prompt, outputs in SCENARIOS:
        print(f"\n{'=' * 72}\n{title}\nPROMPT: {prompt}\n{'=' * 72}", flush=True)
        args = build_arg_parser().parse_args(["--cwd", options.cwd, "--approval", "never"])
        agent = build_agent(args)
        agent.model_client = FakeModelClient(outputs)
        answer = agent.ask(prompt)
        sent = agent.model_client.prompts
        injected = [skill.name for skill in agent.active_skills if any("Active skill: " + skill.name in p for p in sent)]
        print(f"ANSWER: {answer}")
        print(f"skills whose instructions reached the model: {injected or 'none'}", flush=True)

    log = Path(options.cwd).resolve() / "logs" / "skill_execution.log"
    print(f"\nFull audit trail: {log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
