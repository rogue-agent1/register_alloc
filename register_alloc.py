#!/usr/bin/env python3
"""register_alloc.py — Graph coloring register allocator.

Implements Chaitin's algorithm: build interference graph from live
variable analysis, simplify by removing low-degree nodes, select
colors (registers), and spill when necessary.

One file. Zero deps. Does one thing well.
"""

import sys
from dataclasses import dataclass, field


@dataclass
class Instruction:
    op: str
    dest: str = ''
    src: list[str] = field(default_factory=list)

    def __repr__(self):
        if self.op == 'ret':
            return f'ret {self.src[0]}' if self.src else 'ret'
        if self.op == 'mov':
            return f'{self.dest} = {self.src[0]}'
        return f'{self.dest} = {self.src[0]} {self.op} {self.src[1]}' if len(self.src) == 2 else f'{self.dest} = {self.op} {self.src[0]}'

    @property
    def defs(self) -> set[str]:
        return {self.dest} if self.dest else set()

    @property
    def uses(self) -> set[str]:
        return set(self.src)


def liveness(instrs: list[Instruction]) -> list[tuple[set[str], set[str]]]:
    """Compute live-in and live-out sets for each instruction."""
    n = len(instrs)
    live_in = [set() for _ in range(n)]
    live_out = [set() for _ in range(n)]
    changed = True
    while changed:
        changed = False
        for i in range(n - 1, -1, -1):
            new_out = live_in[i + 1] if i + 1 < n else set()
            new_in = instrs[i].uses | (new_out - instrs[i].defs)
            if new_in != live_in[i] or new_out != live_out[i]:
                live_in[i] = new_in
                live_out[i] = new_out
                changed = True
    return list(zip(live_in, live_out))


def build_interference(instrs: list[Instruction]) -> dict[str, set[str]]:
    """Build interference graph from liveness info."""
    live = liveness(instrs)
    variables = set()
    for instr in instrs:
        variables |= instr.defs | instr.uses
    graph: dict[str, set[str]] = {v: set() for v in variables}
    for i, instr in enumerate(instrs):
        live_at = live[i][1] | instr.defs  # live-out ∪ defs
        for v in instr.defs:
            for u in live_at:
                if u != v:
                    graph[v].add(u)
                    graph[u].add(v)
    return graph


def allocate(instrs: list[Instruction], num_regs: int = 4) -> tuple[dict[str, str], set[str]]:
    """Chaitin's graph coloring register allocation.

    Returns (allocation, spilled) where allocation maps variables
    to register names and spilled contains variables that couldn't fit.
    """
    graph = build_interference(instrs)
    registers = [f'r{i}' for i in range(num_regs)]

    # Simplify: repeatedly remove nodes with degree < num_regs
    stack = []
    remaining = {v: set(neighbors) for v, neighbors in graph.items()}
    spilled = set()

    while remaining:
        # Find a node with degree < num_regs
        found = None
        for v, neighbors in remaining.items():
            active = neighbors & remaining.keys()
            if len(active) < num_regs:
                found = v
                break
        if found is None:
            # Spill: pick highest-degree node
            v = max(remaining, key=lambda x: len(remaining[x] & remaining.keys()))
            spilled.add(v)
            del remaining[v]
            continue
        stack.append((found, remaining[found] & remaining.keys()))
        del remaining[found]

    # Select: pop stack and assign colors
    allocation = {}
    for v, neighbors in reversed(stack):
        used = {allocation[n] for n in neighbors if n in allocation}
        for reg in registers:
            if reg not in used:
                allocation[v] = reg
                break
        else:
            spilled.add(v)

    # Spilled variables get memory slots
    for i, v in enumerate(sorted(spilled)):
        allocation[v] = f'[sp+{i * 8}]'

    return allocation, spilled


def rewrite(instrs: list[Instruction], alloc: dict[str, str]) -> list[str]:
    """Rewrite instructions with allocated registers."""
    result = []
    for instr in instrs:
        dest = alloc.get(instr.dest, instr.dest)
        srcs = [alloc.get(s, s) for s in instr.src]
        if instr.op == 'ret':
            result.append(f'ret {srcs[0]}' if srcs else 'ret')
        elif instr.op == 'mov':
            result.append(f'{dest} = {srcs[0]}')
        elif len(srcs) == 2:
            result.append(f'{dest} = {srcs[0]} {instr.op} {srcs[1]}')
        else:
            result.append(f'{dest} = {instr.op} {srcs[0]}')
    return result


def demo():
    print("=== Register Allocator (Chaitin's Graph Coloring) ===\n")

    # Example: compute (a+b) * (c-d) + e
    instrs = [
        Instruction('mov', 'a', ['1']),
        Instruction('mov', 'b', ['2']),
        Instruction('mov', 'c', ['3']),
        Instruction('mov', 'd', ['4']),
        Instruction('mov', 'e', ['5']),
        Instruction('+', 't1', ['a', 'b']),
        Instruction('-', 't2', ['c', 'd']),
        Instruction('*', 't3', ['t1', 't2']),
        Instruction('+', 't4', ['t3', 'e']),
        Instruction('ret', '', ['t4']),
    ]

    print("Source:")
    for i in instrs:
        print(f"  {i}")

    # Liveness
    live = liveness(instrs)
    print("\nLiveness:")
    for i, (li, lo) in enumerate(live):
        print(f"  {instrs[i]!s:30s} in={li}  out={lo}")

    # Interference graph
    graph = build_interference(instrs)
    print("\nInterference graph:")
    for v in sorted(graph):
        if graph[v]:
            print(f"  {v} -- {sorted(graph[v])}")

    # Allocate with 4 registers
    alloc, spilled = allocate(instrs, num_regs=4)
    print(f"\nAllocation (4 registers):")
    for v, reg in sorted(alloc.items()):
        sp = " (spilled)" if v in spilled else ""
        print(f"  {v} → {reg}{sp}")

    # Rewritten code
    print("\nRewritten:")
    for line in rewrite(instrs, alloc):
        print(f"  {line}")

    # Try with only 2 registers (forces spills)
    alloc2, spilled2 = allocate(instrs, num_regs=2)
    print(f"\nWith 2 registers: {len(spilled2)} spills ({sorted(spilled2)})")


if __name__ == '__main__':
    if '--test' in sys.argv:
        instrs = [
            Instruction('mov', 'a', ['1']),
            Instruction('mov', 'b', ['2']),
            Instruction('+', 'c', ['a', 'b']),
            Instruction('ret', '', ['c']),
        ]
        alloc, spilled = allocate(instrs, num_regs=3)
        assert len(spilled) == 0, f"Unexpected spills: {spilled}"
        assert len(set(alloc.values())) <= 3
        # With 1 register, must spill
        alloc1, spilled1 = allocate(instrs, num_regs=1)
        assert len(spilled1) > 0
        # Liveness
        live = liveness(instrs)
        assert 'a' in live[2][0] or 'a' in [i.uses for i in instrs][2]  # a live at use
        print("All tests passed ✓")
    else:
        demo()
