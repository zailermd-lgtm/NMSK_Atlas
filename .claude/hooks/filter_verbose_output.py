#!/usr/bin/env python3
"""PreToolUse hook (Bash matcher): trims verbose pytest / audit-script output
to just the lines worth putting in context, so a full green test run or a
clean audit doesn't burn tokens on output nobody needs to read.
Leaves every other command untouched.
"""
import json
import re
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    print("{}")
    sys.exit(0)

cmd = payload.get("tool_input", {}).get("command", "")

# Commands whose full output is usually noise unless something failed.
pattern = re.compile(
    r"^(pytest\b.*|python -m engine\.build_atlas\b.*|"
    r"python scripts/audit_\w+\.py\b.*)$"
)

if pattern.match(cmd.strip()):
    filtered = (
        f"{cmd} 2>&1 | "
        r"grep -E '(FAIL|ERROR|Traceback|AssertionError|MISMATCH|WARNING|missing source|passed|failed)' "
        "| head -150"
    )
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {**payload.get("tool_input", {}), "command": filtered},
        }
    }
    print(json.dumps(out))
else:
    print("{}")
