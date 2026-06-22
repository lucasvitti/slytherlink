# -*- coding: utf-8 -*-
"""
Created on Sun May 28 08:35:11 2023

@author: lucas
"""

import numpy as np
import networkx as nx
from tqdm import tqdm
import main as sl
import solver as sv


# =============================================================================
# Testa se um vértice do tabuleiro é vizinho do vértice destino
# =============================================================================
def testa_vertice(tabuleiro         : sl.Tabuleiro
                  ,v                : sl.Vertice
                  ,vertice_destino  : sl.Vertice
                  ,caminho_minimo   = 5):
    """
    Testa se um vértice do tabuleiro é vizinho do vértice destino.

    Parameters
    ----------
    v: Vertice
        Vertice sendo testado
    vertice_destino: Vertice
        Vértice destino que o alrogirmo tenta atingir.

    Returns
    -------
    bool
        True se atingiu o destino, False c.c.

    """
    
    if len(tabuleiro.caminho) < caminho_minimo:
        return False
    
    # Valida condições de finalização
    teste_final = [tabuleiro.get_vertice_acima(v)
                   ,tabuleiro.get_vertice_abaixo(v)
                   ,tabuleiro.get_vertice_esquerda(v)
                   ,tabuleiro.get_vertice_direita(v)]

    for t in [t for t in teste_final if t is not None]:
        cond1 = (t == vertice_destino)
        cond2 = (t.visitado == 1)
        cond3 = (not tabuleiro.G.has_edge(v,vertice_destino))
                    
        if cond1 and cond2 and cond3:
            return True
        
    return False



# =============================================================================
# Geração de caminho via passeio aleatório
# =============================================================================
def passeio_aleatorio(tabuleiro         : sl.Tabuleiro
                      ,vertice_origem   : list          = None 
                      ,vertice_destino  : list          = None
                      ,teste1           : bool          = False
                      ,teste2           : bool          = False
                      ,limite_iteracoes : int           = 100):
    """
    Realiza um passeio aleatório pelos vértices do tabuleiro,
    tentando atingir o vértice origem do passeio.
    
    O algoritmo funciona em duas partes: partindo da origem, traça
    um caminho aleatório até encontrar um vértice onde não existem
    mais passos possíveis. Se teste1 = 1 é realizada a checagem da
    condição de parada a cada passo dado no caminho aleatório.
    
    Quando o caminho aleatório encontra um vértice onde não é mais possível
    caminhar, checa se o vértice é adjacente ao vértice de origem (i.e, 
    foi encontrado um caminho fechado). O parâmewtro teste2=1 controla
    a realização ou não do teste de condição de parada nesse momento.
    
    Estando em um vértice sem possibilidade de avanço inicia-se o backtracking
    até que seja encontrado um vértice onde exista a possibilidade de passo
    para outro vértice ainda não visitado. Se teste3 = 1  é realizada a checagem da
    condição de parada a cada passo dado no backtracking.

    Parameters
    ----------
    tabuleiro: Tabuleiro
        Tabuleiro onde será gerado o passeio aleatório. A chamada dessa
        função altera o estado interno do Tabuleiro, fazendo a inclusão/exclusão
        de arestas. Assume-se que o tabuleiro de partida é vazio
    vertice_origem: list
        Lista com dois inteiro representando as coordenadas (col,lin) do vértice de origem 
        para início do passeio aleatório. Se não informado, será sorteado 
        um vértice de forma aleatória. O valor padrão do parâmetro é None
    vertice_destino: list
        Lista com dois inteiro representando as coordenadas (col,lin) do vértice 
        de destino do passeio aleatório. Se não informado, será atribuído
        o vértice de origem. O valor padrão do parâmetro é None
    teste1: bool
        Indica se a condição de parada deve ser validada a cada
        passo de avanço do caminho aleatório. O valor padrão do 
        parâmetro é True
    teste2: bool
        Indica se a condição de parada deve ser validada durante
        a execução do backtracking. Se teste1=True o segundo teste
        não pode ser realizado (para antes de chegar nesse passo).
        O valor padrão do parâmetro é False
    limite_iteracoes : int, optional
        Limite de iterações que o algoritmo de passeio aleatório roda
        sem nenhum movimento (passo dado ou backtracking) antes de parar.
        Valor padrão é 100.

    Returns
    -------
    Retorna uma lista com a sequencia de passos e exclusões no passeio aleatório.
    Os elementos da lista são (v,+1), indicando inclusão do vértice ou
    (v,-1) indicando a exclusão do vértice.

    """
    # Sorteia um ponto de partida, se não foi passado como parâmetro
    if vertice_origem is None:
        vertice_origem = tabuleiro.sorteia_vertice()
    else:
        vertice_origem = tabuleiro.get_verticeXY(vertice_origem[1]
                                                 ,vertice_origem[0])
    
    # Se o vértice destino não foi passado como parâmetro, assume
    # que é o mesmo que o vértice origem
    if vertice_destino is None:
        vertice_destino = vertice_origem
    else:
        vertice_destino = tabuleiro.get_verticeXY(vertice_destino[1]
                                                  ,vertice_destino[0])
    
    vertice_origem.visitado = 1
    vertice_origem.ordem = 1
    v = vertice_origem
    tabuleiro.caminho = [vertice_origem]

    # Marca vértice destino como visitado (necessário para o teste
    # de finalização do algoritmo)
    vertice_destino.visitado = 1

    # Contagem de iterações sem movimento, para critério de parada
    iteracoes_sem_mov = 0
    
    # Flag para parada do algoritmo        
    finalizado = False

    passeio = [(vertice_origem.n,1)]

    while not finalizado:
        
        iteracoes_sem_mov += 1    
        if iteracoes_sem_mov > limite_iteracoes:
            break

        # Busca uma solução com um passeio aleatório em
        # vértices não visitados
        while (True):
            prox_vertice = tabuleiro.sorteia_proximo_vertice(v)
            
            if prox_vertice is None:
                break
        
            # Marca vértice como visitado e atribui ordem
            prox_vertice.visitado = 1
            prox_vertice.ordem = v.ordem + 1
            iteracoes_sem_mov = 0

            tabuleiro.caminho.append(prox_vertice)
            tabuleiro.G.add_edge(v, prox_vertice)
            passeio.append((prox_vertice.n,1))

            v = prox_vertice
            
            # Valida condições de finalização, dentro do algoritmo
            # de avanço do passeio aleatório
            if testa_vertice(tabuleiro,v,vertice_destino) and teste1:
                break


        # Valida condições de finalização
        if testa_vertice(tabuleiro,v,vertice_destino):
            tabuleiro.G.add_edge(v,vertice_destino)
            tabuleiro.caminho.append(vertice_destino)
            finalizado = True
            break

        # Faz o backtracking até encontrar um vértice viável 
        # para continuar o passeio aleatório
        backtracking = True 
        while backtracking:
            if len(tabuleiro.caminho) < 2:
                backtracking = False
                break
            
            v1 = tabuleiro.caminho[-1] # A ser removido
            v2 = tabuleiro.caminho[-2] # Testar existência de caminho viável

            v1.ordem = -1
            tabuleiro.G.remove_edge(v1,v2)
            tabuleiro.caminho.pop()
            iteracoes_sem_mov = 0
            passeio.append((v1.n,-1))


            # Valida condições de finalização, segundo teste,
            # dentro do backtracking. Após o pop, a ponta do caminho é v2
            if testa_vertice(tabuleiro,v2,vertice_destino) and teste2:
                v = v2
                break
            
            # Checa se existe caminho viável
            if tabuleiro.sorteia_proximo_vertice(v2) is not None:
                backtracking = False
                v = v2

    return passeio


