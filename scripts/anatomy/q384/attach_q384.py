#!/usr/bin/env python3
"""Q384 / E3: do the muscles keep their origins and insertions on their bones when a joint is posed?

Owner, 2026-11-22: "latissimus dorsi loses its hold when the hand is abducted -- make sure origin + insertion are always
kept."

The attachment sites are this project's own placed sites (data/derived/Q220_parts_z<page>.json, rule `end_snap_bone`: the
end of the muscle's mesh that touches a bone, the footprint centre on that bone's surface, the footprint radius). For each
site the FOOTPRINT is the muscle's vertices within the footprint radius (8..30 mm) of the centre. In a pose the bone moves
rigidly with its segment; the footprint has kept its hold when its vertices went with that same motion. Measured per site:
  drift  mean distance (mm) between the posed footprint vertices and where the bone's own motion carries them
  gap    change (mm) of the median distance from the footprint vertices to the bone's surface, pose minus rest
A site is LOST in a pose when drift > LIMIT (5 mm). Nothing here is anatomy beyond the placed sites themselves: the measure
is of the display rule (the skinning weights).

    python3 scripts/anatomy/q384/attach_q384.py base_m [RIG.json] [--poses all|test] [--json out.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "q241"))
import pose_replica_q384 as PR  # noqa: E402

LIMIT = 5.0
R_MIN, R_MAX = 8.0, 30.0
FILES = {"base_m": "Q220_parts_zbase_m.json", "base_f": "Q220_parts_zbase_f.json"}
TEST_POSES = {
    "hipknee_l": {"hip_l": {"flex": 90}, "knee_l": {"flex": 90}},
    "hipknee_r": {"hip_r": {"flex": 90}, "knee_r": {"flex": 90}},
    "elbow_l": {"elbow_l": {"flex": 120}},
    "shoulder_l": {"shoulder_l": {"abd": 120}},
    "arm_r": {"shoulder_r": {"abd": 90, "flex": 30}, "elbow_r": {"flex": 120}},
}
SWEEP = dict(TEST_POSES)
for _s in ("l", "r"):
    for _a in (45, 90, 135, 170):
        SWEEP["sh_%s_abd%d" % (_s, _a)] = {"shoulder_" + _s: {"abd": _a}}
        SWEEP["sh_%s_flex%d" % (_s, _a)] = {"shoulder_" + _s: {"flex": _a}}


def sites(key, S, rig):
    """-> list of dict(part, type, muscle (structure index), mid, bone, seg, pos, verts, r): the placed bony ends of muscles on this page"""
    d = json.loads((REPO / "data/derived" / FILES[key]).read_text(encoding="utf-8"))
    by = {x["id"]: x for x in S}
    seg_of = {i: g[0] for g in rig["rigid"] for i in g[1]}
    out = []
    for p in d["placed"]:
        if p.get("rule") != "end_snap_bone" or p.get("part_type") not in ("origin_part", "insertion_point"):
            continue
        mid, bid = p["mesh_ids"][0], p.get("bone_mesh")
        if mid not in by or bid not in by or by[mid]["sys"] != "muscle" or by[bid]["idx"] not in seg_of:
            continue
        v = np.asarray(by[mid]["v"], float); pos = np.array(p["position_mm"], float)
        r = float(np.clip(p.get("patch_radius_mm") or R_MIN, R_MIN, R_MAX))
        vi = np.where(np.linalg.norm(v - pos, axis=1) <= r)[0]
        if len(vi) < 3:
            continue
        out.append(dict(part=p["part_id"], type=p["part_type"], side=p.get("side"), muscle=by[mid]["idx"], mid=mid, bone=by[bid]["idx"], bid=bid,
                        seg=seg_of[by[bid]["idx"]], pos=pos, verts=vi, r=r))
    return out


def measure(site, rest, posed, M, bone_tree=None, bone_rest_gap=None):
    """drift (and gap change when the bone's rest surface is given) of one site in one pose"""
    A = M[site["seg"]]
    v = rest[site["verts"]]; p = posed[site["verts"]]
    carried = v @ A[:3, :3].T + A[:3, 3]
    out = dict(drift=float(np.linalg.norm(p - carried, axis=1).mean()))
    if bone_tree is not None:
        back = (p - A[:3, 3]) @ A[:3, :3]                    # the posed footprint in the bone's rest frame
        out["gap"] = float(np.median(bone_tree.query(back)[0]) - bone_rest_gap)
    return out


def table(key, rigfile=None, poses=None, S=None, verbose=True):
    import model as MD
    if S is None:
        S = MD.Model(key).S
    rig, blob = PR.load_rig(rigfile or REPO / "data/anatomy" / ("pose_rig_%s.json" % key))
    W = PR.decode_all(rig, blob, S)
    blend = PR.blend_of(rig)
    st = sites(key, S, rig)
    need = {s["muscle"] for s in st}
    trees = {}
    for s in st:
        if s["bone"] not in trees:
            trees[s["bone"]] = cKDTree(np.asarray(S[s["bone"]]["v"], float))
        s["gap0"] = float(np.median(trees[s["bone"]].query(np.asarray(S[s["muscle"]]["v"], float)[s["verts"]])[0]))
    res = {}
    for pn, pose in (poses or SWEEP).items():
        M = PR.fk(rig, pose)
        P = PR.posed(S, W, M, need, blend)
        for s in st:
            r = measure(s, np.asarray(S[s["muscle"]]["v"], float), P[s["muscle"]], M, trees[s["bone"]], s["gap0"])
            res.setdefault((s["mid"], s["type"], s["bid"]), {})[pn] = r
    lost = {k: max(v.items(), key=lambda kv: kv[1]["drift"]) for k, v in res.items()}
    lost = {k: v for k, v in lost.items() if v[1]["drift"] > LIMIT}
    if verbose:
        print("%s (%s blend): %d placed bony ends of %d muscles; lost (> %.0f mm off their bone) in at least one of %d poses: %d" % (
            key, rig.get("blend", "linear"), len(st), len(need), LIMIT, len(poses or SWEEP), len(lost)), flush=True)
        for k, (pn, r) in sorted(lost.items(), key=lambda kv: -kv[1][1]["drift"])[:25]:
            print("   %-44s %-15s on %-22s worst %-14s drift %5.1f mm, gap %+5.1f mm" % (k[0], k[1], k[2], pn, r["drift"], r.get("gap", 0.0)))
        for k, v in res.items():
            if k[0].startswith("latissimus_dorsi"):
                print("   " + k[0], k[1], k[2], " ".join("%s %.1f" % (pn.replace("sh_", ""), r["drift"]) for pn, r in v.items() if pn.startswith("sh_" + k[0][-1])))
    return dict(n_sites=len(st), n_muscles=len(need), lost={"%s|%s|%s" % k: dict(pose=v[0], **v[1]) for k, v in lost.items()},
                worst=max((r["drift"] for v in res.values() for r in v.values()), default=0.0))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("key", choices=sorted(FILES)); ap.add_argument("rig", nargs="?"); ap.add_argument("--poses", default="all"); ap.add_argument("--json")
    g = ap.parse_args()
    o = table(g.key, g.rig, TEST_POSES if g.poses == "test" else None)
    if g.json:
        Path(g.json).write_text(json.dumps(o, indent=1), encoding="utf-8")
