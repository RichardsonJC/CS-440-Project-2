"""post_tool hook: after write_file/patch_file on a .py file, report whether it compiles.

Reads the hook payload (JSON) on stdin; prints one line that is appended to the tool result.
"""

import json
import sys
from pathlib import Path


def main():
    payload = json.load(sys.stdin)
    path = Path(str(payload.get("args", {}).get("path", "")))
    if path.suffix != ".py" or not path.is_file():
        return 0
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        compile(source, str(path), "exec")
    except SyntaxError as exc:
        print(f"syntax check FAILED for {path.as_posix()}: line {exc.lineno}: {exc.msg}. Fix it with patch_file.")
        return 0
    print(f"syntax check passed for {path.as_posix()} ({len(source.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
