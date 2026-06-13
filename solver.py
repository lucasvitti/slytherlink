# -*- coding: utf-8 -*-
"""
Solver de Slitherlink por propagação de restrições e backtracking.

O estado de cada aresta do tabuleiro é DESCONHECIDA, DENTRO (faz parte do
laço) ou FORA. O solver propaga três famílias de regras:

  - grau dos vértices: todo vértice tem grau 0 ou 2 no laço;
  - dicas das células: célula com dica k tem exatamente k arestas no laço;
  - paridade dos cortes: um laço fechado cruza qualquer linha do grid um
    número PAR de vezes (teorema da curva de Jordan), então cada corte
    vertical/horizontal do tabuleiro tem um número par de arestas DENTRO;
  - laço único: fechar um ciclo só é permitido se ele completa a solução
    (todas as dicas satisfeitas exatamente e nenhuma aresta do laço fora
    do ciclo fechado).

Há ainda uma poda de conectividade na busca: fragmentos de caminho que
não podem mais se conectar entre si por arestas não descartadas matam
o ramo.

Quando a propagação trava, a busca ramifica em uma aresta (de preferência
na ponta de um caminho aberto) e conta soluções até o limite pedido.
conta_solucoes(limite=2) é o oráculo de unicidade usado por
gerador.reduz_dicas().

Enumeração das arestas (lin x col vértices):
  - horizontais (l,c)-(l,c+1): id = l*(col-1) + c
  - verticais   (l,c)-(l+1,c): id = lin*(col-1) + l*col + c
"""

import numpy as np

DESCONHECIDA = 0
DENTRO = 1
FORA = 2

_VERTICE = 0
_CELULA = 1
_CORTE = 2


def id_aresta_horizontal(l, c, col):
    """Id da aresta entre os vértices (l,c) e (l,c+1)."""
    return l*(col-1) + c


def id_aresta_vertical(l, c, lin, col):
    """Id da aresta entre os vértices (l,c) e (l+1,c)."""
    return lin*(col-1) + l*col + c


def arestas_do_tabuleiro(tabuleiro):
    """
    Conjunto (frozenset) com os ids das arestas do caminho do tabuleiro,
    na enumeração usada pelo Solver.
    """
    lin, col = tabuleiro.lin, tabuleiro.col
    arestas = set()
    for a, b in tabuleiro.G.edges:
        if a.l == b.l:
            arestas.add(id_aresta_horizontal(a.l, min(a.c, b.c), col))
        else:
            arestas.add(id_aresta_vertical(min(a.l, b.l), a.c, lin, col))
    return frozenset(arestas)


def dicas_de_solucao(lin, col, solucao):
    """
    Matriz de dicas (lin-1)x(col-1) induzida por um conjunto de arestas
    (ids na enumeração do Solver).
    """
    dicas = np.zeros((lin-1, col-1), dtype=int)
    for l in range(lin-1):
        for c in range(col-1):
            n = 0
            n += id_aresta_horizontal(l, c, col) in solucao
            n += id_aresta_horizontal(l+1, c, col) in solucao
            n += id_aresta_vertical(l, c, lin, col) in solucao
            n += id_aresta_vertical(l, c+1, lin, col) in solucao
            dicas[l, c] = n
    return dicas


