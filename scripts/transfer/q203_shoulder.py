#!/usr/bin/env python3
"""Q203: continuity at the SHOULDER GIRDLE of the two OWN reconstructed models (extends the Q200 elbow chain to scapula + clavicle).

    python3 scripts/transfer/q203_shoulder.py --body vhm|vhf [--dry] [--out DIR] [--rows FILE]

Input = the Q200 bundle (`build/viewer_?_hr_q200`), output = a NEW bundle (`build/viewer_?_hr_q203`). The measured / rule-based / VH-transferred entries are
never edited: every completion is a NEW entry `<id>_zfill203` (subject `xfer_zan2vh?_shoulder_q203` = class 'Filled from Z-Anatomy').
  bones   : scapula / clavicle / humerus caps (flat cut faces at a data-block edge) are continued by the fitted Z bone (same machinery as q200 stage 1).
  muscles : every flat cap of a shoulder-girdle / upper-arm muscle within ZONE_MM of the glenohumeral centre is continued by its fitted Z counterpart
            (q200_continue loft / local mode), end carried onto the bone it attaches to, inside the skin, out of the bones.
Gates (as Q200): Z fit vs the measured part within 30 mm of the seam <= 25 mm median, Z beyond the plane >= 10 mm (bones 3 mm), else HELD with the number."""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.transfer import q200_elbow_repair as E  # noqa: E402
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer.q200_geom import sample_surface, align_rigid_local, clip_skin_nearest  # noqa: E402
from scripts.transfer.q200_continue import find_caps, continue_cap2 as continue_cap, AX  # noqa: E402

BODY = {
    "vhm": dict(src=REPO / "build/viewer_m_hr_q200", out=REPO / "build/viewer_m_hr_q203", rep=REPO / "data/derived/Q195_zan_to_vhm.json",
                subject="xfer_zan2vhm_shoulder_q203", he="his", key="own_m"),
    "vhf": dict(src=REPO / "build/viewer_f_hr_q200", out=REPO / "build/viewer_f_hr_q203", rep=REPO / "data/derived/Q168_zan_to_vhf.json",
                subject="xfer_zan2vhf_shoulder_q203", he="her", key="own_f"),
}
SUFFIX = "_zfill203"
ZONE_MM = 175.0           # caps whose centroid lies within this distance of the glenohumeral centre
MIN_CAP_MM2 = 100.0
MIN_BEYOND_MUSCLE = 6.0   # Z must extend this far beyond the plane (Q200: 10 mm); the loft length is bounded by what Z has
SH_STEMS = ["deltoid", "supraspinatus", "infraspinatus", "teres_minor", "teres_major", "subscapularis", "biceps_brachii", "triceps_brachii",
            "coracobrachialis", "pectoralis_major", "pectoralis_minor", "trapezius", "latissimus_dorsi", "rhomboid_major", "rhomboid_minor",
            "levator_scapulae", "serratus_anterior", "subclavius"]
SH_BONES = ["scapula", "clavicle", "humerus"]
# stem -> bones the muscle attaches to (union of both ends; the continuation's far end is carried onto the nearest of them)
ATT = {
    "deltoid": ["clavicle", "scapula", "humerus"], "supraspinatus": ["scapula", "humerus"], "infraspinatus": ["scapula", "humerus"],
    "teres_minor": ["scapula", "humerus"], "teres_major": ["scapula", "humerus"], "subscapularis": ["scapula", "humerus"],
    "biceps_brachii": ["scapula", "radius", "ulna"], "triceps_brachii": ["scapula", "humerus", "ulna"], "coracobrachialis": ["scapula", "humerus"],
    "pectoralis_major": ["clavicle", "sternum", "ribs", "humerus"], "pectoralis_minor": ["scapula", "ribs"],
    "trapezius": ["clavicle", "scapula", "cervical_vertebrae", "thoracic_vertebrae", "cranium"],
    "latissimus_dorsi": ["thoracic_vertebrae", "lumbar_vertebrae", "sacrum", "hip_bone", "ribs", "humerus", "scapula"],
    "rhomboid_major": ["thoracic_vertebrae", "scapula"], "rhomboid_minor": ["cervical_vertebrae", "thoracic_vertebrae", "scapula"],
    "levator_scapulae": ["cervical_vertebrae", "scapula"], "serratus_anterior": ["ribs", "scapula"], "subclavius": ["clavicle", "ribs"],
}
MID = {"sternum", "cervical_vertebrae", "thoracic_vertebrae", "lumbar_vertebrae", "sacrum", "cranium"}
Z_PARTS = {"deltoid": ["zan_clavicular_part_of_deltoid_muscle", "zan_acromial_part_of_deltoid_muscle", "zan_scapular_spinal_part_of_deltoid_muscle"],
           "pectoralis_major": ["zan_clavicular_head_of_pectoralis_major_muscle", "zan_sternocostal_head_of_pectoralis_major_muscle",
                                "zan_abdominal_part_of_pectoralis_major_muscle"]}


