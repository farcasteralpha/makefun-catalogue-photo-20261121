#!/usr/bin/env python3
"""TOASTAPHONE - catalogue photo of an impossible gadget.

Pure-stdlib procedural renderer. Writes /output/entry.png (1024x1024).
Deterministic: fixed constants only, no clock, no unseeded randomness.
"""
import math
import os
import struct
import zlib

W = H = 1024
OUT = "/output/entry.png"

fb = bytearray(W * H * 3)


def blend(x, y, r, g, b, a):
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        i = (y * W + x) * 3
        if a >= 1.0:
            fb[i] = r
            fb[i + 1] = g
            fb[i + 2] = b
        else:
            ia = 1.0 - a
            fb[i] = int(fb[i] * ia + r * a + 0.5)
            fb[i + 1] = int(fb[i + 1] * ia + g * a + 0.5)
            fb[i + 2] = int(fb[i + 2] * ia + b * a + 0.5)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp3(c1, c2, t):
    return (int(lerp(c1[0], c2[0], t) + 0.5),
            int(lerp(c1[1], c2[1], t) + 0.5),
            int(lerp(c1[2], c2[2], t) + 0.5))


def vgrad(stops, t):
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        if t <= stops[i][0]:
            t0, c0 = stops[i - 1]
            t1, c1 = stops[i]
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return lerp3(c0, c1, f)
    return stops[-1][1]


def fill_rect(x0, y0, x1, y1, col, a=1.0):
    x0 = max(0, int(x0))
    y0 = max(0, int(y0))
    x1 = min(W, int(x1))
    y1 = min(H, int(y1))
    r, g, b = col
    for y in range(y0, y1):
        base = y * W * 3
        for x in range(x0, x1):
            i = base + x * 3
            if a >= 1.0:
                fb[i] = r
                fb[i + 1] = g
                fb[i + 2] = b
            else:
                ia = 1.0 - a
                fb[i] = int(fb[i] * ia + r * a + 0.5)
                fb[i + 1] = int(fb[i + 1] * ia + g * a + 0.5)
                fb[i + 2] = int(fb[i + 2] * ia + b * a + 0.5)


def rounded_rect(x0, y0, x1, y1, r, color_fn):
    x0i = max(0, int(x0))
    y0i = max(0, int(y0))
    x1i = min(W, int(x1))
    y1i = min(H, int(y1))
    cx0, cy0 = x0 + r, y0 + r
    cx1, cy1 = x1 - r, y1 - r
    r2 = r * r
    for y in range(y0i, y1i):
        for x in range(x0i, x1i):
            dx = 0.0
            if x < cx0:
                dx = cx0 - x
            elif x > cx1:
                dx = x - cx1
            dy = 0.0
            if y < cy0:
                dy = cy0 - y
            elif y > cy1:
                dy = y - cy1
            if dx * dx + dy * dy <= r2:
                c = color_fn(x, y)
                if c is not None:
                    blend(x, y, c[0], c[1], c[2], c[3])


def ellipse(cx, cy, rx, ry, col, a):
    x0 = max(0, int(cx - rx))
    x1 = min(W, int(cx + rx) + 1)
    y0 = max(0, int(cy - ry))
    y1 = min(H, int(cy + ry) + 1)
    for y in range(y0, y1):
        t = (y - cy) / ry
        dx = rx * math.sqrt(max(0.0, 1.0 - t * t))
        xa = max(x0, int(cx - dx))
        xb = min(x1, int(cx + dx) + 1)
        for x in range(xa, xb):
            blend(x, y, col[0], col[1], col[2], a)


def disc(cx, cy, r, col, a=1.0):
    ellipse(cx, cy, r, r, col, a)


