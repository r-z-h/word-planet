import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw

W, H = 1280, 720
FPS = 24
DUR = 93.58
N = int(DUR * FPS) + 1
FRAMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frames")
os.makedirs(FRAMES, exist_ok=True)

SCENES = [
    (0.00, 3.23, "title", "#1a1033", "#0a0518"),
    (3.23, 7.38, "kid", "#2a1a4d", "#120a24"),
    (7.38, 11.31, "launch", "#2b1b3f", "#0e0620"),
    (11.31, 18.50, "letters", "#123a5a", "#0a1626"),
    (18.50, 25.69, "bubbles", "#5a1a44", "#200a1c"),
    (25.69, 30.20, "maze", "#14503a", "#081e18"),
    (30.20, 37.10, "puzzle", "#5a3a10", "#211505"),
    (37.10, 47.37, "sound", "#3a1a5a", "#160a26"),
    (47.37, 55.53, "blackhole", "#0d1430", "#05070f"),
    (55.53, 59.01, "blackcore", "#0a0a16", "#000000"),
    (59.01, 70.02, "mirror", "#2a4a5a", "#0c1820"),
    (70.02, 76.47, "approach", "#5a4a10", "#221a05"),
    (76.47, 77.86, "crownrise", "#6a5410", "#2a1e05"),
    (77.86, 85.24, "coronation", "#7a5f12", "#2e2106"),
    (85.24, 89.35, "victory", "#4a2a5a", "#180a24"),
    (89.35, 93.58, "logo", "#1a1033", "#08040f"),
]
BEAT = 60.0 / 129.2
PEAKS = [3.23, 7.38, 11.31, 25.69, 30.20, 37.10, 38.98, 40.02, 47.37, 48.97, 50.06, 51.44, 53.28, 54.67, 55.53, 59.01, 64.73, 70.02, 73.65, 76.47, 77.86, 80.62, 82.47, 85.24, 87.54, 88.48, 89.35, 90.56, 92.30]


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def make_bg(c1, c2):
    top = np.array(hex2rgb(c1), dtype=np.float32)
    bot = np.array(hex2rgb(c2), dtype=np.float32)
    rows = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    arr = top[None, :] * (1 - rows) + bot[None, :] * rows
    arr = np.repeat(arr[:, None, :], W, axis=1)
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W * 0.5) / W) ** 2 + ((yy - H * 0.42) / H) ** 2)
    glow = np.clip(1 - d * 1.5, 0, 1)[..., None] * 30
    arr = np.clip(arr + glow, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


BGS = [make_bg(s[3], s[4]) for s in SCENES]

# 视差星空三层
LAYERS = []
for si in range(len(SCENES)):
    rnd = random.Random(2000 + si)
    layers = []
    for depth, count in [(0.35, 70), (0.7, 50), (1.2, 30)]:
        pts = [(rnd.random() * W, rnd.random() * H, rnd.random() * 6.28, rnd.choice([1, 1, 2])) for _ in range(count)]
        layers.append((depth, pts))
    LAYERS.append(layers)

# 暗角
yy, xx = np.mgrid[0:H, 0:W]
vd = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
va = np.clip((vd - 0.55) * 0.9, 0, 1)[..., None] * 130
VIG = Image.fromarray(np.concatenate([np.zeros((H, W, 3), np.uint8), va.astype(np.uint8)], axis=2), "RGBA")


def ease(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def star(d, cx, cy, r, fill="#ffd166", outline=None):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.44
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
    d.polygon(pts, fill=fill, outline=outline)


def crown(d, cx, cy, w, h):
    x0, x1 = cx - w / 2, cx + w / 2
    base = cy + h / 2
    top = cy - h / 2
    pts = [(x0, base), (x0, cy), (cx - w * 0.25, cy - h * 0.10), (cx - w * 0.18, top), (cx, cy - h * 0.05),
           (cx + w * 0.18, top), (cx + w * 0.25, cy - h * 0.10), (x1, cy), (x1, base)]
    d.polygon(pts, fill="#ffd43b", outline="#b8860b")
    d.rectangle([x0, base - h * 0.10, x1, base + h * 0.06], fill="#f59f00", outline="#b8860b")
    for gx, col in [(x0 + w * 0.08, "#ff6b6b"), (cx, "#74c0fc"), (x1 - w * 0.08, "#63e6be")]:
        d.ellipse([gx - 5, base - h * 0.03, gx + 5, base + h * 0.05], fill=col)


def kid(d, cx, cy, s=1.0, t=0.0, arm=0.0):
    # 披风（飘动）
    flap = math.sin(t * 6) * 8 * s
    d.polygon([(cx - 26 * s, cy - 6 * s), (cx - 48 * s + flap, cy + 62 * s), (cx - 10 * s, cy + 46 * s),
               (cx, cy + 58 * s), (cx + 10 * s, cy + 46 * s), (cx + 48 * s + flap, cy + 62 * s), (cx + 26 * s, cy - 6 * s)],
              fill=(210, 44, 50))
    # 腿
    d.rounded_rectangle([cx - 18 * s, cy + 34 * s, cx - 4 * s, cy + 62 * s], radius=7 * s, fill="#e8590c")
    d.rounded_rectangle([cx + 4 * s, cy + 34 * s, cx + 18 * s, cy + 62 * s], radius=7 * s, fill="#e8590c")
    # 身体
    d.rounded_rectangle([cx - 26 * s, cy - 14 * s, cx + 26 * s, cy + 40 * s], radius=15 * s, fill="#ff922b", outline="#b34700", width=max(1, int(2 * s)))
    d.ellipse([cx + 8 * s, cy - 10 * s, cx + 24 * s, cy + 36 * s], fill="#f76707")  # 阴影
    d.rounded_rectangle([cx - 16 * s, cy - 8 * s, cx - 10 * s, cy + 34 * s], radius=4 * s, fill="#ffd8a8")
    # 手臂（摆动）
    ang = math.sin(t * 5 + arm) * 0.3
    d.ellipse([cx - 40 * s, cy - 6 * s + ang * 20, cx - 20 * s, cy + 24 * s + ang * 20], fill="#ff922b", outline="#b34700")
    d.ellipse([cx + 20 * s, cy - 6 * s - ang * 20, cx + 40 * s, cy + 24 * s - ang * 20], fill="#ff922b", outline="#b34700")
    # 背包星
    star(d, cx, cy + 6 * s, 11 * s, fill="#ffe066", outline="#b8860b")
    # 头
    hr = 25 * s
    d.ellipse([cx - hr, cy - 60 * s, cx + hr, cy - 10 * s], fill="#ffd9b3", outline="#c98a5b")
    d.chord([cx - hr, cy - 64 * s, cx + hr, cy - 32 * s], 180, 360, fill="#4b3470")
    er = max(1, int(2.6 * s))
    d.ellipse([cx - 10 * s - er, cy - 39 * s - er, cx - 10 * s + er, cy - 39 * s + er], fill="#2b1b12")
    d.ellipse([cx + 10 * s - er, cy - 39 * s + er, cx + 10 * s + er, cy - 39 * s + er], fill="#2b1b12")
    d.ellipse([cx - 10 * s - er, cy - 39 * s - er, cx - 10 * s + er, cy - 39 * s + er], fill="#2b1b12")
    d.ellipse([cx + 10 * s - er, cy - 39 * s - er, cx + 10 * s + er, cy - 39 * s + er], fill="#2b1b12")
    d.arc([cx - 8 * s, cy - 32 * s, cx + 8 * s, cy - 22 * s], 20, 160, fill="#2b1b12", width=max(1, int(2 * s)))
    d.ellipse([cx - 18 * s, cy - 31 * s, cx - 12 * s, cy - 25 * s], fill="#ff9db4")
    d.ellipse([cx + 12 * s, cy - 31 * s, cx + 18 * s, cy - 25 * s], fill="#ff9db4")
    # 头盔玻璃
    d.arc([cx - hr - 6 * s, cy - 65 * s, cx + hr + 6 * s, cy - 5 * s], 0, 360, fill=(170, 215, 255), width=max(1, int(3 * s)))
    d.arc([cx - hr + 2 * s, cy - 59 * s, cx + hr - 2 * s, cy - 12 * s], 200, 250, fill=(255, 255, 255), width=max(1, int(3 * s)))


def rocket(d, x, y, s=1.0, flame=1.0):
    d.polygon([(x - 14 * s, y - 4 * s), (x - 30 * s, y + 18 * s), (x - 10 * s, y + 16 * s)], fill="#e8590c")
    d.polygon([(x + 14 * s, y - 4 * s), (x + 30 * s, y + 18 * s), (x + 10 * s, y + 16 * s)], fill="#e8590c")
    d.ellipse([x - 15 * s, y - 24 * s, x + 15 * s, y + 24 * s], fill="#f1f3f5", outline="#adb5bd")
    d.ellipse([x - 7 * s, y - 8 * s, x + 7 * s, y + 6 * s], fill="#74c0fc")
    d.polygon([(x - 11 * s, y + 22 * s), (x, y + 58 * s * flame), (x + 11 * s, y + 22 * s)], fill="#ffd43b")
    d.polygon([(x - 5 * s, y + 22 * s), (x, y + 42 * s * flame), (x + 5 * s, y + 22 * s)], fill="#fff3bf")


def glow(img, cx, cy, r, color, alpha=90):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for k in range(8, 0, -1):
        rr = r * k / 8
        od.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=color + (max(3, int(alpha / k)),))
    img.paste(ov, (0, 0), ov)


def speed_lines(d, t, color=(255, 255, 255), n=18, alpha=90):
    rnd = random.Random(int(t * 10) + 7)
    for _ in range(n):
        y = rnd.random() * H
        l = rnd.randint(60, 220)
        x = (rnd.random() * (W + 300) - t * 1500) % (W + 300)
        d.line([x, y, x + l, y], fill=color, width=rnd.choice([1, 1, 2]))


CONFETTI = [(random.Random(7 + i).random(), random.Random(70 + i).random(), random.Random(700 + i).random() * 6.28,
             random.Random(i).choice(["#ffd166", "#ff8fb1", "#74c0fc", "#63e6be"])) for i in range(150)]

for idx in range(N):
    t = idx / FPS
    si = 0
    for j, s in enumerate(SCENES):
        if s[0] <= t < s[1]:
            si = j
            break
    if t >= SCENES[-1][1]:
        si = len(SCENES) - 1
    s0, s1, typ = SCENES[si][0], SCENES[si][1], SCENES[si][2]
    p = ease((t - s0) / max(0.001, s1 - s0))
    img = BGS[si].copy()
    d = ImageDraw.Draw(img)
    pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi / BEAT)

    # 视差星空
    for depth, pts in LAYERS[si]:
        for (sx, sy, ph, sz) in pts:
            x = (sx - t * 18 * depth) % W
            a = 0.3 + 0.7 * abs(math.sin(t * 1.4 + ph))
            c = int(110 + 140 * a)
            d.ellipse([x, sy, x + sz, sy + sz], fill=(c, c, min(255, c + 25)))

    if typ == "title":
        glow(img, W / 2, H / 2, 160 + 30 * pulse, (255, 214, 120), 90)
        star(d, W / 2, H / 2, 64 + 10 * pulse, fill="#ffd43b", outline="#b8860b")
        for k in range(6):
            ang = t * 0.6 + k * math.pi / 3
            d.arc([W / 2 - 200, H / 2 - 200, W / 2 + 200, H / 2 + 200], math.degrees(ang), math.degrees(ang) + 30, fill=(255, 230, 150), width=2)
    elif typ == "kid":
        y = H / 2 + math.sin(t * 2) * 12
        glow(img, W / 2, y, 170, (255, 214, 120), 60)
        kid(d, W / 2, y, 2.6, t)
        for k in range(10):
            ang = t + k * 0.628
            d.ellipse([W / 2 + math.cos(ang) * 210 - 3, y + math.sin(ang) * 160 - 3, W / 2 + math.cos(ang) * 210 + 3, y + math.sin(ang) * 160 + 3], fill="#fff3bf")
    elif typ == "launch":
        for k in range(7):
            px = 150 + k * 160
            d.ellipse([px - 16, 120 - 16, px + 16, 120 + 16], fill=["#74c0fc", "#ff9db4", "#63e6be", "#ffd43b", "#b197fc", "#ffa94d", "#ff8787"][k])
        speed_lines(d, t)
        rx = -120 + (W + 280) * p
        ry = H * 0.68 - math.sin(p * math.pi) * 150
        rocket(d, rx, ry, 2.3, 1.0 + 0.15 * math.sin(t * 30))
    elif typ == "letters":
        # 冰蓝陨石碎片（不用文字）
        for k in range(24):
            lx = (k * 137 + 60) % W
            ly = ((k * 113 + int(p * 760)) % (H + 200)) - 100
            sz = 12 + (k % 5) * 6
            d.polygon([(lx, ly - sz), (lx + sz * 0.7, ly), (lx, ly + sz), (lx - sz * 0.7, ly)],
                      fill=(165, 216, 255), outline=(120, 170, 220))
            d.line([lx - sz, ly - sz * 2, lx, ly - sz], fill=(120, 190, 255), width=2)
        speed_lines(d, t, (165, 216, 255), 14, 70)
        kid(d, 200, 440 + math.sin(t * 2.2) * 10, 1.4, t)
        d.line([230, 440, 580, 300 - 50 * math.sin(p * 6)], fill="#74c0fc", width=5)
    elif typ == "bubbles":
        for k in range(11):
            bx = 90 + (k * 127) % (W - 180)
            by = H + 90 - ((p * 720 + k * 90) % (H + 180))
            rr = 28 + (k % 3) * 13
            d.ellipse([bx - rr, by - rr, bx + rr, by + rr], outline=(255, 157, 180), width=3)
            d.ellipse([bx - rr * 0.45, by - rr * 0.6, bx - rr * 0.1, by - rr * 0.28], fill=(255, 255, 255))
        kid(d, W * 0.35 + math.sin(t * 1.5) * 46, 430 - abs(math.sin(t * 3)) * 70, 1.7, t)
    elif typ == "maze":
        off = int(p * 120) % 70
        for gx in range(-70, W + 70, 70):
            d.line([gx + off, 60, gx + off, H], fill=(60, 180, 150), width=7)
        for gy in range(60, H, 70):
            d.line([0, gy, W, gy], fill=(60, 180, 150), width=7)
        glow(img, W * (0.15 + 0.7 * p), 400, 70, (99, 230, 190), 70)
        kid(d, W * (0.15 + 0.7 * p), 400 + math.sin(t * 4) * 18, 1.45, t)
    elif typ == "puzzle":
        for k in range(10):
            bx = k * 150 - (p * 200) % 150
            by = 420 + (k % 2) * 22
            if -120 < bx < W:
                d.rounded_rectangle([bx, by, bx + 120, by + 62], radius=10, fill="#ffa94d", outline="#b34700", width=3)
                d.ellipse([bx + 46, by - 8, bx + 76, by + 14], fill="#211505")
        kid(d, W * 0.5, 330 - abs(math.sin(p * 8)) * 100, 1.55, t)
        glow(img, W * 0.5, 330, 90, (255, 169, 77), 60)
    elif typ == "sound":
        for k in range(7):
            rr = 60 + ((p * 520 + k * 80) % 540)
            d.arc([W * 0.7 - rr, H * 0.5 - rr, W * 0.7 + rr, H * 0.5 + rr], 120, 240, fill=(177, 151, 252), width=6)
        for k in range(8):
            nx = 120 + (k * 143 + int(p * 130)) % (W - 100)
            ny = 120 + (k * 79) % 420
            d.line([nx, ny + 10, nx, ny - 26], fill="#d0bfff", width=5)
            d.ellipse([nx - 12, ny + 2, nx - 1, ny + 15], fill="#d0bfff")
            if k % 2:
                d.line([nx, ny - 26, nx + 16, ny - 17], fill="#d0bfff", width=5)
        kid(d, W * 0.26, 430 + math.sin(t * 5) * 20, 1.55, t)
    elif typ == "blackhole":
        glow(img, W / 2, H / 2, 210, (116, 120, 255), 55)
        d.ellipse([W / 2 - 160, H / 2 - 160, W / 2 + 160, H / 2 + 160], fill=(2, 3, 8), outline=(90, 70, 160), width=6)
        for k in range(6):
            rr = 175 + k * 26
            d.arc([W / 2 - rr, H / 2 - rr, W / 2 + rr, H / 2 + rr], k * 40, k * 40 + 220, fill=(120, 100, 200), width=3)
        speed_lines(d, -t, (120, 110, 190), 10, 60)
        kid(d, W * 0.22, 410 + math.sin(t * 1.4) * 8, 1.2, t)
    elif typ == "blackcore":
        core = 0.5 + 0.5 * math.sin(t * 6)
        glow(img, W / 2, H / 2, 55 + core * 25, (255, 120, 170), 80)
        d.ellipse([W / 2 - 16, H / 2 - 16, W / 2 + 16, H / 2 + 16], fill=(255, 170, 200))
        kid(d, W / 2, H / 2 + 120, 0.75, t)
    elif typ == "mirror":
        glow(img, W / 2, H / 2, 240, (255, 157, 220), 45)
        for k in range(8):
            sx = 100 + k * 150
            d.line([sx, 90, sx + 90, 660], fill=(120, 220, 230), width=2)
        kid(d, W * 0.34, 410, 1.55, t)
        for k in range(3):
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(ov)
            kid(od, W * 0.66, 390 + k * 10, 1.5 - k * 0.16, t, 1.5)
            ov.putalpha(55)
            img.paste(ov, (0, 0), ov)
    elif typ == "approach":
        for k in range(9):
            yy = H - k * 52
            d.rectangle([W / 2 - 170 + k * 8, yy, W / 2 + 170 - k * 8, yy + 38], fill="#ffd43b", outline="#b8860b")
        glow(img, W / 2, 150, 150, (255, 214, 120), 100)
        crown(d, W / 2, 140, 170, 105)
        kid(d, W / 2 + math.sin(t * 2) * 34, 360, 1.25, t)
        speed_lines(d, -t, (255, 230, 150), 12, 60)
    elif typ == "crownrise":
        glow(img, W / 2, H / 2, 220 + 40 * pulse, (255, 214, 120), 110)
        cr = H * 0.78 - p * (H * 0.36)
        crown(d, W / 2, cr, 250 + 45 * pulse, 155)
        for k in range(12):
            ang = k * math.pi * 2 / 12 + t
            d.ellipse([W / 2 + math.cos(ang) * (265 + 30 * math.sin(t + k)) - 4, cr + math.sin(ang) * 170 - 4,
                       W / 2 + math.cos(ang) * (265 + 30 * math.sin(t + k)) + 4, cr + math.sin(ang) * 170 + 4], fill="#fff3bf")
    elif typ == "coronation":
        glow(img, W / 2, H / 2, 280 + 60 * pulse, (255, 230, 150), 130)
        crown(d, W / 2, 300, 270, 165)
        kid(d, W / 2, 480, 1.75, t)
        for k in range(5):
            rr = 210 + k * 60 + int((t * 140) % 90)
            d.arc([W / 2 - rr, H / 2 - rr, W / 2 + rr, H / 2 + rr], 0, 360, fill=(255, 230, 150), width=3)
        if p > 0.9:
            fl = int(190 * (1 - (p - 0.9) / 0.1))
            ov = Image.new("RGBA", (W, H), (255, 255, 240, max(0, fl)))
            img.paste(Image.new("RGB", (W, H), (255, 255, 245)), (0, 0), ov)
    elif typ == "victory":
        for k in range(7):
            ang = k * math.pi * 2 / 7 + t * 0.5
            px = W / 2 + math.cos(ang) * 430
            py = H * 0.45 + math.sin(ang) * 175
            d.ellipse([px - 23, py - 23, px + 23, py + 23], fill=["#74c0fc", "#ff9db4", "#63e6be", "#ffd43b", "#b197fc", "#ffa94d", "#ff8787"][k])
        # 光芒
        for k in range(24):
            ang = k * math.pi / 12 + t * 0.3
            d.line([W / 2, 300, W / 2 + math.cos(ang) * 520, 300 + math.sin(ang) * 520], fill=(255, 230, 150), width=2)
        kid(d, W / 2, 380, 1.95, t)
        crown(d, W / 2, 225, 235, 145)
        for (fx, fy, ph, col) in CONFETTI:
            yy = (fy * H + t * 100) % H
            xx = fx * W
            d.rectangle([xx, yy, xx + 8, yy + 13], fill=col)
        for k in range(18):
            ang = t * 0.8 + k * 0.35
            d.ellipse([W / 2 + math.cos(ang) * (260 + k * 8) - 5, 500 + math.sin(ang) * (120 + k * 3) - 3,
                       W / 2 + math.cos(ang) * (260 + k * 8) + 5, 500 + math.sin(ang) * (120 + k * 3) + 3], fill="#ff9db4")
    elif typ == "logo":
        glow(img, W / 2, H / 2 - 20, 150, (255, 214, 120), 80)
        crown(d, W / 2, H / 2 - 90, 160, 95)
        star(d, W / 2, H / 2 + 60, 26 + 4 * pulse, fill="#ffd43b", outline="#b8860b")

    # 镜头 zoom / pan
    zoom = 1.0
    px = py = 0.0
    if typ in ("title", "kid"):
        zoom = 1.02 + 0.06 * p
    elif typ == "letters":
        zoom = 1.0 + 0.08 * p
    elif typ == "blackcore":
        zoom = 1.18 + 0.05 * p
    elif typ in ("coronation", "victory"):
        zoom = 1.03 + 0.07 * p
    elif typ == "logo":
        zoom = 1.0 + 0.03 * p
    if zoom != 1.0:
        nw, nh = int(W * zoom), int(H * zoom)
        big = img.resize((nw, nh), Image.Resampling.LANCZOS)
        left = (nw - W) // 2 + int(px)
        top = (nh - H) // 2 + int(py)
        img = big.crop((left, top, left + W, top + H))

    # 重音冲击白闪
    for pt in PEAKS:
        if abs(t - pt) < 0.045:
            ov = Image.new("RGBA", (W, H), (255, 255, 255, 70))
            img.paste(Image.new("RGB", (W, H), (255, 255, 255)), (0, 0), ov)
            break

    # 暗角
    img.paste(VIG, (0, 0), VIG)
    img.save(os.path.join(FRAMES, f"{idx:05d}.jpg"), quality=87)
    if idx % 240 == 0:
        print(f"frame {idx}/{N}", flush=True)

print("DONE", N)