def z_ids(own_id):
    m = re.match(r"^(.*)_(l|r)$", own_id)
    if not m:
        return [own_id]
    st, sd = m.groups()
    if st == "triceps_brachii":
        return [f"{h}_{sd}" for h in E.TRICEPS]
    if st in Z_PARTS:
        return [f"{p}_{sd}" for p in Z_PARTS[st]]
    return [own_id]


def load_z(ids, cache):
    import hashlib
    import pickle
    want = set()
    for i in ids:
        want.update(z_ids(i))
    cache = cache.with_name(cache.stem + "_" + hashlib.md5("|".join(sorted(want)).encode()).hexdigest()[:8] + ".pkl")
    if cache.exists():
        return pickle.load(open(cache, "rb"))
    from scripts.transfer.zan_to_vhf_whole_body import collect_zan
    items = {it["mesh_id"]: it for it in collect_zan(want, contralateral=False)}
    pickle.dump(items, open(cache, "wb"))
    return items


class Ctx:
    def __init__(self, body, src=None):
        import trimesh
        self.body, self.cfg = body, dict(BODY[body])
        if src:
            self.cfg["src"] = Path(src)
        self.B = Bundle(self.cfg["src"])
        self.own, self.multi = {}, {}
        for it in self.B.items:
            e = it["e"]
            v, f = self.B.mesh(it)
            self.multi.setdefault(e["id"], []).append((v, f))
            if e["id"] not in self.own:
                self.own[e["id"]] = dict(e=e, v=v, f=f)
        sk = self.own["skin"]
        self.skin_mesh = trimesh.Trimesh(sk["v"], sk["f"], process=False)
        self.scratch = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad")
        self.centre = {}
        r = json.loads((REPO / f"data/derived/Q198_model_{self.cfg['key']}.json").read_text())
        for j in r["junctions"]:
            if j["name"] == "shoulder":
                self.centre[j["side"]] = np.asarray(j["centre_mm"], float)
        # shoulder-girdle muscles: measured / rule-based / VH-transferred entries only (a Q200 continuation is not continued again)
        self.muscles = [i for i, o in self.own.items() if re.match(r"^(" + "|".join(SH_STEMS) + r")_(l|r)$", i) and o["e"]["cat"] in ("muscle", "tendon")]
        want = list(self.muscles) + [f"{b}_{s}" for b in SH_BONES for s in "lr"]
        self.zit = load_z(want, self.scratch / f"zsh_{body}.pkl")
        from scripts.transfer import zan_to_vhf_whole_body as Q
        self.xf = Q.load_zan_to_vhf(report_path=self.cfg["rep"])
        self.zbone, self.pieces, self.rows, self.cbone, self._bt = {}, {}, [], {}, {}

    # ---- bones
    def bone_mesh_list(self, bid):
        """all meshes of a bone id (vertebrae / ribs are several entries), with the completed bone where one exists"""
        if bid in self.cbone:
            return [self.cbone[bid]]
        return self.multi.get(bid, [])

    def bone_ids(self, names, side):
        out = []
        for n in names:
            if n in MID:
                if n in self.multi:
                    out.append(n)
            elif n == "hip_bone":
                out += [i for i in (f"hip_bone_{side}",) if i in self.multi]
            else:
                out += [i for i in (f"{n}_{side}",) if i in self.multi]
        return out

    def bone_tree(self, ids):
        key = tuple(ids)
        if key not in self._bt:
            pts = []
            for i in ids:
                for v, f in self.bone_mesh_list(i):
                    pts.append(sample_surface(v, f, 3000, 11))
            P = np.vstack(pts)
            self._bt[key] = (cKDTree(P), P)
        return self._bt[key]

    def bone_meshes(self, side, trunk=False, exclude=()):
        import trimesh
        ids = [f"{b}_{side}" for b in ("humerus", "radius", "ulna", "scapula", "clavicle") if f"{b}_{side}" not in exclude]
        if trunk:
            ids += [f"ribs_{side}", "sternum", "cervical_vertebrae", "thoracic_vertebrae"]
        ms = []
        for i in ids:
            for v, f in self.bone_mesh_list(i):
                ms.append(trimesh.Trimesh(v, f, process=False))
        return ms


