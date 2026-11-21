#!/usr/bin/env python3
"""The Catalogue Photo of an Impossible Gadget.

Renders, with the Python standard library only, a studio catalogue photograph
of a chrome two-slot toaster toasting a smartphone, with a single butter knife
as the one accessory. Writes /output/entry.png (1024x1024, deterministic).
"""
import math
import os
import struct
import zlib

W = H = 1024


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rows = [bytearray(w * 3) for _ in range(h)]

    def set(self, x, y, r, g, b):
        if 0 <= x < self.w and 0 <= y < self.h:
            row = self.rows[y]
            i = x * 3
            row[i] = r
            row[i + 1] = g
            row[i + 2] = b

    def blend(self, x, y, r, g, b, a):
        """Blend colour over pixel (x, y); a in 0..255."""
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        row = self.rows[y]
        i = x * 3
        if a >= 255:
            row[i] = r
            row[i + 1] = g
            row[i + 2] = b
            return
        inv = 255 - a
        row[i] = (r * a + row[i] * inv) // 255
        row[i + 1] = (g * a + row[i + 1] * inv) // 255
        row[i + 2] = (b * a + row[i + 2] * inv) // 255

    def fill_row(self, y, x0, x1, r, g, b):
        if y < 0 or y >= self.h:
            return
        x0 = max(0, x0)
        x1 = min(self.w, x1)
        if x1 <= x0:
            return
        row = self.rows[y]
        row[x0 * 3:x1 * 3] = bytes((r, g, b)) * (x1 - x0)

    def fill_row_dithered(self, y, x0, x1, r, g, b):
        """Fill a row span with 4x4 Bayer dither varying per pixel (no banding)."""
        if y < 0 or y >= self.h:
            return
        x0 = max(0, x0)
        x1 = min(self.w, x1)
        if x1 <= x0:
            return
        row = self.rows[y]
        brow = BAYER[y & 3]
        for p in range(4):
            xs = x0 + ((p - x0) & 3)
            if xs >= x1:
                continue
            cnt = (x1 - 1 - xs) // 4 + 1
            off = (brow[p] - 8) * 0.9
            rr, gg, bb = clamp(r + off), clamp(g + off), clamp(b + off)
            for ch, val in ((0, rr), (1, gg), (2, bb)):
                row[xs * 3 + ch:xs * 3 + ch + cnt * 12:12] = bytes([val]) * cnt

    def blend_row(self, y, x0, x1, r, g, b, a):
        if y < 0 or y >= self.h or a <= 0:
            return
        x0 = max(0, x0)
        x1 = min(self.w, x1)
        for x in range(x0, x1):
            self.blend(x, y, r, g, b, a)


def clamp(v, lo=0, hi=255):
    return lo if v < lo else hi if v > hi else int(v)


def lerp(a, b, t):
    return a + (b - a) * t


def grad(stops, t):
    """stops: list of (pos, (r,g,b)); t in 0..1 -> (r,g,b)."""
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        p0, c0 = stops[i - 1]
        p1, c1 = stops[i]
        if t <= p1:
            f = (t - p0) / (p1 - p0) if p1 > p0 else 0.0
            return (lerp(c0[0], c1[0], f), lerp(c0[1], c1[1], f),
                    lerp(c0[2], c1[2], f))
    return stops[-1][1]


# BAYER 4x4 dither (deterministic, kills banding on smooth gradients)
BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def dither(x, y):
    return (BAYER[y & 3][x & 3] - 8) * 0.9


# ---------------------------------------------------------------- shapes
def rounded_span(x0, x1, y, cy0, cy1, r):
    """Horizontal span of a rounded rect on scanline y, or None."""
    if y < cy0 or y >= cy1:
        return None
    lo, hi = x0, x1
    if y < cy0 + r:
        dy = cy0 + r - y
        dx = int(math.sqrt(max(0, r * r - dy * dy)))
        lo = max(lo, x0 + r - dx)
        hi = min(hi, x1 - r + dx)
    elif y >= cy1 - r:
        dy = y - (cy1 - r) + 1
        dx = int(math.sqrt(max(0, r * r - dy * dy)))
        lo = max(lo, x0 + r - dx)
        hi = min(hi, x1 - r + dx)
    return (lo, hi) if hi > lo else None


