#!/usr/bin/env python3
"""Q200: vertex-level proof that measured data stayed untouched: every entry of the Q193 bundle vs the Q200 bundle (same id + subject).
Writes data/derived/Q200_vertex_diff.json."""
import json
import sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle

out = {}
for body, a, b in (("vhm", "build/viewer_m_hr_q193", "build/viewer_m_hr_q200"), ("vhf", "build/viewer_f_hr_q193", "build/viewer_f_hr_q200")):
    A, B = Bundle(REPO / a), Bundle(REPO / b)
    ident, changed, removed = 0, [], []
    n0 = len(A.items)
    for ia, it in enumerate(A.items):                      # the Q200 bundle keeps every Q193 entry in place (position ia); additions are appended
        n = B.items[ia]
        assert n["e"]["id"] == it["e"]["id"] and n["e"]["subject"] == it["e"]["subject"], (ia, it["e"]["id"], n["e"]["id"])
        va, fa = A.mesh(it); vb, fb = B.mesh(n)
        if it["raw"] == n["raw"]:
            ident += 1
        else:
            d = float(np.abs(va - vb).max()) if va.shape == vb.shape else None
            changed.append(dict(id=it["e"]["id"], subject=it["e"]["subject"], max_vertex_shift_mm=None if d is None else round(d, 2), same_topology=bool(va.shape == vb.shape and (fa == fb).all())))
    added = [dict(id=n["e"]["id"], subject=n["e"]["subject"], cat=n["e"]["cat"], nv=n["e"]["nv"]) for n in B.items[n0:]]
    meas = [c for c in changed if not c["subject"].startswith("xfer_zan2")]
    out[body] = dict(entries_before=len(A.items), entries_after=len(B.items), identical_entries=ident, changed=changed, changed_non_Z_entries=len(meas), removed=removed, added_count=len(added),
                     added=added)
    print(body, "identical", ident, "of", len(A.items), "| changed", len(changed), "(non-Z:", len(meas), ") | removed", len(removed), "| added", len(added))
(REPO / "data/derived/Q200_vertex_diff.json").write_text(json.dumps(out, indent=1))