class Solver:
    """
    Solver para um tabuleiro lin x col com a matriz de dicas informada.

    A matriz de dicas tem dimensão (lin-1)x(col-1); valores de 0 a 3 são
    dicas e valores negativos indicam célula sem dica.

    Cada instância serve para uma única chamada de conta_solucoes() ou
    resolve() -- o estado interno não é reiniciado entre chamadas.
    """

    def __init__(self, lin, col, dicas, max_nos=60000):
        self.lin = lin
        self.col = col
        self.max_nos = max_nos
        dicas = np.asarray(dicas).astype(int)

        nH = lin*(col-1)
        nE = nH + (lin-1)*col
        nv = lin*col
        self.nE = nE

        # Estrutura do grafo: arestas por vértice e vértices por aresta
        arestas_vertice = [[] for _ in range(nv)]
        vertices_aresta = [None]*nE
        for l in range(lin):
            for c in range(col-1):
                e = l*(col-1) + c
                v1, v2 = l*col + c, l*col + c + 1
                arestas_vertice[v1].append(e)
                arestas_vertice[v2].append(e)
                vertices_aresta[e] = (v1, v2)
        for l in range(lin-1):
            for c in range(col):
                e = nH + l*col + c
                v1, v2 = l*col + c, (l+1)*col + c
                arestas_vertice[v1].append(e)
                arestas_vertice[v2].append(e)
                vertices_aresta[e] = (v1, v2)
        self.arestas_vertice = arestas_vertice
        self.vertices_aresta = vertices_aresta

        # Células com dica
        n_cel = (lin-1)*(col-1)
        self.dica_celula = [-1]*n_cel
        self.arestas_celula = [None]*n_cel
        self.celulas_aresta = [[] for _ in range(nE)]
        self.ids_celulas = []
        for l in range(lin-1):
            for c in range(col-1):
                k = dicas[l, c]
                if k < 0:
                    continue
                cel = l*(col-1) + c
                quatro = [id_aresta_horizontal(l, c, col)
                          ,id_aresta_horizontal(l+1, c, col)
                          ,id_aresta_vertical(l, c, lin, col)
                          ,id_aresta_vertical(l, c+1, lin, col)]
                self.dica_celula[cel] = k
                self.arestas_celula[cel] = quatro
                self.ids_celulas.append(cel)
                for e in quatro:
                    self.celulas_aresta[e].append(cel)

        # Cortes do tabuleiro: o corte vertical c é cruzado pelas arestas
        # horizontais (l,c)-(l,c+1); o corte horizontal l é cruzado pelas
        # arestas verticais (l,c)-(l+1,c). Pela paridade da curva fechada,
        # cada corte tem um número par de arestas DENTRO
        n_cortes = (col-1) + (lin-1)
        self.corte_aresta = [0]*nE
        self.arestas_corte = [[] for _ in range(n_cortes)]
        for l in range(lin):
            for c in range(col-1):
                e = l*(col-1) + c
                self.corte_aresta[e] = c
                self.arestas_corte[c].append(e)
        for l in range(lin-1):
            for c in range(col):
                e = nH + l*col + c
                ct = (col-1) + l
                self.corte_aresta[e] = ct
                self.arestas_corte[ct].append(e)
        self.in_corte = [0]*n_cortes
        self.unk_corte = [len(self.arestas_corte[ct])
                          for ct in range(n_cortes)]

        # Estado da busca
        self.estado = [DESCONHECIDA]*nE
        self.in_v = [0]*nv
        self.unk_v = [len(arestas_vertice[v]) for v in range(nv)]
        self.in_c = [0]*n_cel
        self.unk_c = [4]*n_cel
        self.pontas = set()        # vértices com grau 1 (pontas de caminho)
        self.total_in = 0
        self.n_dicas = len(self.ids_celulas)
        self.n_sat = sum(1 for cel in self.ids_celulas
                         if self.dica_celula[cel] == 0)

        # União-busca dos componentes ligados por arestas DENTRO
        self.pai = list(range(nv))
        self.tam = [1]*nv

        # Trilhas para desfazer atribuições no backtracking
        self.trilha = []
        self.trilha_uf = []
        self.fila = []

        self.num_solucoes = 0
        self.solucoes = []
        self.nos = 0
        self.completa = True   # False se a busca estourou max_nos

    def _find(self, x):
        pai = self.pai
        while pai[x] != x:
            x = pai[x]
        return x

    def _set(self, e, valor):
        """
        Atribui um valor a uma aresta, atualizando contadores e agendando
        a repropagação dos vértices e células afetados. Retorna False em
        contradição (inclusive quando um ciclo é fechado: se o ciclo
        completa uma solução válida, ela é registrada antes de retornar).
        """
        est = self.estado[e]
        if est != DESCONHECIDA:
            return est == valor
        self.estado[e] = valor
        self.trilha.append(e)

        v1, v2 = self.vertices_aresta[e]
        fila = self.fila
        self.unk_v[v1] -= 1
        self.unk_v[v2] -= 1
        fila.append((_VERTICE, v1))
        fila.append((_VERTICE, v2))
        for cel in self.celulas_aresta[e]:
            self.unk_c[cel] -= 1
            fila.append((_CELULA, cel))
        corte = self.corte_aresta[e]
        self.unk_corte[corte] -= 1
        fila.append((_CORTE, corte))

        if valor == FORA:
            return True

        # valor == DENTRO
        self.in_corte[corte] += 1
        contradicao = False
        self.total_in += 1
        for v in (v1, v2):
            iv = self.in_v[v] + 1
            self.in_v[v] = iv
            if iv == 1:
                self.pontas.add(v)
            elif iv == 2:
                self.pontas.discard(v)
            else:
                contradicao = True
        for cel in self.celulas_aresta[e]:
            ic = self.in_c[cel] + 1
            self.in_c[cel] = ic
            k = self.dica_celula[cel]
            if ic == k:
                self.n_sat += 1
            elif ic == k + 1:
                self.n_sat -= 1
            if ic > k:
                contradicao = True
        if contradicao:
            return False

        r1, r2 = self._find(v1), self._find(v2)
        if r1 == r2:
            # Fechou um ciclo. É solução se e somente se todas as dicas
            # estão exatamente satisfeitas e não existe nenhuma aresta
            # DENTRO fora deste componente (componente com graus <= 2 e
            # um ciclo é, necessariamente, um ciclo simples)
            if self.total_in == self.tam[r1] and self.n_sat == self.n_dicas:
                self.num_solucoes += 1
                estado = self.estado
                self.solucoes.append(frozenset(
                    i for i in range(self.nE) if estado[i] == DENTRO))
            return False
        if self.tam[r1] < self.tam[r2]:
            r1, r2 = r2, r1
        self.pai[r2] = r1
        self.tam[r1] += self.tam[r2]
        self.trilha_uf.append((r2, r1))
        return True

    def _desfaz(self, marca):
        """Desfaz todas as atribuições feitas depois da marca."""
        m_e, m_uf = marca
        while len(self.trilha_uf) > m_uf:
            r2, r1 = self.trilha_uf.pop()
            self.tam[r1] -= self.tam[r2]
            self.pai[r2] = r2
        while len(self.trilha) > m_e:
            e = self.trilha.pop()
            valor = self.estado[e]
            self.estado[e] = DESCONHECIDA
            v1, v2 = self.vertices_aresta[e]
            self.unk_v[v1] += 1
            self.unk_v[v2] += 1
            for cel in self.celulas_aresta[e]:
                self.unk_c[cel] += 1
            self.unk_corte[self.corte_aresta[e]] += 1
            if valor == DENTRO:
                self.in_corte[self.corte_aresta[e]] -= 1
                self.total_in -= 1
                for v in (v1, v2):
                    iv = self.in_v[v] - 1
                    self.in_v[v] = iv
                    if iv == 1:
                        self.pontas.add(v)
                    elif iv == 0:
                        self.pontas.discard(v)
                for cel in self.celulas_aresta[e]:
                    ic = self.in_c[cel] - 1
                    self.in_c[cel] = ic
                    k = self.dica_celula[cel]
                    if ic == k:
                        self.n_sat += 1
                    elif ic == k - 1:
                        self.n_sat -= 1

    def _regra_vertice(self, v):
        iv = self.in_v[v]
        uv = self.unk_v[v]
        if iv > 2:
            return False
        if iv == 2:
            if uv:
                for e in self.arestas_vertice[v]:
                    if self.estado[e] == DESCONHECIDA and not self._set(e, FORA):
                        return False
        elif iv == 1:
            if uv == 0:
                return False
            if uv == 1:
                for e in self.arestas_vertice[v]:
                    if self.estado[e] == DESCONHECIDA:
                        return self._set(e, DENTRO)
        else:  # iv == 0
            if uv == 1:
                for e in self.arestas_vertice[v]:
                    if self.estado[e] == DESCONHECIDA:
                        return self._set(e, FORA)
        return True

    def _regra_celula(self, cel):
        ic = self.in_c[cel]
        uc = self.unk_c[cel]
        k = self.dica_celula[cel]
        if ic > k or ic + uc < k:
            return False
        if uc == 0:
            return True
        if ic == k:
            for e in self.arestas_celula[cel]:
                if self.estado[e] == DESCONHECIDA and not self._set(e, FORA):
                    return False
        elif ic + uc == k:
            for e in self.arestas_celula[cel]:
                if self.estado[e] == DESCONHECIDA and not self._set(e, DENTRO):
                    return False
        return True

    def _regra_corte(self, ct):
        # Paridade: o laço cruza cada corte um número par de vezes
        uc = self.unk_corte[ct]
        if uc > 1:
            return True
        impar = self.in_corte[ct] % 2 == 1
        if uc == 0:
            return not impar
        # Resta uma aresta desconhecida no corte: a paridade decide
        valor = DENTRO if impar else FORA
        estado = self.estado
        for e in self.arestas_corte[ct]:
            if estado[e] == DESCONHECIDA:
                return self._set(e, valor)
        return True

    def _propaga(self):
        """Propaga as regras até o ponto fixo. False em contradição."""
        fila = self.fila
        while fila:
            tipo, x = fila.pop()
            if tipo == _VERTICE:
                ok = self._regra_vertice(x)
            elif tipo == _CELULA:
                ok = self._regra_celula(x)
            else:
                ok = self._regra_corte(x)
            if not ok:
                fila.clear()
                return False
        return True

    def _conectavel(self):
        """
        Poda por conectividade: para formar um laço único, todos os
        fragmentos de caminho (arestas DENTRO) precisam ser conectáveis
        entre si por arestas ainda não descartadas (não-FORA). Se algum
        fragmento ficou isolado dos demais por uma parede de arestas FORA,
        o ramo não tem solução.

        Assume o ponto fixo da propagação: arestas desconhecidas nunca
        tocam vértices de grau 2, então o BFS por arestas não-FORA só
        atravessa vértices com capacidade disponível.
        """
        if len(self.pontas) <= 2:
            # Zero ou um fragmento: a conectividade é trivial, não paga
            # o custo do BFS
            return True
        estado = self.estado
        arestas_vertice = self.arestas_vertice
        vertices_aresta = self.vertices_aresta
        inicio = next(iter(self.pontas))
        visitado = [False]*(self.lin*self.col)
        visitado[inicio] = True
        pilha = [inicio]
        while pilha:
            v = pilha.pop()
            for e in arestas_vertice[v]:
                if estado[e] == FORA:
                    continue
                v1, v2 = vertices_aresta[e]
                w = v2 if v1 == v else v1
                if not visitado[w]:
                    visitado[w] = True
                    pilha.append(w)
        in_v = self.in_v
        for v in range(self.lin*self.col):
            if in_v[v] and not visitado[v]:
                return False
        return True

    def _escolhe_aresta(self):
        """
        Escolhe a aresta desconhecida para ramificar: primeiro nas pontas
        de caminhos abertos, depois nas células com dica não resolvida,
        por fim qualquer aresta desconhecida.
        """
        estado = self.estado
        for v in self.pontas:
            for e in self.arestas_vertice[v]:
                if estado[e] == DESCONHECIDA:
                    return e
        for cel in self.ids_celulas:
            if self.unk_c[cel]:
                for e in self.arestas_celula[cel]:
                    if estado[e] == DESCONHECIDA:
                        return e
        for e in range(self.nE):
            if estado[e] == DESCONHECIDA:
                return e
        return None

    def _busca(self, limite):
        if self.num_solucoes >= limite or not self.completa:
            return
        self.nos += 1
        if self.nos > self.max_nos:
            # Orçamento de busca estourado: o resultado é inconclusivo
            self.completa = False
            return
        if not self._conectavel():
            return
        e = self._escolhe_aresta()
        if e is None:
            # Tudo atribuído sem fechar ciclo: não é solução (o laço é
            # obrigatório), apenas retorna
            return
        for valor in (DENTRO, FORA):
            marca = (len(self.trilha), len(self.trilha_uf))
            ok = self._set(e, valor)
            if ok:
                ok = self._propaga()
            else:
                self.fila.clear()
            if ok:
                self._busca(limite)
            self._desfaz(marca)
            if self.num_solucoes >= limite or not self.completa:
                return

    def conta_solucoes(self, limite=2):
        """
        Conta as soluções do puzzle, parando ao atingir o limite.

        Parameters
        ----------
        limite : int, optional
            Número máximo de soluções a procurar. Padrão 2, suficiente
            para o teste de unicidade.

        Returns
        -------
        Tupla (n, solucoes): n é o número de soluções encontradas (até o
        limite) e solucoes é a lista dos conjuntos de ids de arestas de
        cada solução.
        """
        self.fila.extend((_CELULA, cel) for cel in self.ids_celulas)
        if self._propaga():
            self._busca(limite)
        return self.num_solucoes, self.solucoes

    def resolve(self, profundidade=0):
        """
        Tenta resolver o puzzle com técnicas de dedução limitadas, sem
        busca completa. Usado para graduar a dificuldade do puzzle.

        Parameters
        ----------
        profundidade : int, optional
            0: apenas propagação das regras locais.
            1: propagação + teste de contradição de profundidade 1
               (assume um valor para uma aresta; se propagar leva a
               contradição, o valor oposto é deduzido).

        Returns
        -------
        bool : True se a solução foi encontrada com as técnicas permitidas.
        """
        self.fila.extend((_CELULA, cel) for cel in self.ids_celulas)
        if not self._propaga():
            return self.num_solucoes > 0
        if profundidade < 1:
            return False

        progresso = True
        while progresso:
            progresso = False
            for e in range(self.nE):
                if self.estado[e] != DESCONHECIDA:
                    continue
                for valor, oposto in ((DENTRO, FORA), (FORA, DENTRO)):
                    marca = (len(self.trilha), len(self.trilha_uf))
                    ok = self._set(e, valor)
                    if ok:
                        ok = self._propaga()
                    else:
                        self.fila.clear()
                    achou = self.num_solucoes > 0
                    self._desfaz(marca)
                    if achou:
                        # O palpite fechou a solução
                        return True
                    if not ok:
                        # O palpite leva a contradição: deduz o oposto
                        if not (self._set(e, oposto) and self._propaga()):
                            self.fila.clear()
                            return self.num_solucoes > 0
                        progresso = True
                        break
                if progresso:
                    break
        return False


def avalia_dificuldade(lin, col, dicas):
    """
    Gradua a dificuldade de um puzzle pela técnica de dedução necessária
    para resolvê-lo:

      - 'facil':   propagação das regras locais resolve sozinha;
      - 'medio':   precisa de testes de contradição de profundidade 1;
      - 'dificil': exige busca com retrocesso mais profunda.

    Assume que o puzzle tem solução única.
    """
    if Solver(lin, col, dicas).resolve(profundidade=0):
        return 'facil'
    if Solver(lin, col, dicas).resolve(profundidade=1):
        return 'medio'
    return 'dificil'
