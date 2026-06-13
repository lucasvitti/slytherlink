# -*- coding: utf-8 -*-
"""Testes e benchmark dos geradores do slitherlink."""
import time

import numpy as np
import networkx as nx
import cv2

import main as sl
import gerador as ger
import plota


def valida_ciclo(tab, fechado=True):
    """Valida que o caminho do tabuleiro é um único ciclo simples."""
    visitados = [v for v in tab.G.nodes if tab.G.degree(v) > 0]
    graus = [tab.G.degree(v) for v in visitados]
    assert all(g == 2 for g in graus), f"graus != 2 encontrados: {set(graus)}"
    sub = tab.G.subgraph(visitados)
    n_comp = nx.number_connected_components(sub)
    assert n_comp == 1, f"{n_comp} componentes (deveria ser 1 ciclo)"
    assert sub.number_of_edges() == len(visitados), "nao e um ciclo"
    return len(visitados)


print("=" * 70)
print("1) Ciclo hamiltoniano 20x20 (densidade alvo 1.0)")
t0 = time.perf_counter()
d, tab, passeio = ger.gera_Tabuleiro2(densidade=1.0, lin=20, col=20, seed=42)
t1 = time.perf_counter()
n_vert = valida_ciclo(tab)
print(f"   densidade obtida = {d:.4f} | vertices no ciclo = {n_vert}/400"
      f" | tempo = {(t1-t0)*1000:.1f} ms")
assert n_vert == 400 and abs(d - 1.0) < 1e-9

print("2) Regiao aleatoria 20x20 (densidade alvo 0.6)")
t0 = time.perf_counter()
d2, tab2, passeio2 = ger.gera_Tabuleiro2(densidade=0.6, lin=20, col=20, seed=7)
t1 = time.perf_counter()
n_vert2 = valida_ciclo(tab2)
print(f"   densidade obtida = {d2:.4f} | vertices no ciclo = {n_vert2}/400"
      f" | tempo = {(t1-t0)*1000:.1f} ms")

print("3) Regiao aleatoria 20x20 (densidade alvo 0.3)")
t0 = time.perf_counter()
d3, tab3, _ = ger.gera_Tabuleiro2(densidade=0.3, lin=20, col=20, seed=7)
t1 = time.perf_counter()
n_vert3 = valida_ciclo(tab3)
print(f"   densidade obtida = {d3:.4f} | vertices no ciclo = {n_vert3}/400"
      f" | tempo = {(t1-t0)*1000:.1f} ms")

print("4) Hamiltoniano em varios tamanhos")
for dim in (4, 10, 30, 50):
    t0 = time.perf_counter()
    dh, tabh, _ = ger.gera_Tabuleiro2(densidade=1.0, lin=dim, col=dim, dicas=False)
    t1 = time.perf_counter()
    nh = valida_ciclo(tabh)
    assert nh == dim * dim
    print(f"   {dim}x{dim}: densidade = {dh:.3f} | tempo = {(t1-t0)*1000:.1f} ms")

print("5) Benchmark: gerador antigo (passeio aleatorio) 20x20")
np.random.seed(0)
t0 = time.perf_counter()
d_old, tab_old, _ = ger.gera_Tabuleiro(densidade=0.6, lin=20, col=20,
                                       max_tentativas=200)
t1 = time.perf_counter()
dens_real = len(set(tab_old.caminho)) / tab_old.numero_vertices
print(f"   alvo 0.6 com 200 tentativas: densidade obtida = {dens_real:.4f}"
      f" | tempo = {t1-t0:.1f} s")

print("6) Imagens de verificacao")
img1 = plota.gera_imagem(tab, pad=50, raio_vertice=5, escala_fonte=0.7,
                         espessura_fonte=1)
cv2.imwrite("ham_20x20.png", cv2.cvtColor(img1, cv2.COLOR_RGB2BGR))
img2 = plota.gera_imagem(tab2, pad=50, raio_vertice=5, escala_fonte=0.7,
                         espessura_fonte=1)
cv2.imwrite("regiao_20x20.png", cv2.cvtColor(img2, cv2.COLOR_RGB2BGR))
img3 = plota.gera_imagem(tab_old, pad=50, raio_vertice=5, escala_fonte=0.7,
                         espessura_fonte=1)
cv2.imwrite("antigo_20x20.png", cv2.cvtColor(img3, cv2.COLOR_RGB2BGR))
print("   ham_20x20.png / regiao_20x20.png / antigo_20x20.png gravadas")

print("OK - todos os testes passaram")
