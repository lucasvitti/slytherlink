/*
 * game.js — UI jogável do Slitherlink (tema escuro, segmentos coloridos).
 *
 * Camada de apresentação/interação sobre o motor de core.js (objeto global SL).
 * Renderiza o tabuleiro em SVG, trata o clique nas arestas, deriva o estado
 * visual (proibições, erros, vitória) e anima o solucionador.
 *
 * Interação:
 *   - clique curto numa aresta: traça / apaga a linha
 *   - clique-e-segura: marca / desmarca a aresta como inviável (×) pelo jogador
 *   - arestas da grade são pontilhadas; as inviáveis (checagem automática)
 *     ficam ainda mais fracas
 *   - cada segmento conectado tem uma cor; ao unir dois segmentos, a cor do
 *     segmento MAIOR prevalece
 *
 * Estado global em S (ver abaixo). A geração roda num Web Worker (worker.js)
 * para não travar a thread da UI.
 *
 * Identificação das arestas (UI e CSV): "H:r:c" liga (r,c)-(r,c+1);
 * "V:r:c" liga (r,c)-(r+1,c).
 */
(function () {
  'use strict';

  const SVGNS = 'http://www.w3.org/2000/svg';
  const $ = (id) => document.getElementById(id);   // atalho p/ getElementById
  const HOLD_MS = 280;                              // limiar tap vs. hold (ms)
  const VERSION = '20';   // bump quando core.js/worker.js mudarem (cache-busting)

  // paleta de cores dos segmentos (vivas, sobre fundo escuro)
  const PALETA = ['#4f9dff', '#41d18f', '#33c7c7', '#f2c14e', '#e86af0',
    '#ff8c42', '#ff5d73', '#9d7bff', '#7bd645', '#5ad1ff', '#ff6ec7', '#c0e84a'];

  // Estado global da UI.
  const S = {
    puzzle: null,         // puzzle atual (saída de SL.generatePuzzle / CSV)
    lines: new Set(),     // arestas traçadas
    marks: new Set(),     // arestas marcadas como inviáveis pelo jogador (×)
    colors: {},           // chave de aresta -> cor (persistente p/ regra do maior)
    colorSeq: 0,          // contador p/ gerar cores extras quando a paleta acaba
    undo: [], redo: [],   // pilhas de movimentos (cada item = { changes })
    edgeEls: {}, markEls: {}, clueEls: null,   // refs dos elementos SVG
    geo: null, won: false,                     // geometria e flag de vitória
    zoom: 1,                    // fator de zoom do tabuleiro (1 = tamanho base)
    panX: 0, panY: 0,           // deslocamento (pan/câmera) do tabuleiro, em px
    gesturing: false,           // true durante pan/pinça multitoque (suspende o traço)
    slots: [null, null, null, null, null],  // 5 checkpoints (estados salvos)
    anim: null, focoEl: null,   // animação do solucionador (timer + aresta em foco)
    camRAF: null,               // rAF da câmera animada (recuo até 100% ao vencer)
    miniEls: null,              // refs do minimapa { board, lines, visor }
  };

  // Web Worker preguiçoso: criado na 1ª geração e reaproveitado.
  let worker = null;
  function getWorker() {
    if (!worker) {
      worker = new Worker('js/worker.js?v=' + VERSION);
      worker.onmessage = (e) => onGenerated(e.data);
    }
    return worker;
  }

  // -------------------------------------------------- chaves / topologia
  // Espelham as convenções de core.js, mas para uso da UI.
  const hKey = (r, c) => 'H:' + r + ':' + c;
  const vKey = (r, c) => 'V:' + r + ':' + c;
  // decompõe "H:r:c" -> { t:'H', r, c }
  const parseKey = (k) => { const p = k.split(':'); return { t: p[0], r: +p[1], c: +p[2] }; };
  // os 2 pontos extremos de uma aresta
  function edgeDots(k) {
    const { t, r, c } = parseKey(k);
    return t === 'H' ? [[r, c], [r, c + 1]] : [[r, c], [r + 1, c]];
  }
  // as (até 2) células que tocam uma aresta (algumas podem ficar fora do tabuleiro)
  function edgeCells(k) {
    const { t, r, c } = parseKey(k);
    return t === 'H' ? [[r - 1, c], [r, c]] : [[r, c - 1], [r, c]];
  }

  // -------------------------------------------------- geometria
  /**
   * Calcula as medidas do desenho a partir do tamanho do tabuleiro e da
   * largura da janela: passo da grade (gap), margem (pad), tamanho da tela
   * (w/h), fonte das dicas, tamanho do × (mx) e raio dos pontos.
   * @returns {object} geometria usada por dx/dy e pela renderização.
   */
  function computeGeo(rows, cols) {
    const max = Math.min(820, window.innerWidth - 80);
    const gap = Math.max(15, Math.min(58, Math.floor(max / Math.max(rows, cols))));
    const pad = Math.max(16, Math.round(gap * 0.7));
    return { pad, gap, w: pad * 2 + cols * gap, h: pad * 2 + rows * gap,
             // fonte das dicas PROPORCIONAL à célula (≈52% do passo): preenche a
             // caixa na mesma proporção em qualquer tamanho. Em unidades do
             // viewBox, então escala junto com o zoom automaticamente.
             fonte: Math.max(7, +(gap * 0.52).toFixed(1)),
             mx: Math.max(2.5, Math.round(gap * 0.16)),
             raio: Math.max(1.3, +(gap * 0.06).toFixed(1)) };
  }
  // coordenadas em pixel do ponto (r,c)
  const dx = (c) => S.geo.pad + c * S.geo.gap;
  const dy = (r) => S.geo.pad + r * S.geo.gap;

  // -------------------------------------------------- zoom
  const ZOOM_MIN = 0.25, ZOOM_MAX = 5;

  /**
   * Aplica a "câmera" (zoom + pan). O zoom muda só o tamanho RENDERIZADO do SVG
   * (viewBox fixo → desenho nítido) e o pan é um translate(). O palco tem
   * overflow:hidden, então NÃO há barras de rolagem: navega-se arrastando.
   */
  function aplicaView() {
    const svg = $('tabuleiro');
    svg.setAttribute('width', Math.round(S.geo.w * S.zoom));
    svg.setAttribute('height', Math.round(S.geo.h * S.zoom));
    // espessura das linhas escala como 1/√zoom (sub-linear): ao ampliar, a
    // linha cresce mais devagar que as células e não vira "salsicha".
    svg.style.setProperty('--sw', (1 / Math.sqrt(S.zoom)).toFixed(3));
    svg.style.transform = 'translate(' + Math.round(S.panX) + 'px,' + Math.round(S.panY) + 'px)';
    const pct = $('zoomPct');
    if (pct) pct.textContent = Math.round(S.zoom * 100) + '%';
    atualizaVisor();   // mantém o retângulo do minimapa em sincronia com a câmera
  }

  // Centraliza o tabuleiro no palco (ao gerar e no "Ajustar").
  function centraliza() {
    cancelAnimacaoCamera();
    const r = $('scroll').getBoundingClientRect();
    S.panX = (r.width - S.geo.w * S.zoom) / 2;
    S.panY = (r.height - S.geo.h * S.zoom) / 2;
    aplicaView();
  }

  // Oculta/mostra a barra superior (libera mais área para o tabuleiro).
  function toggleTopbar() {
    const oculta = document.querySelector('.topbar').classList.toggle('oculta');
    const btn = $('toggleTop');
    if (btn) { btn.textContent = oculta ? '▾' : '▴'; btn.title = oculta ? 'Mostrar a barra' : 'Ocultar a barra'; }
    if (S.puzzle) requestAnimationFrame(centraliza);
  }

  /**
   * Ajusta o zoom mantendo fixo o ponto do tabuleiro sob (ax,ay) em pixels de
   * tela (padrão: centro da viewport de rolagem). Recoloca a rolagem para que
   * o ponto ancorado não escorregue ao ampliar/reduzir.
   */
  function setZoom(z, ax, ay) {
    if (!S.puzzle) return;
    cancelAnimacaoCamera();
    const r = $('scroll').getBoundingClientRect();
    if (ax == null) { ax = r.left + r.width / 2; ay = r.top + r.height / 2; }
    z = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z));
    const old = S.zoom;
    if (Math.abs(z - old) < 1e-4) return;
    // coordenada de conteúdo (não-escalada) sob a âncora
    const cx = (ax - r.left - S.panX) / old;
    const cy = (ay - r.top - S.panY) / old;
    S.zoom = z;
    S.panX = ax - r.left - cx * z;
    S.panY = ay - r.top - cy * z;
    aplicaView();
  }

  // Ajusta o zoom para o tabuleiro inteiro caber no palco e centraliza.
  function zoomFit() {
    if (!S.puzzle) return;
    const r = $('scroll').getBoundingClientRect();
    const z = Math.min(r.width / S.geo.w, r.height / S.geo.h) * 0.97;
    S.zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z));
    centraliza();
  }

  /**
   * "Câmera que segue o solver": durante a animação, desloca o pan para manter
   * a aresta em foco perto do centro do palco — assim, ao gravar um vídeo de um
   * tabuleiro AMPLIADO, o olho acompanha onde o solver está trabalhando.
   * Só age no eixo em que o tabuleiro é MAIOR que o palco (se cabe, não mexe);
   * usa uma "zona morta" central para a câmera não tremer a cada passo e mantém
   * o tabuleiro cobrindo o palco (sem margens vazias entrando em cena). A
   * suavidade vem de um transition no transform, ligado só durante a animação.
   */
  function seguirFoco(key) {
    const el = S.edgeEls[key];
    if (!el) return;
    const r = $('scroll').getBoundingClientRect();
    const W = S.geo.w * S.zoom, H = S.geo.h * S.zoom;
    const mx = ((+el.getAttribute('x1') + +el.getAttribute('x2')) / 2) * S.zoom;
    const my = ((+el.getAttribute('y1') + +el.getAttribute('y2')) / 2) * S.zoom;
    let px = S.panX, py = S.panY;
    const zmx = r.width * 0.28, zmy = r.height * 0.28;   // meia-largura da zona morta
    if (W > r.width + 1) {                                // mais largo que o palco: segue em X
      const fx = S.panX + mx;                            // posição do foco na viewport
      if (fx < r.width / 2 - zmx || fx > r.width / 2 + zmx) px = r.width / 2 - mx;
      px = Math.min(0, Math.max(r.width - W, px));        // clampa: board sempre cobre o palco
    }
    if (H > r.height + 1) {                               // mais alto que o palco: segue em Y
      const fy = S.panY + my;
      if (fy < r.height / 2 - zmy || fy > r.height / 2 + zmy) py = r.height / 2 - my;
      py = Math.min(0, Math.max(r.height - H, py));
    }
    if (Math.abs(px - S.panX) > 0.5 || Math.abs(py - S.panY) > 0.5) {
      S.panX = px; S.panY = py; aplicaView();
    }
  }

  // interrompe a câmera animada (ao vencer) se o usuário assume o controle
  function cancelAnimacaoCamera() {
    if (S.camRAF) { cancelAnimationFrame(S.camRAF); S.camRAF = null; }
  }
  /**
   * Anima a "câmera" de (zoom,pan) atuais até um zoom alvo, CENTRALIZANDO o
   * tabuleiro, ao longo de `dur` ms. Usado para, ao resolver, recuar devagar
   * até 100% e revelar o laço inteiro. requestAnimationFrame + easeOutCubic.
   */
  function animaCamera(zAlvo, dur) {
    if (!S.puzzle) return;
    cancelAnimacaoCamera();
    const r = $('scroll').getBoundingClientRect();
    zAlvo = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, zAlvo));
    const z0 = S.zoom, px0 = S.panX, py0 = S.panY;
    const pxA = (r.width - S.geo.w * zAlvo) / 2;     // pan alvo = centralizado
    const pyA = (r.height - S.geo.h * zAlvo) / 2;
    if (Math.abs(zAlvo - z0) < 1e-3 && Math.abs(pxA - px0) < 1 && Math.abs(pyA - py0) < 1) return;
    const svg = $('tabuleiro'); if (svg) svg.style.transition = '';   // aqui animamos via rAF
    let t0 = null;
    const quadro = (t) => {
      if (t0 === null) t0 = t;
      let u = (t - t0) / dur; if (u > 1) u = 1;
      const e = 1 - Math.pow(1 - u, 3);              // easeOutCubic (desacelera no fim)
      S.zoom = z0 + (zAlvo - z0) * e;
      S.panX = px0 + (pxA - px0) * e;
      S.panY = py0 + (pyA - py0) * e;
      aplicaView();
      S.camRAF = u < 1 ? requestAnimationFrame(quadro) : null;
    };
    S.camRAF = requestAnimationFrame(quadro);
  }

  // -------------------------------------------------- minimapa ("mapa")
  /**
   * (Re)cria o SVG do minimapa para o tabuleiro atual: usa o MESMO viewBox do
   * tabuleiro (coords do board), então arestas e visor são desenhados direto em
   * coordenadas do board. Mostra só o fundo + as arestas traçadas (sem dicas).
   */
  function montaMinimapa() {
    const mini = $('miniSvg');
    while (mini.firstChild) mini.removeChild(mini.firstChild);
    const MAX = 168;                                   // maior lado do mapa, em px
    const s = MAX / Math.max(S.geo.w, S.geo.h);
    mini.setAttribute('width', Math.round(S.geo.w * s));
    mini.setAttribute('height', Math.round(S.geo.h * s));
    mini.setAttribute('viewBox', '0 0 ' + S.geo.w + ' ' + S.geo.h);
    const board = document.createElementNS(SVGNS, 'rect');
    board.setAttribute('x', 0); board.setAttribute('y', 0);
    board.setAttribute('width', S.geo.w); board.setAttribute('height', S.geo.h);
    board.setAttribute('class', 'mini-board');
    const lines = document.createElementNS(SVGNS, 'path');
    lines.setAttribute('class', 'mini-lines');
    lines.setAttribute('vector-effect', 'non-scaling-stroke');   // traço fino constante
    const visor = document.createElementNS(SVGNS, 'rect');
    visor.setAttribute('class', 'mini-visor');
    visor.setAttribute('vector-effect', 'non-scaling-stroke');
    mini.appendChild(board); mini.appendChild(lines); mini.appendChild(visor);
    S.miniEls = { board, lines, visor };
  }
  // redesenha as arestas traçadas no minimapa (a partir de S.lines)
  function desenhaLinhasMini() {
    if (!S.miniEls || $('minimap').classList.contains('oculto')) return;
    let d = '';
    for (const key of S.lines) {
      const dots = edgeDots(key);
      d += 'M' + dx(dots[0][1]) + ',' + dy(dots[0][0]) + 'L' + dx(dots[1][1]) + ',' + dy(dots[1][0]);
    }
    S.miniEls.lines.setAttribute('d', d);
  }
  /**
   * Atualiza o retângulo "visor" (região visível) no minimapa e mostra/oculta o
   * mapa: ele só aparece quando o tabuleiro EXCEDE o palco (faz sentido navegar).
   */
  function atualizaVisor() {
    const mm = $('minimap');
    if (!S.puzzle || !S.miniEls) { return; }
    const r = $('scroll').getBoundingClientRect();
    const W = S.geo.w * S.zoom, H = S.geo.h * S.zoom;
    const precisa = W > r.width + 2 || H > r.height + 2;
    const estavaOculto = mm.classList.contains('oculto');
    mm.classList.toggle('oculto', !precisa);
    if (!precisa) return;
    const visor = S.miniEls.visor;
    visor.setAttribute('x', -S.panX / S.zoom);
    visor.setAttribute('y', -S.panY / S.zoom);
    visor.setAttribute('width', r.width / S.zoom);
    visor.setAttribute('height', r.height / S.zoom);
    if (estavaOculto) desenhaLinhasMini();             // acabou de aparecer: sincroniza
  }
  /**
   * Liga as interações do minimapa: arrastar o "grip" reposiciona o painel;
   * arrastar/clicar no corpo do mapa reposiciona a câmera (pan) do tabuleiro.
   * Usa pointer events, então funciona com mouse e toque.
   */
  function setupMinimapa() {
    const mm = $('minimap'), grip = mm.querySelector('.mini-grip'), mini = $('miniSvg');
    let movePainel = null, navega = false;
    // arrastar o ponto clicado no mapa -> centraliza a câmera nele
    const navegar = (e) => {
      const r = mini.getBoundingClientRect();
      if (!r.width || !S.puzzle) return;                     // mapa oculto/sem tabuleiro
      cancelAnimacaoCamera();
      const bx = (e.clientX - r.left) / r.width * S.geo.w;   // ponto em coords do board
      const by = (e.clientY - r.top) / r.height * S.geo.h;
      const sc = $('scroll').getBoundingClientRect();
      S.panX = sc.width / 2 - bx * S.zoom;                   // centraliza o ponto clicado
      S.panY = sc.height / 2 - by * S.zoom;
      aplicaView();
    };
    grip.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      const r = mm.getBoundingClientRect();
      movePainel = { dx: e.clientX - r.left, dy: e.clientY - r.top };
    });
    mini.addEventListener('pointerdown', (e) => { e.preventDefault(); navega = true; navegar(e); });
    // move/up no WINDOW (como o pan do botão do meio): segue o ponteiro mesmo
    // fora do painel, sem depender de setPointerCapture.
    window.addEventListener('pointermove', (e) => {
      if (movePainel) {
        const pr = $('palco').getBoundingClientRect();
        let x = e.clientX - pr.left - movePainel.dx, y = e.clientY - pr.top - movePainel.dy;
        x = Math.max(0, Math.min(pr.width - mm.offsetWidth, x));
        y = Math.max(0, Math.min(pr.height - mm.offsetHeight, y));
        mm.style.left = x + 'px'; mm.style.top = y + 'px'; mm.style.right = 'auto';
      } else if (navega) { navegar(e); }
    });
    const solta = () => { movePainel = null; navega = false; };
    window.addEventListener('pointerup', solta);
    window.addEventListener('pointercancel', solta);
  }

  // -------------------------------------------------- pan (arrastar a viewport)
  /**
   * Liga as formas de arrastar o tabuleiro dentro do contêiner .scroll:
   *  - desktop: arrastar com o botão do MEIO do mouse;
   *  - mobile:  dois dedos arrastam (pan) e pinçam (zoom) ao mesmo tempo.
   * (rolagem normal: roda do mouse / barras; teclado: setas — ver init.)
   */
  function setupPan() {
    const sc = $('scroll');

    // --- botão do meio do mouse ---
    let mid = null;
    sc.addEventListener('mousedown', (e) => {
      if (e.button !== 1) return;
      e.preventDefault();                  // evita o autoscroll do botão do meio
      cancelAnimacaoCamera();
      mid = { x: e.clientX, y: e.clientY, px: S.panX, py: S.panY };
      sc.classList.add('panning');
    });
    window.addEventListener('mousemove', (e) => {
      if (!mid) return;
      S.panX = mid.px + (e.clientX - mid.x);
      S.panY = mid.py + (e.clientY - mid.y);
      aplicaView();
    });
    window.addEventListener('mouseup', () => {
      if (mid) { mid = null; sc.classList.remove('panning'); }
    });

    // --- dois dedos: pan + pinça (mobile) ---
    const ptrs = new Map();   // pointerId -> {x,y} (apenas toques)
    let g = null;             // estado do gesto enquanto há 2 dedos
    const centroide = () => {
      const a = [...ptrs.values()];
      return {
        x: (a[0].x + a[1].x) / 2,
        y: (a[0].y + a[1].y) / 2,
        d: Math.hypot(a[0].x - a[1].x, a[0].y - a[1].y) || 1,
      };
    };
    sc.addEventListener('pointerdown', (e) => {
      if (e.pointerType !== 'touch') return;
      ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (ptrs.size === 2) {
        if (edgeAtivo) edgeAtivo.cancelar();       // cancela traço/marca do 1º dedo
        cancelAnimacaoCamera();
        S.gesturing = true;
        const c = centroide(), r = sc.getBoundingClientRect();
        // ponto de conteúdo (não-escalado) sob o centróide no início do gesto
        g = { d0: c.d, z0: S.zoom,
              cx: (c.x - r.left - S.panX) / S.zoom,
              cy: (c.y - r.top - S.panY) / S.zoom };
      }
    });
    sc.addEventListener('pointermove', (e) => {
      if (e.pointerType !== 'touch' || !ptrs.has(e.pointerId)) return;
      ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (!g || ptrs.size < 2) return;
      e.preventDefault();
      const c = centroide(), r = sc.getBoundingClientRect();
      const z = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, g.z0 * (c.d / g.d0)));
      S.zoom = z;
      // mantém o ponto de conteúdo ancorado sob o centróide atual (pan + zoom)
      S.panX = c.x - r.left - g.cx * z;
      S.panY = c.y - r.top - g.cy * z;
      aplicaView();
    }, { passive: false });
    const fimToque = (e) => {
      if (e.pointerType !== 'touch') return;
      ptrs.delete(e.pointerId);
      if (ptrs.size < 2 && g) { g = null; S.gesturing = false; }
    };
    sc.addEventListener('pointerup', fimToque);
    sc.addEventListener('pointercancel', fimToque);
  }

  // -------------------------------------------------- geração
  /**
   * Lê os controles da UI, normaliza os parâmetros e dispara a geração do
   * puzzle no Web Worker (a resposta chega em onGenerated).
   */
  function gerar() {
    stopSolve();
    const dificuldade = $('dificuldade').value;
    // 'nenhuma' não reduz dicas (geração barata), então libera tabuleiros bem
    // grandes; as demais ficam mais limitadas porque a redução de dicas é cara.
    // Os tetos são só proteção contra travar o navegador (render/redução) —
    // ainda assim, tabuleiros enormes podem demorar para desenhar.
    const maxDim = dificuldade === 'nenhuma' ? 400 : 80;
    const clamp = (v) => Math.max(3, Math.min(maxDim, Math.round(v) || 7));
    const rows = clamp(+$('linhas').value), cols = clamp(+$('colunas').value);
    $('linhas').value = rows; $('colunas').value = cols;
    let seed = $('semente').value.trim();
    // checkbox "aleatória": sempre sorteia uma semente nova (e a mostra no campo)
    if ($('aleatorio').checked || !seed) {
      seed = Math.random().toString(36).slice(2, 8);
      $('semente').value = seed;
    }
    const metodo = $('metodo').value;
    showOverlay('Gerando…');
    getWorker().postMessage({ rows, cols, seed, dificuldade, metodo });
  }
  // callback do worker: trata erro ou instala o puzzle gerado
  function onGenerated(msg) {
    hideOverlay();
    if (!msg.ok) { setStatus('Falha ao gerar: ' + msg.error, 'aviso'); return; }
    setPuzzle(msg.puzzle);
  }
  /**
   * Instala um puzzle (gerado ou importado): zera o estado de jogo, recalcula a
   * geometria, (re)constrói o SVG, renderiza e atualiza as legendas de status.
   * @param {object} p  puzzle no formato de SL.generatePuzzle.
   */
  function setPuzzle(p) {
    stopSolve();
    S.puzzle = p;
    S.lines = new Set(); S.marks = new Set(); S.colors = {}; S.colorSeq = 0;
    S.undo = []; S.redo = []; S.won = false;
    S.geo = computeGeo(p.rows, p.cols);
    S.zoom = 1;
    S.slots = [null, null, null, null, null];   // checkpoints são por tabuleiro
    atualizaCheckpoints();
    buildSvg(); refresh();
    zoomFit();                                   // ajusta e centraliza no palco
    setStatus('Tabuleiro ' + p.rows + '×' + p.cols + ' — dificuldade ' + p.dificuldade + '.');
    const metodoTxt = (p.metodo && p.dificuldade !== 'nenhuma') ? ' · ' + p.metodo : '';
    const tempoTxt = (p.ms != null) ? ' · ' + p.ms + ' ms' : '';
    $('infoPuzzle').textContent = 'Semente “' + p.seed + '”, ' + p.nClues + ' dicas' + metodoTxt + tempoTxt + '.';
  }

  // -------------------------------------------------- SVG
  /**
   * Constrói do zero o SVG do tabuleiro: textos das dicas, todas as arestas
   * (cada uma com uma linha "hit" invisível p/ clique, a linha visível e um ×
   * oculto) e os pontos. Guarda as refs em S.edgeEls / S.markEls / S.clueEls.
   */
  function buildSvg() {
    const svg = $('tabuleiro');
    svg.classList.remove('resolvido');
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute('viewBox', '0 0 ' + S.geo.w + ' ' + S.geo.h);
    montaMinimapa();   // (re)cria o minimapa p/ a geometria atual
    aplicaView();   // define width/height (zoom) + translate (pan)
    S.edgeEls = {}; S.markEls = {};

    const { rows, cols, clues } = S.puzzle;

    // dicas
    S.clueEls = [];
    for (let r = 0; r < rows; r++) {
      S.clueEls[r] = [];
      for (let c = 0; c < cols; c++) {
        if (clues[r][c] == null || clues[r][c] < 0) { S.clueEls[r][c] = null; continue; }
        const t = document.createElementNS(SVGNS, 'text');
        t.setAttribute('x', dx(c) + S.geo.gap / 2);
        t.setAttribute('y', dy(r) + S.geo.gap / 2);
        t.setAttribute('class', 'dica');
        t.setAttribute('font-size', S.geo.fonte);
        t.textContent = clues[r][c];
        svg.appendChild(t); S.clueEls[r][c] = t;
      }
    }

    const addEdge = (key, x1, y1, x2, y2) => {
      const hit = document.createElementNS(SVGNS, 'line');
      hit.setAttribute('x1', x1); hit.setAttribute('y1', y1);
      hit.setAttribute('x2', x2); hit.setAttribute('y2', y2);
      hit.setAttribute('class', 'hit');
      bindEdgePointer(hit, key);
      svg.appendChild(hit);

      const ln = document.createElementNS(SVGNS, 'line');
      ln.setAttribute('x1', x1); ln.setAttribute('y1', y1);
      ln.setAttribute('x2', x2); ln.setAttribute('y2', y2);
      ln.setAttribute('class', 'aresta grade');
      svg.appendChild(ln); S.edgeEls[key] = ln;

      // × no ponto médio (oculto por padrão)
      const mx = (x1 + x2) / 2, my = (y1 + y2) / 2, s = S.geo.mx;
      const g = document.createElementNS(SVGNS, 'path');
      g.setAttribute('d', 'M' + (mx - s) + ',' + (my - s) + ' L' + (mx + s) + ',' + (my + s)
        + ' M' + (mx - s) + ',' + (my + s) + ' L' + (mx + s) + ',' + (my - s));
      g.setAttribute('class', 'marca oculto');
      svg.appendChild(g); S.markEls[key] = g;
    };
    // arestas horizontais e verticais
    for (let r = 0; r <= rows; r++) for (let c = 0; c < cols; c++) addEdge(hKey(r, c), dx(c), dy(r), dx(c + 1), dy(r));
    for (let r = 0; r < rows; r++) for (let c = 0; c <= cols; c++) addEdge(vKey(r, c), dx(c), dy(r), dx(c), dy(r + 1));

    // pontos da grade
    for (let r = 0; r <= rows; r++) for (let c = 0; c <= cols; c++) {
      const d = document.createElementNS(SVGNS, 'circle');
      d.setAttribute('cx', dx(c)); d.setAttribute('cy', dy(r));
      d.setAttribute('r', S.geo.raio); d.setAttribute('class', 'ponto');
      svg.appendChild(d);
    }
  }

  // -------------------------------------------------- ponteiro: tap vs hold
  /**
   * Liga os eventos de ponteiro de uma aresta, distinguindo "tap" de "hold":
   * ao pressionar, agenda um timer de HOLD_MS; se disparar antes do soltar, é
   * um hold (toggleMark, ×); se soltar antes, é um tap (toggleLine, traço).
   * @param {SVGElement} el  a linha "hit" que captura o ponteiro.
   * @param {string} key  chave da aresta.
   */
  // interação de aresta em andamento (global: no máximo uma por vez). Permite
  // que o início de um gesto multitoque/pan cancele o traço/marca pendente.
  let edgeAtivo = null;

  function bindEdgePointer(el, key) {
    let timer = null, fired = false;
    const limpaTimer = () => { if (timer) { clearTimeout(timer); timer = null; } };
    const down = (ev) => {
      if (ev.pointerType === 'mouse' && ev.button !== 0) return;  // só botão esquerdo
      if (S.gesturing) return;                  // gesto multitoque em andamento
      if (edgeAtivo) { edgeAtivo.cancelar(); return; }  // 2º dedo: vira gesto, não traça
      ev.preventDefault();
      fired = false;
      edgeAtivo = { cancelar: () => { limpaTimer(); fired = true; edgeAtivo = null; } };
      timer = setTimeout(() => { fired = true; toggleMark(key); }, HOLD_MS);
    };
    const up = () => {
      limpaTimer();
      if (!fired && !S.gesturing) toggleLine(key);
      edgeAtivo = null;
    };
    const cancel = () => { limpaTimer(); fired = false; edgeAtivo = null; };
    el.addEventListener('pointerdown', down);
    el.addEventListener('pointerup', up);
    el.addEventListener('pointerleave', cancel);
    el.addEventListener('pointercancel', cancel);
    el.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  // -------------------------------------------------- movimentos
  // Um "movimento" é uma lista de mudanças { key, kind:'line'|'mark', from, to }.
  // Guardar from/to torna cada movimento reversível (undo) e re-aplicável (redo).

  // aplica (ou re-aplica) as mudanças usando o lado `to`
  function applyChanges(changes) {
    for (const ch of changes) {
      const set = ch.kind === 'mark' ? S.marks : S.lines;
      if (ch.to) set.add(ch.key); else set.delete(ch.key);
    }
  }
  // reverte as mudanças usando o lado `from`
  function revertChanges(changes) {
    for (const ch of changes) {
      const set = ch.kind === 'mark' ? S.marks : S.lines;
      if (ch.from) set.add(ch.key); else set.delete(ch.key);
    }
  }
  // registra um movimento novo: aplica, empilha no undo e limpa o redo
  function pushMove(changes) {
    stopSolve();
    applyChanges(changes);
    S.undo.push({ changes });
    S.redo = [];
    refresh();
  }

  // alterna o traço de uma aresta (e remove um × conflitante, se houver)
  function toggleLine(key) {
    if (!S.puzzle) return;
    const from = S.lines.has(key), to = !from;
    const changes = [{ key, kind: 'line', from, to }];
    if (to && S.marks.has(key)) changes.push({ key, kind: 'mark', from: true, to: false });
    pushMove(changes);
  }
  // alterna o × de uma aresta (e remove um traço conflitante, se houver)
  function toggleMark(key) {
    if (!S.puzzle) return;
    const from = S.marks.has(key), to = !from;
    const changes = [{ key, kind: 'mark', from, to }];
    if (to && S.lines.has(key)) changes.push({ key, kind: 'line', from: true, to: false });
    pushMove(changes);
  }
  // -------------------------------------------------- resolver (animação)
  // interrompe a animação em curso e restaura o botão
  function stopSolve() {
    if (S.anim) { clearInterval(S.anim); S.anim = null; }
    if (S.focoEl) { S.focoEl.classList && S.focoEl.classList.remove('foco'); S.focoEl = null; }
    const svg = $('tabuleiro'); if (svg) svg.style.transition = '';   // desliga a câmera suave
    $('resolver').textContent = '▶ Resolver';
  }
  /**
   * Anima a resolução. Pede a core.js o trace conforme o modo:
   *   - 'deducao': solveTrace (avança sempre, usa a solução conhecida);
   *   - 'busca':   solveTraceBusca (busca real, com palpites e backtracking).
   * Depois reproduz o trace passo a passo (agrupando passos por quadro quando
   * é longo), destacando a aresta corrente. Um 2º clique no botão para.
   */
  function resolver() {
    if (!S.puzzle) return;
    if (S.anim) { stopSolve(); refresh(); return; }   // segundo clique: parar
    cancelAnimacaoCamera();                            // se ainda recuava de uma vitória
    const p = S.puzzle;
    const modo = $('modoSolve').value;
    const solSet = new Set(p.solution);

    // CONTINUA do progresso do jogador: mantém só o que é consistente com a
    // solução (traços ∈ solução, marcas ∉ solução) e descarta os erros, para o
    // solver poder convergir. O tabuleiro NÃO é apagado.
    const seedLines = [...S.lines].filter((k) => solSet.has(k));
    const seedMarks = [...S.marks].filter((k) => !solSet.has(k));
    S.lines = new Set(seedLines); S.marks = new Set(seedMarks);
    S.colors = {}; S.colorSeq = 0;
    S.undo = []; S.redo = [];
    refresh();

    // 'deducao': avança sempre (usa a solução). 'busca': busca real (palpites +
    // backtracking). Ambos PARTEM do progresso do jogador (sementes).
    const trace = modo === 'busca'
      ? SL.solveTraceBusca(p.rows, p.cols, p.clues, undefined, undefined, seedLines, seedMarks)
      : SL.solveTrace(p.rows, p.cols, p.clues, p.solution, seedLines, seedMarks);

    $('resolver').textContent = '⏸ Parar';

    // velocidade = passos por segundo (slider). dPasso = ms por passo pedido.
    // Como o setInterval não roda bem abaixo de ~16ms, para velocidades ALTAS
    // (passo < 16ms) mantemos o quadro em 16ms e fazemos VÁRIOS passos por quadro
    // em vez de encurtar o delay. Para velocidades baixas/médias, 1 passo por
    // quadro no ritmo exato pedido — assim o slider é sempre respeitado.
    const sps = Math.max(2, +$('velocidade').value || 15);
    const dPasso = 1000 / sps;
    let porQuadro = 1, delay;
    if (dPasso >= 16) { delay = dPasso; }
    else { delay = 16; porQuadro = Math.max(1, Math.round(16 / dPasso)); }
    // segurança só p/ traços ENORMES (tabuleiros gigantes): nunca passar de ~2min
    // no total — e isso só ACELERA (mais passos por quadro), nunca desacelera o
    // que o usuário pediu.
    const MAX_TOTAL = 120000;
    if ((trace.length / porQuadro) * delay > MAX_TOTAL) {
      porQuadro = Math.ceil(trace.length * delay / MAX_TOTAL);
    }
    // câmera que segue o solver: transition no transform p/ o pan deslizar
    // (quanto mais rápido o solver, mais curto o deslize)
    const durCam = Math.min(700, Math.max(250, dPasso * 4));
    $('tabuleiro').style.transition = 'transform ' + durCam + 'ms ease-out';
    let i = 0;
    S.anim = setInterval(() => {
      if (i >= trace.length) {
        // busca real truncada: encerra mostrando a solução
        if (modo === 'busca' && !S.won && p.solution) {
          S.lines = new Set(p.solution); S.marks = new Set(); S.colors = {};
        }
        stopSolve(); refresh(); return;
      }
      let st;
      for (let n = 0; n < porQuadro && i < trace.length; n++) {
        st = trace[i++];
        if (st.val === 'line') { S.lines.add(st.key); S.marks.delete(st.key); }
        else if (st.val === 'empty') { S.marks.add(st.key); S.lines.delete(st.key); }
        else { S.lines.delete(st.key); S.marks.delete(st.key); }   // unset (backtrack)
      }
      refresh();
      if (S.focoEl) S.focoEl.classList.remove('foco');
      if (st) {
        S.focoEl = S.edgeEls[st.key]; if (S.focoEl) S.focoEl.classList.add('foco');
        if (!S.won) seguirFoco(st.key);   // segue a aresta — mas, ao vencer, deixa a câmera recuar
      }
    }, delay);
  }

  // desfaz o último movimento (move undo -> redo)
  function undo() {
    stopSolve();
    if (!S.undo.length) return;
    const m = S.undo.pop();
    revertChanges(m.changes);
    S.redo.push(m);
    refresh();
  }
  // refaz o último desfeito (move redo -> undo)
  function redo() {
    stopSolve();
    if (!S.redo.length) return;
    const m = S.redo.pop();
    applyChanges(m.changes);
    S.undo.push(m);
    refresh();
  }
  // apaga todos os traços e marcas como um único movimento (desfazível)
  function limpar() {
    if (!S.lines.size && !S.marks.size) return;
    const changes = [];
    for (const k of S.lines) changes.push({ key: k, kind: 'line', from: true, to: false });
    for (const k of S.marks) changes.push({ key: k, kind: 'mark', from: true, to: false });
    pushMove(changes);
  }

  // -------------------------------------------------- checkpoints (5 estados)
  // Salva o estado atual (traços, marcas e cores) no slot i (sobrescreve).
  function salvarSlot(i) {
    if (!S.puzzle) return;
    S.slots[i] = { lines: new Set(S.lines), marks: new Set(S.marks), colors: { ...S.colors } };
    atualizaCheckpoints();
    setStatus('Checkpoint ' + (i + 1) + ' salvo (' + S.lines.size + ' arestas).');
  }
  // Volta o tabuleiro ao estado salvo no slot i. É um único movimento
  // desfazível (a diferença em relação ao estado atual).
  function carregarSlot(i) {
    const s = S.slots[i];
    if (!s || !S.puzzle) return;
    stopSolve();
    const changes = [];
    for (const k of S.lines) if (!s.lines.has(k)) changes.push({ key: k, kind: 'line', from: true, to: false });
    for (const k of s.lines) if (!S.lines.has(k)) changes.push({ key: k, kind: 'line', from: false, to: true });
    for (const k of S.marks) if (!s.marks.has(k)) changes.push({ key: k, kind: 'mark', from: true, to: false });
    for (const k of s.marks) if (!S.marks.has(k)) changes.push({ key: k, kind: 'mark', from: false, to: true });
    // aplica direto (preservando as cores salvas) e registra para desfazer
    S.lines = new Set(s.lines);
    S.marks = new Set(s.marks);
    S.colors = { ...s.colors };
    if (changes.length) { S.undo.push({ changes }); S.redo = []; }
    refresh();
    setStatus('Checkpoint ' + (i + 1) + ' carregado.');
  }
  // Sincroniza os botões dos checkpoints com o que está salvo.
  function atualizaCheckpoints() {
    for (let i = 0; i < 5; i++) {
      const cheio = !!S.slots[i];
      const sv = document.querySelector('[data-save="' + i + '"]');
      const ld = document.querySelector('[data-load="' + i + '"]');
      if (sv) sv.classList.toggle('cheio', cheio);
      if (ld) { ld.classList.toggle('cheio', cheio); ld.disabled = !cheio; }
    }
  }

  // -------------------------------------------------- cores dos segmentos
  /**
   * Recolore os segmentos (componentes conexos das linhas traçadas). Agrupa as
   * arestas por componente (union-find sobre os pontos) e dá a cada componente
   * a cor MAJORITÁRIA entre as cores que suas arestas já tinham — é assim que,
   * ao fundir dois segmentos, prevalece a cor do segmento MAIOR (mais arestas).
   * Componentes sem cor anterior recebem uma cor livre da paleta (ou uma cor
   * HSL gerada quando a paleta se esgota). Atualiza S.colors in-place.
   */
  function recolor() {
    // union-find por pontos "r,c"
    const parent = {};
    const find = (x) => { while (parent[x] !== x) { x = parent[x]; } return x; };
    const ensure = (x) => { if (parent[x] === undefined) parent[x] = x; };
    for (const key of S.lines) {
      const [[r1, c1], [r2, c2]] = edgeDots(key);
      const a = r1 + ',' + c1, b = r2 + ',' + c2;
      ensure(a); ensure(b);
      const ra = find(a), rb = find(b);
      if (ra !== rb) parent[ra] = rb;
    }

    // agrupa as arestas por componente (raiz)
    const grupos = {};
    for (const key of S.lines) {
      const [[r1, c1]] = edgeDots(key);
      const root = find(r1 + ',' + c1);
      (grupos[root] = grupos[root] || []).push(key);
    }

    const novo = {};
    const usadas = new Set();
    const pendentes = [];
    // 1ª passada: componente herda a cor majoritária das suas arestas
    for (const root in grupos) {
      const arestas = grupos[root];
      const tally = {};
      for (const k of arestas) {
        const cor = S.colors[k];
        if (cor) tally[cor] = (tally[cor] || 0) + 1;
      }
      let cor = null, melhor = 0;
      for (const c in tally) if (tally[c] > melhor) { melhor = tally[c]; cor = c; }
      if (cor) {
        for (const k of arestas) novo[k] = cor;
        usadas.add(cor);
      } else {
        pendentes.push(arestas);
      }
    }
    // 2ª passada: componentes novos (sem cor anterior) ganham cor livre da paleta
    for (const arestas of pendentes) {
      let cor = PALETA.find((c) => !usadas.has(c));
      if (!cor) cor = 'hsl(' + Math.round((S.colorSeq++ * 137.5) % 360) + ',75%,62%)';
      usadas.add(cor);
      for (const k of arestas) novo[k] = cor;
    }
    S.colors = novo;
  }

  // -------------------------------------------------- derivações
  /**
   * Deriva, a partir das linhas traçadas, dois agregados usados na renderização
   * e nas checagens:
   *   - dotDeg["r,c"]: grau (nº de linhas) em cada ponto;
   *   - cellCount[r][c]: nº de arestas traçadas ao redor de cada célula.
   * @returns {{dotDeg: object, cellCount: number[][]}}
   */
  function computeDerived() {
    const { rows, cols } = S.puzzle;
    const dotDeg = {};
    const cellCount = Array.from({ length: rows }, () => new Array(cols).fill(0));
    const inc = (r, c) => { dotDeg[r + ',' + c] = (dotDeg[r + ',' + c] || 0) + 1; };
    for (const key of S.lines) {
      const [[r1, c1], [r2, c2]] = edgeDots(key);
      inc(r1, c1); inc(r2, c2);
      for (const [cr, cc] of edgeCells(key))
        if (cr >= 0 && cr < rows && cc >= 0 && cc < cols) cellCount[cr][cc]++;
    }
    return { dotDeg, cellCount };
  }
  /**
   * Aresta PROIBIDA (dica de jogo, sem ser erro ainda): traçá-la JÁ seria
   * inviável porque algum ponto já tem grau 2 ou alguma célula já bateu a dica.
   * Usada para esmaecer arestas que não podem mais entrar no laço.
   */
  function isForbidden(key, der) {
    const { rows, cols, clues } = S.puzzle;
    for (const [r, c] of edgeDots(key)) if ((der.dotDeg[r + ',' + c] || 0) >= 2) return true;
    for (const [r, c] of edgeCells(key))
      if (r >= 0 && r < rows && c >= 0 && c < cols && clues[r][c] >= 0 && der.cellCount[r][c] >= clues[r][c]) return true;
    return false;
  }
  /**
   * Aresta em ERRO: já traçada e violando uma restrição (ponto com grau > 2 ou
   * célula que excedeu a dica). Renderizada em vermelho.
   */
  function isError(key, der) {
    const { rows, cols, clues } = S.puzzle;
    for (const [r, c] of edgeDots(key)) if ((der.dotDeg[r + ',' + c] || 0) > 2) return true;
    for (const [r, c] of edgeCells(key))
      if (r >= 0 && r < rows && c >= 0 && c < cols && clues[r][c] >= 0 && der.cellCount[r][c] > clues[r][c]) return true;
    return false;
  }
  /**
   * Verifica VITÓRIA. Três condições, todas necessárias:
   *   1. toda dica está exatamente satisfeita;
   *   2. todo ponto tem grau 0 ou 2 (sem pontas nem cruzamentos);
   *   3. as linhas formam UM ÚNICO componente conexo (um só laço).
   * A condição 3 é checada por um flood fill no grafo das linhas: deve alcançar
   * todos os pontos que têm linhas.
   * @returns {boolean}
   */
  function checkWin(der) {
    const { rows, cols, clues } = S.puzzle;
    if (!S.lines.size) return false;
    // (1) dicas satisfeitas
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++)
      if (clues[r][c] >= 0 && der.cellCount[r][c] !== clues[r][c]) return false;
    // (2) todo ponto com grau 0 ou 2
    for (const k in der.dotDeg) if (der.dotDeg[k] !== 0 && der.dotDeg[k] !== 2) return false;
    // (3) conexidade: monta a lista de adjacências das linhas...
    const adj = {};
    const add = (a, b) => { (adj[a] = adj[a] || []).push(b); (adj[b] = adj[b] || []).push(a); };
    for (const key of S.lines) {
      const [[r1, c1], [r2, c2]] = edgeDots(key);
      add(r1 + ',' + c1, r2 + ',' + c2);
    }
    // ...e faz um flood fill a partir de um ponto qualquer
    const nodes = Object.keys(adj);
    const seen = new Set([nodes[0]]);
    const st = [nodes[0]];
    while (st.length) {
      const v = st.pop();
      for (const w of adj[v]) if (!seen.has(w)) { seen.add(w); st.push(w); }
    }
    return seen.size === nodes.length;
  }

  // -------------------------------------------------- render
  /**
   * Re-renderiza tudo a partir do estado atual (S): recolore, recalcula as
   * derivações e atualiza classe/cor de cada aresta, das marcas (×), das dicas
   * (ok / excesso) e a flag de vitória; sincroniza também os botões e o status.
   * É o ponto único de atualização da tela, chamado após qualquer mudança.
   */
  function refresh() {
    recolor();
    const der = computeDerived();
    const { rows, cols, clues } = S.puzzle;
    // arestas DEDUZIDAS como vazias (esmaecimento inteligente): propaga as
    // regras a partir dos traços + marcas × do jogador (não só os casos
    // imediatos). Inclui as consequências das marcas em arestas vizinhas.
    const deduzidas = SL.deduceEmpties(rows, cols, clues, [...S.lines], [...S.marks]);

    for (const key in S.edgeEls) {
      const el = S.edgeEls[key];
      const mk = S.markEls[key];
      if (S.lines.has(key)) {
        if (isError(key, der)) { el.setAttribute('class', 'aresta erro'); el.style.stroke = ''; }
        else { el.setAttribute('class', 'aresta traco'); el.style.stroke = S.colors[key] || '#4f9dff'; }
        mk.setAttribute('class', 'marca oculto');
      } else {
        el.style.stroke = '';
        el.setAttribute('class', 'aresta ' + (deduzidas.has(key) ? 'inviavel' : 'grade'));
        mk.setAttribute('class', S.marks.has(key) ? 'marca' : 'marca oculto');
      }
    }

    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const t = S.clueEls[r] && S.clueEls[r][c]; if (!t) continue;
      const n = der.cellCount[r][c], k = clues[r][c];
      t.setAttribute('class', 'dica' + (n > k ? ' excesso' : n === k ? ' ok' : ''));
    }

    const ganhou = checkWin(der);
    const venceuAgora = ganhou && !S.won;   // transição perdeu -> venceu (dispara só 1x)
    S.won = ganhou;
    $('tabuleiro').classList.toggle('resolvido', S.won);
    if (S.won) setStatus('Resolvido! 🎉', 'vitoria');
    else setStatus('Tabuleiro ' + rows + '×' + cols + ' — ' + S.lines.size + ' arestas, ' + S.marks.size + ' marcas.');

    $('desfazer').disabled = !S.undo.length;
    $('refazer').disabled = !S.redo.length;
    $('limpar').disabled = !S.lines.size && !S.marks.size;

    desenhaLinhasMini();   // espelha as arestas traçadas no minimapa

    // ao resolver (jogador OU solver), recua devagar até 100% revelando o laço
    if (venceuAgora) animaCamera(1, 1400);
  }

  // -------------------------------------------------- CSV
  /**
   * Exporta o estado atual como CSV (formato por seções na 1ª coluna): meta
   * (tamanho/seed/dificuldade), clue (dicas), sol (laço solução), line/mark
   * (jogadas atuais) e move (histórico de undo). Dispara o download do arquivo.
   */
  function exportCsv() {
    if (!S.puzzle) return;
    const p = S.puzzle;
    const linhas = [['section', 'a', 'b', 'c', 'd']];
    linhas.push(['meta', p.rows, p.cols, p.seed, p.dificuldade]);
    for (let r = 0; r < p.rows; r++) for (let c = 0; c < p.cols; c++)
      if (p.clues[r][c] >= 0) linhas.push(['clue', r, c, p.clues[r][c], '']);
    for (const k of p.solution) linhas.push(['sol', k, '', '', '']);
    for (const k of S.lines) linhas.push(['line', k, '', '', '']);
    for (const k of S.marks) linhas.push(['mark', k, '', '', '']);
    S.undo.forEach((m, i) => m.changes.forEach((ch) =>
      linhas.push(['move', i, ch.key, ch.kind, ch.to ? 'add' : 'remove'])));

    const csv = linhas.map((row) => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'slitherlink_' + p.rows + 'x' + p.cols + '_' + p.seed + '.csv';
    a.click(); URL.revokeObjectURL(url);
  }
  /**
   * Importa um CSV no formato de exportCsv: reconstrói o puzzle (meta + clues +
   * sol), instala-o e reaplica jogadas (line/mark) e o histórico de undo (move).
   * @param {string} texto  conteúdo do arquivo CSV.
   */
  function importCsv(texto) {
    const linhas = texto.split(/\r?\n/).filter((l) => l.trim().length);
    let rows = 0, cols = 0, seed = '', dif = 'medio';
    const clueRows = [], sol = [], lines = [], marks = [], movesByIdx = {};
    for (const linha of linhas) {
      const f = linha.split(',');
      switch (f[0]) {
        case 'meta': rows = +f[1]; cols = +f[2]; seed = f[3]; dif = f[4]; break;
        case 'clue': clueRows.push([+f[1], +f[2], +f[3]]); break;
        case 'sol': sol.push(f[1]); break;
        case 'line': lines.push(f[1]); break;
        case 'mark': marks.push(f[1]); break;
        case 'move': (movesByIdx[+f[1]] = movesByIdx[+f[1]] || []).push({ key: f[2], kind: f[3], action: f[4] }); break;
        default: break;
      }
    }
    if (!rows || !cols) { setStatus('CSV inválido (sem meta).', 'aviso'); return; }
    const clues = Array.from({ length: rows }, () => new Array(cols).fill(-1));
    for (const [r, c, v] of clueRows) clues[r][c] = v;

    setPuzzle({ rows, cols, seed, dificuldade: dif, clues, solution: sol, nClues: clueRows.length });
    S.lines = new Set(lines); S.marks = new Set(marks);
    const idxs = Object.keys(movesByIdx).map(Number).sort((a, b) => a - b);
    S.undo = idxs.map((i) => ({
      changes: movesByIdx[i].map((mv) => ({ key: mv.key, kind: mv.kind, to: mv.action === 'add', from: mv.action !== 'add' })),
    }));
    S.redo = []; refresh();
    setStatus('Importado: ' + rows + '×' + cols + ', ' + clueRows.length + ' dicas, ' + S.undo.length + ' movimentos.');
  }

  // -------------------------------------------------- utilidades
  // escreve a barra de status (cls opcional: 'aviso' | 'vitoria' | ...)
  function setStatus(txt, cls) { const el = $('status'); el.textContent = txt; el.className = 'status' + (cls ? ' ' + cls : ''); }
  // overlay "Gerando…" durante o trabalho do worker
  function showOverlay(txt) { $('overlayTexto').textContent = txt; $('overlay').classList.remove('oculto'); }
  function hideOverlay() { $('overlay').classList.add('oculto'); }

  /**
   * Liga os listeners dos controles e atalhos (Ctrl+Z / Ctrl+Y) e gera o
   * primeiro puzzle. Chamado no carregamento da página.
   */
  function init() {
    $('gerar').addEventListener('click', gerar);
    $('resolver').addEventListener('click', resolver);
    $('desfazer').addEventListener('click', undo);
    $('refazer').addEventListener('click', redo);
    $('limpar').addEventListener('click', limpar);
    document.querySelectorAll('[data-save]').forEach((b) =>
      b.addEventListener('click', () => salvarSlot(+b.dataset.save)));
    document.querySelectorAll('[data-load]').forEach((b) =>
      b.addEventListener('click', () => carregarSlot(+b.dataset.load)));
    $('exportar').addEventListener('click', exportCsv);
    $('importar').addEventListener('click', () => $('arquivo').click());
    $('arquivo').addEventListener('change', (e) => {
      const file = e.target.files[0]; if (!file) return;
      const reader = new FileReader();
      reader.onload = () => importCsv(String(reader.result));
      reader.readAsText(file); e.target.value = '';
    });
    // zoom: botões, Ctrl+roda (ancorado no cursor) e teclado
    $('zoomIn').addEventListener('click', () => setZoom(S.zoom * 1.25));
    $('zoomOut').addEventListener('click', () => setZoom(S.zoom / 1.25));
    $('zoomFit').addEventListener('click', zoomFit);
    $('toggleTop').addEventListener('click', toggleTopbar);
    setupMinimapa();
    // leitura ao vivo da velocidade (passos por segundo)
    const vel = $('velocidade'), velVal = $('velVal');
    const mostraVel = () => { velVal.textContent = vel.value + '/s'; };
    vel.addEventListener('input', mostraVel); mostraVel();
    let rt; window.addEventListener('resize', () => {
      clearTimeout(rt); rt = setTimeout(() => { if (S.puzzle) centraliza(); }, 150);
    });
    setupPan();
    $('scroll').addEventListener('wheel', (e) => {
      e.preventDefault();
      if (e.ctrlKey) {                                  // Ctrl+roda = zoom no cursor
        setZoom(S.zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15), e.clientX, e.clientY);
      } else if (S.puzzle) {                            // roda normal = pan (sem barras)
        cancelAnimacaoCamera();
        if (e.shiftKey) S.panX -= e.deltaY; else { S.panX -= e.deltaX; S.panY -= e.deltaY; }
        aplicaView();
      }
    }, { passive: false });
    document.addEventListener('keydown', (e) => {
      const campo = /^(INPUT|SELECT|TEXTAREA)$/.test((document.activeElement || {}).tagName || '');
      if (e.ctrlKey && e.key.toLowerCase() === 'z') { e.preventDefault(); undo(); }
      else if (e.ctrlKey && e.key.toLowerCase() === 'y') { e.preventDefault(); redo(); }
      else if (e.ctrlKey && (e.key === '=' || e.key === '+')) { e.preventDefault(); setZoom(S.zoom * 1.25); }
      else if (e.ctrlKey && e.key === '-') { e.preventDefault(); setZoom(S.zoom / 1.25); }
      else if (e.ctrlKey && e.key === '0') { e.preventDefault(); zoomFit(); }
      // setas: arrastam (pan) o tabuleiro; Shift = passo maior
      else if (!campo && e.key.indexOf('Arrow') === 0) {
        e.preventDefault();
        cancelAnimacaoCamera();
        const step = e.shiftKey ? 220 : 70;
        if (e.key === 'ArrowUp') S.panY += step;
        else if (e.key === 'ArrowDown') S.panY -= step;
        else if (e.key === 'ArrowLeft') S.panX += step;
        else if (e.key === 'ArrowRight') S.panX -= step;
        aplicaView();
      }
    });
    gerar();
  }

  // gancho de testes/depuração: expõe o estado e atalhos no window (__SL.solve()
  // preenche a solução de uma vez e devolve se isso é vitória).
  window.__SL = {
    state: S,
    solve() { S.lines = new Set(S.puzzle.solution); S.marks = new Set(); S.undo = []; S.redo = []; S.colors = {}; refresh(); return S.won; },
    toggleLine, toggleMark, undo, redo, limpar, refresh, exportCsv, importCsv,
    setZoom, zoomFit, salvarSlot, carregarSlot,
  };

  // inicializa assim que o DOM estiver pronto
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
