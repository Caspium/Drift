"""Generate DRIFT instruction manual as PDF."""
from fpdf import FPDF
import os

OUT = os.path.join(os.path.dirname(__file__), "DRIFT_Instructions.pdf")
ICON = os.path.join(os.path.dirname(__file__), "assets", "title_art.png")


class DriftPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 120, 140)
        self.cell(0, 8, "DRIFT - The Living Board Game", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(0, 180, 220)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def build_pdf():
    pdf = DriftPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ---- PAGE 1: Cover ----
    pdf.add_page()
    pdf.ln(20)

    # Title art
    if os.path.exists(ICON):
        pdf.image(ICON, x=25, w=160)
    pdf.ln(10)

    pdf.set_font("Helvetica", "B", 36)
    pdf.set_text_color(0, 160, 200)
    pdf.cell(0, 18, "DRIFT", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(80, 100, 120)
    pdf.cell(0, 10, "The Living Board Game", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("Helvetica", "I", 12)
    pdf.set_text_color(60, 80, 100)
    pdf.cell(0, 8, "An evolution of Tic-Tac-Toe", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(16)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 6,
        "DRIFT takes the classic game of Tic-Tac-Toe and breathes life into it. "
        "The board is no longer static - pieces slide, age, and eventually vanish. "
        "Every move creates ripples across the entire board. No two games are ever the same.\n\n"
        "Players: 2  |  Ages: 8+  |  Play Time: 5-15 minutes",
        align="C")

    # ---- PAGE 2: Overview & Setup ----
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 160, 200)
    pdf.cell(0, 12, "Overview", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 6,
        "DRIFT is a 2-player strategy game played on a 4x4 grid. "
        "Players take turns placing their marks (X or O) and manipulating the board. "
        "The first player to align 4 of their marks in a row - horizontally, vertically, "
        "or diagonally - wins the game.\n\n"
        "What makes DRIFT unique is that the board is alive: pieces can be pushed, "
        "they age with each turn, and they eventually decay and disappear. "
        "Players also have a limited supply of Anchor tokens to lock key pieces in place.")
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 160, 200)
    pdf.cell(0, 12, "Components", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 30, 30)
    components = [
        "- 1 game board (4x4 grid)",
        "- X marks (red) and O marks (green)",
        "- 2 Anchor tokens per player (gold)",
        "- Age tracking for each piece (6-turn lifespan)",
    ]
    for line in components:
        pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 160, 200)
    pdf.cell(0, 12, "Goal", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 6,
        "Be the first player to create a line of 4 of your marks in a row. "
        "Lines can be horizontal, vertical, or diagonal. "
        "A winning line can be formed by placement, by pushing pieces into alignment, "
        "or even by your opponent's push accidentally aligning your pieces!")

    # ---- PAGE 3: Turn Structure ----
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 160, 200)
    pdf.cell(0, 12, "Turn Structure", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 6,
        "Each turn consists of two phases:")
    pdf.ln(4)

    # Phase 1
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 130, 180)
    pdf.cell(0, 8, "Phase 1: PLACE", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 6,
        "Place your mark (X or O) on any empty cell of the 4x4 grid. "
        "This is mandatory - you must place a mark every turn.\n\n"
        "If your placement immediately creates a line of 4, you win! "
        "The game ends without proceeding to Phase 2.")
    pdf.ln(4)

    # Phase 2
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(255, 140, 0)
    pdf.cell(0, 8, "Phase 2: ACTION (choose one)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 6, "After placing, you must choose one of three actions:\n")

    actions = [
        ("PUSH", 
         "Slide any single row or column by one space in either direction. "
         "Click the arrow on the edge of the board pointing in the direction you want to push. "
         "ALL pieces in that row or column shift together. "
         "Pieces pushed off one edge wrap around to the opposite side. "
         "Anchored pieces resist the push and stay in place while others slide around them."),
        ("ANCHOR",
         "Instead of pushing, you may anchor one of your own pieces. "
         "An anchored piece cannot be moved by any push action (yours or your opponent's). "
         "Each player has only 2 Anchor tokens for the entire game, so use them wisely! "
         "Anchored pieces are shown with a gold border. "
         "Note: anchored pieces still age and decay normally."),
        ("SKIP",
         "You may choose to skip your action phase entirely, doing nothing. "
         "This is sometimes strategically useful to avoid giving your opponent an advantageous board state."),
    ]
    for name, desc in actions:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(0, 7, f"  {name}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.set_x(pdf.l_margin + 6)
        pdf.multi_cell(pdf.epw - 6, 5.5, desc)
        pdf.ln(3)

    # After action
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 130, 180)
    pdf.cell(0, 8, "End of Turn: Aging & Decay", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 6,
        "After your action, ALL pieces on the board age by 1 turn. "
        "Any piece that has been on the board for more than 6 turns is removed (decayed). "
        "This happens automatically.\n\n"
        "Piece age is shown visually: bright pieces are new, dim pieces are old. "
        "Small dots below each piece track its exact age. "
        "This decay mechanic prevents stalemates and forces aggressive, dynamic play.")

    # ---- PAGE 4: Detailed Rules ----
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 160, 200)
    pdf.cell(0, 12, "Detailed Rules", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    sections = [
        ("The Push Mechanic",
         "When you push a row or column, every piece in that line slides one cell in "
         "the chosen direction. Pieces that would be pushed off the edge of the board "
         "wrap around to the opposite side.\n\n"
         "Example: If a row contains [X, _, O, X] and you push right, "
         "it becomes [X, X, _, O] - the rightmost X wraps to the far left, "
         "but wait - the X that was pushed off actually wraps.\n\n"
         "Anchored pieces stay in place. Non-anchored pieces slide among the "
         "remaining free positions, skipping over anchored pieces."),
        ("Wrapping",
         "The board wraps in the direction of the push only. When a piece is pushed "
         "off the right edge, it reappears on the left. When pushed off the bottom, "
         "it reappears at the top. This wrapping creates unexpected connections "
         "and is a key strategic element."),
        ("Anchors in Detail",
         "Each player begins with 2 Anchor tokens. Once used, they cannot be recovered. "
         "An anchored piece:\n"
         "- Cannot be moved by any push (yours or opponent's)\n"
         "- Still ages and decays after 6 turns like any other piece\n"
         "- Is visually marked with a gold border and diamond icon\n"
         "- Causes other pieces to slide around it during a push\n\n"
         "Strategic tip: Anchor a piece that is part of a near-complete line, "
         "or anchor a piece in a position that blocks your opponent's plans."),
        ("Winning",
         "The game is won immediately when any player has 4 of their marks in a "
         "straight line (horizontal, vertical, or diagonal). This can happen:\n"
         "- During Phase 1 (placement)\n"
         "- As a result of Phase 2 (push shifting pieces into alignment)\n"
         "- Technically even from decay removing a blocking piece\n\n"
         "The win check happens after placement and again after the action phase."),
        ("Draws",
         "Draws are extremely rare in DRIFT due to the decay mechanic. The board "
         "can never permanently fill up. However, if both players are unable to "
         "create a line of 4 after an extended period, the game may be declared a draw "
         "by mutual agreement."),
    ]
    for title, body in sections:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(0, 100, 140)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(0, 5.5, body)
        pdf.ln(4)

    # ---- PAGE 5: Strategy Guide ----
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 160, 200)
    pdf.cell(0, 12, "Strategy Guide", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    tips = [
        ("Think Ahead",
         "Every piece you place will move. Before placing, consider: "
         "where will this piece be after my opponent pushes? "
         "Plan not just for the current board state but for where pieces will drift."),
        ("Use Push Offensively AND Defensively",
         "Push isn't just for aligning your pieces - it's also for disrupting your opponent's. "
         "A well-timed push can simultaneously advance your position and break their line. "
         "Always check both effects before pushing."),
        ("Manage Your Anchors",
         "Your 2 anchors are the most precious resource in the game. "
         "Don't use them too early - save them for critical moments. "
         "The best anchor is one that both protects your winning threat "
         "and blocks your opponent."),
        ("Exploit Decay",
         "Watch your opponent's piece ages. A piece about to decay is a piece "
         "that doesn't need to be dealt with. Sometimes the best strategy is patience. "
         "Conversely, if your key piece is aging, you need to win soon or replace it."),
        ("Wrapping Tricks",
         "The wrap-around mechanic can create surprise connections. "
         "A piece on the far left and far right of the same row are only "
         "one push away from being adjacent. Think about the board as a cylinder."),
        ("Control the Center",
         "Central pieces are involved in more potential winning lines. "
         "They're also harder for your opponent to push into unfavorable positions "
         "because pushes affect the entire row/column."),
        ("The Skip Trap",
         "Sometimes skipping is the strongest move. If any push you make would "
         "benefit your opponent more than you, skip. Don't push just because you can."),
    ]
    for title, body in tips:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(50, 70, 90)
        pdf.cell(0, 7, f"  {title}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.set_x(pdf.l_margin + 6)
        pdf.multi_cell(pdf.epw - 6, 5.5, body)
        pdf.ln(3)

    # ---- PAGE 6: Controls & Quick Reference ----
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 160, 200)
    pdf.cell(0, 12, "Digital Version Controls", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 30, 30)
    controls = [
        ("Left Click on grid cell", "Place your mark (Phase 1)"),
        ("Left Click on arrow", "Push that row/column (Phase 2)"),
        ("Anchor button + click piece", "Anchor your piece (Phase 2)"),
        ("Skip button", "Skip your action (Phase 2)"),
        ("R key", "Restart the game"),
        ("ESC key", "Quit the game"),
    ]
    for action, desc in controls:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(80, 7, action)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, desc, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Quick Reference Card
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 160, 200)
    pdf.cell(0, 12, "Quick Reference", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_draw_color(0, 160, 200)
    pdf.set_fill_color(240, 248, 255)
    x0 = pdf.get_x()
    y0 = pdf.get_y()
    pdf.rect(x0, y0, 190, 90, style="DF")
    pdf.set_xy(x0 + 6, y0 + 4)

    ref_lines = [
        ("Board:", "4 x 4 grid"),
        ("Win:", "4 in a row (horizontal, vertical, diagonal)"),
        ("Turn:", "1) PLACE  then  2) PUSH / ANCHOR / SKIP"),
        ("Decay:", "Pieces removed after 6 turns"),
        ("Wrapping:", "Pushed-off pieces appear on opposite side"),
        ("Anchors:", "2 per player; locks piece against pushes"),
        ("Players:", "2 (X = red, O = green)"),
    ]
    for label, value in ref_lines:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(36, 10, label)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 10, value, new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(x0 + 6)

    pdf.output(OUT)
    print(f"PDF saved to {OUT}")


if __name__ == "__main__":
    build_pdf()
