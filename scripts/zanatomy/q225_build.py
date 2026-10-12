#!/usr/bin/env python3
"""Q225 build of the two Z-fitted pages (in-process patch of the Q221 / Q222 pages, no Z build; the Q211 machinery pointed at the new sources):
   stage bones  : left-elbow radius + ulna re-seated on the humerus (q225_elbow), patellae re-seated on the femoral trochlea, floating ribs 11 / 12 (+ the 2nd left rib of the female) re-seated on their vertebra
   stage follow : soft tissue near a moved bone follows it (bone-anchored field + guard ladder, q211_soft.follow)
   stage zones  : left elbow, both wrists, both shoulders: tear relaxation of the structures that touch in the Z source + guard ladder (q211_soft.relax_zone)
   stage final  : attachment guard / island-gap revert (as Q211)
   stage pack   : q225_pack
    python3 scripts/zanatomy/q225_build.py male|female bones|follow|zones|final|all"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q225_core as K5  # noqa: E402

Q = K5.patch_q211()
from scripts.zanatomy import q211_build as B11  # noqa: E402
from scripts.zanatomy import q225_elbow as EL  # noqa: E402

State = B11.State
ELBOW_OPTS = dict(taper=0.4, w_reg=0.3, w_pull=2.0, w_ev=0.6, ev_cap=5.0, floor_frac=0.8)
PATELLA_OPTS = dict(rigid=True, w_rot=8.0, w_reg=0.3, w_pull=4.0, w_ev=0.6, ev_cap=5.0, floor_frac=0.8)
RIB_OPTS = dict(taper=0.4, w_reg=0.3, w_pull=2.0, w_ev=0.6, ev_cap=5.0, floor_frac=0.8)
GUARDS = dict(max_penetration_mm=1.0, max_move_mm=20.0, max_fit_error_rise_mm=4.0, volume_ratio=(0.93, 1.07), joint_space_band_mm=(-1.5, 2.5))
ZONE_BONES = {"elbow": ("humerus", "radius", "ulna"), "shoulder": ("scapula", "humerus"), "wrist": ("radius", "ulna")}
CARPALS = ("capitate", "hamate", "lunate", "pisiform", "scaphoid", "trapezium", "trapezoid", "triquetrum")


def mesh_volume(v, f):
    v = np.asarray(v, float)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)


def edge_stretch(v0, v1, f):
    e = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1), axis=0)
    l0 = np.linalg.norm(v0[e[:, 0]] - v0[e[:, 1]], axis=1)
    l1 = np.linalg.norm(v1[e[:, 0]] - v1[e[:, 1]], axis=1)
    r = l1 / np.maximum(l0, 1e-6)
    return round(float(np.percentile(r, 1)), 3), round(float(np.percentile(r, 99)), 3)


def base_gap(base_pg, a, b):
    t = EL.pair_table({a: base_pg.v(a), b: base_pg.v(b)}, {a: base_pg.f(a), b: base_pg.f(b)}, [(a, b)])[f"{a}|{b}"]
    g = t["joint_space_p05_mm"] if t["joint_space_p05_mm"] is not None else t["min_clearance_mm"]
    return max(float(g), 0.3), t


def jobs(which, pg):
    J = [dict(name="left elbow (radius + ulna on the humerus)", kind="elbow_reseat", moving=["ulna_l", "radius_l"], fixed=["humerus_l"], own_for={}, opts=ELBOW_OPTS,
              pairs=[("humerus_l", "ulna_l"), ("humerus_l", "radius_l"), ("radius_l", "ulna_l")], anchor=None)]
    for s in "lr":
        J.append(dict(name=f"patella_{s}", kind="patella_reseat", moving=[f"patella_{s}"], fixed=[f"femur_{s}"], own_for={}, opts=PATELLA_OPTS, pairs=[(f"femur_{s}", f"patella_{s}")], anchor=None))
    for s in "lr":
        for k, v in (("eleventh", "zan_vertebra_t11"), ("twelfth", "zan_vertebra_t12")):
            J.append(dict(name=f"{k} rib {s}", kind="rib_reseat", moving=[f"zan_{k}_rib_{s}"], fixed=[v], own_for={f"zan_{k}_rib_{s}": f"ribs_{s}"}, opts=RIB_OPTS, pairs=[(v, f"zan_{k}_rib_{s}")], anchor=None))
    if which == "female":
        J.append(dict(name="second rib l", kind="rib_reseat", moving=["zan_second_rib_l"], fixed=["zan_vertebra_t2"], own_for={"zan_second_rib_l": "ribs_l"}, opts=RIB_OPTS, pairs=[("zan_vertebra_t2", "zan_second_rib_l")], anchor=None))
    return J


def stage_bones(which, log=print, only=None):
    st = State(which)
    pg, base = st.pg, st.base
    own = K5.own_bones(which)
    rep = {}
    for j in jobs(which, pg):
        if only and j["kind"] not in only:
            continue
        t0 = time.time()
        gaps, bgap = {}, {}
        for a, b in j["pairs"]:
            gaps[(a, b)], bgap[f"{a}|{b}"] = base_gap(base, a, b)
        names = j["fixed"] + j["moving"]
        bones = {n: (pg.v(n), pg.f(n)) for n in names}
        anchor = pg.v(j["fixed"][0])
        if j["kind"] == "elbow_reseat":
            hv = anchor
            anchor = hv[hv[:, 1] < hv[:, 1].min() + 25].mean(0)
        else:
            anchor = anchor.mean(0)
        R = EL.reseat(bones, own, gaps, anchor, j["moving"], j["fixed"], j["opts"], log=log, own_for=j["own_for"])
        r = R["report"]
        # guards
        ok, why = True, []
        for k, t in r["joint_after"].items():
            if t["max_penetration_mm"] > GUARDS["max_penetration_mm"]:
                ok = False
                why.append(f"penetration {k} {t['max_penetration_mm']} mm")
            g = gaps[tuple(k.split("|"))] if tuple(k.split("|")) in gaps else gaps[tuple(k.split("|"))[::-1]]
            p = t["joint_space_p05_mm"]
            if p is not None and not (g + GUARDS["joint_space_band_mm"][0] <= p <= g + GUARDS["joint_space_band_mm"][1]):
                why.append(f"joint space {k} {p} vs base {g:.2f} (band)")
                ok = False if p < 0 else ok
        for n in j["moving"]:
            b = r["bones"][n]
            v0, v1, f = pg.v(n), R["W"][n], pg.f(n)
            vr = mesh_volume(v1, f) / mesh_volume(v0, f)
            b["volume_ratio"] = round(vr, 3)
            b["edge_ratio_p01_p99"] = edge_stretch(v0, v1, f)
            if not (GUARDS["volume_ratio"][0] <= vr <= GUARDS["volume_ratio"][1]):
                ok = False
                why.append(f"volume {n} x{vr:.3f}")
            if b["max_move_mm"] > GUARDS["max_move_mm"]:
                ok = False
                why.append(f"move {n} {b['max_move_mm']} mm")
            if "fit_error_before_zone_whole" in b:
                rise = b["fit_error_after_zone_whole"][1][0] - b["fit_error_before_zone_whole"][1][0]
                if rise > GUARDS["max_fit_error_rise_mm"]:
                    ok = False
                    why.append(f"fit error {n} +{rise:.1f} mm")
        r["base_gaps"] = {k: dict(joint_space_p05_mm=v["joint_space_p05_mm"], min_clearance_mm=v["min_clearance_mm"], max_penetration_mm=v["max_penetration_mm"]) for k, v in bgap.items()}
        r["target_gaps_mm"] = {f"{a}|{b}": round(g, 2) for (a, b), g in gaps.items()}
        r["accepted"], r["reasons_if_not"] = ok, why
        rep[j["name"]] = r
        log(f"{which} {j['name']}: accepted={ok} {why} [{time.time() - t0:.0f}s]")
        log("   joint before: " + json.dumps(r["joint_before"])[:600])
        log("   joint after : " + json.dumps(r["joint_after"])[:600])
        for n in j["moving"]:
            log("   " + n + ": " + json.dumps(r["bones"][n]))
        if ok:
            for n in j["moving"]:
                st.set(n, R["W"][n], stage="bone", kind=j["kind"], job=j["name"], bone=n, bone_report=r["bones"][n], joint_before=r["joint_before"], joint_after=r["joint_after"], base_gaps=r["base_gaps"])
    st.reports["bones"] = rep
    st.save("bones")
    (K5.BUILD / f"{which}_bones_report.json").write_text(json.dumps(rep, indent=1, default=float))
    return st


def moved_groups(st):
    """groups of moved bones that are treated together by the follow stage (one environment box each)"""
    g = {}
    for i, v in st.V.items():
        if st.pg.sys(i) != "bone":
            continue
        key = "elbow_l" if i in ("ulna_l", "radius_l") else i
        g.setdefault(key, {})[i] = v
    return g


def stage_follow(which, log=print):
    from scripts.zanatomy import q211_soft as SF
    st = State.load(which, "bones")
    names = {"ulna_l": "left ulna", "radius_l": "left radius", "patella_l": "left patella", "patella_r": "right patella"}
    for key, moved in moved_groups(st).items():
        pts = np.vstack([np.vstack([st.pg.v(i), v]) for i, v in moved.items()])
        lo, hi = pts.min(0) - 75.0, pts.max(0) + 75.0
        env = B11.make_env(st, {"follow": (lo, hi)}, log)
        out = SF.follow(env, "follow", st, moved, log=log)
        for i, (v, rep) in out.items():
            st.set(i, v, stage="follow", bones=sorted(names.get(b, b.replace("zan_", "").replace("_", " ")) for b in moved), **rep)
        st.reports.setdefault("follow", {})[key] = {i: r for i, (v, r) in out.items()}
        st.save("follow")
        log(f"follow {key}: {len(out)} structures followed")
    st.save("follow")
    return st


def stage_zones(which, log=print, joints=(("elbow", "l"), ("wrist", "l"), ("wrist", "r"), ("shoulder", "l"), ("shoulder", "r")), src="follow"):
    from scripts.zanatomy import q211_soft as SF
    from scripts.zanatomy import q206_carry as _C6
    cfg = K5.PAGES[which]
    st = State.load(which, src)
    rb = json.loads((REPO / f"build/q223_raw/Q198_model_{cfg['base_key']}.json").read_text())
    st.reports.setdefault("zones", {})
    matched = set(Q.matched(st.pg, st.base))
    for jn, side in joints:
        jb = next(x for x in rb["junctions"] if x["name"] == jn and x["side"] == side)
        c, R = np.asarray(jb["centre_mm"], float), jb["R"] + 25
        ids = SF.zone_ids_fitseams(st.pg, st.base, c, R)
        allp = np.vstack([st.v(i) for i in ids] + [st.v(i) for i in st.pg.ids if st.pg.sys(i) == "bone" and i.endswith("_" + side) and np.linalg.norm(st.v(i).mean(0) - c) < 250])
        zone = f"{jn}_{side}"
        env = B11.make_env(st, {zone: (allp.min(0) - 20, allp.max(0) + 20)}, log)
        t = time.time()
        fb = [b + "_" + side for b in ZONE_BONES[jn] if b + "_" + side in matched]
        if jn == "wrist":
            fb += [i for i in st.pg.ids if st.pg.sys(i) == "bone" and i.endswith("_" + side) and any(k in i for k in CARPALS) and i in matched]
        out, rep, Z, X = SF.relax_zone(env, zone, st, ids, c, R, log=log, frame_bones=fb)
        mus_all = [i for i in jb["zone_ids"] if st.pg.sys(i) == "muscle"]
        bone_ids_ = [i for i in st.pg.ids if st.pg.sys(i) == "bone" and np.linalg.norm(st.v(i).mean(0) - c) < 400]
        out_a, ainfo = SF.attach_guard(st, dict(out), bone_ids_, log=log)
        out2, ginfo = SF.overlap_guard(st, mus_all, out_a, log=log)
        changed = set(ainfo) | set(ginfo)
        if changed:
            for k, i in enumerate(Z.ids):
                if i in changed:
                    v_ = out2.get(i, st.v(i))
                    X[Z.off[i]:Z.off[i] + len(v_)] = v_
            t1 = Z.tears(X)
            rep["tear_gt5_after"], rep["tear_gt2_after"], rep["tear_median_after_mm"] = round(float((t1 > 5).mean()), 4), round(float((t1 > 2).mean()), 4), round(float(np.median(t1)), 2)
            for k, i in enumerate(Z.ids):
                sel = (Z.lab[Z.P[:, 0]] == k) | (Z.lab[Z.P[:, 1]] == k)
                if sel.sum():
                    rep["tear_gt5_by_structure"]["after"][i] = round(float((t1[sel] > 5).mean()), 3)
            rep["attach_guard"] = {i: {"end_dist_before_mm": [round(x, 1) for x in a_], "end_dist_after_relaxation_mm": [round(x, 1) for x in b_], "move_factor": f_} for i, (a_, b_, f_) in ainfo.items()}
            rep["overlap_guard"] = {i: {"before_pct": b_, "after_pct": a_, "move_factor": f_} for i, (b_, a_, f_) in ginfo.items()}
            for i in changed:
                if i not in out2:
                    rep["structures_report"].pop(i, None)
                else:
                    mv = np.linalg.norm(out2[i] - st.v(i), axis=1)
                    rep["structures_report"][i]["mean_move_mm"], rep["structures_report"][i]["max_move_mm"] = round(float(mv.mean()), 2), round(float(mv.max()), 2)
                    rep["structures_report"][i]["after"] = _C6.metrics(env, zone, out2[i], st.base.v(i).astype(float), st.pg.f(i))
            rep["moved"] = len(out2)
        out = out2
        for i, v in out.items():
            st.set(i, v, stage="zone", zone=zone, **rep["structures_report"][i])
        rep.pop("structures_report")
        st.reports["zones"][zone] = rep
        log(f"  {zone}: moved {len(out)} structures, tear > 5 mm {rep['tear_gt5_before']} -> {rep['tear_gt5_after']} [{time.time() - t:.0f}s]")
        st.save("zones")
    return st


def stage_final(which, log=print, src="zones"):
    """as Q211 stage_final, from the `zones` state"""
    from scripts.zanatomy import q211_soft as SF
    from scripts.zanatomy import q206_carry as C6
    from scipy.spatial import cKDTree
    st = State.load(which, src)
    pg = st.pg
    rep = {"reverted_island_gap": {}, "attachment_guard": {}}
    for i in list(st.V):
        if pg.sys(i) in ("vessel", "nerve"):
            a, b = SF.island_gap(pg.v(i), pg.f(i)), SF.island_gap(st.V[i], pg.f(i))
            if b > a + 3.0:
                rep["reverted_island_gap"][i] = [round(a, 1), round(b, 1), [L["stage"] for L in st.log[i]]]
                st.V.pop(i)
                st.log.pop(i)
    log(f"final: {len(rep['reverted_island_gap'])} vessels / nerves back to the published mesh (island gap): {list(rep['reverted_island_gap'])}")
    bones = [i for i in pg.ids if pg.sys(i) == "bone"]
    tree = cKDTree(np.vstack([st.v(b) for b in bones]))
    blended = {}
    for i in list(st.V):
        if pg.sys(i) not in ("muscle", "tendon"):
            continue
        v0, v1 = pg.v(i).astype(float), st.V[i]
        d0 = SF.end_distances(v0, tree)
        for fct in (1.0, 0.75, 0.5, 0.25, 0.0):
            v = v0 + fct * (v1 - v0)
            d1 = SF.end_distances(v, tree)
            if all(a <= max(b + 1.5, 4.5) for a, b in zip(d1, d0)):
                break
        if fct < 1.0:
            rep["attachment_guard"][i] = {"end_dist_page_mm": [round(x, 1) for x in d0], "end_dist_full_move_mm": [round(x, 1) for x in SF.end_distances(v1, tree)], "kept_share_of_move": fct}
            blended[i] = v
    log(f"final: attachment guard reduced {len(blended)} muscles / tendons")
    if blended:
        pts = np.vstack([np.vstack([pg.v(i), v]) for i, v in blended.items()])
        lo, hi = pts.min(0) - 40.0, pts.max(0) + 40.0
        for i, v in blended.items():
            fct = rep["attachment_guard"][i]["kept_share_of_move"]
            if fct == 0.0:
                st.V.pop(i, None)
                st.log.pop(i, None)
                continue
            for L in st.log[i]:
                L["superseded"] = True
            st.V[i] = v
        env = B11.make_env(st, {"final": (lo, hi)}, log)
        for i, v in blended.items():
            fct = rep["attachment_guard"][i]["kept_share_of_move"]
            if fct == 0.0:
                continue
            r = (st.base.v(i) if (i in st.base.S and len(st.base.v(i)) == len(v)) else pg.v(i)).astype(float)
            m0 = C6.metrics(env, "final", pg.v(i).astype(float), r, pg.f(i))
            m1 = C6.metrics(env, "final", v, r, pg.f(i))
            mv = np.linalg.norm(v - pg.v(i), axis=1)
            st.log[i].append({"stage": "final", "kind": "attachment_guard", "cat": pg.sys(i), "mean_move_mm": round(float(mv.mean()), 2), "max_move_mm": round(float(mv.max()), 2), "before": m0, "after": m1, **rep["attachment_guard"][i]})
    st.reports["final"] = rep
    st.save("final")
    return st


if __name__ == "__main__":
    which, stages = sys.argv[1], sys.argv[2:]
    for s in (["bones", "follow", "zones", "final"] if stages == ["all"] else stages):
        globals()["stage_" + s](which)
