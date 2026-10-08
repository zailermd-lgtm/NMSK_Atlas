#!/usr/bin/env python3
"""Q208 change of the DISPLAYED skin surface seen by the needle tool: the needle tool (clinical/needle_tool.js, TP.skinDepth) measures the depth of a target below the nearest skin hit on the needle path at run time, so
what matters is how far the outer surface of the skin moved, not how far single vertices moved (the forearm slabs were re-placed, the surface moved less than the vertices).  Per patch group: distance of the new outer
sheet from the old outer sheet (nearest point, signed + outward), mean / p95 / max.   python3 scripts/zanatomy/q208_depth.py male|female"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q208_core as K  # noqa: E402
from scripts.zanatomy import q208_refit as RF  # noqa: E402


def run(which):
    import trimesh
    pg, raw = K.load(which)
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    V1 = pickle.load(open(K.state_path(which, "uro"), "rb"))[0]
    rep = pickle.load(open(K.state_path(which, "report"), "rb"))
    out = {"page": which, "patches": {}, "groups": {}}
    for side in "lr":
        bones = K.side_bones(raw, side)
        ids = [i for i in rep["moved"] if i.endswith("_" + side)]
        allids = [i for i in pg.skin_ids if i.endswith("_" + side) and any(k in i for k in K.TUBE + K.ELBOW + K.ARM_NB + K.WRIST_NB)]
        # old outer surface of the whole limb group
        vs, fs, o = [], [], 0
        for i in allids:
            S = RF.Slabs({i: raw.v(i)}, {i: pg.f(i)}, [i])
            of = S.outer_flags(bone_pts=bones)
            f = pg.f(i)
            vs.append(V0[i])
            fs.append(f[of[f].all(1)] + o)
            o += len(V0[i])
        old = trimesh.Trimesh(np.vstack(vs), np.vstack(fs), process=False)
        pq = trimesh.proximity.ProximityQuery(old)
        for i in ids:
            S = RF.Slabs({i: raw.v(i)}, {i: pg.f(i)}, [i])
            of = S.outer_flags(bone_pts=bones)
            P = V1[i][of]
            cp, dist, tri = pq.on_surface(P)
            nrm = old.face_normals[tri]
            sgn = np.sign(((P - cp) * nrm).sum(1))
            d = dist * np.where(sgn == 0, 1, sgn)
            n = i[len("zan_skin_"):-2]
            grp = "forearm / wrist" if n in K.TUBE else ("elbow / cubital" if n in K.ELBOW else "neighbour")
            out["patches"][i] = {"group": grp, "mean_mm": round(float(d.mean()), 2), "p95_abs_mm": round(float(np.percentile(np.abs(d), 95)), 2), "max_abs_mm": round(float(np.abs(d).max()), 2)}
    for g in ("forearm / wrist", "elbow / cubital", "neighbour"):
        xs = [x for x in out["patches"].values() if x["group"] == g]
        if xs:
            out["groups"][g] = {"patches": len(xs), "mean_outward_mm": round(float(np.mean([x["mean_mm"] for x in xs])), 2), "max_patch_mean_mm": max(x["mean_mm"] for x in xs), "p95_abs_mm_max": max(x["p95_abs_mm"] for x in xs)}
    (REPO / "data" / "derived" / f"Q208_skin_surface_change_{which}.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    r = run(sys.argv[1])
    print(r["groups"])
