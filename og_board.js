// Gera um tabuleiro Slitherlink REAL (laço + dicas consistentes) via o motor
// e imprime como JSON — usado por make_og.py para desenhar a imagem de
// compartilhamento (OG). Uso: node og_board.js [seed] [rows] [cols] [dif]
const SL = require('./web/js/core.js');
const seed = process.argv[2] || 'ogboard';
const rows = +(process.argv[3] || 6);
const cols = +(process.argv[4] || 6);
const dif = process.argv[5] || 'medio';
const p = SL.generatePuzzle({ rows, cols, seed, dificuldade: dif });
process.stdout.write(JSON.stringify({
  rows: p.rows, cols: p.cols, clues: p.clues, solution: p.solution, nClues: p.nClues,
}));
