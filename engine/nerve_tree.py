"""Nerve tree graph construction and connectivity validation.

Builds a directed tree from a flat list of schema/nerve_branch.schema.json
records (root -> trunk -> division -> cord -> terminal/muscular/cutaneous
branch) and checks it is well-formed: every non-root node has exactly one
parent that exists, every leaf resolves to a documented target, and the
whole graph is reachable from the plexus roots (no orphans).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class NerveNode:
    id: str
    name: str
    level: str
    parent_id: Optional[str]
    targets: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)


class NerveTree:
    def __init__(self, records: List[dict]):
        self.nodes: Dict[str, NerveNode] = {}
        for r in records:
            self.nodes[r["id"]] = NerveNode(
                id=r["id"], name=r["name"], level=r["level"],
                parent_id=r.get("parent_id"), targets=r.get("targets", []),
            )
        for node in self.nodes.values():
            if node.parent_id is not None and node.parent_id in self.nodes:
                self.nodes[node.parent_id].children.append(node.id)

    def roots(self) -> List[NerveNode]:
        return [n for n in self.nodes.values() if n.parent_id is None]

    def validate_connectivity(self) -> List[str]:
        """Returns a list of problem descriptions; empty list = fully valid."""
        problems = []
        for node in self.nodes.values():
            if node.parent_id is not None and node.parent_id not in self.nodes:
                problems.append(f"{node.id}: parent '{node.parent_id}' does not exist")
        # reachability from roots
        reachable = set()
        stack = [n.id for n in self.roots()]
        while stack:
            nid = stack.pop()
            if nid in reachable:
                continue
            reachable.add(nid)
            stack.extend(self.nodes[nid].children)
        for node in self.nodes.values():
            if node.id not in reachable:
                problems.append(f"{node.id}: unreachable from any plexus root (orphan branch)")
        # leaves must have documented targets
        for node in self.nodes.values():
            is_leaf = len(node.children) == 0
            if is_leaf and node.level in ("terminal_branch", "muscular_branch", "cutaneous_branch") and not node.targets:
                problems.append(f"{node.id}: terminal/leaf branch has no documented target")
        return problems

    def path_to_root(self, node_id: str) -> List[str]:
        path = [node_id]
        cur = self.nodes[node_id]
        while cur.parent_id is not None:
            path.append(cur.parent_id)
            cur = self.nodes[cur.parent_id]
        return path