def vgrad_rrect(cv, x0, y0, x1, y1, r, stops, sheen=None):
    """Rounded rect filled with a vertical gradient. sheen: optional
    callable (x, y) -> extra brightness 0..1 added as white."""
    for y in range(y0, y1):
        sp = rounded_span(x0, x1, y, y0, y1, r)
        if not sp:
            continue
        t = (y - y0) / max(1, y1 - y0)
        cr, cg, cb = grad(stops, t)
        cv.fill_row_dithered(y, sp[0], sp[1], cr, cg, cb)
        if sheen is not None:
            for x in range(sp[0], sp[1]):
                s = sheen(x, y)
                if s > 0.02:
                    cv.blend(x, y, 255, 255, 255, int(255 * min(0.55, s)))


def ellipse(cv, cx, cy, rx, ry, color, peak_alpha, soft=1.0):
    """Soft filled ellipse; alpha falls off smoothly to zero at the edge."""
    r, g, b = color
    x0, x1 = int(cx - rx * soft), int(cx + rx * soft)
    y0, y1 = int(cy - ry * soft), int(cy + ry * soft)
    for y in range(max(0, y0), min(cv.h, y1)):
        ny = (y - cy) / (ry * soft)
        for x in range(max(0, x0), min(cv.w, x1)):
            nx = (x - cx) / (rx * soft)
            d2 = nx * nx + ny * ny
            if d2 >= 1.0:
                continue
            fall = 1.0 - d2
            a = int(peak_alpha * fall * fall)
            if a > 0:
                cv.blend(x, y, r, g, b, a)


def disc(cv, cx, cy, rad, color, alpha=255):
    ellipse(cv, cx, cy, rad, rad, color, alpha, soft=1.0)


def ring(cv, cx, cy, r_out, r_in, color, alpha=255):
    r, g, b = color
    for y in range(int(cy - r_out), int(cy + r_out) + 1):
        for x in range(int(cx - r_out), int(cx + r_out) + 1):
            d = math.hypot(x - cx, y - cy)
            if r_in <= d <= r_out:
                cv.blend(x, y, r, g, b, alpha)


def hline(cv, x0, x1, y, color, alpha=255):
    r, g, b = color
    for x in range(x0, x1):
        cv.blend(x, y, r, g, b, alpha)


def vline(cv, x, y0, y1, color, alpha=255):
    r, g, b = color
    for y in range(y0, y1):
        cv.blend(x, y, r, g, b, alpha)


# ---------------------------------------------------------------- 5x7 font
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
}


def draw_text(cv, text, x, y, scale, color):
    cx = x
    for ch in text:
        glyph = FONT.get(ch)
        if glyph is None:
            cx += 6 * scale
            continue
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == '1':
                    for dy in range(scale):
                        for dx in range(scale):
                            cv.set(cx + gx * scale + dx, y + gy * scale + dy,
                                   *color)
        cx += 6 * scale
    return cx - x


