#!/usr/bin/env python3
"""Q203: continuity of the two OWN reconstructed models at the SHOULDER GIRDLE and at the remaining data-block seams (extends the Q200 elbow chain).

    python3 scripts/transfer/q203_complete.py --body vhm|vhf [--dry] [--scope shoulder|all] [--out DIR] [--rows FILE]

Input = the Q200 bundle (`build/viewer_?_hr_q200`), output = a NEW bundle (`build/viewer_?_hr_q203`). The measured / rule-based / VH-transferred entries
are never edited: every completion is a NEW entry (`<id>_zfill203` = shoulder-girdle zone, `<id>_zfill203s` = other seams) of subject
`xfer_zan2vh?_shoulder_q203` / `xfer_zan2vh?_seams_q203` (Source facet class 'Filled from Z-Anatomy').
  bones   : scapula / clavicle / humerus caps (flat cut faces at a data-block edge) continued by the fitted Z bone (q200 machinery).
  muscles : every flat cap (axis-aligned planar end face >= 100 mm2 at a structure extreme) is continued by its Z-Anatomy counterpart (q200_continue loft /
            local mode), end carried onto the bone it attaches to, inside the skin, out of the bones, separated from the neighbour muscles.
Z counterpart candidates (the best fit to the measured part within 30 mm of the cap wins; the choice is in the badge):
  (a) the Q168 / Q195 per-bone transform of the Z-Anatomy mesh onto this body's own bones (as in Q200),
  (b) the Z-Anatomy page already FITTED to this body (his: Q201 chain page, hers: Q199 chain page): the same Z-Anatomy meshes, refitted on this body's
      labels / cryosection photographs (real source, not new geometry).
Gates (as Q200): Z fit vs the measured part within 30 mm of the cap <= 25 mm median, Z beyond the plane >= 6 mm (bones 3 mm), else HELD with the number."""
from __future__ import annotations
import argparse
import json
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))

from scripts.transfer import q200_elbow_repair as E  # noqa: E402
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer.q200_geom import sample_surface, align_rigid_local, clip_skin_nearest  # noqa: E402
from scripts.transfer.q200_continue import find_caps, continue_cap2 as continue_cap, AX  # noqa: E402

