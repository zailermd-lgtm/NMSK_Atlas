#!/usr/bin/env python3
"""Q215: honest side effect of re-bounding the thigh muscles in the registered frame while her photo-traced nerves / vessels (Q53 sciatic, Q55 femoral, Q56 popliteal / tibial; placed in the lost frame,
Q179) stay where they are: share of their vertices that lie inside a TARGET muscle mesh before (Q214 bundle) and after (Q215 bundle).  Writes data/derived/Q215_traced_overlap.json (no geometry changed)."""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q215_refit as RF  # noqa: E402

TRACED = ("sciatic_n", "femoral_a_r", "femoral_v_r", "femoral_n", "popliteal_a_r", "popliteal_v_r", "tibial_n")


def share(B, ids):
    out = {}
    tm = {}
    for it in B.items:
        if it["e"]["id"] in ids:
            v, f = B.mesh(it)
            tm[it["e"]["id"]] = trimesh.Trimesh(v, f, process=False)
    for tid in TRACED:
        v = B.get(tid)["v"]
        inm = np.zeros(len(v), bool)
        for sid, m in tm.items():
            lo, hi = m.bounds[0] - 1, m.bounds[1] + 1
            sel = np.flatnonzero(np.all((v >= lo) & (v <= hi), axis=1) & ~inm)
            if len(sel):
                inm[sel] = m.contains(v[sel])
        out[tid] = dict(vertices=int(len(v)), inside_target_muscle=int(inm.sum()), pct=round(100.0 * float(inm.mean()), 1))
    return out


def main():
    ids = set(RF.target_ids())
    A, N = Bundle(REPO / "build/viewer_f_hr_q214"), Bundle(REPO / "build/viewer_f_hr_q215")
    d = dict(before=share(A, ids), after=share(N, ids), note="traced structures keep their (lost-frame) positions; the re-bounded muscles lie in the registered frame (Q179: the traced outlines sit 4-14 mm off her femur-registered photographs)")
    (REPO / "data/derived/Q215_traced_overlap.json").write_text(json.dumps(d, indent=1) + "\n")
    for k in TRACED:
        print(f"{k:16s} {d['before'][k]['pct']:5.1f} % -> {d['after'][k]['pct']:5.1f} %")


if __name__ == "__main__":
    main()
