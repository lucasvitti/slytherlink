# slytherlink

Gerador, solver e renderizador de puzzles de **Slitherlink** em Python.

Um Slitherlink é resolvido traçando um único laço fechado sobre uma grade de
pontos, de modo que cada célula com um número tenha exatamente aquela
quantidade de lados do laço ao seu redor. Este projeto gera tabuleiros, reduz
as dicas mantendo a solução única, resolve e desenha tudo.

## Módulos

| Arquivo | Conteúdo |
|---|---|
| `main.py` | Classes `Vertice` e `Tabuleiro` (grade como grafo NetworkX). |
| `gerador.py` | Geração do laço e dos puzzles (ver abaixo). |
| `solver.py` | Solver por propagação de restrições + backtracking; oráculo de unicidade `conta_solucoes`; `avalia_dificuldade`. |
| `solver_cpsat.py` | Oráculo de unicidade via OR-Tools CP-SAT (opcional, muito mais rápido em tabuleiros grandes). |
| `plota.py` | Renderização do tabuleiro com OpenCV (imagem e vídeo do passeio). |

## Geração do laço

O gerador antigo (`gera_Tabuleiro`) traçava passeios aleatórios e repetia até
atingir a densidade desejada — lento e sem garantia de cobertura. Os geradores
novos são **construtivos** (o laço é correto por construção, sem tentativa e
erro):

- `gera_caminho_hamiltoniano` — laço que cobre **todos** os vértices
  (densidade 1.0), via contorno de uma árvore geradora aleatória de
  supercélulas 2x2. Exige dimensões pares. O(n log n).
- `gera_caminho_regiao` — laço com densidade-alvo exata, como contorno de uma
  região aleatória cultivada célula a célula.
- `gera_Tabuleiro2` — substituto direto de `gera_Tabuleiro` usando os acima.

## Geração de puzzles

`gera_Puzzle` produz um puzzle jogável: gera o laço, reduz as dicas mantendo a
**solução única** (`reduz_dicas`, estratégia CEGAR guiada por contraexemplo com
cache + minimização gulosa, com simetria rotacional opcional) e estima a
dificuldade. O motor de unicidade é escolhido automaticamente (`motor='auto'`):
solver puro-Python para tabuleiros pequenos, CP-SAT para os grandes.

```python
import gerador as ger
import plota
import cv2

# Puzzle 10x10 com solução única, simétrico
tab, puzzle, dificuldade = ger.gera_Puzzle(densidade=1.0, lin=10, col=10,
                                           seed=42, simetria=True)
print(dificuldade)                 # 'facil' | 'medio' | 'dificil'

# Desenha só as dicas (puzzle) e o laço (solução)
tab.dicas = puzzle.astype(float)
img = plota.gera_imagem(tab, plota_caminho=False)
cv2.imwrite('puzzle.png', cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
```

## Como rodar

Os scripts importam os módulos de forma plana, então **rode de dentro desta
pasta**:

```bash
pip install numpy networkx opencv-python matplotlib tqdm
pip install ortools          # opcional, acelera tabuleiros grandes

python teste_slitherlink.py  # testes/benchmark dos geradores de laço
python teste_puzzle.py       # testes do solver e da redução de dicas
python gera_imagens.py       # amostras de puzzles (puzzle + solução)
python gera_100.py           # laços 100x100 (imagem do passeio)
```

As imagens e vídeos gerados ficam nesta pasta (e são ignorados pelo git).

## Licença

Veja [LICENSE](LICENSE).
