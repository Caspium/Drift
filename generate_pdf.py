"""Generate DRIFT v2.0 instruction manual as PDF."""
from fpdf import FPDF
import os

OUT = os.path.join(os.path.dirname(__file__), "DRIFT_Instructions.pdf")
ICON = os.path.join(os.path.dirname(__file__), "assets", "title_art.png")

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
C_ACCENT = (0, 160, 200)       # section titles / accents
C_ACCENT2 = (0, 130, 180)      # sub-headings
C_ORANGE = (255, 140, 0)       # action phase highlights
C_BODY = (30, 30, 30)          # body text
C_BODY2 = (40, 40, 40)         # lighter body text
C_BODY3 = (50, 50, 50)         # even lighter
C_TIP_LABEL = (50, 70, 90)     # strategy tip labels
C_SUBTITLE = (80, 100, 120)    # subtitle text
C_MUTED = (60, 80, 100)        # muted text
C_HEADER = (100, 120, 140)     # page header
C_FOOTER = (120, 120, 120)     # page footer


class DriftPDF(FPDF):
    """Custom PDF class with header/footer for DRIFT v2.0."""

    def header(self):
        if self.page_no() == 1:
            return  # no header on cover
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*C_HEADER)
        self.cell(0, 8, "DRIFT v2.0 - No Move Is Safe. No Piece Is Permanent.",
                  align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*C_ACCENT)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*C_FOOTER)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    # ---- helpers ----------------------------------------------------------
    def section_title(self, text):
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(*C_ACCENT)
        self.cell(0, 12, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def sub_heading(self, text, colour=C_ACCENT2):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*colour)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")

    def body(self, text):
        self.set_font("Helvetica", "", 11)
        self.set_text_color(*C_BODY)
        self.multi_cell(0, 6, text)

    def body_sm(self, text, indent=0):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*C_BODY2)
        if indent:
            self.set_x(self.l_margin + indent)
            self.multi_cell(self.epw - indent, 5.5, text)
        else:
            self.multi_cell(0, 5.5, text)

    def bullet(self, text):
        self.set_font("Helvetica", "", 11)
        self.set_text_color(*C_BODY)
        self.cell(0, 7, f"  - {text}", new_x="LMARGIN", new_y="NEXT")

    def named_block(self, name, desc, name_sz=12, desc_sz=10,
                    name_col=C_BODY3, indent=6):
        self.set_font("Helvetica", "B", name_sz)
        self.set_text_color(*name_col)
        self.cell(0, 7, f"  {name}", new_x="LMARGIN", new_y="NEXT")
        self.body_sm(desc, indent=indent)
        self.ln(3)

    def page_break_if_needed(self, h=50):
        if self.get_y() + h > self.h - self.b_margin:
            self.add_page()


