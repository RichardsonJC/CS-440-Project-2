---
name: pr-review
description: Review a pull request, diff, or set of code changes for bugs, risks, missing tests, and style issues.
triggers: pull request, PR, code review, review diff, review changes, review my code, git diff, merge request
enabled: true
---

# PR Review Skill

You are reviewing a set of code changes. Work through these steps in order and
use tools instead of guessing.

## Steps

1. **Collect the diff.** Run `git status --short` and `git diff` (or
   `git diff <base>...HEAD` if the user names a base branch) with `run_shell`.
   If there is no git diff, ask which files to review, or review the files the user named.
2. **Read context.** For each changed file, use `read_file` on the changed
   region plus enough surrounding code to understand it.
3. **Check correctness first.** Look for logic errors, off-by-one errors,
   unhandled `None`/empty inputs, exceptions that are swallowed, resource leaks,
   and changed behaviour that callers depend on.
4. **Check risk.** Look for security issues (path traversal, shell injection,
   secrets in code), destructive operations, and breaking API changes.
5. **Check tests.** Is the new behaviour covered? If a test command is obvious,
   run it with `run_shell` and report the result.
6. **Check style last.** Only mention naming or formatting when it hurts readability.

## Output format

Return a `<final>` answer shaped like this:

```
Summary: <one sentence on what the change does>
Verdict: APPROVE | REQUEST CHANGES | COMMENT

Findings (most severe first):
- [severity: high|medium|low] <file>:<line>: <problem>. Suggested fix: <fix>.

Tests: <what you ran and the result, or "not run">
```

Do not modify files during a review unless the user explicitly asks you to fix something.
