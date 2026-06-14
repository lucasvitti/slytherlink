/*
 * core.js — motor do Slitherlink no navegador.
 *
 * Porta para JavaScript o essencial do projeto Python: geração construtiva
 * de um laço (contorno de uma região cultivada), derivação das dicas, solver
 * por propagação + backtracking (oráculo de unicidade) e redução das dicas
 * por nível de dificuldade.
 *
 * Modelo de coordenadas (rows x cols CÉLULAS):
 *   - pontos (dots): (rows+1) x (cols+1), dot(r,c)
 *   - aresta horizontal H(r,c): liga dot(r,c)-dot(r,c+1)   r in [0,rows], c in [0,cols-1]
 *   - aresta vertical   V(r,c): liga dot(r,c)-dot(r+1,c)   r in [0,rows-1], c in [0,cols]
 *   - célula(r,c) tem as arestas H(r,c) topo, H(r+1,c) base, V(r,c) esq, V(r,c+1) dir
 *   - id textual da aresta: "H:r:c" ou "V:r:c"  (usado na UI e no CSV)
 *
 * VISÃO GERAL DO PIPELINE (ver generatePuzzle):
 *   1. generateLoop  — cultiva uma região de células e extrai seu contorno
 *                      (um único laço simples, por construção).
 *   2. cluesFromLoop — conta, para cada célula, quantas das suas 4 arestas
 *                      pertencem ao laço (a "dica" 0..4).
 *   3. countSolutions — solver que conta soluções até um limite; usado como
 *                      ORÁCULO DE UNICIDADE (count === 1 ⇒ puzzle válido).
 *   4. reduceClues*  — remove o máximo de dicas mantendo a solução única
 *                      (três estratégias: gulosa, binária, CEGAR).
 *
 * TEORIA-CHAVE (detalhada nas funções):
 *   - Propagação por regras locais: grau de vértice 0/2 e contagem de dica
 *     da célula podem FORÇAR arestas a LINHA ou VAZIO sem adivinhar.
 *   - União-busca (union-find) SEM compressão de caminho para detectar quando
 *     o laço fecha — precisa ser reversível no backtracking (ver find/setEdge).
 *   - Monotonicidade da remoção de dicas: tirar dicas só pode AUMENTAR o
 *     conjunto de soluções, o que valida a busca binária por k dicas.
 *
 * Roda tanto no navegador (window.SL) quanto no Node (module.exports).
 */
