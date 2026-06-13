# -*- coding: utf-8 -*-
"""Gera a imagem do laco de tabuleiros grandes (100x100), sem reducao de
dicas: apenas o caminho fechado renderizado."""
import time

import cv2

import gerador as ger
import plota


def salva_laco(nome, lin, col, densidade, seed, pad=12):
    t0 = time.perf_counter()
    _, tab, _ = ger.gera_Tabuleiro2(densidade=densidade, lin=lin, col=col,
                                    seed=seed, dicas=False)
    t1 = time.perf_counter()
    img = plota.gera_imagem(tab, plota_caminho=True, plota_dicas=False,
                            plota_grid=False, pad=pad,
                            raio_vertice=0, espessura_aresta=max(1, pad//6),
                            cor_v=(65, 105, 225))
    cv2.imwrite(nome + ".png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    t2 = time.perf_counter()
    n = len(tab.caminho)
    print(f"{nome}: {lin}x{col} | laco {n} vertices (densidade {n/(lin*col):.2f})"
          f" | gerar {t1-t0:.2f}s render {t2-t1:.1f}s | {img.shape[1]}x{img.shape[0]}px")


salva_laco("loop_100x100_ham",    100, 100, 1.0,  42)
salva_laco("loop_100x100_regiao", 100, 100, 0.6, 123)
print("ok")
