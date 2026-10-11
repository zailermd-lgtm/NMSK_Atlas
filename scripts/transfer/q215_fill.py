#!/usr/bin/env python3
"""Q215: replace the male-carried HIP / THIGH target muscles of the own female page by muscles re-bounded on HER OWN evidence, worst first, inside guards.

    python3 scripts/transfer/q215_fill.py --work SCRATCH/q215/work --crops SCRATCH/q215/crops [--dry] [--only id,id] [--out build/viewer_f_hr_q215] [--report data/derived/Q215_report.json]

Input  = the Q214 female bundle (build/viewer_f_hr_q214); output = a NEW bundle (build/viewer_f_hr_q215).  Every entry that is not listed in the report stays byte for byte.
Evidence = her 1 mm colour cryosections registered to her CT femur (Q179 / Q181 registration, `vhf_thigh_refit_q181.py photos`) and her CT bones / own CT and pelvic-floor muscles.
Method = the Q48 marker watershed redone in the registered frame (q215_refit.py): region = her photographed muscle, markers = the previous (Q48) labels moved by the registered offset, her bones and
her own measured muscles are never part of a target muscle; every muscle that is not a target is held at its base voxels.  The muscle SET (identity) is still the male's: Source class stays
TRANSFERRED -- the card says so; what changes is the position, extent and boundaries, which are hers.
Per candidate the guards (all must hold, else the muscle is NOT replaced and the reasons are recorded; a failed muscle is held and the refit re-run, max MAX_ROUNDS):
  skin (every vertex inside, >= 1 mm deep), bone (<= 8 % of the vertices inside bone, deepest embedding <= 5 mm on the Q204 lattice), photographed-muscle share (>= 0.60 and not below the old
  mesh's), volume within 0.55-1.45 of the old mesh (her measured compartment = the Q48 septa-bounded region it replaces), end-to-end length >= 0.85 x the old mesh, <= 60 % of the volume inside the
  other muscles (Q204 lattice measure, final state with all replacements swapped in), one connected piece (>= 0.98 of the vertices or the old mesh's share), surface move <= 25 mm (p95), and a
  Z-fill continuation piece welded to the old mesh (if any) must still meet the new mesh within 2.5 mm."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import nibabel as nib
import trimesh
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q214_fit as F  # noqa: E402
from scripts.transfer import q213_inbone as IB  # noqa: E402
from scripts.transfer import q215_refit as RF  # noqa: E402
from scripts.transfer.q215_common import *  # noqa: E402,F401,F403
from scripts.cryo import vhf_thigh_refit_q181 as R  # noqa: E402

SUBJECT = "xfer_vhm2vhf_sep_q215"
BUDGET = 9000                     # triangles of a muscle of this page (the replaced meshes have 9000)
MAX_ROUNDS = 6
# ------------------------------------------------------------------ guards
SKIN_DEPTH_MIN_MM = 1.0
IN_BONE_MAX_PCT = 8.0             # ray-parity share of vertices inside a bone mesh (the Q213 in-bone repair threshold)
BONE_DEPTH_MAX_MM = 5.0           # Q204 lattice depth
MUSC_SHARE_MIN = 0.60
VOL_LO, VOL_HI = 0.55, 1.45
LEN_LO = 0.85
OVERLAP_MAX = 60.0
OVERLAP_NOTE = 40.0
MAIN_PIECE_MIN = 0.98
MOVE_P95_MAX_MM = 25.0
SEAM_MAX_MM = 2.5
Z_GATE_LO, Z_GATE_HI = 0.25, 4.5  # reported against the Z-Anatomy female reference volume; gated wide (a muscle outside it is not a plausible adult muscle)

ATTRIBUTION = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections via the NCI Imaging Data Commons, registered to her CT femur (Q179); the transferred muscle "
               "set from the male's DU lower-limb release (Andreassen et al. 2023, Sci Data 10:34, doi:10.1038/s41597-022-01905-2, CC BY 4.0). Hip / thigh target muscles re-bounded on her registered "
               "photographs in Q215 (scripts/transfer/q215_refit.py, q215_fill.py). Derived data.")


# ------------------------------------------------------------------ small helpers
def vol_cm3(v, f):
    return abs(IB.volume(v, f)) / 1000.0


def principal_axis(v):
    c = v.mean(0)
    return c, np.linalg.svd(v - c, full_matrices=False)[2][0]


def extent_along(v, c, u):
    t = (v - c) @ u
    return float(np.percentile(t, 99) - np.percentile(t, 1))


def main_frac(f):
    mf, _lab, _cnt = R.main_frac(np.asarray(f, np.int64))
    return float(mf)


def decimate(v, f, budget=BUDGET):
    from scripts.export_viewer_bundle import decimate_quadric
    out = decimate_quadric(np.asarray(v, float), np.asarray(f, np.int64), budget)
    return (v, f) if out is None else out


def surface_move(v_new, v_old):
    d1 = cKDTree(v_old).query(v_new)[0]
    d0 = cKDTree(v_new).query(v_old)[0]
    a = np.r_[d1, d0]
    return dict(median_mm=round(float(np.median(a)), 2), p95_mm=round(float(np.percentile(a, 95)), 2), max_mm=round(float(a.max()), 2))


def label_boundary_points(V, A, lab, origin):
    """atlas coordinates of the voxel centres on the surface of one label (the segmented compartment that the mesh was cut from)"""
    from engine import volume_ingest as vol
    m = V == lab
    if not m.any():
        return np.zeros((0, 3))
    sh = m & ~ndi.binary_erosion(m)
    ijk = np.argwhere(sh).astype(float)
    return vol.voxels_to_atlas(ijk, A) - np.asarray(origin, float)


def mesh_to_label_error(v, bpts):
    d = cKDTree(bpts).query(v)[0]
    return dict(median_mm=round(float(np.median(d)), 2), p95_mm=round(float(np.percentile(d, 95)), 2), max_mm=round(float(d.max()), 2))


class Evidence:
    """her registered photographs: per label, how much of it lies on her photographed muscle (her Q179 rule: mus == 2), on known non-muscle (fat, fascia, gel: mus == 1) or where the photograph is unknown"""

    def __init__(self, work):
        self.work = Path(work)

    def shares(self, D, labels):
        cnt = np.zeros((256, 3), np.int64)
        for side, (i0, i1) in R.SIDE_I.items():
            meta = json.loads((self.work / f"p1_{side}.json").read_text())
            mus = np.load(self.work / f"p1_{side}_mus.npy", mmap_mode="r")
            for t, k in enumerate(meta["ks"]):
                sub = D[i0:i1, :, k].astype(np.int64)
                m = np.asarray(mus[t]).astype(np.int64)
                sel = sub > 0
                if sel.any():
                    cnt += np.bincount(sub[sel] * 3 + m[sel], minlength=768).reshape(256, 3)
        out = {}
        for aid, l in labels.items():
            n = int(cnt[l].sum())
            out[aid] = dict(voxels=n, musc=round(float(cnt[l, 2] / max(n, 1)), 3), non_muscle=round(float(cnt[l, 1] / max(n, 1)), 3), unknown=round(float(cnt[l, 0] / max(n, 1)), 3))
        return out


# ------------------------------------------------------------------ the page state (guards are measured on the Q214 bundle with replacements swapped in)
class Page:
    def __init__(self, bundle):
        self.B = bundle
        self.ctx = F.Context(bundle)

    def pieces(self, sid):
        """context keys of the base piece and the zfill continuations of a muscle id"""
        base = [k for k in self.ctx.muscles if k.split("#")[0] == sid]
        zf = [k for k in self.ctx.muscles if re.fullmatch(re.escape(sid) + r"_zfill\w*#\d+", k)]
        return base, zf

    def overlap_state(self, replaced):
        """{group id: % of its voxels inside other muscles} for the page with `replaced` = {id: (v, f)} swapped in (Q204 lattice measure, Z-fill pieces merged)"""
        mus = dict(self.ctx.muscles)
        for sid, (v, f) in replaced.items():
            base, _zf = self.pieces(sid)
            assert len(base) == 1, (sid, base)
            mus[base[0]] = (v, f)
        shim = SimpleNamespace(all_min=self.ctx.all_min, all_max=self.ctx.all_max, muscles=mus, skin=self.ctx.skin)
        of = F.OverlapField(shim)
        out = {}
        for mid, w in of.groups.items():
            out[mid] = round(100.0 * float((of.cnt[tuple(w.T)] > 1).mean()), 1)
        return out

    def metrics(self, v, f, v_ref=None, f_ref=None):
        ctx = self.ctx
        g = {}
        ins, _cp, _dist = ctx.bone_field.inside(v)
        g["in_bone_pct"] = round(100.0 * float(ins.mean()), 1)
        bdp = ctx.bone_depth().depth(v)
        g["bone_depth_max_mm"] = round(float(bdp.max()), 1)
        g["bone_deep_pct"] = round(100.0 * float((bdp > 1.5).mean()), 1)
        sk_in, sk_d = ctx.skin_state(v)
        g["inside_skin_pct"], g["min_skin_depth_mm"] = round(sk_in, 2), round(sk_d, 1)
        g["volume_cm3"] = round(vol_cm3(v, f), 1)
        g["main_piece"] = round(main_frac(f), 4)
        if v_ref is not None:
            c, u = principal_axis(v_ref)
            g["length_mm"] = round(extent_along(v, c, u), 1)
        return g


# ------------------------------------------------------------------ the muscles
def severity_rows(B, evid_base, labels, q213):
    """worst-first order of the candidate muscle-sides: Q213 audit numbers (scale vs the male, overlap, inside bone) + her photographed-muscle share of the Q48 region"""
    rows = {}
    for aid in labels:
        a = q213.get(aid, {})
        vol = a.get("vol_cm3", {})
        vf, vm, vz = vol.get("vhf"), vol.get("vhm"), vol.get("zan_f")
        own = a.get("own_q204", {})
        sc = 0.0
        if vf and vz:
            sc += 3.0 * abs(np.log(max(vf, 1e-3) / max(vz, 1e-3)))
        sc += float(own.get("overlap_pct") or 0.0) / 20.0 + float(own.get("inside_bone_pct") or 0.0) / 10.0 + 5.0 * (1.0 - evid_base[aid]["musc"])
        rows[aid] = dict(score=round(float(sc), 2), vol_own=vf, vol_male=vm, vol_z=vz, scale_vs_male=(round(vf / vm, 2) if vf and vm else None), overlap_pct_q213=own.get("overlap_pct"),
                         inside_bone_pct_q213=own.get("inside_bone_pct"), musc_share_base=evid_base[aid]["musc"])
    return rows


def evaluate(page, aid, v1, f1, v0, f0, bpts, ev_base, ev_new, zref, zfill_meshes):
    """individual guards of one candidate (the overlap guard is the final-state check)"""
    g1 = page.metrics(v1, f1, v0)
    g0 = page.metrics(v0, f0, v0)
    why = []
    g = dict(before=g0, after=g1)
    g["volume_ratio"] = round(g1["volume_cm3"] / max(g0["volume_cm3"], 1e-6), 3)
    g["length_ratio"] = round(g1["length_mm"] / max(g0["length_mm"], 1e-6), 3)
    g["move"] = surface_move(v1, v0)
    g["fit_error_vs_label"] = mesh_to_label_error(v1, bpts)
    g["musc_share"] = [ev_base["musc"], ev_new["musc"]]
    g["non_muscle_share"] = [ev_base["non_muscle"], ev_new["non_muscle"]]
    g["z_ref_cm3"] = zref
    if zref:
        g["volume_vs_z"] = round(g1["volume_cm3"] / zref, 2)
    if g1["inside_skin_pct"] < 100.0 or g1["min_skin_depth_mm"] < SKIN_DEPTH_MIN_MM:
        why.append(f"skin: {g1['inside_skin_pct']} % inside, closest {g1['min_skin_depth_mm']} mm")
    if g1["in_bone_pct"] > IN_BONE_MAX_PCT:
        why.append(f"{g1['in_bone_pct']} % of the vertices inside her bone (gate {IN_BONE_MAX_PCT:g})")
    if g1["bone_depth_max_mm"] > BONE_DEPTH_MAX_MM:
        why.append(f"embedded {g1['bone_depth_max_mm']} mm in bone (gate {BONE_DEPTH_MAX_MM:g})")
    if ev_new["musc"] < MUSC_SHARE_MIN:
        why.append(f"only {ev_new['musc']} of it lies on her photographed muscle (gate {MUSC_SHARE_MIN})")
    elif ev_new["musc"] < ev_base["musc"]:
        why.append(f"photographed-muscle share fell {ev_base['musc']} -> {ev_new['musc']}")
    if not (VOL_LO <= g["volume_ratio"] <= VOL_HI):
        why.append(f"volume x{g['volume_ratio']} of the old mesh ({g0['volume_cm3']} -> {g1['volume_cm3']} cm3; gate {VOL_LO}-{VOL_HI})")
    if g["length_ratio"] < LEN_LO:
        why.append(f"length x{g['length_ratio']} of the old mesh (gate >= {LEN_LO})")
    if g1["main_piece"] < min(MAIN_PIECE_MIN, g0["main_piece"]) - 1e-9:
        why.append(f"main piece {g1['main_piece']} < {min(MAIN_PIECE_MIN, g0['main_piece'])}")
    if g["move"]["p95_mm"] > MOVE_P95_MAX_MM:
        why.append(f"surface move p95 {g['move']['p95_mm']} mm (gate {MOVE_P95_MAX_MM:g})")
    if zref and not (Z_GATE_LO <= g["volume_vs_z"] <= Z_GATE_HI):
        why.append(f"volume {g1['volume_cm3']} cm3 is x{g['volume_vs_z']} of the Z-Anatomy female reference ({zref} cm3; gate {Z_GATE_LO}-{Z_GATE_HI})")
    if zfill_meshes:
        zv = np.vstack([m[0] for m in zfill_meshes])
        old_tree = cKDTree(v0)
        seam = zv[old_tree.query(zv)[0] < 0.6]               # the vertices of the continuation that sit on the old mesh's end face
        if len(seam):
            d = cKDTree(v1).query(seam)[0]
            g["seam_gap_mm"] = dict(vertices=int(len(seam)), median=round(float(np.median(d)), 2), p95=round(float(np.percentile(d, 95)), 2))
            if g["seam_gap_mm"]["p95"] > SEAM_MAX_MM:
                why.append(f"the Z-fill continuation welded to the old mesh would be {g['seam_gap_mm']['p95']} mm off the new mesh at the seam (gate {SEAM_MAX_MM:g})")
    return g, why


def run_rounds(work, crops, page, targets, only, log=print):
    """refit + guards, auto-hold loop -> (label volume, accepted {id: dict(v, f, guards, bpts, ...)}, failed {id: [reasons]}, rounds)"""
    ids = R.label_ids()
    base_img = nib.load(str(R.Q48_VOL))
    A = base_img.affine
    D0 = np.asarray(base_img.dataobj)
    evd = Evidence(work)
    ev_base = evd.shares(D0, {a: ids[a] for a in targets})
    rules = R.q152_rules()
    q213 = json.loads((REPO / "data/derived/Q213_target_muscle_audit.json").read_text())
    zmeshes = load_z()
    hold_targets, failed, rounds = set(), {}, []
    sev = severity_rows(page.B, ev_base, targets, q213)
    for rnd in range(MAX_ROUNDS):
        want = [a for a in targets if a not in hold_targets and (not only or a in only)]
        hold = sorted((set(ids) - set(want)) | hold_targets)
        t0 = time.time()
        out, lv, before, after, changed, img, full = RF.refit(work, crops, hold, "her")
        log(f"round {rnd}: refit {time.time() - t0:.0f} s, targets in play {len(want)}")
        ev_new = evd.shares(out, {a: ids[a] for a in want})
        cand, fails_now = {}, {}
        for aid in want:
            t1 = time.time()
            r = R.label_mesh(out, A, ids[aid], aid, R.ORIGIN, rules)
            if r is None:
                fails_now[aid] = ["empty label"]
                continue
            v, f, smooth, note = r
            v, f = decimate(v, f)
            v, f = np.asarray(v, float), np.asarray(f, np.int64)
            it = page.B.items[page.B.find(aid)[0]]
            v0, f0 = page.B.mesh(it)
            base_k, zf_k = page.pieces(aid)
            zfm = [page.ctx.muscles[k] for k in zf_k]
            bpts = label_boundary_points(out, A, ids[aid], R.ORIGIN)
            zv = zmeshes.get(aid)
            zref = round(vol_cm3(zv["v"], zv["f"]), 1) if zv is not None else None
            g, why = evaluate(page, aid, v, f, v0, f0, bpts, ev_base[aid], ev_new[aid], zref, zfm)
            cand[aid] = dict(v=v, f=f, guards=g, smooth=smooth, notes=note, why=why, voxels=[before[aid], after[aid]])
            if why:
                fails_now[aid] = why
            log(f"   {aid:26s} vol {g['before']['volume_cm3']:6.1f} -> {g['after']['volume_cm3']:6.1f}  musc {ev_base[aid]['musc']:.2f} -> {ev_new[aid]['musc']:.2f}  bone {g['after']['in_bone_pct']:4.1f}% "
                f"len x{g['length_ratio']}  move p95 {g['move']['p95_mm']}  {'FAIL ' + '; '.join(why) if why else 'ok'}  [{time.time() - t1:.0f}s]")
        # final-state overlap with every passing candidate swapped in
        ok = {a: c for a, c in cand.items() if a not in fails_now}
        t2 = time.time()
        ov_before = page.overlap_state({})
        ov_after = page.overlap_state({a: (c["v"], c["f"]) for a, c in ok.items()})
        log(f"   overlap state {time.time() - t2:.0f} s")
        for a, c in ok.items():
            c["guards"]["overlap_vol_pct"] = [ov_before.get(a), ov_after.get(a)]
            if ov_after.get(a, 0.0) > OVERLAP_MAX:
                fails_now[a] = [f"{ov_after[a]} % of its volume inside the other muscles (gate {OVERLAP_MAX:g}; old mesh {ov_before.get(a)} %)"]
        rounds.append(dict(round=rnd, held_in=sorted(hold_targets), failed={a: w for a, w in fails_now.items()}))
        new_fail = [a for a in fails_now if a not in hold_targets]
        if not new_fail:
            accepted = {a: c for a, c in cand.items() if a not in fails_now}
            for a, c in accepted.items():
                c["ev"] = [ev_base[a], ev_new[a]]
                c["neighbour_overlap"] = {m: [ov_before.get(m), ov_after.get(m)] for m in ov_after if ov_before.get(m) is not None and abs(ov_after[m] - ov_before[m]) >= 1.0 and m != a}
            for a in want:
                if a in fails_now:
                    failed[a] = fails_now[a]
            return out, accepted, failed, rounds, sev, ev_base, ov_before, ov_after, A
        for a in new_fail:
            failed[a] = fails_now[a]
            hold_targets.add(a)
        log(f"   held after round {rnd}: {new_fail}")
    raise RuntimeError("did not settle")


def badge(name, aid, c, sev_row):
    g = c["guards"]
    b0, b1 = g["before"], g["after"]
    ev0, ev1 = c["ev"]
    fe = g["fit_error_vs_label"]
    mv = g["move"]
    ov = g.get("overlap_vol_pct", [None, None])
    sc = (f" (the male's {name.lower()} is {sev_row['vol_male']} cm3: x{sev_row['scale_vs_male']})" if sev_row.get("vol_male") else "")
    z = (f" The Z-Anatomy female reference muscle is {g['z_ref_cm3']} cm3 (x{g['volume_vs_z']}; shown for scale only, not used as geometry)." if g.get("z_ref_cm3") else "")
    seam = (f" Seam to its Z-fill continuation piece: p95 {g['seam_gap_mm']['p95']} mm." if g.get("seam_gap_mm") else "")
    return (f"TRANSFERRED, re-bounded on her own evidence (Q215): the muscle SET is still the male's (Q48: his muscle carried onto her bones), so the Source class stays transferred -- but where this muscle "
            f"lies and where it ends are hers. The Q48 boundaries had been drawn on her photographs in a frame that sits 2-14 mm off her CT bones; Q215 redoes the Q48 marker watershed in the frame in which her 1 mm "
            f"colour cryosections are registered to her CT femur (Q179): region = her photographed muscle (colour rule validated on her traced outlines), borders = her intermuscular septa, her bones and her own CT / "
            f"pelvic-floor muscles are never part of it. Volume {b1['volume_cm3']} cm3 (previous mesh {b0['volume_cm3']} cm3){sc}. Fit error: mesh to its segmented compartment median {fe['median_mm']} mm, p95 {fe['p95_mm']} mm, "
            f"max {fe['max_mm']} mm; share of the muscle lying on her photographed muscle {ev0['musc']} -> {ev1['musc']} (on photographed fat / fascia {ev0['non_muscle']} -> {ev1['non_muscle']}); moved from the previous mesh "
            f"median {mv['median_mm']} mm, p95 {mv['p95_mm']} mm. Guards passed: inside her skin (>= {SKIN_DEPTH_MIN_MM:g} mm), {b1['in_bone_pct']} % of the vertices in her bone mesh (was {b0['in_bone_pct']} %), volume x{g['volume_ratio']}, "
            f"length x{g['length_ratio']}, {ov[1]} % of its volume inside her other muscles (was {ov[0]} %; gate {OVERLAP_MAX:g}).{z}{seam} The muscle's identity inside her thigh is not measured: the watershed was seeded with "
            f"the male's muscle set. A position and boundary estimate, not a segmentation.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True); ap.add_argument("--crops", required=True)
    ap.add_argument("--src", default=str(SRC_BUNDLE)); ap.add_argument("--out", default=str(OUT_BUNDLE))
    ap.add_argument("--report", default=str(REPO / "data/derived/Q215_report.json"))
    ap.add_argument("--only", default=""); ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    B = Bundle(a.src)
    n0 = len(B.items)
    page = Page(B)
    targets = RF.target_ids()
    only = [x for x in a.only.split(",") if x]
    t0 = time.time()
    out, accepted, failed, rounds, sev, ev_base, ov_before, ov_after, A = run_rounds(a.work, a.crops, page, targets, only)
    rep = dict(source_bundle=str(Path(a.src).relative_to(REPO)), targets=targets, rounds=rounds, severity=sev, replaced={}, kept={}, piriformis={},
               params=dict(SKIN_DEPTH_MIN_MM=SKIN_DEPTH_MIN_MM, IN_BONE_MAX_PCT=IN_BONE_MAX_PCT, BONE_DEPTH_MAX_MM=BONE_DEPTH_MAX_MM, MUSC_SHARE_MIN=MUSC_SHARE_MIN, VOL=[VOL_LO, VOL_HI], LEN_LO=LEN_LO,
                           OVERLAP_MAX=OVERLAP_MAX, MAIN_PIECE_MIN=MAIN_PIECE_MIN, MOVE_P95_MAX_MM=MOVE_P95_MAX_MM, SEAM_MAX_MM=SEAM_MAX_MM, Z_GATE=[Z_GATE_LO, Z_GATE_HI], BUDGET=BUDGET))
    order = sorted(accepted, key=lambda x: -sev[x]["score"])
    for aid in order:
        c = accepted[aid]
        it = B.items[B.find(aid)[0]]
        name = it["e"]["rec"].get("name", aid)
        bd = badge(name, aid, c, sev[aid])
        rep["replaced"][aid] = dict(severity=sev[aid], guards=c["guards"], neighbour_overlap=c["neighbour_overlap"], notes=c["notes"], voxels_before_after=c["voxels"], badge=bd,
                                    subject_before=it["e"]["subject"])
        if not a.dry:
            B.replace(aid, c["v"], c["f"], rec_updates={"procedural_badge": bd}, subject=SUBJECT)
    for aid in failed:
        rep["kept"][aid] = dict(severity=sev[aid], why_not=failed[aid])
    rep["piriformis"] = dict(piriformis_r="not in the Q48 septa volume (xfer_vhm2vhf, never refined to her septa) and above the photographed window: left as is",
                             piriformis_l="same")
    if not a.dry:
        subs = B.j["subject"].split("+")
        base_att = B.j["attribution"][subs.index("xfer_vhm2vhf_sep")] if "xfer_vhm2vhf_sep" in subs else ""
        n = B.write(a.out, new_subject_attribution={SUBJECT: ATTRIBUTION})
        print(f"wrote {a.out}: {n} bytes, {len(B.items)} entries (was {n0})")
    Path(a.report).write_text(json.dumps(rep, indent=1, default=str) + "\n")
    print(f"replaced {len(rep['replaced'])}, kept {len(rep['kept'])} [{time.time() - t0:.0f} s]")


if __name__ == "__main__":
    main()
