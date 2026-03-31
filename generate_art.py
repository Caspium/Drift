"""
DRIFT Board Game - Artwork Generator
Generates icon.png (256x256) and title_art.png (800x400)
using Pillow with anti-aliased rendering at 2x resolution.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import math
import os

# ── Colour palette ──────────────────────────────────────────────
BG        = (10, 22, 40)        # deep navy  #0a1628
GRID      = (0, 212, 255)       # cyan/teal  #00d4ff
X_COLOR   = (255, 71, 87)       # coral/red  #ff4757
O_COLOR   = (46, 213, 115)      # electric green #2ed573
WHITE     = (255, 255, 255)
SUBTITLE  = (140, 170, 200)     # muted blue-grey for subtitle

OUTPUT_DIR = r"C:\Users\Mark_Golla\Drift\assets"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Helper utilities ────────────────────────────────────────────

def glow_layer(size, draw_fn, color, radius=6, intensity=3):
    """Return an RGBA layer with a soft glow around shapes drawn by *draw_fn*."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    draw_fn(d, color + (255,))
    # blur and brighten to create glow
    glow = layer.filter(ImageFilter.GaussianBlur(radius))
    for _ in range(intensity):
        glow = ImageChops.add(glow, glow)
    glow = Image.blend(Image.new("RGBA", size, (0, 0, 0, 0)), glow, 0.45)
    # composite the crisp shape on top
    glow = Image.alpha_composite(glow, layer)
    return glow


def draw_x(draw, cx, cy, half, width, color):
    """Draw an X centred at (cx, cy)."""
    draw.line([(cx - half, cy - half), (cx + half, cy + half)], fill=color, width=width)
    draw.line([(cx - half, cy + half), (cx + half, cy - half)], fill=color, width=width)


def draw_o(draw, cx, cy, radius, width, color):
    """Draw an O (circle outline) centred at (cx, cy)."""
    bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
    draw.ellipse(bbox, outline=color, width=width)


def draw_motion_trail(img, cx, cy, dx, dy, steps, draw_shape_fn, base_alpha=180):
    """
    Composite progressively fading copies of a shape to simulate motion blur.
    *draw_shape_fn(draw, alpha)* should draw the shape in full position;
    the function shifts each ghost by multiples of (dx, dy).
    """
    for i in range(steps, 0, -1):
        alpha = int(base_alpha * (1 - i / (steps + 1)) * 0.55)
        ghost = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(ghost)
        ox = int(dx * i)
        oy = int(dy * i)
        draw_shape_fn(gd, alpha, ox, oy)
        img = Image.alpha_composite(img, ghost)
    return img


# ═══════════════════════════════════════════════════════════════
#  1.  ICON  (256 x 256)  — rendered at 2x then downscaled
# ═══════════════════════════════════════════════════════════════

