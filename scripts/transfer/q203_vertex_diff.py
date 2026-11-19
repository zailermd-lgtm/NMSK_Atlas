#!/usr/bin/env python3
"""Q203: vertex-level proof that measured data stayed untouched: every entry of the Q193 bundle and of the Q200 bundle vs the Q203 bundle (same position, id, subject).
Writes data/derived/Q203_vertex_diff.json."""
import json
import sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle


def diff(A, B):
    ident, changed = 0, []
    for ia, it in enumerate(A.items):
        n = B.items[ia]
        assert n["e"]["id"] == it["e"]["id"] and n["e"]["subject"] == it["e"]["subject"], (ia, it["e"]["id"], n["e"]["id"])
        if it["raw"] == n["raw"]:
            ident += 1
        else:
            va, fa = A.mesh(it); vb, fb = B.mesh(n)
            d = float(np.abs(va - vb).max()) if va.shape == vb.shape else None
            changed.append(dict(id=it["e"]["id"], subject=it["e"]["subject"], max_vertex_shift_mm=None if d is None else round(d, 2)))
    return ident, changed


out = {}
for body, a, a2, b in (("vhm", "build/viewer_m_hr_q193", "build/viewer_m_hr_q200", "build/viewer_m_hr_q203"),
                       ("vhf", "build/viewer_f_hr_q193", "build/viewer_f_hr_q200", "build/viewer_f_hr_q203")):
    A, A2, B = Bundle(REPO / a), Bundle(REPO / a2), Bundle(REPO / b)
    i1, c1 = diff(A, B)
    i2, c2 = diff(A2, B)
    added = [dict(id=n["e"]["id"], subject=n["e"]["subject"], cat=n["e"]["cat"], nv=n["e"]["nv"], nf=n["e"]["nf"]) for n in B.items[len(A2.items):]]
    out[body] = dict(entries_q193=len(A.items), entries_q200=len(A2.items), entries_q203=len(B.items),
                     vs_q193=dict(identical=i1, changed=c1, changed_non_Z=len([c for c in c1 if not c["subject"].startswith("xfer_zan2")])),
                     vs_q200=dict(identical=i2, changed=c2, changed_non_Z=len([c for c in c2 if not c["subject"].startswith("xfer_zan2")])),
                     added_count=len(added), added=added)
    print(body, "vs Q193: identical", i1, "/", len(A.items), "changed", len(c1), "| vs Q200: identical", i2, "/", len(A2.items), "changed", len(c2),
          "(non-Z", out[body]["vs_q200"]["changed_non_Z"], ") | added", len(added))
(REPO / "data/derived/Q203_vertex_diff.json").write_text(json.dumps(out, indent=1))
