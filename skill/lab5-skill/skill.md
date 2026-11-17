---
name: lab5-vacuum-rl
description: Solve Lab 4, the vacuum robot reinforcement learning task - build a model-free 4x4 grid world environment and Q-learning scaffolding with chosen living reward, discount factor, learning rate, and exploration rate.
triggers: lab 4, vacuum robot, vacuum, reinforcement learning, grid world, gridworld, q-learning, q learning, q table, living reward, discount factor, gamma, learning rate, alpha, exploration rate, epsilon greedy, model-free, markov decision process
enabled: true
---

# Lab 5 Skill: Solve Lab 4 (Vacuum Robot RL Grid World)

Goal: create ONE file, `lab4/vacuum_rl.py`, then make the checker pass. Do not do full training.

## Environment (fixed by Lab 4)

```
row 0:  start |  0  |  0  |  0
row 1:    0   |  X  |  0  |  0
row 2:    0   |  0  |  0  |  0
row 3:    0   | -1  |  0  | 10
```

States are `(row, col)`. START=(0, 0). WALL X at (1, 1) cannot be entered.
Terminal states: (3, 1) gives -1.0 and (3, 3) gives +10.0; the episode ends there.
Actions: "up", "down", "left", "right". Moving into the wall or off the grid leaves
the robot where it is. T and R are unknown to the agent (model-free): the agent only
learns from `step()`; it must never read the transition model.
Transitions are noisy: the intended move happens with probability `1 - slip`, otherwise one
of the two perpendicular moves (slip/2 each). Default slip = 0.2.
Reward for entering a terminal = its terminal value; every other step = LIVING_REWARD.

## Parameters (Lab 5) - use exactly these values and keep the justification comments

```python
LIVING_REWARD = -0.04  # small step cost: pushes toward the shortest path to +10, but is far too small to make ending at -1 attractive
GAMMA = 0.9            # goal is ~6 steps away; 0.9**6 = 0.53, so +10 still dominates while < 1 keeps returns bounded
ALPHA = 0.1            # transitions are stochastic, so a small learning rate averages out noisy samples instead of chasing them
EPSILON = 0.2          # 20% random actions: enough exploration to find (3,3) behind the wall in a 15-state grid; decay later during training
```

## Required API in `lab4/vacuum_rl.py` (standard library only: `random`)

```python
ROWS, COLS = 4, 4
START = (0, 0)
WALLS = {(1, 1)}
TERMINALS = {(3, 1): -1.0, (3, 3): 10.0}
ACTIONS = ["up", "down", "left", "right"]

class VacuumGridEnv:
    def __init__(self, slip=0.2, seed=None): ...      # use random.Random(seed)
    def reset(self, state=None): ...                  # set self.state (default START) and return it
    def step(self, action): ...                       # return (next_state, reward, done)

def init_q_table(): ...      # {state: {action: 0.0}} for every non-wall state
def epsilon_greedy(q, state, epsilon, rng): ...       # random action with prob epsilon, else argmax
def q_update(q, s, a, r, s2, done, alpha=ALPHA, gamma=GAMMA): ...
    # target = r if done else r + gamma * max(q[s2].values()); q[s][a] += alpha * (target - q[s][a]); return q[s][a]
```

Under `if __name__ == "__main__":` print the grid, print the 4 parameters, then run
3 short demo episodes (max 30 steps each) with `epsilon_greedy` + `q_update`, printing
each episode's total reward and step count. That is the "prepare for Q-learning" part.

## Steps

1. Write the whole file at once with `write_file` (path `lab4/vacuum_rl.py`). Use the XML
   style: `<tool name="write_file" path="lab4/vacuum_rl.py"><content>...</content></tool>`.
   A hook runs a syntax check automatically after each write and appends the result.
2. Run the checker with `run_shell`:
   `python skill/lab5-skill/check_lab4.py lab4/vacuum_rl.py`
3. If any line says FAIL, fix only that part with `patch_file`, then rerun step 2.
4. Run the demo: `python lab4/vacuum_rl.py` with `run_shell`.
5. Sub-agent review: call `delegate` with task
   "Read lab4/vacuum_rl.py and confirm the four RL parameters and their justifications are present."
6. Finish with `<final>` containing: the checker result line, the 4 parameter values with
   one-line justifications, and the demo episode rewards.