# =============================================================================
# Gera tabuleiro a partir de um passeio aleatório
# =============================================================================
def gera_Tabuleiro(densidade            : float = 0.3
                   ,vertice_origem      : list  = None 
                   ,vertice_destino     : list  = None
                   ,dicas               : bool  = True
                   ,max_tentativas      : int   = 1000
                   ,seed                : int   = None
                   ,verbose             : bool  = False
                   ,**kwargs):
    """
    Tenta gerar um tabuleiro com caminho aleatório com a densidade 
    mínima especificada, dentro do número máximo de tentativas.
    
    O algoritmo gera passeios aleatórios até atingir a densidade desejada.

    Parameters
    ----------
    densidade : float, optional
        Densidade desejada no tabuleiro, número entre 0 e 1. Padrão é 0.3
    max_tentativas: int, optional
        Limite de tentativas para gerar o tabuleiro com a densidade especificada
    seed: int, optional
        Seed para gerador do número aleatório do numpy.random. Para cada tabuleiro, soma
        1 no seed para variar os tabuleiros gerados nas tentativas. Esse valor
        é o mesmo passado para o construtor do Taubuleiro. 
        Não é um parâmetro thread safe
    dicas: bool, optional
        Indica se as dicas do tabuleiro devem ser preenchidas
    **kwargs :
        Variáveis para criação do tabuleiro. Consultar documentação da classe
        Tabuleiro()

    Returns
    -------
    Retorna a lista [densidade, tabuleiro, passeio], com densidade (float entre
    0 e 1) representando a densidade máxima obtida com na rodada, o tabuleiro 
    gerado e uma lista representando o passeio aleatória que gerou o tabuleiro
    """
    
    if verbose:
        print('Total de iterações a testar: {}'.format(max_tentativas))
    
    
    # Tabuleiro vazio para obter os parâmetros padrão do construtor
    tab_aux = sl.Tabuleiro()
    
    # Avalia parâmetros do construtor do Tabuleiro
    lin = kwargs['lin'] if 'lin' in kwargs else tab_aux.lin
    col = kwargs['col'] if 'col' in kwargs else tab_aux.col
    
    max_densidade = 0
    max_tabuleiro = None
    max_caminho = []
    
    barra_progresso = tqdm(range(max_tentativas)
                           ,disable=not verbose
                           ,position=0
                           ,leave=True
                           ,desc="Densidade máxima obtida = 0 ")
    
    for conta_iteracao in barra_progresso:
        
        tabuleiro = sl.Tabuleiro(lin=lin
                                 ,col=col
                                 ,seed=seed)

        caminho = passeio_aleatorio(tabuleiro
                                    ,vertice_origem
                                    ,vertice_destino)
        if seed is not None:
            seed += 1

        densidade_obtida = tabuleiro.get_densidade_caminho()

        if densidade_obtida > max_densidade:
            max_densidade = densidade_obtida
            max_tabuleiro = tabuleiro
            max_caminho = caminho
            if verbose:
                barra_progresso.set_description_str("Densidade máx obtida {:0.4f} de {:0.4f}".format(max_densidade,densidade))
        
        if densidade_obtida >= densidade:
            tqdm.write('\nObtido na {} tentativa'.format(conta_iteracao))
            break

    if dicas:
        max_tabuleiro.preenche_dicas()

    return [max_densidade,max_tabuleiro,max_caminho]


