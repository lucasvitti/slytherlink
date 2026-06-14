// Web Worker: gera o puzzle fora da thread da UI para não travar a página.
// Repassa a versão (cache-busting) para o importScripts do core.js.
var __v = (new URLSearchParams(self.location.search).get('v')) || '';
importScripts('core.js?v=' + __v);

onmessage = function (e) {
  const opts = e.data;
  try {
    const t0 = Date.now();
    const puzzle = SL.generatePuzzle(opts);
    puzzle.ms = Date.now() - t0;     // tempo de geração (p/ comparar métodos)
    postMessage({ ok: true, puzzle });
  } catch (err) {
    postMessage({ ok: false, error: String((err && err.message) || err) });
  }
};
