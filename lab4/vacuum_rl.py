import random

ROWS, COLS = 4, 4
START = (0, 0)
WALLS = {(1, 1)}
TERMINALS = {(3, 1): -1.0, (3, 3): 10.0}
ACTIONS = ["up", "down", "left", "right"]
MOVES = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
# A slip turns the robot 90 degrees: never backwards, never a diagonal or two-cell jump.
PERPENDICULAR = {"up": ("left", "right"), "down": ("left", "right"), "left": ("up", "down"), "right": ("up", "down")}

LIVING_REWARD = -0.04  # small step cost: pushes toward the shortest path to +10, but is far too small to make ending at -1 attractive
GAMMA = 0.9            # goal is ~6 steps away; 0.9**6 = 0.53, so +10 still dominates while < 1 keeps returns bounded
ALPHA = 0.1            # transitions are stochastic, so a small learning rate averages out noisy samples instead of chasing them
EPSILON = 0.2          # 20% random actions: enough exploration to find (3,3) behind the wall in a 15-state grid; decay later during training

class VacuumGridEnv:
    def __init__(self, slip=0.2, seed=None):
        self.rng = random.Random(seed)
        self.slip = slip
        self.reset()

    def reset(self, state=None):
        self.state = state if state is not None else START
        return self.state

    def _move(self, state, action):
        """Deterministic move; bumping an edge or the wall leaves the robot in place."""
        dr, dc = MOVES[action]
        r, c = state[0] + dr, state[1] + dc
        if not (0 <= r < ROWS and 0 <= c < COLS) or (r, c) in WALLS:
            return state
        return (r, c)

    def step(self, action):
        if action not in ACTIONS:
            raise ValueError(f"Invalid action: {action}")
        # Hidden from the agent (model-free): with probability `slip` the robot
        # moves to one of the two perpendicular directions instead.
        if self.rng.random() < self.slip:
            action = self.rng.choice(PERPENDICULAR[action])
        self.state = self._move(self.state, action)
        if self.state in TERMINALS:
            return self.state, TERMINALS[self.state], True
        return self.state, LIVING_REWARD, False

def init_q_table():
    q_table = {}
    for row in range(ROWS):
        for col in range(COLS):
            state = (row, col)
            if state not in WALLS:
                q_table[state] = {action: 0.0 for action in ACTIONS}
    return q_table

def epsilon_greedy(q, state, epsilon, rng):
    if rng.random() < epsilon:
        return rng.choice(ACTIONS)
    else:
        return max(q[state], key=q[state].get)

def q_update(q, s, a, r, s2, done, alpha=ALPHA, gamma=GAMMA):
    target = r if done else r + gamma * max(q[s2].values())
    q[s][a] += alpha * (target - q[s][a])
    return q[s][a]

if __name__ == "__main__":
    env = VacuumGridEnv()
    q_table = init_q_table()

    print("Grid:")
    for row in range(ROWS):
        cells = []
        for col in range(COLS):
            cell = (row, col)
            cells.append("start" if cell == START else "X" if cell in WALLS else str(TERMINALS.get(cell, 0)))
        print(" | ".join(f"{c:>5}" for c in cells))
    print(f"LIVING_REWARD: {LIVING_REWARD}")
    print(f"GAMMA: {GAMMA}")
    print(f"ALPHA: {ALPHA}")
    print(f"EPSILON: {EPSILON}")

    rng = random.Random(0)
    for episode in range(3):
        state = env.reset()
        total_reward = 0.0
        for steps in range(1, 31):  # cap episodes at 30 steps
            action = epsilon_greedy(q_table, state, EPSILON, rng)
            next_state, reward, done = env.step(action)
            q_update(q_table, state, action, reward, next_state, done)
            total_reward += reward
            state = next_state
            if done:
                break
        print(f"Episode {episode + 1}: reward={total_reward:.2f}, steps={steps}")
