#!/usr/bin/env python3
"""Q256: per-page `plexus_groups.json` sidecar -- which of the brachial / lumbar / sacral plexus's nodes (root, trunk, division,
cord, branch) this ONE page actually has meshes for, per side, so the viewer's "Nerve groups" picker can honestly show "12 of 14
downstream nerves present" rather than assume every page has every level (own pages: branches only; Z pages: often the full tree --
checked per page, not assumed, exactly as the brief asks).

    python3 scripts/anatomy/q256/build_plexus_sidecar.py --html PAGE.html -o plexus_groups.json

Resolution of one node id on one side mirrors scripts/anatomy/q219/build_geometry.py's Body.ids_for: try "<id>_<side>",
"zan_<id>_<side>", then (rare: a genuinely midline mesh) the bare id, else absent -- never fabricated."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(HERE.parent / "q220"))
from build_parts_sidecar import load_page  # noqa: E402  (Q220's own page-mesh reader; reused, not reimplemented)

GROUPS = REPO / "data/derived/Q256_plexus_groups.json"


def resolve(nid: str, side: str, idset: set[str]) -> str | None:
    for c in (f"{nid}_{side}", f"zan_{nid}_{side}", nid, f"zan_{nid}"):
        if c in idset:
            return c
    # Q258: the registry's brachial root ids are mixed-case (brachial_root_C5 ...) while every mesh id on every page
    # is lowercase-only (checked: no page carries a single uppercase-letter id otherwise) -- a case-insensitive
    # fallback lets the new C5-T1 root meshes resolve without renaming the registry or introducing the one
    # mixed-case id this codebase would otherwise have.
    low = nid.lower()
    if low != nid:
        for c in (f"{low}_{side}", f"zan_{low}_{side}", low, f"zan_{low}"):
            if c in idset:
                return c
    return None


def build(html: Path) -> dict:
    g = json.loads(GROUPS.read_text(encoding="utf-8"))
    _, meshes = load_page(html)
    idset = {m[0] for m in meshes}
    nodes_out = {}
    by_plexus = {p: [] for p in g["plexuses"]}
    for nid, node in g["nodes"].items():
        sides = {}
        for s in ("r", "l"):
            resolved = []
            for d in node["downstream"]:
                m = resolve(d, s, idset)
                if m:
                    resolved.append(m)
            if resolved:
                missing = [d for d in node["downstream"] if not resolve(d, s, idset)]
                sides[s] = dict(resolved_ids=sorted(resolved), resolved_count=len(resolved), total=node["downstream_count"],
                                 missing_sample=missing[:12], missing_count=len(missing))
        if sides:
            # Q267 (8): parent_name (what it's a branch of) + targets (what it innervates, muscle ids -- resolved to
            # real names client-side against this page's own geo.names) + source citation, so the injury-annotation
            # reference card can show real, cited data instead of just a name -- nothing invented here.
            nodes_out[nid] = dict(name=node["name"], display_name=node["display_name"], level=node["level"], level_label=node["level_label"],
                                   plexus=node["plexus"], parent_id=node["parent_id"], parent_name=(g["nodes"].get(node["parent_id"], {}) or {}).get("name"),
                                   is_leaf=node["is_leaf"], sides=sides, targets=node.get("targets", []), source=node.get("source", ""))
            by_plexus[node["plexus"]].append(nid)
    for p in by_plexus:
        by_plexus[p].sort()
    return dict(schema="nmsk.plexus_sidecar.v1", generated_by="scripts/anatomy/q256/build_plexus_sidecar.py",
                plexuses=[p for p in g["plexuses"] if by_plexus[p]], by_plexus={p: v for p, v in by_plexus.items() if v}, nodes=nodes_out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True, type=Path)
    ap.add_argument("-o", "--out", required=True, type=Path)
    a = ap.parse_args()
    out = build(a.html)
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(a.html, "nodes with >=1 side present:", len(out["nodes"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