# ---------------------------------------------------------------- scene
def render():
    cv = Canvas(W, H)

    # --- seamless studio backdrop: warm off-white vertical gradient
    bg = [(0.0, (250, 248, 245)), (0.55, (240, 236, 231)),
          (0.82, (228, 223, 216)), (1.0, (214, 208, 200))]
    for y in range(H):
        cr, cg, cb = grad(bg, y / (H - 1))
        cv.fill_row_dithered(y, 0, W, cr, cg, cb)

    # soft centre glow behind the product
    ellipse(cv, 512, 520, 430, 400, (255, 255, 255), 46, soft=1.0)

    # --- floor shadows (soft, layered)
    ellipse(cv, 512, 838, 330, 46, (60, 52, 44), 96, soft=1.0)
    ellipse(cv, 512, 838, 250, 34, (60, 52, 44), 80, soft=1.0)
    ellipse(cv, 865, 894, 140, 16, (60, 52, 44), 70, soft=1.0)

    # --- warm glow above the toasting phone (heat)
    ellipse(cv, 630, 250, 150, 120, (255, 166, 66), 42, soft=1.0)

    # --- smartphone rising out of the right slot (drawn before toaster body
    #     so the body hides its lower end, as if inside the slot)
    ph_x0, ph_y0, ph_x1, ph_y1 = 566, 168, 706, 430
    # bezel
    vgrad_rrect(cv, ph_x0, ph_y0, ph_x1, ph_y1, 22,
                [(0.0, (38, 40, 46)), (1.0, (12, 13, 16))])
    # screen: hot amber, toasted darker towards the top edge
    scr = [(0.0, (146, 74, 22)), (0.18, (214, 110, 30)),
           (0.45, (255, 176, 72)), (0.75, (255, 205, 110)),
           (1.0, (255, 224, 150))]
    vgrad_rrect(cv, ph_x0 + 10, ph_y0 + 12, ph_x1 - 10, ph_y1 - 8, 16, scr)
    # toasted crust: irregular brown scorch along the top of the screen
    ellipse(cv, 600, ph_y0 + 16, 34, 12, (96, 52, 16), 150, soft=1.0)
    ellipse(cv, 660, ph_y0 + 14, 40, 13, (120, 66, 20), 150, soft=1.0)
    ellipse(cv, 636, ph_y0 + 10, 26, 9, (70, 38, 12), 170, soft=1.0)
    # screen glare
    for y in range(ph_y0 + 20, ph_y1 - 20):
        t = (y - ph_y0) / (ph_y1 - ph_y0)
        x0 = ph_x0 + 22 + int(26 * t)
        x1 = x0 + 16
        cv.blend_row(y, x0, x1, 255, 255, 255, 26)
    # app icons on the glowing screen (a toaster app, a clock, a flame)
    icon_cols = [(255, 244, 214), (214, 236, 255), (255, 214, 190),
                 (226, 255, 214), (255, 226, 240), (240, 226, 255)]
    k = 0
    for row_i in range(2):
        for col_i in range(3):
            ix = ph_x0 + 26 + col_i * 38
            iy = ph_y0 + 96 + row_i * 40
            vgrad_rrect(cv, ix, iy, ix + 28, iy + 28, 7,
                        [(0.0, icon_cols[k]), (1.0, (255, 255, 255))])
            k += 1
    # home indicator
    hline(cv, ph_x0 + 52, ph_x1 - 52, ph_y1 - 22, (255, 255, 255), 200)
    hline(cv, ph_x0 + 52, ph_x1 - 52, ph_y1 - 21, (255, 255, 255), 120)

    # --- toaster body: brushed chrome, rounded, hero-centred
    bx0, by0, bx1, by1 = 252, 382, 774, 802
    chrome = [(0.0, (233, 236, 239)), (0.16, (205, 210, 215)),
              (0.38, (168, 174, 181)), (0.55, (196, 201, 206)),
              (0.72, (226, 229, 232)), (0.88, (178, 184, 190)),
              (1.0, (140, 146, 152))]

    def sheen(x, y):
        # soft diagonal studio streak across the chrome
        s = 1.0 - abs((x - y * 0.55 - 330) / 90.0)
        return max(0.0, s) * 0.5

    vgrad_rrect(cv, bx0, by0, bx1, by1, 46, chrome, sheen=sheen)
    # left edge highlight + right edge shade (cylindrical read)
    for y in range(by0 + 30, by1 - 30):
        cv.blend_row(y, bx0 + 6, bx0 + 26, 255, 255, 255, 60)
        cv.blend_row(y, bx1 - 30, bx1 - 8, 40, 44, 50, 46)
    # bottom plinth
    vgrad_rrect(cv, bx0 + 14, by1 - 34, bx1 - 14, by1 + 2, 14,
                [(0.0, (96, 100, 106)), (1.0, (58, 62, 68))])
    # top plate (slightly darker brushed steel)
    vgrad_rrect(cv, bx0 + 4, by0, bx1 - 4, by0 + 34, 30,
                [(0.0, (196, 200, 205)), (1.0, (150, 156, 162))])
    # slots: left empty, right holds the phone
    vgrad_rrect(cv, 322, by0 + 10, 452, by0 + 26, 8,
                [(0.0, (20, 20, 22)), (1.0, (52, 52, 56))])
    vgrad_rrect(cv, 576, by0 + 10, 696, by0 + 26, 8,
                [(0.0, (16, 16, 18)), (1.0, (44, 44, 48))])
    # slot rims catch the light
    hline(cv, 322, 452, by0 + 9, (240, 242, 244), 160)
    hline(cv, 576, 696, by0 + 9, (240, 242, 244), 160)

    # --- brand + model line on the body
    draw_text(cv, "TOASTAPHONE", 512 - 99, 556, 3, (52, 56, 62))
    draw_text(cv, "PHONE", 512 - 45, 596, 2, (96, 100, 106))
    draw_text(cv, "TOASTER", 512 - 35, 614, 2, (96, 100, 106))
    hline(cv, 452, 572, 588, (120, 124, 130), 120)

    # --- browning dial
    disc(cv, 360, 690, 46, (228, 231, 234), 255)
    ring(cv, 360, 690, 46, 41, (120, 126, 132), 255)
    disc(cv, 360, 690, 34, (178, 184, 190), 255)
    disc(cv, 360, 690, 30, (206, 210, 214), 255)
    for i in range(7):
        ang = math.pi * (0.75 + i * 0.25 / 3.0 * 2.0 / 2.0)  # ticks arc
        # ticks from 135deg to 405deg
        a = math.radians(135 + i * 45)
        x0 = 360 + int(38 * math.cos(a))
        y0 = 690 + int(38 * math.sin(a))
        x1 = 360 + int(44 * math.cos(a))
        y1 = 690 + int(44 * math.sin(a))
        for t in range(9):
            xx = int(lerp(x0, x1, t / 8.0))
            yy = int(lerp(y0, y1, t / 8.0))
            cv.set(xx, yy, 70, 74, 80)
    # pointer at "extra toasted"
    a = math.radians(315)
    for t in range(1, 27):
        xx = 360 + int(t * math.cos(a))
        yy = 690 + int(t * math.sin(a))
        cv.set(xx, yy, 176, 84, 24)
        cv.set(xx + 1, yy, 176, 84, 24)
    disc(cv, 360, 690, 6, (70, 74, 80), 255)

    # --- side lever (right)
    vgrad_rrect(cv, 774, 540, 800, 566, 10,
                [(0.0, (60, 62, 66)), (1.0, (28, 30, 33))])
    disc(cv, 800, 553, 9, (40, 42, 46), 255)

    # --- the ONE accessory: a butter knife lying on the floor, right side
    # blade: metallic parallelogram, handle: dark wood
    blade = [(0.0, (226, 230, 234)), (0.5, (196, 201, 206)),
             (1.0, (168, 174, 180))]
    for yy in range(852, 884):
        t = (yy - 852) / 32.0
        x0 = int(742 + 16 * t)
        x1 = int(906 + 16 * t)
        cr, cg, cb = grad(blade, t)
        cv.fill_row(yy, x0, x1, clamp(cr), clamp(cg), clamp(cb))
    # blade tip taper
    for yy in range(852, 884):
        t = (yy - 852) / 32.0
        x1 = int(906 + 16 * t)
        taper = int(12 * t)
        for x in range(x1 - taper, x1):
            cv.blend(x, yy, 240, 242, 244, 120)
    # bright cutting edge
    for yy in range(852, 884):
        t = (yy - 852) / 32.0
        x = int(742 + 16 * t)
        cv.set(x, yy, 250, 251, 252)
    # handle
    vgrad_rrect(cv, 906, 848, 988, 888, 14,
                [(0.0, (74, 50, 34)), (1.0, (46, 30, 20))])
    disc(cv, 922, 868, 3, (200, 170, 120), 255)
    disc(cv, 950, 868, 3, (200, 170, 120), 255)

    # --- final soft contact shadow under the toaster base
    ellipse(cv, 512, 806, 270, 16, (50, 44, 38), 60, soft=1.0)
    return cv


# ---------------------------------------------------------------- PNG out
def chunk(typ, data):
    c = struct.pack(">I", len(data)) + typ + data
    return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


def write_png(cv, path):
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    raw = bytearray()
    for row in cv.rows:
        raw.append(0)
        raw += row
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", ihdr)
    data += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def main():
    cv = render()
    n = write_png(cv, "/output/entry.png")
    print("wrote /output/entry.png", n, "bytes")


if __name__ == "__main__":
    main()
