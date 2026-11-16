---
name: unit-tests
description: Write or extend pytest unit tests for existing Python code and run them.
triggers: unit test, pytest, test coverage, write tests, add tests, test case, failing test
enabled: true
---

# Unit Tests Skill

1. Read the implementation under test with `read_file` before writing any test.
2. Find existing tests (`list_files` on `tests/`, or `search` for `def test_`) and
   match their style, fixtures, and import pattern.
3. Cover the normal case, edge cases (empty input, boundaries, invalid input),
   and any bug the user mentioned. Use one behaviour per test function.
4. Write tests with `write_file` (new file) or `patch_file` (existing file).
5. Run `python -m pytest -q <test file>` with `run_shell`. If tests fail because
   the test is wrong, fix the test. If the implementation is wrong, report it
   and do not change the implementation unless the user asked you to.
6. Finish with a `<final>` answer listing the tests added and the pytest result.
