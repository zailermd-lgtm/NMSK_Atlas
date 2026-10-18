#!/usr/bin/env python3
"""Q256: nerve GROUPS (root / trunk / division / cord / branch) for the brachial and lumbosacral plexuses.

Owner's request: "Add an option to mark/select nerves by group, such as a common root, or a common cord in a plexus, etc."
This does NOT invent a lineage: `data/nerves/brachial_plexus.json` and `data/nerves/lumbosacral_plexus.json` already encode a real,
cited parent_id tree (checked here, not assumed) -- this script only walks that tree and writes, for every node, the full set of
node ids downstream of it (the node itself plus every descendant at every level), so the viewer can select "everything downstream of
the posterior cord" etc. with the project's EXISTING Q232 selection-sets controller, not a parallel system.

Known, inherited limitation of the SOURCE data (not introduced here): the tree is single-parent, so a nerve that genuinely receives
fibres from two plexus components in real anatomy (e.g. the median nerve's lateral root from the lateral cord AND medial root from
the medial cord) is only a child of ONE of them in this data (median_n's parent is "median_n_lateral_root", under the lateral cord).
"Downstream of the medial cord" therefore will NOT include the median nerve or its sub-branches here, even though the medial cord
does anatomically contribute to the median nerve via its medial root -- flagged in docs/OPEN_ITEMS_FOR_OWNER.md, not silently fixed by
adding an un-cited second parent.

    python3 scripts/anatomy/q256/plexus_groups.py
writes data/derived/Q256_plexus_groups.json (schema nmsk.plexus_groups.v1)."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = REPO / "data/derived/Q256_plexus_groups.json"
SOURCES = [REPO / "data/nerves/brachial_plexus.json", REPO / "data/nerves/lumbosacral_plexus.json"]
LEVEL_LABEL = {"root": "Root", "trunk": "Trunk", "division": "Division", "cord": "Cord",
               "terminal_branch": "Terminal branch", "muscular_branch": "Muscular branch", "cutaneous_branch": "Cutaneous branch"}
LEVEL_ORDER = ["root", "trunk", "division", "cord", "terminal_branch", "muscular_branch", "cutaneous_branch"]


def disp_name(rec: dict) -> str:
    n = rec.get("name") or rec["id"]
    rc = rec.get("root_contributions")
    return f"{n} ({rc})" if rc else n


def main() -> int:
    recs = {}
    for f in SOURCES:
        for r in json.loads(f.read_text()):
            assert r["id"] not in recs, f"duplicate node id {r['id']} ({f})"
            recs[r["id"]] = r
    children = defaultdict(list)
    for r in recs.values():
        if r.get("parent_id"):
            assert r["parent_id"] in recs, f"{r['id']}: parent {r['parent_id']} not found"
            children[r["parent_id"]].append(r["id"])

    def subtree(node_id: str) -> list[str]:
        out = [node_id]
        for c in children.get(node_id, []):
            out += subtree(c)
        return out

    nodes = {}
    for nid, r in recs.items():
        down = subtree(nid)
        nodes[nid] = dict(id=nid, name=r.get("name", nid), plexus=r["plexus"], level=r["level"], level_label=LEVEL_LABEL.get(r["level"], r["level"]),
                           parent_id=r.get("parent_id"), root_contributions=r.get("root_contributions"), display_name=disp_name(r),
                           children=sorted(children.get(nid, [])), downstream=sorted(down), downstream_count=len(down),
                           is_leaf=nid not in children, source=r.get("source", ""))
    plexuses = sorted({r["plexus"] for r in recs.values()})
    by_plexus = {p: sorted([nid for nid, r in recs.items() if r["plexus"] == p],
                            key=lambda i: (LEVEL_ORDER.index(recs[i]["level"]), i)) for p in plexuses}
    out = dict(schema="nmsk.plexus_groups.v1", generated_by="scripts/anatomy/q256/plexus_groups.py",
               note=("Node ids are the SAME base ids used elsewhere in this project for these nerve meshes (side suffix _r/_l, or none for "
                     "a midline root, added per page at sidecar-build time: scripts/anatomy/q256/build_plexus_sidecar.py). 'downstream' is "
                     "every node at or below this one in the real, cited parent_id tree of data/nerves/{brachial,lumbosacral}_plexus.json "
                     "(single-parent: see this script's own docstring for the one known gap, the median nerve's dual cord origin)."),
               plexuses=plexuses, by_plexus=by_plexus, nodes=nodes)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=False) + "\n")
    print("nodes:", len(nodes), "plexuses:", plexuses)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
