"""Q384 verifier, part B: the deformation, measured on the page itself (see verify_pose_q384.py).

The poses, the test structures and the limits are the round's acceptance list; the measures are those of
pose_metrics_q384.py. A "kink" is the INCREASE of the bend at one centreline node over the rest pose: the meshes are coarse
decimated tubes whose rest centreline already shows 14-99 degrees of sampling noise, so the absolute angle says nothing."""
from __future__ import annotations

import base64
import math
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "q241"))
import pose_metrics_q384 as PM  # noqa: E402

POSES = {
    "hipknee_l": {"hip_l": {"flex": 90}, "knee_l": {"flex": 90}},
    "hipknee_r": {"hip_r": {"flex": 90}, "knee_r": {"flex": 90}},
    "elbow_l": {"elbow_l": {"flex": 120}},
    "shoulder_l": {"shoulder_l": {"abd": 120}},
    "arm_r": {"shoulder_r": {"abd": 90, "flex": 30}, "elbow_r": {"flex": 120}},
}
LEG = ["zan_great_saphenous_vein_%s", "zan_femoral_artery_%s", "zan_femoral_vein_%s", "sciatic_n_%s", "rectus_femoris_%s", "gastrocnemius_%s"]
ARM = ["zan_cephalic_vein_%s", "zan_basilic_vein_%s", "zan_brachial_artery_%s", "ulnar_n_%s", "biceps_brachii_%s"]
TUBES = {"hipknee_l": [t % "l" for t in LEG], "hipknee_r": [t % "r" for t in LEG], "elbow_l": [t % "l" for t in ARM],
         "shoulder_l": [t % "l" for t in ARM if "basilic" not in t], "arm_r": [t % "r" for t in ARM]}
JOINTS = {"hipknee_l": ["hip_l", "knee_l"], "hipknee_r": ["hip_r", "knee_r"], "elbow_l": ["elbow_l"], "shoulder_l": ["shoulder_l"], "arm_r": ["shoulder_r", "elbow_r"]}
LIM = dict(gap=0.5, bend=35.0, xsec=0.6, dlen=12.0)
NEAR = 170.0
LK = ["bone", "cartilage", "joint", "insertion", "muscle", "fascia", "bursa", "nerve", "cns", "vessel", "lymph", "viscera", "fat", "skin"]
VIEWS = {"hipknee_l": ([-80.0, -150.0, 60.0], 1500.0), "hipknee_r": ([80.0, -150.0, 60.0], 1500.0), "elbow_l": ([-220.0, 300.0, 0.0], 1100.0),
         "shoulder_l": ([-230.0, 520.0, 0.0], 1300.0), "arm_r": ([230.0, 520.0, 40.0], 1300.0)}


def live(pg, i):
    s = pg.evaluate("(i) => window.__q384.b64(i)", i)
    return None if s is None else np.frombuffer(base64.b64decode(s), np.float32).reshape(-1, 3).astype(np.float64)