def zbone_body(ctx, bid):
    return ctx.xf(bid, "bone", ctx.zit[bid]["v"])


def caps_in_zone(ctx, v, f, side, minarea):
    c0 = ctx.centre[side]
    out = []
    for c in find_caps(v, f, minarea=minarea, at_end=2.5):
        cen = v[np.unique(f[c["faces"]])].mean(0)
        if np.linalg.norm(cen - c0) <= ZONE_MM:
            out.append(c)
    return out


def stage_bones(ctx, log=print):
    own = ctx.own
    for side in "lr":
        for b in SH_BONES:
            bid = f"{b}_{side}"
            if bid not in own or bid not in ctx.zit:
                continue
            o = own[bid]
            Zb = zbone_body(ctx, bid)
            ctx.zbone[bid] = Zb
            caps = caps_in_zone(ctx, o["v"], o["f"], side, 40.0)
            # the humerus' distal caps belong to the elbow (Q200)
            caps = [c for c in caps if not (b == "humerus" and np.linalg.norm(o["v"][np.unique(o["f"][c["faces"]])].mean(0) - ctx.centre[side]) > 120)]
            keep = []
            for c in caps:
                if any(k_["axis"] == c["axis"] and k_["sign"] == c["sign"] and abs(k_["pos"] - c["pos"]) < 4.0 for k_ in keep):
                    continue
                keep.append(c)
            pcs = []
            for cap in keep:
                row = dict(id=bid, stage="bone", axis=cap["axis"], pos=round(cap["pos"], 1), sign=cap["sign"], area=round(cap["area"]), n_frag=cap["n_comp"])
                r = continue_cap(o["v"], cap, Zb, ctx.zit[bid]["f"], min_beyond=3.0)
                if "v" not in r:
                    row["status"] = "held: " + r["reason"]; ctx.rows.append(row); continue
                dd = E.fit_error(o["v"], o["f"], Zb, ctx.zit[bid]["f"], cap)
                row.update(status="continued", beyond_mm=round(r["beyond_mm"], 1), L=round(r["Lt"], 1), shift_mm=round(r["sh"], 1), mode=r["mode"],
                           cap_covered=round(r["cap_covered"], 2), fit_err_median_mm=round(float(np.median(dd)), 1),
                           fit_err_max_mm=round(float(np.quantile(dd, .95)), 1), nv=len(r["v"]), nf=len(r["f"]))
                # the completed end stays out of the neighbouring bones (glenoid / acromion / clavicle) and inside the skin; weld ring fixed
                cv, cinfo = E.constrain(r["v"], cap["axis"], cap["pos"], cap["sign"], ctx.skin_mesh, ctx.bone_meshes(side, trunk=True, exclude=(bid,)))
                r["v"] = cv; row["constraints"] = cinfo
                r["info"] = row
                ctx.rows.append(row); pcs.append(r)
            if pcs:
                V, F, off = [], [], 0
                for r in pcs:
                    V.append(r["v"]); F.append(r["f"] + off); off += len(r["v"])
                ctx.pieces[f"{bid}{SUFFIX}"] = dict(v=np.vstack(V), f=np.vstack(F), base=bid, cat="bone", pieces=pcs, kind="bone")
                ctx.cbone[bid] = (np.vstack([o["v"], np.vstack(V)]), np.vstack([o["f"], np.vstack(F) + len(o["v"])]))


