# -*- coding: utf-8 -*-
"""Testes da busca esperta (padrões fixos) e dos métodos de redução de dicas."""
import time
import numpy as np
import gerador as ger
import solver as sv


def board(dens, dim, seed):
    _, tab, _ = ger.gera_Tabuleiro2(densidade=dens, lin=dim, col=dim, seed=seed)
    return dim, tab.dicas.astype(int), sv.arestas_do_tabuleiro(tab)


print("=" * 64)
print("1) SOUNDNESS: contar com padrões == sem padrões (full + sub-mapas)")
rs = np.random.RandomState(0)
comparacoes = pulados = falhas = 0
for dens, dim, seed in [(0.6, 7, 3), (0.6, 7, 11), (0.6, 8, 5),
                        (1.0, 6, 7), (0.6, 8, 21)]:
    d, alvo, sol = board(dens, dim, seed)
    casos = [alvo]
    for _ in range(6):
        p = alvo.copy()
        p[rs.random_sample(p.shape) < 0.35] = -1   # remove ~35% das dicas
        casos.append(p)
    for p in casos:
        s1 = sv.Solver(d, d, p, max_nos=600000, semear=True)
        n_s, _ = s1.conta_solucoes(limite=2)
        s0 = sv.Solver(d, d, p, max_nos=600000, semear=False)
        n_u, _ = s0.conta_solucoes(limite=2)
        if not (s1.completa and s0.completa):
            pulados += 1
            continue
        comparacoes += 1
        if n_s != n_u:
            falhas += 1
            print("   MISMATCH dim=%d seed=%d: semeado=%d sem=%d" % (d, seed, n_s, n_u))
print("   %d comparações concluídas, %d divergências (%d pulados/inconclusivos)"
      % (comparacoes, falhas, pulados))
assert falhas == 0

print("2) SMART SEARCH: acha a solução, igual ao alvo (+ tempo semeado vs sem)")
for dens, dim, seed in [(0.6, 8, 5), (0.6, 9, 13), (0.6, 10, 7)]:
    d, alvo, sol = board(dens, dim, seed)
    t = time.perf_counter()
    ns, ss = sv.Solver(d, d, alvo, semear=True).conta_solucoes(2)
    ts = time.perf_counter() - t
    t = time.perf_counter()
    nu, _ = sv.Solver(d, d, alvo, semear=False).conta_solucoes(2)
    tu = time.perf_counter() - t
    assert ns == 1 and ss[0] == sol, "solução difere do alvo"
    print("   %dx%d: única e igual | semeado %.0fms  vs  sem padrões %.0fms"
          % (d, d, ts * 1000, tu * 1000))

print("3) REDUÇÃO (métodos do site): guloso / binária / cegar -> única e == alvo")
d, alvo, sol = board(0.6, 8, 5)
n_total = int((alvo >= 0).sum())
for metodo in ('guloso', 'binaria', 'cegar'):
    linha = []
    for dif in ('facil', 'medio', 'dificil'):
        p = ger.reduz_dicas_metodo(metodo, d, d, alvo, sol, dificuldade=dif, seed=1)
        n, ss = sv.Solver(d, d, p, max_nos=600000).conta_solucoes(2)
        assert n == 1 and ss[0] == sol, "%s/%s não é única/igual" % (metodo, dif)
        linha.append("%s=%d" % (dif, int((p >= 0).sum())))
    print("   %-8s (de %d dicas): %s" % (metodo, n_total, "  ".join(linha)))

print("OK - testes passaram")
