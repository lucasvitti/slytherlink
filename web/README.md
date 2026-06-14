# Slitherlink — jogo no navegador

SPA estática (sem backend) para jogar Slitherlink. Gera o tabuleiro, reduz as
dicas mantendo solução única e oferece o tabuleiro jogável — tudo em
JavaScript no navegador.

## Estrutura

| Arquivo | Papel |
|---|---|
| `index.html` | Estrutura da página e barra superior. |
| `css/style.css` | Estilos. |
| `js/core.js` | Motor: RNG semeado, gerador do laço, solver (oráculo de unicidade) e redução de dicas por dificuldade. Roda no navegador e no Node. |
| `js/worker.js` | Web Worker que gera o puzzle fora da thread da UI. |
| `js/game.js` | UI jogável: render SVG, clique nas arestas, arestas inviáveis esmaecidas, validação, desfazer/refazer, CSV. |
| `js/test_core.js`, `js/fuzz_core.js` | Testes em Node (não vão para produção). |

## Rodar localmente

Web Workers exigem `http://` (não `file://`). Sirva a pasta:

```bash
cd web
python -m http.server 8778
# abra http://127.0.0.1:8778
```

Testes do motor (Node):

```bash
node js/test_core.js   # gera puzzles e valida unicidade/consistência
node js/fuzz_core.js   # compara o solver com força bruta em tabuleiros pequenos
```

## Como jogar

- **Barra superior:** linhas e colunas (independentes), semente, dificuldade,
  **Gerar tabuleiro**, desfazer/refazer, limpar, exportar/importar CSV.
  - **Semente:** qualquer texto reproduz o mesmo tabuleiro; em branco (ou com
    o check **aleatória** ligado), sorteia uma semente nova a cada geração (e a
    escreve no campo, para reproduzir depois).
  - **Resolver** anima o solver; o seletor ao lado escolhe o modo:
    `dedução` (avança sempre, usando a solução conhecida — nunca retrocede) ou
    `busca real` (resolve só pelas dicas, com palpites e **backtracking** —
    mostra o solver "lutando"; em tabuleiros difíceis grandes o trace é
    limitado e ao fim ele salta para a solução).
  - **Dificuldade:** `Nenhuma` mostra todas as dicas; `Fácil`/`Médio`/`Difícil`
    removem dicas progressivamente (sempre mantendo solução única).
  - **Método** (algoritmo de redução de dicas — todos mantêm solução única; a
    semente não entra no método, então dá para comparar os três no MESMO laço):
    - `Guloso` — remove dica a dica (O(n) chamadas do solver); resultado
      próximo do mínimo, mais lento em tabuleiros grandes.
    - `Busca binária` — remove o maior prefixo embaralhado por rodada via
      binária O(log n); bem mais rápido (10×+ em tabuleiros grandes), com
      algumas dicas a mais.
    - `CEGAR` — bottom-up guiado por contraexemplo; tende ao menor número de
      dicas, porém o mais lento.
    O rodapé mostra `nº dicas · método · tempo` para comparar.
- **Tabuleiro:** clique numa aresta para traçar; clique de novo para apagar.
  Arestas **inviáveis** aparecem esmaecidas (ex.: as 4 ao redor de um `0`, ou as
  que bifurcariam um vértice que já tem dois traços). Traços que violam uma
  regra ficam vermelhos. Ao fechar o laço correto, ele fica verde.

## Formato do CSV

Uma linha por registro, primeira coluna identifica a seção. As arestas são
identificadas por `H:r:c` (liga o ponto `(r,c)` ao `(r,c+1)`) e `V:r:c` (liga
`(r,c)` ao `(r+1,c)`).

```
section,a,b,c,d
meta,<linhas>,<colunas>,<semente>,<dificuldade>
clue,<r>,<c>,<valor>           # uma por célula com dica
sol,<chaveAresta>              # arestas da solução (laço)
line,<chaveAresta>            # arestas traçadas pelo jogador (estado atual)
move,<idx>,<chaveAresta>,<add|remove>   # histórico de movimentos (desfazer/refazer)
```

Importar restaura o tabuleiro, o estado atual e o histórico de movimentos.

## Deploy

Site estático: basta copiar `index.html`, `css/` e `js/` (sem os
`js/*test*`/`js/*fuzz*` e sem `preview_*.png`) para a raiz web do subdomínio
no servidor.
