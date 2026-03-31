"""
DRIFT - The Living Board Game
An evolution of tic-tac-toe where the board is alive.
Place. Push. Decay. Anchor.
"""

import pygame
import sys
import math
import os
import copy
from enum import Enum

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CELL_SIZE = 120
GRID_COLS = 4
GRID_ROWS = 4
BOARD_W = CELL_SIZE * GRID_COLS
BOARD_H = CELL_SIZE * GRID_ROWS
SIDEBAR_W = 280
ARROW_MARGIN = 50
TOP_MARGIN = 80
BOTTOM_MARGIN = 40
WIN_W = ARROW_MARGIN + BOARD_W + ARROW_MARGIN + SIDEBAR_W
WIN_H = TOP_MARGIN + BOARD_H + ARROW_MARGIN + BOTTOM_MARGIN
BOARD_X0 = ARROW_MARGIN
BOARD_Y0 = TOP_MARGIN
MAX_AGE = 6
ANCHORS_PER_PLAYER = 2
WIN_LENGTH = 4
FPS = 60
ANIM_DURATION = 0.25  # seconds for push animation

# Colors
BG_COLOR = (10, 22, 40)
GRID_COLOR = (0, 180, 220)
GRID_GLOW = (0, 100, 140, 60)
X_COLOR = (255, 71, 87)
O_COLOR = (46, 213, 115)
X_DIM = (120, 40, 50)
O_DIM = (25, 100, 60)
TEXT_COLOR = (220, 230, 240)
SIDEBAR_BG = (16, 30, 52)
HIGHLIGHT_COLOR = (255, 255, 255, 40)
ANCHOR_COLOR = (255, 215, 0)
ARROW_COLOR = (60, 90, 120)
ARROW_HOVER = (0, 212, 255)
BUTTON_COLOR = (30, 60, 100)
BUTTON_HOVER = (50, 100, 160)
BUTTON_TEXT = (220, 240, 255)
WIN_LINE_COLOR = (255, 255, 255)
PHASE_COLORS = {
    "place": (0, 212, 255),
    "action": (255, 165, 0),
}


# ---------------------------------------------------------------------------
# Enums / Data
# ---------------------------------------------------------------------------
class Mark(Enum):
    EMPTY = 0
    X = 1
    O = 2


class Phase(Enum):
    TITLE = "title"
    PLACE = "place"
    ACTION = "action"  # push or anchor (or skip)
    GAME_OVER = "game_over"


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


# ---------------------------------------------------------------------------
# Cell
# ---------------------------------------------------------------------------
class Cell:
    __slots__ = ("mark", "age", "anchored", "anchor_turns_left")

    def __init__(self):
        self.mark = Mark.EMPTY
        self.age = 0
        self.anchored = False
        self.anchor_turns_left = 0

    def copy(self):
        c = Cell()
        c.mark = self.mark
        c.age = self.age
        c.anchored = self.anchored
        c.anchor_turns_left = self.anchor_turns_left
        return c


