# -*- coding: utf-8 -*-
"""Exemplo mínimo: cria um tabuleiro de Slitherlink e o resolve.

Roda de QUALQUER pasta:  python caminho/para/exemplo_resolve.py
Em notebook/Spyder, antes dos imports use:
    import os
    os.chdir(r'C:\\Users\\lucas\\OneDrive\\Desktop\\claude_wksp\\slitherlink')
"""
import os
import sys

# layout plano (gerador/solver/main): garante a pasta do projeto no sys.path
# e entra nela (saídas relativas caem aqui). Como script já funciona de fora,
# isto só reforça e também serve quando o arquivo é importado de outro lugar.
_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
os.chdir(_AQUI)

import gerador as ger
import solver as sv


# 1) CRIA o puzzle: laço aleatório + dicas reduzidas (escolhe método/dificuldade)
tab, puzzle, dificuldade = ger.gera_Puzzle(
    lin=8, col=8,            # 8x8 vértices -> 7x7 células
    densidade=0.6, seed=42,
    metodo='guloso',         # 'guloso' | 'binaria' | 'cegar'
    dificuldade='medio',     # 'facil' | 'medio' | 'dificil'
)
lin, col = tab.lin, tab.col

# 2) RESOLVE com a busca esperta (padrões fixos já vêm ligados em Solver)
n, solucoes = sv.Solver(lin, col, puzzle).conta_solucoes(limite=1)
solucao = solucoes[0]
assert solucao == sv.arestas_do_tabuleiro(tab)   # confere com o laço gerado


def render(lin, col, clues, sol):
    """Desenha o tabuleiro em ASCII: dicas + arestas do conjunto `sol`."""
    H = lambda l, c: sv.id_aresta_horizontal(l, c, col)
    V = lambda l, c: sv.id_aresta_vertical(l, c, lin, col)
    linhas = []
    for l in range(lin):
        s = '·'                                   # linha de pontos + horizontais
        for c in range(col - 1):
            s += ('───' if H(l, c) in sol else '   ') + '·'
        linhas.append(s)
        if l < lin - 1:                           # linha de verticais + dicas
            s = ''
            for c in range(col):
                s += '│' if V(l, c) in sol else ' '
                if c < col - 1:
                    k = int(clues[l][c])
                    s += ' %s ' % (k if k >= 0 else ' ')
            linhas.append(s)
    return '\n'.join(linhas)


print('Puzzle %dx%d células | dificuldade=%s | %d dicas | %d solução(ões)'
      % (lin - 1, col - 1, dificuldade, int((puzzle >= 0).sum()), n))
print('\nPUZZLE (só dicas):\n')
print(render(lin, col, puzzle, frozenset()))
print('\nSOLUÇÃO:\n')
print(render(lin, col, puzzle, solucao))
