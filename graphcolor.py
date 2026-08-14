#!/usr/bin/env python3
"""Exact chromatic-number solver for small dense graphs.

Pure-Python 3 (stdlib only). Designed for Erdős–Rényi G(n=30, p=0.35):
returns the optimal χ(G) and a valid χ-coloring, typically well under 5 s.

Algorithm (Nash consensus — Grok + DeepSeek + GLM):
    Tomita/Bron–Kerbosch max-clique (and α via the complement) for LB
    → DSATUR + Culberson iterated greedy for UB
    → k-core reduction + clique precolor
    → exact DSATUR branch-and-bound on k-colorability, k = LB .. UB-1
      with prefix-only fresh-color symmetry, forward checking, unit
      propagation, residual-clique matching prune, and greedy *accept*
      (never greedy-as-LB — that would be unsound).

MIT License. See LICENSE.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from collections import Counter
from statistics import mean, median
from typing import List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Bit helpers
# ---------------------------------------------------------------------------

def lsb(x: int) -> int:
    """Index of the least-significant set bit. x must be nonzero."""
    return (x & -x).bit_length() - 1


def bits(x: int):
    """Yield set-bit indices of x, low to high."""
    while x:
        b = x & -x
        yield b.bit_length() - 1
        x ^= b


def bit_list(x: int) -> List[int]:
    return list(bits(x))


# ---------------------------------------------------------------------------
# Instance generator
# ---------------------------------------------------------------------------

def generate_gnp(n: int, p: float, seed: int) -> List[int]:
    """Erdős–Rényi G(n, p). Edges in lex order (i < j); Mersenne Twister."""
    rng = random.Random(seed)
    adj = [0] * n
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < p:
                adj[i] |= 1 << j
                adj[j] |= 1 << i
    return adj


def complement(adj: Sequence[int], n: int) -> List[int]:
    full = (1 << n) - 1
    return [full ^ (1 << v) ^ adj[v] for v in range(n)]


def n_edges(adj: Sequence[int], n: int) -> int:
    return sum(a.bit_count() for a in adj) // 2


# ---------------------------------------------------------------------------
# Exact maximum clique (bitset Bron–Kerbosch + Tomita pivot)
# ---------------------------------------------------------------------------

def max_clique(adj: Sequence[int], n: int) -> List[int]:
    """Exact maximum clique. Vertices in increasing id order."""
    best_set = 0
    best_size = 0

    order = sorted(range(n), key=lambda v: (-adj[v].bit_count(), v))
    seed = 0
    for v in order:
        if (seed & adj[v]) == seed:
            seed |= 1 << v
    best_set, best_size = seed, seed.bit_count()

    def expand(R: int, P: int, X: int) -> None:
        nonlocal best_set, best_size
        if P == 0:
            if X == 0:
                sz = R.bit_count()
                if sz > best_size:
                    best_set, best_size = R, sz
            return
        if R.bit_count() + P.bit_count() <= best_size:
            return

        # Tomita pivot: u ∈ P ∪ X maximizing |P ∩ N(u)|.
        u = -1
        best_nu = -1
        tmp = P | X
        while tmp:
            v = lsb(tmp)
            tmp &= tmp - 1
            nu = (P & adj[v]).bit_count()
            if nu > best_nu:
                best_nu = nu
                u = v
        cand = P if u < 0 else (P & ~adj[u])
        while cand:
            v = lsb(cand)
            cand &= cand - 1
            bit = 1 << v
            expand(R | bit, P & adj[v], X & adj[v])
            P &= ~bit
            X |= bit
            if R.bit_count() + P.bit_count() <= best_size:
                return

    expand(0, (1 << n) - 1, 0)
    return bit_list(best_set)


def max_independent_set(adj: Sequence[int], n: int) -> List[int]:
    return max_clique(complement(adj, n), n)


# ---------------------------------------------------------------------------
# Heuristic colourings (upper bounds)
# ---------------------------------------------------------------------------

def first_fit(adj: Sequence[int], n: int, order: Sequence[int]) -> List[int]:
    color = [-1] * n
    for v in order:
        used = 0
        nb = adj[v]
        while nb:
            w = lsb(nb)
            nb &= nb - 1
            if color[w] >= 0:
                used |= 1 << color[w]
        c = 0
        while (used >> c) & 1:
            c += 1
        color[v] = c
    return color


def dsatur_greedy(adj: Sequence[int], n: int, degree: Sequence[int]) -> List[int]:
    color = [-1] * n
    sat = [0] * n
    remaining = n
    while remaining:
        best = -1
        best_key = (-1, -1, -1)
        for v in range(n):
            if color[v] >= 0:
                continue
            key = (sat[v].bit_count(), degree[v], -v)
            if key > best_key:
                best_key = key
                best = v
        used = sat[best]
        c = 0
        while (used >> c) & 1:
            c += 1
        color[best] = c
        remaining -= 1
        bit = 1 << c
        nb = adj[best]
        while nb:
            w = lsb(nb)
            nb &= nb - 1
            if color[w] < 0:
                sat[w] |= bit
    return color


def _chi(color: Sequence[int]) -> int:
    return max(color) + 1 if color else 0


def iterated_greedy(
    adj: Sequence[int],
    n: int,
    color: List[int],
    rng: random.Random,
    iters: int,
) -> List[int]:
    """Culberson iterated greedy: shuffle colour-class order, first-fit again."""
    best = color[:]
    best_k = _chi(best)
    cur = color[:]
    for _ in range(iters):
        k = _chi(cur)
        classes: List[List[int]] = [[] for _ in range(k)]
        for v, c in enumerate(cur):
            classes[c].append(v)
        order_idx = list(range(k))
        rng.shuffle(order_idx)
        seq: List[int] = []
        for i in order_idx:
            rng.shuffle(classes[i])
            seq.extend(classes[i])
        cur = first_fit(adj, n, seq)
        ck = _chi(cur)
        if ck < best_k:
            best_k = ck
            best = cur[:]
            if best_k <= 1:
                break
    return best


def random_order_greedy(
    adj: Sequence[int], n: int, rng: random.Random, trials: int
) -> List[int]:
    verts = list(range(n))
    best: Optional[List[int]] = None
    best_k = n + 1
    for _ in range(trials):
        rng.shuffle(verts)
        col = first_fit(adj, n, verts)
        k = _chi(col)
        if k < best_k:
            best_k = k
            best = col
    assert best is not None
    return best


# ---------------------------------------------------------------------------
# k-core reduction (vertices of deg < k are always k-colourable last)
# ---------------------------------------------------------------------------

def k_core(adj: Sequence[int], n: int, k: int) -> Tuple[int, List[int]]:
    """Return (core_mask, elimination_order)."""
    deg = [adj[v].bit_count() for v in range(n)]
    alive = (1 << n) - 1
    elim: List[int] = []
    changed = True
    while changed:
        changed = False
        for v in range(n):
            if ((alive >> v) & 1) and deg[v] < k:
                alive &= ~(1 << v)
                elim.append(v)
                nb = adj[v]
                while nb:
                    w = lsb(nb)
                    nb &= nb - 1
                    if (alive >> w) & 1:
                        deg[w] -= 1
                changed = True
    return alive, elim


def extend_from_elim(
    adj: Sequence[int], n: int, color: List[int], elim: Sequence[int]
) -> None:
    """Colour eliminated vertices in reverse order with the lowest free colour."""
    for v in reversed(elim):
        used = 0
        nb = adj[v]
        while nb:
            w = lsb(nb)
            nb &= nb - 1
            if color[w] >= 0:
                used |= 1 << color[w]
        c = 0
        while (used >> c) & 1:
            c += 1
        color[v] = c


# ---------------------------------------------------------------------------
# Exact k-colourability — DSATUR B&B
# ---------------------------------------------------------------------------

class SearchStats:
    __slots__ = ("nodes", "decisions", "pruned_domain", "pruned_clique", "accepted_greedy")

    def __init__(self) -> None:
        self.nodes = 0
        self.decisions = 0
        self.pruned_domain = 0
        self.pruned_clique = 0
        self.accepted_greedy = 0


def k_colorable(
    adj: Sequence[int],
    n: int,
    k: int,
    clique: Sequence[int],
    degree: Sequence[int],
    stats: SearchStats,
) -> Optional[List[int]]:
    """Return a k-colouring or None. Clique is precoloured 0..ω-1."""
    if k <= 0:
        return None if n else []
    omega = len(clique)
    if omega > k:
        return None

    core_mask, elim = k_core(adj, n, k)
    # Clique vertices of deg ≥ k stay in the core; drop those that were peeled
    # (they get coloured in extend_from_elim). A peeled clique vertex would
    # contradict ω ≤ k + something, but be defensive.
    core_clique = [v for v in clique if (core_mask >> v) & 1]
    if len(core_clique) > k:
        return None

    full = (1 << k) - 1
    color = [-1] * n
    sat = [0] * n
    n_used = 0
    n_colored = 0
    dead = False

    def do_assign(v: int, c: int):
        nonlocal n_used, n_colored, dead
        old_used = n_used
        color[v] = c
        n_colored += 1
        if c == n_used:
            n_used = c + 1
        bit = 1 << c
        saved = []
        nb = adj[v]
        while nb:
            w = lsb(nb)
            nb &= nb - 1
            if color[w] < 0:
                old = sat[w]
                ns = old | bit
                if ns != old:
                    saved.append((w, old))
                    sat[w] = ns
                    if (ns & full) == full:
                        dead = True
        return saved, old_used

    def undo_assign(v: int, saved, old_used: int) -> None:
        nonlocal n_used, n_colored, dead
        color[v] = -1
        n_colored -= 1
        n_used = old_used
        for w, old in saved:
            sat[w] = old
        dead = False

    def undo_chain(chain) -> None:
        for v, saved, old_used in reversed(chain):
            undo_assign(v, saved, old_used)

    # Precolour the surviving clique.
    for i, v in enumerate(core_clique):
        saved, _ = do_assign(v, i)
        if dead:
            return None

    core_size = core_mask.bit_count()

    def residual_clique_uncolorable() -> bool:
        """Exact matching: greedy residual clique vs. current colour domains."""
        rem = 0
        for v in range(n):
            if color[v] < 0:
                rem |= 1 << v
        if rem.bit_count() < 2:
            return False
        C: List[int] = []
        cand = rem
        while cand:
            best_v = -1
            best_d = -1
            t = cand
            while t:
                v = lsb(t)
                t &= t - 1
                d = (adj[v] & cand).bit_count()
                if d > best_d:
                    best_d = d
                    best_v = v
            C.append(best_v)
            cand &= adj[best_v]
        m = len(C)
        if m <= 1:
            return False
        mate = [-1] * k

        def dfs(i: int, seen: List[bool]) -> bool:
            v = C[i]
            dom = (~sat[v]) & full
            while dom:
                c = lsb(dom)
                dom &= dom - 1
                if seen[c]:
                    continue
                seen[c] = True
                if mate[c] < 0 or dfs(mate[c], seen):
                    mate[c] = i
                    return True
            return False

        for i in range(m):
            if not dfs(i, [False] * k):
                return True
        return False

    def try_greedy_complete() -> bool:
        """Sound *accept*: if DSATUR finishes with ≤ k colours, keep it.

        This is an upper-bound heuristic on the residual, never a prune.
        """
        col = color[:]
        sm = sat[:]
        left = [v for v in range(n) if col[v] < 0]
        while left:
            best = left[0]
            best_key = (-1, -1, -1)
            for v in left:
                key = ((sm[v] & full).bit_count(), degree[v], -v)
                if key > best_key:
                    best_key = key
                    best = v
            dom = (~sm[best]) & full
            if not dom:
                return False
            c = lsb(dom)
            col[best] = c
            bit = 1 << c
            left.remove(best)
            nb = adj[best]
            while nb:
                w = lsb(nb)
                nb &= nb - 1
                if col[w] < 0:
                    sm[w] |= bit
        for v in range(n):
            color[v] = col[v]
        stats.accepted_greedy += 1
        return True

    def propagate(chain) -> bool:
        """Unit-propagate singleton domains. Appends forced assigns to chain."""
        nonlocal dead
        while True:
            progress = False
            for v in range(n):
                if color[v] >= 0:
                    continue
                if not ((core_mask >> v) & 1):
                    continue
                dom = (~sat[v]) & full
                if dom == 0:
                    stats.pruned_domain += 1
                    return False
                if (dom & (dom - 1)) == 0:
                    c = lsb(dom)
                    # A singleton domain cannot be a non-prefix fresh colour:
                    # every unused colour is available, so the only legal
                    # singleton-fresh is c == n_used. If c > n_used the
                    # prefix invariant is already broken — treat as fail.
                    if c > n_used:
                        stats.pruned_domain += 1
                        return False
                    saved, old_used = do_assign(v, c)
                    chain.append((v, saved, old_used))
                    if dead:
                        stats.pruned_domain += 1
                        return False
                    progress = True
            if not progress:
                return True

    def search() -> bool:
        nonlocal dead
        stats.nodes += 1
        chain: list = []
        if not propagate(chain):
            undo_chain(chain)
            return False
        if n_colored >= core_size:
            return True
        rem = 0
        for u in range(n):
            if color[u] < 0 and ((core_mask >> u) & 1):
                rem |= 1 << u
        # Independent residual: each vertex only fights already-coloured
        # neighbours, so any nonempty domain is a valid assignment.
        indep = True
        t = rem
        while t:
            u = lsb(t)
            t &= t - 1
            if adj[u] & rem:
                indep = False
                break
        if indep:
            for u in bits(rem):
                dom = (~sat[u]) & full
                if not dom:
                    undo_chain(chain)
                    return False
                do_assign(u, lsb(dom))
            return True
        uncolored = rem.bit_count()
        # Greedy is an *accept* heuristic. On infeasible k it always fails,
        # so running it at every node multiplies the hard-tail cost. Try it
        # only when the residual is small enough that a hit is plausible.
        if uncolored <= 14 and try_greedy_complete():
            return True
        if uncolored >= 8 and residual_clique_uncolorable():
            stats.pruned_clique += 1
            undo_chain(chain)
            return False

        best_v = -1
        best_key = (-1, -1, -1)
        for v in range(n):
            if color[v] >= 0 or not ((core_mask >> v) & 1):
                continue
            sm = sat[v] & full
            dom = (~sm) & full
            if dom == 0:
                stats.pruned_domain += 1
                undo_chain(chain)
                return False
            key = (sm.bit_count(), degree[v], -v)
            if key > best_key:
                best_key = key
                best_v = v

        if best_v < 0:
            return True

        stats.decisions += 1
        v = best_v
        domain = (~sat[v]) & full
        while domain:
            c = lsb(domain)
            domain &= domain - 1
            if c > n_used:
                break
            saved, old_used = do_assign(v, c)
            ok = (not dead) and search()
            if ok:
                return True
            undo_assign(v, saved, old_used)
        undo_chain(chain)
        return False

    if not search():
        return None
    extend_from_elim(adj, n, color, elim)
    if any(c < 0 for c in color):
        return None
    return color


# ---------------------------------------------------------------------------
# Top-level solve
# ---------------------------------------------------------------------------

SOLVER_SEED = 0xC01A
IG_ITERS = 200
RANDOM_GREEDY_TRIALS = 80


class SolveInfo:
    __slots__ = (
        "chi",
        "coloring",
        "lb",
        "ub",
        "omega",
        "alpha",
        "stats",
        "closed_by",
    )

    def __init__(self) -> None:
        self.chi = 0
        self.coloring: List[int] = []
        self.lb = 0
        self.ub = 0
        self.omega = 0
        self.alpha = 0
        self.stats = SearchStats()
        self.closed_by = ""


def solve(adj: Sequence[int], n: int, rng_seed: int = SOLVER_SEED) -> SolveInfo:
    info = SolveInfo()
    if n == 0:
        info.closed_by = "empty"
        return info

    degree = [adj[v].bit_count() for v in range(n)]
    clique = max_clique(adj, n)
    indep = max_independent_set(adj, n)
    omega = len(clique)
    alpha = max(1, len(indep))
    lb = max(omega, (n + alpha - 1) // alpha)
    info.omega, info.alpha, info.lb = omega, alpha, lb

    rng = random.Random(rng_seed)

    ds = dsatur_greedy(adj, n, degree)
    best = ds
    ub = _chi(best)
    if ub > lb:
        ig = iterated_greedy(adj, n, best[:], rng, IG_ITERS)
        if _chi(ig) < ub:
            best, ub = ig, _chi(ig)
    if ub > lb:
        rg = random_order_greedy(adj, n, rng, RANDOM_GREEDY_TRIALS)
        if _chi(rg) < ub:
            best, ub = rg, _chi(rg)
    info.ub = ub

    if ub == lb:
        info.chi = ub
        info.coloring = best
        info.closed_by = "bounds"
        return info

    stats = info.stats
    found: Optional[List[int]] = None
    chi = ub
    for k in range(lb, ub):
        col = k_colorable(adj, n, k, clique, degree, stats)
        if col is not None:
            found = col
            chi = k
            break
    if found is None:
        info.chi = ub
        info.coloring = best
        info.closed_by = "ub-proven"
    else:
        info.chi = chi
        info.coloring = found
        info.closed_by = f"k={chi}"
    return info


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(adj: Sequence[int], n: int, chi: int, coloring: Sequence[int]) -> None:
    if len(coloring) != n:
        raise AssertionError(f"coloring length {len(coloring)} != n={n}")
    if n == 0:
        if chi != 0:
            raise AssertionError("empty graph must have χ=0")
        return
    if any(c < 0 or c >= chi for c in coloring):
        raise AssertionError(f"colour out of range 0..{chi-1}: {list(coloring)}")
    used = set(coloring)
    if used != set(range(chi)):
        raise AssertionError(f"colours {sorted(used)} are not the prefix 0..{chi-1}")
    for u in range(n):
        nb = adj[u]
        while nb:
            v = lsb(nb)
            nb &= nb - 1
            if v > u and coloring[u] == coloring[v]:
                raise AssertionError(f"monochromatic edge {u}-{v} colour={coloring[u]}")


def read_edgelist(path: str) -> Tuple[List[int], int]:
    """First line 'n m', then m lines 'u v' (0- or 1-based, auto-detected)."""
    with open(path, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    n, m = map(int, lines[0].split())
    adj = [0] * n
    one_based = False
    edges = [tuple(map(int, ln.split()[:2])) for ln in lines[1 : 1 + m]]
    if edges and min(min(u, v) for u, v in edges) >= 1 and max(max(u, v) for u, v in edges) == n:
        one_based = True
    for u, v in edges:
        if one_based:
            u -= 1
            v -= 1
        if u == v or not (0 <= u < n and 0 <= v < n):
            continue
        adj[u] |= 1 << v
        adj[v] |= 1 << u
    return adj, n


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _pct(sorted_xs: Sequence[float], p: float) -> float:
    if not sorted_xs:
        return 0.0
    i = min(len(sorted_xs) - 1, max(0, int(p * len(sorted_xs))))
    return float(sorted_xs[i])


def run_bench(n: int, p: float, n_inst: int, verbose: bool) -> int:
    # Warm-up (import / first-touch), not timed.
    solve(generate_gnp(n, p, 0), n)

    times: List[float] = []
    chis: List[int] = []
    t_all = time.perf_counter()
    ok = 0
    for seed in range(n_inst):
        adj = generate_gnp(n, p, seed)
        t0 = time.perf_counter()
        info = solve(adj, n)
        dt = time.perf_counter() - t0
        try:
            validate(adj, n, info.chi, info.coloring)
            status = "OK"
            ok += 1
        except AssertionError as exc:
            status = f"FAIL:{exc}"
        times.append(dt)
        chis.append(info.chi)
        extra = ""
        if verbose:
            extra = (
                f" lb={info.lb} ub={info.ub} ω={info.omega} α={info.alpha}"
                f" nodes={info.stats.nodes} via={info.closed_by}"
            )
        print(
            f"seed={seed:3d} chi={info.chi} time={dt:.4f}s status={status}{extra}",
            flush=True,
        )
    times_sorted = sorted(times)
    print("--- summary ---")
    print(f"n={n} p={p} instances={n_inst}")
    print(
        f"mean={mean(times):.4f}s median={median(times):.4f}s "
        f"p95={_pct(times_sorted, 0.95):.4f}s max={times_sorted[-1]:.4f}s"
    )
    hist = Counter(chis)
    print("chi histogram:", " ".join(f"{c}:{hist[c]}" for c in sorted(hist)))
    print(f"correct={ok}/{n_inst} total_wall={time.perf_counter() - t_all:.2f}s")
    return 0 if ok == n_inst else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="graphcolor",
        description="Exact graph colouring (pure Python, bitset DSATUR B&B).",
    )
    ap.add_argument("--bench", type=int, default=0, help="G(n,p) instances, seeds 0..BENCH-1")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--p", type=float, default=0.35)
    ap.add_argument("--seed", type=int, default=0, help="single-instance seed when --bench=0")
    ap.add_argument("--graph", type=str, default=None, help="edge-list file: 'n m' then m 'u v'")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--coloring", action="store_true", help="print the colour array")
    args = ap.parse_args(argv)

    if args.graph:
        adj, n = read_edgelist(args.graph)
        t0 = time.perf_counter()
        info = solve(adj, n)
        dt = time.perf_counter() - t0
        validate(adj, n, info.chi, info.coloring)
        print(f"chi={info.chi} time={dt:.4f}s status=OK")
        if args.coloring or args.verbose:
            print("coloring:", " ".join(map(str, info.coloring)))
        return 0

    if args.bench > 0:
        return run_bench(args.n, args.p, args.bench, args.verbose)

    adj = generate_gnp(args.n, args.p, args.seed)
    t0 = time.perf_counter()
    info = solve(adj, args.n)
    dt = time.perf_counter() - t0
    validate(adj, args.n, info.chi, info.coloring)
    extra = ""
    if args.verbose:
        extra = (
            f" lb={info.lb} ub={info.ub} ω={info.omega} α={info.alpha}"
            f" nodes={info.stats.nodes} via={info.closed_by}"
            f" edges={n_edges(adj, args.n)}"
        )
    print(f"seed={args.seed} chi={info.chi} time={dt:.4f}s status=OK{extra}")
    if args.coloring or args.verbose:
        print("coloring:", " ".join(map(str, info.coloring)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
