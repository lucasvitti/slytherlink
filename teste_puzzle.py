# -*- coding: utf-8 -*-
"""Testes do solver e da geração de puzzles (redução de dicas)."""
import time

import numpy as np
import cv2

import gerador as ger
import solver as sv
import plota


print("=" * 70)
print("1) Solver no mapa completo de dicas")
for nome, dens, dim, seed in (("hamiltoniano", 1.0, 10, 3),
                              ("regiao 0.6", 0.6, 10, 11),
                              ("hamiltoniano", 1.0, 14, 5)):
    _, tab, _ = ger.gera_Tabuleiro2(densidade=dens, lin=dim, col=dim, seed=seed)
    alvo = sv.arestas_do_tabuleiro(tab)
    t0 = time.perf_counter()
    n, sols = sv.Solver(dim, dim, tab.dicas.astype(int)).conta_solucoes(limite=2)
    t1 = time.perf_counter()
    assert n == 1, f"esperava 1 solucao, achei {n}"
    assert sols[0] == alvo, "solucao difere do laco gerado"
    print(f"   {dim}x{dim} {nome}: unica e igual ao laco | {(t1-t0)*1000:.0f} ms")

print("2) reduz_dicas em 10x10 (densidade 0.6)")
np.random.seed(20)
_, tab2, _ = ger.gera_Tabuleiro2(densidade=0.6, lin=10, col=10, seed=11)
n_total = (10-1)*(10-1)
t0 = time.perf_counter()
puzzle = ger.reduz_dicas(tab2)
t1 = time.perf_counter()
n_fim = int((puzzle >= 0).sum())
# verificacao independente de unicidade
n, sols = sv.Solver(10, 10, puzzle).conta_solucoes(limite=2)
assert n == 1 and sols[0] == sv.arestas_do_tabuleiro(tab2)
dif = sv.avalia_dificuldade(10, 10, puzzle)
print(f"   dicas: {n_total} -> {n_fim} | unica: sim | dificuldade: {dif}"
      f" | tempo: {t1-t0:.1f} s")

print("3) Minimalidade local: nenhuma dica restante pode sair")
necessarias = 0
for l, c in np.argwhere(puzzle >= 0):
    backup = puzzle[l, c]
    puzzle[l, c] = -1
    n, _ = sv.Solver(10, 10, puzzle).conta_solucoes(limite=2)
    puzzle[l, c] = backup
    assert n == 2, f"dica ({l},{c}) era redundante"
    necessarias += 1
print(f"   todas as {necessarias} dicas sao necessarias")

print("4) Pipeline completo 10x10 hamiltoniano (gera_Puzzle)")
t0 = time.perf_counter()
tab3, puzzle3, dif3 = ger.gera_Puzzle(densidade=1.0, lin=10, col=10, seed=77)
t1 = time.perf_counter()
n, sols = sv.Solver(10, 10, puzzle3).conta_solucoes(limite=2)
assert n == 1 and sols[0] == sv.arestas_do_tabuleiro(tab3)
print(f"   dicas: 81 -> {int((puzzle3 >= 0).sum())} | dificuldade: {dif3}"
      f" | tempo: {t1-t0:.1f} s")

print("5) Pipeline com simetria 180 graus")
t0 = time.perf_counter()
tab4, puzzle4, dif4 = ger.gera_Puzzle(densidade=1.0, lin=10, col=10, seed=78,
                                      simetria=True)
t1 = time.perf_counter()
n, _ = sv.Solver(10, 10, puzzle4).conta_solucoes(limite=2)
assert n == 1
# checa a simetria
m = puzzle4 >= 0
assert np.array_equal(m, m[::-1, ::-1]), "padrao de dicas nao e simetrico"
print(f"   dicas: 81 -> {int((puzzle4 >= 0).sum())} | simetrico: sim"
      f" | dificuldade: {dif4} | tempo: {t1-t0:.1f} s")

print("6) Tamanho de jogo: 14x14 (densidade 0.5)")
t0 = time.perf_counter()
tab5, puzzle5, dif5 = ger.gera_Puzzle(densidade=0.5, lin=14, col=14, seed=99)
t1 = time.perf_counter()
# Verificacao independente com CP-SAT: puzzles minimais de 14x14 ja sao
# instancias dificeis demais para o solver puro-Python verificar
import solver_cpsat as sc
s = sc.SolverCpSat(14, 14, puzzle5, tempo_max=600)
n, sols = s.conta_solucoes(limite=2)
assert n == 1 and s.completa and sols[0] == sv.arestas_do_tabuleiro(tab5)
print(f"   dicas: {13*13} -> {int((puzzle5 >= 0).sum())} | dificuldade: {dif5}"
      f" | tempo: {t1-t0:.1f} s")

print("7) Imagens: puzzle (so dicas) e solucao")
dicas_completas = tab3.dicas.copy()
tab3.dicas = puzzle3.astype(float)
img_p = plota.gera_imagem(tab3, plota_caminho=False, pad=60, raio_vertice=5,
                          escala_fonte=0.9, espessura_fonte=2)
cv2.imwrite("puzzle_10x10.png", cv2.cvtColor(img_p, cv2.COLOR_RGB2BGR))
img_s = plota.gera_imagem(tab3, plota_caminho=True, pad=60, raio_vertice=5,
                          escala_fonte=0.9, espessura_fonte=2)
cv2.imwrite("puzzle_10x10_solucao.png", cv2.cvtColor(img_s, cv2.COLOR_RGB2BGR))
tab3.dicas = dicas_completas
print("   puzzle_10x10.png / puzzle_10x10_solucao.png gravadas")

print("OK - todos os testes passaram")
