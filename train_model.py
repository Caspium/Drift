"""
DRIFT AI Training — Self-Play Reinforcement Learning
Trains a policy-value network via self-play on GPU.
Exports weights as numpy .npz for inference in the game (no PyTorch needed).
"""

import sys, os, time, random, math, copy
from enum import Enum
from collections import deque

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

# ---------------------------------------------------------------------------
# Import game logic (reuse from drift.py)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))
from drift import (Board, Cell, Mark, Phase, PieceType, Zone, Direction,
                   GRID_ROWS, GRID_COLS, MAX_AGE, SENTINEL_DECAY,
                   PHANTOM_DURATION, ANCHORS_PER_PLAYER, ZONE_LAYOUT,
                   POWER_PIECE_INFO, _WIN_LINES, _PUSH_SPECS, _sim_push,
                   _eval_board, _can_surge_win)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# State encoding dimensions
N_MARK = 3        # empty, X, O
N_PTYPE = 5       # normal, phantom, catalyst, leech, sentinel
N_ZONE = 4        # none, rift, accel, warp
CELL_FEATURES = N_MARK + 1 + 1 + N_PTYPE + N_ZONE + 1  # mark_oh + age_norm + anchored + ptype_oh + zone_oh + phantom_norm
GLOBAL_FEATURES = 2 + 4 + 4 + 2 + 1  # anchors(2) + pp_x(4) + pp_o(4) + phase(2) + turn_norm
STATE_DIM = GRID_ROWS * GRID_COLS * CELL_FEATURES + GLOBAL_FEATURES  # 16*15 + 13 = 253

# Action space
N_PLACE = GRID_ROWS * GRID_COLS * 5   # 16 cells x 5 piece types = 80
N_ACTION = len(_PUSH_SPECS) + 16 + 1  # 16 pushes + 16 anchors + 1 skip = 33
TOTAL_ACTIONS = N_PLACE + N_ACTION     # 113

# Training
BATCH_SIZE = 512
REPLAY_SIZE = 50000
LR = 3e-4
GAMMA = 0.99
EPISODES = 80000
SAVE_EVERY = 5000
EPS_START = 1.0
EPS_END = 0.05
EPS_DECAY = 40000

# ---------------------------------------------------------------------------
# State encoding
# ---------------------------------------------------------------------------
MARK_IDX = {Mark.EMPTY: 0, Mark.X: 1, Mark.O: 2}
PTYPE_IDX = {PieceType.NORMAL: 0, PieceType.PHANTOM: 1, PieceType.CATALYST: 2,
             PieceType.LEECH: 3, PieceType.SENTINEL: 4}
ZONE_IDX = {Zone.NONE: 0, Zone.RIFT: 1, Zone.ACCELERATOR: 2, Zone.WARP: 3}
PTYPES_LIST = [PieceType.NORMAL, PieceType.PHANTOM, PieceType.CATALYST,
               PieceType.LEECH, PieceType.SENTINEL]


def encode_state(board, mark, anchors, power_pieces, phase_is_place, turn):
    """Encode board state as a flat numpy array from `mark`'s perspective."""
    opp = Mark.O if mark == Mark.X else Mark.X
    feat = np.zeros(STATE_DIM, dtype=np.float32)
    idx = 0
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            cell = board.grid[r][c]
            zone = board.zones.get((r, c), Zone.NONE)
            # Mark one-hot (from perspective: 0=empty, 1=ours, 2=theirs)
            if cell.mark == Mark.EMPTY:
                feat[idx] = 1.0
            elif cell.mark == mark:
                feat[idx + 1] = 1.0
            else:
                feat[idx + 2] = 1.0
            idx += N_MARK
            # Age normalized
            max_a = SENTINEL_DECAY if cell.piece_type == PieceType.SENTINEL else MAX_AGE
            feat[idx] = cell.age / max_a if cell.mark != Mark.EMPTY else 0
            idx += 1
            # Anchored
            feat[idx] = 1.0 if cell.anchored else 0.0
            idx += 1
            # Piece type one-hot
            if cell.mark != Mark.EMPTY:
                feat[idx + PTYPE_IDX[cell.piece_type]] = 1.0
            idx += N_PTYPE
            # Zone one-hot
            feat[idx + ZONE_IDX[zone]] = 1.0
            idx += N_ZONE
            # Phantom turns
            feat[idx] = cell.phantom_turns / PHANTOM_DURATION if cell.phantom_turns > 0 else 0
            idx += 1
    # Global features
    feat[idx] = anchors.get(mark, 0) / ANCHORS_PER_PLAYER
    feat[idx + 1] = anchors.get(opp, 0) / ANCHORS_PER_PLAYER
    idx += 2
    for i, pt in enumerate(PTYPES_LIST[1:]):  # skip NORMAL
        feat[idx + i] = power_pieces.get(mark, {}).get(pt, 0) / 2.0
    idx += 4
    for i, pt in enumerate(PTYPES_LIST[1:]):
        feat[idx + i] = power_pieces.get(opp, {}).get(pt, 0) / 2.0
    idx += 4
    feat[idx] = 1.0 if phase_is_place else 0.0
    feat[idx + 1] = 0.0 if phase_is_place else 1.0
    idx += 2
    feat[idx] = min(turn / 30.0, 1.0)
    return feat


