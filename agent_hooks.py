"""Hooks component (component 8) for mini-coding-agent.

Hooks are shell commands the agent runs around tool calls, configured in
``<workspace>/hooks.json``:

    {
      "pre_tool":  [{"match": "run_shell", "command": "python hooks/block_dangerous_shell.py"}],
      "post_tool": [{"match": "write_file|patch_file", "command": "python hooks/check_python_syntax.py"}]
    }

- ``{python}`` in a command is replaced by the interpreter running the agent (works on every OS).
- ``match`` is a regular expression matched against the full tool name.
- The hook receives JSON on stdin: {"event", "tool", "args", "result"} ("result" for post_tool only).
- ``pre_tool``: exit code 2 BLOCKS the tool; stdout/stderr becomes the reason the model sees.
- ``post_tool``: stdout is appended to the tool result, so the model sees it on its next step.
- Any other non-zero exit, or a timeout, is logged as a hook error and does not block.

Hooks run with the same permissions as the agent, so only use hooks.json files you trust.
"""

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HOOKS_FILE_NAME = "hooks.json"
EVENTS = ("pre_tool", "post_tool")
BLOCK_EXIT_CODE = 2
HOOK_TIMEOUT = 30


@dataclass
class Hook:
    event: str
    match: str
    command: str


@dataclass
class HookOutcome:
    blocked: bool = False
    messages: list = field(default_factory=list)


def load_hooks(path):
    """Parse hooks.json; raises ValueError with a readable message on bad config."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("hooks.json must be a JSON object")
    hooks = []
    for event, entries in data.items():
        if event not in EVENTS:
            raise ValueError(f"unknown hook event {event!r}; expected one of {EVENTS}")
        for entry in entries:
            if not isinstance(entry, dict) or not str(entry.get("command", "")).strip():
                raise ValueError(f"{event} hook needs a 'command': {entry!r}")
            match = str(entry.get("match", ".*"))
            re.compile(match)
            hooks.append(Hook(event, match, str(entry["command"])))
    return hooks


class HookRunner:
    def __init__(self, hooks, cwd, logger=None, timeout=HOOK_TIMEOUT, path=None):
        self.hooks = list(hooks)
        self.cwd = Path(cwd)
        self.logger = logger
        self.timeout = timeout
        self.path = path

    @classmethod
    def from_file(cls, path, cwd):
        """Return a runner for hooks.json at `path`, or None when the file does not exist."""
        path = Path(path)
        if not path.is_file():
            return None
        return cls(load_hooks(path), cwd, path=path)

    def log_loaded(self):
        if self.logger:
            self.logger.write(
                "HOOKS_LOADED",
                f"file={self.logger.display_path(self.path)} count={len(self.hooks)}",
                [f"{hook.event:<9} match={hook.match:<22} command={hook.command}" for hook in self.hooks],
            )

    def report(self):
        lines = [f"Hooks ({len(self.hooks)}) from {self.path}:"]
        lines += [f"- {hook.event:<9} match={hook.match:<22} {hook.command}" for hook in self.hooks]
        return "\n".join(lines)

    def matching(self, event, tool):
        return [hook for hook in self.hooks if hook.event == event and re.fullmatch(hook.match, tool)]

    def run(self, event, tool, args, result=None):
        outcome = HookOutcome()
        payload = {"event": event, "tool": tool, "args": args}
        if result is not None:
            payload["result"] = result
        for hook in self.matching(event, tool):
            try:
                proc = subprocess.run(
                    hook.command.replace("{python}", f'"{sys.executable}"'),
                    cwd=self.cwd,
                    shell=True,
                    input=json.dumps(payload),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False,
                )
                code, output = proc.returncode, (proc.stdout.strip() or proc.stderr.strip())
            except subprocess.TimeoutExpired:
                code, output = None, f"timed out after {self.timeout}s"
            blocked = event == "pre_tool" and code == BLOCK_EXIT_CODE
            status = "BLOCKED" if blocked else "ok" if code == 0 else "error"
            if self.logger:
                self.logger.write(
                    f"HOOK_{event.upper()}",
                    f"tool={tool} status={status} exit={code} command={hook.command}",
                    [line for line in (output or "(no output)").splitlines()[:8]],
                )
            if blocked:
                outcome.blocked = True
                outcome.messages.append(output or f"blocked by hook: {hook.command}")
                break
            if output and (event == "post_tool" or code != 0):
                outcome.messages.append(output)
        return outcome
