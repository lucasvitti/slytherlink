# -*- coding: utf-8 -*-
"""Gera a imagem de compartilhamento (Open Graph) 1200x630 do site."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

W, H = 1200, 630
BG = (14, 15, 19)
BLUE = (79, 157, 255)
SALMON = (244, 160, 140)
WHITE = (236, 238, 244)
MUTED = (141, 152, 168)
DOT = (78, 82, 92)


def font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()

TITLE = font(['segoeuib.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf'], 104)
TAG = font(['segoeui.ttf', 'arial.ttf', 'DejaVuSans.ttf'], 36)
URLF = font(['segoeuib.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf'], 31)
CLUE = font(['arialbd.ttf', 'segoeuib.ttf', 'DejaVuSans-Bold.ttf'], 40)

img = Image.new('RGB', (W, H), BG)

# --- tabuleiro à esquerda ---
m, size = 90, 460
oy = (H - size) // 2


def P(gx, gy):
    return (m + gx / 4 * size, oy + gy / 4 * size)

dd = ImageDraw.Draw(img)
for gx in range(5):
    for gy in range(5):
        x, y = P(gx, gy)
        dd.ellipse([x - 5, y - 5, x + 5, y + 5], fill=DOT)

loop = [(0, 1), (2, 1), (2, 0), (3, 0), (3, 2), (4, 2), (4, 4), (1, 4), (1, 3), (0, 3)]
pts = [P(*g) for g in loop]

# brilho
glow = Image.new('RGB', (W, H), (0, 0, 0))
gd = ImageDraw.Draw(glow)
for i in range(len(pts)):
    gd.line([pts[i], pts[(i + 1) % len(pts)]], fill=BLUE, width=30)
glow = glow.filter(ImageFilter.GaussianBlur(11)).point(lambda p: int(p * 0.6))
img = ImageChops.add(img, glow)

dd = ImageDraw.Draw(img)
for i in range(len(pts)):
    dd.line([pts[i], pts[(i + 1) % len(pts)]], fill=BLUE, width=15, joint='curve')
for p in pts:
    dd.ellipse([p[0] - 8, p[1] - 8, p[0] + 8, p[1] + 8], fill=BLUE)

for gx, gy, n in [(0, 2, '2'), (1, 1, '3'), (3, 3, '1'), (2, 2, '2')]:
    cx, cy = m + (gx + 0.5) / 4 * size, oy + (gy + 0.5) / 4 * size
    dd.text((cx, cy), n, font=CLUE, fill=SALMON, anchor='mm')

# --- texto à direita ---
x = 630
dd.text((x, 232), 'Slitherlink', font=TITLE, fill=WHITE)
dd.text((x, 360), 'Gere e resolva o laço único.', font=TAG, fill=MUTED)
dd.text((x, 406), 'Pura dedução lógica.', font=TAG, fill=MUTED)
dd.text((x, 470), 'slitherlink.lucas.mat.br', font=URLF, fill=BLUE)

img.save('web/og-image.png')
print('og-image gerada (1200x630)')
