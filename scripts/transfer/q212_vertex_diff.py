#!/usr/bin/env python3
"""Q212: vertex-level proof that nothing already in the Q203 bundle moved: every Q203 entry vs the Q212 bundle (same position, id, subject, mesh bytes). Q212 only ADDS entries; the
only change to an existing entry is the `hidden_default` flag + a badge sentence on the three entries the CT re-segmentation of his wrist supersedes (mesh bytes identical).
Writes data/derived/Q212_vertex_diff.json."""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle
out = {}
for body, a, b in (("vhm", "build/viewer_m_hr_q203", "build/viewer_m_hr_q212"), ("vhf", "build/viewer_f_hr_q203", "build/viewer_f_hr_q212")):
    A, Bn = Bundle(REPO / a), Bundle(REPO / b)
    ident, flagged, bad = 0, [], []
    for ia, it in enumerate(A.items):
        n = Bn.items[ia]
        assert n["e"]["id"] == it["e"]["id"] and n["e"]["subject"] == it["e"]["subject"], (ia, it["e"]["id"])
        if it["raw"] == n["raw"]:
            ident += 1
        else:
            bad.append(it["e"]["id"])
        if n["e"].get("hidden_default") and not it["e"].get("hidden_default"):
            flagged.append(it["e"]["id"])
    added = [dict(id=n["e"]["id"], subject=n["e"]["subject"], cat=n["e"]["cat"], nv=n["e"]["nv"], nf=n["e"]["nf"]) for n in Bn.items[len(A.items):]]
    out[body] = dict(entries_q203=len(A.items), entries_q212=len(Bn.items), mesh_bytes_identical=ident, mesh_bytes_changed=bad, hidden_by_default_added=flagged, added_count=len(added), added=added,
                     measured_added=[x["id"] for x in added if not x["subject"].startswith("xfer_zan2")], triangles_q203=A.j["triangles"], triangles_q212=Bn.items and int(sum(i["e"]["nf"] for i in Bn.items)))
    print(body, "identical", ident, "/", len(A.items), "changed", bad, "| hidden added", flagged, "| added", len(added), "| triangles", out[body]["triangles_q203"], "->", out[body]["triangles_q212"])
(REPO / "data/derived/Q212_vertex_diff.json").write_text(json.dumps(out, indent=1))