def generate_icon():
    S = 512  # work at 2x
    img = Image.new("RGBA", (S, S), BG + (255,))

    # ── background vignette ─────────────────────────────────
    vignette = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    cx, cy = S // 2, S // 2
    for r in range(S, 0, -2):
        a = int(90 * (r / S) ** 2)
        vd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, a))
    img = Image.alpha_composite(img, vignette)

    # ── grid ────────────────────────────────────────────────
    margin = 80
    cell = (S - 2 * margin) / 4
    grid_w = 3

    def _draw_grid(d, color):
        for i in range(1, 4):
            x = int(margin + i * cell)
            d.line([(x, margin), (x, S - margin)], fill=color, width=grid_w)
        for j in range(1, 4):
            y = int(margin + j * cell)
            d.line([(margin, y), (S - margin, y)], fill=color, width=grid_w)

    grid_glow = glow_layer((S, S), _draw_grid, GRID, radius=8, intensity=2)
    img = Image.alpha_composite(img, grid_glow)

    # Cell centres helper
    def cell_center(col, row):
        return (int(margin + col * cell + cell / 2),
                int(margin + row * cell + cell / 2))

    # ── motion trails ───────────────────────────────────────

    # X sliding from (0,0) toward (1,1) — trail goes upper-left
    xc, yc = cell_center(1, 1)
    half_x = int(cell * 0.28)
    xw = 7

    def _trail_x(d, alpha, ox, oy):
        c = X_COLOR + (alpha,)
        draw_x(d, xc + ox, yc + oy, half_x, xw, c)

    img = draw_motion_trail(img, xc, yc, -12, -12, 7, _trail_x, base_alpha=200)
    # crisp X
    xl = glow_layer((S, S),
                    lambda d, c: draw_x(d, xc, yc, half_x, xw, c),
                    X_COLOR, radius=10, intensity=2)
    img = Image.alpha_composite(img, xl)

    # O sliding from (3,3) toward (2,2) — trail goes lower-right
    oc, or_ = cell_center(2, 2)
    o_r = int(cell * 0.26)
    ow = 6

    def _trail_o(d, alpha, ox, oy):
        c = O_COLOR + (alpha,)
        draw_o(d, oc + ox, or_ + oy, o_r, ow, c)

    img = draw_motion_trail(img, oc, or_, 12, 12, 7, _trail_o, base_alpha=200)
    ol = glow_layer((S, S),
                    lambda d, c: draw_o(d, oc, or_, o_r, ow, c),
                    O_COLOR, radius=10, intensity=2)
    img = Image.alpha_composite(img, ol)

    # ── faint static pieces for atmosphere ──────────────────
    ghost_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(ghost_layer)
    # faded X at (3, 0) — "decaying" piece
    fx, fy = cell_center(3, 0)
    draw_x(gd, fx, fy, int(half_x * 0.8), 4, X_COLOR + (55,))
    # faded O at (0, 3) — "decaying" piece
    fo_x, fo_y = cell_center(0, 3)
    draw_o(gd, fo_x, fo_y, int(o_r * 0.8), 4, O_COLOR + (55,))
    img = Image.alpha_composite(img, ghost_layer)

    # ── subtle corner accents (rounded-rect feel) ──────────
    acc = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ad = ImageDraw.Draw(acc)
    corner_len = 30
    cw = 4
    cc = GRID + (100,)
    # top-left
    ad.line([(margin, margin), (margin + corner_len, margin)], fill=cc, width=cw)
    ad.line([(margin, margin), (margin, margin + corner_len)], fill=cc, width=cw)
    # top-right
    tr = S - margin
    ad.line([(tr, margin), (tr - corner_len, margin)], fill=cc, width=cw)
    ad.line([(tr, margin), (tr, margin + corner_len)], fill=cc, width=cw)
    # bottom-left
    bl = S - margin
    ad.line([(margin, bl), (margin + corner_len, bl)], fill=cc, width=cw)
    ad.line([(margin, bl), (margin, bl - corner_len)], fill=cc, width=cw)
    # bottom-right
    ad.line([(tr, bl), (tr - corner_len, bl)], fill=cc, width=cw)
    ad.line([(tr, bl), (tr, bl - corner_len)], fill=cc, width=cw)
    img = Image.alpha_composite(img, acc)

    # ── downscale with LANCZOS for clean AA ────────────────
    img = img.resize((256, 256), Image.LANCZOS)
    img.save(os.path.join(OUTPUT_DIR, "icon.png"))
    print("  -> icon.png saved (256x256)")


# ═══════════════════════════════════════════════════════════════
#  2.  TITLE ART  (800 x 400)  — rendered at 2x then downscaled
# ═══════════════════════════════════════════════════════════════

