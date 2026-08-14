# graphcolor

Exact chromatic-number solver in **pure Python 3** (stdlib only).

Built with a **Nash loop** on MCP Reasoner: Grok 4.6 + DeepSeek + GLM.
The two external designs each contained an unsound lower bound; both were
rejected. The shipped solver is the equilibrium. See [`nash/CRITIQUE.md`](nash/CRITIQUE.md).

## Result (the number that matters)

```
python3 graphcolor.py --bench 200 --n 30 --p 0.35
```

| | measured | challenge |
|---|---|---|
| instances | G(30, p=0.35), seeds 0..199 | same |
| correct χ + colouring | **200 / 200** | 200 / 200 |
| mean `solve()` | **0.0196 s** | < 5 s |
| p95 | **0.0267 s** | < 15 s |
| max | 0.0280 s | no hang |
| χ histogram | 4:1 · 5:92 · 6:106 · 7:1 | — |

CPython 3.14.4, 1 thread, Intel Xeon E5-2673 v3 @ 2.40 GHz.
`ensemble_judge` on the final design: **0.97** (σ = 0.03).

## Algorithm

**Bitset DSATUR k-colourability B&B**

1. **LB** — exact ω (Bron–Kerbosch + Tomita pivot) and exact α (clique of
   the complement). `lb = max(ω, ceil(n/α))`.
2. **UB** — DSATUR greedy, Culberson iterated greedy (200), random-order
   first-fit (80). Stop if `ub == lb`.
3. **Exact** — for `k = lb .. ub-1`, decide k-colourability:
   - k-core reduction (deg < k coloured last);
   - precolour a maximum clique `0..ω-1`;
   - DSATUR branch (max saturation, then degree, then id);
   - prefix-only fresh colour (`c > n_used` is forbidden — safe symmetry);
   - forward checking + unit propagation + delta-undo;
   - residual-clique ↔ colour matching (sound prune);
   - greedy / independent-set on the residual is **accept-only**.
4. First feasible k is χ. Failure of k = χ−1 is the optimality certificate.

What the Nash loop tried and we **refused**:

- GLM: prune when residual greedy uses too many colours (greedy is an
  *upper* bound — unsound).
- DeepSeek: prune when `ceil(n / q_greedy) > k` (q does not upper-bound α).
- DeepSeek: replace the engine with Lawler MIS enumeration (correct in
  principle, worse tail in CPython at this density).

## Usage

```bash
# official challenge bench
python3 graphcolor.py --bench 200 --n 30 --p 0.35 --verbose

# one seeded instance
python3 graphcolor.py --seed 14 --n 30 --p 0.35 --verbose --coloring

# edge list: first line "n m", then m lines "u v"
python3 graphcolor.py --graph instance.txt --coloring

# tests (Petersen, Grötzsch, cycles, wheels, K_n, random)
python3 -m unittest test_graphcolor -v
```

No dependencies. Python 3.10+ (uses `int.bit_count()`).

## Layout

```
graphcolor.py         solver + CLI
test_graphcolor.py    known graphs + random G(n,p)
LICENSE               MIT
nash/CRITIQUE.md      full Nash critique transcript
video/nash_critique.gif   replay of the critique iterations
video/index.html          same frames, play/pause
```

## License

MIT. Open source, one file, no native code.
# desafiogrok