def run(pg, d, check, shots=None, tag=""):
    import make_pose_rig as MK
    import model as MD
    key = MK.DIRKEY[d.name]
    os.environ["Q241_SRC_" + key] = str(d.resolve())
    S = MD.Model(key).S
    by = {x["id"]: x for x in S}
    print("B. deformation (%s, %d structures)" % (key, len(S)), flush=True)
    pg.wait_for_function("window.__poseApi && __poseApi.ready()", timeout=180000)
    import verify_pose_q384 as VP
    pg.evaluate(VP.JS_LIB)
    idx = pg.evaluate("() => { const o = window.__poseIndex(), r = {}; for (const k in o) r[k] = o[k].index; return r; }")
    rig = pg.evaluate("() => { const r = window.__poseApi.rig(); return {blend: r.blend || 'linear', joints: r.joints.map(j => [j.id, j.c]), q384: r.q384 || null}; }")
    jc = {j[0]: np.array(j[1]) for j in rig["joints"]}
    print("   blend: %s%s" % (rig["blend"], "; zones %s" % rig["q384"]["zones"] if rig["q384"] else ""), flush=True)
    skin = [x for x in S if x["sys"] == "skin"]
    parts = [(x["idx"], np.asarray(x["v"], float)) for x in skin]
    pairs = PM.border_pairs(parts)
    out = {"blend": rig["blend"], "poses": {}, "ms": {}}
    pg.evaluate("() => { const P = window.__poseApi; P.open(false); P.rings(false); P.reset(); }")
    pg.wait_for_timeout(400)
    for pn, pose in POSES.items():
        pg.evaluate("() => window.__poseApi.reset()")
        ms = []
        for jid, dofs in pose.items():
            for k, val in dofs.items():
                pg.evaluate("(a) => window.__poseApi.set(a[0], a[1], a[2])", [jid, k, val])
                ms.append(pg.evaluate("() => { const s = window.__poseApi.stats(); return [s.ms, s.changed]; }"))
        # one more slider step, everything decoded and warm: the time a drag pays per move
        j0, k0 = next(iter(pose.items())); kk, vv = next(iter(k0.items()))
        step = []
        for dv in (-4, -8, -4, 0):
            pg.evaluate("(a) => window.__poseApi.set(a[0], a[1], a[2])", [j0, kk, vv + dv])
            step.append(pg.evaluate("() => window.__poseApi.stats().ms"))
        out["ms"][pn] = dict(first=[round(m[0], 1) for m in ms], changed=[m[1] for m in ms], step=round(float(np.median(step)), 1))
        row = {}
        for t in TUBES[pn]:
            if t not in by or t not in idx:
                print("   (no structure %s on this page)" % t); continue
            x = by[t]; rest = np.asarray(x["v"], float); p = live(pg, idx[t])
            if p is None or len(p) != len(rest):
                check("%s: %s was moved by the pose" % (pn, t), False); continue
            sl, h, L = PM.slabs(rest, x["f"], cluster=x["sys"] != "muscle")
            row[t] = PM.tube(rest, p, sl, h, x["f"])
        posed = []
        for i, v in parts:
            p = live(pg, idx[S[i]["id"]])
            posed.append(v if p is None else p)
        g = PM.gaps(posed, pairs)
        sk = {}
        for j in JOINTS[pn]:
            m = np.linalg.norm(pairs[4] - jc[j], axis=1) < NEAR
            sk[j] = dict(pairs=int(m.sum()), max=float(g[m].max()), over=int((g[m] > LIM["gap"]).sum()))
        sk["all"] = dict(pairs=len(g), max=float(g.max()), over=int((g > LIM["gap"]).sum()))
        out["poses"][pn] = dict(tubes=row, skin=sk)
        for j in JOINTS[pn]:
            check("%s: skin gap at %s <= %.1f mm (max %.2f mm over %d border pairs, %d over)" % (pn, j, LIM["gap"], sk[j]["max"], sk[j]["pairs"], sk[j]["over"]), sk[j]["max"] <= LIM["gap"])
        print("   %s: skin gap anywhere on the body: max %.1f mm, %d of %d pairs over %.1f mm" % (pn, sk["all"]["max"], sk["all"]["over"], sk["all"]["pairs"], LIM["gap"]), flush=True)
        for t, r in row.items():
            check("%s: %s kink +%.1f deg (<= %.0f; bend %.0f, rest %.0f), cross-section %.2f (>= %.1f), length %+.1f %% (within %.0f)" % (
                pn, t, r["bend_add"], LIM["bend"], r["bend"], r["bend_rest"], r["xsec"], LIM["xsec"], r["dlen"], LIM["dlen"]),
                r["bend_add"] <= LIM["bend"] and r["xsec"] >= LIM["xsec"] and abs(r["dlen"]) <= LIM["dlen"])
        if shots:
            pg.add_style_tag(content="body.q384shot *{visibility:hidden !important} body.q384shot canvas{visibility:visible !important}")
            pg.evaluate("() => document.body.classList.add('q384shot')")
            tgt, dist = VIEWS[pn]
            for lk, Lr in (("skin", {"fat": 0, "fascia": 0.15, "bursa": 0.6}), ("noskin", {"skin": 0, "fat": 0, "fascia": 0.15, "bursa": 0.6})):
                pg.evaluate("() => window.__q338.defaults()")
                for kk_ in LK:
                    pg.evaluate("([k, v]) => window.__q338.layer(k, v)", [kk_, Lr.get(kk_, 1)])
                for vn, az in (("ant", 0.0), ("left", -math.pi / 2), ("post", math.pi), ("right", math.pi / 2)):
                    if lk == "noskin" and vn in ("post",) and not pn.startswith("hipknee_l"):
                        continue
                    pg.evaluate("(c) => window.__q338.cam(c)", {"az": az, "el": 0.08, "dist": dist, "tgt": tgt})
                    pg.wait_for_timeout(450)
                    pg.screenshot(path=str(Path(shots) / ("q384_B_%s_%s_%s_%s.png" % (tag, pn, lk, vn))))
            pg.evaluate("() => { window.__q338.defaults(); document.body.classList.remove('q384shot'); }")
    # back at the model pose: the built geometry, bit for bit
    pg.evaluate("() => window.__poseApi.reset()"); pg.wait_for_timeout(300)
    r = pg.evaluate("""() => { const n = window.__poseApi.rig().count; let bad = 0, moved = 0, worst = 0;
      for (let i = 0; i < n; i++){ const a = window.__poseLive(i), b = window.__poseRestPos(i); if (!a || !b) continue; moved++;
        for (let k = 0; k < a.length; k++) if (a[k] !== b[k]){ bad++; worst = Math.max(worst, Math.abs(a[k] - b[k])); } }
      return {bad, moved, worst, rest: window.__poseApi.isRest()}; }""")
    out["rest"] = r
    check("after Reset the %d structures that moved are the built geometry bit for bit (%d values differ, worst %.2e mm)" % (r["moved"], r["bad"], r["worst"]), r["rest"] and r["bad"] == 0)
    print("   pose update time (ms): " + "; ".join("%s first %s, per slider step %.1f (%s structures)" % (k, v["first"], v["step"], v["changed"][-1]) for k, v in out["ms"].items()), flush=True)
    return out
