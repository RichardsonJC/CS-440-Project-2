"""pre_tool hook: block destructive or outward-facing shell commands before they run.

Exit code 2 tells the agent to block the tool call; the printed reason is shown to the model.
"""

import json
import re
import sys

BLOCKED = [
    (r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r", "recursive force delete"),
    (r"\bRemove-Item\b.*-Recurse", "recursive delete"),
    (r"\bdel\s+/s\b|\brmdir\s+/s\b", "recursive delete"),
    (r"\bgit\s+push\b", "pushing to a remote"),
    (r"\bgit\s+reset\s+--hard\b", "discarding work"),
    (r"\bgit\s+(checkout|switch)\s+(main|master)\b", "switching to the main branch"),
    (r"\bgit\s+merge\b", "merging branches"),
    (r"\b(curl|wget)\b.*\|\s*(sh|bash)\b", "piping a download into a shell"),
]


def main():
    payload = json.load(sys.stdin)
    command = str(payload.get("args", {}).get("command", ""))
    for pattern, reason in BLOCKED:
        if re.search(pattern, command, re.IGNORECASE):
            print(f"blocked by hooks/block_dangerous_shell.py ({reason}): {command}")
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
