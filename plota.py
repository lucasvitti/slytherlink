# -*- coding: utf-8 -*-
"""
Created on Sat May 27 09:17:14 2023

@author: lucas
"""

import numpy as np
import cv2
import matplotlib.pyplot as plt
from tqdm import tqdm

import slitherlink.main as sl


# =============================================================================
# Função para traçar uma linha pontilhada
# =============================================================================
def linha_pontilhada(img
                     ,origem
                     ,destino
                     ,tam_linha
                     ,tam_espaco
                     ,cor
                     ,espessura):
    """
    Desenha uma linha pontilhada na imagem. Função baseada em
    https://stackoverflow.com/a/75765173/3853329

    Parameters
    ----------
    img : np.array
        Matriz representando a imagem
    origem : tuple
        Coordenadas de origem da linha
    destino : tuple
        Coordenadas de destino da linha
    tam_linha : int
        Tamanho (em pixels) do segmento desenhado da linha tracejada
    tam_espaco : int
        Tamanho (em pixels) do segmento em branco da linha tracejada
    cor : tuple
        Tupla com 3 posições representando a cor da linha
    espessura : int
        Espessura da linha

    Returns
    -------
    None.

    """
    dx = destino[0] - origem[0]
    dy = destino[1] - origem[1]
    compr = np.sqrt(dx*dx + dy*dy)
    dx = dx / compr
    dy = dy / compr
        
    compr_desenhado = 0
    origem_aux = origem
    while (compr_desenhado < compr):
        
        # Desenha o segmento
        destino_aux = (int(origem_aux[0] + tam_linha*dx), int(origem_aux[1] + tam_linha*dy))
        _ = cv2.line(img
                     ,origem_aux
                     ,destino_aux
                     ,color=cor
                     ,thickness=espessura)
        
        # Ajusta a nova origem dando o espaço
        origem_aux = (int(destino_aux[0] + tam_espaco*dx), int(destino_aux[1] + tam_espaco*dy))
       
        compr_desenhado += tam_espaco + tam_linha
    
    

    