def polygon(points, col, a=1.0):
    ys = [p[1] for p in points]
    y0 = max(0, int(min(ys)))
    y1 = min(H, int(max(ys)) + 1)
    n = len(points)
    for y in range(y0, y1):
        xs = []
        for i in range(n):
            x1, y1p = points[i]
            x2, y2p = points[(i + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                t = (y - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        if len(xs) >= 2:
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = max(0, int(xs[k]))
                xb = min(W, int(xs[k + 1]) + 1)
                for x in range(xa, xb):
                    blend(x, y, col[0], col[1], col[2], a)


def line(x0, y0, x1, y1, col, a=1.0, width=1):
    steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for s in range(steps + 1):
        t = s / max(1, steps)
        x = int(x0 + (x1 - x0) * t)
        y = int(y0 + (y1 - y0) * t)
        for wy in range(-(width // 2), width // 2 + 1):
            for wx in range(-(width // 2), width // 2 + 1):
                blend(x + wx, y + wy, col[0], col[1], col[2], a)


FONT = {
    'T': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    'O': [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'A': [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'S': [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    'P': ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    'H': ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'N': ["#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"],
    'E': ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
}


def draw_text(s, x, y, scale, col, spacing=3):
    cx = x
    for ch in s:
        g = FONT.get(ch)
        if g is None:
            cx += 5 * scale + spacing
            continue
        for r in range(7):
            row = g[r]
            for c in range(5):
                if row[c] == '#':
                    fill_rect(cx + c * scale, y + r * scale,
                              cx + c * scale + scale, y + r * scale + scale, col)
        cx += 5 * scale + spacing


def chrome_fn(x, y):
    t = (y - 440) / 340.0
    base = vgrad([(0.0, (233, 234, 237)), (0.35, (204, 207, 212)),
                  (0.70, (169, 173, 180)), (1.0, (134, 139, 147))], t)
    sheen = math.exp(-((x - 335) ** 2) / (2 * 70.0 ** 2)) * 0.38
    dark = 0.0
    if x > 700:
        dark = (x - 700) / 74.0 * 0.18
    r = min(255, int(base[0] * (1.0 - dark) + 255 * sheen))
    g = min(255, int(base[1] * (1.0 - dark) + 255 * sheen))
    b = min(255, int(base[2] * (1.0 - dark) + 255 * sheen))
    return (r, g, b, 1.0)


def plate_fn(x, y):
    t = (y - 408) / 40.0
    base = vgrad([(0.0, (118, 122, 130)), (1.0, (88, 91, 99))], t)
    sheen = math.exp(-((x - 360) ** 2) / (2 * 90.0 ** 2)) * 0.25
    return (min(255, int(base[0] + 255 * sheen)),
            min(255, int(base[1] + 255 * sheen)),
            min(255, int(base[2] + 255 * sheen)), 1.0)


def bezel_fn(x, y):
    t = (y - 128) / 320.0
    base = vgrad([(0.0, (54, 56, 62)), (0.5, (32, 34, 40)),
                  (1.0, (22, 23, 27))], t)
    if y < 190:
        f = (190 - y) / 62.0 * 0.70
        base = lerp3(base, (122, 74, 32), f)
    return (base[0], base[1], base[2], 1.0)


def screen_fn(x, y):
    t = (y - 142) / 306.0
    base = vgrad([(0.0, (255, 196, 90)), (0.5, (255, 140, 50)),
                  (1.0, (232, 84, 28))], t)
    if y < 200:
        tb = (y - 142) / 58.0
        base = lerp3((110, 62, 26), base, tb)
    d = (x - 352) - (y - 142) * 0.55
    if 30 < d < 82:
        base = lerp3(base, (255, 255, 255), 0.16)
    return (base[0], base[1], base[2], 1.0)


def solid(col):
    return lambda x, y: (col[0], col[1], col[2], 1.0)


def render():
    # 1. Studio backdrop: warm light-grey vertical gradient + soft vignette.
    top = (243, 241, 235)
    bot = (213, 208, 199)
    for y in range(H):
        t = y / (H - 1)
        base = lerp3(top, bot, t)
        row = y * W * 3
        dy = y - 420
        for x in range(W):
            dx = x - 512
            d2 = dx * dx + dy * dy
            f = 1.0 - 0.045 * d2 / (950.0 * 950.0)
            fb[row + x * 3] = int(base[0] * f + 0.5)
            fb[row + x * 3 + 1] = int(base[1] * f + 0.5)
            fb[row + x * 3 + 2] = int(base[2] * f + 0.5)

    # 2. Floor band + horizon line.
    fill_rect(0, 780, W, H, (205, 199, 188), 0.6)
    fill_rect(0, 779, W, 782, (180, 174, 164), 0.25)

    # 3. Warm heat glow behind the phone (subtle, wide).
    ellipse(425, 230, 200, 150, (255, 150, 60), 0.05)

    # 4. Soft floor shadows.
    ellipse(512, 798, 340, 40, (40, 36, 30), 0.20)
    ellipse(512, 796, 300, 32, (40, 36, 30), 0.22)
    ellipse(512, 794, 250, 24, (40, 36, 30), 0.22)
    ellipse(512, 783, 290, 14, (40, 36, 30), 0.28)
    ellipse(895, 862, 110, 11, (40, 36, 30), 0.20)

    # 5. Butter knife (the one accessory), lying on the floor, right side.
    # Bigger and clearer: wide steel blade, dark wooden handle.
    polygon([(862, 830), (985, 800), (998, 812), (872, 844)], (198, 201, 207))
    polygon([(866, 832), (982, 803), (990, 809), (872, 840)], (238, 240, 243), 0.7)
    polygon([(790, 842), (862, 828), (868, 842), (796, 858)], (88, 60, 38))
    polygon([(796, 844), (860, 830), (864, 838), (800, 854)], (122, 86, 54), 0.8)

    # 6. Toaster body, chrome.
    rounded_rect(250, 440, 774, 780, 28, chrome_fn)
    fill_rect(252, 450, 258, 772, (255, 255, 255), 0.30)
    fill_rect(766, 450, 772, 772, (70, 74, 80), 0.25)

    # 7. Top plate + slots.
    rounded_rect(262, 408, 762, 448, 14, plate_fn)
    rounded_rect(330, 414, 520, 442, 8, solid((16, 18, 20)))
    rounded_rect(560, 414, 700, 442, 8, solid((16, 18, 20)))

    # 8. Smartphone rising out of the left slot, mid-toast.
    rounded_rect(340, 128, 510, 448, 18, bezel_fn)
    rounded_rect(352, 142, 498, 448, 12, screen_fn)
    # Notch.
    rounded_rect(408, 146, 442, 160, 6, solid((30, 32, 36)))
    # App icons, 3 x 4 grid, still alive on the hot screen.
    icon_cols = [(255, 255, 255), (120, 200, 255), (255, 210, 90),
                 (140, 230, 160), (255, 150, 180), (190, 160, 255),
                 (255, 240, 200), (110, 220, 210), (255, 190, 120),
                 (200, 220, 255), (180, 255, 190), (255, 170, 150)]
    k = 0
    for row in range(4):
        for col in range(3):
            ix = 366 + col * 44
            iy = 200 + row * 44
            rounded_rect(ix, iy, ix + 28, iy + 28, 7, solid(icon_cols[k]))
            disc(ix + 14, iy + 14, 4, (255, 255, 255), 0.8)
            k += 1
    # Dock bar.
    rounded_rect(366, 400, 484, 428, 10, solid((255, 255, 255)))

    # 9. Lever on the right side.
    rounded_rect(770, 590, 806, 612, 6, solid((200, 203, 208)))
    disc(810, 601, 10, (40, 42, 46))
    disc(807, 598, 3, (120, 124, 130), 0.8)

    # 10. Browning dial, set to extra toasted.
    disc(655, 622, 46, (58, 60, 64))
    disc(655, 622, 41, (246, 243, 237))
    for ang in (150, 105, 60, 15, -30):
        rad = math.radians(ang)
        x1 = 655 + math.cos(rad) * 30
        y1 = 622 - math.sin(rad) * 30
        x2 = 655 + math.cos(rad) * 37
        y2 = 622 - math.sin(rad) * 37
        line(x1, y1, x2, y2, (70, 72, 76), 1.0, 2)
    prad = math.radians(15)
    line(655, 622, 655 + math.cos(prad) * 28, 622 - math.sin(prad) * 28,
         (200, 60, 30), 1.0, 3)
    disc(655, 622, 6, (60, 62, 66))

    # 11. Brand + dial label.
    draw_text("TOASTAPHONE", 415, 500, 3, (58, 60, 65))
    draw_text("TOAST", 639, 678, 1, (90, 92, 96))

    # 12. Deterministic fine grain, photo feel.
    for y in range(H):
        row = y * W * 3
        for x in range(W):
            h = (x * 374761393 + y * 668265263 + 12345) & 0xFFFFFFFF
            n = (((h ^ (h >> 13)) % 9) - 4)
            i = row + x * 3
            fb[i] = max(0, min(255, fb[i] + n))
            fb[i + 1] = max(0, min(255, fb[i + 1] + n))
            fb[i + 2] = max(0, min(255, fb[i + 2] + n))


def write_png(path):
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return c

    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += fb[y * W * 3:(y + 1) * W * 3]
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    render()
    os.makedirs("/output", exist_ok=True)
    n = write_png(OUT)
    print("wrote %s (%d bytes)" % (OUT, n))


if __name__ == "__main__":
    main()