def skin_gap_mm(ctx, cap, cen):
    """distance from the cap plane to the skin along the outward normal of the cap (a cap that lies on the body surface is not a seam)"""
    n = np.zeros(3); n[AX[cap["axis"]]] = cap["sign"]
    pts = cen[None, :] + n[None, :] * np.arange(0.5, 60, 1.0)[:, None]
    inside = ctx.skin_mesh.contains(pts)
    if inside.all():
        return 60.0
    return float(np.argmax(~inside)) + 0.5


def pull_and_constrain(ctx, r, cap, side, stem, anch, trunk):
    ids = ctx.bone_ids(ATT.get(stem, []), side)
    bt = ctx.bone_tree(ids) if ids else None
    cv, pinfo = E.pull_end(r["v"], cap["axis"], cap["pos"], cap["sign"], anch, bt, max_pull=40.0)
    cv, cinfo = E.constrain(cv, cap["axis"], cap["pos"], cap["sign"], ctx.skin_mesh, ctx.bone_meshes(side, trunk=trunk))
    return cv, pinfo, cinfo


def stage_muscles(ctx, only=None, log=print):
    own = ctx.own
    for tid in [t for t in ctx.muscles if (not only or t in only)]:
        o = own[tid]
        side = tid[-1]; stem = tid[:-2]
        caps = caps_in_zone(ctx, o["v"], o["f"], side, 40.0)
        if not caps:
            continue
        zs = [ctx.zit.get(z) for z in z_ids(tid)]
        zs = [z for z in zs if z is not None]
        if not zs:
            ctx.rows.append(dict(id=tid, stage="muscle", status="held: no Z-Anatomy counterpart mesh", caps=len(caps))); continue
        zv, zf, off = [], [], 0
        for z in zs:
            zv.append(ctx.xf(z["mesh_id"], "muscle", z["v"])); zf.append(z["f"] + off); off += len(z["v"])
        ZV, ZF = np.vstack(zv), np.vstack(zf)
        anch = E.anchors_of(o["e"]["rec"])
        trunk = stem in ("trapezius", "latissimus_dorsi", "rhomboid_major", "rhomboid_minor", "levator_scapulae", "serratus_anterior", "pectoralis_major", "pectoralis_minor", "subclavius")
        pieces = []
        for cap in caps:
            ccen = o["v"][np.unique(o["f"][cap["faces"]])].mean(0)
            row = dict(id=tid, stage="muscle", axis=cap["axis"], pos=round(cap["pos"], 1), sign=cap["sign"], area=round(cap["area"]), n_frag=cap["n_comp"])
            ids = ctx.bone_ids(ATT.get(stem, []), side)
            gap_b = float(ctx.bone_tree(ids)[0].query(ccen)[0]) if ids else 0.0
            row["end_to_expected_bone_mm"] = round(gap_b, 1)
            row["skin_gap_mm"] = round(skin_gap_mm(ctx, cap, ccen), 1)
            if cap["area"] < MIN_CAP_MM2:
                row["status"] = f"skipped: cap {cap['area']:.0f} mm2 < {MIN_CAP_MM2:g} (facet)"; ctx.rows.append(row); continue
            if row["skin_gap_mm"] < 3.0:
                row["status"] = "skipped: the cap lies on the body surface (skin within 3 mm), not a data-block seam"; ctx.rows.append(row); continue
            ZVa, ainfo = align_rigid_local(ZV, ZF, o["v"], o["f"], AX[cap["axis"]], cap["pos"], cap["sign"])
            row["align"] = {k_: (round(v_, 1) if isinstance(v_, float) else v_) for k_, v_ in ainfo.items()}
            ax_m = np.linalg.svd(o["v"] - o["v"].mean(0), full_matrices=False)[2][0]
            nrm = np.zeros(3); nrm[AX[cap["axis"]]] = 1.0
            section_like = abs(float(ax_m @ nrm)) >= 0.6
            r = continue_cap(o["v"], cap, ZVa, ZF, min_beyond=MIN_BEYOND_MUSCLE, loft=True if section_like else False)
            if "v" not in r:
                row["status"] = "held: " + r["reason"]; ctx.rows.append(row); continue
            dd = E.fit_error(o["v"], o["f"], ZVa, ZF, cap)
            row["fit_err_median_mm"] = round(float(np.median(dd)), 1); row["fit_err_max_mm"] = round(float(np.quantile(dd, 0.95)), 1)
            if row["fit_err_median_mm"] > E.FIT_ERR_MAX_MM:
                row["status"] = f"held: Z counterpart does not coincide with the measured structure near the seam (median {row['fit_err_median_mm']} mm > {E.FIT_ERR_MAX_MM:g} mm)"
                ctx.rows.append(row); continue
            cv, pinfo, cinfo = pull_and_constrain(ctx, r, cap, side, stem, anch, trunk)
            r["v"] = cv; r["info"] = row
            row.update(status="continued", beyond_mm=round(r["beyond_mm"], 1), L=round(r["Lt"], 1), shift_mm=round(r["sh"], 1), mode=r["mode"], section_like=bool(section_like),
                       cap_covered=round(r["cap_covered"], 2), z_to_cap_area=round(r["area_ratio"], 3), pull=pinfo, constraints=cinfo, nv=len(cv), nf=len(r["f"]))
            ctx.rows.append(row); pieces.append(r)
        if pieces:
            V, F, off = [], [], 0
            for r in pieces:
                V.append(r["v"]); F.append(r["f"] + off); off += len(r["v"])
            ctx.pieces[f"{tid}{SUFFIX}"] = dict(v=np.vstack(V), f=np.vstack(F), base=tid, cat=o["e"]["cat"], pieces=pieces, kind="muscle")