# =============================================================================
# Constrói o caminho do tabuleiro a partir de um conjunto de arestas
# que formam um único ciclo simples
# =============================================================================
def _monta_caminho_de_arestas(tabuleiro, arestas):
    """
    Ordena um conjunto de arestas que formam um único ciclo simples e aplica
    o resultado ao tabuleiro: preenche tabuleiro.caminho, inclui as arestas
    em tabuleiro.G e marca os vértices como visitados.

    Parameters
    ----------
    tabuleiro : Tabuleiro
        Tabuleiro (assumido vazio) onde o ciclo será aplicado
    arestas : set
        Conjunto de tuplas ((l1,c1),(l2,c2)) representando as arestas do ciclo

    Returns
    -------
    Lista no formato de passeio [(n,+1), ...] com os vértices do ciclo
    em ordem de percurso.
    """
    adjacencia = {}
    for a, b in arestas:
        adjacencia.setdefault(a, []).append(b)
        adjacencia.setdefault(b, []).append(a)

    # Percorre o ciclo a partir de um vértice qualquer
    inicio = next(iter(adjacencia))
    caminho_coords = [inicio]
    anterior, atual = None, inicio
    while True:
        vizinhos = adjacencia[atual]
        proximo = vizinhos[0] if vizinhos[0] != anterior else vizinhos[1]
        if proximo == inicio:
            break
        caminho_coords.append(proximo)
        anterior, atual = atual, proximo

    tabuleiro.caminho = []
    passeio = []
    v_anterior = None
    for i, (l, c) in enumerate(caminho_coords):
        v = tabuleiro.get_verticeXY(l, c)
        v.visitado = 1
        v.ordem = i + 1
        tabuleiro.caminho.append(v)
        if v_anterior is not None:
            tabuleiro.G.add_edge(v_anterior, v)
        passeio.append((v.n, 1))
        v_anterior = v

    # Fecha o ciclo
    tabuleiro.G.add_edge(v_anterior, tabuleiro.caminho[0])
    return passeio


