import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

_HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(_HERE, "ref_frames")
OUT = os.path.join(_HERE, "ref_out")
os.makedirs(OUT, exist_ok=True)
W, H = 1280, 720
N = len([f for f in os.listdir(SRC) if f.lower().endswith(".jpg")])

# vignette
yy, xx = np.mgrid[0:H, 0:W]
vd = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
va = np.clip((vd - 0.6) * 1.1, 0, 1)[..., None] * 120
VIG = Image.fromarray(np.concatenate([np.zeros((H, W, 3), np.uint8), va.astype(np.uint8)], axis=2), "RGBA")

# 右下角羽化黑块（彻底盖掉水印）
mask = Image.new("L", (W, H), 0)
md = ImageDraw.Draw(mask)
md.rectangle([1000, 600, W, H], fill=255)
MASK = mask.filter(ImageFilter.GaussianBlur(16))
BLACK = Image.new("RGB", (W, H), (4, 3, 9))

import random

rnd = random.Random(99)
SPARK = [(rnd.random() * W, rnd.random() * H, rnd.random() * 6.28, rnd.uniform(0.4, 1.4), rnd.choice([1, 1, 2, 3])) for _ in range(90)]
PEAKS = [3.23, 7.38]

for i in range(N):
    fn = os.path.join(SRC, f"{i+1:05d}.jpg")
    if not os.path.exists(fn):
        fn = os.path.join(SRC, f"{i:05d}.jpg")
    img = Image.open(fn).convert("RGB")
    # gentle zoom
    p = i / max(1, N - 1)
    z = 1.02 + 0.04 * math.sin(math.pi * p)
    nw, nh = int(W * z), int(H * z)
    big = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left, top = (nw - W) // 2, (nh - H) // 2
    img = big.crop((left, top, left + W, top + H))

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    # gold light rays top-left
    for k in range(4):
        xx0 = -120 + k * 80
        od.polygon([(xx0, 0), (xx0 + 180, 0), (xx0 + 520, H), (xx0 + 260, H)], fill=(255, 220, 150, 12))
    # sparkles
    for (sx, sy, ph, sp, sz) in SPARK:
        y = (sy - i * sp) % H
        a = int(120 + 120 * abs(math.sin(i * 0.15 + ph)))
        col = (255, 240, 190, a) if sz > 1 else (255, 255, 255, a)
        od.ellipse([sx, y, sx + sz, y + sz], fill=col)
    img.paste(ov, (0, 0), ov)
    img.paste(BLACK, (0, 0), MASK)
    img.paste(VIG, (0, 0), VIG)
    # beat flash
    t = i / 24.0
    for pt in PEAKS:
        if abs(t - pt) < 0.05:
            ov2 = Image.new("RGBA", (W, H), (255, 250, 230, 70))
            img.paste(Image.new("RGB", (W, H), (255, 250, 230)), (0, 0), ov2)
            break
    img.save(os.path.join(OUT, f"{i:05d}.jpg"), quality=90)

print("processed", N)
