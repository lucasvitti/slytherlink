# -*- coding: utf-8 -*-
"""Gera os ícones do PWA: um laço de Slitherlink azul sobre fundo escuro."""
import os
import cv2
import numpy as np

os.makedirs('web/icons', exist_ok=True)

BG = (19, 15, 14)        # #0e0f13 em BGR
BLUE = (255, 157, 79)    # #4f9dff em BGR
DOT = (70, 70, 70)

# laço fechado (coordenadas numa grade 4x4 de células -> pontos 0..4)
LOOP = [(0, 1), (2, 1), (2, 0), (3, 0), (3, 2), (4, 2),
        (4, 4), (1, 4), (1, 3), (0, 3)]


def draw(size, maskable=False):
    img = np.full((size, size, 3), BG, np.uint8)
    margin = size * (0.30 if maskable else 0.16)   # área segura p/ maskable
    span = size - 2 * margin

    def P(gx, gy):
        return (int(margin + gx / 4 * span), int(margin + gy / 4 * span))

    for gx in range(5):
        for gy in range(5):
            cv2.circle(img, P(gx, gy), max(2, int(size * 0.012)), DOT, -1, cv2.LINE_AA)

    pts = [P(*g) for g in LOOP]
    th = max(4, int(size * 0.052))

    # brilho (linha grossa borrada por baixo)
    glow = np.zeros_like(img)
    for i in range(len(pts)):
        cv2.line(glow, pts[i], pts[(i + 1) % len(pts)], BLUE, th * 2, cv2.LINE_AA)
    glow = cv2.GaussianBlur(glow, (0, 0), size * 0.018)
    img = cv2.addWeighted(img, 1.0, glow, 0.55, 0)

    for i in range(len(pts)):
        cv2.line(img, pts[i], pts[(i + 1) % len(pts)], BLUE, th, cv2.LINE_AA)
    for p in pts:
        cv2.circle(img, p, th // 2, BLUE, -1, cv2.LINE_AA)
    return img


big = draw(512)
cv2.imwrite('web/icons/icon-512.png', big)
cv2.imwrite('web/icons/icon-192.png', cv2.resize(big, (192, 192), interpolation=cv2.INTER_AREA))
cv2.imwrite('web/icons/icon-maskable-512.png', draw(512, maskable=True))
cv2.imwrite('web/icons/apple-touch.png', cv2.resize(big, (180, 180), interpolation=cv2.INTER_AREA))
cv2.imwrite('web/icons/favicon-32.png', cv2.resize(big, (32, 32), interpolation=cv2.INTER_AREA))
print('icones gerados em web/icons/')
