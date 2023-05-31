# -*- coding: utf-8 -*-
"""
Created on Sun May 28 08:35:11 2023

@author: lucas
"""

from tqdm import tqdm
import slitherlink.main as sl


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
            # dentro do backtracking
            if testa_vertice(tabuleiro,v,vertice_destino) and teste2:
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
    col = kwargs['col'] if 'lin' in kwargs else tab_aux.col
    
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