# =============================================================================
# Constroi imagem
# =============================================================================
def gera_imagem(tab,**kwargs):
    """
    Gera uma imagem do tabuleiro

    Parameters
    ----------
    tab : Tabuleiro
        Tabuleiro para plotagem. A imagem representa o estado do tabuleiro
        no momento da chamada da função.
    **kwargs : dict
        Parâmetros para construção da imagem.
        
        plota_caminho : bool
            Indica se o caminho é ou não plotado. Valor padrão True
        plota_dicas:  bool
            Indica se as dicas de construção do caminho (números nas 
            células do tabuleiro) serão plotados. Valor padrão True
        pad: int
            Número de pixels entre os vértices. Valor padrão 100.
        raio_vertice: int
            Raio do vértice. Valor padrão 10.
        espessura_aresta: int
            Espessura, em pixels, das arestas. Valor padrão 4
        cor_nv: list
            Cor para plotar os vértices não visitados pelo caminho.
            A cor é representada por uma lista de três inteiros, representando
            os valores R,G,B
            Valor padrão (211,211,211)
        cor_v: list
            Cor para plotar os vértices visitados pelo caminho.
            A cor é representada por uma lista de três inteiros, representando
            os valores R,G,B
            Valor padrão (65,105,225)
        cor_grid: list
            Cor para plotar as arestas entre vértices, montando o grid.
            As linhas poltadas são pntilhadas, com parâmetros específicos
            (tam_segmento_pontilhado e tam_espaco_pontilhado) para definir 
            o estilo do pontilhado. A cor é representada por uma lista de 
            três inteiros, representando os valores R,G,B. Valor padrão (211,211,211)
        tam_segmento_pontilhado: int
            Número de pixels que representam o segmento plotado da linha pontilhada.
            A linha pontilhada é usada para plotar o grid entre os vértices.
            Valor padrão 4
        tam_espaco_pontilhado: int
            Número de pixels que representam o espaço entre os segmentos plotados
            da linha pontilhada. A linha pontilhada é usada para plotar o grid 
            entre os vértices. Valor padrão 8
        espessura_pontilhado: int
            Espessura da linha pontilhada traçada para plotar o grid.
            Valor padrão 2
        escala_fonte: int
            Tamanho da fonte para plotar as dicas do tabuleiro.
            Valor padrão 1.5
        espessura_fonte: int
            Espessura da fonte para plotar as dicas do tabuleiro.
            Valor padrão 2
        cor_fonte: list
            Cor da fonte usada para as dicas no tabuleiro.
            A cor é representada por uma lista de três inteiros, representando
            os valores R,G,B. Valor padrão (0,0,0)

    Returns
    -------
    Matriz (numpy.ndarray) representando a imagem do tabuleiro.
    """
    
    # Parâmetros para plotar o tabuleiro
    plota_grid                  = kwargs.pop('plota_grid'               ,True)
    plota_caminho               = kwargs.pop('plota_caminho'            ,True)
    plota_dicas                 = kwargs.pop('plota_dicas'              ,True)
    pad                         = kwargs.pop('pad'                      ,100)
    raio_vertice                = kwargs.pop('raio_vertice'             ,10)
    espessura_aresta            = kwargs.pop('espessura_aresta'         ,4)
    cor_nv                      = kwargs.pop('cor_nv'                   ,(211,211,211))
    cor_v                       = kwargs.pop('cor_v'                    ,(65,105,225))
    cor_grid                    = kwargs.pop('cor_grid'                 ,(211,211,211))
    tam_segmento_pontilhado     = kwargs.pop('tam_segmento_pontilhado'  ,4)
    tam_espaco_pontilhado       = kwargs.pop('tam_espaco_pontilhado'    ,8)
    espessura_pontilhado        = kwargs.pop('espessura_pontilhado'     ,1)
    escala_fonte                = kwargs.pop('escala_fonte'             ,1.5)
    espessura_fonte             = kwargs.pop('espessura_fonte'          ,2)
    cor_fonte                   = kwargs.pop('cor_fonte'                ,(0,0,0))
    
    shape = (pad*(tab.lin+1)
             ,pad*(tab.col+1),3)
    
    img = 255*np.ones(shape,np.uint8)
    
    # Plota os vértices
    for x in range(tab.col):
        for y in range(tab.lin):
            v = tab.get_verticeXY(y,x)
            pos_v = (pad*(x+1),pad*(y+1))
            
            if plota_caminho:
                cor = cor_v if v in tab.caminho else cor_nv
            else:
                cor = cor_nv
    
            # Plota todas as arestas do grid, apenas se plota_grid=True
            v_dir  = tab.get_verticeXY(v.l,v.c+1)
            v_cima = tab.get_verticeXY(v.l+1,v.c)
    
            if (plota_grid and v_dir is not None):
                pos_v_dir  = (pad*(v_dir.c+1),pad*(v_dir.l+1))
                linha_pontilhada(img
                                 ,origem=pos_v
                                 ,destino=pos_v_dir
                                 ,tam_linha=tam_segmento_pontilhado
                                 ,tam_espaco=tam_espaco_pontilhado
                                 ,cor=cor_grid
                                 ,espessura=espessura_pontilhado)
    
            
            if (plota_grid and v_cima is not None):
                pos_v_cima = (pad*(v_cima.c+1),pad*(v_cima.l+1))
                linha_pontilhada(img
                                 ,origem=pos_v
                                 ,destino=pos_v_cima
                                 ,tam_linha=tam_segmento_pontilhado
                                 ,tam_espaco=tam_espaco_pontilhado
                                 ,cor=cor_grid
                                 ,espessura=espessura_pontilhado)
    
            # Plota o vérvice
            cv2.circle(img
                     ,pos_v
                     ,radius=raio_vertice
                     ,color=cor
                     ,thickness=-1)
    
    
    # Plota o caminho no grafo
    if len(tab.caminho) > 0:
        if plota_caminho:
            v0 = tab.caminho[-1]
            for i in range(len(tab.caminho)):
                v1 = tab.caminho[i]
                    
                # Plota apenas se os vértices forem vizinhos
                if v1.distancia(v0) <= 1:
                    cv2.line(img
                             ,(pad*(v0.c+1),pad*(v0.l+1))
                             ,(pad*(v1.c+1),pad*(v1.l+1))
                             ,color=cor_v
                             ,thickness=espessura_aresta) 
                v0 = v1
        
   
    # Plota as dicas do tabuleiro
    if plota_dicas:
        for l in range(tab.lin-1):
            for c in range(tab.col-1):
                dica = tab.dicas[l][c]
                v = tab.get_verticeXY(l,c)
                texto = '{:0.0f}'.format(dica)
                
                box_texto,bl = cv2.getTextSize(text=texto
                                               ,fontFace=cv2.FONT_HERSHEY_SIMPLEX
                                               ,fontScale=escala_fonte
                                               ,thickness=espessura_fonte)
                dx = int((pad - box_texto[0])/2)
                dy = int((pad - box_texto[1])/2)
                
                origem = (pad*(v.c+1) + dx, pad*(v.l+1) + 2*dy)
                _ = cv2.putText(img
                                ,text=texto
                                ,org=origem
                                ,fontFace=cv2.FONT_HERSHEY_SIMPLEX
                                ,fontScale=escala_fonte
                                ,color=cor_fonte
                                ,thickness=espessura_fonte
                                ,bottomLeftOrigin=False)  
            
    return img


