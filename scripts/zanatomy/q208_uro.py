"""Q208 male urogenital rims: weld the two urogenital patches to the anal and thigh patches (Q207 left 4-5 mm vertex steps and a 7.4 mm slit of the l | r seam at the anal end).
One sparse least-squares solve (q207_weld.solve: shared-border constraints, smoothness over the slab, minimal movement) over the urogenital patches and their direct neighbours (anal, anterior thigh,
hypogastric, inguinal, both sides); every other patch that shares a border with them is a fixed constraint.  The neighbours move only as far as the solve needs (reported per patch)."""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from scripts.zanatomy import q207_weld as WD

UROS = ("zan_skin_urogenital_region_l", "zan_skin_urogenital_region_r")
NEIGH = tuple(f"zan_skin_{n}_{s}" for n in ("anal_region", "anterior_region_of_thigh", "hypogastric_region", "inguinal_region") for s in "lr")


def group(raw_v, skin_ids, tol=1.5):
    free = list(UROS) + list(NEIGH)
    trees = {i: cKDTree(raw_v[i]) for i in skin_ids if i in raw_v}
    fixed = set()
    for f in free:
        for j, t in trees.items():
            if j in free:
                continue
            if (t.query(raw_v[f])[0] < tol).sum() >= 3:
                fixed.add(j)
    return free, sorted(fixed)


def weld(pg_faces, raw_v, V, skin_ids, w_pull=8.0, w_hold=1.0, lam_s=1.0, lam_0=0.01, gate=0.8, log=print):
    free, fixed = group(raw_v, skin_ids)
    ids = free + fixed
    cons = WD.border_pairs({i: raw_v[i] for i in ids}, ids)
    new = WD.solve({i: V[i] for i in ids}, {i: pg_faces[i] for i in ids}, ids, cons, set(free), gate_gap=gate, w_pull=w_pull, w_hold=w_hold, lam_s=lam_s, lam_0=lam_0, log=log)
    out = dict(V)
    out.update(new)
    return out, dict(free=free, fixed=fixed, constraints=len(cons))