# ---------------------------------------------------------------------------
# Action encoding/decoding
# ---------------------------------------------------------------------------
def get_valid_placements(board, mark, power_pieces):
    """Returns list of (action_idx, r, c, piece_type)."""
    valid = []
    avail = [PieceType.NORMAL]
    for pt, cnt in power_pieces.get(mark, {}).items():
        if cnt > 0:
            avail.append(pt)
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            if board.grid[r][c].mark == Mark.EMPTY:
                for pt in avail:
                    action_idx = (r * GRID_COLS + c) * 5 + PTYPE_IDX[pt]
                    valid.append((action_idx, r, c, pt))
    return valid


def get_valid_actions(board, mark, anchors):
    """Returns list of (action_idx, action_type, params)."""
    valid = []
    base = N_PLACE
    # Pushes
    for i, (axis, idx, d) in enumerate(_PUSH_SPECS):
        valid.append((base + i, "push", (axis, idx, d)))
    # Anchors
    if anchors.get(mark, 0) > 0:
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                cell = board.grid[r][c]
                if cell.mark == mark and not cell.anchored:
                    zone = board.zones.get((r, c), Zone.NONE)
                    if zone != Zone.RIFT:
                        action_idx = base + len(_PUSH_SPECS) + r * GRID_COLS + c
                        valid.append((action_idx, "anchor", (r, c)))
    # Skip
    valid.append((base + len(_PUSH_SPECS) + 16, "skip", ()))
    return valid


# ---------------------------------------------------------------------------
# Neural Network
# ---------------------------------------------------------------------------
class DriftNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(STATE_DIM, 512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.ReLU(),
        )
        # Policy head (all actions)
        self.policy = nn.Sequential(
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, TOTAL_ACTIONS),
        )
        # Value head
        self.value = nn.Sequential(
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Tanh(),
        )

    def forward(self, x):
        h = self.shared(x)
        return self.policy(h), self.value(h)


# ---------------------------------------------------------------------------
# Game simulation for self-play
# ---------------------------------------------------------------------------
class SimGame:
    """Lightweight game simulation for training (no pygame)."""
    def __init__(self):
        self.board = Board()
        self.current = Mark.X
        self.anchors = {Mark.X: ANCHORS_PER_PLAYER, Mark.O: ANCHORS_PER_PLAYER}
        self.power_pieces = {Mark.X: {}, Mark.O: {}}
        self.phase_is_place = True
        self.turn = 1
        self.done = False
        self.winner = None
        self._auto_draft()

    def _auto_draft(self):
        """Random draft for both players."""
        for m in (Mark.X, Mark.O):
            types = [pt for pt, *_ in POWER_PIECE_INFO]
            picks = random.sample(types, 2)
            self.power_pieces[m] = {p: 1 for p in picks}

    def state(self, mark):
        return encode_state(self.board, mark, self.anchors,
                           self.power_pieces, self.phase_is_place, self.turn)

    def step_place(self, r, c, pt):
        """Execute a placement. Returns (reward, done)."""
        mark = self.current
        if not self.board.place(r, c, mark, pt):
            return -1.0, True  # invalid move penalty
        if pt != PieceType.NORMAL:
            self.power_pieces[mark][pt] = max(0, self.power_pieces[mark].get(pt, 0) - 1)
        if pt == PieceType.LEECH:
            self.board.apply_leech(r, c)
        w, _ = self.board.check_winner()
        if w:
            self.done = True
            self.winner = w
            return 1.0 if w == mark else -1.0, True
        self.phase_is_place = False
        return 0.0, False

    def step_action(self, action_type, params):
        """Execute an action. Returns (reward, done)."""
        mark = self.current
        if action_type == "push":
            axis, idx, d = params
            ml = self.board.push(axis, idx, d)
            self.board.apply_catalyst_effects(ml)
            self.board.apply_warp_effects(ml)
        elif action_type == "anchor":
            r, c = params
            cell = self.board.grid[r][c]
            if cell.mark == mark and not cell.anchored:
                cell.anchored = True
                self.anchors[mark] = max(0, self.anchors[mark] - 1)
        # Skip: do nothing
        # Check winner
        w, _ = self.board.check_winner()
        if w:
            self.done = True
            self.winner = w
            return 1.0 if w == mark else -1.0, True
        # Check surge
        if self.board.has_three_in_a_row(mark):
            # Surge: get another action (simplified: just skip for training speed)
            pass
        # End turn
        self.board.age_pieces()
        w, _ = self.board.check_winner()
        if w:
            self.done = True
            self.winner = w
            return 1.0 if w == mark else -1.0, True
        self.current = Mark.O if self.current == Mark.X else Mark.X
        self.phase_is_place = True
        self.turn += 1
        if self.turn > 60:  # safety cap
            self.done = True
            return 0.0, True
        return 0.0, False