# ===========================================================================
# PDF builder
# ===========================================================================
def build_pdf():
    pdf = DriftPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ================================================================
    # PAGE 1 - Cover
    # ================================================================
    pdf.add_page()
    pdf.ln(18)

    if os.path.exists(ICON):
        pdf.image(ICON, x=25, w=160)
    pdf.ln(10)

    pdf.set_font("Helvetica", "B", 40)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(0, 20, "DRIFT", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 18)
    pdf.set_text_color(*C_SUBTITLE)
    pdf.cell(0, 10, "No Move Is Safe. No Piece Is Permanent.  -  v2.0",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("Helvetica", "I", 12)
    pdf.set_text_color(*C_MUTED)
    pdf.cell(0, 8, "An evolution of Tic-Tac-Toe with Power Pieces, Board Zones & Momentum",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(14)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*C_BODY)
    pdf.multi_cell(0, 6,
        "DRIFT takes the classic game of Tic-Tac-Toe and breathes life into it. "
        "The board is no longer static - pieces slide, age, and eventually vanish. "
        "Version 2.0 introduces Power Pieces you draft before the game, special "
        "Board Zones with permanent effects, and a Momentum system that rewards "
        "aggressive play with bonus actions.\n\n"
        "Players: 2  |  Ages: 10+  |  Play Time: 10-20 minutes",
        align="C")

    # ================================================================
    # PAGE 2 - Overview & Components
    # ================================================================
    pdf.add_page()
    pdf.section_title("Overview")
    pdf.body(
        "DRIFT is a 2-player strategy game played on a 4x4 grid. "
        "Players take turns placing their marks (X or O) and manipulating the board. "
        "The first player to align 4 of their marks in a row - horizontally, vertically, "
        "or diagonally - wins the game.\n\n"
        "What makes DRIFT unique is that the board is alive: pieces can be pushed, "
        "they age with each turn, and they eventually decay and disappear. "
        "Version 2.0 expands on this with three major new systems: Power Pieces, "
        "Board Zones, and the Momentum (Surge) mechanic.")
    pdf.ln(6)

    pdf.section_title("Components")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*C_BODY)
    components = [
        "1 game board (4x4 grid with 4 special Zone cells)",
        "X marks (red) and O marks (green)",
        "2 Anchor tokens per player (gold border indicator)",
        "Age tracking for each piece (6-turn default lifespan)",
        "4 Power Piece types in a shared draft pool (Phantom, Catalyst, Leech, Sentinel)",
        "Surge token tracker (1 per turn max)",
    ]
    for c in components:
        pdf.bullet(c)
    pdf.ln(6)

    pdf.section_title("Goal")
    pdf.body(
        "Be the first player to create a line of 4 of your marks in a row. "
        "Lines can be horizontal, vertical, or diagonal. "
        "A winning line can be formed by placement, by pushing pieces into alignment, "
        "by power-piece effects, or even by your opponent's push accidentally aligning "
        "your pieces!")

    # ================================================================
    # PAGE 3 - Turn Structure
    # ================================================================
    pdf.add_page()
    pdf.section_title("Turn Structure")
    pdf.body("Each turn consists of two main phases, preceded by a draft at the start "
             "of the game:")
    pdf.ln(4)

    # Draft
    pdf.sub_heading("Pre-Game: Power Piece Draft", colour=C_ACCENT2)
    pdf.body_sm(
        "Before the first turn, each player drafts 2 Power Pieces from a shared pool "
        "of 4 types (Phantom, Catalyst, Leech, Sentinel). You may pick 2 of the same "
        "type. These are held in reserve and can be used during any PLACE phase instead "
        "of a normal mark. Right-click a draft card to remove a selection during the "
        "draft.", indent=0)
    pdf.ln(5)

    # Phase 1
    pdf.sub_heading("Phase 1: PLACE")
    pdf.body_sm(
        "Place your mark (X or O) on any empty cell of the 4x4 grid. This is mandatory. "
        "Alternatively, you may spend one of your drafted Power Pieces by clicking the "
        "power-piece button in the sidebar and then clicking a cell. The power piece "
        "replaces your normal mark for that turn.\n\n"
        "If your placement immediately creates a line of 4, you win! The game ends "
        "without proceeding to Phase 2.", indent=0)
    pdf.ln(5)

    # Phase 2
    pdf.sub_heading("Phase 2: ACTION (choose one)", colour=C_ORANGE)
    pdf.body_sm("After placing, you must choose one of three actions:\n", indent=0)

    actions = [
        ("PUSH",
         "Slide any single row or column by one space in either direction. "
         "Click the arrow on the edge of the board. ALL pieces in that line shift together. "
         "Pieces pushed off one edge wrap around to the opposite side. "
         "Anchored pieces resist the push and stay in place while others slide around them."),
        ("ANCHOR",
         "Lock one of your own pieces against all future pushes. "
         "Each player has only 2 Anchor tokens for the entire game. "
         "Anchored pieces are shown with a gold border. "
         "Anchored pieces still age and decay normally."),
        ("SKIP",
         "Do nothing for your action phase. Sometimes strategically useful to avoid "
         "giving your opponent an advantageous board state."),
    ]
    for name, desc in actions:
        pdf.named_block(name, desc)

    # Aging
    pdf.ln(2)
    pdf.sub_heading("End of Turn: Aging & Decay")
    pdf.body_sm(
        "After your action, ALL pieces on the board age by 1 turn. "
        "Any piece that has been on the board for more than 6 turns is removed (decayed). "
        "Piece age is shown visually: bright pieces are new, dim pieces are old. "
        "Small dots below each piece track its exact age. "
        "This decay mechanic prevents stalemates and forces aggressive, dynamic play.",
        indent=0)

    # ================================================================
    # PAGE 4 - Power Pieces
    # ================================================================
    pdf.add_page()
    pdf.section_title("Power Pieces (Draft System)")
    pdf.body(
        "Before the game begins, each player drafts 2 power pieces from a shared pool "
        "of 4 types. You can pick 2 of the same type. During the PLACE phase, you may "
        "choose to place a power piece instead of a normal mark by clicking the "
        "power-piece button in the sidebar, then clicking an empty cell.\n\n"
        "Each power piece has a unique ability that triggers when it is placed or "
        "when certain conditions are met. After its ability resolves, a power piece "
        "generally becomes a normal piece (unless otherwise stated).")
    pdf.ln(6)

    power_pieces = [
        ("1. Phantom",
         "When placed, the Phantom is immune to pushes for 2 turns. It appears with "
         "a ghostly, dashed outline. After 2 turns it materialises into a normal piece "
         "and can be pushed normally.\n\n"
         "Important: the Phantom still counts for winning lines while ghostly, and it "
         "still ages normally. Use it to lock down a critical position that your opponent "
         "cannot push away for 2 turns."),
        ("2. Catalyst",
         "When this piece is moved by a push, it detonates: all 4 orthogonally adjacent "
         "pieces at its NEW position are pushed 1 cell outward (away from the Catalyst). "
         "The Catalyst then becomes a normal piece.\n\n"
         "Immovable / anchored pieces resist the explosion. "
         "Pieces wrap around edges as usual. "
         "The Catalyst does NOT detonate when initially placed - only when pushed."),
        ("3. Leech",
         "When placed, the Leech immediately ages all orthogonally adjacent OPPONENT "
         "pieces by 2 extra turns. This can cause immediate decay if those pieces exceed "
         "their max age (6 for normal, 4 for Sentinel).\n\n"
         "Devastating against aging enemy pieces. A well-placed Leech next to the "
         "Accelerator zone can wipe out nearby opponents instantly."),
        ("4. Sentinel",
         "Automatically anchored when placed - this does NOT cost one of your 2 Anchor "
         "tokens. However, the Sentinel decays in only 4 turns instead of 6. "
         "Think of it as a quick fortress.\n\n"
         "Exception: Sentinels placed on a Rift zone are NOT auto-anchored, because "
         "the Rift prevents any piece from being anchored."),
    ]
    for name, desc in power_pieces:
        pdf.page_break_if_needed(50)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*C_ACCENT2)
        pdf.cell(0, 8, name, new_x="LMARGIN", new_y="NEXT")
        pdf.body_sm(desc, indent=0)
        pdf.ln(4)

    # ================================================================
    # PAGE 5 - Board Zones
    # ================================================================
    pdf.add_page()
    pdf.section_title("Board Zones")
    pdf.body(
        "Four special cells on the 4x4 board have permanent effects that last the "
        "entire game. They are shown as coloured overlays with labels. Zones affect "
        "any piece occupying that cell, regardless of owner.")
    pdf.ln(6)

    zones = [
        ("Rift  -  Row 1, Col 1",
         "Pieces on the Rift cell NEVER decay - they are eternal for as long as they "
         "remain on this cell. However, pieces on the Rift CANNOT be anchored. "
         "This means the Rift is the most valuable cell on the board, but your piece "
         "there can always be pushed away.\n\n"
         "Note: Sentinels placed on the Rift do NOT receive their auto-anchor ability."),
        ("Accelerator  -  Row 2, Col 2",
         "Pieces on the Accelerator age at 2x speed. A normal piece here decays in "
         "only 3 turns instead of 6. A Sentinel here decays in just 2 turns.\n\n"
         "The Accelerator is dangerous for both players. Place here only if you plan "
         "to win quickly, or use it to bait opponents into placing pieces that will "
         "decay rapidly."),
        ("Warp (x2)  -  Row 0, Col 3  &  Row 3, Col 0",
         "The two Warp cells are linked teleporters. When a piece is pushed ONTO a "
         "Warp cell, it immediately teleports to the other Warp cell - but only if the "
         "destination is empty. If the other Warp cell is occupied, no teleport occurs.\n\n"
         "Warp enables powerful cross-board manoeuvres. Push a piece onto one Warp "
         "to surprise-teleport it to the opposite corner for an unexpected 4-in-a-row."),
    ]
    for name, desc in zones:
        pdf.page_break_if_needed(50)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*C_ACCENT2)
        pdf.cell(0, 8, name, new_x="LMARGIN", new_y="NEXT")
        pdf.body_sm(desc, indent=0)
        pdf.ln(4)

    # Zone map diagram
    pdf.page_break_if_needed(65)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*C_ACCENT2)
    pdf.cell(0, 8, "Zone Map (row, col)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    cell_w, cell_h = 38, 14
    x0 = pdf.l_margin + 10
    y0 = pdf.get_y()
    labels = [
        ["", "", "", "WARP"],
        ["", "RIFT", "", ""],
        ["", "", "ACCEL", ""],
        ["WARP", "", "", ""],
    ]
    zone_fills = {
        (0, 3): (180, 120, 255),   # warp purple
        (1, 1): (50, 200, 200),    # rift teal
        (2, 2): (255, 180, 60),    # accel orange
        (3, 0): (180, 120, 255),   # warp purple
    }
    for r in range(4):
        for c in range(4):
            x = x0 + c * cell_w
            y = y0 + r * cell_h
            if (r, c) in zone_fills:
                pdf.set_fill_color(*zone_fills[(r, c)])
                pdf.set_draw_color(80, 80, 80)
                pdf.rect(x, y, cell_w, cell_h, style="DF")
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(255, 255, 255)
            else:
                pdf.set_fill_color(235, 235, 235)
                pdf.set_draw_color(180, 180, 180)
                pdf.rect(x, y, cell_w, cell_h, style="DF")
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(160, 160, 160)
            lbl = labels[r][c] if labels[r][c] else f"({r},{c})"
            pdf.set_xy(x, y)
            pdf.cell(cell_w, cell_h, lbl, align="C")
    pdf.set_y(y0 + 4 * cell_h + 4)

    # ================================================================
    # PAGE 6 - Momentum (Surge)
    # ================================================================
    pdf.add_page()
    pdf.section_title("Momentum: Surge")
    pdf.body(
        "DRIFT v2.0 rewards aggressive play with the Surge mechanic. "
        "If your PUSH action during Phase 2 creates a 3-in-a-row of your own pieces "
        "(any 3 consecutive marks in a horizontal, vertical, or diagonal line), you "
        "earn a SURGE: an immediate bonus action.")
    pdf.ln(4)

    pdf.sub_heading("Surge Rules")
    pdf.ln(2)
    surge_rules = [
        "A Surge is earned only from your PUSH action, not from placement.",
        "The 3-in-a-row must consist of 3 consecutive pieces of your colour in a line.",
        "Your bonus action can be: PUSH, ANCHOR, or SKIP - the same options as Phase 2.",
        "Maximum 1 Surge per turn. A Surge action does NOT trigger another Surge.",
        "Surge is checked immediately after your push resolves (including wrapping, "
        "Catalyst detonations, and Warp teleports).",
    ]
    for rule in surge_rules:
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*C_BODY)
        pdf.cell(0, 7, f"  - {rule}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.sub_heading("Surge Example")
    pdf.body_sm(
        "You have pieces at (0,0), (0,1). You push row 0 to the right, sliding your "
        "third piece from (0,3) (wrapped) to (0,0). Now you have 3 in a row at "
        "(0,0), (0,1), (0,2). A Surge is triggered! You immediately get a bonus action. "
        "You use your bonus push to shift column 3, landing your fourth piece and "
        "completing a 4-in-a-row for the win.", indent=0)
    pdf.ln(8)

    # ================================================================
    # Detailed Rules (continued on same or next page)
    # ================================================================
    pdf.section_title("Detailed Rules")
    pdf.ln(1)
    detail_sections = [
        ("The Push Mechanic",
         "When you push a row or column, every piece in that line slides one cell in "
         "the chosen direction. Pieces that would be pushed off the edge wrap around to "
         "the opposite side. Anchored pieces stay in place; non-anchored pieces slide "
         "among the remaining free positions, skipping over anchored pieces.\n\n"
         "If a piece is pushed onto a Warp cell, it teleports to the linked Warp "
         "(if empty). If a Catalyst is pushed, it detonates at its new position."),
        ("Wrapping",
         "The board wraps in the direction of the push only. Right edge wraps to left; "
         "bottom wraps to top; and vice versa. Wrapping creates unexpected connections "
         "and is a key strategic element."),
        ("Anchors in Detail",
         "Each player begins with 2 Anchor tokens. Once used, they cannot be recovered. "
         "An anchored piece:\n"
         "- Cannot be moved by any push (yours or opponent's)\n"
         "- Still ages and decays after 6 turns (or 4 for Sentinels)\n"
         "- Is visually marked with a gold border\n"
         "- Causes other pieces to slide around it during a push\n"
         "- Cannot be placed on the Rift zone"),
        ("Winning Conditions",
         "The game is won immediately when any player has 4 of their marks in a "
         "straight line (horizontal, vertical, or diagonal). The win check happens:\n"
         "- After Phase 1 (placement / power piece)\n"
         "- After Phase 2 (push / Catalyst / Warp)\n"
         "- After a Surge bonus action\n"
         "- After decay removes a blocking piece"),
        ("Draws",
         "Draws are extremely rare in DRIFT due to the decay mechanic. The board "
         "can never permanently fill up. If both players are unable to create a line "
         "of 4 after an extended period, the game may be declared a draw by mutual "
         "agreement."),
    ]
    for title, detail_body in detail_sections:
        pdf.page_break_if_needed(35)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(0, 100, 140)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.body_sm(detail_body, indent=0)
        pdf.ln(4)

    # ================================================================
    # PAGE 7 - Strategy Guide
    # ================================================================
    pdf.add_page()
    pdf.section_title("Strategy Guide")

    tips = [
        ("Draft Wisely",
         "Your power-piece choices define your strategy. Leech + Catalyst is aggressive, "
         "aiming to disrupt and destroy. Phantom + Sentinel is defensive, locking down "
         "key positions. Two Phantoms can create an impenetrable wall for 2 turns."),
        ("Zone Control",
         "The Rift cell is the most valuable position on the board. An eternal piece "
         "there can anchor a winning strategy - but remember it can't be anchored, so "
         "it can always be pushed away. Fight for the Rift every game."),
        ("Accelerator Trap",
         "Place a Leech adjacent to the Accelerator zone to devastate any enemy piece "
         "placed there. A piece on the Accelerator already ages at 2x; the Leech's +2 "
         "age can cause instant decay."),
        ("Warp Combos",
         "Push a piece onto a Warp cell to teleport it across the board. This is "
         "powerful for surprise 4-in-a-rows. Keep track of which Warp cell is empty "
         "to plan teleportation plays."),
        ("Catalyst Timing",
         "Don't place a Catalyst randomly. Position it so that when an opponent pushes "
         "it (or you push it yourself), its explosion creates maximum disruption - "
         "clearing enemy pieces or pushing yours into alignment."),
        ("Surge Setup",
         "Building toward a 3-in-a-row before pushing is powerful. Push to complete 3, "
         "earn a Surge, then use the bonus action to push toward 4. The two-push combo "
         "is one of the strongest plays in the game."),
        ("Phantom Blocking",
         "Place a Phantom in a critical position. For 2 turns your opponent cannot push "
         "it away. Use this to block an opponent's near-complete line or to hold a "
         "position while you build around it."),
        ("Manage Your Anchors",
         "Your 2 Anchor tokens are the most precious resource. Don't use them too early. "
         "The best anchor protects your winning threat AND blocks your opponent. "
         "Remember that Sentinels grant a free anchor, so drafting one can effectively "
         "give you 3 anchors."),
        ("Exploit Decay",
         "Watch opponent piece ages. A piece about to decay doesn't need to be dealt with. "
         "Conversely, if your key piece is aging, push for the win or replace it. "
         "Place a Leech next to old enemy pieces to accelerate their demise."),
        ("The Skip Trap",
         "Sometimes skipping is the strongest move. If any push you make would benefit "
         "your opponent more than you, skip. Don't push just because you can."),
    ]
    for title, tip_body in tips:
        pdf.page_break_if_needed(30)
        pdf.named_block(title, tip_body, name_col=C_TIP_LABEL)

    # ================================================================
    # PAGE 8 - Controls & Quick Reference
    # ================================================================
    pdf.add_page()
    pdf.section_title("Digital Version Controls")

    controls = [
        ("Left Click (grid cell)", "Place your mark or power piece"),
        ("Left Click (arrow)", "Push that row/column"),
        ("Left Click (power piece btn)", "Select power piece type for placement"),
        ("Right Click (draft card)", "Remove selection during draft"),
        ("Anchor button + click piece", "Anchor your piece (Phase 2)"),
        ("Skip button", "Skip your action (Phase 2)"),
        ("R key", "Restart the game"),
        ("ESC key", "Quit the game"),
    ]
    for action, desc in controls:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(84, 7, action)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, desc, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # Quick Reference Card
    pdf.section_title("Quick Reference Card")
    pdf.set_draw_color(*C_ACCENT)
    pdf.set_fill_color(240, 248, 255)
    x0 = pdf.get_x()
    y0 = pdf.get_y()
    box_h = 120
    pdf.rect(x0, y0, 190, box_h, style="DF")
    pdf.set_xy(x0 + 6, y0 + 4)

    ref_lines = [
        ("Board:", "4x4 grid with 4 special Zone cells"),
        ("Players:", "2 (X = red, O = green)"),
        ("Win:", "4 in a row (horizontal, vertical, diagonal)"),
        ("Turn:", "1) PLACE mark/power piece   2) PUSH / ANCHOR / SKIP"),
        ("Decay:", "Normal pieces removed after 6 turns; Sentinels after 4"),
        ("Wrapping:", "Pushed-off pieces appear on opposite side"),
        ("Anchors:", "2 per player; locks piece against pushes (gold border)"),
        ("Power Pieces:", "2 drafted per player (Phantom / Catalyst / Leech / Sentinel)"),
        ("Zones:", "Rift (eternal) | Accelerator (2x age) | Warp x2 (teleport)"),
        ("Surge:", "3-in-a-row from PUSH = bonus action (max 1/turn)"),
    ]
    for label, value in ref_lines:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(42, 10, label)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 10, value, new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(x0 + 6)

    # Finish
    pdf.output(OUT)
    print(f"PDF saved to {OUT}")


if __name__ == "__main__":
    build_pdf()