# =============================================================================
# Plota o tabuleiro
# =============================================================================
def plota_tabuleiro(tabuleiro: sl.Tabuleiro 
                    ,escala:   int = 15
                    ,**kwargs):
    """
    Plota o estado do tabuleiro passado como parâmetro

    Parameters
    ----------
    tabuleiro: Tabuleiro
        Tabuleiro a ser plotado
    escala : float, optional
        Escala para plotar o gráfico. Por padrão assume 0.5

    Returns
    -------
    Matriz numpy.darray representando a imagem gerada

    """
    img = gera_imagem(tabuleiro,kwargs=kwargs)
           
    # Exibe a imagem
    ratio = (img.shape[0]/sum(img.shape),img.shape[1]/sum(img.shape))
    plt.figure(figsize=(escala*ratio[0]
                        ,escala*ratio[1]))
    plt.imshow(img)
    
    
    
   
   


# =============================================================================
# Grava o caminho do tabuleiro (em teste)
# =============================================================================
def grava_caminho(tabuleiro     : sl.Tabuleiro
                  ,arquivo_saida: str
                  ,caminho      : list = None
                  ,plota_dicas  : bool = False
                  ,fps          : int  = 15
                  ,segundos_fim : int  = 3
                  ,verbose      : bool = True
                  ,**kwargs     : dict):
    """
    Grava um vídeo no formato MP3 com o passeio aleatório
    realizado

    Parameters
    ----------
    tabuleiro: Tabuleiro
        Tabuleiro para referência
    arquivo_saida : str
        Nome do arquivo a ser salvo
    caminho: list, optional
        Indica qual o caminho deve ser gravado no vídeo. Deve ser passada uma lista
        de números de vértices. Números positivos indicam inclusão de vértice, números
        negativos são as exclusões de vértice. Se esse parâmetro não for especificado
        plota o caminho no tabuleiro.
    plota_dicas: bool, optional
        Indica se as dicas devem ser recalculadas a cada passo, para ser exibida no vídeo
    fps: int, optional
        Frames por segundo (FPS). Padrão é 15.
    segundos_fim: int, optional
        Quantos segundos no fim do vídeo o estado final é mostrado.
        Padrão são 3s.
    verbose: bool,optional
        Indica se será mostrara a barra de progresso da gravação do vídeo.
        Valor padrão True.
    kwargs: dict, optional
        Parâmetros da função de geração de imagem do tabuleiro. 
        Cosultar gera_imagem()

    Returns
    -------
    None.

    """ 
    
    # Cria um tabuleiro auxiliar para capturar os estados
    # do passeio aleatório
    tab = tabuleiro.__copy__()
    
    # Captura uma imagem do tabuleiro vazio, para obter
    # as dimensões da imagem
    if plota_dicas:
        tab.preenche_dicas()
    img = gera_imagem(tab
                      ,plota_dicas=plota_dicas
                      ,kwargs=kwargs)

    # Inicia o gravador de vídeo        
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    vvw = cv2.VideoWriter(arquivo_saida
                          ,fourcc
                          ,fps
                          ,(img.shape[1],img.shape[0]))


    # Se o caminho não for especificado, usa o do tabuleiro
    if caminho is None:
        caminho = [(v.n,1) for v in tabuleiro.caminho]

    # Varre os vértices replicando o caminho aleatório
    n = caminho[0][0]
    v = tab.get_verticeN(n)
    tab.caminho.append(v)

    for i in tqdm(range(len(caminho))
                  ,disable=not verbose):
        if i == 0:
            continue

        sinal = caminho[i][1]      
        n_original = caminho[i][0]
        v_auxiliar = tab.get_verticeN(n_original)  

        # Inclui o novo vértice (sinal > 0)
        if sinal == 1: 
            
            # Inclui a aresta no tabuleiro auxiliar
            tab.caminho.append(v_auxiliar)
            tab.G.add_edge(v,v_auxiliar)
        
        # Exclui o novo vértice (sinal < 0)
        else:
            tab.caminho.remove(v_auxiliar)
            try:
                tab.G.remove_edge(v_auxiliar,tab.caminho[-1])
            except:
                pass

        # Avança o vértice
        v = v_auxiliar
            
        
        # Captura a imagem do estado do tabuleiro
        if plota_dicas:
            tab.preenche_dicas()
        img = gera_imagem(tab
                          ,plota_dicas=plota_dicas
                          ,kwargs=kwargs)
        
        # Converte para RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Registra a imagem no vídeo
        vvw.write(img)

    # Mantem o estado final por mais frames
    for i in range(fps*segundos_fim):
        vvw.write(img)

    vvw.release()


