#!/usr/bin/env python3
"""Register Allocator — graph coloring with simplify/spill (Chaitin-Briggs)."""
import sys
from collections import defaultdict

class InterferenceGraph:
    def __init__(self):
        self.adj = defaultdict(set); self.nodes = set()
    def add_node(self, n): self.nodes.add(n)
    def add_edge(self, u, v):
        if u != v: self.adj[u].add(v); self.adj[v].add(u); self.nodes.update([u,v])
    def degree(self, n): return len(self.adj[n])
    def remove(self, n):
        for nb in self.adj[n]: self.adj[nb].discard(n)
        del self.adj[n]; self.nodes.discard(n)

def allocate_registers(ig, k):
    adj_backup = {n: set(ig.adj[n]) for n in ig.nodes}
    nodes = set(ig.nodes); stack = []; spilled = set()
    # Simplify
    while nodes:
        found = None
        for n in nodes:
            if len(ig.adj[n] & nodes) < k: found = n; break
        if found is None:
            # Spill: pick highest degree
            found = max(nodes, key=lambda n: len(ig.adj[n] & nodes))
            spilled.add(found)
        stack.append(found); nodes.remove(found)
    # Color
    colors = {}
    for n in reversed(stack):
        used = {colors[nb] for nb in adj_backup[n] if nb in colors}
        for c in range(k):
            if c not in used: colors[n] = c; break
        else: colors[n] = 'SPILL'
    return colors

if __name__ == "__main__":
    ig = InterferenceGraph()
    for v in 'abcdef': ig.add_node(v)
    for u, v in [('a','b'),('a','c'),('b','c'),('b','d'),('c','d'),('d','e'),('e','f')]:
        ig.add_edge(u, v)
    colors = allocate_registers(ig, 3)
    print(f"3 registers: {colors}")
    colors4 = allocate_registers(InterferenceGraph(), 4)
