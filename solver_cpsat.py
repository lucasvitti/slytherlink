# -*- coding: utf-8 -*-
"""
Oráculo de unicidade via OR-Tools CP-SAT (opcional, muito mais rápido que
o solver puro-Python para tabuleiros grandes).

Modela cada aresta como uma variável booleana com as restrições lineares
das dicas das células. A restrição de laço ÚNICO usa AddCircuit, a
restrição nativa de circuito do CP-SAT: cada aresta vira dois arcos
direcionados (um literal por sentido) e cada vértice ganha um arco-laço
("self-loop") que o marca como fora do circuito. O AddCircuit exige
exatamente um circuito cobrindo os vértices não pulados -- exatamente a
regra do Slitherlink, sem eliminação preguiçosa de subciclos.

A interface (conta_solucoes, num_solucoes, solucoes, completa) é compatível
com slitherlink.solver.Solver, usando a mesma enumeração de arestas, para
servir de substituto direto em gerador.reduz_dicas().

Requer: pip install ortools
"""

import time

import numpy as np
from ortools.sat.python import cp_model

from solver import id_aresta_horizontal, id_aresta_vertical


class SolverCpSat:
    """
    Conta soluções de um puzzle de Slitherlink com CP-SAT.

    Parameters
    ----------
    lin, col : int
        Dimensões do tabuleiro (em vértices).
    dicas : matriz (lin-1)x(col-1)
        Valores 0 a 3 são dicas; valores negativos indicam célula sem dica.
    max_nos : int, optional
        Ignorado (existe por compatibilidade com solver.Solver).
    tempo_max : float, optional
        Tempo máximo total (em segundos) por chamada de conta_solucoes.
        Se estourar, self.completa fica False (resultado inconclusivo).
    solucao_hint : conjunto de ids de arestas, optional
        Solução conhecida do puzzle (o laço alvo). Usada como palpite
        inicial (hint) do CP-SAT: a primeira solução é encontrada
        imediatamente e o custo da chamada vira só a prova de unicidade.
    trabalhadores : int, optional
        Número de threads de busca do CP-SAT. Padrão 8. Com mais de um
        trabalhador o resultado deixa de ser determinístico (a solução
        alternativa encontrada pode variar entre execuções).
    """

    def __init__(self, lin, col, dicas, max_nos=None, tempo_max=60.0,
                 solucao_hint=None, trabalhadores=8):
        self.lin = lin
        self.col = col
        self.tempo_max = tempo_max
        self.trabalhadores = trabalhadores
        dicas = np.asarray(dicas).astype(int)

        nH = lin*(col-1)
        nE = nH + (lin-1)*col
        self.nE = nE

        # Vértices por aresta (mesma enumeração do solver puro-Python)
        vertices_aresta = [None]*nE
        for l in range(lin):
            for c in range(col-1):
                vertices_aresta[l*(col-1) + c] = (l*col + c, l*col + c + 1)
        for l in range(lin-1):
            for c in range(col):
                vertices_aresta[nH + l*col + c] = (l*col + c, (l+1)*col + c)
        self.vertices_aresta = vertices_aresta

        m = cp_model.CpModel()
        x = [m.NewBoolVar('e{}'.format(i)) for i in range(nE)]

        # Um circuito único: cada aresta vira dois arcos direcionados e
        # cada vértice tem um arco-laço que o tira do circuito
        arcos = []
        for e, (v1, v2) in enumerate(vertices_aresta):
            ida = m.NewBoolVar('a{}_'.format(e))
            volta = m.NewBoolVar('a_{}'.format(e))
            arcos.append((v1, v2, ida))
            arcos.append((v2, v1, volta))
            # A aresta está no laço se é usada em um dos dois sentidos
            m.Add(x[e] == ida + volta)
        for v in range(lin*col):
            fora = m.NewBoolVar('s{}'.format(v))
            arcos.append((v, v, fora))
        m.AddCircuit(arcos)

        # Dicas das células
        for l in range(lin-1):
            for c in range(col-1):
                k = dicas[l, c]
                if k < 0:
                    continue
                quatro = [id_aresta_horizontal(l, c, col)
                          ,id_aresta_horizontal(l+1, c, col)
                          ,id_aresta_vertical(l, c, lin, col)
                          ,id_aresta_vertical(l, c+1, lin, col)]
                m.Add(sum(x[e] for e in quatro) == k)

        # O laço é obrigatório (o menor ciclo do grid tem 4 arestas)
        m.Add(sum(x) >= 4)

        # Restrições redundantes (implícitas no circuito, mas fortalecem
        # a propagação do CP-SAT em tabuleiros com poucas dicas):
        # 1) grau de cada vértice: 0 ou 2
        arestas_vertice = [[] for _ in range(lin*col)]
        for e, (v1, v2) in enumerate(vertices_aresta):
            arestas_vertice[v1].append(e)
            arestas_vertice[v2].append(e)
        for v, lst in enumerate(arestas_vertice):
            usa = m.NewBoolVar('g{}'.format(v))
            m.Add(sum(x[e] for e in lst) == 2*usa)
        # 2) paridade dos cortes: o laço cruza cada linha do grid um
        # número par de vezes (curva de Jordan)
        for c in range(col-1):
            cruzam = [l*(col-1) + c for l in range(lin)]
            meio = m.NewIntVar(0, lin//2, 'pc{}'.format(c))
            m.Add(sum(x[e] for e in cruzam) == 2*meio)
        for l in range(lin-1):
            cruzam = [nH + l*col + c for c in range(col)]
            meio = m.NewIntVar(0, col//2, 'pl{}'.format(l))
            m.Add(sum(x[e] for e in cruzam) == 2*meio)

        # Palpite inicial: a solução conhecida (se fornecida)
        if solucao_hint is not None:
            for e in range(nE):
                m.AddHint(x[e], 1 if e in solucao_hint else 0)

        self.modelo = m
        self.x = x
        self.num_solucoes = 0
        self.solucoes = []
        self.completa = True

    def conta_solucoes(self, limite=2):
        """
        Conta as soluções do puzzle, parando ao atingir o limite.
        Mesma interface de solver.Solver.conta_solucoes().
        """
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = self.trabalhadores
        solver.parameters.random_seed = 0

        t0 = time.monotonic()
        while self.num_solucoes < limite:
            restante = self.tempo_max - (time.monotonic() - t0)
            if restante <= 0:
                self.completa = False
                break
            solver.parameters.max_time_in_seconds = restante

            status = solver.Solve(self.modelo)
            if status == cp_model.INFEASIBLE:
                break   # não há mais soluções: contagem completa
            if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                self.completa = False
                break

            sol = frozenset(e for e in range(self.nE)
                            if solver.Value(self.x[e]))
            self.solucoes.append(sol)
            self.num_solucoes += 1
            # Bloqueia esta solução: nenhum outro ciclo simples pode
            # conter todas as arestas dela
            self.modelo.Add(sum(self.x[e] for e in sol) <= len(sol) - 1)

        return self.num_solucoes, self.solucoes