# ---------------------------------------------------------------------------
# Board Logic
# ---------------------------------------------------------------------------
class Board:
    def __init__(self):
        self.grid = [[Cell() for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
        self.turn_count = 0

    def place(self, r, c, mark):
        if self.grid[r][c].mark != Mark.EMPTY:
            return False
        self.grid[r][c].mark = mark
        self.grid[r][c].age = 0
        self.grid[r][c].anchored = False
        self.grid[r][c].anchor_turns_left = 0
        return True

    def push(self, axis, index, direction):
        """Push a row or column. axis='row' or 'col'. direction=+1 or -1.
        Returns list of (old_r, old_c, new_r, new_c) for animation.
        Anchored pieces stay in place; non-anchored pieces slide among
        the free slots, wrapping around."""
        moves = []
        if axis == "row":
            row = [self.grid[index][c].copy() for c in range(GRID_COLS)]
            anchored_positions = {c for c in range(GRID_COLS) if row[c].anchored}
            final_row = [None] * GRID_COLS
            for c in anchored_positions:
                final_row[c] = row[c]
                moves.append((index, c, index, c))
            non_anch_cells = [row[c] for c in range(GRID_COLS) if c not in anchored_positions]
            free_slots = [c for c in range(GRID_COLS) if c not in anchored_positions]
            if free_slots:
                shifted_slots = [free_slots[(i + direction) % len(free_slots)] for i in range(len(free_slots))]
                for i, cell in enumerate(non_anch_cells):
                    final_row[shifted_slots[i]] = cell
                    moves.append((index, free_slots[i], index, shifted_slots[i]))
            for c in range(GRID_COLS):
                self.grid[index][c] = final_row[c] if final_row[c] else Cell()

        elif axis == "col":
            col = [self.grid[r][index].copy() for r in range(GRID_ROWS)]
            anchored_positions = {r for r in range(GRID_ROWS) if col[r].anchored}
            final_col = [None] * GRID_ROWS
            moves = []
            for r in anchored_positions:
                final_col[r] = col[r]
                moves.append((r, index, r, index))
            non_anch_cells = [col[r] for r in range(GRID_ROWS) if r not in anchored_positions]
            free_slots = [r for r in range(GRID_ROWS) if r not in anchored_positions]
            if len(free_slots) > 0:
                shifted_slots = [free_slots[(i + direction) % len(free_slots)] for i in range(len(free_slots))]
                for i, cell in enumerate(non_anch_cells):
                    final_col[shifted_slots[i]] = cell
                    moves.append((free_slots[i], index, shifted_slots[i], index))
            for r in range(GRID_ROWS):
                self.grid[r][index] = final_col[r] if final_col[r] else Cell()

        return moves

    def age_pieces(self):
        """Age all pieces by 1. Remove those that exceed MAX_AGE."""
        removed = []
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                cell = self.grid[r][c]
                if cell.mark != Mark.EMPTY:
                    cell.age += 1
                    if cell.anchored:
                        cell.anchor_turns_left -= 1
                        if cell.anchor_turns_left <= 0:
                            cell.anchored = False
                    if cell.age > MAX_AGE:
                        removed.append((r, c, cell.mark))
                        cell.mark = Mark.EMPTY
                        cell.age = 0
                        cell.anchored = False
        return removed

    def check_winner(self):
        """Check for 4-in-a-row. Returns (Mark, [(r,c)...]) or (None, None)."""
        lines = []
        # Rows
        for r in range(GRID_ROWS):
            lines.append([(r, c) for c in range(GRID_COLS)])
        # Cols
        for c in range(GRID_COLS):
            lines.append([(r, c) for r in range(GRID_ROWS)])
        # Diagonals
        lines.append([(i, i) for i in range(4)])
        lines.append([(i, 3 - i) for i in range(4)])

        for line in lines:
            marks = [self.grid[r][c].mark for r, c in line]
            if marks[0] != Mark.EMPTY and all(m == marks[0] for m in marks):
                return marks[0], line
        return None, None

    def is_full(self):
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                if self.grid[r][c].mark == Mark.EMPTY:
                    return False
        return True


# ---------------------------------------------------------------------------
# Arrow Hit Zones (for push controls)
# ---------------------------------------------------------------------------
class Arrow:
    def __init__(self, cx, cy, direction, axis, index, points):
        self.cx = cx
        self.cy = cy
        self.direction = direction
        self.axis = axis
        self.index = index
        self.points = points  # polygon points for drawing
        self.rect = pygame.Rect(0, 0, 0, 0)
        if points:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            pad = 6
            self.rect = pygame.Rect(min(xs) - pad, min(ys) - pad,
                                    max(xs) - min(xs) + 2 * pad,
                                    max(ys) - min(ys) + 2 * pad)

    def contains(self, pos):
        return self.rect.collidepoint(pos)


# ---------------------------------------------------------------------------
# Game Class
# ---------------------------------------------------------------------------
class DriftGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("DRIFT - The Living Board Game")
        # Try to load icon
        icon_path = self._resource_path("assets/icon.png")
        if os.path.exists(icon_path):
            try:
                icon = pygame.image.load(icon_path)
                pygame.display.set_icon(icon)
            except Exception:
                pass

        self.clock = pygame.time.Clock()
        self.font_sm = pygame.font.SysFont("consolas", 16)
        self.font_md = pygame.font.SysFont("consolas", 22, bold=True)
        self.font_lg = pygame.font.SysFont("consolas", 36, bold=True)
        self.font_xl = pygame.font.SysFont("consolas", 52, bold=True)
        self.font_title = pygame.font.SysFont("consolas", 28, bold=True)

        # Load title art
        self.title_art = None
        title_path = self._resource_path("assets/title_art.png")
        if os.path.exists(title_path):
            try:
                self.title_art = pygame.image.load(title_path).convert_alpha()
                # Scale to fit nicely
                art_w = min(WIN_W - 60, self.title_art.get_width())
                scale = art_w / self.title_art.get_width()
                art_h = int(self.title_art.get_height() * scale)
                self.title_art = pygame.transform.smoothscale(self.title_art, (art_w, art_h))
            except Exception:
                pass

        self.reset_game()
        self.phase = Phase.TITLE  # start on title screen
        self.arrows = self._build_arrows()
        self.hovered_arrow = None
        self.hovered_cell = None
        self.anchor_mode = False
        self.hovered_anchor_cell = None

        # Animation state
        self.animating = False
        self.anim_moves = []  # list of (old_r, old_c, new_r, new_c, mark, age, anchored)
        self.anim_start = 0
        self.anim_removed = []  # cells to flash-remove after animation
        self.pending_winner_check = False

        # Win animation
        self.win_line = None
        self.win_time = 0

        # Buttons
        btn_y = WIN_H - BOTTOM_MARGIN - 40
        self.skip_btn = pygame.Rect(WIN_W - SIDEBAR_W + 20, btn_y, 110, 36)
        self.anchor_btn = pygame.Rect(WIN_W - SIDEBAR_W + 145, btn_y, 115, 36)
        self.restart_btn = pygame.Rect(WIN_W // 2 - 80, WIN_H // 2 + 60, 160, 44)
        self.start_btn = pygame.Rect(WIN_W // 2 - 100, WIN_H // 2 + 80, 200, 50)
        self.show_instructions = False
        self.instructions_btn = pygame.Rect(WIN_W - SIDEBAR_W + 20, TOP_MARGIN + 280, 240, 36)

    def _resource_path(self, relative):
        """Get path to resource, works for dev and PyInstaller."""
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)

    def reset_game(self):
        self.board = Board()
        self.current_player = Mark.X
        self.phase = Phase.PLACE
        self.anchors_remaining = {Mark.X: ANCHORS_PER_PLAYER, Mark.O: ANCHORS_PER_PLAYER}
        self.winner = None
        self.win_line = None
        self.turn_number = 1
        self.animating = False
        self.anchor_mode = False
        self.message = ""
        self.message_timer = 0

    def _build_arrows(self):
        arrows = []
        sz = 14
        # Top arrows (push column down)
        for c in range(GRID_COLS):
            cx = BOARD_X0 + c * CELL_SIZE + CELL_SIZE // 2
            cy = BOARD_Y0 - 22
            pts = [(cx, cy + sz), (cx - sz, cy - sz // 2), (cx + sz, cy - sz // 2)]
            arrows.append(Arrow(cx, cy, Direction.DOWN, "col", c, pts))
        # Bottom arrows (push column up)
        for c in range(GRID_COLS):
            cx = BOARD_X0 + c * CELL_SIZE + CELL_SIZE // 2
            cy = BOARD_Y0 + BOARD_H + 22
            pts = [(cx, cy - sz), (cx - sz, cy + sz // 2), (cx + sz, cy + sz // 2)]
            arrows.append(Arrow(cx, cy, Direction.UP, "col", c, pts))
        # Left arrows (push row right)
        for r in range(GRID_ROWS):
            cx = BOARD_X0 - 22
            cy = BOARD_Y0 + r * CELL_SIZE + CELL_SIZE // 2
            pts = [(cx + sz, cy), (cx - sz // 2, cy - sz), (cx - sz // 2, cy + sz)]
            arrows.append(Arrow(cx, cy, Direction.RIGHT, "row", r, pts))
        # Right arrows (push row left)
        for r in range(GRID_ROWS):
            cx = BOARD_X0 + BOARD_W + 22
            cy = BOARD_Y0 + r * CELL_SIZE + CELL_SIZE // 2
            pts = [(cx - sz, cy), (cx + sz // 2, cy - sz), (cx + sz // 2, cy + sz)]
            arrows.append(Arrow(cx, cy, Direction.LEFT, "row", r, pts))
        return arrows

    # ------------------------------------------------------------------
    # Game logic
    # ------------------------------------------------------------------
    def do_place(self, r, c):
        if self.phase != Phase.PLACE or self.animating:
            return
        if self.board.place(r, c, self.current_player):
            # Check for winner immediately after placement
            winner, line = self.board.check_winner()
            if winner:
                self.winner = winner
                self.win_line = line
                self.win_time = pygame.time.get_ticks()
                self.phase = Phase.GAME_OVER
                return
            self.phase = Phase.ACTION
            self.anchor_mode = False

    def do_push(self, arrow):
        if self.phase != Phase.ACTION or self.animating:
            return
        axis = arrow.axis
        index = arrow.index
        d = 1 if arrow.direction in (Direction.DOWN, Direction.RIGHT) else -1
        # Save pre-push state for animation
        pre_grid = [[self.board.grid[r][c].copy() for c in range(GRID_COLS)] for r in range(GRID_ROWS)]
        move_list = self.board.push(axis, index, d)
        # Build animation data
        self.anim_moves = []
        for (or_, oc, nr, nc) in move_list:
            cell = pre_grid[or_][oc]
            if cell.mark != Mark.EMPTY:
                self.anim_moves.append((or_, oc, nr, nc, cell.mark, cell.age, cell.anchored))
        self.animating = True
        self.anim_start = pygame.time.get_ticks()
        self.pending_winner_check = True

    def do_anchor(self, r, c):
        if self.phase != Phase.ACTION or self.animating:
            return
        cell = self.board.grid[r][c]
        if cell.mark != self.current_player:
            return
        if cell.anchored:
            self.set_message("Already anchored!")
            return
        if self.anchors_remaining[self.current_player] <= 0:
            self.set_message("No anchors left!")
            return
        cell.anchored = True
        cell.anchor_turns_left = 99  # permanent until piece decays
        self.anchors_remaining[self.current_player] -= 1
        self.end_turn()

    def do_skip(self):
        if self.phase != Phase.ACTION or self.animating:
            return
        self.end_turn()

    def end_turn(self):
        # Age pieces
        removed = self.board.age_pieces()
        # Check winner after push/aging
        winner, line = self.board.check_winner()
        if winner:
            self.winner = winner
            self.win_line = line
            self.win_time = pygame.time.get_ticks()
            self.phase = Phase.GAME_OVER
            return
        # Switch player
        self.current_player = Mark.O if self.current_player == Mark.X else Mark.X
        self.phase = Phase.PLACE
        self.anchor_mode = False
        self.turn_number += 1

    def set_message(self, msg):
        self.message = msg
        self.message_timer = pygame.time.get_ticks()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self):
        self.screen.fill(BG_COLOR)
        if self.phase == Phase.TITLE:
            self._draw_title_screen()
            pygame.display.flip()
            return
        self._draw_header()
        self._draw_sidebar()
        if self.animating:
            self._draw_board_animating()
        else:
            self._draw_board()
        self._draw_arrows()
        if self.phase == Phase.ACTION and not self.animating:
            self._draw_action_buttons()
        if self.phase == Phase.GAME_OVER:
            self._draw_game_over()
        if self.message and pygame.time.get_ticks() - self.message_timer < 2000:
            self._draw_message()
        pygame.display.flip()

    def _draw_title_screen(self):
        if self.title_art:
            ax = (WIN_W - self.title_art.get_width()) // 2
            ay = WIN_H // 2 - self.title_art.get_height() // 2 - 40
            self.screen.blit(self.title_art, (ax, ay))
        else:
            txt = self.font_xl.render("DRIFT", True, (0, 212, 255))
            self.screen.blit(txt, (WIN_W // 2 - txt.get_width() // 2, WIN_H // 3))
            sub = self.font_md.render("The Living Board Game", True, (100, 140, 170))
            self.screen.blit(sub, (WIN_W // 2 - sub.get_width() // 2, WIN_H // 3 + 60))

        mouse = pygame.mouse.get_pos()
        hover = self.start_btn.collidepoint(mouse)
        c = BUTTON_HOVER if hover else BUTTON_COLOR
        pygame.draw.rect(self.screen, c, self.start_btn, border_radius=10)
        pygame.draw.rect(self.screen, (0, 212, 255), self.start_btn, 2, border_radius=10)
        txt = self.font_md.render("START GAME", True, BUTTON_TEXT)
        self.screen.blit(txt, (self.start_btn.centerx - txt.get_width() // 2,
                                self.start_btn.centery - txt.get_height() // 2))

        hint = self.font_sm.render("Place. Push. Decay. Anchor.", True, (80, 110, 140))
        self.screen.blit(hint, (WIN_W // 2 - hint.get_width() // 2, self.start_btn.bottom + 20))

    def _draw_header(self):
        title = self.font_title.render("DRIFT", True, (0, 212, 255))
        self.screen.blit(title, (BOARD_X0, 14))
        sub = self.font_sm.render("The Living Board Game", True, (100, 140, 170))
        self.screen.blit(sub, (BOARD_X0, 48))

        # Turn indicator
        if self.phase != Phase.GAME_OVER:
            player_name = "X" if self.current_player == Mark.X else "O"
            color = X_COLOR if self.current_player == Mark.X else O_COLOR
            phase_text = "PLACE" if self.phase == Phase.PLACE else "PUSH / ANCHOR / SKIP"
            turn_surf = self.font_md.render(f"Player {player_name}", True, color)
            phase_surf = self.font_sm.render(phase_text, True, PHASE_COLORS.get(self.phase.value, TEXT_COLOR))
            self.screen.blit(turn_surf, (BOARD_X0 + BOARD_W - turn_surf.get_width(), 16))
            self.screen.blit(phase_surf, (BOARD_X0 + BOARD_W - phase_surf.get_width(), 46))

    def _draw_sidebar(self):
        sidebar_rect = pygame.Rect(WIN_W - SIDEBAR_W, 0, SIDEBAR_W, WIN_H)
        pygame.draw.rect(self.screen, SIDEBAR_BG, sidebar_rect)
        x = WIN_W - SIDEBAR_W + 20
        y = TOP_MARGIN

        # Turn number
        t = self.font_sm.render(f"Turn: {self.turn_number}", True, TEXT_COLOR)
        self.screen.blit(t, (x, y))
        y += 30

        # Anchors remaining
        for mark in (Mark.X, Mark.O):
            color = X_COLOR if mark == Mark.X else O_COLOR
            name = "X" if mark == Mark.X else "O"
            remaining = self.anchors_remaining[mark]
            txt = self.font_sm.render(f"{name} Anchors: {'*' * remaining}{'.' * (ANCHORS_PER_PLAYER - remaining)}", True, color)
            self.screen.blit(txt, (x, y))
            y += 24

        y += 16
        # Legend
        legend_items = [
            ("Bright = New piece", TEXT_COLOR),
            ("Dim = Aging (decays at 6)", (100, 120, 140)),
            ("Gold border = Anchored", ANCHOR_COLOR),
        ]
        for text, color in legend_items:
            s = self.font_sm.render(text, True, color)
            self.screen.blit(s, (x, y))
            y += 22

        y += 16
        # Instructions summary
        instructions = [
            "HOW TO PLAY:",
            "",
            "1. PLACE your mark",
            "2. Then: PUSH a row/col",
            "   or ANCHOR a piece",
            "   or SKIP",
            "",
            "Get 4 in a row to win!",
            "",
            "Pieces decay after 6 turns.",
            "Pushed-off pieces wrap.",
            "Anchored pieces resist pushes.",
        ]
        for line in instructions:
            color = (0, 212, 255) if line == "HOW TO PLAY:" else (160, 180, 200)
            s = self.font_sm.render(line, True, color)
            self.screen.blit(s, (x, y))
            y += 20

    def _draw_board(self):
        # Draw grid background
        board_rect = pygame.Rect(BOARD_X0, BOARD_Y0, BOARD_W, BOARD_H)
        pygame.draw.rect(self.screen, (14, 28, 48), board_rect)

        # Draw cells
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                x = BOARD_X0 + c * CELL_SIZE
                y = BOARD_Y0 + r * CELL_SIZE
                cell_rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)

                # Hover highlight
                if self.hovered_cell == (r, c) and not self.animating:
                    if self.phase == Phase.PLACE and self.board.grid[r][c].mark == Mark.EMPTY:
                        s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                        s.fill((255, 255, 255, 20))
                        self.screen.blit(s, (x, y))
                    elif self.anchor_mode and self.phase == Phase.ACTION:
                        cell = self.board.grid[r][c]
                        if cell.mark == self.current_player and not cell.anchored:
                            s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                            s.fill((255, 215, 0, 30))
                            self.screen.blit(s, (x, y))

                cell = self.board.grid[r][c]
                if cell.mark != Mark.EMPTY:
                    self._draw_mark(x, y, cell)

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

    def _draw_board_animating(self):
        board_rect = pygame.Rect(BOARD_X0, BOARD_Y0, BOARD_W, BOARD_H)
        pygame.draw.rect(self.screen, (14, 28, 48), board_rect)

        t = (pygame.time.get_ticks() - self.anim_start) / (ANIM_DURATION * 1000)
        t = min(t, 1.0)
        # Ease out
        t = 1 - (1 - t) ** 3

        # Draw animated pieces
        for (or_, oc, nr, nc, mark, age, anchored) in self.anim_moves:
            # Interpolate position, handling wrap-around
            ox = BOARD_X0 + oc * CELL_SIZE
            oy = BOARD_Y0 + or_ * CELL_SIZE
            nx = BOARD_X0 + nc * CELL_SIZE
            ny = BOARD_Y0 + nr * CELL_SIZE

            # Handle wrapping: if distance is more than 2 cells, piece wraps
            dx = nx - ox
            dy = ny - oy
            if abs(dx) > CELL_SIZE * 2:
                if dx > 0:
                    dx -= BOARD_W
                else:
                    dx += BOARD_W
            if abs(dy) > CELL_SIZE * 2:
                if dy > 0:
                    dy -= BOARD_H
                else:
                    dy += BOARD_H

            cx = ox + dx * t
            cy = oy + dy * t

            # Create temporary cell for drawing
            temp_cell = Cell()
            temp_cell.mark = mark
            temp_cell.age = age
            temp_cell.anchored = anchored
            self._draw_mark(cx, cy, temp_cell)

        # Draw non-moving pieces (those not in the animated axis)
        # Actually all moving pieces are captured in anim_moves.
        # Draw pieces NOT in the animated set
        animated_destinations = set()
        for (_, _, nr, nc, _, _, _) in self.anim_moves:
            animated_destinations.add((nr, nc))

        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                if (r, c) not in animated_destinations:
                    cell = self.board.grid[r][c]
                    if cell.mark != Mark.EMPTY:
                        x = BOARD_X0 + c * CELL_SIZE
                        y = BOARD_Y0 + r * CELL_SIZE
                        self._draw_mark(x, y, cell)

        # Grid lines
        for i in range(GRID_COLS + 1):
            lx = BOARD_X0 + i * CELL_SIZE
            pygame.draw.line(self.screen, GRID_COLOR, (lx, BOARD_Y0), (lx, BOARD_Y0 + BOARD_H), 2)
        for i in range(GRID_ROWS + 1):
            ly = BOARD_Y0 + i * CELL_SIZE
            pygame.draw.line(self.screen, GRID_COLOR, (BOARD_X0, ly), (BOARD_X0 + BOARD_W, ly), 2)

        # Check if animation done
        if t >= 1.0:
            self.animating = False
            if self.pending_winner_check:
                self.pending_winner_check = False
                self.end_turn()

    def _draw_mark(self, x, y, cell):
        cx = x + CELL_SIZE // 2
        cy = y + CELL_SIZE // 2
        # Fade based on age
        fade = max(0.2, 1.0 - (cell.age / (MAX_AGE + 1)) * 0.8)
        sz = int(CELL_SIZE * 0.32)

        if cell.mark == Mark.X:
            color = tuple(int(c * fade) for c in X_COLOR)
            lw = max(3, int(5 * fade))
            pygame.draw.line(self.screen, color, (cx - sz, cy - sz), (cx + sz, cy + sz), lw)
            pygame.draw.line(self.screen, color, (cx + sz, cy - sz), (cx - sz, cy + sz), lw)
        elif cell.mark == Mark.O:
            color = tuple(int(c * fade) for c in O_COLOR)
            lw = max(3, int(5 * fade))
            pygame.draw.circle(self.screen, color, (cx, cy), sz, lw)

        # Anchor indicator
        if cell.anchored:
            pygame.draw.rect(self.screen, ANCHOR_COLOR,
                             (x + 4, y + 4, CELL_SIZE - 8, CELL_SIZE - 8), 2)
            # Small anchor icon (diamond) in corner
            ax, ay = x + 16, y + 16
            diamond_sz = 6
            pts = [(ax, ay - diamond_sz), (ax + diamond_sz, ay),
                   (ax, ay + diamond_sz), (ax - diamond_sz, ay)]
            pygame.draw.polygon(self.screen, ANCHOR_COLOR, pts)

        # Age indicator (small dots at bottom)
        if cell.mark != Mark.EMPTY:
            for i in range(MAX_AGE):
                dot_x = cx - (MAX_AGE * 4) // 2 + i * 8 + 4
                dot_y = y + CELL_SIZE - 12
                if i < cell.age:
                    pygame.draw.circle(self.screen, (80, 50, 50) if cell.mark == Mark.X else (30, 70, 50),
                                       (dot_x, dot_y), 2)
                else:
                    pygame.draw.circle(self.screen, (40, 50, 60), (dot_x, dot_y), 2)

    def _draw_arrows(self):
        if self.phase != Phase.ACTION or self.animating or self.anchor_mode:
            # Draw dimmed arrows
            for arrow in self.arrows:
                pygame.draw.polygon(self.screen, (30, 45, 60), arrow.points)
            return
        for arrow in self.arrows:
            color = ARROW_HOVER if arrow == self.hovered_arrow else ARROW_COLOR
            pygame.draw.polygon(self.screen, color, arrow.points)

    def _draw_action_buttons(self):
        mouse = pygame.mouse.get_pos()

        # Skip button
        hover = self.skip_btn.collidepoint(mouse)
        color = BUTTON_HOVER if hover else BUTTON_COLOR
        pygame.draw.rect(self.screen, color, self.skip_btn, border_radius=6)
        pygame.draw.rect(self.screen, GRID_COLOR, self.skip_btn, 1, border_radius=6)
        txt = self.font_sm.render("Skip", True, BUTTON_TEXT)
        self.screen.blit(txt, (self.skip_btn.centerx - txt.get_width() // 2,
                                self.skip_btn.centery - txt.get_height() // 2))

        # Anchor button
        can_anchor = self.anchors_remaining[self.current_player] > 0
        if can_anchor:
            hover = self.anchor_btn.collidepoint(mouse)
            color = (80, 70, 20) if self.anchor_mode else (BUTTON_HOVER if hover else BUTTON_COLOR)
            pygame.draw.rect(self.screen, color, self.anchor_btn, border_radius=6)
            border_c = ANCHOR_COLOR if self.anchor_mode else GRID_COLOR
            pygame.draw.rect(self.screen, border_c, self.anchor_btn, 1, border_radius=6)
            label = "Anchoring..." if self.anchor_mode else "Anchor"
            txt = self.font_sm.render(label, True, ANCHOR_COLOR if self.anchor_mode else BUTTON_TEXT)
        else:
            pygame.draw.rect(self.screen, (30, 30, 40), self.anchor_btn, border_radius=6)
            txt = self.font_sm.render("No Anchors", True, (80, 80, 90))
        self.screen.blit(txt, (self.anchor_btn.centerx - txt.get_width() // 2,
                                self.anchor_btn.centery - txt.get_height() // 2))

    def _draw_win_line(self):
        if not self.win_line:
            return
        elapsed = (pygame.time.get_ticks() - self.win_time) / 1000.0
        alpha = int(abs(math.sin(elapsed * 3)) * 200 + 55)
        r0, c0 = self.win_line[0]
        r1, c1 = self.win_line[-1]
        x0 = BOARD_X0 + c0 * CELL_SIZE + CELL_SIZE // 2
        y0 = BOARD_Y0 + r0 * CELL_SIZE + CELL_SIZE // 2
        x1 = BOARD_X0 + c1 * CELL_SIZE + CELL_SIZE // 2
        y1 = BOARD_Y0 + r1 * CELL_SIZE + CELL_SIZE // 2
        # Draw glowing line
        for w in (8, 5, 2):
            c = (255, 255, 255) if w == 2 else ((200, 220, 255) if w == 5 else (100, 150, 200))
            pygame.draw.line(self.screen, c, (x0, y0), (x1, y1), w)

    def _draw_game_over(self):
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))

        if self.winner:
            name = "X" if self.winner == Mark.X else "O"
            color = X_COLOR if self.winner == Mark.X else O_COLOR
            txt = self.font_xl.render(f"Player {name} Wins!", True, color)
        else:
            txt = self.font_xl.render("Draw!", True, TEXT_COLOR)
        self.screen.blit(txt, (WIN_W // 2 - txt.get_width() // 2, WIN_H // 2 - 50))

        mouse = pygame.mouse.get_pos()
        hover = self.restart_btn.collidepoint(mouse)
        c = BUTTON_HOVER if hover else BUTTON_COLOR
        pygame.draw.rect(self.screen, c, self.restart_btn, border_radius=8)
        pygame.draw.rect(self.screen, GRID_COLOR, self.restart_btn, 2, border_radius=8)
        txt = self.font_md.render("Play Again", True, BUTTON_TEXT)
        self.screen.blit(txt, (self.restart_btn.centerx - txt.get_width() // 2,
                                self.restart_btn.centery - txt.get_height() // 2))

        hint = self.font_sm.render("Press R to restart", True, (80, 110, 140))
        self.screen.blit(hint, (WIN_W // 2 - hint.get_width() // 2, self.restart_btn.bottom + 12))

    def _draw_message(self):
        elapsed = pygame.time.get_ticks() - self.message_timer
        if elapsed > 2000:
            return
        alpha = 255 if elapsed < 1500 else int(255 * (2000 - elapsed) / 500)
        txt = self.font_sm.render(self.message, True, (255, 200, 100))
        self.screen.blit(txt, (BOARD_X0, BOARD_Y0 + BOARD_H + ARROW_MARGIN + 4))

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def handle_click(self, pos):
        if self.animating:
            return

        # Title screen
        if self.phase == Phase.TITLE:
            if self.start_btn.collidepoint(pos):
                self.reset_game()
            return

        # Game over - restart button
        if self.phase == Phase.GAME_OVER:
            if self.restart_btn.collidepoint(pos):
                self.reset_game()
            return

        # Action phase buttons
        if self.phase == Phase.ACTION:
            if self.skip_btn.collidepoint(pos):
                self.do_skip()
                return
            if self.anchor_btn.collidepoint(pos) and self.anchors_remaining[self.current_player] > 0:
                self.anchor_mode = not self.anchor_mode
                return

        # Board clicks
        bx = pos[0] - BOARD_X0
        by = pos[1] - BOARD_Y0
        if 0 <= bx < BOARD_W and 0 <= by < BOARD_H:
            c = bx // CELL_SIZE
            r = by // CELL_SIZE
            if self.phase == Phase.PLACE:
                self.do_place(r, c)
            elif self.phase == Phase.ACTION and self.anchor_mode:
                self.do_anchor(r, c)
            return

        # Arrow clicks (push)
        if self.phase == Phase.ACTION and not self.anchor_mode:
            for arrow in self.arrows:
                if arrow.contains(pos):
                    self.do_push(arrow)
                    return

    def handle_mouse_move(self, pos):
        self.hovered_arrow = None
        self.hovered_cell = None

        # Check board hover
        bx = pos[0] - BOARD_X0
        by = pos[1] - BOARD_Y0
        if 0 <= bx < BOARD_W and 0 <= by < BOARD_H:
            c = bx // CELL_SIZE
            r = by // CELL_SIZE
            self.hovered_cell = (r, c)

        # Check arrow hover
        if self.phase == Phase.ACTION and not self.anchor_mode:
            for arrow in self.arrows:
                if arrow.contains(pos):
                    self.hovered_arrow = arrow
                    break

    # ------------------------------------------------------------------
    # Main Loop
    # ------------------------------------------------------------------
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)
                elif event.type == pygame.MOUSEMOTION:
                    self.handle_mouse_move(event.pos)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        self.reset_game()
                    elif event.key == pygame.K_ESCAPE:
                        running = False

            self.draw()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    game = DriftGame()
    game.run()
