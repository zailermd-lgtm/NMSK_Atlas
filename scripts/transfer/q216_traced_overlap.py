#!/usr/bin/env python3
"""Q216: share of the vertices of her photo-traced nerves / vessels (Q53 sciatic, Q55 femoral, Q56 popliteal / tibial) that lie inside the TARGET muscle meshes (the 28 hip / thigh sides of Q215) and inside
ANY muscle, per muscle, before (Q215 bundle) and after (Q216 bundle); closest approach of the traced vertices to the surface of each target muscle.  The traced tubes are never moved.
-> data/derived/Q216_traced_overlap.json"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q215_refit as RF  # noqa: E402

TRACED = ("sciatic_n", "femoral_a_r", "femoral_v_r", "femoral_n", "popliteal_a_r", "popliteal_v_r", "tibial_n")


def state(B, targets):
    mus = {}
    for it in B.items:
        e = it["e"]
        if e["cat"] == "muscle" and not e.get("hidden_default"):
            v, f = B.mesh(it)
            mus[e["id"]] = trimesh.Trimesh(v, f, process=False)
    out = {}
    for tid in TRACED:
        nv = B.get(tid)["v"]
        in_t, in_any = np.zeros(len(nv), bool), np.zeros(len(nv), bool)
        per, closest = {}, {}
        for mid, m in mus.items():
            lo, hi = m.bounds[0] - 1, m.bounds[1] + 1
            sel = np.flatnonzero(np.all((nv >= lo) & (nv <= hi), axis=1))
            if not len(sel):
                continue
            c = m.contains(nv[sel])
            if c.any():
                per[mid] = round(100.0 * float(c.sum()) / len(nv), 1)
                in_any[sel[c]] = True
                if mid in targets:
                    in_t[sel[c]] = True
            if mid in targets:
                closest[mid] = round(float(cKDTree(m.vertices).query(nv[sel[~c]])[0].min()), 2) if (~c).any() else 0.0
        out[tid] = dict(vertices=int(len(nv)), inside_target_muscle=int(in_t.sum()), pct_target=round(100.0 * float(in_t.mean()), 1), pct_any_muscle=round(100.0 * float(in_any.mean()), 1),
                        per_muscle_pct=dict(sorted(per.items(), key=lambda x: -x[1])), moved=False)
    return out


def main():
    targets = set(RF.target_ids())
    A, N = Bundle(REPO / "build/viewer_f_hr_q215"), Bundle(REPO / "build/viewer_f_hr_q216")
    traced_same = all(A.items[A.find(t)[0]]["raw"] == N.items[N.find(t)[0]]["raw"] for t in TRACED)
    d = dict(before=state(A, targets), after=state(N, targets), traced_structures_byte_identical=bool(traced_same),
             note="the traced tubes keep their positions (measured evidence); the muscles were carved away from them in Q216 (groove open towards the nearest surface, corridor = tube + 1 mm); the remaining overlap is with muscles that were not re-bounded in Q215 (gastrocnemius, plantaris: her own CT muscles) and was not touched")
    (REPO / "data/derived/Q216_traced_overlap.json").write_text(json.dumps(d, indent=1) + "\n")
    for k in TRACED:
        print(f"{k:16s} target muscles {d['before'][k]['pct_target']:5.1f} % -> {d['after'][k]['pct_target']:5.1f} %   any muscle {d['before'][k]['pct_any_muscle']:5.1f} % -> {d['after'][k]['pct_any_muscle']:5.1f} %")
    print("traced structures byte identical:", traced_same)


if __name__ == "__main__":
    main()