# ---------------------------------------------------------------------------
# Replay buffer
# ---------------------------------------------------------------------------
class ReplayBuffer:
    def __init__(self, capacity):
        self.buf = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done, valid_mask):
        self.buf.append((state, action, reward, next_state, done, valid_mask))

    def sample(self, batch_size):
        batch = random.sample(self.buf, min(batch_size, len(self.buf)))
        states, actions, rewards, next_states, dones, masks = zip(*batch)
        return (np.array(states), np.array(actions), np.array(rewards, dtype=np.float32),
                np.array(next_states), np.array(dones, dtype=np.float32), np.array(masks))

    def __len__(self):
        return len(self.buf)


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------
def make_valid_mask(valid_indices, total):
    mask = np.zeros(total, dtype=np.float32)
    for idx in valid_indices:
        mask[idx] = 1.0
    return mask


def select_action(net, state, valid_actions, epsilon, device):
    """Epsilon-greedy action selection with valid action masking."""
    valid_indices = [a[0] for a in valid_actions]
    if random.random() < epsilon:
        choice = random.choice(valid_actions)
        return choice[0], choice
    with torch.no_grad():
        s = torch.FloatTensor(state).unsqueeze(0).to(device)
        logits, _ = net(s)
        logits = logits.squeeze(0).cpu().numpy()
        # Mask invalid actions
        mask = np.full(len(logits), -1e9)
        for idx in valid_indices:
            mask[idx] = logits[idx]
        best_idx = np.argmax(mask)
        for a in valid_actions:
            if a[0] == best_idx:
                return best_idx, a
    return valid_actions[0][0], valid_actions[0]


def train_step(net, target_net, optimizer, replay, device):
    if len(replay) < BATCH_SIZE:
        return 0.0
    states, actions, rewards, next_states, dones, masks = replay.sample(BATCH_SIZE)

    states_t = torch.FloatTensor(states).to(device)
    actions_t = torch.LongTensor(actions).to(device)
    rewards_t = torch.FloatTensor(rewards).to(device)
    next_states_t = torch.FloatTensor(next_states).to(device)
    dones_t = torch.FloatTensor(dones).to(device)
    masks_t = torch.FloatTensor(masks).to(device)

    # Current Q values
    logits, values = net(states_t)
    q_values = logits.gather(1, actions_t.unsqueeze(1)).squeeze(1)

    # Target Q values
    with torch.no_grad():
        next_logits, next_values = target_net(next_states_t)
        # Mask invalid actions in next state
        next_logits = next_logits + (masks_t - 1) * 1e9
        next_q = next_logits.max(1)[0]
        target = rewards_t + GAMMA * next_q * (1 - dones_t)

    # Loss: Q-learning + value loss
    q_loss = F.mse_loss(q_values, target)
    v_loss = F.mse_loss(values.squeeze(1), target.detach())
    loss = q_loss + 0.5 * v_loss

    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
    optimizer.step()
    return loss.item()


