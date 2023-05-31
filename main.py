
# -*- coding: utf-8 -*-
"""
Created on Thu May 11 17:5:33 2023

@author: lucas
"""

import numpy as np
import networkx as nx

class Vertice:
    def __init__(self, l, c, n):
        self.l = l
        self.c = c
        self.n = n
        self.pos = (self.c,self.l)
        self.visitado = 0
        self.ordem= -1
        self.cor = -1
        self.dica = 0
        
    def __str__(self):
        t = "({},{})".format(self.c, self.l)
        return (t)
    
    def __eq__(self, obj):
        if not isinstance(obj, Vertice):
            return False
        
        if (obj.l == self.l and obj.c == self.c):
            return True
        
        return False
    
    def __hash__(self):
        return self.n
    
    def __int__(self):
        return self.n

    def distancia(self,v):
        """
        Calcula a distância entre esse e outro vértice. Nesse
        conceito a distância é o número mínimo de passos necessários
        para ir de um vértice a outro.

        Parameters
        ----------
        v : Vertice
            Vértice a ser avaliado

        Returns
        -------
        Maior distância diferença entre os eixos de ambos os vértices.
        """
        dx = abs(self.l - v.l)
        dy = abs(self.c - v.c)
        return dx+dy




class Tabuleiro:
    
    def __init__(self
                 ,lin=20
                 ,col=20
                 ,seed=None):
        """
        Inicia um tabuleiro vazio (sem caminho definido), dadas as dimensões.
        As dimensões lin e col representam o número de vértives do grafo que
        representa o tabuleiro.

        Parameters
        ----------
        lin : int, optional
            Número de linhas do tabuleiro. Valor padrão são 20 linhas.
        col : int, optional
            Número de colunas do tabuleiro. Valor padrão são 20 colunas.
        seed : int, optional
            Semente utilizada para iniciar o gerador de números aleatorios
            do numpy.random. Valor padrão é None (semente aleatória escolhida).
            Esse parâmetro impacta como o passeio aleatório gera o caminho
            no tabuleiro.

        Returns
        -------
        None.

        """
        self.lin = lin
        self.col = col
        self.shape = (self.lin, self.col)
        self.G = nx.Graph()
        self.vertices = {}
        self.numero_vertices = self.lin * self.col
        self.caminho = []
        self.seed = seed
        self.dicas = np.zeros((lin-1,col-1))
        
        if seed is not None:
            np.random.seed(seed)
        
        # Inclui os vértices no grafo
        for l in range(self.lin):
            for c in range(self.col):
                n = self.col*l+c
                a = Vertice(l,c,n)
                self.G.add_node(a)
                self.vertices[a.n] = a # Cadastra vértice em dict pelo id

    def par(self):
        return {'lin':self.lin
                ,'col':self.col
                ,'shape':self.shape
                ,'escala_imagem':self.escala_imagem
                ,'escala_ponto':self.escala_ponto}        

    def n_para_xy(self,n):
        """
        Converte o número do vértice e coordenadas (lin,col)

        Parameters
        ----------
        n : int
            Número do vértice

        Returns
        -------
        Ponto com as coordenadas do vértice (lin,col)

        """
        col = n % self.col
        lin = (n - col) / self.col
        return(lin,col)

    def xy_para_n(self,l,c):
        """
        Converte coordenadas do vértice (lin,col) no número do vértice

        Parameters
        ----------
        l : int
            Número da linha do vértice no tabuleiro
        c : int
            Número da coluna do vértice no tabuleiro

        Returns
        -------
        int
            Número do vértice

        """
        return self.col*l+c

    def get_verticeXY(self,lin,col):
        """
        Retorna o vértice do grafo na posiçao especificada

        Parameters
        ----------
        lin : int
            Número da linha do vértice
        col : int
            Número da coluna do vértice

        Returns
        -------
        Vertice do grafo na posição especificada, None se a posição não existe

        """
        if lin >= 0 and lin < self.lin and col>= 0 and col < self.col:
            n = self.xy_para_n(lin, col)
            return self.vertices[n]
        return None
        
    def get_verticeN(self,n):
        """
        Retorna o vértice do grafo na posiçao especificada

        Parameters
        ----------
        n: int
            Número do vértice

        Returns
        -------
        Vertice do grafo especificado, None se a posição não existe

        """
        if n >= 0 and n < self.numero_vertices:
            return self.vertices[n]
        return None
        
    def sorteia_vertice(self):
        """
        Sorteia um vértice não visitado no tabuleiro

        Returns
        -------
        Vértice não visitado. None se não houver mais vértices não visitados

        """
        lista = np.random.choice(a=self.numero_vertices
                                 ,size=self.numero_vertices
                                 ,replace=False)
        for i in lista:
            v = self.get_verticeN(i)
            if v.visitado == 0:
                return v
        return None

    def get_vertice_direita(self,v):
        """
        Retorna o vértice vizinho, acima do vértice informado, se existir.

        Parameters
        ----------
        v : Vertice
            Vértice para calcular o vizinho superior

        Returns
        -------
        Vertice
            Vértice superior, None se não existir (vértice informado estiver
            na borda do tabuleiro)

        """
        if v.l < self.lin-1:
            return self.get_verticeXY(v.l+1,v.c)
        else:
            return None

    def get_vertice_esquerda(self,v):
        """
        Retorna o vértice vizinho, à esquerda do vértice informado, se existir.

        Parameters
        ----------
        v : Vertice
            Vértice para calcular o vizinho à esquerda

        Returns
        -------
        Vertice
            Vértice à esquerda, None se não existir (vértice informado estiver
            na borda do tabuleiro)

        """ 
        if v.l > 0:
            return self.get_verticeXY(v.l-1,v.c)
        else:
            return None
        
    def get_vertice_acima(self,v):
        """
        Retorna o vértice vizinho, acima do vértice informado, se existir.

        Parameters
        ----------
        v : Vertice
            Vértice para calcular o vizinho acima

        Returns
        -------
        Vertice
            Vértice acima, None se não existir (vértice informado estiver
            na borda do tabuleiro)

        """ 
        if v.c < self.col-1:
            return self.get_verticeXY(v.l,v.c+1)
        else:
            return None
        
    def get_vertice_abaixo(self,v):
        """
        Retorna o vértice vizinho, abaixo do vértice informado, se existir.

        Parameters
        ----------
        v : Vertice
            Vértice para calcular o vizinho abaixo

        Returns
        -------
        Vertice
            Vértice abaixo, None se não existir (vértice informado estiver
            na borda do tabuleiro)

        """ 
        if v.c > 0:
            return self.get_verticeXY(v.l,v.c-1)
        else:
            return None

    def sorteia_proximo_vertice(self,v):
        """
        Sorteia um vértice vizinho para dar um próximo 
        passo no passeio aleatório.

        Parameters
        ----------
        v : Vertice
            Vértice de origem para o próximo passo

        Returns
        -------
        Vertice
            Retorna Vervice viável, escolhido aleatóriamente a partir de v

        """
        v_acima = self.get_vertice_acima(v)
        v_abaixo = self.get_vertice_abaixo(v)
        v_direita = self.get_vertice_direita(v)
        v_esquerda = self.get_vertice_esquerda(v)
        
        direcao_valida = []
        
        if v_acima is not None:
            direcao_valida.append(v_acima) if v_acima.visitado == 0 else 0
        
        if v_abaixo is not None:
            direcao_valida.append(v_abaixo) if v_abaixo.visitado == 0 else 0
        
        if v_direita is not None:
            direcao_valida.append(v_direita) if v_direita.visitado == 0 else 0
        
        if v_esquerda is not None:
            direcao_valida.append(v_esquerda) if v_esquerda.visitado == 0 else 0
        
        if len(direcao_valida) == 0:
            return None
        else:
            return np.random.choice(direcao_valida)
       
   
    def testa_fim(self,v,vertice_destino,caminho_minimo=5):
        """
        Testa se o passeio aleatório terminou, chegando novamente ao vértice
        destino
    
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
        
        if len(self.caminho) < caminho_minimo:
            return False
        
        # Valida condições de finalização
        teste_final = [self.get_vertice_acima(v)
                       ,self.get_vertice_abaixo(v)
                       ,self.get_vertice_esquerda(v)
                       ,self.get_vertice_direita(v)]
    
        for t in [t for t in teste_final if t is not None]:
            cond1 = (t == vertice_destino)
            cond2 = (t.visitado == 1)
            cond3 = (not self.G.has_edge(v,vertice_destino))
                        
            if cond1 and cond2 and cond3:
                #self.G.add_edge(v,vertice_destino)
                return True
            
        return False

    def get_comprimento_caminho(self):
        """
        Retorna o número de vértices que fazem parte do caminho no tabuleiro

        Returns
        -------
        int
            Quantidade de vértices visitados pelo caminho do tabuleiro

        """
        return len(self.caminho)
    
    
    def get_densidade_caminho(self):
        """
        Retorna a razão entre o número de vértices que fazem parte do caminho 
        no tabuleiro e o total de vértices do tabuleiro - medida chamada
        aqui de densidade do caminho

        Returns
        -------
        float
            Retorna a densidade do caminho do tabuleiro

        """
        return len(self.caminho)/self.numero_vertices


    def __eq__(self, o):
        if not isinstance(o, Tabuleiro):
            return False
        
        condicao1 = (self.lin == o.lin)
        condicao2 = (self.col == o.col)
        condicao3 = (nx.utils.graphs_equal(self.G, o.G))
        
        if (condicao1 and condicao2 and condicao3):
            return True
        
        return False

    def get_dica(self,l,c):
        """
        Retorna a quantidade de vértices ocupados ao retor do quadrado de vértices
        formado por (l,c),(l+1,c),(l,c+1),(l+1,c+1).

        Parameters
        ----------
        l : int
            Número da linha, variando de zero a lin-1 
            (lin é a dimensão do tabuleiro no eixo y)
        c : int
            Número da coluna, variando de zero a col-1 
            (lin é a dimensão do tabuleiro no eixo x)

        Returns
        -------
        int, representando a quantidade de vértices ocupados
        """
        dica = 0
        
        v00 = self.get_verticeXY(l  ,c  )
        v10 = self.get_verticeXY(l+1,c  )
        v01 = self.get_verticeXY(l  ,c+1)
        v11 = self.get_verticeXY(l+1,c+1)
        
        dica += 1 if self.G.has_edge(v00,v10) else 0
        dica += 1 if self.G.has_edge(v10,v11) else 0
        dica += 1 if self.G.has_edge(v11,v01) else 0
        dica += 1 if self.G.has_edge(v01,v00) else 0
            
        return dica

    def preenche_dicas(self):
        """
        Preenche as dicas do tabuleiro a partir do caminho gerado.

        Returns
        -------
        None.

        """
        self.dicas = np.zeros((self.lin-1,self.col-1))
        for l in range(self.lin-1):
            for c in range(self.col-1):
                dica = self.get_dica(l,c)
                self.dicas[l][c] = dica
                self.get_verticeXY(l,c).dica = dica



    def __copy__(self):
        """
        Retorna uma cópia vazia (i.e., sem o passeio aleatório), apenas
        com os mesmos parâmetros do tabuleiro

        Returns
        -------
        Tabuleiro
            Tabuleiro vazio com mesmos parâmetros do tabuleiro origem

        """
        return Tabuleiro(lin=self.lin
                         ,col=self.col)