"""
DRIFT - No Move Is Safe. No Piece Is Permanent. (v2.0)
An evolution of tic-tac-toe where the board is alive.
Place. Push. Decay. Anchor. Draft. Surge.
"""

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
import sys
import math
import random
import threading
from enum import Enum
from concurrent.futures import ProcessPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CELL_SIZE = 120
GRID_COLS = 4
GRID_ROWS = 4
BOARD_W = CELL_SIZE * GRID_COLS
BOARD_H = CELL_SIZE * GRID_ROWS
SIDEBAR_W = 290
ARROW_MARGIN = 50
TOP_MARGIN = 80
BOTTOM_MARGIN = 50
WIN_W = ARROW_MARGIN + BOARD_W + ARROW_MARGIN + SIDEBAR_W
WIN_H = TOP_MARGIN + BOARD_H + ARROW_MARGIN + BOTTOM_MARGIN
BOARD_X0 = ARROW_MARGIN
BOARD_Y0 = TOP_MARGIN
MAX_AGE = 6
SENTINEL_DECAY = 4
PHANTOM_DURATION = 2
LEECH_DRAIN = 2
ANCHORS_PER_PLAYER = 2
FPS = 60
ANIM_DURATION = 0.25

# Colors
BG_COLOR = (10, 22, 40)
GRID_COLOR = (0, 180, 220)
X_COLOR = (255, 71, 87)
O_COLOR = (46, 213, 115)
TEXT_COLOR = (220, 230, 240)
SIDEBAR_BG = (16, 30, 52)
ANCHOR_COLOR = (255, 215, 0)
ARROW_COLOR = (60, 90, 120)
ARROW_HOVER = (0, 212, 255)
BUTTON_COLOR = (30, 60, 100)
BUTTON_HOVER = (50, 100, 160)
BUTTON_TEXT = (220, 240, 255)
SURGE_COLOR = (255, 200, 50)

ZONE_COLORS = {
    "rift": (0, 80, 160, 50),
    "accel": (160, 60, 0, 50),
    "warp": (100, 0, 160, 50),
}
ZONE_TEXT_COLORS = {
    "rift": (60, 140, 220),
    "accel": (220, 120, 40),
    "warp": (160, 80, 220),
}

POWER_COLORS = {
    "phantom": (150, 200, 255),
    "catalyst": (255, 180, 50),
    "leech": (180, 50, 220),
    "sentinel": (200, 200, 200),
}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Mark(Enum):
    EMPTY = 0
    X = 1
    O = 2


class Phase(Enum):
    TITLE = "title"
    MODE_SELECT = "mode_select"
    DRAFT = "draft"
    PLACE = "place"
    ACTION = "action"
    SURGE = "surge"
    GAME_OVER = "game_over"


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class PieceType(Enum):
    NORMAL = "normal"
    PHANTOM = "phantom"
    CATALYST = "catalyst"
    LEECH = "leech"
    SENTINEL = "sentinel"


class Zone(Enum):
    NONE = "none"
    RIFT = "rift"
    ACCELERATOR = "accel"
    WARP = "warp"


ZONE_LAYOUT = {
    (1, 1): Zone.RIFT,
    (2, 2): Zone.ACCELERATOR,
    (0, 3): Zone.WARP,
    (3, 0): Zone.WARP,
}

POWER_PIECE_INFO = [
    (PieceType.PHANTOM, "Phantom", "Immune to pushes", "for 2 turns"),
    (PieceType.CATALYST, "Catalyst", "When pushed, explodes", "pushing adjacent pieces"),
    (PieceType.LEECH, "Leech", "On place, ages adjacent", "enemy pieces by 2"),
    (PieceType.SENTINEL, "Sentinel", "Auto-anchored on place", "Decays in 4 turns"),
]


