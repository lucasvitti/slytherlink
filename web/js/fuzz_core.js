// Fuzzer: compara countSolutions com um solver de força bruta (referência
// obviamente correta) em tabuleiros pequenos, para achar bugs de
// completude/solidez.
const SL = require('./core.js');

function brute(rows, cols, clues, limit) {
  const topo = SL.buildTopology(rows, cols);
  const { nE, nDots, edgeEnds, edgeKey } = topo;
  const sols = [];
  const full = (mask) => {
    // grau + ciclo único + dicas
    const grau = new Int8Array(nDots);
    let nEdges = 0;
    for (let e = 0; e < nE; e++) if (mask & (1 << e)) {
      const [a, b] = edgeEnds[e]; grau[a]++; grau[b]++; nEdges++;
    }
    if (nEdges === 0) return null;
    for (let d = 0; d < nDots; d++) if (grau[d] !== 0 && grau[d] !== 2) return null;
    // ciclo único: dfs nas arestas
    const adj = Array.from({ length: nDots }, () => []);
    let start = -1;
    for (let e = 0; e < nE; e++) if (mask & (1 << e)) {
      const [a, b] = edgeEnds[e]; adj[a].push(b); adj[b].push(a);
      if (start < 0) start = a;
    }
    const vis = new Uint8Array(nDots); const st = [start]; vis[start] = 1; let cnt = 0;
    while (st.length) { const v = st.pop(); cnt++; for (const w of adj[v]) if (!vis[w]) { vis[w] = 1; st.push(w); } }
    let nUsed = 0; for (let d = 0; d < nDots; d++) if (grau[d]) nUsed++;
    if (cnt !== nUsed) return null;
    // dicas
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const k = clues[r][c]; if (k == null || k < 0) continue;
      const es = topo.cellEdges(r, c);
      let n = 0; for (const e of es) if (mask & (1 << e)) n++;
      if (n !== k) return null;
    }
    const s = new Set(); for (let e = 0; e < nE; e++) if (mask & (1 << e)) s.add(edgeKey[e]);
    return s;
  };
  for (let mask = 1; mask < (1 << nE); mask++) {
    const s = full(mask); if (s) { sols.push(s); if (sols.length >= limit) break; }
  }
  return { count: sols.length, solutions: sols };
}

function setEq(a, b) { if (a.size !== b.size) return false; for (const x of a) if (!b.has(x)) return false; return true; }

const rng = SL.makeRng('fuzz');
let testes = 0, falhas = 0;
const exemplos = [];

// nE para 2x2 = 12 (ok), 3x2 = 17, 3x3 = 24 (forca bruta ate ~2^20 ok; 3x3 lento)
const formas = [[2, 2], [3, 2], [2, 3], [3, 3]];
for (const [rows, cols] of formas) {
  const nIter = (rows * cols <= 6) ? 400 : 120;
  for (let it = 0; it < nIter; it++) {
    // clues aleatórias parciais: cada célula tem 40% de chance de ter dica
    // sorteada de uma solução real, senão fica vazia (garante consistência)
    // Gera um laço real para extrair dicas plausíveis
    const loop = SL.generateLoop(rows, cols, rng, { densidade: 0.5 + rng.float() * 0.3 });
    const full = SL.cluesFromLoop(rows, cols, loop);
    const clues = full.map((row) => row.map((v) => (rng.float() < 0.45 ? v : -1)));

    const ref = brute(rows, cols, clues, 2);
    const got = SL.countSolutions(rows, cols, clues, 2, 1e8);
    testes++;
    const okCount = ref.count === got.count;
    let okSols = true;
    if (got.count <= 2 && got.complete) {
      // conjuntos devem coincidir quando count < 2
      if (ref.count < 2) {
        okSols = ref.count === got.count &&
          (ref.count === 0 || setEq(ref.solutions[0], got.solutions[0]));
      }
    }
    if (!okCount || !okSols) {
      falhas++;
      if (exemplos.length < 3) exemplos.push({ rows, cols, clues, ref: ref.count, got: got.count });
    }
  }
}

console.log(`testes=${testes} falhas=${falhas}`);
for (const e of exemplos) {
  console.log(`-- ${e.rows}x${e.cols} ref=${e.ref} got=${e.got}`);
  console.log(e.clues.map((row) => row.map((v) => v < 0 ? '.' : v).join(' ')).join('\n'));
}
process.exit(falhas === 0 ? 0 : 1);
