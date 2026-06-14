# slytherlink

### ▶ Play it live: **[slitherlink.lucas.mat.br](https://slitherlink.lucas.mat.br)**

**English** · [Português (pt-BR)](README.pt-BR.md)

A from-scratch **Slitherlink** toolkit: a constructive puzzle **generator**, a
constraint‑propagation **solver**, several **clue‑reduction** strategies, and a
playable, dependency‑free **browser game** — with the theory and benchmarks
behind each piece documented below.

There are two implementations that share the same ideas:

| | Language | Where | Role |
|---|---|---|---|
| **Library** | Python (NumPy, NetworkX, OpenCV, optional OR‑Tools) | repo root | Reference engine: generators, solver (+ CP‑SAT), clue reduction, image/video rendering. |
| **Game** | Vanilla JavaScript (no framework, no backend) | [`web/`](web/) | Static single‑page app: a full port of the engine plus an interactive board. |

---

## Table of contents

- [What is Slitherlink?](#what-is-slitherlink)
- [The theory](#the-theory)
  - [A loop is the boundary of a region](#1-a-loop-is-the-boundary-of-a-region)
  - [Why uniqueness is the whole problem (monotonicity)](#2-why-uniqueness-is-the-whole-problem-monotonicity)
- [Generation](#generation)
- [The solver](#the-solver)
- [Clue reduction (making a puzzle)](#clue-reduction-making-a-puzzle)
- [Difficulty and the animated solver](#difficulty-and-the-animated-solver)
- [Performance](#performance)
- [The browser game](#the-browser-game)
- [Repository layout](#repository-layout)
- [Running it](#running-it)
- [References & acknowledgements](#references--acknowledgements)
- [License](#license)

---

## What is Slitherlink?

Slitherlink (also *Loop the Loop*, *Fences*) is played on a grid of dots. You
draw a **single closed loop** along the grid edges so that every numbered cell
has *exactly* that many of its four sides on the loop. A correct puzzle has
**one** solution, reachable by logic alone.

```
.   .   .   .          ┌───┐   .   .
  3   2                │ 3 │ 2
.   .   .   .    →     │   └───┐   .
  2   . 1             │ 2   . │1
.   .   .   .          └───────┘   .
```

---

## The theory

### 1. A loop is the boundary of a region

By the **Jordan curve theorem**, a single closed loop partitions the plane into
an *inside* and an *outside*. Equivalently: **the loop is exactly the boundary
of its interior region**. This is the cornerstone of the whole project, used in
both directions:

- **Generation runs it forwards.** Instead of *searching* for a valid loop, we
  *grow a region of cells* and take its contour. The contour is a single simple
  loop **if and only if** the region is:
  1. **edge‑connected** (one piece),
  2. **simply connected** (no holes — the complement stays connected to the
     border), and
  3. **corner‑touch‑free** (no two region cells touch only diagonally, which
     would create a degree‑4 pinch point in the contour).

  Maintaining those three invariants while growing means the result is *correct
  by construction* — no trial and error.

- **The solver runs it backwards** (in the inside/outside formulation): an edge
  is on the loop ⇔ its two adjacent cells (counting the exterior) are on
  opposite sides, and a clue `k` means "exactly `k` of my neighbours are on the
  opposite side."

A consequence used by the solver: a closed loop crosses any straight grid line
an **even** number of times (the *cut‑parity* rule), which is a cheap, powerful
deduction.

### 2. Why uniqueness is the whole problem (monotonicity)

Each clue is a **constraint that removes candidate loops**. So if `S(C)` is the
set of valid loops consistent with a clue set `C`, then

> `C' ⊆ C  ⟹  S(C) ⊇ S(C')`  — removing clues can only **grow** the solution set.

Two important corollaries:

- **Solvability is free.** A loop we generated satisfies *every* clue it
  produced, so it remains a valid solution of *any* subset of those clues. We
  never risk making a puzzle unsolvable by removing clues.
- **Uniqueness is the entire battle.** The full clue map almost always has one
  solution; removing clues can only add solutions. So clue reduction is a hunt
  for a *small* subset that is *still unique* — and the monotonicity above is
  exactly what makes the **binary‑search** reducer valid (see below).

Deciding uniqueness is NP‑complete in general (Slitherlink is NP‑complete), but
constraint propagation makes it fast in practice at game sizes.

---

## Generation

The loop is built **constructively**, never by rejection sampling.

- **Region growth (`generateLoop`, both implementations).** Start from a seed
  cell and repeatedly annex frontier cells, each time checking the three
  invariants above (corner‑touch via a local test, no‑holes via a flood fill).
  The loop length equals the region's perimeter, so growth simply stops at a
  target density. To avoid leaving a board half empty on elongated boards, the
  JS version grows in **two phases**: a *spread* phase that prefers cells which
  extend the region's bounding box until it covers ≥85 % of both axes, then a
  *wiggle* phase that maximises perimeter for detail. Default density `0.75`.
- **Hamiltonian loop (`gera_caminho_hamiltoniano`, Python).** For full‑coverage
  boards (density `1.0`), draw a random spanning tree of the 2×2 super‑cell grid
  and take the contour of that "thickened" tree. Because the tree is connected
  and acyclic, the contour is provably one cycle through **every** vertex.
  `O(n log n)`, no retries. (Requires even dimensions — an odd‑vertex grid is
  bipartite and admits no Hamiltonian cycle.)

The old approach this replaced — a self‑avoiding random walk that retries until
it closes a large loop — is both slow and unable to guarantee coverage; see the
[performance](#performance) numbers for the contrast.

---

## The solver

A single primitive underlies everything: *count the solutions of a clue set, up
to 2* (a **uniqueness oracle**). It combines **constraint propagation** with
**backtracking search**.

**Propagation** repeatedly applies forced deductions to a tri‑state edge model
(unknown / line / cross) until a fixpoint:

- **Vertex rule** — every dot has degree 0 or 2: two lines ⇒ its other edges are
  crosses; one line with a single unknown left ⇒ that edge is a line; etc.
- **Cell rule** — a cell with clue `k` and `k` lines already ⇒ its remaining
  edges are crosses; if lines + unknowns equals `k` ⇒ the unknowns are lines.
- **Cut‑parity rule** (Python) — each grid cut carries an even number of lines.

When propagation stalls, the search **branches** on an edge (preferring one at
the end of an open path), recursing and counting solutions, stopping at 2.

Two structural devices keep it correct and fast:

- **Union‑find for single‑loop detection.** Path fragments are tracked in a
  disjoint‑set structure; an edge that would close a cycle is rejected *unless*
  it completes the whole solution (all clues satisfied, no other line segments)
  — the subtour‑elimination of Slitherlink.
  - ⚠️ **The union‑find must NOT use path compression.** The search *undoes*
    unions on backtrack; path compression mutates parent pointers of nodes that
    aren't recorded on the undo trail, which silently corrupts the structure on
    rollback and makes the solver **undercount** solutions. (We hit exactly this
    bug in the JS port — it produced "unique" puzzles that actually had two
    solutions. Plain `find` with union‑by‑size is rollback‑safe.) It was caught
    by a fuzzer that compares the solver against brute force on small boards.
- **Connectivity pruning.** If the placed line fragments can no longer be joined
  into one component through still‑available edges, the branch is abandoned.

**`solver_cpsat.py` (Python, optional).** For large boards there is an OR‑Tools
**CP‑SAT** oracle: it models the single loop with `AddCircuit` (each edge → two
directed arcs, plus a self‑loop per skipped vertex), adds the clue and redundant
degree/parity constraints, and — crucially — feeds the known target loop as an
`AddHint` so the first solution is found instantly and each call costs only the
*refutation* of a second solution. Without the hint + redundant constraints a
sparse 20×20 took 60 s and found nothing; with them, 0.5 s.

---

## Clue reduction (making a puzzle)

Turning a full clue map into a puzzle means removing clues while preserving
uniqueness. The project keeps **multiple strategies as selectable options** (in
the browser game, a dropdown), because they trade speed against minimality
differently:

| Method | Idea | Character |
|---|---|---|
| **Greedy** (`reduceClues`) | Shuffle cells; remove each if the result is still unique (`O(n)` oracle calls). | Near‑minimal; slow on big boards. |
| **Binary search** (`reduceCluesBinaria`) | Monotonicity ⇒ "the first *k* of a shuffled order are jointly removable" is monotone in *k*, so **binary‑search** the max removable prefix in `O(log n)` calls per round; re‑shuffle and repeat. | **Fast** (≈10× on large boards); a few more clues. |
| **CEGAR** (`reduceCluesCEGAR`) | Counterexample‑guided, bottom‑up: start with some clues; while the solver finds a solution ≠ target, add a clue where they differ (killing that counterexample); a cache of past counterexamples avoids redundant solver calls. | Tends to the **fewest** clues; slowest. |

Difficulty is then tuned by **adding some removed clues back** (more clues =
easier). Since any superset of a unique clue set is still unique (monotonicity),
this never breaks the puzzle.

> **A hard‑won practical note:** the solver explodes combinatorially when there
> are *very few* clues (it degenerates into enumerating self‑avoiding walks), not
> when there are many. That is why CEGAR seeds with ~50 % of the clues instead of
> starting empty, and why a node/step budget guards every oracle call.

The Python library (`reduz_dicas`) implements the CEGAR strategy with a
counterexample cache plus a final greedy minimisation and optional 180°
rotational symmetry.

---

## Difficulty and the animated solver

The game can **animate** a solve, in two honest modes:

- **Deduction (oracle).** Because the unique solution is known, this propagates
  forced deductions and, when stuck, places the *next correct loop edge*. It
  **never backtracks** — a clean, always‑forward fill. (The clue‑saturation and
  degree deductions appear as crosses; the loop grows in colour.)
- **Real search (backtracking).** An *answer‑blind* search from the clues alone:
  it guesses, hits contradictions, **erases, and re‑routes**. You can literally
  watch it struggle. An *all‑clues* board solves with **zero** backtracking
  (pure logic); a minimal *hard* board thrashes — a nice visualisation of "how
  much guessing does this puzzle need."

A minimal hard 9×9 needs ~485 k search steps, so the real‑search trace is capped
(8 000 steps) and snaps to the solution if it runs over.

---

## Performance

Indicative numbers (single core; your hardware will differ). They illustrate the
*shape* of the trade‑offs, not absolute speed.

**Constructive generation beats the old random walk decisively** (Python,
20×20, target density 0.9):

| Generator | Result | Time |
|---|---|---|
| Old self‑avoiding random walk (2000 retries) | peaked at density **0.69** | 14.3 s |
| New constructive (`gera_Tabuleiro2`) | density **0.90** | **0.13 s** |

**Clue‑reduction methods** (JS engine, Node; same board per row, so the loop is
identical and only the reducer differs):

| Board / difficulty | Greedy | Binary search | CEGAR |
|---|---|---|---|
| 10×10 hard | 33 clues · ~3.4 s | 39 clues · ~1.0 s | 29 clues · ~1.5 s |
| 14×14 hard | 69 clues · ~13.7 s | 88 clues · ~11.3 s | 64 clues · ~24.7 s |
| 18×18 medium | 203 clues · ~74 s | 237 clues · **~7 s** | 155 clues · ~89 s |

Takeaway: **binary search** wins big on large boards (≈10×) for a few extra
clues; **CEGAR** yields the fewest clues but is slowest; **greedy** is the
balanced middle. (These instances are NP‑hard, so per‑board variance is high.)

**All‑clues generation** (no reduction) is cheap even when large: 50×50 in
< 1 s, 60×60 ≈ 0.85 s (JS).

**Python clue reduction with the CP‑SAT oracle** (full pipeline): 10×10 ≈ 2 s,
14×14 ≈ 14 s, 20×20 ≈ 2 min (361 → 162 clues), 24×24 ≈ 9 min.

**Loop coverage fix:** on a 7×20 board the worst contiguous block of `0`‑clues
("dead space") dropped from ~41 cells to ~10 after the spread‑growth + density
change, while keeping a varied clue mix (~14 % zeros, ~27 % ones).

---

## The browser game

A static, offline, dependency‑free SPA in [`web/`](web/) — deploys as plain
files behind any web server. Highlights:

- **Top bar:** independent rows/cols, a text **seed** (any string; blank or the
  *random* checkbox draws a fresh one and writes it back so it's reproducible),
  **difficulty** (incl. *None* = show every clue), the **reduction method**
  selector, and generation timing.
- **Play:** click an edge to draw/erase a line; **press‑and‑hold** to mark it
  *impossible* (×). The grid is dotted; edges that are automatically impossible
  (around a `0`, or a third edge at a degree‑2 vertex) are shown fainter.
- **Segment colouring:** each connected chain of lines gets its own colour;
  when two chains merge, the **larger** one's colour wins.
- **Solve** with the deduction or real‑search animation; **undo/redo**, reset.
- **CSV import/export** of the whole state (board, solution, current lines,
  ×‑marks, *and* the move history). Edges are identified as `H:r:c` / `V:r:c`.

See [`web/README.md`](web/README.md) for the CSV schema and controls in detail.

Generation runs in a **Web Worker** so the UI never blocks, and assets are
cache‑busted by a `?v=` version query.

---

## Repository layout

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

## Running it

**The game** (Web Workers need `http://`, not `file://`):

```bash
cd web
python -m http.server 8778      # then open http://127.0.0.1:8778
```

**The Python library:**

```bash
pip install numpy networkx opencv-python matplotlib tqdm
pip install ortools             # optional, speeds up large-board reduction
python teste_slitherlink.py     # generator tests / benchmark
python teste_puzzle.py          # solver + clue-reduction tests
```

**Engine tests (Node):**

```bash
cd web
node js/test_core.js            # generation + uniqueness across sizes/difficulties
node js/fuzz_core.js            # solver compared to brute force on small boards
```

## References & acknowledgements

- **Liam Appelbe — [_How to generate Slither Link puzzles_](https://liamappelbe.medium.com/how-to-generate-slither-link-puzzles-6c65510b2ba1).** This project's region/cell‑colouring approach to loop generation and its **binary‑search clue removal** are directly informed by this excellent writeup — well worth reading.
- Jonathan Olson — [_How Slitherlink Should Be Solved_](https://jonathanolson.net/slitherlink/): a catalogue of the logical solving patterns.
- Yoshinaka, Saitoh, Kawahara, Tsuruma, Iwashita & Minato — [_Finding All Solutions and Instances of Numberlink and Slitherlink by ZDDs_](https://www.mdpi.com/1999-4893/5/2/176), *Algorithms* 5(2), 2012.

## License

See [LICENSE](LICENSE).
