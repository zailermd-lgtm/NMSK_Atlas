#!/usr/bin/env python3
"""Q211 build of the two Z-fitted pages (in-process patch of the published pages, no Z build):
   stage bones  : evidence-bounded bone re-seats (male left tibia + fibula distal ends, female zan_vertebra_l1)           (q211_bones)
   stage follow : soft tissue near a moved bone follows it (bone-anchored field + guard ladder)                              (q211_soft.follow)
   stage zones  : elbow + shoulder zones: tear relaxation of the structures that touch in the Z source + guard ladder      (q211_relax / q211_soft)
   stage inbone : soft structures that the fit left inside bone (worse than the unfitted base) pushed out                    (q211_soft.push_group)
   stage pack   : changed meshes re-packed into the published page with before -> after badges; ship diff                    (q211_pack)
    python3 scripts/zanatomy/q211_build.py male|female bones|follow|zones|inbone|pack|all"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q211_core as K  # noqa: E402


class State:
    """V: id -> vertices of every structure changed so far; log: id -> [dict(stage, ...)]"""

    def __init__(self, which):
        self.which = which
        self.pg = K.load(which)
        self.base = K.load(which, base=True)
        self.V, self.log, self.reports = {}, {}, {}

    def v(self, i):
        return self.V[i] if i in self.V else self.pg.v(i)

    def set(self, i, v, **info):
        self.V[i] = np.asarray(v, float)
        self.log.setdefault(i, []).append(info)

    def save(self, stage):
        pickle.dump(dict(V=self.V, log=self.log, reports=self.reports), open(K.state_path(self.which, stage), "wb"))

    @classmethod
    def load(cls, which, stage):
        s = cls(which)
        d = pickle.load(open(K.state_path(which, stage), "rb"))
        s.V, s.log, s.reports = d["V"], d["log"], d["reports"]
        return s


def own_bones(which):
    import scripts.zanatomy.q209_paths  # noqa: F401
    from scripts.zanatomy.q198_load import load
    S = load("own_m" if which == "male" else "own_f")
    return {s["id"]: s["v"] for s in S if s["sys"] == "bone"}


def stage_bones(which, log=print):
    from scripts.zanatomy import q211_bones as B
    st = State(which)
    own = own_bones(which)
    rep = {}
    if which == "male":
        tib, fib, tal = "tibia_l", "fibula_l", "talus_l"
        zt, zf, zl = st.pg.v(tib), st.pg.v(fib), st.pg.v(tal)
        gap0 = B.min_gap(np.vstack([zt, zf]), zl)
        for nm in (tib, fib):
            v = st.pg.v(nm)
            L_z = float(v[:, 1].max() - v[:, 1].min())
            L_o = float(own[nm][:, 1].max() - own[nm][:, 1].min())
            rep[nm] = dict(z_length=L_z, own_length=L_o)
        delta = min(rep[tib]["own_length"] - rep[tib]["z_length"], gap0 - 1.2)
        log(f"male left tibia/fibula: ankle gap {gap0:.2f} mm, own length diff {rep[tib]['own_length'] - rep[tib]['z_length']:.2f} -> delta {delta:.2f} mm")
        for nm in (tib, fib):
            v = st.pg.v(nm)
            top = v[v[:, 1] > v[:, 1].max() - 15].mean(0)
            bot = v[v[:, 1] < v[:, 1].min() + 15].mean(0)
            d = B.axial_field(v, top, bot, delta, t0=0.3)
            w = v + d
            c0, c1 = B.chamfer(v, own[nm]), B.chamfer(w, own[nm])
            rep[nm].update(delta_mm=round(delta, 2), max_move_mm=round(float(np.linalg.norm(d, axis=1).max()), 2), chamfer_z_to_own=[round(c0[0], 2), round(c1[0], 2)], chamfer_own_to_z=[round(c0[1], 2), round(c1[1], 2)])
            st.set(nm, w, stage="bone", kind="axial_extension", **rep[nm])
        wt, wf = st.v(tib), st.v(fib)
        rep["gap_ankle_mm"] = [round(gap0, 2), round(B.min_gap(np.vstack([wt, wf]), zl), 2)]
        rep["gap_ankle_own_mm"] = round(B.min_gap(np.vstack([own[tib], own[fib]]), own[tal]), 2)
        rep["gap_knee_mm"] = [round(B.min_gap(st.pg.v("femur_l"), np.vstack([zt, st.pg.v("patella_l")])), 2), round(B.min_gap(st.pg.v("femur_l"), np.vstack([wt, st.pg.v("patella_l")])), 2)]
        rep["gap_knee_own_mm"] = round(B.min_gap(own["femur_l"], np.vstack([own[tib], own["patella_l"]])), 2)
    else:
        nm, up, lo_ = "zan_vertebra_l1", "zan_vertebra_t12", "zan_vertebra_l2"
        v = st.pg.v(nm)
        gap0 = B.min_gap(st.pg.v(up), v)
        target = B.min_gap(v, st.pg.v(lo_))
        ax_bot = np.array([0.0, float(v[:, 1].min()), 0.0])
        ax_top = np.array([0.0, float(v[:, 1].max()), 0.0])
        # the displacement is along +y (towards T12): bisection on delta so that the T12 | L1 gap equals the L1 | L2 gap
        a, b = 0.0, 14.0
        for _ in range(30):
            m = 0.5 * (a + b)
            w = v + B.axial_field(v, ax_bot, ax_top, m, linear=True)
            if B.min_gap(st.pg.v(up), w) > target:
                a = m
            else:
                b = m
        delta = 0.5 * (a + b)
        d = B.axial_field(v, ax_bot, ax_top, delta, linear=True)
        w = v + d
        own_u = np.vstack([own["lumbar_vertebrae#5"], own["lumbar_vertebrae#6"]])
        c0, c1 = B.chamfer(v, own_u), B.chamfer(w, own_u)
        rep[nm] = dict(delta_mm=round(delta, 2), max_move_mm=round(float(np.linalg.norm(d, axis=1).max()), 2), gap_t12_l1_mm=[round(gap0, 2), round(B.min_gap(st.pg.v(up), w), 2)],
                       gap_l1_l2_mm=[round(target, 2), round(B.min_gap(w, st.pg.v(lo_)), 2)], gap_own_t12_l1_mm=round(B.min_gap(own["thoracic_vertebrae#1"], own["lumbar_vertebrae#5"]), 2),
                       height_mm=[round(float(v[:, 1].max() - v[:, 1].min()), 1), round(float(w[:, 1].max() - w[:, 1].min()), 1)], chamfer_z_to_own_union=[round(c0[0], 2), round(c1[0], 2)],
                       chamfer_own_union_to_z=[round(c0[1], 2), round(c1[1], 2)])
        st.set(nm, w, stage="bone", kind="axial_extension", **rep[nm])
        log(f"female L1: {rep[nm]}")
    st.reports["bones"] = rep
    st.save("bones")
    log(json.dumps(rep, default=float)[:1500])
    return st


def make_env(st, zones=(), log=print):
    """Q198-aligned environment of the CURRENT state (moved bones included): skin field + bone grids of the named zones {name: (lo, hi)}"""
    from scripts.zanatomy import q211_env as EN
    env = EN.Env(st.which, st.pg, V={i: v for i, v in st.V.items() if st.pg.sys(i) == "bone"}, log=log)
    for n, (lo, hi) in dict(zones).items():
        env.add_zone(n, lo, hi)
    return env


def stage_follow(which, log=print):
    from scripts.zanatomy import q211_soft as SF
    st = State.load(which, "bones")
    moved = {i: v for i, v in st.V.items() if st.pg.sys(i) == "bone"}
    pts = np.vstack([np.vstack([st.pg.v(i), v]) for i, v in moved.items()])
    lo, hi = pts.min(0) - 75.0, pts.max(0) + 75.0
    env = make_env(st, {"follow": (lo, hi)}, log)
    out = SF.follow(env, "follow", st, moved, log=log)
    names = {"tibia_l": "left tibia", "fibula_l": "left fibula", "zan_vertebra_l1": "L1 vertebra"}
    for i, (v, rep) in out.items():
        st.set(i, v, stage="follow", bones=sorted(names.get(b, b) for b in moved), **rep)
    st.reports["follow"] = {i: r for i, (v, r) in out.items()}
    st.save("follow")
    return st


def stage_zones(which, log=print, joints=("shoulder", "elbow"), sides=("l", "r")):
    from scripts.zanatomy import q211_soft as SF
    cfg = K.PAGES[which]
    st = State.load(which, "follow")
    rb = json.loads((REPO / f"build/q209_raw/Q198_model_{cfg['base_key']}.json").read_text())
    st.reports.setdefault("zones", {})
    for side in sides:
        for jn in joints:
            jb = next(x for x in rb["junctions"] if x["name"] == jn and x["side"] == side)
            c, R = np.asarray(jb["centre_mm"], float), jb["R"] + 25
            ids = SF.zone_ids(st.pg, st.base, jb["zone_ids"])
            allp = np.vstack([st.v(i) for i in ids] + [st.v(i) for i in st.pg.ids if st.pg.sys(i) == "bone" and i.endswith("_" + side) and np.linalg.norm(st.v(i).mean(0) - c) < 250])
            zone = f"{jn}_{side}"
            env = make_env(st, {zone: (allp.min(0) - 20, allp.max(0) + 20)}, log)
            t = time.time()
            out, rep, Z, X = SF.relax_zone(env, zone, st, ids, c, R, log=log)
            for i, v in out.items():
                st.set(i, v, stage="zone", zone=zone, **rep["structures_report"][i])
            rep.pop("structures_report")
            st.reports["zones"][zone] = rep
            log(f"  {zone}: moved {len(out)} structures, tear > 5 mm {rep['tear_gt5_before']} -> {rep['tear_gt5_after']} [{time.time() - t:.0f}s]")
            st.save("zones")
    return st


REGION_GROUPS = {   # Q204 region -> zone group (separate boxes per side where the region is paired)
    "head_neck": "head", "thorax": "trunk", "abdomen_pelvis": "trunk", "shoulder": "arm", "arm_elbow_forearm": "arm", "wrist_hand": "arm", "hip": "leg", "thigh": "leg", "knee": "leg", "leg": "leg", "ankle": "leg", "foot": "leg"}


def inbone_targets(which, st):
    """soft structures with a Q204 inside-bone / outside-skin defect (severity >= 2) on the page that the unfitted Z base does NOT have (created or worsened by the fit)"""
    cfg = K.PAGES[which]
    F = {r["id"]: r for r in json.loads((REPO / f"build/q211_raw/Q204_regions_{cfg['key0']}.json").read_text())["rows"]}
    B = {r["id"]: r for r in json.loads((REPO / f"build/q209_raw/Q204_regions_{cfg['base_key']}.json").read_text())["rows"]}
    flagged = lambda r: any(x["check"] in ("inside_bone", "outside_skin") and x["severity"] >= 2 for x in r["defects"])
    return sorted(i for i, r in F.items() if r["sys"] not in ("bone", "skin") and flagged(r) and not (i in B and flagged(B[i])))


def stage_inbone(which, log=print, src="zones"):
    from scripts.zanatomy import q211_soft as SF
    st = State.load(which, src)
    ids = inbone_targets(which, st)
    log(f"inbone: {len(ids)} structures with a fit-made inside-bone defect")
    cfg = K.PAGES[which]
    F = {r["id"]: r for r in json.loads((REPO / f"build/q211_raw/Q204_regions_{cfg['key0']}.json").read_text())["rows"]}
    groups = {}
    for i in ids:
        g = REGION_GROUPS.get(F[i]["region"], "trunk")
        side = i[-1] if i[-2:] in ("_l", "_r") else "m"
        groups.setdefault((g, side if g in ("arm", "leg") else "m"), []).append(i)
    st.reports["inbone"] = {"targets": ids, "repaired": {}, "kept": []}
    for (g, side), gi in sorted(groups.items()):
        pts = np.vstack([st.v(i) for i in gi])
        lo, hi = pts.min(0) - 30, pts.max(0) + 30
        zone = f"inbone_{g}_{side}"
        env = make_env(st, {zone: (lo, hi)}, log)
        out = SF.push_group(env, zone, st, gi, log=log)
        for i, (v, rep) in out.items():
            st.set(i, v, stage="inbone", zone=zone, **rep)
            st.reports["inbone"]["repaired"][i] = rep
        st.reports["inbone"]["kept"] += [i for i in gi if i not in out]
        log(f"  {zone}: {len(gi)} targets, {len(out)} repaired")
        st.save("inbone")
    return st


if __name__ == "__main__":
    which, stages = sys.argv[1], sys.argv[2:]
    for s in (["bones", "follow", "zones", "inbone", "pack"] if stages == ["all"] else stages):
        globals()["stage_" + s](which)
