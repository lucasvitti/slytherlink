# -*- coding: utf-8 -*-
"""Gera a imagem de compartilhamento (Open Graph) 1200x630 do site.

Agora desenha um tabuleiro Slitherlink REAL: o laço-solução e as dicas vêm do
próprio motor (core.js, via og_board.js), então o quadro é sempre válido.
"""
import json
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

# --- tabuleiro real (laço + dicas consistentes) ---
SEED, ROWS, COLS, DIF = 'ogboard', 6, 6, 'medio'
proc = subprocess.run(['node', 'og_board.js', SEED, str(ROWS), str(COLS), DIF],
                      capture_output=True, text=True, check=True)
board = json.loads(proc.stdout)
rows, cols, clues = board['rows'], board['cols'], board['clues']
solution = board['solution']

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

img = Image.new('RGB', (W, H), BG)

# --- geometria do tabuleiro (à esquerda, centrado verticalmente) ---
box = 470
step = box / max(rows, cols)
bw, bh = cols * step, rows * step
ox = 80 + (box - bw) / 2
oy = (H - bh) / 2

CLUE = font(['arialbd.ttf', 'segoeuib.ttf', 'DejaVuSans-Bold.ttf'], int(step * 0.5))


def P(r, c):
    return (ox + c * step, oy + r * step)


def edge_pts(key):
    t, r, c = key.split(':')
    r, c = int(r), int(c)
    return (P(r, c), P(r, c + 1)) if t == 'H' else (P(r, c), P(r + 1, c))

dd = ImageDraw.Draw(img)

# pontos da grade
for r in range(rows + 1):
    for c in range(cols + 1):
        x, y = P(r, c)
        dd.ellipse([x - 4, y - 4, x + 4, y + 4], fill=DOT)

segs = [edge_pts(k) for k in solution]
lw = max(7, int(step * 0.19))

# brilho do laço
glow = Image.new('RGB', (W, H), (0, 0, 0))
gd = ImageDraw.Draw(glow)
for a, b in segs:
    gd.line([a, b], fill=BLUE, width=lw * 2)
glow = glow.filter(ImageFilter.GaussianBlur(10)).point(lambda p: int(p * 0.6))
img = ImageChops.add(img, glow)

# laço sólido + cantos arredondados
dd = ImageDraw.Draw(img)
for a, b in segs:
    dd.line([a, b], fill=BLUE, width=lw)
vert = set()
for k in solution:
    t, r, c = k.split(':')
    r, c = int(r), int(c)
    vert.add((r, c))
    vert.add((r, c + 1) if t == 'H' else (r + 1, c))
for r, c in vert:
    x, y = P(r, c)
    dd.ellipse([x - lw / 2, y - lw / 2, x + lw / 2, y + lw / 2], fill=BLUE)

# dicas (consistentes com o laço)
for r in range(rows):
    for c in range(cols):
        k = clues[r][c]
        if k is None or k < 0:
            continue
        x, y = P(r + 0.5, c + 0.5)
        dd.text((x, y), str(k), font=CLUE, fill=SALMON, anchor='mm')

# --- texto à direita ---
x = 630
dd.text((x, 232), 'Slitherlink', font=TITLE, fill=WHITE)
dd.text((x, 360), 'Gere e resolva o laço único.', font=TAG, fill=MUTED)
dd.text((x, 406), 'Pura dedução lógica.', font=TAG, fill=MUTED)
dd.text((x, 470), 'slitherlink.lucas.mat.br', font=URLF, fill=BLUE)

img.save('web/og-image.png')
print('og-image gerada (1200x630) — tabuleiro %dx%d, %d dicas' % (rows, cols, board['nClues']))
