// Teste do motor (Node): valida geração, unicidade e consistência das dicas.
const SL = require('./core.js');

function validaLaco(rows, cols, loop) {
  // grau de cada ponto deve ser 0 ou 2, e tudo num único ciclo
  const grau = {};
  const adj = {};
  const dotId = (r, c) => r + ',' + c;
  const addEdge = (a, b) => {
    grau[a] = (grau[a] || 0) + 1; grau[b] = (grau[b] || 0) + 1;
    (adj[a] = adj[a] || []).push(b); (adj[b] = adj[b] || []).push(a);
  };
  for (const k of loop) {
    const [t, r, c] = k.split(':'); const R = +r, C = +c;
    if (t === 'H') addEdge(dotId(R, C), dotId(R, C + 1));
    else addEdge(dotId(R, C), dotId(R + 1, C));
  }
  const dots = Object.keys(grau);
  for (const d of dots) if (grau[d] !== 2) return { ok: false, motivo: 'grau ' + grau[d] };
  // único componente?
  const vis = new Set([dots[0]]); const pilha = [dots[0]];
  while (pilha.length) {
    const v = pilha.pop();
    for (const w of adj[v]) if (!vis.has(w)) { vis.add(w); pilha.push(w); }
  }
  if (vis.size !== dots.length) return { ok: false, motivo: 'multiplos ciclos' };
  return { ok: true, nVert: dots.length };
}

let falhas = 0;
const casos = [
  { rows: 5, cols: 5, dif: 'facil' },
  { rows: 6, cols: 6, dif: 'medio' },
  { rows: 7, cols: 7, dif: 'dificil' },
  { rows: 8, cols: 8, dif: 'medio' },
  { rows: 10, cols: 10, dif: 'dificil' },
  { rows: 8, cols: 12, dif: 'facil' },
];

console.log('='.repeat(64));
for (const cs of casos) {
  for (const seed of ['alpha', 'bravo', 'charlie']) {
    const t0 = Date.now();
    const p = SL.generatePuzzle({ rows: cs.rows, cols: cs.cols, seed, dificuldade: cs.dif });
    const dt = Date.now() - t0;
    const loop = new Set(p.solution);

    // 1) o laço é um ciclo único
    const v = validaLaco(cs.rows, cs.cols, loop);
    // 2) o puzzle tem solução única e igual ao laço
    const res = SL.countSolutions(cs.rows, cs.cols, p.clues, 2);
    const unico = res.count === 1 && res.complete;
    const igual = unico && setEq(res.solutions[0], loop);
    // 3) as dicas do puzzle batem com o laço onde existem
    const full = SL.cluesFromLoop(cs.rows, cs.cols, loop);
    let dicasOk = true;
    for (let r = 0; r < cs.rows; r++) for (let c = 0; c < cs.cols; c++)
      if (p.clues[r][c] >= 0 && p.clues[r][c] !== full[r][c]) dicasOk = false;

    const ok = v.ok && unico && igual && dicasOk;
    if (!ok) falhas++;
    const tot = cs.rows * cs.cols;
    console.log(
      `${ok ? 'OK ' : 'XX '} ${cs.rows}x${cs.cols} ${cs.dif.padEnd(7)} seed=${seed.padEnd(8)}`
      + ` | laco=${v.ok ? v.nVert + 'v' : v.motivo}`
      + ` | unico=${unico} igual=${igual} dicas=${dicasOk}`
      + ` | dicas ${p.nClues}/${tot} | ${dt}ms`
    );
  }
}

function setEq(a, b) {
  if (a.size !== b.size) return false;
  for (const x of a) if (!b.has(x)) return false;
  return true;
}

console.log('='.repeat(64));
console.log(falhas === 0 ? 'TODOS OS TESTES PASSARAM' : falhas + ' FALHAS');
process.exit(falhas === 0 ? 0 : 1);
