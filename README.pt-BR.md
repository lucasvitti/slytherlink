# slytherlink

### ▶ Jogue online: **[slitherlink.lucas.mat.br](https://slitherlink.lucas.mat.br)**

[English](README.md) · **Português (pt-BR)**

Um kit de ferramentas **Slitherlink** feito do zero: um **gerador** construtivo de
quebra-cabeças, um **solver** por propagação de restrições, várias estratégias de
**redução de dicas** e um **jogo de navegador** jogável e sem dependências — com a
teoria e os benchmarks por trás de cada peça documentados abaixo.

Há duas implementações que compartilham as mesmas ideias:

| | Linguagem | Onde | Papel |
|---|---|---|---|
| **Biblioteca** | Python (NumPy, NetworkX, OpenCV, OR‑Tools opcional) | raiz do repositório | Motor de referência: geradores, solver (+ CP‑SAT), redução de dicas, renderização de imagem/vídeo. |
| **Jogo** | JavaScript puro (sem framework, sem backend) | [`web/`](web/) | App de página única estático: uma porta completa do motor mais um tabuleiro interativo. |

---

## Sumário

- [O que é Slitherlink?](#o-que-é-slitherlink)
- [A teoria](#a-teoria)
  - [Um laço é a fronteira de uma região](#1-um-laço-é-a-fronteira-de-uma-região)
  - [Por que a unicidade é o problema inteiro (monotonicidade)](#2-por-que-a-unicidade-é-o-problema-inteiro-monotonicidade)
- [Geração](#geração)
- [O solver](#o-solver)
- [Redução de dicas (criando um quebra-cabeça)](#redução-de-dicas-criando-um-quebra-cabeça)
- [Dificuldade e o solver animado](#dificuldade-e-o-solver-animado)
- [Desempenho](#desempenho)
- [O jogo de navegador](#o-jogo-de-navegador)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Como executar](#como-executar)
- [Referências e agradecimentos](#referências-e-agradecimentos)
- [Licença](#licença)

---

## O que é Slitherlink?

Slitherlink (também *Loop the Loop*, *Fences*) é jogado em uma grade de pontos. Você
desenha um **único laço fechado** ao longo das arestas da grade de modo que cada
célula numerada tenha *exatamente* aquela quantidade dos seus quatro lados sobre o
laço. Um quebra-cabeça correto tem **uma** solução, alcançável apenas pela lógica.

```
.   .   .   .          ┌───┐   .   .
  3   2                │ 3 │ 2
.   .   .   .    →     │   └───┐   .
  2   . 1             │ 2   . │1
.   .   .   .          └───────┘   .
```

---

## A teoria

### 1. Um laço é a fronteira de uma região

Pelo **teorema da curva de Jordan**, um único laço fechado divide o plano em um
*interior* e um *exterior*. De forma equivalente: **o laço é exatamente a fronteira
da sua região interior**. Esta é a pedra angular de todo o projeto, usada nas duas
direções:

- **A geração o aplica para frente.** Em vez de *buscar* um laço válido, nós
  *crescemos uma região de células* e tomamos seu contorno. O contorno é um único
  laço simples **se e somente se** a região for:
  1. **conexa por arestas** (uma só peça),
  2. **simplesmente conexa** (sem buracos — o complemento permanece conectado à
     borda), e
  3. **livre de toque de cantos** (nenhuma dupla de células da região se toca apenas
     diagonalmente, o que criaria um ponto de estrangulamento de grau 4 no contorno).

  Manter esses três invariantes durante o crescimento significa que o resultado é
  *correto por construção* — sem tentativa e erro.

- **O solver o aplica para trás** (na formulação interior/exterior): uma aresta está
  sobre o laço ⇔ suas duas células adjacentes (contando o exterior) estão em lados
  opostos, e uma dica `k` significa "exatamente `k` dos meus vizinhos estão no lado
  oposto."

Uma consequência usada pelo solver: um laço fechado cruza qualquer linha reta da
grade um número **par** de vezes (a regra de *paridade de corte*), que é uma dedução
barata e poderosa.

### 2. Por que a unicidade é o problema inteiro (monotonicidade)

Cada dica é uma **restrição que remove laços candidatos**. Então, se `S(C)` é o
conjunto de laços válidos consistentes com um conjunto de dicas `C`, então

> `C' ⊆ C  ⟹  S(C) ⊇ S(C')`  — remover dicas só pode **aumentar** o conjunto solução.

Dois corolários importantes:

- **A solubilidade é grátis.** Um laço que geramos satisfaz *todas* as dicas que ele
  produziu, então ele continua sendo uma solução válida de *qualquer* subconjunto
  dessas dicas. Nunca corremos o risco de tornar um quebra-cabeça insolúvel ao
  remover dicas.
- **A unicidade é a batalha inteira.** O mapa completo de dicas quase sempre tem uma
  solução; remover dicas só pode adicionar soluções. Então a redução de dicas é uma
  caça por um *pequeno* subconjunto que *ainda seja único* — e a monotonicidade acima
  é exatamente o que torna o redutor por **busca binária** válido (veja abaixo).

Decidir a unicidade é NP‑completo em geral (Slitherlink é NP‑completo), mas a
propagação de restrições a torna rápida na prática em tamanhos de jogo.

---

## Geração

O laço é construído **construtivamente**, nunca por amostragem por rejeição.

- **Crescimento de região (`generateLoop`, ambas as implementações).** Comece de uma
  célula semente e anexe repetidamente células da fronteira, verificando a cada vez
  os três invariantes acima (toque de cantos via um teste local, ausência de buracos
  via um flood fill). O comprimento do laço é igual ao perímetro da região, então o
  crescimento simplesmente para em uma densidade alvo. Para evitar deixar um tabuleiro
  meio vazio em tabuleiros alongados, a versão JS cresce em **duas fases**: uma fase
  de *espalhamento* (*spread*) que prefere células que estendam o retângulo
  envolvente da região até cobrir ≥85 % de ambos os eixos, e então uma fase de
  *serpenteio* (*wiggle*) que maximiza o perímetro para detalhe. Densidade padrão
  `0.75`.
- **Laço hamiltoniano (`gera_caminho_hamiltoniano`, Python).** Para tabuleiros de
  cobertura total (densidade `1.0`), desenhe uma árvore geradora aleatória da grade
  de supercélulas 2×2 e tome o contorno dessa árvore "engrossada". Como a árvore é
  conexa e acíclica, o contorno é comprovadamente um ciclo único passando por **cada**
  vértice. `O(n log n)`, sem retentativas. (Requer dimensões pares — uma grade de
  vértices ímpares é bipartida e não admite ciclo hamiltoniano.)

A abordagem antiga que isto substituiu — uma caminhada aleatória auto-evitante que
retenta até fechar um laço grande — é ao mesmo tempo lenta e incapaz de garantir
cobertura; veja os números de [desempenho](#desempenho) para o contraste.

---

## O solver

Uma única primitiva sustenta tudo: *contar as soluções de um conjunto de dicas, até
2* (um **oráculo de unicidade**). Ela combina **propagação de restrições** com
**busca com backtracking**.

A **propagação** aplica repetidamente deduções forçadas a um modelo de aresta de três
estados (desconhecida / linha / cruz) até um ponto fixo:

- **Regra do vértice** — todo ponto tem grau 0 ou 2: duas linhas ⇒ suas outras
  arestas são cruzes; uma linha com uma única desconhecida restante ⇒ essa aresta é
  uma linha; etc.
- **Regra da célula** — uma célula com dica `k` e `k` linhas já presentes ⇒ suas
  arestas restantes são cruzes; se linhas + desconhecidas é igual a `k` ⇒ as
  desconhecidas são linhas.
- **Regra de paridade de corte** (Python) — cada corte da grade carrega um número par
  de linhas.

Quando a propagação estagna, a busca **ramifica** sobre uma aresta (preferindo uma na
ponta de um caminho aberto), recorrendo e contando soluções, parando em 2.

Dois dispositivos estruturais a mantêm correta e rápida:

- **Union‑find para detecção de laço único.** Fragmentos de caminho são rastreados em
  uma estrutura de conjuntos disjuntos; uma aresta que fecharia um ciclo é rejeitada
  *a menos que* ela complete a solução inteira (todas as dicas satisfeitas, nenhum
  outro segmento de linha) — a eliminação de subtour do Slitherlink.
  - ⚠️ **O union‑find NÃO deve usar compressão de caminho.** A busca *desfaz* as
    uniões no backtrack; a compressão de caminho altera os ponteiros pai de nós que
    não estão registrados na trilha de desfazer, o que corrompe silenciosamente a
    estrutura no rollback e faz o solver **subcontar** soluções. (Batemos exatamente
    nesse bug na porta JS — ele produzia quebra-cabeças "únicos" que na verdade tinham
    duas soluções. Um `find` simples com union‑by‑size é seguro para rollback.) Foi
    detectado por um fuzzer que compara o solver com força bruta em tabuleiros
    pequenos.
- **Poda por conectividade.** Se os fragmentos de linha colocados já não podem ser
  unidos em um único componente através das arestas ainda disponíveis, o ramo é
  abandonado.

**`solver_cpsat.py` (Python, opcional).** Para tabuleiros grandes há um oráculo
**CP‑SAT** do OR‑Tools: ele modela o laço único com `AddCircuit` (cada aresta → dois
arcos direcionados, mais um self‑loop por vértice pulado), adiciona as restrições de
dica e as restrições redundantes de grau/paridade e — crucialmente — alimenta o laço
alvo conhecido como um `AddHint`, de modo que a primeira solução é encontrada
instantaneamente e cada chamada custa apenas a *refutação* de uma segunda solução. Sem
a dica + restrições redundantes, um 20×20 esparso levou 60 s e não encontrou nada; com
elas, 0,5 s.

---

## Redução de dicas (criando um quebra-cabeça)

Transformar um mapa completo de dicas em um quebra-cabeça significa remover dicas
preservando a unicidade. O projeto mantém **múltiplas estratégias como opções
selecionáveis** (no jogo de navegador, um dropdown), porque elas trocam velocidade por
minimalidade de formas diferentes:

| Método | Ideia | Característica |
|---|---|---|
| **Guloso** (`reduceClues`) | Embaralha as células; remove cada uma se o resultado ainda for único (`O(n)` chamadas ao oráculo). | Quase mínimo; lento em tabuleiros grandes. |
| **Busca binária** (`reduceCluesBinaria`) | Monotonicidade ⇒ "as primeiras *k* de uma ordem embaralhada são conjuntamente removíveis" é monótono em *k*, então faz **busca binária** do prefixo removível máximo em `O(log n)` chamadas por rodada; reembaralha e repete. | **Rápido** (≈10× em tabuleiros grandes); algumas dicas a mais. |
| **CEGAR** (`reduceCluesCEGAR`) | Guiado por contraexemplos, de baixo para cima: começa com algumas dicas; enquanto o solver encontra uma solução ≠ alvo, adiciona uma dica onde elas diferem (matando esse contraexemplo); um cache de contraexemplos passados evita chamadas redundantes ao solver. | Tende ao **menor número** de dicas; o mais lento. |

A dificuldade é então ajustada **devolvendo algumas dicas removidas** (mais dicas =
mais fácil). Como qualquer superconjunto de um conjunto de dicas único ainda é único
(monotonicidade), isso nunca quebra o quebra-cabeça.

> **Uma nota prática conquistada a duras penas:** o solver explode
> combinatorialmente quando há *pouquíssimas* dicas (ele degenera em enumerar
> caminhos auto-evitantes), não quando há muitas. É por isso que o CEGAR é semeado
> com ~50 % das dicas em vez de começar vazio, e por que um orçamento de nós/passos
> protege cada chamada ao oráculo.

A biblioteca Python (`reduz_dicas`) implementa a estratégia CEGAR com um cache de
contraexemplos mais uma minimização gulosa final e simetria rotacional de 180°
opcional.

---

## Dificuldade e o solver animado

O jogo pode **animar** uma resolução, em dois modos honestos:

- **Dedução (oráculo).** Como a solução única é conhecida, isto propaga deduções
  forçadas e, quando travado, coloca a *próxima aresta correta do laço*. Ele **nunca
  faz backtracking** — um preenchimento limpo, sempre para frente. (As deduções de
  saturação de dicas e de grau aparecem como cruzes; o laço cresce em cor.)
- **Busca real (backtracking).** Uma busca *cega à resposta* a partir das dicas
  apenas: ela adivinha, atinge contradições, **apaga e refaz o trajeto**. Você pode
  literalmente assistir a ela se debater. Um tabuleiro com *todas as dicas* resolve
  com **zero** backtracking (lógica pura); um tabuleiro *difícil* mínimo se debate —
  uma boa visualização de "quanto chute este quebra-cabeça precisa."

Um 9×9 difícil mínimo precisa de ~485 mil passos de busca, então o traço da busca real
é limitado (8 000 passos) e salta para a solução se ultrapassar.

---

## Desempenho

Números indicativos (núcleo único; seu hardware será diferente). Eles ilustram o
*formato* dos trade-offs, não a velocidade absoluta.

**A geração construtiva supera a antiga caminhada aleatória decisivamente** (Python,
20×20, densidade alvo 0,9):

| Gerador | Resultado | Tempo |
|---|---|---|
| Antiga caminhada aleatória auto-evitante (2000 retentativas) | estabilizou em densidade **0,69** | 14,3 s |
| Nova construtiva (`gera_Tabuleiro2`) | densidade **0,90** | **0,13 s** |

**Métodos de redução de dicas** (motor JS, Node; mesmo tabuleiro por linha, então o
laço é idêntico e apenas o redutor difere):

| Tabuleiro / dificuldade | Guloso | Busca binária | CEGAR |
|---|---|---|---|
| 10×10 difícil | 33 dicas · ~3,4 s | 39 dicas · ~1,0 s | 29 dicas · ~1,5 s |
| 14×14 difícil | 69 dicas · ~13,7 s | 88 dicas · ~11,3 s | 64 dicas · ~24,7 s |
| 18×18 médio | 203 dicas · ~74 s | 237 dicas · **~7 s** | 155 dicas · ~89 s |

Conclusão: a **busca binária** ganha de longe em tabuleiros grandes (≈10×) ao custo de
algumas dicas extras; o **CEGAR** produz o menor número de dicas, mas é o mais lento; o
**guloso** é o meio-termo equilibrado. (Essas instâncias são NP‑difíceis, então a
variância por tabuleiro é alta.)

**A geração com todas as dicas** (sem redução) é barata mesmo quando grande: 50×50 em
< 1 s, 60×60 ≈ 0,85 s (JS).

**Redução de dicas em Python com o oráculo CP‑SAT** (pipeline completo): 10×10 ≈ 2 s,
14×14 ≈ 14 s, 20×20 ≈ 2 min (361 → 162 dicas), 24×24 ≈ 9 min.

**Correção de cobertura do laço:** em um tabuleiro 7×20 o pior bloco contíguo de dicas
`0` ("espaço morto") caiu de ~41 células para ~10 após a mudança de crescimento por
espalhamento + densidade, mantendo uma mistura variada de dicas (~14 % de zeros, ~27 %
de uns).

---

## O jogo de navegador

Um SPA estático, offline e sem dependências em [`web/`](web/) — implanta-se como
arquivos simples atrás de qualquer servidor web. Destaques:

- **Barra superior:** linhas/colunas independentes, uma **semente** (*seed*) em texto
  (qualquer string; em branco ou com a caixa *random* marcada, sorteia uma nova e a
  reescreve para que seja reproduzível), **dificuldade** (incl. *None* = mostrar todas
  as dicas), o seletor de **método de redução** e o tempo de geração.
- **Jogar:** clique em uma aresta para desenhar/apagar uma linha; **pressione e
  segure** para marcá-la como *impossível* (×). A grade é pontilhada; arestas que são
  automaticamente impossíveis (em torno de um `0`, ou uma terceira aresta em um vértice
  de grau 2) são mostradas mais esmaecidas.
- **Coloração de segmentos:** cada cadeia conexa de linhas recebe sua própria cor;
  quando duas cadeias se fundem, a cor da **maior** prevalece.
- **Resolver** com a animação de dedução ou de busca real; **desfazer/refazer**,
  reiniciar.
- **Importação/exportação CSV** de todo o estado (tabuleiro, solução, linhas atuais,
  marcas ×, *e* o histórico de jogadas). As arestas são identificadas como `H:r:c` /
  `V:r:c`.

Veja [`web/README.md`](web/README.md) para o esquema CSV e os controles em detalhe.

A geração roda em um **Web Worker** para que a UI nunca trave, e os assets têm
cache-busting por uma query de versão `?v=`.

---

## Estrutura do repositório

```
slytherlink/
├── main.py            # Vertice / Tabuleiro (grid as a NetworkX graph)
├── gerador.py         # generators + clue reduction (greedy/binary/CEGAR helpers)
├── solver.py          # propagation + backtracking uniqueness oracle, difficulty grading
├── solver_cpsat.py    # optional OR-Tools CP-SAT oracle (AddCircuit + hint)
├── plota.py           # OpenCV rendering (image + walk-replay video)
├── teste_*.py         # Python tests / benchmarks
└── web/               # the browser game
    ├── index.html
    ├── css/style.css
    └── js/
        ├── core.js        # the engine (RNG, generator, solver, reducers, tracers)
        ├── game.js        # SVG UI + interaction
        ├── worker.js      # generation off the UI thread
        ├── test_core.js   # Node: generation + uniqueness checks
        └── fuzz_core.js   # Node: solver vs brute force
```

## Como executar

**O jogo** (Web Workers precisam de `http://`, não `file://`):

```bash
cd web
python -m http.server 8778      # then open http://127.0.0.1:8778
```

**A biblioteca Python:**

```bash
pip install numpy networkx opencv-python matplotlib tqdm
pip install ortools             # optional, speeds up large-board reduction
python teste_slitherlink.py     # generator tests / benchmark
python teste_puzzle.py          # solver + clue-reduction tests
```

**Testes do motor (Node):**

```bash
cd web
node js/test_core.js            # generation + uniqueness across sizes/difficulties
node js/fuzz_core.js            # solver compared to brute force on small boards
```

## Referências e agradecimentos

- **Liam Appelbe — [_How to generate Slither Link puzzles_](https://liamappelbe.medium.com/how-to-generate-slither-link-puzzles-6c65510b2ba1).** A abordagem de geração do laço por coloração de células/regiões e a **remoção de dicas por busca binária** deste projeto são diretamente inspiradas por esse excelente artigo — vale muito a leitura.
- Jonathan Olson — [_How Slitherlink Should Be Solved_](https://jonathanolson.net/slitherlink/): um catálogo dos padrões de dedução lógica.
- Yoshinaka, Saitoh, Kawahara, Tsuruma, Iwashita & Minato — [_Finding All Solutions and Instances of Numberlink and Slitherlink by ZDDs_](https://www.mdpi.com/1999-4893/5/2/176), *Algorithms* 5(2), 2012.

## Licença

Veja [LICENSE](LICENSE).
