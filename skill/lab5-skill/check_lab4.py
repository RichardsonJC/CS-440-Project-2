"""Checker for the Lab 4 solution produced with the lab5-vacuum-rl skill.

Usage: python skill/lab5-skill/check_lab4.py lab4/vacuum_rl.py

Prints one PASS/FAIL line per check and a summary line; exit code 0 only if all pass.
"""

import importlib.util
import random
import sys
from pathlib import Path

EXPECTED_PARAMS = {"LIVING_REWARD": -0.04, "GAMMA": 0.9, "ALPHA": 0.1, "EPSILON": 0.2}
MOVES = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


def load(path):
    spec = importlib.util.spec_from_file_location("vacuum_rl", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_checks(m):
    def env(state):
        e = m.VacuumGridEnv(slip=0.0, seed=0)
        e.reset(state)
        return e

    def check_params():
        for name, value in EXPECTED_PARAMS.items():
            actual = getattr(m, name)
            assert abs(actual - value) < 1e-9, f"{name}={actual}, expected {value}"

    def check_layout():
        assert (m.ROWS, m.COLS) == (4, 4)
        assert tuple(m.START) == (0, 0)
        assert set(m.WALLS) == {(1, 1)}
        assert dict(m.TERMINALS) == {(3, 1): -1.0, (3, 3): 10.0}
        assert sorted(m.ACTIONS) == sorted(MOVES)

    def check_reset():
        e = m.VacuumGridEnv(seed=0)
        assert tuple(e.reset()) == (0, 0)

    def check_moves_and_living_reward():
        s2, r, done = env((0, 0)).step("right")
        assert tuple(s2) == (0, 1), f"right from (0,0) went to {s2}"
        assert abs(r - m.LIVING_REWARD) < 1e-9 and not done, f"got reward={r}, done={done}"

    def check_edges_and_wall():
        assert tuple(env((0, 0)).step("up")[0]) == (0, 0), "moving off the grid must stay in place"
        assert tuple(env((0, 1)).step("down")[0]) == (0, 1), "moving into the wall must stay in place"
        assert tuple(env((1, 0)).step("right")[0]) == (1, 0), "moving into the wall must stay in place"

    def check_terminals():
        s2, r, done = env((3, 2)).step("right")
        assert tuple(s2) == (3, 3) and abs(r - 10.0) < 1e-9 and done, f"(3,2)->right gave {(s2, r, done)}"
        s2, r, done = env((2, 1)).step("down")
        assert tuple(s2) == (3, 1) and abs(r + 1.0) < 1e-9 and done, f"(2,1)->down gave {(s2, r, done)}"

    def check_stochastic_and_model_free():
        e = m.VacuumGridEnv(slip=0.2, seed=1)
        outcomes = set()
        for _ in range(300):
            e.reset((2, 2))
            s2, _, _ = e.step("up")
            outcomes.add(tuple(s2))
        assert (1, 2) in outcomes, "intended move never happened"
        assert outcomes <= {(1, 2), (2, 1), (2, 3)}, f"impossible outcomes {outcomes}"
        assert len(outcomes) > 1, "slip=0.2 should sometimes move perpendicular"

    def check_q_table():
        q = m.init_q_table()
        assert (1, 1) not in q, "wall must not be a Q-table state"
        assert len(q) == 15, f"expected 15 states, got {len(q)}"
        assert all(set(row) == set(MOVES) and all(v == 0.0 for v in row.values()) for row in q.values())

    def check_epsilon_greedy():
        q = m.init_q_table()
        q[(0, 0)]["down"] = 1.0
        rng = random.Random(0)
        assert all(m.epsilon_greedy(q, (0, 0), 0.0, rng) == "down" for _ in range(20)), "epsilon=0 must be greedy"
        picks = {m.epsilon_greedy(q, (0, 0), 1.0, rng) for _ in range(200)}
        assert len(picks) > 1, "epsilon=1 must explore"

    def check_q_update():
        q = m.init_q_table()
        q[(2, 3)]["down"] = 5.0
        value = m.q_update(q, (2, 2), "right", -0.04, (2, 3), False, alpha=0.1, gamma=0.9)
        expected = 0.1 * (-0.04 + 0.9 * 5.0)
        assert abs(value - expected) < 1e-9 and abs(q[(2, 2)]["right"] - expected) < 1e-9, f"got {value}"
        value = m.q_update(q, (3, 2), "right", 10.0, (3, 3), True, alpha=0.1, gamma=0.9)
        assert abs(value - 1.0) < 1e-9, f"terminal update must ignore future value, got {value}"

    checks = [
        ("parameters LIVING_REWARD/GAMMA/ALPHA/EPSILON", check_params),
        ("grid layout, wall, terminals, actions", check_layout),
        ("reset() returns START", check_reset),
        ("step() moves and pays living reward", check_moves_and_living_reward),
        ("edges and wall block movement", check_edges_and_wall),
        ("terminal rewards and done flag", check_terminals),
        ("stochastic transitions (slip)", check_stochastic_and_model_free),
        ("init_q_table() covers 15 states x 4 actions", check_q_table),
        ("epsilon_greedy() explores and exploits", check_epsilon_greedy),
        ("q_update() matches the Q-learning rule", check_q_update),
    ]
    failures = 0
    for label, check in checks:
        try:
            check()
            print(f"PASS  {label}")
        except Exception as exc:  # noqa: BLE001 - report every kind of failure as a FAIL line
            failures += 1
            print(f"FAIL  {label}: {type(exc).__name__}: {exc}")
    return failures, len(checks)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0] if argv else "lab4/vacuum_rl.py")
    if not path.is_file():
        print(f"FAIL  file not found: {path}")
        return 1
    try:
        module = load(path)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  could not import {path}: {type(exc).__name__}: {exc}")
        return 1
    failures, total = run_checks(module)
    print(f"RESULT: {total - failures}/{total} checks passed" + ("" if failures else " - Lab 4 solution OK"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