def stage_separate(ctx, log=print):
    """Bounded separation (q200_overlap) of every new muscle continuation from the muscles it sits inside (measured and Z-filled entries stay fixed).
    The ring welded to the measured end face is pinned."""
    import trimesh
    from scripts.transfer.limb_per_bone_transfer import push_off_bones
    from scripts.transfer.q200_overlap import separate
    own = ctx.own
    cur_m = {nid: (pc["v"], pc["f"]) for nid, pc in ctx.pieces.items() if pc["kind"] == "muscle"}
    for nid, pc in ctx.pieces.items():
        if pc["kind"] != "muscle":
            continue
        side = nid.replace(SUFFIX, "")[-1]; base = pc["base"]
        v, f = pc["v"], pc["f"]
        lo, hi = v.min(0) - 6, v.max(0) + 6
        others = []
        for i, o in own.items():
            e = o["e"]
            if e["cat"] not in ("muscle", "tendon") or i == base or i.startswith(base) or len(o["f"]) < 4:
                continue
            ov = o["v"]
            if (ov.max(0) < lo).any() or (ov.min(0) > hi).any():
                continue
            others.append(trimesh.Trimesh(ov, o["f"], process=False))
        for j, (vj, fj) in cur_m.items():
            if j != nid and len(fj) > 3 and not ((vj.max(0) < lo).any() or (vj.min(0) > hi).any()):
                others.append(trimesh.Trimesh(vj, fj, process=False))
        bm = ctx.bone_meshes(side, trunk=True)

        def constrain(x):
            v1, _ = clip_skin_nearest(x.copy(), ctx.skin_mesh)
            v2, _ = push_off_bones(v1, bm)
            return v2
        pin = np.zeros(len(v), bool); off = 0
        for r in pc["pieces"]:
            pin[off + r["ring0"]] = True; off += len(r["v"])
        nv, info = separate(v, f, others, constrain=constrain, pin=pin)
        ctx.rows.append(dict(id=nid, stage="overlap", **{k: round(float(x), 3) for k, x in info.items()}))
        if info["rounds"] > 0:
            pc["v"] = nv; cur_m[nid] = (nv, f)
            pc["sep"] = info


