"""Vascular tree graph construction and connectivity validation.

Same pattern as nerve_tree.py, with one addition: real vascular trees are
not strictly trees -- they anastomose (e.g. the palmar arches, the genicular
network around the knee). `anastomoses_with` edges are validated separately
as extra connectivity (both endpoints must exist) rather than forced into
the strict parent/child tree.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class VesselNode:
    id: str
    name: str
    system: str
    level: str
    parent_id: Optional[str]
    supplies_or_drains: List[str] = field(default_factory=list)
    anastomoses_with: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)


class VascularTree:
    def __init__(self, records: List[dict]):
        self.nodes: Dict[str, VesselNode] = {}
        for r in records:
            self.nodes[r["id"]] = VesselNode(
                id=r["id"], name=r["name"], system=r["system"], level=r["level"],
                parent_id=r.get("parent_id"),
                supplies_or_drains=r.get("supplies_or_drains", []),
                anastomoses_with=r.get("anastomoses_with", []),
            )
        for node in self.nodes.values():
            if node.parent_id is not None and node.parent_id in self.nodes:
                self.nodes[node.parent_id].children.append(node.id)

    def roots(self) -> List[VesselNode]:
        return [n for n in self.nodes.values() if n.parent_id is None]

    def validate_connectivity(self) -> List[str]:
        problems = []
        for node in self.nodes.values():
            if node.parent_id is not None and node.parent_id not in self.nodes:
                problems.append(f"{node.id}: parent '{node.parent_id}' does not exist")
            for target in node.anastomoses_with:
                if target not in self.nodes:
                    problems.append(f"{node.id}: anastomosis target '{target}' does not exist")
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
                problems.append(f"{node.id}: unreachable from tree root (orphan branch)")
        for node in self.nodes.values():
            is_leaf = len(node.children) == 0
            if is_leaf and not node.supplies_or_drains and not node.anastomoses_with:
                problems.append(f"{node.id}: terminal vessel has no documented supply/drain territory")
        return problems