(function (root) {
  'use strict';

  // ----------------------------------------------------------------- RNG
  // Gerador pseudoaleatório SEMEADO e determinístico: a mesma chave produz
  // sempre a mesma sequência, para que um puzzle seja reprodutível pela seed.
  //
  // Composição em dois estágios:
  //   - xmur3: faz o hash de uma string em uma semente inteira de 32 bits.
  //   - mulberry32: PRNG rápido que, a partir dessa semente, emite floats.

  /**
   * Hash de string -> função geradora de semente inteira (algoritmo xmur3).
   * @param {string} str  texto-chave (ex.: "slither|7x7|medio").
   * @returns {function(): number}  função que, a cada chamada, devolve um
   *   inteiro de 32 bits sem sinal derivado do hash (usada como semente).
   */
  function xmur3(str) {
    let h = 1779033703 ^ str.length;
    for (let i = 0; i < str.length; i++) {
      h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
      h = (h << 13) | (h >>> 19);
    }
    return function () {
      h = Math.imul(h ^ (h >>> 16), 2246822507);
      h = Math.imul(h ^ (h >>> 13), 3266489909);
      h ^= h >>> 16;
      return h >>> 0;
    };
  }

  /**
   * PRNG mulberry32: a partir de um estado inteiro de 32 bits, devolve uma
   * função que emite floats em [0, 1) e avança o estado interno a cada chamada.
   * @param {number} a  semente/estado inicial de 32 bits.
   * @returns {function(): number}  gerador de floats em [0, 1).
   */
  function mulberry32(a) {
    return function () {
      a |= 0;
      a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /**
   * Constrói um RNG semeado a partir de uma chave (string). Encadeia
   * xmur3 -> mulberry32 e expõe utilitários comuns.
   * @param {string|number} chave  semente lógica do puzzle.
   * @returns {{float: function(): number, int: function(number): number,
   *            shuffle: function(Array): Array, pick: function(Array): *}}
   *   - float():      float em [0, 1)
   *   - int(n):       inteiro em [0, n)
   *   - shuffle(arr): embaralha arr in-place (Fisher-Yates) e o devolve
   *   - pick(a):      elemento aleatório de a
   */
  function makeRng(chave) {
    const seedFn = xmur3(String(chave));
    const rand = mulberry32(seedFn());
    function int(n) {
      return Math.floor(rand() * n);
    }
    // Embaralhamento Fisher-Yates: percorre de trás para frente trocando cada
    // posição com uma anterior (ou ela mesma) sorteada uniformemente.
    function shuffle(arr) {
      for (let i = arr.length - 1; i > 0; i--) {
        const j = int(i + 1);
        const t = arr[i];
        arr[i] = arr[j];
        arr[j] = t;
      }
      return arr;
    }
    return { float: rand, int, shuffle, pick: (a) => a[int(a.length)] };
  }

  // ------------------------------------------------------ ids de arestas
  // Chave textual de uma aresta. "H:r:c" = aresta horizontal entre os pontos
  // (r,c) e (r,c+1); "V:r:c" = aresta vertical entre (r,c) e (r+1,c). É a
  // identificação usada na UI e no CSV (estável e legível).
  function hKey(r, c) { return 'H:' + r + ':' + c; }
  function vKey(r, c) { return 'V:' + r + ':' + c; }

  // ----------------------------------------------- topologia do tabuleiro
  /**
   * Pré-calcula toda a estrutura combinatória do tabuleiro rows x cols.
   * O solver opera sobre ÍNDICES INTEIROS de arestas/pontos (rápido, cabe em
   * arrays tipados); as chaves textuais ("H:r:c") são só para UI/CSV.
   *
   * Numeração das arestas: primeiro todas as horizontais (nH delas), depois
   * todas as verticais (nV delas), num único espaço de índices [0, nE).
   *
   * @param {number} rows  número de linhas de células.
   * @param {number} cols  número de colunas de células.
   * @returns {object} topo com, entre outros:
   *   - nH, nV, nE: contagens de arestas (horizontais, verticais, total)
   *   - nDots: número de pontos = (rows+1)*(cols+1)
   *   - edgeEnds[e]: par [dotA, dotB] dos pontos que a aresta e conecta
   *   - edgeKey[e]: chave textual da aresta e
   *   - dotEdges[d]: lista de índices de arestas incidentes ao ponto d
   *   - cellEdges(r,c): as 4 arestas da célula (topo, base, esq, dir)
   *   - hIdx/vIdx: mapeiam (r,c) -> índice de aresta
   *   - keyToIdx: chave textual -> índice de aresta
   */
  function buildTopology(rows, cols) {
    const nH = (rows + 1) * cols;
    const nV = rows * (cols + 1);
    const nE = nH + nV;
    const nDots = (rows + 1) * (cols + 1);

    // Mapas (r,c) -> índice. dot indexa pontos; hIdx as horizontais (a partir
    // de 0); vIdx as verticais (deslocadas por nH para virem depois delas).
    const dot = (r, c) => r * (cols + 1) + c;
    const hIdx = (r, c) => r * cols + c;
    const vIdx = (r, c) => nH + r * (cols + 1) + c;

    const edgeEnds = new Array(nE);
    const edgeKey = new Array(nE);
    const dotEdges = Array.from({ length: nDots }, () => []);

    // Arestas horizontais: H(r,c) liga (r,c)-(r,c+1). Registra extremidades,
    // chave textual e incidência nos dois pontos.
    for (let r = 0; r <= rows; r++) {
      for (let c = 0; c < cols; c++) {
        const e = hIdx(r, c);
        edgeEnds[e] = [dot(r, c), dot(r, c + 1)];
        edgeKey[e] = hKey(r, c);
        dotEdges[dot(r, c)].push(e);
        dotEdges[dot(r, c + 1)].push(e);
      }
    }
    // Arestas verticais: V(r,c) liga (r,c)-(r+1,c). Mesma ideia.
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c <= cols; c++) {
        const e = vIdx(r, c);
        edgeEnds[e] = [dot(r, c), dot(r + 1, c)];
        edgeKey[e] = vKey(r, c);
        dotEdges[dot(r, c)].push(e);
        dotEdges[dot(r + 1, c)].push(e);
      }
    }

    // As 4 arestas de cada célula (índices), na ordem topo, base, esq, dir
    const cellEdges = (r, c) => [hIdx(r, c), hIdx(r + 1, c), vIdx(r, c), vIdx(r, c + 1)];

    // Índice inverso: chave textual -> índice inteiro de aresta.
    const keyToIdx = {};
    for (let e = 0; e < nE; e++) keyToIdx[edgeKey[e]] = e;

    return { rows, cols, nH, nV, nE, nDots, edgeEnds, edgeKey, dotEdges,
             cellEdges, hIdx, vIdx, keyToIdx };
  }

  // --------------------------------------------------- gerador do laço
  /**
   * Cultiva uma região aleatória de células e devolve o CONTORNO dessa região
   * (conjunto de chaves de aresta). Por construção o contorno é um único laço
   * simples — é assim que garantimos um Slitherlink válido.
   *
   * IDEIA (crescimento por região, "spread-then-wiggle"):
   *   Mantemos um conjunto `inside` de células dentro da região, começando por
   *   uma semente no centro, e o expandimos célula a célula a partir de uma
   *   fronteira. Cada célula candidata só é aceita se preservar duas invariantes
   *   que garantem que o contorno seja UM laço simples:
   *     (a) semToqueDeCanto: a região nunca se toca apenas pela diagonal
   *         (isso criaria um vértice de grau 4 — laço não simples);
   *     (b) semBuraco: o complemento (células de fora) permanece conexo e
   *         ligado à borda (sem ilhas internas — senão haveria 2 laços).
   *
   *   O crescimento tem DUAS FASES:
   *     1. ESPALHAR: enquanto a bounding box não cobre ~85% do tabuleiro,
   *        prefere candidatas que mais ESTENDEM a caixa, empurrando o laço de
   *        ponta a ponta (evita deixar um canto inteiro de células com dica 0).
   *     2. WIGGLE: depois de cobrir, prefere candidatas de maior GANHO de
   *        perímetro (4 - 2*vizinhasDentro), tornando o laço mais sinuoso e
   *        interessante. Para quando o perímetro atinge o alvo e a caixa cobre.
   *
   * @param {number} rows  linhas de células.
   * @param {number} cols  colunas de células.
   * @param {object} rng   RNG semeado (ver makeRng).
   * @param {object} [opts]
   * @param {number} [opts.densidade=0.75]  controla o alvo de perímetro
   *   (laços maiores/mais longos com valores maiores).
   * @param {number} [opts.ganancia=0.85]   probabilidade, na fase wiggle, de
   *   escolher gananciosamente a candidata de maior ganho de perímetro.
   * @returns {Set<string>}  conjunto de chaves de aresta do laço.
   */
  function generateLoop(rows, cols, rng, opts) {
    opts = opts || {};
    const densidade = opts.densidade != null ? opts.densidade : 0.75;
    const ganancia = opts.ganancia != null ? opts.ganancia : 0.85;

    // inside[r][c] = a célula (r,c) pertence à região cultivada.
    const inside = Array.from({ length: rows }, () => new Array(cols).fill(false));
    const valid = (r, c) => r >= 0 && r < rows && c >= 0 && c < cols;

    // Quantas das 4 vizinhas ortogonais de (r,c) já estão dentro. Usado para o
    // ganho de perímetro: incluir (r,c) acrescenta 4 arestas novas e remove 2
    // por vizinha já dentro -> ganho = 4 - 2*vizDentro.
    const vizDentro = (r, c) => {
      let n = 0;
      if (valid(r - 1, c) && inside[r - 1][c]) n++;
      if (valid(r + 1, c) && inside[r + 1][c]) n++;
      if (valid(r, c - 1) && inside[r][c - 1]) n++;
      if (valid(r, c + 1) && inside[r][c + 1]) n++;
      return n;
    };

    // Rejeita "toque só de canto": uma diagonal dentro cujas DUAS células
    // ortogonais entre ela e (r,c) estão fora. Isso faria duas partes da região
    // se encontrarem só num ponto (vértice de grau 4) — laço não simples.
    const semToqueDeCanto = (r, c) => {
      const diag = [[-1, -1], [-1, 1], [1, -1], [1, 1]];
      for (const [dr, dc] of diag) {
        const lr = r + dr, lc = c + dc;
        if (valid(lr, lc) && inside[lr][lc]) {
          const ok1 = valid(r + dr, c) && inside[r + dr][c];
          const ok2 = valid(r, c + dc) && inside[r][c + dc];
          if (!ok1 && !ok2) return false;
        }
      }
      return true;
    };

    // Teste "sem buraco": se incluíssemos (r,c), as células de FORA continuariam
    // todas conexas e ligadas à borda? Um flood fill começando pelas células de
    // fora que tocam a borda deve alcançar TODAS as células de fora. Se sobrar
    // alguma, ela seria uma ilha interna -> o contorno teria mais de um laço.
    // Faz a inclusão de (r,c) temporariamente e a desfaz antes de retornar.
    const semBuraco = (r, c) => {
      inside[r][c] = true;

      // conta o total de células de fora
      let foraTotal = 0;
      for (let i = 0; i < rows; i++) {
        for (let j = 0; j < cols; j++) {
          if (!inside[i][j]) foraTotal++;
        }
      }
      if (foraTotal === 0) {
        inside[r][c] = false;
        return true;
      }

      // semeia o flood fill com toda célula de fora que esteja na borda
      const vis = Array.from({ length: rows }, () => new Array(cols).fill(false));
      const pilha = [];
      for (let i = 0; i < rows; i++) {
        for (let j = 0; j < cols; j++) {
          const naBorda = (i === 0 || i === rows - 1 || j === 0 || j === cols - 1);
          if (naBorda && !inside[i][j] && !vis[i][j]) {
            vis[i][j] = true;
            pilha.push([i, j]);
          }
        }
      }

      // DFS pelas células de fora; conta quantas foram alcançadas
      let cont = 0;
      while (pilha.length) {
        const [pr, pc] = pilha.pop();
        cont++;
        const viz = [[pr - 1, pc], [pr + 1, pc], [pr, pc - 1], [pr, pc + 1]];
        for (const [vr, vc] of viz) {
          if (valid(vr, vc) && !inside[vr][vc] && !vis[vr][vc]) {
            vis[vr][vc] = true;
            pilha.push([vr, vc]);
          }
        }
      }

      inside[r][c] = false;
      // sem buraco sse o flood alcançou TODAS as células de fora
      return cont === foraTotal;
    };

    // alvo de perímetro: quanto maior a densidade, mais longo o laço.
    const alvo = densidade * (rows + 1) * (cols + 1);

    // semente perto do centro ajuda a região a alcançar todas as bordas
    const l0 = Math.floor(rows / 2), c0 = Math.floor(cols / 2);
    inside[l0][c0] = true;
    let perimetro = 4;

    // bounding box da região (para forçá-la a cobrir o tabuleiro inteiro)
    let minR = l0, maxR = l0, minC = c0, maxC = c0;

    // fronteira = células de fora adjacentes à região (candidatas a entrar),
    // guardadas como strings "r,c" num Set para deduplicar.
    const fronteira = new Set();
    const addFront = (r, c) => {
      if (valid(r, c) && !inside[r][c]) fronteira.add(r + ',' + c);
    };
    addFront(l0 - 1, c0);
    addFront(l0 + 1, c0);
    addFront(l0, c0 - 1);
    addFront(l0, c0 + 1);

    // A região cresce em duas fases: enquanto NÃO cobre quase todo o tabuleiro
    // (bounding box < ~85% em cada eixo), prefere células que ESTENDEM a caixa
    // (espalha o laço de ponta a ponta — evita deixar uma região de 0s); depois
    // de cobrir, volta à preferência "wiggly" (perímetro máximo) para detalhe.
    // Para quando o perímetro atinge o alvo E a região já cobre o tabuleiro.
    const cobre = () => (maxR - minR >= (rows - 1) * 0.85) && (maxC - minC >= (cols - 1) * 0.85);

    while (fronteira.size && (perimetro < alvo || !cobre())) {
      const cands = [...fronteira].map((s) => s.split(',').map(Number));
      let lista;
      if (!cobre()) {
        // prioriza quem mais estende o bounding box (alcança bordas distantes)
        let best = -1;
        for (const [r, c] of cands) {
          const ext = Math.max(0, minR - r) + Math.max(0, r - maxR)
            + Math.max(0, minC - c) + Math.max(0, c - maxC);
          if (ext > best) best = ext;
        }
        lista = best > 0
          ? cands.filter(([r, c]) => (Math.max(0, minR - r) + Math.max(0, r - maxR)
            + Math.max(0, minC - c) + Math.max(0, c - maxC)) === best)
          : cands.slice();
      } else {
        let ganhoMax = -Infinity;
        for (const [r, c] of cands) ganhoMax = Math.max(ganhoMax, 4 - 2 * vizDentro(r, c));
        if (rng.float() < ganancia && ganhoMax > 0) {
          lista = cands.filter(([r, c]) => 4 - 2 * vizDentro(r, c) === ganhoMax);
        } else {
          lista = cands.slice();
        }
      }
      rng.shuffle(lista);
      // tenta também o resto da fronteira se as preferidas falharem
      const resto = cands.filter((rc) => !lista.includes(rc));
      const ordem = lista.concat(resto);

      // escolhe a primeira candidata que preserva as duas invariantes
      let escolhida = null;
      for (const [r, c] of ordem) {
        if (semToqueDeCanto(r, c) && semBuraco(r, c)) {
          escolhida = [r, c];
          break;
        }
      }
      if (!escolhida) break;

      // efetiva a inclusão: atualiza perímetro, bounding box e fronteira
      const [er, ec] = escolhida;
      perimetro += 4 - 2 * vizDentro(er, ec);
      inside[er][ec] = true;
      if (er < minR) minR = er;
      if (er > maxR) maxR = er;
      if (ec < minC) minC = ec;
      if (ec > maxC) maxC = ec;
      fronteira.delete(er + ',' + ec);
      addFront(er - 1, ec);
      addFront(er + 1, ec);
      addFront(er, ec - 1);
      addFront(er, ec + 1);
    }

    // Contorno: para cada célula DENTRO, toda aresta que a separa de uma
    // vizinha de FORA (ou da borda do tabuleiro) pertence ao laço.
    const loop = new Set();
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (!inside[r][c]) continue;
        if (!(valid(r - 1, c) && inside[r - 1][c])) loop.add(hKey(r, c));
        if (!(valid(r + 1, c) && inside[r + 1][c])) loop.add(hKey(r + 1, c));
        if (!(valid(r, c - 1) && inside[r][c - 1])) loop.add(vKey(r, c));
        if (!(valid(r, c + 1) && inside[r][c + 1])) loop.add(vKey(r, c + 1));
      }
    }
    return loop;
  }

  /**
   * Deriva a matriz de dicas (rows x cols) a partir do conjunto de arestas do
   * laço. A dica de cada célula é quantas das suas 4 arestas estão no laço (0..4).
   * @param {number} rows
   * @param {number} cols
   * @param {Set<string>} loop  conjunto de chaves de aresta do laço.
   * @returns {number[][]}  matriz de dicas.
   */
  function cluesFromLoop(rows, cols, loop) {
    const clues = Array.from({ length: rows }, () => new Array(cols).fill(0));
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        let n = 0;
        if (loop.has(hKey(r, c))) n++;
        if (loop.has(hKey(r + 1, c))) n++;
        if (loop.has(vKey(r, c))) n++;
        if (loop.has(vKey(r, c + 1))) n++;
        clues[r][c] = n;
      }
    }
    return clues;
  }

  // -------------------------------------------------------- solver
  // Estado de cada aresta durante a busca.
  const UNKNOWN = 0, LINE = 1, EMPTY = 2;

  /**
   * Conta as soluções de um puzzle até um limite, servindo como ORÁCULO DE
   * UNICIDADE: se devolve count === 1 com complete === true, o puzzle tem
   * solução única; count >= 2 é ambíguo; complete === false significa que a
   * busca estourou maxNodes (inconclusivo).
   *
   * ALGORITMO — propagação de restrições + backtracking:
   *   Cada aresta está em UNKNOWN/LINE/EMPTY. Atribuir uma aresta dispara a
   *   PROPAGAÇÃO de deduções forçadas pelas regras locais (ver regraVertice /
   *   regraCelula). Quando nada mais é forçado, ESCOLHE uma aresta livre e
   *   tenta LINE e depois EMPTY (backtracking), desfazendo o estado entre as
   *   tentativas. Vários cortes podam a árvore cedo:
   *     - contradição imediata em vértice (grau > 2) ou célula (dica excedida);
   *     - conectividade (conectavel): pontas soltas devem poder se ligar;
   *     - detecção de laço fechado via UNIÃO-BUSCA.
   *
   *   DETECÇÃO DE LAÇO ÚNICO (union-find): cada ponto começa em sua própria
   *   componente; ligar uma aresta LINE une as componentes das suas pontas.
   *   Quando uma aresta LINE fecha um ciclo (as duas pontas já na mesma
   *   componente) e, nesse instante, TODAS as arestas LINE pertencem a essa
   *   componente (totalIn === tam[raiz]) e todas as dicas estão satisfeitas
   *   (nSat === nCells), encontramos uma solução: um único laço que respeita
   *   as dicas.
   *
   * @param {number} rows
   * @param {number} cols
   * @param {number[][]} clues  matriz de dicas; null/-1 = célula sem dica.
   * @param {number} [limit=2]  para a busca ao atingir tantas soluções.
   * @param {number} [maxNodes=200000]  teto de nós da busca (anti-travamento).
   * @returns {{count: number, solutions: Set<string>[], complete: boolean}}
   *   count: nº de soluções achadas (até limit); solutions: cada uma como Set
   *   de chaves de aresta; complete: false se a busca foi truncada por maxNodes.
   */
  function countSolutions(rows, cols, clues, limit, maxNodes) {
    limit = limit || 2;
    maxNodes = maxNodes || 200000;
    const topo = buildTopology(rows, cols);
    const { nE, nDots, edgeEnds, dotEdges, edgeKey } = topo;

    // Indexa só as células COM dica (id compacto 0..nCells-1):
    //   cellClue[id] = valor da dica; cellEdges[id] = suas 4 arestas;
    //   edgeCells[e] = ids das células com dica que tocam a aresta e.
    const cellClue = [];
    const cellEdges = [];
    const edgeCells = Array.from({ length: nE }, () => []);
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const k = clues[r][c];
        if (k == null || k < 0) continue;
        const id = cellClue.length;
        const es = topo.cellEdges(r, c);
        cellClue.push(k);
        cellEdges.push(es);
        for (const e of es) edgeCells[e].push(id);
      }
    }
    const nCells = cellClue.length;

    // Estado por aresta e contadores incrementais mantidos pela busca:
    //   state[e]: UNKNOWN/LINE/EMPTY
    //   inV[v]:   nº de arestas LINE incidentes ao vértice v (grau do laço)
    //   unkV[v]:  nº de arestas UNKNOWN incidentes a v (inicia = grau total)
    //   inC[cel]: nº de arestas LINE na célula cel
    //   unkC[cel]:nº de arestas UNKNOWN na célula cel (inicia 4)
    const state = new Uint8Array(nE);
    const inV = new Int16Array(nDots);
    const unkV = new Int16Array(nDots);
    for (let d = 0; d < nDots; d++) unkV[d] = dotEdges[d].length;
    const inC = new Int16Array(nCells);
    const unkC = new Int16Array(nCells).fill(4);

    // Union-find sobre os pontos (pai[]) com união por tamanho (tam[]).
    // Inicialmente cada ponto é sua própria componente.
    const pai = new Int32Array(nDots);
    for (let d = 0; d < nDots; d++) pai[d] = d;
    const tam = new Int32Array(nDots).fill(1);

    // pontas: vértices de grau 1 (extremidades de caminhos abertos).
    // totalIn: total de arestas LINE colocadas.
    // nSat: nº de células cuja dica já está exatamente satisfeita (dica 0 já
    //   nasce satisfeita).
    const pontas = new Set();
    let totalIn = 0;
    let nSat = 0;
    for (let i = 0; i < nCells; i++) if (cellClue[i] === 0) nSat++;

    // Trilhas para desfazer (backtracking):
    //   trilha:   arestas atribuídas, em ordem (para reverter state/contadores)
    //   trilhaUf: uniões feitas, em ordem (para reverter pai/tam)
    //   fila:     itens (vértices/células) pendentes de re-checagem na propagação
    const trilha = [];
    const trilhaUf = [];
    const fila = [];

    let nSol = 0;
    const solucoes = [];
    let nodes = 0;
    let completo = true;

    // find SEM compressão de caminho — e isso é PROPOSITAL e necessário.
    // A busca desfaz uniões no backtracking (trilhaUf guarda exatamente os
    // pares (filho, pai) criados). A compressão de caminho mutaria pai[] de
    // nós que NÃO estão registrados na trilhaUf, e ao desfazer não daria para
    // restaurá-los — corrompendo a união-busca. Com união por tamanho, find
    // continua O(log n), barato o bastante e totalmente reversível.
    function find(x) {
      while (pai[x] !== x) x = pai[x];
      return x;
    }

    /**
     * Atribui um valor (LINE/EMPTY) a uma aresta UNKNOWN e atualiza todos os
     * contadores incrementais, detectando contradições e fechamento de laço.
     * @param {number} e    índice da aresta.
     * @param {number} val  LINE ou EMPTY.
     * @returns {boolean} false se a atribuição é INCONSISTENTE (contradição) ou
     *   fechou um ciclo (em ambos os casos a busca não deve seguir por aqui);
     *   true se ficou consistente e a propagação pode continuar.
     */
    function setEdge(e, val) {
      // já atribuída: ok só se for o mesmo valor (idempotência da propagação)
      if (state[e] !== UNKNOWN) return state[e] === val;
      state[e] = val;
      trilha.push(e);

      // a aresta deixa de ser UNKNOWN para seus 2 vértices e células com dica;
      // reenfileira ambos para reavaliação. O bit 0x40000000 marca "é vértice".
      const [v1, v2] = edgeEnds[e];
      unkV[v1]--; unkV[v2]--;
      fila.push(v1 | 0x40000000);
      fila.push(v2 | 0x40000000);
      for (const cel of edgeCells[e]) {
        unkC[cel]--;
        fila.push(cel);
      }

      // EMPTY não altera grau/dica/união — nada mais a verificar.
      if (val === EMPTY) return true;

      // --- aresta LINE: atualiza graus, dicas e detecta contradições ---
      totalIn++;
      let contra = false;

      // grau dos vértices: 1 cria uma ponta; 2 fecha a ponta; >2 é impossível.
      for (const v of [v1, v2]) {
        const iv = ++inV[v];
        if (iv === 1) pontas.add(v);
        else if (iv === 2) pontas.delete(v);
        else contra = true;
      }

      // contagem das células: ic===k satisfaz a dica; ic===k+1 a "des-satisfaz";
      // ic>k é dica excedida (contradição).
      for (const cel of edgeCells[e]) {
        const ic = ++inC[cel];
        const k = cellClue[cel];
        if (ic === k) nSat++;
        else if (ic === k + 1) nSat--;
        if (ic > k) contra = true;
      }
      if (contra) return false;

      // união das pontas. Se já estavam na mesma componente, esta LINE FECHA
      // um ciclo: testa se é uma solução completa (todas as LINE no ciclo e
      // todas as dicas satisfeitas). Em qualquer caso, não se une (retorna
      // false: não há mais o que propagar por este ramo).
      let r1 = find(v1), r2 = find(v2);
      if (r1 === r2) {
        if (totalIn === tam[r1] && nSat === nCells) {
          nSol++;
          const s = new Set();
          for (let i = 0; i < nE; i++) if (state[i] === LINE) s.add(edgeKey[i]);
          solucoes.push(s);
        }
        return false;
      }

      // une por tamanho (a menor componente passa a apontar para a maior) e
      // registra a união para poder desfazê-la no backtracking.
      if (tam[r1] < tam[r2]) { const t = r1; r1 = r2; r2 = t; }
      pai[r2] = r1;
      tam[r1] += tam[r2];
      trilhaUf.push([r2, r1]);
      return true;
    }

    /**
     * Desfaz todas as atribuições e uniões feitas depois dos marcadores dados,
     * restaurando exatamente o estado anterior (rollback do backtracking).
     * @param {number} mE  tamanho de `trilha` a preservar.
     * @param {number} mU  tamanho de `trilhaUf` a preservar.
     */
    function desfaz(mE, mU) {
      // primeiro desfaz as uniões (ordem inversa): a raiz volta a apontar p/ si
      while (trilhaUf.length > mU) {
        const [r2, r1] = trilhaUf.pop();
        tam[r1] -= tam[r2];
        pai[r2] = r2;
      }
      // depois reverte cada aresta, espelhando os incrementos feitos em setEdge
      while (trilha.length > mE) {
        const e = trilha.pop();
        const val = state[e];
        state[e] = UNKNOWN;
        const [v1, v2] = edgeEnds[e];
        unkV[v1]++; unkV[v2]++;
        for (const cel of edgeCells[e]) unkC[cel]++;
        if (val === LINE) {
          totalIn--;
          for (const v of [v1, v2]) {
            const iv = --inV[v];
            if (iv === 1) pontas.add(v);
            else if (iv === 0) pontas.delete(v);
          }
          for (const cel of edgeCells[e]) {
            const ic = --inC[cel];
            const k = cellClue[cel];
            if (ic === k) nSat++;
            else if (ic === k - 1) nSat--;
          }
        }
      }
    }

    /**
     * Regra de propagação no VÉRTICE v. Num laço, todo vértice tem grau 0 ou 2.
     * Conforme o grau atual (inV) e quantas arestas ainda estão livres (unkV):
     *   - grau 2: o vértice está completo -> todas as livres viram EMPTY;
     *   - grau 1 (uma ponta): se sobra 1 livre, ela DEVE fechar o par -> LINE;
     *     se não sobra nenhuma, é beco sem saída -> contradição;
     *   - grau 0: se sobra só 1 livre, ela não pode ser a única -> EMPTY.
     * @returns {boolean} false em caso de contradição.
     */
    function regraVertice(v) {
      const iv = inV[v], uv = unkV[v];
      if (iv > 2) return false;
      if (iv === 2) {
        if (uv) for (const e of dotEdges[v])
          if (state[e] === UNKNOWN && !setEdge(e, EMPTY)) return false;
      } else if (iv === 1) {
        if (uv === 0) return false;
        if (uv === 1) for (const e of dotEdges[v])
          if (state[e] === UNKNOWN) return setEdge(e, LINE);
      } else { // iv === 0
        if (uv === 1) for (const e of dotEdges[v])
          if (state[e] === UNKNOWN) return setEdge(e, EMPTY);
      }
      return true;
    }

    /**
     * Regra de propagação na CÉLULA cel, com dica k. Sejam ic = arestas já LINE
     * e uc = arestas ainda UNKNOWN:
     *   - ic > k ou ic+uc < k: impossível satisfazer a dica -> contradição;
     *   - ic === k: a dica já está cheia -> todas as livres viram EMPTY;
     *   - ic+uc === k: todas as livres são necessárias -> viram LINE.
     * @returns {boolean} false em caso de contradição.
     */
    function regraCelula(cel) {
      const ic = inC[cel], uc = unkC[cel], k = cellClue[cel];
      if (ic > k || ic + uc < k) return false;
      if (uc === 0) return true;
      if (ic === k) {
        for (const e of cellEdges[cel])
          if (state[e] === UNKNOWN && !setEdge(e, EMPTY)) return false;
      } else if (ic + uc === k) {
        for (const e of cellEdges[cel])
          if (state[e] === UNKNOWN && !setEdge(e, LINE)) return false;
      }
      return true;
    }

    /**
     * Laço de propagação: drena a `fila` aplicando regraVertice/regraCelula até
     * estabilizar (ponto fixo) ou achar contradição. O bit 0x40000000 no item
     * distingue vértice (com a flag) de célula (sem). Como setEdge reenfileira
     * os itens afetados, as deduções se encadeiam até nada mais ser forçado.
     * @returns {boolean} false se alguma regra detectou contradição.
     */
    function propaga() {
      while (fila.length) {
        const x = fila.pop();
        let ok;
        if (x & 0x40000000) ok = regraVertice(x & 0x3FFFFFFF);
        else ok = regraCelula(x);
        if (!ok) { fila.length = 0; return false; }
      }
      return true;
    }

    /**
     * Poda por CONECTIVIDADE: a partir de uma ponta solta, faz um flood pelas
     * arestas não-EMPTY (LINE ou ainda UNKNOWN). Se algum vértice que já tem
     * arestas LINE ficar inalcançável, o caminho atual nunca poderá fechar num
     * único laço -> ramo morto. Quando há <= 2 pontas, não há o que checar.
     * (SL._noPrune desliga a poda; usado em testes.)
     * @returns {boolean} false se o estado é comprovadamente inviável.
     */
    function conectavel() {
      if (SL && SL._noPrune) return true;
      if (pontas.size <= 2) return true;
      const inicio = pontas.values().next().value;
      const vis = new Uint8Array(nDots);
      vis[inicio] = 1;
      const pilha = [inicio];
      while (pilha.length) {
        const v = pilha.pop();
        for (const e of dotEdges[v]) {
          if (state[e] === EMPTY) continue;
          const [a, b] = edgeEnds[e];
          const w = a === v ? b : a;
          if (!vis[w]) {
            vis[w] = 1;
            pilha.push(w);
          }
        }
      }
      for (let v = 0; v < nDots; v++) if (inV[v] && !vis[v]) return false;
      return true;
    }

    /**
     * Heurística de escolha da próxima aresta a ramificar. Preferência:
     *   1. estender uma ponta solta (mantém o caminho contínuo, poda mais);
     *   2. completar uma célula com dica ainda não satisfeita;
     *   3. qualquer aresta UNKNOWN restante.
     * @returns {number} índice da aresta, ou -1 se não há nenhuma UNKNOWN.
     */
    function escolheAresta() {
      for (const v of pontas)
        for (const e of dotEdges[v]) if (state[e] === UNKNOWN) return e;
      for (let cel = 0; cel < nCells; cel++)
        if (unkC[cel]) for (const e of cellEdges[cel]) if (state[e] === UNKNOWN) return e;
      for (let e = 0; e < nE; e++) if (state[e] === UNKNOWN) return e;
      return -1;
    }

    /**
     * Núcleo recursivo do backtracking. Em cada nó: para se já atingiu o limite
     * de soluções ou estourou maxNodes; poda por conectividade; escolhe uma
     * aresta e tenta LINE e depois EMPTY, propagando e desfazendo entre as
     * tentativas. As soluções são contabilizadas dentro de setEdge ao fechar
     * o laço.
     */
    function busca() {
      if (nSol >= limit || !completo) return;
      if (++nodes > maxNodes) { completo = false; return; }
      if (!conectavel()) return;
      const e = escolheAresta();
      if (e < 0) return;
      for (const val of [LINE, EMPTY]) {
        const mE = trilha.length, mU = trilhaUf.length;
        let ok = setEdge(e, val);
        if (ok) ok = propaga(); else fila.length = 0;
        if (ok) busca();
        desfaz(mE, mU);
        if (nSol >= limit || !completo) return;
      }
    }

    // Propagação inicial: enfileira todas as células com dica (algumas já
    // forçam arestas de saída) e, se consistente, dispara a busca.
    for (let cel = 0; cel < nCells; cel++) fila.push(cel);
    if (propaga()) busca();
    return { count: nSol, solutions: solucoes, complete: completo };
  }

  // ----------------------------------------- redução de dicas
  /**
   * REDUÇÃO GULOSA (método padrão). Parte do mapa completo de dicas e tenta
   * remover cada dica, numa ordem aleatória; mantém a remoção apenas se o
   * puzzle continuar com solução única. Ao final, devolve uma fração das dicas
   * removidas conforme a dificuldade (mais fácil = mais dicas de volta).
   *
   * INVARIANTE DE UNICIDADE: qualquer SUPERCONJUNTO de um conjunto de dicas com
   * solução única também tem solução única (mais dicas só restringem). Por isso
   * (a) é seguro devolver dicas no fim e (b) quando a busca é INCONCLUSIVA
   * (estourou maxNodes) preferimos MANTER a dica — o puzzle pode ficar mais
   * fácil, nunca ambíguo.
   *
   * @param {number} rows
   * @param {number} cols
   * @param {number[][]} fullClues  mapa completo de dicas (0..4 em toda célula).
   * @param {Set<string>|string[]} solutionLoop  laço solução (não usado aqui;
   *   presente para padronizar a assinatura com os outros métodos).
   * @param {object} rng  RNG semeado.
   * @param {'facil'|'medio'|'dificil'} dificuldade  controla quantas dicas
   *   voltam (facil=0.75, medio=0.4, dificil=0.0).
   * @param {number} [maxNodes=40000]  teto por chamada do solver.
   * @returns {number[][]}  matriz do puzzle (-1 = célula sem dica).
   */
  function reduceClues(rows, cols, fullClues, solutionLoop, rng, dificuldade, maxNodes) {
    const fracVolta = { dificil: 0.0, medio: 0.4, facil: 0.75 };
    const f = fracVolta[dificuldade] != null ? fracVolta[dificuldade] : 0.4;
    maxNodes = maxNodes || 40000;

    const puzzle = fullClues.map((row) => row.slice());
    const celulas = [];
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) celulas.push([r, c]);
    rng.shuffle(celulas);

    const removidas = [];
    for (const [r, c] of celulas) {
      const bak = puzzle[r][c];
      puzzle[r][c] = -1;
      const res = countSolutions(rows, cols, puzzle, 2, maxNodes);
      // count===1 && complete prova unicidade; busca inconclusiva ⇒ mantém
      // a dica por segurança (puzzle só fica mais fácil, nunca ambíguo)
      if (res.count === 1 && res.complete) {
        removidas.push([r, c]);          // pode sair de vez
      } else {
        puzzle[r][c] = bak;              // necessária para a unicidade
      }
    }

    // Devolve uma fração das removidas para suavizar a dificuldade
    rng.shuffle(removidas);
    const nVolta = Math.round(f * removidas.length);
    for (let i = 0; i < nVolta; i++) {
      const [r, c] = removidas[i];
      puzzle[r][c] = fullClues[r][c];
    }
    return puzzle;
  }

  /**
   * Helper comum: devolve uma fração das dicas removidas conforme a dificuldade
   * (mais fácil = mais dicas de volta), modificando `puzzle` in-place. Mantém a
   * unicidade (qualquer superconjunto de um conjunto único continua único).
   * @param {number[][]} puzzle  puzzle reduzido (será mutado).
   * @param {number[][]} fullClues  mapa completo de dicas.
   * @param {Array<[number,number]>} removidas  coords das dicas removidas.
   * @param {object} rng  RNG semeado.
   * @param {string} dificuldade  'facil' | 'medio' | 'dificil'.
   * @returns {number[][]}  o próprio `puzzle`.
   */
  function _devolveDicas(puzzle, fullClues, removidas, rng, dificuldade) {
    const fracVolta = { dificil: 0.0, medio: 0.4, facil: 0.75 };
    const f = fracVolta[dificuldade] != null ? fracVolta[dificuldade] : 0.4;
    rng.shuffle(removidas);
    const nVolta = Math.round(f * removidas.length);
    for (let i = 0; i < nVolta; i++) {
      const [r, c] = removidas[i];
      puzzle[r][c] = fullClues[r][c];
    }
    return puzzle;
  }

  // ----------------------------------------- redução de dicas (método 2)
  /**
   * REDUÇÃO POR BUSCA BINÁRIA (método rápido). Mesma assinatura de reduceClues.
   *
   * MONOTONICIDADE: fixada uma ordem das dicas, defina P(k) = "remover as
   * primeiras k dicas dessa ordem mantém a solução única". Como remover dicas
   * só pode AUMENTAR o conjunto de soluções, se P(k) falha então P(k') falha
   * para todo k' > k. Logo P é monótona e dá para achar o maior k válido por
   * BUSCA BINÁRIA: O(log n) chamadas do solver, contra O(n) da gulosa.
   *
   * Trade-off: troca minimalidade por velocidade — o resultado costuma ter mais
   * dicas que o guloso, pois cada rodada só remove um prefixo (limitado pela 1ª
   * dica "crítica" da ordem). Reembaralhar a cada rodada traz outras dicas para
   * a frente; repete-se até uma rodada não remover nada.
   *
   * @returns {number[][]}  matriz do puzzle (-1 = sem dica).
   */
  function reduceCluesBinaria(rows, cols, fullClues, solutionLoop, rng, dificuldade, maxNodes) {
    maxNodes = maxNodes || 40000;
    const puzzle = fullClues.map((row) => row.slice());
    const removidas = [];

    let progrediu = true;
    while (progrediu) {
      progrediu = false;

      // dicas ainda presentes, em ordem aleatória
      const restantes = [];
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          if (puzzle[r][c] >= 0) restantes.push([r, c]);
        }
      }
      rng.shuffle(restantes);

      // P(k): remover as k primeiras de `restantes` mantém a unicidade?
      const unicoRemovendo = (k) => {
        const p = puzzle.map((row) => row.slice());
        for (let i = 0; i < k; i++) {
          const [r, c] = restantes[i];
          p[r][c] = -1;
        }
        const res = countSolutions(rows, cols, p, 2, maxNodes);
        return res.count === 1 && res.complete;
      };

      // binária pelo maior k com P(k) verdadeiro (invariante: P(lo) vale)
      let lo = 0, hi = restantes.length;
      while (lo < hi) {
        const m = Math.ceil((lo + hi) / 2);
        if (unicoRemovendo(m)) lo = m; else hi = m - 1;
      }

      // efetiva a remoção desse prefixo, se houver
      if (lo > 0) {
        for (let i = 0; i < lo; i++) {
          const [r, c] = restantes[i];
          puzzle[r][c] = -1;
          removidas.push([r, c]);
        }
        progrediu = true;
      }
    }
    return _devolveDicas(puzzle, fullClues, removidas, rng, dificuldade);
  }

  // ----------------------------------------- redução de dicas (método 3)
  /**
   * REDUÇÃO POR CEGAR (CounterExample-Guided Abstraction Refinement, bottom-up).
   * Mesma assinatura de reduceClues (mais um parâmetro opcional `semente`).
   *
   * IDEIA: em vez de partir de TODAS as dicas e remover (top-down), parte de
   * POUCAS (uma fração `semente` sorteada) e vai REFINANDO: enquanto o solver
   * achar uma solução DIFERENTE do laço alvo (um "contraexemplo"), adiciona a
   * dica verdadeira em alguma célula onde o contraexemplo DIVERGE do alvo —
   * isso elimina aquele contraexemplo (e potencialmente outros). Repete até o
   * solver provar unicidade. Um cache de contraexemplos evita chamadas
   * redundantes ao solver (um contraexemplo ainda consistente com o puzzle
   * atual continua válido). Começar com algumas dicas evita o regime
   * exponencial do solver com pouquíssimas dicas.
   *
   * Ao final faz um PENTE-FINO guloso (remove o que sobrou de supérfluo) e
   * devolve dicas conforme a dificuldade.
   *
   * @param {number} [semente=0.5]  fração inicial de dicas mantidas.
   * @returns {number[][]}  matriz do puzzle (-1 = sem dica).
   */
  function reduceCluesCEGAR(rows, cols, fullClues, solutionLoop, rng, dificuldade, maxNodes, semente) {
    maxNodes = maxNodes || 40000;
    semente = semente != null ? semente : 0.5;
    const alvoSol = solutionLoop instanceof Set ? solutionLoop : new Set(solutionLoop);

    // igualdade de conjuntos de arestas (compara o laço alvo com uma solução)
    const eqSet = (a, b) => {
      if (a.size !== b.size) return false;
      for (const x of a) if (!b.has(x)) return false;
      return true;
    };

    // puzzle inicial: mantém cada dica com probabilidade `semente`
    const puzzle = fullClues.map((row) => row.map((v) => (rng.float() < semente ? v : -1)));
    const cache = [];

    // um contraexemplo (mapa de dicas `cts`) ainda é útil se for consistente
    // com as dicas atualmente presentes no puzzle
    const consistente = (cts) => {
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          if (puzzle[r][c] >= 0 && cts[r][c] !== puzzle[r][c]) return false;
        }
      }
      return true;
    };

    // adiciona ao puzzle uma dica verdadeira numa célula onde o contraexemplo
    // diverge do alvo (mata o contraexemplo). false se não houver onde divergir.
    const adicionaDica = (cts) => {
      const op = [];
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          if (puzzle[r][c] < 0 && cts[r][c] !== fullClues[r][c]) op.push([r, c]);
        }
      }
      if (!op.length) return false;
      const [r, c] = op[rng.int(op.length)];
      puzzle[r][c] = fullClues[r][c];
      return true;
    };

    // procura um contraexemplo (solução != alvo). Devolve seu mapa de dicas, ou
    // null quando a unicidade fica provada.
    const contraexemplo = () => {
      // 1. reaproveita um contraexemplo cacheado ainda consistente
      for (const cts of cache) if (consistente(cts)) return cts;

      // 2. chama o solver e filtra soluções diferentes do alvo
      const res = countSolutions(rows, cols, puzzle, 2, maxNodes);
      const alts = res.solutions.filter((s) => !eqSet(s, alvoSol));
      if (alts.length) {
        const m = cluesFromLoop(rows, cols, alts[0]);
        cache.push(m);
        return m;
      }
      if (res.complete) return null;            // unicidade provada

      // 3. inconclusivo (estourou maxNodes): aperta com uma dica aleatória e
      //    tenta de novo, para o solver convergir
      const livres = [];
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          if (puzzle[r][c] < 0) livres.push([r, c]);
        }
      }
      if (!livres.length) return null;
      const [r, c] = livres[rng.int(livres.length)];
      puzzle[r][c] = fullClues[r][c];
      return contraexemplo();
    };

    // laço de refinamento (com guarda contra loop infinito)
    let guard = 0;
    while (guard++ < rows * cols * 4) {
      const cts = contraexemplo();
      if (cts === null) break;
      if (!adicionaDica(cts)) break;
    }

    // pente-fino guloso final, depois devolve dicas conforme a dificuldade
    const celulas = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (puzzle[r][c] >= 0) celulas.push([r, c]);
      }
    }
    rng.shuffle(celulas);
    const removidas = [];
    for (const [r, c] of celulas) {
      const bak = puzzle[r][c];
      puzzle[r][c] = -1;
      const res = countSolutions(rows, cols, puzzle, 2, maxNodes);
      if (res.count === 1 && res.complete) removidas.push([r, c]);
      else puzzle[r][c] = bak;
    }
    return _devolveDicas(puzzle, fullClues, removidas, rng, dificuldade);
  }

  /**
   * Despacha para o método de redução escolhido. 'guloso' (padrão) preserva o
   * comportamento original.
   * @param {string} metodo  'guloso' | 'binaria' | 'cegar'.
   * @returns {number[][]}  matriz do puzzle reduzido.
   */
  function reduzDicas(rows, cols, fullClues, solutionLoop, rng, dificuldade, maxNodes, metodo) {
    if (metodo === 'binaria') return reduceCluesBinaria(rows, cols, fullClues, solutionLoop, rng, dificuldade, maxNodes);
    if (metodo === 'cegar') return reduceCluesCEGAR(rows, cols, fullClues, solutionLoop, rng, dificuldade, maxNodes);
    return reduceClues(rows, cols, fullClues, solutionLoop, rng, dificuldade, maxNodes);
  }

  // ------------------------------------------- geração de puzzle completo
  /**
   * Gera um puzzle completo: laço -> dicas -> redução, garantindo unicidade.
   *
   * @param {object} opts
   * @param {number} opts.rows
   * @param {number} opts.cols
   * @param {string|number} [opts.seed='slither']  semente reprodutível.
   * @param {string} [opts.dificuldade='medio']  'facil'|'medio'|'dificil' ou
   *   'nenhuma'/'none' (mostra o mapa completo de dicas, sem reduzir).
   * @param {string} [opts.metodo='guloso']  'guloso'|'binaria'|'cegar'.
   * @param {number} [opts.densidade=0.75]  passada a generateLoop.
   * @returns {{rows, cols, seed, dificuldade, metodo, clues: number[][],
   *            solution: string[], nClues: number}}
   *   clues: matriz do puzzle (-1 = sem dica); solution: chaves de aresta do
   *   laço solução, ordenadas; nClues: nº de dicas restantes.
   */
  function generatePuzzle(opts) {
    const rows = opts.rows, cols = opts.cols;
    const seed = opts.seed != null ? opts.seed : 'slither';
    const dificuldade = opts.dificuldade || 'medio';
    const metodo = opts.metodo || 'guloso';   // guloso | binaria | cegar
    const densidade = opts.densidade != null ? opts.densidade : 0.75;
    // O método NÃO entra na semente: mesma seed/tamanho/dificuldade gera o
    // MESMO laço, então dá para comparar métodos no mesmo tabuleiro.
    const rng = makeRng(seed + '|' + rows + 'x' + cols + '|' + dificuldade);

    const loop = generateLoop(rows, cols, rng, { densidade });
    const full = cluesFromLoop(rows, cols, loop);

    // O mapa completo precisa ter solução única; se não tiver (laços
    // distintos com o mesmo mapa), tenta outro laço variando a semente.
    let tentativa = 0, base = countSolutions(rows, cols, full, 2);
    let curLoop = loop, curFull = full;
    while ((base.count !== 1 || !base.complete) && tentativa < 8) {
      tentativa++;
      const r2 = makeRng(seed + '|' + rows + 'x' + cols + '|' + dificuldade + '|' + tentativa);
      curLoop = generateLoop(rows, cols, r2, { densidade });
      curFull = cluesFromLoop(rows, cols, curLoop);
      base = countSolutions(rows, cols, curFull, 2);
    }

    // 'nenhuma' mostra o mapa completo (todas as dicas), sem reduzir
    const puzzle = (dificuldade === 'nenhuma' || dificuldade === 'none')
      ? curFull.map((row) => row.slice())
      : reduzDicas(rows, cols, curFull, curLoop, rng, dificuldade, undefined, metodo);
    const nClues = puzzle.reduce((a, row) => a + row.filter((v) => v >= 0).length, 0);
    return {
      rows, cols, seed: String(seed), dificuldade, metodo,
      clues: puzzle,
      solution: [...curLoop].sort(),
      nClues,
    };
  }

  // ------------------------------------------- trace de resolução (animação)
  /**
   * Gera a sequência de passos de uma resolução, para a animação do botão
   * "Resolver" no modo DEDUÇÃO (oráculo). Como a solução única já é conhecida,
   * NÃO há retrocesso: o trace só AVANÇA. Propaga as deduções forçadas (mesmas
   * regras de vértice/célula do solver) e, quando empaca, "coloca" a próxima
   * aresta correta do laço como um `guess` — preferindo estender uma ponta
   * aberta, para o laço crescer continuamente — e propaga de novo.
   *
   * Difere de solveTraceBusca (busca real) por NUNCA errar nem desfazer: aqui o
   * `guess` é sempre uma aresta do laço solução; lá é um palpite que pode falhar
   * e gerar backtracking.
   *
   * @param {number} rows
   * @param {number} cols
   * @param {number[][]} clues  matriz de dicas (null/-1 = sem dica).
   * @param {string[]|Set<string>} solution  arestas do laço solução.
   * @returns {Array<{key: string, val: 'line'|'empty', type: 'deduce'|'guess'}>}
   *   passos em ordem; `deduce` = forçado por regra, `guess` = aresta do laço
   *   colocada para destravar.
   */
  function solveTrace(rows, cols, clues, solution, seedLines, seedMarks) {
    const topo = buildTopology(rows, cols);
    const { nE, nDots, edgeEnds, dotEdges, edgeKey } = topo;
    const sol = new Set(solution);

    // indexa células com dica (igual ao solver)
    const cellClue = [], cellEdgesArr = [], edgeCells = Array.from({ length: nE }, () => []);
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const k = clues[r][c];
      if (k == null || k < 0) continue;
      const id = cellClue.length;
      const es = topo.cellEdges(r, c);
      cellClue.push(k); cellEdgesArr.push(es);
      for (const e of es) edgeCells[e].push(id);
    }
    const nCells = cellClue.length;

    // contadores incrementais (sem union-find: não detectamos laço, já o temos)
    const state = new Uint8Array(nE);
    const inV = new Int16Array(nDots), unkV = new Int16Array(nDots);
    for (let d = 0; d < nDots; d++) unkV[d] = dotEdges[d].length;
    const inC = new Int16Array(nCells), unkC = new Int16Array(nCells).fill(4);

    const trace = [];
    const queue = [];
    let placed = 0;

    // atribui uma aresta, registra o passo no trace e atualiza contadores
    function set(e, val, type) {
      if (state[e] !== UNKNOWN) return;
      state[e] = val;
      trace.push({ key: edgeKey[e], val: val === LINE ? 'line' : 'empty', type });
      const [v1, v2] = edgeEnds[e];
      unkV[v1]--; unkV[v2]--;
      queue.push(v1 | 0x40000000, v2 | 0x40000000);
      for (const cel of edgeCells[e]) {
        unkC[cel]--;
        queue.push(cel);
      }
      if (val === LINE) {
        placed++;
        inV[v1]++; inV[v2]++;
        for (const cel of edgeCells[e]) inC[cel]++;
      }
    }
    // regra de vértice (mesma lógica do solver, mas sem detectar contradição)
    function vertexRule(v) {
      const iv = inV[v], uv = unkV[v];
      if (iv === 2) {
        if (uv) for (const e of dotEdges[v]) if (state[e] === UNKNOWN) set(e, EMPTY, 'deduce');
      } else if (iv === 1) {
        if (uv === 1) for (const e of dotEdges[v]) if (state[e] === UNKNOWN) set(e, LINE, 'deduce');
      } else if (uv === 1) {
        for (const e of dotEdges[v]) if (state[e] === UNKNOWN) set(e, EMPTY, 'deduce');
      }
    }
    // regra de célula (idem)
    function cellRule(cel) {
      const ic = inC[cel], uc = unkC[cel], k = cellClue[cel];
      if (uc === 0) return;
      if (ic === k) {
        for (const e of cellEdgesArr[cel]) if (state[e] === UNKNOWN) set(e, EMPTY, 'deduce');
      } else if (ic + uc === k) {
        for (const e of cellEdgesArr[cel]) if (state[e] === UNKNOWN) set(e, LINE, 'deduce');
      }
    }
    function propagate() {
      while (queue.length) {
        const x = queue.pop();
        if (x & 0x40000000) vertexRule(x & 0x3FFFFFFF);
        else cellRule(x);
      }
    }

    // semeia o estado inicial com o progresso do jogador (NÃO emite passos:
    // essas arestas já estão na tela). Só semeia o que é consistente com a
    // solução (o chamador filtra: linhas ∈ solução, marcas ∉ solução).
    const semente = (k, val) => {
      const e = topo.keyToIdx[k];
      if (e == null || state[e] !== UNKNOWN) return;
      state[e] = val;
      const [v1, v2] = edgeEnds[e];
      unkV[v1]--; unkV[v2]--;
      for (const cel of edgeCells[e]) unkC[cel]--;
      if (val === LINE) { placed++; inV[v1]++; inV[v2]++; for (const cel of edgeCells[e]) inC[cel]++; }
    };
    for (const k of (seedLines || [])) semente(k, LINE);
    for (const k of (seedMarks || [])) semente(k, EMPTY);

    // propagação inicial a partir das dicas (e das sementes)
    for (let cel = 0; cel < nCells; cel++) queue.push(cel);
    propagate();

    // enquanto faltam arestas do laço, coloca a próxima e re-propaga
    let guard = 0;
    while (placed < sol.size && guard++ < nE * 4) {
      // próxima aresta do laço ainda não colocada — de preferência na ponta
      // de um caminho aberto (vértice de grau 1), para o laço crescer contínuo
      let frente = -1, qualquer = -1;
      for (let e = 0; e < nE; e++) {
        if (state[e] !== UNKNOWN || !sol.has(edgeKey[e])) continue;
        if (qualquer < 0) qualquer = e;
        const [v1, v2] = edgeEnds[e];
        if (inV[v1] === 1 || inV[v2] === 1) {
          frente = e;
          break;
        }
      }
      const e = frente >= 0 ? frente : qualquer;
      if (e < 0) break;
      set(e, LINE, 'guess');
      propagate();
    }
    return trace;
  }

  // ------------------------------------ trace de BUSCA REAL (com backtracking)
  /**
   * Gera o trace da resolução no modo BUSCA REAL: resolve a partir SÓ das dicas
   * (sem conhecer a solução). É essencialmente o mesmo motor de countSolutions
   * (propagação + backtracking + union-find reversível), mas INSTRUMENTADO:
   * cada atribuição vira um passo ('deduce' ou 'guess') e cada desfazimento no
   * backtracking vira um passo 'unset'/'backtrack' — para a animação mostrar o
   * solver "lutando", arriscando e voltando atrás. Para na PRIMEIRA solução
   * (quando para, NÃO desfaz: a solução fica na tela).
   *
   * Diferenças em relação ao trace por dedução (solveTrace): aqui há palpites
   * que podem FALHAR e ser desfeitos; lá todo palpite é uma aresta correta do
   * laço já conhecido.
   *
   * @param {number} rows
   * @param {number} cols
   * @param {number[][]} clues  matriz de dicas (null/-1 = sem dica).
   * @param {number} [maxNodes=5000000]  teto de nós da busca.
   * @param {number} [maxPassos=8000]  teto de passos do trace (p/ animação).
   * @returns {Array<{key: string, val: 'line'|'empty'|'unset',
   *                  type: 'deduce'|'guess'|'backtrack'}>}  passos em ordem.
   */
  function solveTraceBusca(rows, cols, clues, maxNodes, maxPassos, seedLines, seedMarks) {
    maxNodes = maxNodes || 5000000;
    maxPassos = maxPassos || 8000;   // limita o tamanho do trace p/ animação
    const topo = buildTopology(rows, cols);
    const { nE, nDots, edgeEnds, dotEdges, edgeKey } = topo;

    // indexa células com dica (igual ao solver)
    const cellClue = [], cellEdgesArr = [], edgeCells = Array.from({ length: nE }, () => []);
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const k = clues[r][c];
      if (k == null || k < 0) continue;
      const id = cellClue.length;
      const es = topo.cellEdges(r, c);
      cellClue.push(k); cellEdgesArr.push(es);
      for (const e of es) edgeCells[e].push(id);
    }
    const nCells = cellClue.length;

    // mesmos contadores e estruturas de countSolutions (ver lá os comentários)
    const state = new Uint8Array(nE);
    const inV = new Int16Array(nDots), unkV = new Int16Array(nDots);
    for (let d = 0; d < nDots; d++) unkV[d] = dotEdges[d].length;
    const inC = new Int16Array(nCells), unkC = new Int16Array(nCells).fill(4);
    const pai = new Int32Array(nDots);
    for (let d = 0; d < nDots; d++) pai[d] = d;
    const tam = new Int32Array(nDots).fill(1);
    const pontas = new Set();
    let totalIn = 0, nSat = 0;
    for (let i = 0; i < nCells; i++) if (cellClue[i] === 0) nSat++;
    const trilha = [], trilhaUf = [], fila = [], trace = [];
    let nodes = 0, done = false;   // done = achou solução ou estourou limite

    // union-find SEM compressão de caminho (reversível no backtracking)
    function find(x) {
      while (pai[x] !== x) x = pai[x];
      return x;
    }

    // como setEdge do solver, mas também grava o passo no trace e detecta
    // solução via `done` em vez de coletar todas as soluções
    function setEdge(e, val, type) {
      if (state[e] !== UNKNOWN) return state[e] === val;
      state[e] = val;
      trilha.push(e);
      trace.push({ key: edgeKey[e], val: val === LINE ? 'line' : 'empty', type });
      if (trace.length >= maxPassos) done = true;   // estoura o limite de passos
      const [v1, v2] = edgeEnds[e];
      unkV[v1]--; unkV[v2]--;
      fila.push(v1 | 0x40000000, v2 | 0x40000000);
      for (const cel of edgeCells[e]) {
        unkC[cel]--;
        fila.push(cel);
      }
      if (val === EMPTY) return true;
      totalIn++;
      let contra = false;
      for (const v of [v1, v2]) {
        const iv = ++inV[v];
        if (iv === 1) pontas.add(v);
        else if (iv === 2) pontas.delete(v);
        else contra = true;
      }
      for (const cel of edgeCells[e]) {
        const ic = ++inC[cel];
        const k = cellClue[cel];
        if (ic === k) nSat++;
        else if (ic === k + 1) nSat--;
        if (ic > k) contra = true;
      }
      if (contra) return false;
      let r1 = find(v1), r2 = find(v2);
      if (r1 === r2) {
        // fechou um ciclo: se é a solução completa, sinaliza done
        if (totalIn === tam[r1] && nSat === nCells) done = true;
        return false;
      }
      if (tam[r1] < tam[r2]) { const t = r1; r1 = r2; r2 = t; }
      pai[r2] = r1;
      tam[r1] += tam[r2];
      trilhaUf.push([r2, r1]);
      return true;
    }

    // rollback; cada aresta LINE/EMPTY desfeita vira um passo 'unset' (a menos
    // que já tenhamos terminado — aí não poluímos o trace final)
    function desfaz(mE, mU) {
      while (trilhaUf.length > mU) {
        const [r2, r1] = trilhaUf.pop();
        tam[r1] -= tam[r2];
        pai[r2] = r2;
      }
      while (trilha.length > mE) {
        const e = trilha.pop();
        const val = state[e];
        state[e] = UNKNOWN;
        if (!done) trace.push({ key: edgeKey[e], val: 'unset', type: 'backtrack' });
        const [v1, v2] = edgeEnds[e];
        unkV[v1]++; unkV[v2]++;
        for (const cel of edgeCells[e]) unkC[cel]++;
        if (val === LINE) {
          totalIn--;
          for (const v of [v1, v2]) {
            const iv = --inV[v];
            if (iv === 1) pontas.add(v);
            else if (iv === 0) pontas.delete(v);
          }
          for (const cel of edgeCells[e]) {
            const ic = --inC[cel];
            const k = cellClue[cel];
            if (ic === k) nSat++;
            else if (ic === k - 1) nSat--;
          }
        }
      }
    }

    // regras de propagação (idênticas às de countSolutions)
    function regraVertice(v) {
      const iv = inV[v], uv = unkV[v];
      if (iv > 2) return false;
      if (iv === 2) {
        if (uv) for (const e of dotEdges[v])
          if (state[e] === UNKNOWN && !setEdge(e, EMPTY, 'deduce')) return false;
      } else if (iv === 1) {
        if (uv === 0) return false;
        if (uv === 1) for (const e of dotEdges[v])
          if (state[e] === UNKNOWN) return setEdge(e, LINE, 'deduce');
      } else if (uv === 1) {
        for (const e of dotEdges[v])
          if (state[e] === UNKNOWN) return setEdge(e, EMPTY, 'deduce');
      }
      return true;
    }
    function regraCelula(cel) {
      const ic = inC[cel], uc = unkC[cel], k = cellClue[cel];
      if (ic > k || ic + uc < k) return false;
      if (uc === 0) return true;
      if (ic === k) {
        for (const e of cellEdgesArr[cel])
          if (state[e] === UNKNOWN && !setEdge(e, EMPTY, 'deduce')) return false;
      } else if (ic + uc === k) {
        for (const e of cellEdgesArr[cel])
          if (state[e] === UNKNOWN && !setEdge(e, LINE, 'deduce')) return false;
      }
      return true;
    }
    function propaga() {
      while (fila.length) {
        if (done) { fila.length = 0; return false; }
        const x = fila.pop();
        const ok = (x & 0x40000000) ? regraVertice(x & 0x3FFFFFFF) : regraCelula(x);
        if (!ok) { fila.length = 0; return false; }
      }
      return true;
    }
    function conectavel() {
      if (pontas.size <= 2) return true;
      const inicio = pontas.values().next().value;
      const vis = new Uint8Array(nDots);
      vis[inicio] = 1;
      const pilha = [inicio];
      while (pilha.length) {
        const v = pilha.pop();
        for (const e of dotEdges[v]) {
          if (state[e] === EMPTY) continue;
          const [a, b] = edgeEnds[e];
          const w = a === v ? b : a;
          if (!vis[w]) {
            vis[w] = 1;
            pilha.push(w);
          }
        }
      }
      for (let v = 0; v < nDots; v++) if (inV[v] && !vis[v]) return false;
      return true;
    }
    function escolhe() {
      for (const v of pontas)
        for (const e of dotEdges[v]) if (state[e] === UNKNOWN) return e;
      for (let cel = 0; cel < nCells; cel++)
        if (unkC[cel]) for (const e of cellEdgesArr[cel]) if (state[e] === UNKNOWN) return e;
      for (let e = 0; e < nE; e++) if (state[e] === UNKNOWN) return e;
      return -1;
    }
    function busca() {
      if (done) return;
      if (++nodes > maxNodes) { done = true; return; }
      if (!conectavel()) return;
      const e = escolhe();
      if (e < 0) return;
      for (const val of [LINE, EMPTY]) {
        const mE = trilha.length, mU = trilhaUf.length;
        let ok = setEdge(e, val, 'guess');
        if (ok) ok = propaga(); else fila.length = 0;
        if (ok) busca();
        if (done) return;          // achou a solução: NÃO desfaz (fica na tela)
        desfaz(mE, mU);
      }
    }

    // semeia o progresso do jogador como estado FIXO (busca não o desfaz, pois
    // fica abaixo do 1º marcador de backtracking). Esses passos são as próprias
    // arestas do jogador, já na tela, então são cortados do trace devolvido.
    for (const k of (seedLines || [])) { const e = topo.keyToIdx[k]; if (e != null && state[e] === UNKNOWN) setEdge(e, LINE, 'seed'); }
    for (const k of (seedMarks || [])) { const e = topo.keyToIdx[k]; if (e != null && state[e] === UNKNOWN) setEdge(e, EMPTY, 'seed'); }
    const nSemente = trace.length;

    for (let cel = 0; cel < nCells; cel++) fila.push(cel);
    if (!done && propaga()) busca();
    return trace.slice(nSemente);
  }

  // API pública do módulo.
  // ------------------------------------------- dedução de arestas inviáveis
  // Propaga as deduções LOCAIS (regras de vértice e de célula) a partir do
  // estado atual do jogador — traços (LINE), marcas × (EMPTY) e dicas — e
  // devolve o conjunto de arestas DEDUZIDAS como vazias (i.e., que não podem
  // mais entrar no laço). É o que alimenta o esmaecimento "inteligente": além
  // dos casos imediatos (em volta de um 0, vértice de grau 2…), propaga as
  // consequências das marcas do jogador. Robusto a estados contraditórios:
  // nunca sobrescreve uma aresta já definida; na dúvida, simplesmente para.
  function deduceEmpties(rows, cols, clues, lineKeys, markKeys) {
    const topo = buildTopology(rows, cols);
    const { nE, nDots, edgeEnds, dotEdges, edgeKey, keyToIdx } = topo;

    const cellClue = [], cellEdgesArr = [], edgeCells = Array.from({ length: nE }, () => []);
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const k = clues[r][c];
      if (k == null || k < 0) continue;
      const id = cellClue.length, es = topo.cellEdges(r, c);
      cellClue.push(k); cellEdgesArr.push(es);
      for (const e of es) edgeCells[e].push(id);
    }
    const nCells = cellClue.length;

    const state = new Uint8Array(nE);   // UNKNOWN / LINE / EMPTY
    for (const k of (lineKeys || [])) { const e = keyToIdx[k]; if (e != null) state[e] = LINE; }
    for (const k of (markKeys || [])) { const e = keyToIdx[k]; if (e != null && state[e] === UNKNOWN) state[e] = EMPTY; }

    const lineV = new Int16Array(nDots), unkV = new Int16Array(nDots);
    for (let d = 0; d < nDots; d++) for (const e of dotEdges[d]) {
      if (state[e] === LINE) lineV[d]++; else if (state[e] === UNKNOWN) unkV[d]++;
    }
    const lineC = new Int16Array(nCells), unkC = new Int16Array(nCells);
    for (let i = 0; i < nCells; i++) for (const e of cellEdgesArr[i]) {
      if (state[e] === LINE) lineC[i]++; else if (state[e] === UNKNOWN) unkC[i]++;
    }

    const empties = new Set();
    const fila = [];
    for (let d = 0; d < nDots; d++) fila.push(d | 0x40000000);
    for (let i = 0; i < nCells; i++) fila.push(i);

    function setEdge(e, val) {
      if (state[e] !== UNKNOWN) return;            // já decidida: não sobrescreve
      state[e] = val;
      if (val === EMPTY) empties.add(edgeKey[e]);
      const [v1, v2] = edgeEnds[e];
      for (const v of [v1, v2]) {
        unkV[v]--; if (val === LINE) lineV[v]++;
        fila.push(v | 0x40000000);
      }
      for (const cel of edgeCells[e]) {
        unkC[cel]--; if (val === LINE) lineC[cel]++;
        fila.push(cel);
      }
    }
    function regraVertice(v) {
      const L = lineV[v], U = unkV[v];
      if (U === 0) return;
      if (L >= 2) { for (const e of dotEdges[v]) if (state[e] === UNKNOWN) setEdge(e, EMPTY); }
      else if (L === 1 && U === 1) { for (const e of dotEdges[v]) if (state[e] === UNKNOWN) setEdge(e, LINE); }
      else if (L === 0 && U === 1) { for (const e of dotEdges[v]) if (state[e] === UNKNOWN) setEdge(e, EMPTY); }
    }
    function regraCelula(cel) {
      const L = lineC[cel], U = unkC[cel], k = cellClue[cel];
      if (U === 0) return;
      if (L >= k) { for (const e of cellEdgesArr[cel]) if (state[e] === UNKNOWN) setEdge(e, EMPTY); }
      else if (L + U === k) { for (const e of cellEdgesArr[cel]) if (state[e] === UNKNOWN) setEdge(e, LINE); }
    }

    let guard = 0;
    while (fila.length && guard++ < nE * 8) {
      const x = fila.pop();
      if (x & 0x40000000) regraVertice(x & 0x3FFFFFFF); else regraCelula(x);
    }
    return empties;
  }

  const SL = {
    makeRng, buildTopology, generateLoop, cluesFromLoop, countSolutions,
    reduceClues, reduceCluesBinaria, reduceCluesCEGAR, reduzDicas,
    generatePuzzle, solveTrace, solveTraceBusca, deduceEmpties, hKey, vKey,
    UNKNOWN, LINE, EMPTY,
  };

  // Exportação UMD: módulo no Node (module.exports), global SL no navegador.
  if (typeof module !== 'undefined' && module.exports) module.exports = SL;
  else root.SL = SL;
})(typeof window !== 'undefined' ? window : globalThis);