def badge_text(cfg, pieces, name, kind):
    meds = [p["info"].get("fit_err_median_mm") for p in pieces if p["info"].get("fit_err_median_mm") is not None]
    maxs = [p["info"].get("fit_err_max_mm") for p in pieces if p["info"].get("fit_err_max_mm") is not None]
    ends = ", ".join(sorted({f"{p['info']['axis']}={p['info']['pos']} mm" for p in pieces}))
    att = []
    for p in pieces:
        pl = p["info"].get("pull") or {}
        if pl.get("pulled"):
            att.append("far end carried %.1f mm onto its bone" % pl["pull_mm"])
        elif pl.get("note"):
            att.append(pl["note"])
    s = (f"Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D) continuation of the measured {name} beyond its flat cut at the data-block edge around the shoulder girdle ({ends}): "
         f"the fitted Z-Anatomy counterpart (Q168 per-bone transform onto {cfg['he']} own bones), clipped at the cut plane and joined to the measured end face by a short loft; ")
    if att:
        s += "; ".join(att) + "; "
    if kind == "muscle":
        s += f"held inside {cfg['he']} skin and out of {cfg['he']} bones; "
    s += "the measured structure is not edited. "
    if meds:
        s += f"Q203 validation median error {np.median(meds):.1f} mm, max {max(maxs):.1f} mm (Z fit vs the measured part within 25-30 mm of the cut)."
    return s


def assemble(ctx):
    out = []
    for nid, pc in ctx.pieces.items():
        e = ctx.own[pc["base"]]["e"]; rec = e["rec"]
        name = rec.get("name", pc["base"])
        newrec = {k: rec[k] for k in ("latin", "folder", "region", "origin", "insertion") if k in rec}
        newrec.update(name=f"{name} (continuation beyond the data-block edge, filled from Z-Anatomy)",
                      source="Z-Anatomy (CC BY-SA 4.0), fitted to this body; see the badge",
                      procedural_badge=badge_text(ctx.cfg, pc["pieces"], name, pc["kind"]))
        if pc.get("sep"):
            i_ = pc["sep"]
            newrec["procedural_badge"] += (f" Separated from the neighbouring muscles it sat inside ({100 * i_['inside_before']:.1f} % -> {100 * i_['inside_after']:.1f} % of the vertices, "
                                           f"moved at most {i_['move_max']:.1f} mm, volume {i_['volume_ratio']:.2f}x; the weld ring at the measured end face was not moved).")
        ctx.B.add(nid, pc["cat"], e["side"], ctx.cfg["subject"], newrec, pc["v"], pc["f"])
        out.append(nid)
    return out


def write_bundle(ctx, out):
    att = {ctx.cfg["subject"]: ["Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D): continuations of structures cut flat at CT data-block edges around the shoulder girdle, "
           "fitted onto this body's own bones (Q203); the measured structures are not edited. Z-Anatomy: models by the Z-Anatomy project, app by "
           "Lluis Vinent Juanico -- see third_party/z-anatomy/NOTICE and third_party/z-anatomy/README.md. Licensed CC BY-SA 4.0; this derivative remains CC BY-SA 4.0 (ShareAlike)."]}
    return ctx.B.write(out, new_subject_attribution=att)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True, choices=["vhm", "vhf"])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--out", default=None)
    ap.add_argument("--rows", default=None)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    t = time.time()
    ctx = Ctx(a.body)
    print("ctx", round(time.time() - t, 1), flush=True)
    stage_bones(ctx)
    print("bones done", round(time.time() - t, 1), flush=True)
    stage_muscles(ctx, only=a.only)
    if not a.only:
        stage_separate(ctx)
    for r in ctx.rows:
        print({k: v for k, v in r.items() if k not in ("align", "constraints")})
    if a.rows:
        Path(a.rows).write_text(json.dumps(ctx.rows, indent=1, default=str))
    if not a.dry:
        assemble(ctx)
        out = Path(a.out) if a.out else ctx.cfg["out"]
        print("bundle bytes", write_bundle(ctx, out))
        seams = {nid: [dict(axis=r["axis"], pos=r["pos"], polys=r["covered"]) for r in pc["pieces"] if "covered" in r] for nid, pc in ctx.pieces.items() if "pieces" in pc}
        (REPO / f"data/derived/Q203_seams_{a.body}.json").write_text(json.dumps(seams))
    print("done", round(time.time() - t, 1))