SCRATCH = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad")
BODY = {
    "vhm": dict(src=REPO / "build/viewer_m_hr_q200", out=REPO / "build/viewer_m_hr_q203", rep=REPO / "data/derived/Q195_zan_to_vhm.json", he="his", key="own_m",
                page=(REPO / "build/q201", "viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "Q201 chain page (Z-Anatomy fitted to his labels and photographs)")),
    "vhf": dict(src=REPO / "build/viewer_f_hr_q200", out=REPO / "build/viewer_f_hr_q203", rep=REPO / "data/derived/Q168_zan_to_vhf.json", he="her", key="own_f",
                page=(REPO / "build/q199", "viewer_zan_female", "atlas_viewer_zan_female.html", "Q199 chain page (Z-Anatomy fitted to her labels and photographs)")),
}
SUBJECT = {("vhm", "sh"): "xfer_zan2vhm_shoulder_q203", ("vhm", "seam"): "xfer_zan2vhm_seams_q203",
           ("vhf", "sh"): "xfer_zan2vhf_shoulder_q203", ("vhf", "seam"): "xfer_zan2vhf_seams_q203"}
SUFFIX = {"sh": "_zfill203", "seam": "_zfill203s"}
ZONE_MM = 175.0           # caps whose centroid lies within this distance of the glenohumeral centre belong to the shoulder-girdle group
MIN_CAP_MM2 = 100.0
MAX_SHIFT_MM = 30.0       # in-plane move of the Z section onto the measured cap face (a larger move = the Z structure is not where the measured one is)
MIN_BEYOND_MUSCLE = 6.0   # Z must extend this far beyond the plane (Q200: 10 mm); the loft length is bounded by what Z has
SH_STEMS = ["deltoid", "supraspinatus", "infraspinatus", "teres_minor", "teres_major", "subscapularis", "biceps_brachii", "triceps_brachii",
            "coracobrachialis", "pectoralis_major", "pectoralis_minor", "trapezius", "latissimus_dorsi", "rhomboid_major", "rhomboid_minor",
            "levator_scapulae", "serratus_anterior", "subclavius"]
SH_BONES = ["scapula", "clavicle", "humerus"]
GEN_BONES = ["femur", "tibia", "fibula", "hip_bone"]       # long bones / pelvis outside the shoulder: caps continued by the same rule (group "seam")
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
    "brachialis": ["humerus", "ulna"], "brachioradialis": ["humerus", "radius"], "pronator_teres": ["humerus", "ulna", "radius"],
}
MID = {"sternum", "cervical_vertebrae", "thoracic_vertebrae", "lumbar_vertebrae", "sacrum", "cranium", "mandible", "hyoid", "coccyx"}
Z_PARTS = {"deltoid": ["zan_clavicular_part_of_deltoid_muscle", "zan_acromial_part_of_deltoid_muscle", "zan_scapular_spinal_part_of_deltoid_muscle"],
           "pectoralis_major": ["zan_clavicular_head_of_pectoralis_major_muscle", "zan_sternocostal_head_of_pectoralis_major_muscle",
                                "zan_abdominal_part_of_pectoralis_major_muscle"]}
SKIP_IDS = re.compile(r"intercostal|^skin$|fascia|bursa|capsule|retinaculum|aponeurosis|sheath|lig|disc|cartilage|membrane")


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


def load_page(body):
    """muscles / tendons / bones of the Z-Anatomy page fitted to this body (decoded from the page's own geo files, as q198_load does)"""
    d, dn, hn, _ = BODY[body]["page"]
    cache = SCRATCH / f"zpage_{body}.pkl"
    if cache.exists():
        return pickle.load(open(cache, "rb"))
    from scripts.zanatomy import q198_load as L
    L.Q = d
    L.MODELS["zpage"] = (dn, hn, "zan", "x")
    out = {}
    for s in L.load("zpage"):
        if s["sys"] in ("muscle", "tendon", "bone"):
            out[s["id"]] = dict(v=s["v"], f=s["f"], sys=s["sys"])
    pickle.dump(out, open(cache, "wb"))
    return out


class Ctx:
    def __init__(self, body, src=None, scope="all"):
        import trimesh
        self.body, self.cfg, self.scope = body, dict(BODY[body]), scope
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
        self.centre = {}
        r = json.loads((REPO / f"data/derived/Q198_model_{self.cfg['key']}.json").read_text())
        for j in r["junctions"]:
            if j["name"] == "shoulder":
                self.centre[j["side"]] = np.asarray(j["centre_mm"], float)
        self.q200cov = {}
        p = REPO / f"data/derived/Q200_seams_{body}.json"
        if p.exists():
            self.q200cov = json.loads(p.read_text())
        self.page = load_page(body)
        # candidate muscles: measured / rule-based / VH- or Z-transferred entries (never a continuation)
        pat = re.compile(r"^(" + "|".join(SH_STEMS) + r")_(l|r)$")
        self.muscles = [i for i, o in self.own.items() if o["e"]["cat"] in ("muscle", "tendon") and not re.search(r"_zfill", i) and not SKIP_IDS.search(i)
                        and (scope == "all" or pat.match(i))]
        want = list(self.muscles) + [f"{b}_{s}" for b in SH_BONES + GEN_BONES + ["radius", "ulna"] for s in "lr"]
        self.zit = load_z(want, SCRATCH / f"zc_{body}_{scope}.pkl")
        from scripts.transfer import zan_to_vhf_whole_body as Q
        self.xf = Q.load_zan_to_vhf(report_path=self.cfg["rep"])
        self.zbone, self.pieces, self.rows, self.cbone, self._bt = {}, {}, [], {}, {}
        self._allb = None

    # ---- bones
    def bone_mesh_list(self, bid):
        if bid in self.cbone:
            return [self.cbone[bid]]
        return self.multi.get(bid, [])

    def bone_ids(self, names, side):
        out = []
        for n in names:
            if n in MID:
                if n in self.multi:
                    out.append(n)
            else:
                out += [i for i in (f"{n}_{side}",) if i in self.multi]
        return out

    def all_bone_ids(self):
        return [i for i, o in self.own.items() if o["e"]["cat"] == "bone" and not i.endswith("_zfill")]

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

    def bones_near(self, lo, hi, exclude=(), pad=8.0):
        """trimesh of every bone (completed where a continuation exists) whose bounding box meets [lo-pad, hi+pad]"""
        import trimesh
        if self._allb is None:
            self._allb = [(i, v, f) for i in self.all_bone_ids() for v, f in self.bone_mesh_list(i)]
        out = []
        for i, v, f in self._allb:
            if i in exclude:
                continue
            if (v.max(0) < lo - pad).any() or (v.min(0) > hi + pad).any():
                continue
            out.append(trimesh.Trimesh(self.cbone[i][0], self.cbone[i][1], process=False) if i in self.cbone else trimesh.Trimesh(v, f, process=False))
        return out

    def refresh_bones(self):
        self._allb = None; self._bt = {}


def zbone_body(ctx, bid):
    return ctx.xf(bid, "bone", ctx.zit[bid]["v"])


def shoulder_dist(ctx, p, side):
    c = ctx.centre.get(side)
    return float(np.linalg.norm(p - c)) if c is not None else 1e9


def group_of(ctx, cen, side):
    return "sh" if shoulder_dist(ctx, cen, side) <= ZONE_MM else "seam"


def stage_bones(ctx, log=print):
    own = ctx.own
    for side in "lr":
        for b in SH_BONES + GEN_BONES:
            bid = f"{b}_{side}"
            if bid not in own or bid not in ctx.zit:
                continue
            o = own[bid]
            cands = [("Q168/Q195 per-bone transform", zbone_body(ctx, bid), ctx.zit[bid]["f"])]
            if bid in ctx.page:
                cands.append((BODY[ctx.body]["page"][3], ctx.page[bid]["v"], ctx.page[bid]["f"]))
            ctx.zbone[bid] = cands[0][1]
            caps = []
            for c in find_caps(o["v"], o["f"], minarea=40.0, at_end=2.5):
                cen = o["v"][np.unique(o["f"][c["faces"]])].mean(0)
                if b in SH_BONES and (shoulder_dist(ctx, cen, side) > ZONE_MM or (b == "humerus" and shoulder_dist(ctx, cen, side) > 120)):
                    continue
                if any(k_["axis"] == c["axis"] and k_["sign"] == c["sign"] and abs(k_["pos"] - c["pos"]) < 4.0 for k_ in caps):
                    continue
                caps.append(c)
            pcs = {"sh": [], "seam": []}
            for cap in caps:
                cen = o["v"][np.unique(o["f"][cap["faces"]])].mean(0)
                grp = group_of(ctx, cen, side)
                row = dict(id=bid, stage="bone", group=grp, axis=cap["axis"], pos=round(cap["pos"], 1), sign=cap["sign"], area=round(cap["area"]), n_frag=cap["n_comp"])
                best = None
                for cname, zv, zf in cands:
                    r = continue_cap(o["v"], cap, zv, zf, min_beyond=3.0)
                    if "v" not in r:
                        row.setdefault("tried", []).append(f"{cname[:12]}: {r['reason'][:60]}"); continue
                    if r["sh"] > MAX_SHIFT_MM:
                        row.setdefault("tried", []).append(f"{cname[:12]}: Z section {r['sh']:.0f} mm off the cap face"); continue
                    dd = E.fit_error(o["v"], o["f"], zv, zf, cap)
                    med = float(np.median(dd))
                    if med > 8.0:
                        row.setdefault("tried", []).append(f"{cname[:12]}: fit {med:.1f} mm > 8"); continue
                    if best is None or med < best[0]:
                        best = (med, float(np.quantile(dd, .95)), r, cname)
                if best is None:
                    row["status"] = "held: " + "; ".join(row.get("tried", ["no Z counterpart"])); ctx.rows.append(row); continue
                med, p95, r, cname = best
                others = ctx.bones_near(r["v"].min(0), r["v"].max(0), exclude=(bid,))
                k_ = AX[cap["axis"]]
                far = cap["sign"] * (r["v"][:, k_] - cap["pos"]) > 1.0
                inside = np.zeros(len(r["v"]), bool)
                for m_ in others:
                    lo_, hi_ = m_.bounds
                    sel = np.where(far & np.all((r["v"] >= lo_ - 1) & (r["v"] <= hi_ + 1), axis=1))[0]
                    if len(sel):
                        inside[sel[m_.contains(r["v"][sel])]] = True
                frac_in = float(inside.sum() / max(far.sum(), 1))
                row["inside_other_bone_frac"] = round(frac_in, 2)
                if frac_in > 0.25:
                    row["status"] = f"held: the cut face lies against the neighbouring bone ({100 * frac_in:.0f} % of the Z continuation would sit inside it)"
                    ctx.rows.append(row); continue
                cv, cinfo = E.constrain(r["v"], cap["axis"], cap["pos"], cap["sign"], ctx.skin_mesh, others, ramp_mm=2.0)
                r["v"] = cv
                row.update(status="continued", z_source=cname, beyond_mm=round(r["beyond_mm"], 1), L=round(r["Lt"], 1), shift_mm=round(r["sh"], 1), mode=r["mode"],
                           cap_covered=round(r["cap_covered"], 2), fit_err_median_mm=round(med, 1), fit_err_max_mm=round(p95, 1), nv=len(r["v"]), nf=len(r["f"]), constraints=cinfo)
                r["info"] = row
                ctx.rows.append(row); pcs[grp].append(r)
            for grp, lst in pcs.items():
                if lst:
                    V, F, off = [], [], 0
                    for r in lst:
                        V.append(r["v"]); F.append(r["f"] + off); off += len(r["v"])
                    ctx.pieces[f"{bid}{SUFFIX[grp]}"] = dict(v=np.vstack(V), f=np.vstack(F), base=bid, cat="bone", pieces=lst, kind="bone", group=grp)
                    cb = ctx.cbone.get(bid, (o["v"], o["f"]))
                    ctx.cbone[bid] = (np.vstack([cb[0], np.vstack(V)]), np.vstack([cb[1], np.vstack(F) + len(cb[0])]))
    ctx.refresh_bones()


def stage_bone_ends(ctx, log=print):
    """Long-bone ENDS the data block / segmentation stopped short of (his radius / ulna distal ends, her right ulna): the part of the Z bone (candidates: per-bone
    transform, page fitted to this body) that lies beyond the measured (+ Q200) bone's end along the shaft axis is added, clipped 12 mm inside the measured end
    and closed by a planar face that lies inside the measured bone; Z beyond >= 6 mm, fit of the Z shaft to the measured shaft within 40 mm of the end <= 5 mm (median)."""
    import trimesh
    own = ctx.own
    for side in "lr":
        for b in ("radius", "ulna"):
            bid = f"{b}_{side}"
            o = own.get(bid)
            if o is None or str(o["e"].get("subject", "")).startswith("xfer_zan2"):
                continue
            mv, mf = o["v"], o["f"]
            zf_ = ctx.own.get(f"{bid}_zfill")
            if zf_ is not None:
                mv = np.vstack([mv, zf_["v"]]); mf = np.vstack([mf, zf_["f"] + len(o["v"])])
            c = mv.mean(0); u = np.linalg.svd(mv - c, full_matrices=False)[2][0]
            if u[1] < 0:
                u = -u                                   # towards the elbow
            tm = (mv - c) @ u
            cands = []
            if bid in ctx.zit:
                cands.append(("Q168/Q195 per-bone transform", zbone_body(ctx, bid), ctx.zit[bid]["f"]))
            if bid in ctx.page:
                # the page fitted to this body carries the axial position from both ends; the per-bone transform of a truncated bone can slide along its shaft
                cands = [(BODY[ctx.body]["page"][3], ctx.page[bid]["v"], ctx.page[bid]["f"])]
            for end, sgn in (("distal", -1), ("proximal", 1)):
                row = dict(id=bid, stage="bone_end", end=end)
                tend = tm.max() if sgn > 0 else tm.min()
                best = None
                for cname, zv, zf in cands:
                    tz = (zv - c) @ u
                    beyond = sgn * (tz.max() if sgn > 0 else tz.min()) - sgn * tend
                    if beyond < 6.0:
                        row.setdefault("tried", []).append(f"{cname[:12]}: Z ends {beyond:.1f} mm beyond"); continue
                    win = mv[(sgn * (tm - tend) > -40) ]
                    zs = sample_surface(zv, zf, 6000, 3)
                    d = cKDTree(zs).query(win)[0]
                    med = float(np.median(d))
                    if med > 5.0:
                        row.setdefault("tried", []).append(f"{cname[:12]}: shaft fit {med:.1f} mm > 5"); continue
                    if best is None or med < best[0]:
                        best = (med, float(np.quantile(d, .95)), zv, zf, cname, beyond)
                if best is None:
                    row["status"] = "held: " + "; ".join(row.get("tried", ["no Z bone"])); ctx.rows.append(row); continue
                med, p95, zv, zf, cname, beyond = best
                pl = c + u * (tend - sgn * 12.0)
                m = trimesh.Trimesh(zv, zf, process=False)
                try:
                    r = trimesh.intersections.slice_mesh_plane(m, -sgn * u, pl, cap=True)
                except Exception as ex:  # noqa: BLE001
                    row["status"] = f"held: clip failed ({ex})"; ctx.rows.append(row); continue
                pv, pf = np.asarray(r.vertices, float), np.asarray(r.faces, np.int64)
                if len(pf) < 20:
                    row["status"] = "held: clip left too little"; ctx.rows.append(row); continue
                others = ctx.bones_near(pv.min(0), pv.max(0), exclude=(bid,))
                far = sgn * ((pv - c) @ u - tend) > -1.0
                inside = np.zeros(len(pv), bool)
                for m_ in others:
                    lo_, hi_ = m_.bounds
                    sel = np.where(far & np.all((pv >= lo_ - 1) & (pv <= hi_ + 1), axis=1))[0]
                    if len(sel):
                        inside[sel[m_.contains(pv[sel])]] = True
                frac_in = float(inside.sum() / max(far.sum(), 1))
                row["inside_other_bone_frac"] = round(frac_in, 2)
                if frac_in > 0.35:
                    row["status"] = f"held: {100 * frac_in:.0f} % of the Z end would sit inside the neighbouring (carpal / humeral) bones"; ctx.rows.append(row); continue
                # keep out of the other bones beyond the overlap zone only (weight ramps from the closing plane)
                from scripts.transfer.limb_per_bone_transfer import push_off_bones
                w = np.clip(sgn * ((pv - c) @ u - tend) / 6.0 + 2.0, 0, 1)[:, None]
                v1, nsk = clip_skin_nearest(pv.copy(), ctx.skin_mesh)
                v2, nb = push_off_bones(v1, others)
                pv2 = pv + w * (v2 - pv)
                row.update(status="continued", z_source=cname, beyond_mm=round(beyond, 1), fit_err_median_mm=round(med, 1), fit_err_max_mm=round(p95, 1),
                           nv=len(pv2), nf=len(pf), constraints=dict(skin_clipped=int(nsk), bone_pushed=int(nb)))
                ctx.rows.append(row)
                piece = dict(v=pv2, f=pf, info=row, ring0=np.zeros(0, int), covered=[])
                key = f"{bid}{SUFFIX['seam']}"
                if key in ctx.pieces:
                    pc = ctx.pieces[key]; off = len(pc["v"])
                    pc["v"] = np.vstack([pc["v"], pv2]); pc["f"] = np.vstack([pc["f"], pf + off]); pc["pieces"].append(piece)
                else:
                    ctx.pieces[key] = dict(v=pv2, f=pf, base=bid, cat="bone", pieces=[piece], kind="bone", group="seam")
                cb = ctx.cbone.get(bid, (o["v"], o["f"]))
                ctx.cbone[bid] = (np.vstack([cb[0], pv2]), np.vstack([cb[1], pf + len(cb[0])]))
    ctx.refresh_bones()


def skin_gap_mm(ctx, cap, cen):
    """distance from the cap plane to the skin along the outward normal of the cap (a cap that lies on the body surface is not a seam)"""
    n = np.zeros(3); n[AX[cap["axis"]]] = cap["sign"]
    pts = cen[None, :] + n[None, :] * np.arange(0.5, 60, 1.0)[:, None]
    inside = ctx.skin_mesh.contains(pts)
    if inside.all():
        return 60.0
    return float(np.argmax(~inside)) + 0.5


def q200_covered_frac(ctx, tid, cap):
    """fraction of the cap already covered by a Q200 continuation of this structure (same plane)"""
    from shapely.ops import unary_union
    from shapely.geometry import Polygon
    ent = ctx.q200cov.get(f"{tid}_zfill", [])
    kk = [i for i in range(3) if i != AX[cap["axis"]]]
    polys = [Polygon(p).buffer(0.2) for e in ent if e["axis"] == cap["axis"] and abs(e["pos"] - cap["pos"]) < 1.5 for p in e["polys"] if len(p) >= 3]
    if not polys:
        return 0.0
    capA = unary_union(cap["polys"])
    return float(unary_union(polys).intersection(capA).area / max(capA.area, 1e-9))


def candidates(ctx, tid):
    out = []
    zs = [ctx.zit.get(z) for z in z_ids(tid)]
    zs = [z for z in zs if z is not None]
    if zs:
        zv, zf, off = [], [], 0
        for z in zs:
            zv.append(ctx.xf(z["mesh_id"], "muscle", z["v"])); zf.append(z["f"] + off); off += len(z["v"])
        out.append(("Q168/Q195 per-bone transform", np.vstack(zv), np.vstack(zf)))
    ps = [ctx.page.get(z) for z in z_ids(tid)]
    if ps and all(p is not None for p in ps):
        zv, zf, off = [], [], 0
        for p in ps:
            zv.append(p["v"]); zf.append(p["f"] + off); off += len(p["v"])
        out.append((BODY[ctx.body]["page"][3], np.vstack(zv), np.vstack(zf)))
    return out


def stage_muscles(ctx, only=None, log=print):
    own = ctx.own
    allb_tree = None
    for tid in [t for t in ctx.muscles if (not only or t in only)]:
        o = own[tid]
        m_ = re.match(r"^(.*)_(l|r)$", tid)
        stem, side = (m_.group(1), m_.group(2)) if m_ else (tid, "m")
        caps = [c for c in find_caps(o["v"], o["f"], minarea=40.0, at_end=2.0)]
        if not caps:
            continue
        cands = candidates(ctx, tid)
        anch = E.anchors_of(o["e"]["rec"])
        pieces = {"sh": [], "seam": []}
        ids = ctx.bone_ids(ATT[stem], side) if stem in ATT else []
        for cap in caps:
            ccen = o["v"][np.unique(o["f"][cap["faces"]])].mean(0)
            grp = group_of(ctx, ccen, side)
            row = dict(id=tid, stage="muscle", group=grp, axis=cap["axis"], pos=round(cap["pos"], 1), sign=cap["sign"], area=round(cap["area"]), n_frag=cap["n_comp"])
            if cap["area"] < MIN_CAP_MM2:
                row["status"] = f"skipped: cap {cap['area']:.0f} mm2 < {MIN_CAP_MM2:g} (facet)"; ctx.rows.append(row); continue
            cov = q200_covered_frac(ctx, tid, cap)
            if cov >= 0.5:
                row["status"] = f"skipped: {100 * cov:.0f} % of the cap already continued in Q200"; ctx.rows.append(row); continue
            row["skin_gap_mm"] = round(skin_gap_mm(ctx, cap, ccen), 1)
            if row["skin_gap_mm"] < 3.0:
                row["status"] = "skipped: the cap lies on the body surface (skin within 3 mm), not a data-block seam"; ctx.rows.append(row); continue
            if not cands:
                row["status"] = "held: no Z-Anatomy counterpart mesh"; ctx.rows.append(row); continue
            bt = ctx.bone_tree(ids) if ids else None
            if bt is None:
                if allb_tree is None:
                    allb_tree = ctx.bone_tree(ctx.all_bone_ids())
                bt = allb_tree
            row["end_to_nearest_bone_mm"] = round(float(bt[0].query(ccen)[0]), 1)
            ax_m = np.linalg.svd(o["v"] - o["v"].mean(0), full_matrices=False)[2][0]
            nrm = np.zeros(3); nrm[AX[cap["axis"]]] = 1.0
            section_like = abs(float(ax_m @ nrm)) >= 0.6
            best = None
            tried = []
            for cname, ZV, ZF in cands:
                ZVa, ainfo = align_rigid_local(ZV, ZF, o["v"], o["f"], AX[cap["axis"]], cap["pos"], cap["sign"])
                r = continue_cap(o["v"], cap, ZVa, ZF, min_beyond=MIN_BEYOND_MUSCLE, loft=True if section_like else False)
                if "v" not in r:
                    tried.append(f"{cname[:14]}: {r['reason'][:70]}"); continue
                if r["sh"] > MAX_SHIFT_MM:
                    tried.append(f"{cname[:14]}: Z section {r['sh']:.0f} mm off the cap face > {MAX_SHIFT_MM:g}"); continue
                dd = E.fit_error(o["v"], o["f"], ZVa, ZF, cap)
                med = float(np.median(dd))
                if med > E.FIT_ERR_MAX_MM:
                    tried.append(f"{cname[:14]}: fit median {med:.1f} mm > {E.FIT_ERR_MAX_MM:g}"); continue
                if best is None or med < best[0]:
                    best = (med, float(np.quantile(dd, .95)), r, cname, ainfo)
            if best is None:
                row["status"] = "held: " + "; ".join(tried); ctx.rows.append(row); continue
            med, p95, r, cname, ainfo = best
            pull_max = 40.0 if ids else 15.0
            cv, pinfo = E.pull_end(r["v"], cap["axis"], cap["pos"], cap["sign"], anch, bt, max_pull=pull_max)
            cv, cinfo = E.constrain(cv, cap["axis"], cap["pos"], cap["sign"], ctx.skin_mesh, ctx.bones_near(cv.min(0), cv.max(0)))
            r["v"] = cv; r["info"] = row
            row.update(status="continued", z_source=cname, fit_err_median_mm=round(med, 1), fit_err_max_mm=round(p95, 1), beyond_mm=round(r["beyond_mm"], 1), L=round(r["Lt"], 1),
                       shift_mm=round(r["sh"], 1), mode=r["mode"], section_like=bool(section_like), cap_covered=round(r["cap_covered"], 2),
                       z_to_cap_area=round(r["area_ratio"], 3), pull=pinfo, constraints=cinfo, nv=len(cv), nf=len(r["f"]),
                       align={k_: (round(v_, 1) if isinstance(v_, float) else v_) for k_, v_ in ainfo.items()})
            ctx.rows.append(row); pieces[grp].append(r)
        for grp, pcs in pieces.items():
            if pcs:
                V, F, off = [], [], 0
                for r in pcs:
                    V.append(r["v"]); F.append(r["f"] + off); off += len(r["v"])
                ctx.pieces[f"{tid}{SUFFIX[grp]}"] = dict(v=np.vstack(V), f=np.vstack(F), base=tid, cat=o["e"]["cat"], pieces=pcs, kind="muscle", group=grp)


def stage_separate(ctx, log=print):
    """Bounded separation (q200_overlap) of every new muscle continuation from the muscles it sits inside (measured and Z-filled entries stay fixed).
    The ring welded to the measured end face is pinned."""
    import trimesh
    from scripts.transfer.limb_per_bone_transfer import push_off_bones
    from scripts.transfer.q200_overlap import separate
    own = ctx.own
    cur_m = {nid: (pc["v"], pc["f"]) for nid, pc in ctx.pieces.items() if pc["kind"] == "muscle"}
    boxes = {i: (o["v"].min(0), o["v"].max(0)) for i, o in own.items() if o["e"]["cat"] in ("muscle", "tendon") and len(o["f"]) >= 4}
    for nid, pc in ctx.pieces.items():
        if pc["kind"] != "muscle":
            continue
        base = pc["base"]
        v, f = pc["v"], pc["f"]
        lo, hi = v.min(0) - 6, v.max(0) + 6
        others = []
        for i, o in own.items():
            if i not in boxes or i == base or i.startswith(base + "_zfill"):
                continue
            bl, bh = boxes[i]
            if (bh < lo).any() or (bl > hi).any():
                continue
            others.append(trimesh.Trimesh(o["v"], o["f"], process=False))
        for j, (vj, fj) in cur_m.items():
            if j != nid and len(fj) > 3 and not ((vj.max(0) < lo).any() or (vj.min(0) > hi).any()):
                others.append(trimesh.Trimesh(vj, fj, process=False))
        bm = ctx.bones_near(lo, hi)

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


def badge_text(ctx, pieces, name, kind, group):
    cfg = ctx.cfg
    meds = [p["info"].get("fit_err_median_mm") for p in pieces if p["info"].get("fit_err_median_mm") is not None]
    maxs = [p["info"].get("fit_err_max_mm") for p in pieces if p["info"].get("fit_err_max_mm") is not None]
    ends = ", ".join(sorted({(f"{p['info']['axis']}={p['info']['pos']} mm" if "axis" in p["info"] else f"{p['info']['end']} end of the shaft") for p in pieces}))
    if all(p["info"].get("stage") == "bone_end" for p in pieces):
        srcs0 = sorted({p["info"].get("z_source", "") for p in pieces})
        meds0 = [p["info"]["fit_err_median_mm"] for p in pieces]
        return (f"Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D) completion of the measured {name}: its {ends} stops {', '.join('%.0f' % p['info']['beyond_mm'] for p in pieces)} mm "
                f"short of the Z-Anatomy bone fitted to {cfg['he']} own bones [{'; '.join(srcs0)}] (the CT segmentation / data block ends there); the Z end is clipped 12 mm inside the measured end, closed by a planar face "
                f"inside the measured bone, kept inside {cfg['he']} skin and out of the neighbouring bones; the measured bone is not edited. Q203 validation: Z shaft vs the measured shaft within 40 mm of the end, "
                f"median {np.median(meds0):.1f} mm.")
    srcs = sorted({p["info"].get("z_source", "") for p in pieces if p["info"].get("z_source")})
    att = []
    for p in pieces:
        pl = p["info"].get("pull") or {}
        if pl.get("pulled"):
            att.append("far end carried %.1f mm onto its bone" % pl["pull_mm"])
        elif pl.get("note"):
            att.append(pl["note"])
    where = "around the shoulder girdle" if group == "sh" else "at a CT data-block seam"
    s = (f"Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D) continuation of the measured {name} beyond its flat cut {where} ({ends}): "
         f"Z-Anatomy counterpart [{'; '.join(srcs)}], clipped at the cut plane and joined to the measured end face by a short loft; ")
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
        newrec.update(name=f"{name} (continuation beyond the data-block cut, filled from Z-Anatomy)",
                      source="Z-Anatomy (CC BY-SA 4.0), fitted to this body; see the badge",
                      procedural_badge=badge_text(ctx, pc["pieces"], name, pc["kind"], pc["group"]))
        if pc.get("sep"):
            i_ = pc["sep"]
            newrec["procedural_badge"] += (f" Separated from the neighbouring muscles it sat inside ({100 * i_['inside_before']:.1f} % -> {100 * i_['inside_after']:.1f} % of the vertices, "
                                           f"moved at most {i_['move_max']:.1f} mm, volume {i_['volume_ratio']:.2f}x; the weld ring at the measured end face was not moved).")
        ctx.B.add(nid, pc["cat"], e["side"], SUBJECT[(ctx.body, pc["group"])], newrec, pc["v"], pc["f"])
        out.append(nid)
    return out


def write_bundle(ctx, out):
    he = ctx.cfg["he"]
    att = {s: [f"Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D): continuations of structures cut flat at CT data-block edges ({'around the shoulder girdle' if 'shoulder' in s else 'elsewhere in the body'}), "
               f"fitted onto {he} own bones or taken from the Z-Anatomy page fitted to {he} body (Q203); the measured structures are not edited. Z-Anatomy: models by the Z-Anatomy project, app by "
               "Lluis Vinent Juanico -- see third_party/z-anatomy/NOTICE and third_party/z-anatomy/README.md. Licensed CC BY-SA 4.0; this derivative remains CC BY-SA 4.0 (ShareAlike)."]
           for (b, g), s in SUBJECT.items() if b == ctx.body and any(pc["group"] == g for pc in ctx.pieces.values())}
    return ctx.B.write(out, new_subject_attribution=att)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True, choices=["vhm", "vhf"])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--scope", default="all", choices=["shoulder", "all"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--rows", default=None)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    t = time.time()
    ctx = Ctx(a.body, scope=a.scope)
    print("ctx", round(time.time() - t, 1), flush=True)
    stage_bones(ctx)
    stage_bone_ends(ctx)
    print("bones done", round(time.time() - t, 1), flush=True)
    stage_muscles(ctx, only=a.only)
    print("muscles done", round(time.time() - t, 1), flush=True)
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
        seams = {nid: [dict(axis=r["axis"], pos=r["pos"], polys=r["covered"]) for r in pc["pieces"] if "covered" in r and "axis" in r] for nid, pc in ctx.pieces.items() if "pieces" in pc}
        (REPO / f"data/derived/Q203_seams_{a.body}.json").write_text(json.dumps(seams))
    print("done", round(time.time() - t, 1))
