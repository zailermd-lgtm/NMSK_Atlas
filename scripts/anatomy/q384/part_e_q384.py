"""Q384 verifier, part E3: every muscle keeps its placed origin and insertion on its bone (see attach_q384.py).

Two checks. (1) All placed bony ends of this page, in the five test poses and the shoulder swept to 170 degrees of abduction
and of flexion on both sides, computed with the python mirror of the viewer from the rig THE PAGE carries: none more than
5 mm off its bone. (2) On the page itself, for the muscles named by the owner's report and its neighbours: the footprint
read back from the live vertices and the bone's own segment matrix -- so (1) is not a statement about the mirror only."""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "q241")); sys.path.insert(0, str(HERE.parent / "q338"))
import attach_q384 as AT  # noqa: E402

SPOT = [("latissimus_dorsi_%s", {"shoulder_%s": {"abd": 170}}), ("latissimus_dorsi_%s", {"shoulder_%s": {"flex": 170}}), ("teres_major_%s", {"shoulder_%s": {"abd": 170}}),
        ("biceps_brachii_%s", {"shoulder_%s": {"abd": 170}}), ("semimembranosus_%s", {"hip_%s": {"flex": 90}, "knee_%s": {"flex": 90}}),
        ("rectus_femoris_%s", {"hip_%s": {"flex": 90}, "knee_%s": {"flex": 90}})]


def run(pg, d, check):
    import make_pose_rig as MK
    import model as MD
    import rig_io_q338 as RIO
    key = MK.DIRKEY[d.name]
    os.environ["Q241_SRC_" + key] = str(d.resolve())
    S = MD.Model(key).S
    rig, blob = RIO.page_rig(d), RIO.page_weights(d)
    print("E3. origins and insertions stay on their bones (%s)" % key, flush=True)
    o = AT.table(key, S=S, verbose=False, rig_blob=(rig, blob))
    check("the page's rig, %d placed bony ends of %d muscles, %d poses (five test poses + shoulder to 170 abduction / flexion, both sides): "
          "none more than %.0f mm off its bone (worst %.2f mm; lost: %s)" % (o["n_sites"], o["n_muscles"], len(AT.SWEEP), AT.LIMIT, o["worst"], sorted(o["lost"])[:4]),
          o["n_sites"] > 300 and not o["lost"])
    st = AT.sites(key, S, rig)
    idx = pg.evaluate("() => { const o = window.__poseIndex(), r = {}; for (const k in o) r[k] = o[k].index; return r; }")
    worst = {}
    for side in ("l", "r"):
        for mid, pose in SPOT:
            mid = mid % side
            mine = [s for s in st if s["mid"] == mid]
            if not mine or mid not in idx:
                continue
            pg.evaluate("() => window.__poseApi.reset()")
            for j, dofs in pose.items():
                for k, v in dofs.items():
                    pg.evaluate("(a) => window.__poseApi.set(a[0], a[1], a[2])", [j % side, k, v])
            b = pg.evaluate("(i) => window.__q384.b64(i)", idx[mid])
            if b is None:
                check("page: %s was moved by the pose" % mid, False); continue
            p = np.frombuffer(base64.b64decode(b), np.float32).reshape(-1, 3).astype(np.float64)
            M = [np.vstack([np.array(m).reshape(3, 4), [0, 0, 0, 1]]) for m in pg.evaluate("() => window.__poseApi.matrices()")]
            for s in mine:
                r = AT.measure(s, np.asarray(S[s["muscle"]]["v"], float), p, M)
                k = (mid, s["type"], s["bid"])
                worst[k] = max(worst.get(k, 0.0), r["drift"])
    pg.evaluate("() => window.__poseApi.reset()")
    for k, v in sorted(worst.items()):
        check("page: %s %s on %s stays on its bone (%.2f mm off, limit %.0f)" % (k[0], k[1].replace("_part", "").replace("_point", ""), k[2], v, AT.LIMIT), v <= AT.LIMIT)
    check("page: the latissimus dorsi's humeral insertion was read on both sides", sum(1 for k in worst if k[0].startswith("latissimus_dorsi") and k[1] == "insertion_point") == 2)
    return dict(replica=o, page={"%s|%s|%s" % k: v for k, v in worst.items()})