def self_play_episode(net, epsilon, device):
    """Play one full game, collecting (state, action, reward, next_state, done, mask) tuples."""
    game = SimGame()
    transitions = []

    while not game.done:
        mark = game.current
        state = game.state(mark)

        if game.phase_is_place:
            valid = get_valid_placements(game.board, mark, game.power_pieces)
            if not valid:
                break
            mask = make_valid_mask([a[0] for a in valid], TOTAL_ACTIONS)
            action_idx, choice = select_action(net, state, valid, epsilon, device)
            _, r, c, pt = choice
            reward, done = game.step_place(r, c, pt)
        else:
            valid = get_valid_actions(game.board, mark, game.anchors)
            mask = make_valid_mask([a[0] for a in valid], TOTAL_ACTIONS)
            action_idx, choice = select_action(net, state, valid, epsilon, device)
            _, atype, params = choice
            reward, done = game.step_action(atype, params)

        next_state = game.state(mark) if not done else np.zeros(STATE_DIM, dtype=np.float32)

        # Get valid mask for NEXT state (for target Q computation)
        if not done:
            next_mark = game.current
            if game.phase_is_place:
                nv = get_valid_placements(game.board, next_mark, game.power_pieces)
            else:
                nv = get_valid_actions(game.board, next_mark, game.anchors)
            next_mask = make_valid_mask([a[0] for a in nv], TOTAL_ACTIONS)
        else:
            next_mask = np.zeros(TOTAL_ACTIONS, dtype=np.float32)

        transitions.append((state, action_idx, reward, next_state, done, next_mask))

    # Propagate final outcome back through transitions
    if game.winner is not None:
        # Go through transitions and assign rewards based on who won
        for i, (s, a, r, ns, d, m) in enumerate(transitions):
            # Determine which player made this move (alternates, but phase matters)
            # We use a simpler approach: the terminal reward is already set
            if r == 0.0 and not d:
                # Intermediate step: small heuristic reward
                pass
    return transitions


def export_numpy(net, path):
    """Export network weights as numpy arrays for inference without PyTorch."""
    weights = {}
    for name, param in net.named_parameters():
        weights[name.replace(".", "_")] = param.detach().cpu().numpy()
    np.savez_compressed(path, **weights)
    print(f"Exported {len(weights)} weight tensors to {path}")
    print(f"File size: {os.path.getsize(path) / 1024:.1f} KB")


def main():
    print(f"Device: {DEVICE}")
    print(f"State dim: {STATE_DIM}, Total actions: {TOTAL_ACTIONS}")
    print(f"Training for {EPISODES} episodes...", flush=True)

    net = DriftNet().to(DEVICE)
    target_net = DriftNet().to(DEVICE)
    target_net.load_state_dict(net.state_dict())
    optimizer = optim.Adam(net.parameters(), lr=LR)
    replay = ReplayBuffer(REPLAY_SIZE)

    wins = {Mark.X: 0, Mark.O: 0, None: 0}
    losses_log = []
    t0 = time.time()

    for ep in range(1, EPISODES + 1):
        epsilon = EPS_END + (EPS_START - EPS_END) * math.exp(-ep / EPS_DECAY)
        transitions = self_play_episode(net, epsilon, DEVICE)
        for t in transitions:
            replay.push(*t)

        # Train every episode
        loss = train_step(net, target_net, optimizer, replay, DEVICE)
        losses_log.append(loss)

        # Track winner
        game_winner = None
        for _, _, r, _, d, _ in transitions:
            if d and r != 0:
                # Determine winner from last transition
                if r > 0:
                    game_winner = Mark.X if len(transitions) % 2 == 1 else Mark.O
                else:
                    game_winner = Mark.O if len(transitions) % 2 == 1 else Mark.X
        wins[game_winner] = wins.get(game_winner, 0) + 1

        # Update target net
        if ep % 500 == 0:
            target_net.load_state_dict(net.state_dict())

        # Log
        if ep % 1000 == 0:
            elapsed = time.time() - t0
            avg_loss = np.mean(losses_log[-1000:]) if losses_log else 0
            eps_per_sec = ep / elapsed
            print(f"Ep {ep:6d} | eps={epsilon:.3f} | loss={avg_loss:.4f} | "
                  f"X:{wins[Mark.X]} O:{wins[Mark.O]} D:{wins.get(None,0)} | "
                  f"{eps_per_sec:.0f} ep/s | {elapsed:.0f}s", flush=True)

        # Save checkpoint
        if ep % SAVE_EVERY == 0:
            ckpt_path = os.path.join(os.path.dirname(__file__), f"model_ckpt_{ep}.pt")
            torch.save(net.state_dict(), ckpt_path)
            print(f"  Checkpoint saved: {ckpt_path}")

    # Final export
    model_path = os.path.join(os.path.dirname(__file__), "assets", "drift_model.npz")
    export_numpy(net, model_path)

    # Also save PyTorch checkpoint
    final_path = os.path.join(os.path.dirname(__file__), "model_final.pt")
    torch.save(net.state_dict(), final_path)
    print(f"\nTraining complete! Model saved to {model_path}")
    print(f"Total time: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
