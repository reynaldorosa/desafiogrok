#!/usr/bin/env python3
"""Correctness tests for the exact colouring solver."""

from __future__ import annotations

import unittest

from graphcolor import (
    generate_gnp,
    k_colorable,
    max_clique,
    n_edges,
    solve,
    validate,
    SearchStats,
)


def from_edges(n: int, edges) -> list:
    adj = [0] * n
    for u, v in edges:
        adj[u] |= 1 << v
        adj[v] |= 1 << u
    return adj


class TestKnownGraphs(unittest.TestCase):
    def _check(self, adj, n, expected_chi):
        info = solve(adj, n)
        validate(adj, n, info.chi, info.coloring)
        self.assertEqual(info.chi, expected_chi, msg=f"ω={info.omega} α={info.alpha}")
        self.assertGreaterEqual(info.chi, info.omega)
        self.assertGreaterEqual(info.chi, (n + info.alpha - 1) // max(1, info.alpha))

    def test_empty_n1(self):
        self._check([0], 1, 1)

    def test_empty_n5(self):
        self._check([0] * 5, 5, 1)

    def test_single_edge(self):
        self._check(from_edges(2, [(0, 1)]), 2, 2)

    def test_complete(self):
        for n in range(2, 11):
            full = (1 << n) - 1
            adj = [full ^ (1 << v) for v in range(n)]
            self._check(adj, n, n)

    def test_odd_cycles(self):
        for n in (3, 5, 7, 9, 11):
            edges = [(i, (i + 1) % n) for i in range(n)]
            self._check(from_edges(n, edges), n, 3)

    def test_even_cycles(self):
        for n in (4, 6, 8, 10, 12):
            edges = [(i, (i + 1) % n) for i in range(n)]
            self._check(from_edges(n, edges), n, 2)

    def test_complete_bipartite(self):
        # K_{3,4}
        a, b = 3, 4
        n = a + b
        edges = [(i, a + j) for i in range(a) for j in range(b)]
        self._check(from_edges(n, edges), n, 2)

    def test_petersen(self):
        # Outer 5-cycle, inner 5-cycle (spoke+2), spokes.
        edges = []
        for i in range(5):
            edges.append((i, (i + 1) % 5))
            edges.append((i, i + 5))
            edges.append((i + 5, ((i + 2) % 5) + 5))
        self._check(from_edges(10, edges), 10, 3)

    def test_grotzsch(self):
        # Mycielski of C5: 11 vertices, triangle-free, χ=4.
        # C5 on 0..4, copies 5..9, apex 10.
        edges = []
        for i in range(5):
            edges.append((i, (i + 1) % 5))
            edges.append((i, ((i + 1) % 5) + 5))
            edges.append((i, ((i - 1) % 5) + 5))
            edges.append((i + 5, 10))
        self._check(from_edges(11, edges), 11, 4)

    def test_wheel_odd(self):
        # W_6 = C_5 + hub → χ=4
        n = 6
        edges = [(i, (i + 1) % 5) for i in range(5)] + [(i, 5) for i in range(5)]
        self._check(from_edges(n, edges), n, 4)

    def test_wheel_even(self):
        # W_7 = C_6 + hub: even rim is 2-colourable, hub takes a third colour.
        n = 7
        edges = [(i, (i + 1) % 6) for i in range(6)] + [(i, 6) for i in range(6)]
        self._check(from_edges(n, edges), n, 3)

    def test_circulant_c12_1_4(self):
        # Circulant C_12(1,4): 4-regular, 3-colourable (not the Chvátal graph).
        n = 12
        edges = []
        for i in range(n):
            for d in (1, 4):
                j = (i + d) % n
                if i < j:
                    edges.append((i, j))
        self._check(from_edges(n, edges), n, 3)


class TestCliqueAndBounds(unittest.TestCase):
    def test_clique_on_complete(self):
        n = 8
        full = (1 << n) - 1
        adj = [full ^ (1 << v) for v in range(n)]
        self.assertEqual(len(max_clique(adj, n)), 8)

    def test_clique_on_triangle_plus(self):
        adj = from_edges(5, [(0, 1), (1, 2), (2, 0), (0, 3), (3, 4)])
        self.assertEqual(len(max_clique(adj, 5)), 3)

    def test_infeasible_below_omega(self):
        n = 6
        full = (1 << n) - 1
        adj = [full ^ (1 << v) for v in range(n)]
        clique = list(range(n))
        deg = [n - 1] * n
        self.assertIsNone(k_colorable(adj, n, n - 1, clique, deg, SearchStats()))


class TestRandomGnp(unittest.TestCase):
    def test_small_random_exact_vs_bounds(self):
        for n in (8, 12, 16):
            for seed in range(15):
                adj = generate_gnp(n, 0.35, seed)
                info = solve(adj, n)
                validate(adj, n, info.chi, info.coloring)
                self.assertGreaterEqual(info.chi, info.omega)
                self.assertLessEqual(info.chi, info.ub)

    def test_gnp30_first_seeds(self):
        for seed in range(8):
            adj = generate_gnp(30, 0.35, seed)
            info = solve(adj, 30)
            validate(adj, 30, info.chi, info.coloring)
            self.assertGreaterEqual(info.chi, info.omega)
            self.assertGreaterEqual(n_edges(adj, 30), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