# ---------------------------------------------------------------------------
# Cell
# ---------------------------------------------------------------------------
class Cell:
    __slots__ = ("mark", "age", "anchored", "piece_type", "phantom_turns")

    def __init__(self):
        self.mark = Mark.EMPTY
        self.age = 0
        self.anchored = False
        self.piece_type = PieceType.NORMAL
        self.phantom_turns = 0

    def copy(self):
        c = Cell()
        c.mark = self.mark
        c.age = self.age
        c.anchored = self.anchored
        c.piece_type = self.piece_type
        c.phantom_turns = self.phantom_turns
        return c

    def is_immovable(self):
        if self.anchored:
            return True
        if self.piece_type == PieceType.PHANTOM and self.phantom_turns > 0:
            return True
        return False

    def __getstate__(self):
        return (self.mark, self.age, self.anchored, self.piece_type, self.phantom_turns)

    def __setstate__(self, state):
        self.mark, self.age, self.anchored, self.piece_type, self.phantom_turns = state


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------
class Board:
    def __init__(self):
        self.grid = [[Cell() for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
        self.zones = dict(ZONE_LAYOUT)

    def place(self, r, c, mark, piece_type=PieceType.NORMAL):
        cell = self.grid[r][c]
        if cell.mark != Mark.EMPTY:
            return False
        cell.mark = mark
        cell.age = 0
        cell.anchored = False
        cell.piece_type = piece_type
        cell.phantom_turns = PHANTOM_DURATION if piece_type == PieceType.PHANTOM else 0
        # Sentinel auto-anchor (unless on Rift)
        if piece_type == PieceType.SENTINEL:
            zone = self.zones.get((r, c), Zone.NONE)
            if zone != Zone.RIFT:
                cell.anchored = True
        return True

    def apply_leech(self, r, c):
        """Drain adjacent enemy pieces when a Leech is placed."""
        owner = self.grid[r][c].mark
        decayed = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < GRID_ROWS and 0 <= nc < GRID_COLS:
                adj = self.grid[nr][nc]
                if adj.mark != Mark.EMPTY and adj.mark != owner:
                    adj.age += LEECH_DRAIN
                    max_a = SENTINEL_DECAY if adj.piece_type == PieceType.SENTINEL else MAX_AGE
                    if adj.age > max_a:
                        decayed.append((nr, nc))
                        self.grid[nr][nc] = Cell()
        return decayed

    def push(self, axis, index, direction):
        """Push a row or column. Returns move list for animation."""
        moves = []
        if axis == "row":
            row = [self.grid[index][c].copy() for c in range(GRID_COLS)]
            immovable = {c for c in range(GRID_COLS) if row[c].is_immovable()}
            final = [None] * GRID_COLS
            for c in immovable:
                final[c] = row[c]
                moves.append((index, c, index, c))
            free_cells = [row[c] for c in range(GRID_COLS) if c not in immovable]
            free_slots = [c for c in range(GRID_COLS) if c not in immovable]
            if free_slots:
                shifted = [free_slots[(i + direction) % len(free_slots)] for i in range(len(free_slots))]
                for i, cell in enumerate(free_cells):
                    final[shifted[i]] = cell
                    moves.append((index, free_slots[i], index, shifted[i]))
            for c in range(GRID_COLS):
                self.grid[index][c] = final[c] if final[c] else Cell()

        elif axis == "col":
            col = [self.grid[r][index].copy() for r in range(GRID_ROWS)]
            immovable = {r for r in range(GRID_ROWS) if col[r].is_immovable()}
            final = [None] * GRID_ROWS
            for r in immovable:
                final[r] = col[r]
                moves.append((r, index, r, index))
            free_cells = [col[r] for r in range(GRID_ROWS) if r not in immovable]
            free_slots = [r for r in range(GRID_ROWS) if r not in immovable]
            if free_slots:
                shifted = [free_slots[(i + direction) % len(free_slots)] for i in range(len(free_slots))]
                for i, cell in enumerate(free_cells):
                    final[shifted[i]] = cell
                    moves.append((free_slots[i], index, shifted[i], index))
            for r in range(GRID_ROWS):
                self.grid[r][index] = final[r] if final[r] else Cell()

        return moves

    def apply_catalyst_effects(self, move_list):
        """After push, detonate any Catalyst that moved. Returns extra moves."""
        extra = []
        for (or_, oc, nr, nc) in move_list:
            if or_ == nr and oc == nc:
                continue
            cell = self.grid[nr][nc]
            if cell.piece_type != PieceType.CATALYST:
                continue
            cell.piece_type = PieceType.NORMAL  # spent
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ar, ac = nr + dr, nc + dc
                if 0 <= ar < GRID_ROWS and 0 <= ac < GRID_COLS:
                    adj = self.grid[ar][ac]
                    if adj.mark != Mark.EMPTY and not adj.is_immovable():
                        dest_r = (ar + dr) % GRID_ROWS
                        dest_c = (ac + dc) % GRID_COLS
                        if self.grid[dest_r][dest_c].mark == Mark.EMPTY:
                            self.grid[dest_r][dest_c] = adj.copy()
                            self.grid[ar][ac] = Cell()
                            extra.append((ar, ac, dest_r, dest_c))
        return extra

    def apply_warp_effects(self, move_list):
        """After push, teleport pieces that landed on warp cells."""
        warp_cells = [pos for pos, z in self.zones.items() if z == Zone.WARP]
        if len(warp_cells) != 2:
            return []
        wa, wb = warp_cells
        teleports = []
        for (or_, oc, nr, nc) in move_list:
            if or_ == nr and oc == nc:
                continue
            if (nr, nc) == wa:
                dest = wb
            elif (nr, nc) == wb:
                dest = wa
            else:
                continue
            if self.grid[dest[0]][dest[1]].mark == Mark.EMPTY:
                self.grid[dest[0]][dest[1]] = self.grid[nr][nc].copy()
                self.grid[nr][nc] = Cell()
                teleports.append((nr, nc, dest[0], dest[1]))
        return teleports

    def age_pieces(self):
        """Age all pieces. Remove decayed. Returns list of removed (r,c,mark)."""
        removed = []
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                cell = self.grid[r][c]
                if cell.mark == Mark.EMPTY:
                    continue
                zone = self.zones.get((r, c), Zone.NONE)
                # Phantom countdown (always 1/turn regardless of zone)
                if cell.piece_type == PieceType.PHANTOM and cell.phantom_turns > 0:
                    cell.phantom_turns -= 1
                    if cell.phantom_turns <= 0:
                        cell.piece_type = PieceType.NORMAL
                # Aging (affected by zones)
                if zone == Zone.RIFT:
                    continue  # no aging on rift
                increment = 2 if zone == Zone.ACCELERATOR else 1
                cell.age += increment
                max_a = SENTINEL_DECAY if cell.piece_type == PieceType.SENTINEL else MAX_AGE
                if cell.age > max_a:
                    removed.append((r, c, cell.mark))
                    self.grid[r][c] = Cell()
        return removed

    def check_winner(self):
        """Check for 4-in-a-row. Returns (Mark, [(r,c)...]) or (None, None)."""
        lines = []
        for r in range(GRID_ROWS):
            lines.append([(r, c) for c in range(GRID_COLS)])
        for c in range(GRID_COLS):
            lines.append([(r, c) for r in range(GRID_ROWS)])
        lines.append([(i, i) for i in range(4)])
        lines.append([(i, 3 - i) for i in range(4)])
        for line in lines:
            marks = [self.grid[r][c].mark for r, c in line]
            if marks[0] != Mark.EMPTY and all(m == marks[0] for m in marks):
                return marks[0], line
        return None, None

    def has_three_in_a_row(self, mark):
        """Check if mark has any 3 consecutive in a line."""
        # All lines of 3
        lines = []
        for r in range(GRID_ROWS):
            for sc in range(GRID_COLS - 2):
                lines.append([(r, sc + i) for i in range(3)])
        for c in range(GRID_COLS):
            for sr in range(GRID_ROWS - 2):
                lines.append([(sr + i, c) for i in range(3)])
        for r in range(GRID_ROWS - 2):
            for c in range(GRID_COLS - 2):
                lines.append([(r + i, c + i) for i in range(3)])
        for r in range(GRID_ROWS - 2):
            for c in range(2, GRID_COLS):
                lines.append([(r + i, c - i) for i in range(3)])
        for line in lines:
            if all(self.grid[r][c].mark == mark for r, c in line):
                return True
        return False

    def copy(self):
        b = Board()
        b.grid = [[self.grid[r][c].copy() for c in range(GRID_COLS)] for r in range(GRID_ROWS)]
        b.zones = dict(self.zones)
        return b


# ---------------------------------------------------------------------------
# Standalone AI helpers (module-level for multiprocessing pickling)
# ---------------------------------------------------------------------------
_WIN_LINES = []
for _r in range(GRID_ROWS):
    _WIN_LINES.append([(_r, _c) for _c in range(GRID_COLS)])
for _c in range(GRID_COLS):
    _WIN_LINES.append([(_r, _c) for _r in range(GRID_ROWS)])
_WIN_LINES.append([(_i, _i) for _i in range(4)])
_WIN_LINES.append([(_i, 3 - _i) for _i in range(4)])

_PUSH_SPECS = []
for _c in range(GRID_COLS):
    _PUSH_SPECS.append(("col", _c, 1))
for _c in range(GRID_COLS):
    _PUSH_SPECS.append(("col", _c, -1))
for _r in range(GRID_ROWS):
    _PUSH_SPECS.append(("row", _r, 1))
for _r in range(GRID_ROWS):
    _PUSH_SPECS.append(("row", _r, -1))


def _eval_board(board, ai_mark, ai_opp):
    """Standalone board evaluation (no pygame, picklable)."""
    w, _ = board.check_winner()
    if w == ai_mark:
        return 100000
    if w == ai_opp:
        return -100000
    score = 0
    for line in _WIN_LINES:
        own = opp = 0
        for r, c in line:
            m = board.grid[r][c].mark
            if m == ai_mark:
                own += 1
            elif m == ai_opp:
                opp += 1
        # Unblocked lines only (if both players have pieces, line is dead)
        if opp == 0 and own > 0:
            score += (0, 8, 80, 2000)[own]
        if own == 0 and opp > 0:
            score -= (0, 8, 80, 2000)[opp]
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            cell = board.grid[r][c]
            if cell.mark == Mark.EMPTY:
                continue
            mult = 1 if cell.mark == ai_mark else -1
            zone = board.zones.get((r, c), Zone.NONE)
            if zone == Zone.RIFT:
                score += 40 * mult
            elif zone == Zone.ACCELERATOR:
                score -= 12 * mult
            max_a = SENTINEL_DECAY if cell.piece_type == PieceType.SENTINEL else MAX_AGE
            score += max(0, max_a - cell.age) * 2 * mult
            if cell.anchored:
                score += 18 * mult
            if (r, c) in ((1, 1), (1, 2), (2, 1), (2, 2)):
                score += 6 * mult
    return score


def _sim_push(board, axis, index, direction):
    bc = board.copy()
    ml = bc.push(axis, index, direction)
    bc.apply_catalyst_effects(ml)
    bc.apply_warp_effects(ml)
    return bc


def _action_boards(board, mark, anchors_left):
    results = [board]
    for axis, idx, d in _PUSH_SPECS:
        results.append(_sim_push(board, axis, idx, d))
    if anchors_left > 0:
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                cell = board.grid[r][c]
                if cell.mark == mark and not cell.anchored:
                    zone = board.zones.get((r, c), Zone.NONE)
                    if zone != Zone.RIFT:
                        bc = board.copy()
                        bc.grid[r][c].anchored = True
                        results.append(bc)
    return results


def _can_surge_win(board, mark):
    """Can `mark` win via place + push(3-in-a-row) + surge-push(4-in-a-row)?"""
    empties = [(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)
               if board.grid[r][c].mark == Mark.EMPTY]
    for r, c in empties:
        bc = board.copy()
        bc.place(r, c, mark, PieceType.NORMAL)
        w, _ = bc.check_winner()
        if w == mark:
            return True
        for axis, idx, d in _PUSH_SPECS:
            ab = _sim_push(bc, axis, idx, d)
            w, _ = ab.check_winner()
            if w == mark:
                return True
            if ab.has_three_in_a_row(mark):
                for a2, i2, d2 in _PUSH_SPECS:
                    ab2 = _sim_push(ab, a2, i2, d2)
                    w2, _ = ab2.check_winner()
                    if w2 == mark:
                        return True
    return False


def _counter_score(board, ai_mark, ai_opp):
    """Our best counter-response score (3rd ply)."""
    empties = [(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)
               if board.grid[r][c].mark == Mark.EMPTY]
    if not empties:
        return _eval_board(board, ai_mark, ai_opp)
    scored = []
    tie = 0
    for r, c in empties:
        bc = board.copy()
        bc.place(r, c, ai_mark, PieceType.NORMAL)
        scored.append((_eval_board(bc, ai_mark, ai_opp), tie, r, c))
        tie += 1
    scored.sort(reverse=True)
    best = _eval_board(board, ai_mark, ai_opp)
    for _, _, r, c in scored[:6]:
        bc = board.copy()
        bc.place(r, c, ai_mark, PieceType.NORMAL)
        for ab in _action_boards(bc, ai_mark, 0):
            s = _eval_board(ab, ai_mark, ai_opp)
            if s > best:
                best = s
    return best


def _worker_deep_eval(board, ai_mark, ai_opp, opp_type_vals, opp_anchors):
    """Worker function for parallel deep evaluation.
    Models opponent's best response (with surge) + our counter-response."""
    opp_types = [PieceType(v) for v in opp_type_vals]
    empties = [(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)
               if board.grid[r][c].mark == Mark.EMPTY]
    if not empties:
        return _eval_board(board, ai_mark, ai_opp)
    opp_cands = []
    tie = 0
    for r, c in empties:
        for pt in opp_types:
            bc = board.copy()
            bc.place(r, c, ai_opp, pt)
            if pt == PieceType.LEECH:
                bc.apply_leech(r, c)
            opp_cands.append((-_eval_board(bc, ai_mark, ai_opp), tie, r, c, pt))
            tie += 1
    opp_cands.sort()
    top_n = min(len(opp_cands), 12)
    worst = 999999
    for _, _, r, c, pt in opp_cands[:top_n]:
        bc = board.copy()
        bc.place(r, c, ai_opp, pt)
        if pt == PieceType.LEECH:
            bc.apply_leech(r, c)
        best_opp = -999999
        for ab in _action_boards(bc, ai_opp, opp_anchors):
            # Check if opponent (player X) earns a surge from this push
            effective_board = ab
            if ab.has_three_in_a_row(ai_opp):
                # Opponent gets a bonus action — model their best bonus push
                w_check, _ = ab.check_winner()
                if w_check != ai_opp:  # not already a win
                    surge_best_score = _eval_board(ab, ai_opp, ai_mark)
                    surge_best_board = ab
                    for axis, idx, d in _PUSH_SPECS:
                        ab2 = _sim_push(ab, axis, idx, d)
                        s = _eval_board(ab2, ai_opp, ai_mark)
                        if s > surge_best_score:
                            surge_best_score = s
                            surge_best_board = ab2
                    effective_board = surge_best_board
            counter = _counter_score(effective_board, ai_mark, ai_opp)
            opp_g = -counter
            if opp_g > best_opp:
                best_opp = opp_g
        score_for_us = -best_opp
        if score_for_us < worst:
            worst = score_for_us
    return worst


class DriftAI:
    """AI opponent for DRIFT. Plays as Mark.O."""

    DRAFT_PICKS = {
        "easy": [
            {PieceType.LEECH: 1, PieceType.SENTINEL: 1},
            {PieceType.PHANTOM: 1, PieceType.LEECH: 1},
            {PieceType.CATALYST: 1, PieceType.SENTINEL: 1},
        ],
        "medium": [
            {PieceType.LEECH: 1, PieceType.CATALYST: 1},
            {PieceType.LEECH: 2},
            {PieceType.PHANTOM: 1, PieceType.CATALYST: 1},
        ],
        "hard": [
            {PieceType.LEECH: 1, PieceType.CATALYST: 1},
            {PieceType.LEECH: 1, PieceType.PHANTOM: 1},
        ],
    }

    def __init__(self, difficulty="medium"):
        self.difficulty = difficulty
        self.mark = Mark.O
        self.opp = Mark.X
        self.progress = ""
        self.progress_frac = 0.0

    # --- Evaluation ---
    def evaluate(self, board):
        """Score the board from AI's perspective. Higher = better for AI."""
        return _eval_board(board, self.mark, self.opp)

    # --- Draft ---
    def choose_draft(self):
        picks = self.DRAFT_PICKS.get(self.difficulty)
        if picks is None:
            types = [pt for pt, *_ in POWER_PIECE_INFO]
            chosen = random.sample(types, 2)
            return {p: 1 for p in chosen}
        return dict(random.choice(picks))

    # --- Tactical overrides (all difficulties) ---
    def _find_win_threats(self, board, mark):
        """Find cells where placing `mark` would complete 4-in-a-row."""
        threats = set()
        for line in _WIN_LINES:
            own = 0
            empty_cell = None
            n_empty = 0
            blocked = False
            for r, c in line:
                m = board.grid[r][c].mark
                if m == mark:
                    own += 1
                elif m == Mark.EMPTY:
                    n_empty += 1
                    empty_cell = (r, c)
                else:
                    blocked = True
                    break
            if not blocked and own == 3 and n_empty == 1 and empty_cell:
                threats.add(empty_cell)
        return list(threats)

    def _tactical_placement(self, game, empties):
        """Mandatory tactical checks before evaluation. Returns move or None."""
        empties_set = set(empties)
        # 1. Can we win by placing?
        for r, c in empties:
            bc = game.board.copy()
            bc.place(r, c, self.mark, PieceType.NORMAL)
            w, _ = bc.check_winner()
            if w == self.mark:
                return (r, c, PieceType.NORMAL)
        # 2. Can we win by place + push?
        for r, c in empties:
            bc = game.board.copy()
            bc.place(r, c, self.mark, PieceType.NORMAL)
            for axis, idx, d in _PUSH_SPECS:
                ab = _sim_push(bc, axis, idx, d)
                w, _ = ab.check_winner()
                if w == self.mark:
                    return (r, c, PieceType.NORMAL)
        # 3. Must block: opponent can win by placing next turn
        threats = self._find_win_threats(game.board, self.opp)
        if threats:
            for cell in threats:
                if cell in empties_set:
                    return (*cell, PieceType.NORMAL)
        # 4. Must block: opponent can win via push right now
        #    (they'll push on THEIR action phase, but if it's currently their
        #     turn coming up, we need to disrupt)
        #    Actually this is checked in action tactical.
        # 5. Prevent FUTURE threats: fork prevention (Medium/Hard)
        if self.difficulty in ("medium", "hard"):
            fork_cells = {}
            for line in _WIN_LINES:
                own = 0
                empty_cells = []
                blocked = False
                for r, c in line:
                    m = board_mark = game.board.grid[r][c].mark
                    if m == self.opp:
                        own += 1
                    elif m == Mark.EMPTY:
                        empty_cells.append((r, c))
                    else:
                        blocked = True
                        break
                if not blocked and own == 2 and len(empty_cells) == 2:
                    for ec in empty_cells:
                        if ec in empties_set:
                            fork_cells[ec] = fork_cells.get(ec, 0) + 1
            # A cell that appears in 2+ opponent 2-in-a-rows is a fork threat
            for cell, count in sorted(fork_cells.items(), key=lambda x: -x[1]):
                if count >= 2:
                    return (*cell, PieceType.NORMAL)
        return None

    def _tactical_action(self, game):
        """Mandatory tactical checks for action phase. Returns move or None."""
        # 1. Can we win with a push?
        for arrow in game.arrows:
            ab = self._simulate_action(game.board, arrow)
            w, _ = ab.check_winner()
            if w == self.mark:
                return ('push', arrow)
        # 2. Must break opponent's winning threat (3-in-a-row with open cell)
        threats = self._find_win_threats(game.board, self.opp)
        if threats:
            best_arrow = None
            best_remaining = len(threats)
            best_score = -999999
            for arrow in game.arrows:
                ab = self._simulate_action(game.board, arrow)
                remaining = len(self._find_win_threats(ab, self.opp))
                if remaining < best_remaining or (remaining == best_remaining
                                                   and self.evaluate(ab) > best_score):
                    best_remaining = remaining
                    best_arrow = arrow
                    best_score = self.evaluate(ab)
            if best_arrow and best_remaining < len(threats):
                return ('push', best_arrow)
        # 3. Prevent opponent surge-win combo (place+push+surge-push=win)
        if self.difficulty in ("medium", "hard"):
            if _can_surge_win(game.board, self.opp):
                best_arrow = None
                best_score = -999999
                for arrow in game.arrows:
                    ab = self._simulate_action(game.board, arrow)
                    if not _can_surge_win(ab, self.opp):
                        s = self.evaluate(ab)
                        if s > best_score:
                            best_score = s
                            best_arrow = arrow
                if best_arrow:
                    return ('push', best_arrow)
        return None

    # --- Placement ---
    def choose_placement(self, game):
        """Returns (r, c, PieceType)."""
        empties = [(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)
                   if game.board.grid[r][c].mark == Mark.EMPTY]
        if not empties:
            return None

        avail_types = [PieceType.NORMAL]
        for pt, cnt in game.power_pieces[self.mark].items():
            if cnt > 0:
                avail_types.append(pt)

        # Tactical override (all difficulties)
        tactical = self._tactical_placement(game, empties)
        if tactical:
            return tactical

        if self.difficulty == "hard":
            return self._minimax_placement(game, empties, avail_types)

        best = (-999999, None)
        for r, c in empties:
            for pt in avail_types:
                bc = game.board.copy()
                bc.place(r, c, self.mark, pt)
                if pt == PieceType.LEECH:
                    bc.apply_leech(r, c)
                s = self.evaluate(bc)
                if self.difficulty == "medium":
                    s = self._best_action_score(bc, game)
                if s > best[0]:
                    best = (s, (r, c, pt))
        return best[1]

    def _best_action_score(self, board, game):
        """Evaluate the best possible action on a given board state."""
        best = self.evaluate(board)  # skip baseline
        for arrow in game.arrows:
            bc = board.copy()
            d = 1 if arrow.direction in (Direction.DOWN, Direction.RIGHT) else -1
            ml = bc.push(arrow.axis, arrow.index, d)
            bc.apply_catalyst_effects(ml)
            bc.apply_warp_effects(ml)
            s = self.evaluate(bc)
            if bc.has_three_in_a_row(self.mark):
                s += 150  # surge bonus
            if s > best:
                best = s
        return best

    # --- Action ---
    def choose_action(self, game):
        """Returns ('push', arrow) or ('anchor', r, c) or ('skip',)."""
        # Tactical override (all difficulties)
        tactical = self._tactical_action(game)
        if tactical:
            return tactical

        if self.difficulty == "hard":
            return self._minimax_action(game)

        best = (self.evaluate(game.board), ('skip',))
        for arrow in game.arrows:
            bc = game.board.copy()
            d = 1 if arrow.direction in (Direction.DOWN, Direction.RIGHT) else -1
            ml = bc.push(arrow.axis, arrow.index, d)
            if self.difficulty == "medium":
                bc.apply_catalyst_effects(ml)
                bc.apply_warp_effects(ml)
            s = self.evaluate(bc)
            # Surge bonus for us
            if game.phase == Phase.ACTION and bc.has_three_in_a_row(self.mark):
                s += 150
            # Penalty if this leaves opponent with surge-win combo
            if _can_surge_win(bc, self.opp):
                s -= 50000
            if s > best[0]:
                best = (s, ('push', arrow))

        # Try anchoring
        if game.anchors[self.mark] > 0:
            for r in range(GRID_ROWS):
                for c in range(GRID_COLS):
                    cell = game.board.grid[r][c]
                    if cell.mark == self.mark and not cell.anchored:
                        zone = game.board.zones.get((r, c), Zone.NONE)
                        if zone != Zone.RIFT:
                            bc = game.board.copy()
                            bc.grid[r][c].anchored = True
                            s = self.evaluate(bc)
                            if s > best[0]:
                                best = (s, ('anchor', r, c))
        return best[1]

    # --- Minimax (Impossible) ---
    def _simulate_action(self, board, arrow):
        bc = board.copy()
        d = 1 if arrow.direction in (Direction.DOWN, Direction.RIGHT) else -1
        ml = bc.push(arrow.axis, arrow.index, d)
        bc.apply_catalyst_effects(ml)
        bc.apply_warp_effects(ml)
        return bc

    def _opp_piece_types(self, game):
        types = [PieceType.NORMAL]
        for pt, cnt in game.power_pieces.get(self.opp, {}).items():
            if cnt > 0:
                types.append(pt)
        return types

    def _minimax_placement(self, game, empties, avail_types):
        """Impossible: parallel deep evaluation of placements."""
        best = (-999999, None)
        opp_type_vals = [t.value for t in self._opp_piece_types(game)]
        opp_anchors = game.anchors.get(self.opp, 0)

        # Pre-score candidates
        candidates = []
        tie = 0
        for r, c in empties:
            for pt in avail_types:
                bc = game.board.copy()
                bc.place(r, c, self.mark, pt)
                if pt == PieceType.LEECH:
                    bc.apply_leech(r, c)
                quick_score = self._best_action_score(bc, game)
                candidates.append((quick_score, tie, r, c, pt))
                tie += 1
        candidates.sort(reverse=True)
        top = candidates[:16]

        # Prepare boards after our best action
        jobs = []
        for _, _, r, c, pt in top:
            bc = game.board.copy()
            bc.place(r, c, self.mark, pt)
            if pt == PieceType.LEECH:
                bc.apply_leech(r, c)
            best_board = bc
            best_s = self.evaluate(bc)
            for arrow in game.arrows:
                ab = self._simulate_action(bc, arrow)
                s = self.evaluate(ab)
                if ab.has_three_in_a_row(self.mark):
                    s += 200
                if s > best_s:
                    best_s = s
                    best_board = ab
            jobs.append((best_board, r, c, pt))

        # Parallel deep evaluation
        n_workers = min(os.cpu_count() or 4, 8)
        try:
            with ProcessPoolExecutor(max_workers=n_workers) as executor:
                futures = {}
                for board, r, c, pt in jobs:
                    f = executor.submit(_worker_deep_eval, board,
                                        self.mark, self.opp, opp_type_vals, opp_anchors)
                    futures[f] = (r, c, pt)
                done = 0
                for f in as_completed(futures):
                    done += 1
                    self.progress_frac = done / len(futures)
                    self.progress = f"{done}/{len(futures)}"
                    score = f.result()
                    rr, cc, pp = futures[f]
                    if score > best[0]:
                        best = (score, (rr, cc, pp))
        except Exception:
            # Fallback to sequential
            for board, r, c, pt in jobs:
                score = _worker_deep_eval(board, self.mark, self.opp, opp_type_vals, opp_anchors)
                if score > best[0]:
                    best = (score, (r, c, pt))
        return best[1]

    def _minimax_action(self, game):
        """Impossible: parallel deep evaluation of actions."""
        opp_type_vals = [t.value for t in self._opp_piece_types(game)]
        opp_anchors = game.anchors.get(self.opp, 0)

        # Prepare all action boards
        action_jobs = []
        # Skip
        action_jobs.append((game.board, ('skip',), False))
        # Pushes
        for arrow in game.arrows:
            ab = self._simulate_action(game.board, arrow)
            w, _ = ab.check_winner()
            if w == self.mark:
                return ('push', arrow)
            surge = game.phase == Phase.ACTION and ab.has_three_in_a_row(self.mark)
            if surge:
                best_surge = ab
                bonus_best = self.evaluate(ab)
                for a2 in game.arrows:
                    ab2 = self._simulate_action(ab, a2)
                    s = self.evaluate(ab2)
                    if s > bonus_best:
                        bonus_best = s
                        best_surge = ab2
                action_jobs.append((best_surge, ('push', arrow), True))
            else:
                action_jobs.append((ab, ('push', arrow), False))
        # Anchors
        if game.anchors[self.mark] > 0:
            for r in range(GRID_ROWS):
                for c in range(GRID_COLS):
                    cell = game.board.grid[r][c]
                    if cell.mark == self.mark and not cell.anchored:
                        zone = game.board.zones.get((r, c), Zone.NONE)
                        if zone != Zone.RIFT:
                            bc = game.board.copy()
                            bc.grid[r][c].anchored = True
                            action_jobs.append((bc, ('anchor', r, c), False))

        # Parallel deep evaluation
        best = (-999999, ('skip',))
        n_workers = min(os.cpu_count() or 4, 8)
        try:
            with ProcessPoolExecutor(max_workers=n_workers) as executor:
                futures = {}
                for board, action, is_surge in action_jobs:
                    f = executor.submit(_worker_deep_eval, board,
                                        self.mark, self.opp, opp_type_vals, opp_anchors)
                    futures[f] = (action, is_surge)
                done = 0
                for f in as_completed(futures):
                    done += 1
                    self.progress_frac = done / len(futures)
                    self.progress = f"{done}/{len(futures)}"
                    score = f.result()
                    action, is_surge = futures[f]
                    if is_surge:
                        score += 100
                    if score > best[0]:
                        best = (score, action)
        except Exception:
            for board, action, is_surge in action_jobs:
                score = _worker_deep_eval(board, self.mark, self.opp, opp_type_vals, opp_anchors)
                if is_surge:
                    score += 100
                if score > best[0]:
                    best = (score, action)
        return best[1]


# ---------------------------------------------------------------------------
# Arrow
# ---------------------------------------------------------------------------
class Arrow:
    def __init__(self, cx, cy, direction, axis, index, points):
        self.cx, self.cy = cx, cy
        self.direction = direction
        self.axis = axis
        self.index = index
        self.points = points
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        pad = 6
        self.rect = pygame.Rect(min(xs) - pad, min(ys) - pad,
                                max(xs) - min(xs) + 2 * pad,
                                max(ys) - min(ys) + 2 * pad)

    def contains(self, pos):
        return self.rect.collidepoint(pos)


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------
class DriftGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("DRIFT - No Move Is Safe. No Piece Is Permanent.")
        icon_path = self._res("assets/icon.png")
        if os.path.exists(icon_path):
            try:
                pygame.display.set_icon(pygame.image.load(icon_path))
            except Exception:
                pass
        self.clock = pygame.time.Clock()
        self.f_sm = pygame.font.SysFont("consolas", 15)
        self.f_md = pygame.font.SysFont("consolas", 20, bold=True)
        self.f_lg = pygame.font.SysFont("consolas", 34, bold=True)
        self.f_xl = pygame.font.SysFont("consolas", 48, bold=True)
        self.f_title = pygame.font.SysFont("consolas", 26, bold=True)
        self.f_zone = pygame.font.SysFont("consolas", 13, bold=True)

        # Title art
        self.title_art = None
        tp = self._res("assets/title_art.png")
        if os.path.exists(tp):
            try:
                img = pygame.image.load(tp).convert_alpha()
                scale = min(WIN_W - 60, img.get_width()) / img.get_width()
                self.title_art = pygame.transform.smoothscale(
                    img, (int(img.get_width() * scale), int(img.get_height() * scale)))
            except Exception:
                pass

        self.arrows = self._build_arrows()
        self.hovered_arrow = None
        self.hovered_cell = None

        # Animation
        self.animating = False
        self.anim_moves = []
        self.anim_start = 0
        self.pending_post_push = False

        # Buttons (positioned later in draw methods)
        btn_y = WIN_H - BOTTOM_MARGIN - 6
        sb_x = WIN_W - SIDEBAR_W + 15
        self.skip_btn = pygame.Rect(sb_x, btn_y, 100, 34)
        self.anchor_btn = pygame.Rect(sb_x + 115, btn_y, 100, 34)
        self.restart_btn = pygame.Rect(WIN_W // 2 - 80, WIN_H // 2 + 60, 160, 44)
        self.start_btn = pygame.Rect(WIN_W // 2 - 100, WIN_H // 2 + 80, 200, 50)
        self.confirm_btn = pygame.Rect(WIN_W // 2 - 80, 0, 160, 44)  # y set in draw

        # Mode select buttons
        ms_x = WIN_W // 2 - 120
        ms_y0 = 200
        gap = 60
        self.mode_btns = [
            (pygame.Rect(ms_x, ms_y0, 240, 44), "VS HUMAN", None),
            (pygame.Rect(ms_x, ms_y0 + gap, 240, 44), "VS AI: EASY", "easy"),
            (pygame.Rect(ms_x, ms_y0 + gap * 2, 240, 44), "VS AI: MEDIUM", "medium"),
            (pygame.Rect(ms_x, ms_y0 + gap * 3, 240, 44), "VS AI: HARD", "hard"),
        ]

        # Draft card rects (built in draw)
        self.card_rects = []
        self._build_card_rects()

        # Power piece buttons in sidebar (built once)
        self.pp_btns = []  # list of (rect, PieceType)

        self.reset_to_title()

    def _res(self, rel):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, rel)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)

    def _build_arrows(self):
        arrows = []
        sz = 12
        offset = 26
        for c in range(GRID_COLS):
            cx = BOARD_X0 + c * CELL_SIZE + CELL_SIZE // 2
            cy = BOARD_Y0 - offset
            arrows.append(Arrow(cx, cy, Direction.DOWN, "col", c,
                                [(cx, cy + sz), (cx - sz, cy - sz // 2), (cx + sz, cy - sz // 2)]))
        for c in range(GRID_COLS):
            cx = BOARD_X0 + c * CELL_SIZE + CELL_SIZE // 2
            cy = BOARD_Y0 + BOARD_H + offset
            arrows.append(Arrow(cx, cy, Direction.UP, "col", c,
                                [(cx, cy - sz), (cx - sz, cy + sz // 2), (cx + sz, cy + sz // 2)]))
        for r in range(GRID_ROWS):
            cx = BOARD_X0 - offset
            cy = BOARD_Y0 + r * CELL_SIZE + CELL_SIZE // 2
            arrows.append(Arrow(cx, cy, Direction.RIGHT, "row", r,
                                [(cx + sz, cy), (cx - sz // 2, cy - sz), (cx - sz // 2, cy + sz)]))
        for r in range(GRID_ROWS):
            cx = BOARD_X0 + BOARD_W + offset
            cy = BOARD_Y0 + r * CELL_SIZE + CELL_SIZE // 2
            arrows.append(Arrow(cx, cy, Direction.LEFT, "row", r,
                                [(cx - sz, cy), (cx + sz // 2, cy - sz), (cx + sz // 2, cy + sz)]))
        return arrows

    def _build_card_rects(self):
        cw, ch, gap = 180, 130, 20
        gw = cw * 2 + gap
        sx = (WIN_W - gw) // 2
        sy = 160
        self.card_rects = []
        for row in range(2):
            for col in range(2):
                self.card_rects.append(pygame.Rect(
                    sx + col * (cw + gap), sy + row * (ch + gap), cw, ch))
        self.confirm_btn = pygame.Rect(WIN_W // 2 - 80, sy + 2 * (ch + gap) + 20, 160, 44)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------
    def reset_to_title(self):
        self.phase = Phase.TITLE
        self.board = Board()
        self.current_player = Mark.X
        self.anchors = {Mark.X: ANCHORS_PER_PLAYER, Mark.O: ANCHORS_PER_PLAYER}
        self.power_pieces = {Mark.X: {}, Mark.O: {}}
        self.winner = None
        self.win_line = None
        self.win_time = 0
        self.turn_number = 1
        self.animating = False
        self.anchor_mode = False
        self.selected_pp = None  # selected power piece type for placement
        self.message = ""
        self.msg_time = 0
        # Draft state
        self.draft_player = Mark.X
        self.draft_counts = {}  # PieceType -> int
        self._reset_draft_counts()
        # AI state
        self.ai_enabled = False
        self.ai_difficulty = None
        self.ai = None
        self.ai_think_start = 0
        self.ai_thread = None
        self.ai_result = None
        self.ai_computing = False
        self.ai_compute_start = 0

    def _reset_draft_counts(self):
        self.draft_counts = {pt: 0 for pt, _, _, _ in POWER_PIECE_INFO}

    def start_draft(self):
        self.phase = Phase.DRAFT
        self.draft_player = Mark.X
        self._reset_draft_counts()

    def confirm_draft(self):
        picks = {pt: n for pt, n in self.draft_counts.items() if n > 0}
        self.power_pieces[self.draft_player] = picks
        if self.draft_player == Mark.X:
            self.draft_player = Mark.O
            self._reset_draft_counts()
            # If AI, auto-draft for O
            if self.ai_enabled:
                self.power_pieces[Mark.O] = self.ai.choose_draft()
                self.phase = Phase.PLACE
                self.current_player = Mark.X
                self.turn_number = 1
        else:
            self.phase = Phase.PLACE
            self.current_player = Mark.X
            self.turn_number = 1

    def reset_game(self):
        """Full reset back to draft."""
        self.board = Board()
        self.current_player = Mark.X
        self.anchors = {Mark.X: ANCHORS_PER_PLAYER, Mark.O: ANCHORS_PER_PLAYER}
        self.power_pieces = {Mark.X: {}, Mark.O: {}}
        self.winner = None
        self.win_line = None
        self.turn_number = 1
        self.animating = False
        self.anchor_mode = False
        self.selected_pp = None
        self.message = ""
        self.start_draft()

    # ------------------------------------------------------------------
    # Game logic
    # ------------------------------------------------------------------
    def do_place(self, r, c):
        if self.phase != Phase.PLACE or self.animating:
            return
        pt = self.selected_pp or PieceType.NORMAL
        if pt != PieceType.NORMAL:
            avail = self.power_pieces[self.current_player].get(pt, 0)
            if avail <= 0:
                self.set_msg("No pieces of that type left!")
                return
        if not self.board.place(r, c, self.current_player, pt):
            return
        # Consume power piece
        if pt != PieceType.NORMAL:
            self.power_pieces[self.current_player][pt] -= 1
            self.selected_pp = None
        # Leech effect
        if pt == PieceType.LEECH:
            self.board.apply_leech(r, c)
        # Win check
        w, line = self.board.check_winner()
        if w:
            self._set_winner(w, line)
            return
        self.phase = Phase.ACTION
        self.anchor_mode = False

    def do_push(self, arrow):
        if self.phase not in (Phase.ACTION, Phase.SURGE) or self.animating:
            return
        axis = arrow.axis
        index = arrow.index
        d = 1 if arrow.direction in (Direction.DOWN, Direction.RIGHT) else -1
        pre = [[self.board.grid[r][c].copy() for c in range(GRID_COLS)] for r in range(GRID_ROWS)]
        move_list = self.board.push(axis, index, d)
        self.anim_moves = []
        for (or_, oc, nr, nc) in move_list:
            cell = pre[or_][oc]
            if cell.mark != Mark.EMPTY:
                self.anim_moves.append((or_, oc, nr, nc, cell.mark, cell.age,
                                        cell.anchored, cell.piece_type, cell.phantom_turns))
        self._push_move_list = move_list
        self.animating = True
        self.anim_start = pygame.time.get_ticks()
        self.pending_post_push = True

    def _on_push_complete(self):
        """Called when push animation finishes."""
        move_list = self._push_move_list
        # Catalyst chain
        cat_moves = self.board.apply_catalyst_effects(move_list)
        # Warp teleports (from original push + catalyst moves)
        all_moves = move_list + cat_moves
        self.board.apply_warp_effects(all_moves)
        # Win check
        w, line = self.board.check_winner()
        if w:
            self._set_winner(w, line)
            return
        # Surge check (only from ACTION, not from SURGE)
        if self.phase == Phase.ACTION:
            if self.board.has_three_in_a_row(self.current_player):
                self.phase = Phase.SURGE
                self.set_msg("SURGE! Bonus action!")
                return
        self.end_turn()

    def do_anchor(self, r, c):
        if self.phase not in (Phase.ACTION, Phase.SURGE) or self.animating:
            return
        cell = self.board.grid[r][c]
        if cell.mark != self.current_player:
            return
        if cell.anchored:
            self.set_msg("Already anchored!")
            return
        zone = self.board.zones.get((r, c), Zone.NONE)
        if zone == Zone.RIFT:
            self.set_msg("Can't anchor on Rift!")
            return
        if self.anchors[self.current_player] <= 0:
            self.set_msg("No anchors left!")
            return
        cell.anchored = True
        self.anchors[self.current_player] -= 1
        self.end_turn()

    def do_skip(self):
        if self.phase not in (Phase.ACTION, Phase.SURGE) or self.animating:
            return
        self.end_turn()

    def end_turn(self):
        removed = self.board.age_pieces()
        w, line = self.board.check_winner()
        if w:
            self._set_winner(w, line)
            return
        self.current_player = Mark.O if self.current_player == Mark.X else Mark.X
        self.phase = Phase.PLACE
        self.anchor_mode = False
        self.selected_pp = None
        self.turn_number += 1

    def _set_winner(self, mark, line):
        self.winner = mark
        self.win_line = line
        self.win_time = pygame.time.get_ticks()
        self.phase = Phase.GAME_OVER

    def set_msg(self, msg):
        self.message = msg
        self.msg_time = pygame.time.get_ticks()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self):
        self.screen.fill(BG_COLOR)
        if self.phase == Phase.TITLE:
            self._draw_title()
        elif self.phase == Phase.MODE_SELECT:
            self._draw_mode_select()
        elif self.phase == Phase.DRAFT:
            self._draw_draft()
        else:
            self._draw_header()
            self._draw_sidebar()
            self._draw_board()
            self._draw_arrows()
            if self.phase in (Phase.ACTION, Phase.SURGE) and not self.animating:
                self._draw_action_buttons()
            if self.phase == Phase.GAME_OVER:
                self._draw_game_over()
            if self.message and pygame.time.get_ticks() - self.msg_time < 2500:
                self._draw_message()
        pygame.display.flip()

    # --- Title ---
    def _draw_title(self):
        if self.title_art:
            ax = (WIN_W - self.title_art.get_width()) // 2
            self.screen.blit(self.title_art, (ax, WIN_H // 2 - self.title_art.get_height() // 2 - 40))
        else:
            t = self.f_xl.render("DRIFT", True, (0, 212, 255))
            self.screen.blit(t, (WIN_W // 2 - t.get_width() // 2, WIN_H // 3))
        mouse = pygame.mouse.get_pos()
        h = self.start_btn.collidepoint(mouse)
        pygame.draw.rect(self.screen, BUTTON_HOVER if h else BUTTON_COLOR, self.start_btn, border_radius=10)
        pygame.draw.rect(self.screen, (0, 212, 255), self.start_btn, 2, border_radius=10)
        t = self.f_md.render("START GAME", True, BUTTON_TEXT)
        self.screen.blit(t, (self.start_btn.centerx - t.get_width() // 2,
                             self.start_btn.centery - t.get_height() // 2))
        h2 = self.f_sm.render("No move is safe. No piece is permanent.", True, (80, 110, 140))
        self.screen.blit(h2, (WIN_W // 2 - h2.get_width() // 2, self.start_btn.bottom + 20))

    # --- Mode Select ---
    def _draw_mode_select(self):
        title = self.f_lg.render("SELECT MODE", True, (0, 212, 255))
        self.screen.blit(title, (WIN_W // 2 - title.get_width() // 2, 80))
        sub = self.f_sm.render("Player X is always human. Choose opponent.", True, (100, 140, 170))
        self.screen.blit(sub, (WIN_W // 2 - sub.get_width() // 2, 125))

        mouse = pygame.mouse.get_pos()
        diff_colors = {
            None: (0, 212, 255),
            "easy": (100, 200, 100),
            "medium": (200, 180, 60),
            "hard": (220, 80, 80),
        }
        for rect, label, diff in self.mode_btns:
            h = rect.collidepoint(mouse)
            bg = BUTTON_HOVER if h else BUTTON_COLOR
            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            pygame.draw.rect(self.screen, diff_colors.get(diff, GRID_COLOR), rect, 2, border_radius=8)
            t = self.f_md.render(label, True, BUTTON_TEXT)
            self.screen.blit(t, (rect.centerx - t.get_width() // 2,
                                 rect.centery - t.get_height() // 2))

        descs = [
            "Two humans, same screen.",
            "Heuristic evaluation. Fair challenge.",
            "Plans placement + action combos.",
            "Minimax: 2 turns ahead. Good luck.",
        ]
        base_y = 170 + 52 * 5 + 12
        for i, text in enumerate(descs):
            t = self.f_sm.render(text, True, (80, 100, 130))
            # Position each desc next to its button
            btn_rect = self.mode_btns[i][0]
            self.screen.blit(t, (btn_rect.right + 12, btn_rect.centery - t.get_height() // 2))

    # --- Draft ---
    def _draw_draft(self):
        pname = "X" if self.draft_player == Mark.X else "O"
        pcol = X_COLOR if self.draft_player == Mark.X else O_COLOR
        title = self.f_lg.render("DRAFT POWER PIECES", True, (0, 212, 255))
        self.screen.blit(title, (WIN_W // 2 - title.get_width() // 2, 40))
        sub = self.f_md.render(f"Player {pname} - Choose 2", True, pcol)
        self.screen.blit(sub, (WIN_W // 2 - sub.get_width() // 2, 90))
        total = sum(self.draft_counts.values())
        sel_text = self.f_sm.render(f"Selected: {total}/2", True, TEXT_COLOR)
        self.screen.blit(sel_text, (WIN_W // 2 - sel_text.get_width() // 2, 128))

        mouse = pygame.mouse.get_pos()
        for i, (pt, name, desc1, desc2) in enumerate(POWER_PIECE_INFO):
            rect = self.card_rects[i]
            cnt = self.draft_counts[pt]
            hover = rect.collidepoint(mouse)
            # Background
            bg = (35, 55, 80) if hover else (20, 36, 56)
            if cnt > 0:
                bg = (40, 65, 95)
            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            # Border
            bc = POWER_COLORS.get(pt.value, GRID_COLOR)
            bw = 2 if cnt == 0 else 3
            pygame.draw.rect(self.screen, bc, rect, bw, border_radius=8)
            # Name
            nt = self.f_md.render(name, True, bc)
            self.screen.blit(nt, (rect.x + rect.w // 2 - nt.get_width() // 2, rect.y + 12))
            # Description
            d1 = self.f_sm.render(desc1, True, (160, 180, 200))
            d2 = self.f_sm.render(desc2, True, (160, 180, 200))
            self.screen.blit(d1, (rect.x + rect.w // 2 - d1.get_width() // 2, rect.y + 50))
            self.screen.blit(d2, (rect.x + rect.w // 2 - d2.get_width() // 2, rect.y + 70))
            # Count indicator
            if cnt > 0:
                ct = self.f_md.render(f"x{cnt}", True, SURGE_COLOR)
                self.screen.blit(ct, (rect.x + rect.w // 2 - ct.get_width() // 2, rect.y + 98))
            # Click hint
            hint = "L-click: add  R-click: remove"
            ht = self.f_sm.render(hint, True, (70, 90, 110))
            # Only show hint at bottom of card area
        # Hint below cards
        ht = self.f_sm.render("Left-click: add | Right-click: remove", True, (70, 90, 110))
        self.screen.blit(ht, (WIN_W // 2 - ht.get_width() // 2, self.confirm_btn.y - 26))

        # Confirm button
        can_confirm = total == 2
        h = self.confirm_btn.collidepoint(mouse) and can_confirm
        c = BUTTON_HOVER if h else (BUTTON_COLOR if can_confirm else (25, 35, 50))
        pygame.draw.rect(self.screen, c, self.confirm_btn, border_radius=8)
        bc = (0, 212, 255) if can_confirm else (40, 60, 80)
        pygame.draw.rect(self.screen, bc, self.confirm_btn, 2, border_radius=8)
        tc = BUTTON_TEXT if can_confirm else (60, 70, 80)
        t = self.f_md.render("CONFIRM", True, tc)
        self.screen.blit(t, (self.confirm_btn.centerx - t.get_width() // 2,
                             self.confirm_btn.centery - t.get_height() // 2))

    # --- Header ---
    def _draw_header(self):
        t = self.f_title.render("DRIFT", True, (0, 212, 255))
        self.screen.blit(t, (BOARD_X0, 12))
        s = self.f_sm.render("No Move Is Safe. No Piece Is Permanent.", True, (100, 140, 170))
        self.screen.blit(s, (BOARD_X0, 44))
        if self.phase != Phase.GAME_OVER:
            pn = "X" if self.current_player == Mark.X else "O"
            pc = X_COLOR if self.current_player == Mark.X else O_COLOR
            ps = self.f_md.render(f"Player {pn}", True, pc)
            if self.phase == Phase.PLACE:
                pp_name = self.selected_pp.value.upper() if self.selected_pp else "NORMAL"
                phase_text = f"PLACE ({pp_name})"
                phase_col = (0, 212, 255)
            elif self.phase == Phase.SURGE:
                phase_text = "SURGE! BONUS ACTION"
                phase_col = SURGE_COLOR
            else:
                phase_text = "PUSH / ANCHOR / SKIP"
                phase_col = (255, 165, 0)
            pt = self.f_sm.render(phase_text, True, phase_col)
            self.screen.blit(ps, (BOARD_X0 + BOARD_W - ps.get_width(), 14))
            self.screen.blit(pt, (BOARD_X0 + BOARD_W - pt.get_width(), 42))
            # AI thinking indicator
            if self._is_ai_turn():
                if self.ai_computing and self.ai:
                    frac = self.ai.progress_frac
                    # Progress bar only, no text
                    bar_x = BOARD_X0
                    bar_y = 68
                    bar_w = BOARD_W
                    bar_h = 4
                    pygame.draw.rect(self.screen, (30, 50, 70), (bar_x, bar_y, bar_w, bar_h))
                    fill_w = max(1, int(bar_w * frac))
                    pulse = 0.7 + 0.3 * abs(math.sin(pygame.time.get_ticks() / 300))
                    bar_c = tuple(int(v * pulse) for v in (0, 200, 255))
                    pygame.draw.rect(self.screen, bar_c, (bar_x, bar_y, fill_w, bar_h))
                else:
                    pulse = abs(math.sin(pygame.time.get_ticks() / 400))
                    ai_c = tuple(int(v * (0.5 + 0.5 * pulse)) for v in (100, 180, 255))
                    at = self.f_sm.render(f"AI thinking...", True, ai_c)
                    self.screen.blit(at, (BOARD_X0 + BOARD_W - at.get_width(), 62))

    # --- Sidebar ---
    def _draw_sidebar(self):
        sb = pygame.Rect(WIN_W - SIDEBAR_W, 0, SIDEBAR_W, WIN_H)
        pygame.draw.rect(self.screen, SIDEBAR_BG, sb)
        x = WIN_W - SIDEBAR_W + 15
        y = TOP_MARGIN - 4
        # Turn
        self.screen.blit(self.f_sm.render(f"Turn: {self.turn_number}", True, TEXT_COLOR), (x, y))
        y += 24
        # Anchors
        for m in (Mark.X, Mark.O):
            c = X_COLOR if m == Mark.X else O_COLOR
            n = "X" if m == Mark.X else "O"
            rem = self.anchors[m]
            self.screen.blit(self.f_sm.render(
                f"{n} Anchors: {'*' * rem}{'.' * (ANCHORS_PER_PLAYER - rem)}", True, c), (x, y))
            y += 20
        y += 8
        # Power pieces
        self.screen.blit(self.f_sm.render("POWER PIECES:", True, (0, 212, 255)), (x, y))
        y += 22
        self.pp_btns = []
        bw, bh = 124, 28
        for i, (pt, name, _, _) in enumerate(POWER_PIECE_INFO):
            col_idx = i % 2
            row_idx = i // 2
            bx = x + col_idx * (bw + 6)
            by = y + row_idx * (bh + 4)
            rect = pygame.Rect(bx, by, bw, bh)
            self.pp_btns.append((rect, pt))
            avail = self.power_pieces[self.current_player].get(pt, 0)
            is_sel = (self.selected_pp == pt)
            mouse = pygame.mouse.get_pos()
            hover = rect.collidepoint(mouse)
            if avail > 0:
                bg = (60, 50, 20) if is_sel else (BUTTON_HOVER if hover else BUTTON_COLOR)
                pygame.draw.rect(self.screen, bg, rect, border_radius=4)
                bc = POWER_COLORS.get(pt.value, GRID_COLOR) if is_sel else (60, 90, 120)
                pygame.draw.rect(self.screen, bc, rect, 1, border_radius=4)
                label = f"{name[:7]} x{avail}"
                tc = POWER_COLORS.get(pt.value, TEXT_COLOR) if is_sel else BUTTON_TEXT
            else:
                pygame.draw.rect(self.screen, (22, 30, 42), rect, border_radius=4)
                pygame.draw.rect(self.screen, (35, 45, 55), rect, 1, border_radius=4)
                label = f"{name[:7]} x0"
                tc = (55, 65, 75)
            t = self.f_sm.render(label, True, tc)
            self.screen.blit(t, (rect.x + rect.w // 2 - t.get_width() // 2,
                                 rect.y + rect.h // 2 - t.get_height() // 2))
        y += 2 * (bh + 4) + 10

        # Zone legend
        self.screen.blit(self.f_sm.render("ZONES:", True, (0, 212, 255)), (x, y))
        y += 20
        zone_info = [
            ("Rift", "rift", "Eternal, no anchor"),
            ("Accel", "accel", "2x aging speed"),
            ("Warp", "warp", "Linked teleport"),
        ]
        for name, key, desc in zone_info:
            c = ZONE_TEXT_COLORS[key]
            self.screen.blit(self.f_sm.render(f"  {name}: {desc}", True, c), (x, y))
            y += 18
        y += 8

        # Momentum
        self.screen.blit(self.f_sm.render("MOMENTUM:", True, (0, 212, 255)), (x, y))
        y += 20
        self.screen.blit(self.f_sm.render("  Push 3-in-a-row = SURGE", True, SURGE_COLOR), (x, y))
        y += 18
        self.screen.blit(self.f_sm.render("  (bonus action!)", True, (140, 130, 60)), (x, y))
        y += 24

        # Quick ref
        self.screen.blit(self.f_sm.render("HOW TO PLAY:", True, (0, 212, 255)), (x, y))
        y += 20
        for line in ["1. PLACE mark (or power)", "2. PUSH / ANCHOR / SKIP",
                      "4-in-a-row wins!", "Decay after 6 turns",
                      "R=restart  ESC=quit"]:
            self.screen.blit(self.f_sm.render(f"  {line}", True, (130, 150, 170)), (x, y))
            y += 18

    # --- Board ---
    def _draw_board(self):
        br = pygame.Rect(BOARD_X0, BOARD_Y0, BOARD_W, BOARD_H)
        pygame.draw.rect(self.screen, (14, 28, 48), br)

        # Draw zones
        for (r, c), zone in self.board.zones.items():
            x = BOARD_X0 + c * CELL_SIZE
            y = BOARD_Y0 + r * CELL_SIZE
            key = zone.value
            if key in ZONE_COLORS:
                s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                s.fill(ZONE_COLORS[key])
                self.screen.blit(s, (x, y))
                tc = ZONE_TEXT_COLORS.get(key, TEXT_COLOR)
                label = {"rift": "RIFT", "accel": "ACCEL", "warp": "WARP"}.get(key, "")
                zt = self.f_zone.render(label, True, tc)
                self.screen.blit(zt, (x + CELL_SIZE // 2 - zt.get_width() // 2, y + 4))

        # Draw warp connection line
        warp_cells = [pos for pos, z in self.board.zones.items() if z == Zone.WARP]
        if len(warp_cells) == 2:
            (r1, c1), (r2, c2) = warp_cells
            p1 = (BOARD_X0 + c1 * CELL_SIZE + CELL_SIZE // 2, BOARD_Y0 + r1 * CELL_SIZE + CELL_SIZE // 2)
            p2 = (BOARD_X0 + c2 * CELL_SIZE + CELL_SIZE // 2, BOARD_Y0 + r2 * CELL_SIZE + CELL_SIZE // 2)
            pygame.draw.line(self.screen, (80, 40, 120), p1, p2, 1)

        # Hover highlight
        if self.hovered_cell and not self.animating:
            hr, hc = self.hovered_cell
            hx = BOARD_X0 + hc * CELL_SIZE
            hy = BOARD_Y0 + hr * CELL_SIZE
            if self.phase == Phase.PLACE and self.board.grid[hr][hc].mark == Mark.EMPTY:
                s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                s.fill((255, 255, 255, 20))
                self.screen.blit(s, (hx, hy))
            elif self.anchor_mode and self.phase in (Phase.ACTION, Phase.SURGE):
                cell = self.board.grid[hr][hc]
                if cell.mark == self.current_player and not cell.anchored:
                    s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                    s.fill((255, 215, 0, 25))
                    self.screen.blit(s, (hx, hy))

        # Draw pieces (or animation)
        if self.animating:
            self._draw_anim_pieces()
        else:
            for r in range(GRID_ROWS):
                for c in range(GRID_COLS):
                    cell = self.board.grid[r][c]
                    if cell.mark != Mark.EMPTY:
                        self._draw_mark(BOARD_X0 + c * CELL_SIZE, BOARD_Y0 + r * CELL_SIZE, cell)

        # Grid lines
        for i in range(GRID_COLS + 1):
            lx = BOARD_X0 + i * CELL_SIZE
            pygame.draw.line(self.screen, GRID_COLOR, (lx, BOARD_Y0), (lx, BOARD_Y0 + BOARD_H), 2)
        for i in range(GRID_ROWS + 1):
            ly = BOARD_Y0 + i * CELL_SIZE
            pygame.draw.line(self.screen, GRID_COLOR, (BOARD_X0, ly), (BOARD_X0 + BOARD_W, ly), 2)

        # Win line
        if self.win_line:
            self._draw_win_line()

    def _draw_anim_pieces(self):
        t = (pygame.time.get_ticks() - self.anim_start) / (ANIM_DURATION * 1000)
        t = min(t, 1.0)
        t = 1 - (1 - t) ** 3  # ease out

        for (or_, oc, nr, nc, mark, age, anchored, ptype, ph_turns) in self.anim_moves:
            ox, oy = BOARD_X0 + oc * CELL_SIZE, BOARD_Y0 + or_ * CELL_SIZE
            nx, ny = BOARD_X0 + nc * CELL_SIZE, BOARD_Y0 + nr * CELL_SIZE
            dx, dy = nx - ox, ny - oy
            if abs(dx) > CELL_SIZE * 2:
                dx += -BOARD_W if dx > 0 else BOARD_W
            if abs(dy) > CELL_SIZE * 2:
                dy += -BOARD_H if dy > 0 else BOARD_H
            temp = Cell()
            temp.mark = mark
            temp.age = age
            temp.anchored = anchored
            temp.piece_type = ptype
            temp.phantom_turns = ph_turns
            self._draw_mark(ox + dx * t, oy + dy * t, temp)

        # Non-animated pieces
        anim_dests = {(nr, nc) for (_, _, nr, nc, *_) in self.anim_moves}
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                if (r, c) not in anim_dests:
                    cell = self.board.grid[r][c]
                    if cell.mark != Mark.EMPTY:
                        self._draw_mark(BOARD_X0 + c * CELL_SIZE, BOARD_Y0 + r * CELL_SIZE, cell)

        if t >= 1.0:
            self.animating = False
            if self.pending_post_push:
                self.pending_post_push = False
                self._on_push_complete()

    def _draw_mark(self, x, y, cell):
        cx = int(x + CELL_SIZE // 2)
        cy = int(y + CELL_SIZE // 2)
        max_a = SENTINEL_DECAY if cell.piece_type == PieceType.SENTINEL else MAX_AGE
        fade = max(0.2, 1.0 - (cell.age / (max_a + 1)) * 0.8)
        sz = int(CELL_SIZE * 0.28)  # slightly smaller to avoid edge overlaps
        is_phantom = cell.piece_type == PieceType.PHANTOM and cell.phantom_turns > 0
        if is_phantom:
            fade *= 0.5

        base = X_COLOR if cell.mark == Mark.X else O_COLOR
        color = tuple(int(c * fade) for c in base)
        lw = max(3, int(5 * fade))

        if cell.mark == Mark.X:
            if is_phantom:
                for frac in [0.0, 0.3, 0.6]:
                    s = frac
                    e = min(frac + 0.2, 1.0)
                    pygame.draw.line(self.screen, color,
                                     (int(cx - sz + 2 * sz * s), int(cy - sz + 2 * sz * s)),
                                     (int(cx - sz + 2 * sz * e), int(cy - sz + 2 * sz * e)), lw)
                    pygame.draw.line(self.screen, color,
                                     (int(cx + sz - 2 * sz * s), int(cy - sz + 2 * sz * s)),
                                     (int(cx + sz - 2 * sz * e), int(cy - sz + 2 * sz * e)), lw)
            else:
                pygame.draw.line(self.screen, color, (cx - sz, cy - sz), (cx + sz, cy + sz), lw)
                pygame.draw.line(self.screen, color, (cx + sz, cy - sz), (cx - sz, cy + sz), lw)
        elif cell.mark == Mark.O:
            if is_phantom:
                for angle in range(0, 360, 40):
                    a1 = math.radians(angle)
                    a2 = math.radians(angle + 20)
                    pygame.draw.line(self.screen, color,
                                     (int(cx + sz * math.cos(a1)), int(cy + sz * math.sin(a1))),
                                     (int(cx + sz * math.cos(a2)), int(cy + sz * math.sin(a2))), lw)
            else:
                pygame.draw.circle(self.screen, color, (cx, cy), sz, lw)

        # Power piece type indicator (bottom-right corner, clear of mark)
        if cell.piece_type != PieceType.NORMAL:
            pt_col = POWER_COLORS.get(cell.piece_type.value, TEXT_COLOR)
            pt_col = tuple(int(c * fade) for c in pt_col)
            label = {"phantom": "Ph", "catalyst": "Ca", "leech": "Le", "sentinel": "Se"
                     }.get(cell.piece_type.value, "")
            if label:
                lt = self.f_zone.render(label, True, pt_col)
                self.screen.blit(lt, (int(x + CELL_SIZE - lt.get_width() - 6),
                                      int(y + CELL_SIZE - lt.get_height() - 18)))

        # Anchor indicator
        if cell.anchored:
            pygame.draw.rect(self.screen, ANCHOR_COLOR,
                             (int(x + 6), int(y + 6), CELL_SIZE - 12, CELL_SIZE - 12), 2)
            ax, ay = int(x + 14), int(y + 14)
            d = 4
            pygame.draw.polygon(self.screen, ANCHOR_COLOR,
                                [(ax, ay - d), (ax + d, ay), (ax, ay + d), (ax - d, ay)])

        # Age dots (moved inward, smaller spacing)
        if cell.mark != Mark.EMPTY:
            dot_spacing = 6
            total_w = max_a * dot_spacing
            start_x = cx - total_w // 2 + dot_spacing // 2
            dot_y = int(y + CELL_SIZE - 16)
            for i in range(max_a):
                dx = start_x + i * dot_spacing
                filled = i < cell.age
                dc = ((80, 50, 50) if cell.mark == Mark.X else (30, 70, 50)) if filled else (35, 45, 55)
                pygame.draw.circle(self.screen, dc, (dx, dot_y), 2)

    def _draw_win_line(self):
        r0, c0 = self.win_line[0]
        r1, c1 = self.win_line[-1]
        p0 = (BOARD_X0 + c0 * CELL_SIZE + CELL_SIZE // 2, BOARD_Y0 + r0 * CELL_SIZE + CELL_SIZE // 2)
        p1 = (BOARD_X0 + c1 * CELL_SIZE + CELL_SIZE // 2, BOARD_Y0 + r1 * CELL_SIZE + CELL_SIZE // 2)
        for w, c in [(8, (100, 150, 200)), (5, (200, 220, 255)), (2, (255, 255, 255))]:
            pygame.draw.line(self.screen, c, p0, p1, w)

    # --- Arrows ---
    def _draw_arrows(self):
        active = self.phase in (Phase.ACTION, Phase.SURGE) and not self.animating and not self.anchor_mode
        for arrow in self.arrows:
            if active:
                c = ARROW_HOVER if arrow == self.hovered_arrow else ARROW_COLOR
            else:
                c = (30, 45, 60)
            pygame.draw.polygon(self.screen, c, arrow.points)

    # --- Action buttons ---
    def _draw_action_buttons(self):
        mouse = pygame.mouse.get_pos()
        # Skip
        h = self.skip_btn.collidepoint(mouse)
        pygame.draw.rect(self.screen, BUTTON_HOVER if h else BUTTON_COLOR, self.skip_btn, border_radius=6)
        pygame.draw.rect(self.screen, GRID_COLOR, self.skip_btn, 1, border_radius=6)
        t = self.f_sm.render("Skip", True, BUTTON_TEXT)
        self.screen.blit(t, (self.skip_btn.centerx - t.get_width() // 2,
                             self.skip_btn.centery - t.get_height() // 2))
        # Anchor
        can = self.anchors[self.current_player] > 0
        if can:
            h = self.anchor_btn.collidepoint(mouse)
            bg = (80, 70, 20) if self.anchor_mode else (BUTTON_HOVER if h else BUTTON_COLOR)
            pygame.draw.rect(self.screen, bg, self.anchor_btn, border_radius=6)
            bc = ANCHOR_COLOR if self.anchor_mode else GRID_COLOR
            pygame.draw.rect(self.screen, bc, self.anchor_btn, 1, border_radius=6)
            label = "Anchoring..." if self.anchor_mode else "Anchor"
            tc = ANCHOR_COLOR if self.anchor_mode else BUTTON_TEXT
        else:
            pygame.draw.rect(self.screen, (30, 30, 40), self.anchor_btn, border_radius=6)
            label = "No Anchors"
            tc = (80, 80, 90)
        t = self.f_sm.render(label, True, tc)
        self.screen.blit(t, (self.anchor_btn.centerx - t.get_width() // 2,
                             self.anchor_btn.centery - t.get_height() // 2))

        # Surge indicator
        if self.phase == Phase.SURGE:
            pulse = abs(math.sin(pygame.time.get_ticks() / 300))
            sc = tuple(int(c * (0.6 + 0.4 * pulse)) for c in SURGE_COLOR)
            st = self.f_md.render("SURGE!", True, sc)
            self.screen.blit(st, (self.skip_btn.x, self.skip_btn.y - 30))

    # --- Game over ---
    def _draw_game_over(self):
        ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140))
        self.screen.blit(ov, (0, 0))
        if self.winner:
            n = "X" if self.winner == Mark.X else "O"
            c = X_COLOR if self.winner == Mark.X else O_COLOR
            t = self.f_xl.render(f"Player {n} Wins!", True, c)
        else:
            t = self.f_xl.render("Draw!", True, TEXT_COLOR)
        self.screen.blit(t, (WIN_W // 2 - t.get_width() // 2, WIN_H // 2 - 50))
        mouse = pygame.mouse.get_pos()
        h = self.restart_btn.collidepoint(mouse)
        pygame.draw.rect(self.screen, BUTTON_HOVER if h else BUTTON_COLOR, self.restart_btn, border_radius=8)
        pygame.draw.rect(self.screen, GRID_COLOR, self.restart_btn, 2, border_radius=8)
        t = self.f_md.render("Play Again", True, BUTTON_TEXT)
        self.screen.blit(t, (self.restart_btn.centerx - t.get_width() // 2,
                             self.restart_btn.centery - t.get_height() // 2))
        h2 = self.f_sm.render("Press R to restart", True, (80, 110, 140))
        self.screen.blit(h2, (WIN_W // 2 - h2.get_width() // 2, self.restart_btn.bottom + 12))

    def _draw_message(self):
        elapsed = pygame.time.get_ticks() - self.msg_time
        if elapsed > 2500:
            return
        t = self.f_sm.render(self.message, True, SURGE_COLOR if "SURGE" in self.message else (255, 200, 100))
        self.screen.blit(t, (BOARD_X0, BOARD_Y0 + BOARD_H + ARROW_MARGIN + 4))

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def _is_ai_turn(self):
        return self.ai_enabled and self.current_player == Mark.O and self.phase not in (
            Phase.TITLE, Phase.MODE_SELECT, Phase.GAME_OVER)

    def handle_click(self, pos, button=1):
        if self.animating:
            return
        # Block clicks during AI's turn
        if self._is_ai_turn() and self.phase in (Phase.PLACE, Phase.ACTION, Phase.SURGE):
            return

        if self.phase == Phase.TITLE:
            if self.start_btn.collidepoint(pos):
                self.phase = Phase.MODE_SELECT
            return

        if self.phase == Phase.MODE_SELECT:
            for rect, label, diff in self.mode_btns:
                if rect.collidepoint(pos):
                    if diff is None:
                        self.ai_enabled = False
                        self.ai = None
                    else:
                        self.ai_enabled = True
                        self.ai_difficulty = diff
                        self.ai = DriftAI(diff)
                    self.start_draft()
                    return
            return

        if self.phase == Phase.DRAFT:
            self._handle_draft_click(pos, button)
            return

        if self.phase == Phase.GAME_OVER:
            if self.restart_btn.collidepoint(pos):
                self.reset_game()
            return

        # Sidebar power piece buttons (during PLACE)
        if self.phase == Phase.PLACE:
            for rect, pt in self.pp_btns:
                if rect.collidepoint(pos):
                    avail = self.power_pieces[self.current_player].get(pt, 0)
                    if avail > 0:
                        self.selected_pp = pt if self.selected_pp != pt else None
                    return

        # Action buttons
        if self.phase in (Phase.ACTION, Phase.SURGE):
            if self.skip_btn.collidepoint(pos):
                self.do_skip()
                return
            if self.anchor_btn.collidepoint(pos) and self.anchors[self.current_player] > 0:
                self.anchor_mode = not self.anchor_mode
                return

        # Board clicks
        bx, by = pos[0] - BOARD_X0, pos[1] - BOARD_Y0
        if 0 <= bx < BOARD_W and 0 <= by < BOARD_H:
            c = bx // CELL_SIZE
            r = by // CELL_SIZE
            if self.phase == Phase.PLACE:
                self.do_place(r, c)
            elif self.phase in (Phase.ACTION, Phase.SURGE) and self.anchor_mode:
                self.do_anchor(r, c)
            return

        # Arrow clicks
        if self.phase in (Phase.ACTION, Phase.SURGE) and not self.anchor_mode:
            for arrow in self.arrows:
                if arrow.contains(pos):
                    self.do_push(arrow)
                    return

    def _handle_draft_click(self, pos, button):
        total = sum(self.draft_counts.values())
        for i, (pt, *_) in enumerate(POWER_PIECE_INFO):
            if self.card_rects[i].collidepoint(pos):
                if button == 1:  # left click - add
                    if total < 2 and self.draft_counts[pt] < 2:
                        self.draft_counts[pt] += 1
                elif button == 3:  # right click - remove
                    if self.draft_counts[pt] > 0:
                        self.draft_counts[pt] -= 1
                return
        if self.confirm_btn.collidepoint(pos):
            if total == 2:
                self.confirm_draft()

    def handle_mouse_move(self, pos):
        self.hovered_arrow = None
        self.hovered_cell = None
        bx, by = pos[0] - BOARD_X0, pos[1] - BOARD_Y0
        if 0 <= bx < BOARD_W and 0 <= by < BOARD_H:
            self.hovered_cell = (by // CELL_SIZE, bx // CELL_SIZE)
        if self.phase in (Phase.ACTION, Phase.SURGE) and not self.anchor_mode:
            for arrow in self.arrows:
                if arrow.contains(pos):
                    self.hovered_arrow = arrow
                    break

    # ------------------------------------------------------------------
    # AI
    # ------------------------------------------------------------------
    def _update_ai(self):
        """Called every frame. Handles AI moves with threading for heavy compute."""
        if not self._is_ai_turn():
            self.ai_think_start = 0
            return
        if self.animating:
            self.ai_think_start = 0
            return

        # If background compute is running, check if done
        if self.ai_computing:
            if self.ai_thread and not self.ai_thread.is_alive():
                self.ai_computing = False
                self.ai_thread = None
                self._apply_ai_result()
            return

        # Initial thinking delay (brief pause before computing)
        if self.ai_think_start == 0:
            self.ai_think_start = pygame.time.get_ticks()
            return
        delay = {"easy": 400, "medium": 500, "hard": 300}.get(self.ai_difficulty, 400)
        if pygame.time.get_ticks() - self.ai_think_start < delay:
            return
        self.ai_think_start = 0

        # Easy/Medium compute inline, Hard uses background thread
        if self.ai_difficulty in ("easy", "medium"):
            self._ai_make_move()
        else:
            # Impossible: run in background thread
            self.ai_computing = True
            self.ai_compute_start = pygame.time.get_ticks()
            self.ai_result = None
            if self.ai:
                self.ai.progress = "Starting..."
                self.ai.progress_frac = 0.0
            phase = self.phase
            self.ai_thread = threading.Thread(
                target=self._ai_compute_threaded, args=(phase,), daemon=True)
            self.ai_thread.start()

    def _ai_compute_threaded(self, phase):
        """Runs in background thread for Impossible AI."""
        try:
            if phase == Phase.PLACE:
                self.ai_result = ('place', self.ai.choose_placement(self))
            elif phase in (Phase.ACTION, Phase.SURGE):
                self.ai_result = ('action', self.ai.choose_action(self))
        except Exception as e:
            print(f"AI error: {e}")
            self.ai_result = ('action', ('skip',))

    def _apply_ai_result(self):
        """Apply the result from a background AI computation."""
        if not self.ai_result:
            return
        kind, data = self.ai_result
        self.ai_result = None
        if kind == 'place' and data:
            r, c, pt = data
            if pt != PieceType.NORMAL:
                self.selected_pp = pt
            self.do_place(r, c)
        elif kind == 'action':
            if data[0] == 'push':
                self.do_push(data[1])
            elif data[0] == 'anchor':
                self.do_anchor(data[1], data[2])
            else:
                self.do_skip()

    def _ai_make_move(self):
        """Inline AI move for fast difficulties."""
        if self.phase == Phase.PLACE:
            result = self.ai.choose_placement(self)
            if result:
                r, c, pt = result
                if pt != PieceType.NORMAL:
                    self.selected_pp = pt
                self.do_place(r, c)
        elif self.phase in (Phase.ACTION, Phase.SURGE):
            action = self.ai.choose_action(self)
            if action[0] == 'push':
                self.do_push(action[1])
            elif action[0] == 'anchor':
                self.do_anchor(action[1], action[2])
            else:
                self.do_skip()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
                    self.handle_click(event.pos, event.button)
                elif event.type == pygame.MOUSEMOTION:
                    self.handle_mouse_move(event.pos)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        self.reset_game()
                    elif event.key == pygame.K_ESCAPE:
                        running = False
            self._update_ai()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    DriftGame().run()
