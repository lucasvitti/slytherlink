# -*- coding: utf-8 -*-
"""Gera pares de imagens (puzzle + solucao) para alguns tabuleiros."""
import time

import cv2

import gerador as ger
import plota


def salva_par(nome, lin, col, densidade, seed, simetria=False):
    t0 = time.perf_counter()
    tab, puzzle, dif = ger.gera_Puzzle(densidade=densidade, lin=lin, col=col,
                                       seed=seed, simetria=simetria)
    dt = time.perf_counter() - t0
    n_dicas = int((puzzle >= 0).sum())
    tot = (lin-1)*(col-1)

    # parametros de plot proporcionais ao tamanho
    pad = max(34, int(640 / max(lin, col)))
    kw = dict(pad=pad, raio_vertice=max(3, pad//12),
              escala_fonte=pad/70.0, espessura_fonte=2,
              espessura_aresta=max(3, pad//12),
              tam_segmento_pontilhado=3, tam_espaco_pontilhado=6)

    mapa_completo = tab.dicas.copy()

    # Puzzle: so as dicas, sem o caminho
    tab.dicas = puzzle.astype(float)
    img_p = plota.gera_imagem(tab, plota_caminho=False, **kw)
    cv2.imwrite(nome + "_puzzle.png", cv2.cvtColor(img_p, cv2.COLOR_RGB2BGR))

    # Solucao: dicas + o laco
    img_s = plota.gera_imagem(tab, plota_caminho=True, **kw)
    cv2.imwrite(nome + "_solucao.png", cv2.cvtColor(img_s, cv2.COLOR_RGB2BGR))

    tab.dicas = mapa_completo
    sim = " | simetrico" if simetria else ""
    print(f"{nome}: {lin}x{col} | {n_dicas}/{tot} dicas | {dif}{sim}"
          f" | {dt:.1f} s")


salva_par("amostra_8x8",   8,  8,  0.7, 101)
salva_par("amostra_10x10", 10, 10, 1.0, 202, simetria=True)
salva_par("amostra_12x12", 12, 12, 0.55, 303)
print("imagens geradas")