def generate_title_art():
    W, H = 1600, 800  # 2x
    img = Image.new("RGBA", (W, H), BG + (255,))

    # ── radial gradient background ──────────────────────────
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    cx, cy = W // 2, H // 2
    max_r = int(math.hypot(W, H) / 2)
    for r in range(max_r, 0, -3):
        t = r / max_r
        a = int(50 * (1 - t))
        gd.ellipse([cx - r, cy - r, cx + r, cy + r],
                    fill=(0, 60, 90, a))
    img = Image.alpha_composite(img, grad)

    # ── background 4x4 grid (subtle) ───────────────────────
    gw, gh = 560, 560
    gx0 = (W - gw) // 2
    gy0 = (H - gh) // 2
    cell_w = gw / 4
    cell_h = gh / 4
    grid_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gld = ImageDraw.Draw(grid_layer)
    gc = GRID + (35,)
    lw = 2
    for i in range(5):
        x = int(gx0 + i * cell_w)
        gld.line([(x, gy0), (x, gy0 + gh)], fill=gc, width=lw)
    for j in range(5):
        y = int(gy0 + j * cell_h)
        gld.line([(gx0, y), (gx0 + gw, y)], fill=gc, width=lw)
    # add slight blur for softness
    grid_layer = grid_layer.filter(ImageFilter.GaussianBlur(2))
    img = Image.alpha_composite(img, grid_layer)

    # ── scattered X / O with motion trails ──────────────────

    pieces_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    pieces = [
        # (type, cx, cy, dx, dy, size, alpha)
        ("x", 260,  180, -14, -8,  32, 120),
        ("o", 1350, 200,  10, -6,  28, 110),
        ("x", 1300, 620,  12,  8,  30, 100),
        ("o", 280,  630, -10,  10, 26, 105),
        ("x", 750,  680,  -8,  6,  22, 70),
        ("o", 900,  120,   6, -8,  22, 70),
    ]

    for ptype, pcx, pcy, pdx, pdy, psz, palpha in pieces:
        # trail
        for step in range(8, 0, -1):
            a = int(palpha * (1 - step / 9) * 0.45)
            ox = int(pdx * step)
            oy = int(pdy * step)
            pd = ImageDraw.Draw(pieces_layer)
            if ptype == "x":
                draw_x(pd, pcx + ox, pcy + oy, psz, 5, X_COLOR + (a,))
            else:
                draw_o(pd, pcx + ox, pcy + oy, psz, 4, O_COLOR + (a,))
        # solid piece
        pd = ImageDraw.Draw(pieces_layer)
        if ptype == "x":
            draw_x(pd, pcx, pcy, psz, 6, X_COLOR + (palpha,))
        else:
            draw_o(pd, pcx, pcy, psz, 5, O_COLOR + (palpha,))

    # soft glow on pieces
    pieces_glow = pieces_layer.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, pieces_glow)
    img = Image.alpha_composite(img, pieces_layer)

    # ── "DRIFT" title text ──────────────────────────────────

    # Try bold font first, fall back to regular
    try:
        title_font = ImageFont.truetype("arialbd.ttf", 200)
    except OSError:
        title_font = ImageFont.truetype("arial.ttf", 200)

    try:
        sub_font = ImageFont.truetype("arial.ttf", 36)
    except OSError:
        sub_font = ImageFont.load_default()

    title = "DRIFT"
    # Measure title
    tmp = Image.new("RGBA", (1, 1))
    tmp_d = ImageDraw.Draw(tmp)
    bbox = tmp_d.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (W - tw) // 2 - bbox[0]
    ty = (H - th) // 2 - 60 - bbox[1]

    # Letter-by-letter with drift offset
    offsets = [
        (0, -6),   # D
        (2, 4),    # R
        (-3, -2),  # I
        (4, 6),    # F
        (-2, -4),  # T
    ]

    # Shadow / glow pass
    title_glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    tgd = ImageDraw.Draw(title_glow)

    # Measure each character advance
    char_x = tx
    char_positions = []
    for ch in title:
        cb = tmp_d.textbbox((0, 0), ch, font=title_font)
        cw = cb[2] - cb[0]
        char_positions.append((char_x, cb[0]))
        # advance by full character width + small kerning
        full_w = tmp_d.textlength(ch, font=title_font)
        char_x += int(full_w) + 4

    # Re-centre after measuring
    total_w = char_x - tx - 4
    x_shift = (W - total_w) // 2 - tx + tx  # just centre based on total
    start_x = (W - total_w) // 2

    char_positions2 = []
    cx_run = start_x
    for ch in title:
        cb = tmp_d.textbbox((0, 0), ch, font=title_font)
        char_positions2.append(cx_run - cb[0])
        full_w = tmp_d.textlength(ch, font=title_font)
        cx_run += int(full_w) + 4

    # Draw each letter with its drift offset
    for i, ch in enumerate(title):
        ox, oy = offsets[i]
        lx = char_positions2[i] + ox
        ly = ty + oy

        # glow (drawn slightly larger / blurred later)
        tgd.text((lx, ly), ch, font=title_font, fill=GRID + (120,))

    title_glow = title_glow.filter(ImageFilter.GaussianBlur(16))
    img = Image.alpha_composite(img, title_glow)

    # Crisp letters
    title_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    tld = ImageDraw.Draw(title_layer)
    for i, ch in enumerate(title):
        ox, oy = offsets[i]
        lx = char_positions2[i] + ox
        ly = ty + oy
        # dark outline for depth
        for dx2 in range(-3, 4):
            for dy2 in range(-3, 4):
                if dx2 * dx2 + dy2 * dy2 <= 9:
                    tld.text((lx + dx2, ly + dy2), ch, font=title_font,
                             fill=(5, 12, 25, 220))
        # main letter
        tld.text((lx, ly), ch, font=title_font, fill=WHITE + (240,))
    img = Image.alpha_composite(img, title_layer)

    # Bright edge highlight on letters (thin inner bright pass)
    highlight = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(highlight)
    for i, ch in enumerate(title):
        ox, oy = offsets[i]
        lx = char_positions2[i] + ox
        ly = ty + oy
        hd.text((lx, ly), ch, font=title_font, fill=GRID + (60,))
    highlight = highlight.filter(ImageFilter.GaussianBlur(3))
    img = Image.alpha_composite(img, highlight)

    # ── subtitle ────────────────────────────────────────────
    subtitle = "THE LIVING BOARD GAME"
    sb = tmp_d.textbbox((0, 0), subtitle, font=sub_font)
    sw = sb[2] - sb[0]
    sx = (W - sw) // 2 - sb[0]
    sy = ty + th + 80

    sub_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sub_layer)

    # letter-spacing by drawing character by character
    sub_text = subtitle
    spacing = 10
    # Measure total width with spacing
    total_sub_w = 0
    for ch in sub_text:
        cbox = tmp_d.textbbox((0, 0), ch, font=sub_font)
        total_sub_w += int(tmp_d.textlength(ch, font=sub_font)) + spacing
    total_sub_w -= spacing  # remove last spacing
    sub_start_x = (W - total_sub_w) // 2

    run_x = sub_start_x
    for ch in sub_text:
        sd.text((run_x, sy), ch, font=sub_font, fill=SUBTITLE + (200,))
        run_x += int(tmp_d.textlength(ch, font=sub_font)) + spacing

    # subtle glow on subtitle
    sub_glow = sub_layer.filter(ImageFilter.GaussianBlur(4))
    img = Image.alpha_composite(img, sub_glow)
    img = Image.alpha_composite(img, sub_layer)

    # ── horizontal accent lines ─────────────────────────────
    acc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(acc)
    line_y = sy - 20
    line_half = 260
    center = W // 2
    ad.line([(center - line_half, line_y), (center + line_half, line_y)],
            fill=GRID + (50,), width=2)
    # fade ends with gradient dots
    for i in range(30):
        a = int(50 * (1 - i / 30))
        ad.line([(center - line_half - i * 3, line_y),
                 (center - line_half - i * 3 - 2, line_y)],
                fill=GRID + (a,), width=2)
        ad.line([(center + line_half + i * 3, line_y),
                 (center + line_half + i * 3 + 2, line_y)],
                fill=GRID + (a,), width=2)
    img = Image.alpha_composite(img, acc)

    # ── downscale ───────────────────────────────────────────
    img = img.resize((800, 400), Image.LANCZOS)
    img.save(os.path.join(OUTPUT_DIR, "title_art.png"))
    print("  -> title_art.png saved (800x400)")


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generating DRIFT artwork...")
    generate_icon()
    generate_title_art()
    print("Done!")