# =============================================================================
# Geração de ciclo hamiltoniano (densidade 1.0) via árvore geradora
# =============================================================================
def gera_caminho_hamiltoniano(tabuleiro: sl.Tabuleiro):
    """
    Gera um ciclo hamiltoniano aleatório no tabuleiro: um caminho fechado que
    visita TODOS os vértices (densidade = 1.0), sem tentativa e erro.

    O algoritmo usa a construção clássica de ciclo hamiltoniano a partir de
    árvore geradora: o tabuleiro é dividido em supercélulas de 2x2 vértices,
    sorteia-se uma árvore geradora aleatória do grafo das supercélulas
    (pesos aleatórios + árvore geradora mínima) e o ciclo é o contorno dessa
    árvore "engrossada". Para cada lado de cada supercélula:

      - se a árvore cruza o lado, o ciclo atravessa com as duas arestas
        paralelas do tabuleiro que cruzam esse lado;
      - caso contrário, o ciclo corre pela aresta interna do bloco 2x2
        ao longo desse lado.

    Como a árvore é conexa e acíclica, o resultado é sempre um único ciclo
    simples cobrindo os lin*col vértices. Complexidade O(lin*col*log(lin*col)),
    dominada pela árvore geradora mínima.

    A aleatoriedade vem do numpy.random (controlável pela seed do Tabuleiro).

    Parameters
    ----------
    tabuleiro : Tabuleiro
        Tabuleiro vazio onde o ciclo será gerado. lin e col devem ser pares
        (um grafo grade com número ímpar de vértices não admite ciclo
        hamiltoniano, pois o grafo é bipartido).

    Returns
    -------
    Lista no formato de passeio [(n,+1), ...] com os vértices do ciclo
    em ordem de percurso.
    """
    lin, col = tabuleiro.lin, tabuleiro.col
    if lin % 2 != 0 or col % 2 != 0:
        raise ValueError('lin e col devem ser pares: um tabuleiro com número '
                         'ímpar de vértices não admite ciclo hamiltoniano')

    # Árvore geradora aleatória do grafo das supercélulas
    H = nx.grid_2d_graph(lin // 2, col // 2)
    pesos = {e: np.random.random() for e in H.edges}
    nx.set_edge_attributes(H, pesos, 'weight')
    T = nx.minimum_spanning_tree(H)

    arestas = set()
    def adiciona(a, b):
        arestas.add(tuple(sorted((a, b))))

    for I in range(lin // 2):
        for J in range(col // 2):
            l, c = 2 * I, 2 * J
            # Vértices do bloco 2x2 da supercélula (I,J)
            tl, tr = (l, c), (l, c + 1)
            bl, br = (l + 1, c), (l + 1, c + 1)

            # Lado de cima
            if T.has_edge((I, J), (I - 1, J)):
                adiciona(tl, (l - 1, c))
                adiciona(tr, (l - 1, c + 1))
            else:
                adiciona(tl, tr)

            # Lado de baixo
            if T.has_edge((I, J), (I + 1, J)):
                adiciona(bl, (l + 2, c))
                adiciona(br, (l + 2, c + 1))
            else:
                adiciona(bl, br)

            # Lado esquerdo
            if T.has_edge((I, J), (I, J - 1)):
                adiciona(tl, (l, c - 1))
                adiciona(bl, (l + 1, c - 1))
            else:
                adiciona(tl, bl)

            # Lado direito
            if T.has_edge((I, J), (I, J + 1)):
                adiciona(tr, (l, c + 2))
                adiciona(br, (l + 1, c + 2))
            else:
                adiciona(tr, br)

    return _monta_caminho_de_arestas(tabuleiro, arestas)


# =============================================================================
# Geração de caminho com densidade alvo via crescimento de região
# =============================================================================
def gera_caminho_regiao(tabuleiro: sl.Tabuleiro
                        ,densidade: float = 0.5
                        ,ganancia : float = 0.8):
    """
    Gera um caminho fechado fazendo crescer uma região aleatória de células
    do tabuleiro: o caminho é o CONTORNO da região. Por construção o contorno
    é sempre um único ciclo simples, então não há tentativa e erro.

    O crescimento parte de uma célula sorteada e adiciona células da fronteira
    uma a uma, mantendo dois invariantes que garantem que o contorno seja um
    ciclo simples:

      1. sem toque de canto: duas células da região não podem se tocar apenas
         pela diagonal (criaria um vértice de grau 4 no contorno);
      2. sem buracos: o complemento da região permanece conectado à borda do
         tabuleiro (a região é simplesmente conexa).

    O número de vértices do ciclo é igual ao perímetro da região (em arestas).
    O crescimento para quando o perímetro atinge densidade*lin*col vértices ou
    quando não há mais células viáveis para adicionar.

    Parameters
    ----------
    tabuleiro : Tabuleiro
        Tabuleiro vazio onde o caminho será gerado
    densidade : float, optional
        Densidade alvo (fração dos vértices visitados pelo caminho).
        Padrão 0.5. Para densidade 1.0 use gera_caminho_hamiltoniano,
        que garante a cobertura total.
    ganancia : float, optional
        Probabilidade (entre 0 e 1) de escolher uma célula que maximiza o
        crescimento do perímetro, em vez de uma célula qualquer da fronteira.
        Valores altos gera caminhos mais "serpenteados" (atingem densidades
        maiores); valores baixos geram regiões mais compactas. Padrão 0.8

    Returns
    -------
    Lista no formato de passeio [(n,+1), ...] com os vértices do ciclo
    em ordem de percurso.
    """
    lin, col = tabuleiro.lin, tabuleiro.col
    n_cel_l, n_cel_c = lin - 1, col - 1
    alvo = densidade * lin * col

    dentro = np.zeros((n_cel_l, n_cel_c), dtype=bool)

    def valida(l, c):
        return 0 <= l < n_cel_l and 0 <= c < n_cel_c

    def vizinhos_dentro(l, c):
        return sum(1 for vl, vc in ((l-1,c),(l+1,c),(l,c-1),(l,c+1))
                   if valida(vl, vc) and dentro[vl, vc])

    def sem_toque_de_canto(l, c):
        # Toda célula diagonal dentro da região precisa compartilhar com
        # (l,c) uma célula ortogonal que também esteja dentro da região
        for dl, dc in ((-1,-1),(-1,1),(1,-1),(1,1)):
            ld, cd = l + dl, c + dc
            if valida(ld, cd) and dentro[ld, cd]:
                ok1 = valida(l + dl, c) and dentro[l + dl, c]
                ok2 = valida(l, c + dc) and dentro[l, c + dc]
                if not (ok1 or ok2):
                    return False
        return True

    def sem_buraco(l, c):
        # Com (l,c) incluída, todas as células fora da região precisam
        # continuar alcançáveis a partir da borda do tabuleiro (flood fill)
        dentro[l, c] = True
        fora_total = n_cel_l * n_cel_c - int(dentro.sum())
        if fora_total == 0:
            dentro[l, c] = False
            return True

        visitada = np.zeros_like(dentro)
        pilha = [(bl, bc) for bl in range(n_cel_l) for bc in range(n_cel_c)
                 if (bl in (0, n_cel_l-1) or bc in (0, n_cel_c-1))
                 and not dentro[bl, bc]]
        for celula in pilha:
            visitada[celula] = True
        while pilha:
            pl, pc = pilha.pop()
            for vl, vc in ((pl-1,pc),(pl+1,pc),(pl,pc-1),(pl,pc+1)):
                if valida(vl, vc) and not dentro[vl, vc] and not visitada[vl, vc]:
                    visitada[vl, vc] = True
                    pilha.append((vl, vc))
        dentro[l, c] = False
        return int(visitada.sum()) == fora_total

    # Célula inicial sorteada
    l0 = np.random.randint(n_cel_l)
    c0 = np.random.randint(n_cel_c)
    dentro[l0, c0] = True
    perimetro = 4
    fronteira = {(vl, vc) for vl, vc in ((l0-1,c0),(l0+1,c0),(l0,c0-1),(l0,c0+1))
                 if valida(vl, vc)}

    while perimetro < alvo and fronteira:
        # Adicionar uma célula com k vizinhos dentro da região altera o
        # perímetro em 4-2k: células com 1 vizinho aumentam o perímetro
        ganho_maximo = max(4 - 2*vizinhos_dentro(*cel) for cel in fronteira)
        if np.random.random() < ganancia and ganho_maximo > 0:
            candidatas = [cel for cel in fronteira
                          if 4 - 2*vizinhos_dentro(*cel) == ganho_maximo]
        else:
            candidatas = list(fronteira)

        # Tenta as candidatas em ordem aleatória até achar uma viável;
        # se nenhuma célula da fronteira for viável, para o crescimento
        np.random.shuffle(candidatas)
        candidatas += [cel for cel in fronteira if cel not in candidatas]
        escolhida = None
        for cel in candidatas:
            if sem_toque_de_canto(*cel) and sem_buraco(*cel):
                escolhida = cel
                break
        if escolhida is None:
            break

        el, ec = escolhida
        perimetro += 4 - 2*vizinhos_dentro(el, ec)
        dentro[el, ec] = True
        fronteira.discard(escolhida)
        for vl, vc in ((el-1,ec),(el+1,ec),(el,ec-1),(el,ec+1)):
            if valida(vl, vc) and not dentro[vl, vc]:
                fronteira.add((vl, vc))

    # O contorno da região são as arestas entre uma célula dentro e uma
    # célula fora da região (ou a borda do tabuleiro)
    arestas = set()
    for l in range(n_cel_l):
        for c in range(n_cel_c):
            if not dentro[l, c]:
                continue
            if not (valida(l-1, c) and dentro[l-1, c]):
                arestas.add(((l, c), (l, c+1)))
            if not (valida(l+1, c) and dentro[l+1, c]):
                arestas.add(((l+1, c), (l+1, c+1)))
            if not (valida(l, c-1) and dentro[l, c-1]):
                arestas.add(((l, c), (l+1, c)))
            if not (valida(l, c+1) and dentro[l, c+1]):
                arestas.add(((l, c+1), (l+1, c+1)))

    return _monta_caminho_de_arestas(tabuleiro, arestas)


# =============================================================================
# Gera tabuleiro com algoritmo construtivo (substitui gera_Tabuleiro)
# =============================================================================
def gera_Tabuleiro2(densidade : float = 0.3
                    ,dicas    : bool  = True
                    ,seed     : int   = None
                    ,**kwargs):
    """
    Versão construtiva de gera_Tabuleiro: gera o caminho fechado em uma
    única passada, sem repetir passeios aleatórios até atingir a densidade.

      - densidade >= 1.0: gera um ciclo hamiltoniano (cobre TODOS os
        vértices do tabuleiro) via gera_caminho_hamiltoniano. Exige
        lin e col pares.
      - densidade < 1.0: gera o contorno de uma região aleatória via
        gera_caminho_regiao, crescida até o perímetro atingir a
        densidade alvo.

    Parameters
    ----------
    densidade : float, optional
        Densidade alvo do caminho (fração dos vértices do tabuleiro
        visitados). Padrão é 0.3
    dicas : bool, optional
        Indica se as dicas do tabuleiro devem ser preenchidas. Padrão True
    seed : int, optional
        Seed do numpy.random, passada ao construtor do Tabuleiro
    **kwargs :
        Variáveis para criação do tabuleiro (lin, col). Consultar a
        documentação da classe Tabuleiro()

    Returns
    -------
    Lista [densidade, tabuleiro, passeio], no mesmo formato de
    gera_Tabuleiro: densidade obtida, tabuleiro gerado e o passeio
    [(n,+1), ...] com os vértices do caminho em ordem de percurso.
    """
    tab_aux = sl.Tabuleiro()
    lin = kwargs['lin'] if 'lin' in kwargs else tab_aux.lin
    col = kwargs['col'] if 'col' in kwargs else tab_aux.col

    tabuleiro = sl.Tabuleiro(lin=lin, col=col, seed=seed)

    if densidade >= 1.0:
        passeio = gera_caminho_hamiltoniano(tabuleiro)
    else:
        passeio = gera_caminho_regiao(tabuleiro, densidade=densidade)

    if dicas:
        tabuleiro.preenche_dicas()

    return [tabuleiro.get_densidade_caminho(), tabuleiro, passeio]


# =============================================================================
# Fábrica do oráculo de unicidade (CP-SAT se disponível, senão puro-Python)
# =============================================================================
def _novo_oraculo(lin, col, dicas, max_nos, motor, solucao_hint=None):
    """
    Retorna um solver com a interface conta_solucoes/completa. motor:
    'auto' escolhe pelo tamanho do tabuleiro (em tabuleiros pequenos o
    solver puro-Python ganha; nos grandes usa CP-SAT/OR-Tools se
    instalado, com fallback para o puro-Python); 'cpsat' exige OR-Tools;
    'python' força o solver puro-Python. solucao_hint é a solução
    conhecida do puzzle, repassada ao CP-SAT como palpite inicial.
    """
    usa_cpsat = (motor == 'cpsat'
                 or (motor == 'auto' and lin*col > 150))
    if usa_cpsat:
        try:
            import solver_cpsat as sc
            return sc.SolverCpSat(lin, col, dicas, solucao_hint=solucao_hint)
        except ImportError:
            if motor == 'cpsat':
                raise
    return sv.Solver(lin, col, dicas, max_nos=max_nos)


# =============================================================================
# Redução de dicas mantendo a solução única (geração de puzzle)
# =============================================================================
def reduz_dicas(tabuleiro
                ,simetria : bool  = False
                ,minimiza : bool  = True
                ,semente  : float = 0.5
                ,max_nos  : int   = 15000
                ,motor    : str   = 'auto'
                ,verbose  : bool  = False):
    """
    Calcula um subconjunto pequeno das dicas do tabuleiro que ainda define
    o caminho gerado como ÚNICA solução do puzzle.

    Como cada dica apenas restringe o conjunto de laços possíveis, remover
    dicas nunca tira a solução do puzzle (o laço gerado satisfaz todas as
    dicas que ele mesmo produziu) -- o desafio é manter a UNICIDADE.

    O algoritmo é bottom-up, guiado por contraexemplo (CEGAR):

      1. começa com um subconjunto aleatório das dicas (fração semente);
      2. pede ao solver uma solução DIFERENTE do laço alvo;
      3. se existe, ela discorda do alvo na contagem de arestas de alguma
         célula sem dica: colocar a dica do alvo nessa célula elimina esse
         contraexemplo (e, em geral, muitos outros);
      4. repete até o solver provar que não há outra solução.

    Toda solução alternativa encontrada fica em cache: antes de chamar o
    solver, o cache é consultado -- se um contraexemplo antigo ainda é
    consistente com as dicas atuais, a não-unicidade é provada de graça.

    Ao final, uma varredura gulosa opcional (minimiza=True) tenta remover
    cada dica restante, garantindo um puzzle localmente minimal: nenhuma
    dica pode ser removida sem perder a unicidade.

    A semente inicial existe por desempenho: com pouquíssimas dicas a
    contagem de soluções degenera em enumeração de caminhos auto-evitantes
    (exponencial). Começar com uma fração das dicas e deixar a minimização
    removê-las depois mantém todas as chamadas do solver no regime rápido,
    perto da unicidade. Como salvaguarda, o solver tem um orçamento de nós:
    chamadas inconclusivas adicionam uma dica (na fase 1) ou mantêm a dica
    (na fase 2) -- a unicidade do resultado continua garantida, só a
    minimalidade pode ser afetada.

    Parameters
    ----------
    tabuleiro : Tabuleiro
        Tabuleiro com o caminho gerado. As dicas completas são calculadas
        com preenche_dicas(); o tabuleiro não é alterado além disso.
    simetria : bool, optional
        Se True, as dicas são adicionadas/removidas em pares com simetria
        rotacional de 180 graus (estética clássica dos puzzles Nikoli).
        Padrão False
    minimiza : bool, optional
        Se True, faz a varredura final de minimização. Padrão True
    semente : float, optional
        Fração das células que começam com dica na fase de adição
        (entre 0 e 1). Padrão 0.5
    max_nos : int, optional
        Orçamento de nós de busca por chamada do solver puro-Python.
        Valores menores geram mais rápido, com puzzles um pouco menos
        minimais (algumas dicas redundantes podem sobrar). Padrão 15000
    motor : str, optional
        Motor do teste de unicidade: 'auto' (CP-SAT/OR-Tools se instalado,
        senão o solver puro-Python), 'cpsat' ou 'python'. Padrão 'auto'
    verbose : bool, optional
        Se True, imprime o progresso. Padrão False

    Returns
    -------
    Matriz (lin-1)x(col-1) com as dicas do puzzle: valores 0 a 3 nas
    células com dica e -1 nas células sem dica.
    """
    lin, col = tabuleiro.lin, tabuleiro.col
    if len(tabuleiro.caminho) == 0:
        raise ValueError('o tabuleiro não tem caminho gerado')

    tabuleiro.preenche_dicas()
    alvo = tabuleiro.dicas.astype(int)
    alvo_solucao = sv.arestas_do_tabuleiro(tabuleiro)

    # Sanidade: o mapa completo de dicas precisa ter solução única
    n, _ = _novo_oraculo(lin, col, alvo, max_nos, motor
                         ,alvo_solucao).conta_solucoes(limite=2)
    if n != 1:
        raise ValueError('o mapa completo de dicas não tem solução única '
                         '({} soluções encontradas)'.format(n))

    # Subconjunto inicial aleatório de dicas (ver Notes sobre a semente)
    puzzle = np.where(np.random.random((lin-1, col-1)) < semente, alvo, -1)
    if simetria:
        m = (puzzle >= 0) | (puzzle[::-1, ::-1] >= 0)
        puzzle = np.where(m, alvo, -1)

    cache = []   # matrizes de dicas das soluções alternativas já vistas

    def consistente(contagens):
        m = puzzle >= 0
        return bool(np.all(contagens[m] == puzzle[m]))

    def adiciona_dica(l, c):
        puzzle[l, c] = alvo[l, c]
        if simetria:
            ls, cs = lin-2-l, col-2-c
            if puzzle[ls, cs] < 0:
                puzzle[ls, cs] = alvo[ls, cs]

    def contraexemplo():
        # Primeiro o cache: contraexemplo antigo ainda consistente prova
        # a não-unicidade sem chamar o solver
        for contagens in cache:
            if consistente(contagens):
                return contagens
        s = _novo_oraculo(lin, col, puzzle, max_nos, motor, alvo_solucao)
        n, solucoes = s.conta_solucoes(limite=2)
        alternativas = [x for x in solucoes if x != alvo_solucao]
        if alternativas:
            novas = [sv.dicas_de_solucao(lin, col, x) for x in alternativas]
            cache.extend(novas)
            return novas[0]
        if s.completa:
            return None   # provado: solução única (e é o alvo)
        # Busca inconclusiva (orçamento de nós estourado): adiciona uma
        # dica aleatória para apertar o puzzle e tenta de novo
        sem_dica = np.argwhere(puzzle < 0)
        l, c = sem_dica[np.random.randint(len(sem_dica))]
        adiciona_dica(l, c)
        if verbose:
            print('solver inconclusivo, dica extra adicionada')
        return contraexemplo()

    # Fase 1: adição de dicas guiada por contraexemplo
    while True:
        contagens = contraexemplo()
        if contagens is None:
            break
        # Células sem dica onde o contraexemplo discorda do alvo: anotar
        # a dica do alvo em qualquer uma delas elimina o contraexemplo.
        # Escolhe a que elimina o maior número de contraexemplos do cache
        difere = np.argwhere((contagens != alvo) & (puzzle < 0))
        melhor, melhor_pontos = None, -1
        for l, c in difere:
            pontos = sum(1 for outro in cache
                         if outro[l, c] != alvo[l, c] and consistente(outro))
            if pontos > melhor_pontos:
                melhor, melhor_pontos = (l, c), pontos
        adiciona_dica(*melhor)
        if verbose:
            print('dicas: {:3d} | contraexemplos no cache: {}'.format(
                int((puzzle >= 0).sum()), len(cache)))

    # Fase 2: minimização gulosa (remove cada dica que ficou redundante)
    if minimiza:
        com_dica = [tuple(x) for x in np.argwhere(puzzle >= 0)]
        for i in np.random.permutation(len(com_dica)):
            l, c = com_dica[i]
            if puzzle[l, c] < 0:
                continue   # já removida como par simétrico
            backup = puzzle[l, c]
            puzzle[l, c] = -1
            par = None
            if simetria:
                ls, cs = lin-2-l, col-2-c
                if (ls, cs) != (l, c) and puzzle[ls, cs] >= 0:
                    par = (ls, cs, puzzle[ls, cs])
                    puzzle[ls, cs] = -1

            unica = not any(consistente(ct) for ct in cache)
            if unica:
                s = _novo_oraculo(lin, col, puzzle, max_nos, motor
                                  ,alvo_solucao)
                n, solucoes = s.conta_solucoes(limite=2)
                alternativas = [x for x in solucoes if x != alvo_solucao]
                if alternativas:
                    cache.extend(sv.dicas_de_solucao(lin, col, x)
                                 for x in alternativas)
                    unica = False
                elif not s.completa:
                    # Inconclusivo: mantém a dica por segurança
                    unica = False
            if not unica:
                puzzle[l, c] = backup
                if par is not None:
                    puzzle[par[0], par[1]] = par[2]
        if verbose:
            print('após minimização: {} dicas'.format(int((puzzle >= 0).sum())))

    return puzzle


# =============================================================================
# Redução de dicas — métodos do site (guloso / binária / CEGAR) com controle
# de dificuldade. Operam sobre a MATRIZ de dicas completa (`alvo`) + a `solucao`
# (frozenset de ids de aresta), espelhando core.js (reduceClues /
# reduceCluesBinaria / reduceCluesCEGAR). O oráculo de unicidade já usa a
# "busca esperta" (padrões fixos), então toda a redução é acelerada por eles.
# =============================================================================
_FRAC_VOLTA = {'dificil': 0.0, 'medio': 0.4, 'facil': 0.75}


def _devolve_dicas(puzzle, alvo, removidas, rs, dificuldade):
    """Devolve uma fração das dicas removidas conforme a dificuldade (mais
    fácil = mais dicas de volta). Unicidade preservada (qualquer superconjunto
    de um conjunto único continua único). Muta e retorna `puzzle`."""
    frac = _FRAC_VOLTA.get(dificuldade, 0.4)
    removidas = list(removidas)
    rs.shuffle(removidas)
    for i in range(int(round(frac * len(removidas)))):
        l, c = removidas[i]
        puzzle[l, c] = alvo[l, c]
    return puzzle


def _unico(lin, col, puzzle, solucao, max_nos, motor):
    """True se `puzzle` tem solução única E o solver concluiu (completa).
    Como remover dicas mantém o alvo como solução, count==1 ⇒ a única é o alvo."""
    s = _novo_oraculo(lin, col, puzzle, max_nos, motor, solucao)
    n, _ = s.conta_solucoes(limite=2)
    return n == 1 and s.completa


def reduz_guloso(lin, col, alvo, solucao, dificuldade='medio',
                 max_nos=40000, motor='python', seed=None):
    """REDUÇÃO GULOSA (método padrão do site): tenta remover cada dica numa
    ordem aleatória, mantendo a remoção se o puzzle continuar único; ao final
    devolve uma fração das removidas conforme a dificuldade."""
    rs = np.random.RandomState(seed)
    alvo = np.asarray(alvo).astype(int)
    puzzle = alvo.copy()
    celulas = [(l, c) for l in range(lin - 1) for c in range(col - 1)]
    rs.shuffle(celulas)
    removidas = []
    for l, c in celulas:
        if puzzle[l, c] < 0:
            continue
        bak = puzzle[l, c]
        puzzle[l, c] = -1
        if _unico(lin, col, puzzle, solucao, max_nos, motor):
            removidas.append((l, c))
        else:
            puzzle[l, c] = bak
    return _devolve_dicas(puzzle, alvo, removidas, rs, dificuldade)


def reduz_binaria(lin, col, alvo, solucao, dificuldade='medio',
                  max_nos=40000, motor='python', seed=None):
    """REDUÇÃO POR BUSCA BINÁRIA (rápida): fixada uma ordem, P(k)='remover as k
    primeiras mantém único' é monótona, então acha-se o maior k por busca
    binária (O(log n) chamadas do solver). Reembaralha a cada rodada até nada
    mais sair. Costuma deixar mais dicas que o guloso, mas é bem mais rápido."""
    rs = np.random.RandomState(seed)
    alvo = np.asarray(alvo).astype(int)
    puzzle = alvo.copy()
    removidas = []
    progrediu = True
    while progrediu:
        progrediu = False
        restantes = [(l, c) for l in range(lin - 1) for c in range(col - 1)
                     if puzzle[l, c] >= 0]
        rs.shuffle(restantes)

        def unico_removendo(k):
            p = puzzle.copy()
            for i in range(k):
                l, c = restantes[i]
                p[l, c] = -1
            return _unico(lin, col, p, solucao, max_nos, motor)

        lo, hi = 0, len(restantes)
        while lo < hi:
            m = (lo + hi + 1) // 2          # teto
            if unico_removendo(m):
                lo = m
            else:
                hi = m - 1
        if lo > 0:
            for i in range(lo):
                l, c = restantes[i]
                puzzle[l, c] = -1
                removidas.append((l, c))
            progrediu = True
    return _devolve_dicas(puzzle, alvo, removidas, rs, dificuldade)


def reduz_cegar(lin, col, alvo, solucao, dificuldade='medio',
                max_nos=40000, motor='python', seed=None, semente=0.5):
    """REDUÇÃO POR CEGAR (bottom-up, guiada por contraexemplo): parte de poucas
    dicas (fração `semente`) e adiciona a dica verdadeira onde um contraexemplo
    diverge do alvo, até provar unicidade; pente-fino guloso final + devolve por
    dificuldade. Espelha core.js reduceCluesCEGAR (variante matriz-based, à parte
    do reduz_dicas() original baseado em Tabuleiro)."""
    rs = np.random.RandomState(seed)
    alvo = np.asarray(alvo).astype(int)
    alvo_sol = solucao if isinstance(solucao, frozenset) else frozenset(solucao)
    R, C = lin - 1, col - 1
    puzzle = np.where(rs.random_sample((R, C)) < semente, alvo, -1)
    cache = []

    def consistente(cts):
        m = puzzle >= 0
        return bool(np.all(cts[m] == puzzle[m]))

    def adiciona(cts):
        op = [(l, c) for l in range(R) for c in range(C)
              if puzzle[l, c] < 0 and cts[l, c] != alvo[l, c]]
        if not op:
            return False
        l, c = op[rs.randint(len(op))]
        puzzle[l, c] = alvo[l, c]
        return True

    def contraexemplo():
        for cts in cache:
            if consistente(cts):
                return cts
        s = _novo_oraculo(lin, col, puzzle, max_nos, motor, alvo_sol)
        _, solucoes = s.conta_solucoes(limite=2)
        alts = [x for x in solucoes if x != alvo_sol]
        if alts:
            m = sv.dicas_de_solucao(lin, col, alts[0])
            cache.append(m)
            return m
        if s.completa:
            return None
        livres = [(l, c) for l in range(R) for c in range(C) if puzzle[l, c] < 0]
        if not livres:
            return None
        l, c = livres[rs.randint(len(livres))]
        puzzle[l, c] = alvo[l, c]
        return contraexemplo()

    guard = 0
    while guard < R * C * 4:
        guard += 1
        cts = contraexemplo()
        if cts is None or not adiciona(cts):
            break

    celulas = [(l, c) for l in range(R) for c in range(C) if puzzle[l, c] >= 0]
    rs.shuffle(celulas)
    removidas = []
    for l, c in celulas:
        bak = puzzle[l, c]
        puzzle[l, c] = -1
        if _unico(lin, col, puzzle, solucao, max_nos, motor):
            removidas.append((l, c))
        else:
            puzzle[l, c] = bak
    return _devolve_dicas(puzzle, alvo, removidas, rs, dificuldade)


def reduz_dicas_metodo(metodo, lin, col, alvo, solucao, dificuldade='medio',
                       max_nos=40000, motor='python', seed=None):
    """Despacha para o método de redução do site: 'guloso' (padrão), 'binaria'
    ou 'cegar'. Recebe o mapa completo `alvo` (matriz (lin-1)x(col-1)) e a
    `solucao` (frozenset de ids de aresta) e devolve a matriz reduzida na
    dificuldade pedida."""
    if metodo == 'binaria':
        return reduz_binaria(lin, col, alvo, solucao, dificuldade, max_nos, motor, seed)
    if metodo == 'cegar':
        return reduz_cegar(lin, col, alvo, solucao, dificuldade, max_nos, motor, seed)
    return reduz_guloso(lin, col, alvo, solucao, dificuldade, max_nos, motor, seed)


# =============================================================================
# Gera um puzzle completo: tabuleiro + redução de dicas + dificuldade
# =============================================================================
def gera_Puzzle(densidade : float = 0.3
                ,simetria : bool  = False
                ,minimiza : bool  = True
                ,max_nos  : int   = 15000
                ,motor    : str   = 'auto'
                ,seed     : int   = None
                ,dificuldade : str = None
                ,metodo   : str   = 'guloso'
                ,verbose  : bool  = False
                ,**kwargs):
    """
    Gera um puzzle de Slitherlink completo: tabuleiro com caminho fechado
    (gera_Tabuleiro2), redução das dicas mantendo solução única e avaliação
    (ou definição) da dificuldade.

    Há dois modos, conforme o parâmetro `dificuldade`:

      - `dificuldade=None` (padrão): redução MINIMAL via reduz_dicas() (CEGAR
        baseado em Tabuleiro, com simetria opcional) e a dificuldade é então
        ESTIMADA por avalia_dificuldade() -- é o comportamento original.
      - `dificuldade` em {'facil','medio','dificil'}: usa os métodos do site
        (reduz_dicas_metodo, escolhido por `metodo`), que removem as dicas e
        devolvem uma fração conforme a dificuldade ALVO -- a dificuldade vira
        ENTRADA (como no jogo). `simetria` não se aplica nesse modo.

    Parameters
    ----------
    densidade : float, optional
        Densidade alvo do caminho. Padrão é 0.3
    simetria, minimiza, verbose :
        Consultar reduz_dicas() (só no modo `dificuldade=None`).
    max_nos : int, optional
        Orçamento de nós do solver puro-Python. Padrão 15000.
    motor : str, optional
        'auto' | 'cpsat' | 'python' (ver _novo_oraculo). Padrão 'auto'.
    seed : int, optional
        Seed do numpy.random / dos métodos de redução.
    dificuldade : str, optional
        None -> estima a dificuldade (modo original); 'facil'|'medio'|'dificil'
        -> alvo passado aos métodos do site; 'nenhuma'/'none' -> mapa COMPLETO
        de dicas, sem reduzir (todas as dicas). Padrão None.
    metodo : str, optional
        Método de redução quando `dificuldade` é dada: 'guloso' (padrão),
        'binaria' ou 'cegar'. Padrão 'guloso'.
    **kwargs :
        Variáveis para criação do tabuleiro (lin, col)

    Returns
    -------
    Lista [tabuleiro, puzzle, dificuldade]: o tabuleiro com o caminho solução
    (tabuleiro.dicas mantém o mapa completo), a matriz de dicas do puzzle (-1
    nas células sem dica) e a dificuldade -- estimada (modo None) ou a alvo
    pedida.

    Notes
    -----
    Existem laços diferentes que produzem exatamente o mesmo mapa completo
    de dicas -- nesses tabuleiros nenhum subconjunto de dicas define o laço
    de forma única. Quando isso acontece, um novo tabuleiro é gerado
    (até max_tentativas vezes, somando 1 na seed a cada tentativa).
    """
    max_tentativas = 20
    for tentativa in range(max_tentativas):
        _, tabuleiro, _ = gera_Tabuleiro2(densidade=densidade
                                          ,dicas=True
                                          ,seed=seed
                                          ,**kwargs)
        lin, col = tabuleiro.lin, tabuleiro.col

        if dificuldade is None:
            # Modo original: redução minimal (CEGAR) + dificuldade estimada
            try:
                puzzle = reduz_dicas(tabuleiro
                                     ,simetria=simetria
                                     ,minimiza=minimiza
                                     ,max_nos=max_nos
                                     ,motor=motor
                                     ,verbose=verbose)
            except ValueError:
                if seed is not None:
                    seed += 1
                if verbose:
                    print('mapa completo ambíguo, gerando outro tabuleiro')
                continue
            dif = sv.avalia_dificuldade(lin, col, puzzle)
            return [tabuleiro, puzzle, dif]

        # Modos 'nenhuma' (mapa completo) e dificuldade-alvo (guloso/binaria/
        # cegar). Confere a unicidade do mapa completo (igual ao reduz_dicas).
        alvo = tabuleiro.dicas.astype(int)
        solucao = sv.arestas_do_tabuleiro(tabuleiro)
        n, _ = _novo_oraculo(lin, col, alvo, max_nos, motor,
                             solucao).conta_solucoes(limite=2)
        if n != 1:
            if seed is not None:
                seed += 1
            if verbose:
                print('mapa completo ambíguo, gerando outro tabuleiro')
            continue
        if dificuldade in ('nenhuma', 'none'):
            return [tabuleiro, alvo, 'nenhuma']    # TODAS as dicas, sem reduzir
        puzzle = reduz_dicas_metodo(metodo, lin, col, alvo, solucao
                                    ,dificuldade=dificuldade
                                    ,max_nos=max_nos
                                    ,motor=motor
                                    ,seed=seed)
        return [tabuleiro, puzzle, dificuldade]

    raise RuntimeError('não foi possível gerar um tabuleiro com mapa de '
                       'dicas de solução única em {} tentativas'
                       .format(max_tentativas))

