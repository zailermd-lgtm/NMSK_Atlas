#!/usr/bin/env python3
"""Q204 READ-ONLY whole-body REGIONAL anatomy audit of one currently published page (extends the Q198 junction audit beyond the elbow).
    python3 scripts/zanatomy/q204_regions.py MODEL   -> build/q204_raw/Q204_regions_<MODEL>.json   (git-ignored; data/derived/Q204_anatomy_audit.json is the compact result)
Per structure the UNCHANGED Q198 analysers (q198_soft.analyse_belly / analyse_tube: islands, flat cut faces, open edges, ends vs bone, outside skin, inside bone)
with a pseudo-junction (centre = structure centroid, R = infinity) and the Q198 severity thresholds (q198_rank.junction_defects rules, copied below); regions by
nearest-bone label + joint proximity; bones: pair penetration + nearest-bone gap on a 2 mm voxel field; muscle-in-muscle overlap on the same field;
skin: patch-border gaps by region + limb-segment cross-sections (q198_audit.skin_profile); left/right mirrored pairs."""
from __future__ import annotations
import json, re, sys, time
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q204_paths  # noqa: F401,E402
from scripts.zanatomy.q198_load import load, MODELS  # noqa: E402
from scripts.zanatomy.q198_core import Grid, SkinField, weld, boundary_loops, tri_area, surf_points  # noqa: E402
from scripts.zanatomy.q198_joints import find_joints  # noqa: E402
from scripts.zanatomy import q198_soft as SO  # noqa: E402
from scripts.zanatomy import q198_audit as QA  # noqa: E402
from scripts.zanatomy.q198_rank import THRESH, STEP, PLURAL, EARLARYNX  # noqa: E402

OUT = REPO / scripts.zanatomy.q204_paths.RAW_DIR
H = 2.0                                                      # whole-body voxel pitch (mm); Q198 junction zones used 1.5
TUBE_SYS = {"vessel", "nerve"}
CONNECTIVE_SYS = {"tendon", "ligament", "fascia", "cartilage", "joint", "insertion", "bursa", "skin"}
REGIONS = ["head_neck", "shoulder", "arm_elbow_forearm", "wrist_hand", "thorax", "abdomen_pelvis", "hip", "thigh", "knee", "leg", "ankle", "foot"]
JOINT_REGION = {"shoulder": ("shoulder", 60), "hip": ("hip", 60), "knee": ("knee", 55), "ankle": ("ankle", 45), "wrist": ("wrist_hand", 40), "elbow": ("arm_elbow_forearm", 45)}
SKIP_BONE_NN = re.compile(r"tooth|molar|incisor|canine|premolar|incus|malleus|stapes|hyoid|sesamoid|sinus|cartilage|concha|lacrimal|vomer|nasal|ethmoid|palatine|zygomatic|maxilla|sphenoid|temporal|mandible|cranium|occipital|frontal|parietal")


def bone_region(i):
    b = re.sub(r"#\d+$", "", i)
    if re.search(r"carpal|scaphoid|lunate|triquetr|pisiform|trapez|capitate|hamate|metacarp|finger_of_hand|phalanges_hand", b):
        return "wrist_hand"
    if re.search(r"calcaneus|talus|tarsal|cuboid|cuneiform|navicular|metatars|finger_of_foot|phalanges_foot|sesamoid", b):
        return "foot"
    if re.search(r"scapula|clavicle", b):
        return "shoulder"
    if re.search(r"^(zan_)?(humerus|radius|ulna)", b):
        return "arm_elbow_forearm"
    if re.search(r"^(zan_)?femur", b):
        return "thigh"
    if re.search(r"patella", b):
        return "knee"
    if re.search(r"^(zan_)?(tibia|fibula)", b):
        return "leg"
    if re.search(r"hip_bone|sacrum|coccyx|lumbar|vertebra_l\d", b):
        return "abdomen_pelvis"
    if re.search(r"rib|sternum|xiph|thoracic|vertebra_t\d", b):
        return "thorax"
    return "head_neck"


GROUP_RE = re.compile(r"^(tarsals|carpals|metatarsals|phalanges_hand|phalanges_foot|ribs|cervical_vertebrae|thoracic_vertebrae|lumbar_vertebrae)(_[lr])?(#\d+)?$")
INBONE_MIN_MM = 5.0                                          # regional pass: Z attachments embed 3-5 mm by design and the 2 mm pitch adds closing error; Q198 junction zones keep 3 mm
CANAL_RE = re.compile(r"alveolar|mental_|diploic|emissary|nutrient|vertebral_a|spinal|radicular|canal")   # vessels/nerves that run INSIDE bone canals by design
TEETH_RE = re.compile(r"tooth|molar|incisor|canine|premolar|incus|malleus|stapes|sinus")
CENTRAL = {"head_neck", "thorax", "abdomen_pelvis", "hip", "shoulder"}   # mirrored-position test only where the pose does not move the structure
SPINE_RE = re.compile(r"vertebra|sacrum|coccyx|atlas_c1|axis_c2")


def norm_id(i):
    return re.sub(r"_zfill\w*", "", i)


def mesh_volume_cm3(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)) / 1000.0


def pseudo_J(v, side):
    p = v if len(v) < 20000 else v[:: len(v) // 20000 + 1]
    c = p.mean(0)
    ax = np.linalg.svd(p - c, full_matrices=False)[2][0]
    return dict(centre=c, axis=ax, R=1e6, side=side, name="body")


class BoneVox:
    """2 mm voxel field of the individual bone solids: top-two depth arrays (union depth = d1; interpenetration depth of a pair = second-largest depth at the voxel)"""
    def __init__(self, bones, lo, hi, h=H):
        self.g = Grid(lo, hi, h); self.h = h
        sh = self.g.shape
        self.d1 = np.zeros(sh, np.float16); self.d2 = np.zeros(sh, np.float16)
        self.l1 = np.full(sh, -1, np.int16); self.l2 = np.full(sh, -1, np.int16)
        self.ids = [b["id"] for b in bones]
        for k, b in enumerate(bones):
            v = b["v"]
            i0 = np.maximum(np.floor((v.min(0) - 6 - self.g.lo) / h).astype(int), 0)
            lo_l = self.g.lo + i0 * h
            gl = Grid(lo_l, v.max(0) + 6, h)
            try:
                sol = gl.solid(v, b["f"], close=1)
            except Exception:  # noqa
                continue
            if not sol.any():
                continue
            dep = ndi.distance_transform_edt(sol, sampling=h).astype(np.float16)
            sl = tuple(slice(int(i0[a]), min(int(i0[a]) + sol.shape[a], sh[a])) for a in range(3))
            sub = tuple(slice(0, sl[a].stop - sl[a].start) for a in range(3))
            dep = dep[sub]; m = sol[sub]
            D1, D2, L1, L2 = self.d1[sl], self.d2[sl], self.l1[sl], self.l2[sl]
            dd = np.where(m, dep, 0)
            up1 = dd > D1
            up2 = (~up1) & (dd > D2)
            D2[up1] = D1[up1]; L2[up1] = L1[up1]
            D1[up1] = dd[up1]; L1[up1] = k
            D2[up2] = dd[up2]; L2[up2] = k

    def fn(self, p):
        d, ok = self.g.lookup(self.d1, p)
        d = d.astype(np.float32)
        return d > 0, d

    def pair_penetrations(self, bones_by_idx, minmm=2.0):
        idx = np.argwhere(self.d2 > 0)
        if len(idx) == 0:
            return []
        a = self.l1[tuple(idx.T)].astype(int); b = self.l2[tuple(idx.T)].astype(int); d = self.d2[tuple(idx.T)].astype(np.float32)
        out = {}
        for x, y, dd in zip(a, b, d):
            if x < 0 or y < 0:
                continue
            ia, ib = self.ids[x], self.ids[y]
            if norm_id(ia) == norm_id(ib):
                continue
            key = tuple(sorted((ia, ib)))
            r = out.setdefault(key, [0, 0.0])
            r[0] += 1; r[1] = max(r[1], float(dd))
        rows = [{"a": k[0], "b": k[1], "vol_mm3": round(v[0] * self.h ** 3, 1), "max_depth_mm": round(v[1], 2)} for k, v in out.items() if v[1] >= minmm]
        return sorted(rows, key=lambda r: -r["max_depth_mm"])


def structure_defects(r):
    """Q198 junction_defects rules for ONE whole-body row -> list of (check, sev, value, unit, detail)"""
    out = []
    nm, sy = r["id"], r["sys"]

    def add(check, sev, value, unit, detail):
        if sev > 0:
            out.append({"check": check, "severity": int(sev), "value": value, "unit": unit, "detail": detail})
    if r.get("error") or r.get("note"):
        return out
    if sy == "bone":
        for cp in r.get("flat_caps") or []:
            add("bone_flat_cut", 3 if cp["area_mm2"] > 500 else 2 if cp["area_mm2"] > 150 else 0, cp["area_mm2"], "mm2", f"bone cut flat in the {cp['axis']}={cp['plane_mm']} plane ({cp['area_mm2']} mm2)")
        if r.get("max_island_gap_mm", 0) > 5 and r.get("main_area_share", 1) < 0.99:
            add("bone_island", 1, r["max_island_gap_mm"], "mm", f"bone has a detached piece {r['max_island_gap_mm']} mm from the main body")
        g = r.get("nn_bone_gap_mm")
        if g is not None:
            spine = bool(SPINE_RE.search(nm) and SPINE_RE.search(r.get("nn_bone") or ""))
            ge = g - 10.0 if spine else g                                         # intervertebral disc space is not a gap
            if ge > 6:
                add("bone_gap", 1 if ge <= 12 else 2 if ge <= 25 else 3, g, "mm", f"nearest other bone {g} mm away ({r.get('nn_bone')}): floating / gap in the skeletal chain")
        for p in r.get("penetrations") or []:
            if TEETH_RE.search(nm) or TEETH_RE.search(p["other"]):
                continue
            grp = bool(GROUP_RE.match(nm) or GROUP_RE.match(p["other"]))
            add("bone_penetration", min(STEP(p["max_depth_mm"], THRESH["bone_penetration_mm"]), 1) if grp else STEP(p["max_depth_mm"], THRESH["bone_penetration_mm"]), p["max_depth_mm"], "mm",
                f"interpenetrates {p['other']} up to {p['max_depth_mm']} mm" + (" (a grouped bone mesh duplicates its component bones)" if grp else ""))
    elif sy in TUBE_SYS:
        gap = r.get("max_island_gap_mm", 0)
        if 5 < gap <= 150 and not PLURAL.search(nm):
            add("tube_gap", min(STEP(gap, [5, 12, 25]), 2 if sy == "nerve" else 3), gap, "mm", f"{nm}: separate pieces {gap} mm apart (not continuous)")
    else:
        if sy in ("muscle", "tendon"):
            for cp in r.get("flat_caps") or []:
                add("flat_cut_face", 3 if cp["area_mm2"] > THRESH["flat_cut_cap_mm2"][1] else 2 if cp["area_mm2"] > THRESH["flat_cut_cap_mm2"][0] else 0, cp["area_mm2"], "mm2",
                    f"cut flat in the {cp['axis']}={cp['plane_mm']} plane (closed cut face {cp['area_mm2']} mm2)")
            if 5 < r.get("max_island_gap_mm", 0) <= 60 and r.get("max_island_share_gt5mm", 0) > THRESH["island_area_share"][0] and not PLURAL.search(nm):
                add("disconnected_island", STEP(r["max_island_share_gt5mm"], THRESH["island_area_share"]), r["max_island_share_gt5mm"], "area share",
                    f"detached piece with {100 * r['max_island_share_gt5mm']:.1f}% of its area, {r['max_island_gap_mm']} mm from the main belly")
            if THRESH["axial_gap_mm"][0] < r.get("max_axial_gap_mm", 0) < 150:
                add("axial_gap", STEP(r["max_axial_gap_mm"], THRESH["axial_gap_mm"]), r["max_axial_gap_mm"], "mm", f"empty stretch {r['max_axial_gap_mm']} mm along its axis")
            ib, ibx = r.get("inside_bone_pct", 0), r.get("inside_bone_max_mm", 0)
            if ibx > INBONE_MIN_MM and not EARLARYNX.search(nm):
                add("inside_bone", STEP(ib, THRESH["inside_bone_pct_with_>3mm_depth"]), ib, "% of vertices", f"{ib}% inside bone (up to {ibx} mm)")
        if sy == "muscle":
            if r.get("open_edge_frac", 0) > THRESH["open_edge_frac"][0]:
                add("ragged_open_boundary", 2 if r["open_edge_frac"] > THRESH["open_edge_frac"][1] else 1, r["open_edge_frac"], "frac of edges", f"{r.get('open_edges')} open boundary edges ({100 * r['open_edge_frac']:.1f}% of edges)")
            for end, a in (r.get("attach_ends") or {}).items():
                d = a["min_any_bone_mm"]
                if d > THRESH["attachment_distance_mm"][0] and a.get("connective_mm", 99) > 5:
                    add("end_off_bone", min(STEP(d, THRESH["attachment_distance_mm"]), 2), d, "mm", f"{end} end lies {d} mm from the nearest bone and {a.get('connective_mm')} mm from any tendon/ligament/fascia/cartilage")
            ov = r.get("overlap_pct")
            if ov is not None and ov > THRESH["muscle_overlap_pct"][0] and r.get("vol_cm3", 0) > 3 and not r.get("part_link"):
                add("muscle_interpenetration", 2 if ov > THRESH["muscle_overlap_pct"][1] else 1, ov, "% of volume", f"{ov}% of {r.get('vol_cm3')} cm3 inside other muscles")
        if sy in ("organ", "viscera", "cns", "cartilage", "joint", "bursa", "insertion", "lymph", "fascia", "tendon", "ligament", "muscle"):
            pass
    o, ox = r.get("outside_skin_pct", 0), r.get("outside_skin_max_mm", 0)
    if sy != "skin" and ox > 5 and (o > 5 or sy not in TUBE_SYS):
        add("outside_skin", STEP(o, THRESH["outside_skin_pct_with_>5mm_excursion"]), o, "% of vertices", f"{o}% lies outside the skin (up to {ox} mm)")
    if sy in TUBE_SYS and r.get("inside_bone_max_mm", 0) > INBONE_MIN_MM and r.get("inside_bone_pct", 0) > 8 and not PLURAL.search(nm) and not EARLARYNX.search(nm) and not CANAL_RE.search(nm):
        add("inside_bone", STEP(r["inside_bone_pct"], THRESH["inside_bone_pct_with_>3mm_depth"]), r["inside_bone_pct"], "% of vertices", f"{r['inside_bone_pct']}% inside bone (up to {r['inside_bone_max_mm']} mm)")
    return out


def skin_seams(skin_structs, own, region_of_point):
    """Z: gaps between the border vertices of neighbouring skin patches (nearest border vertex of ANOTHER patch): shared-border < 0.5 mm; >= 2 mm = open seam / hole border.
    own: the single skin mesh's open boundary loops by region."""
    out = {}
    if own:
        v, f = weld(skin_structs[0]["v"], skin_structs[0]["f"])
        loops, nb, nm = boundary_loops(v, f)
        for l in loops:
            c = v[l].mean(0)
            r = region_of_point(c)
            e = out.setdefault(r, {"open_loops": 0, "open_boundary_vertices": 0, "max_loop_extent_mm": 0.0})
            e["open_loops"] += 1; e["open_boundary_vertices"] += int(len(l))
            ext = float(np.linalg.norm(v[l].max(0) - v[l].min(0)))
            e["max_loop_extent_mm"] = round(max(e["max_loop_extent_mm"], ext), 1)
        return out, {"open_boundary_edges": int(nb), "nonmanifold_edges": int(nm), "open_loops": len(loops)}
    P, lab, pid = [], [], []
    for k, s in enumerate(skin_structs):
        v, f = weld(s["v"], s["f"])
        loops, nb, nm = boundary_loops(v, f)
        if not loops:
            continue
        idx = np.unique(np.concatenate(loops))
        P.append(v[idx]); lab += [k] * len(idx)
    if not P:
        return out, {}
    P = np.concatenate(P); lab = np.asarray(lab)
    tr = cKDTree(P)
    d, ix = tr.query(P, k=12)
    dist = np.full(len(P), np.inf)
    for j in range(12):
        ok = (lab[ix[:, j]] != lab) & np.isinf(dist)
        dist[ok] = d[ok, j]
    tot = {"border_vertices": int(len(P)), "gap_ge_2mm": int((dist >= 2).sum()), "gap_2_20mm": int(((dist >= 2) & (dist < 20)).sum()), "max_gap_below_60mm": round(float(dist[dist < 60].max()), 1) if (dist < 60).any() else 0.0}
    for r_ in REGIONS:
        pass
    reg = np.array([region_of_point(p) for p in P[:: 1]])
    for r_ in sorted(set(reg)):
        m = reg == r_
        e = {"border_vertices": int(m.sum()), "seam_mismatch_0p5_2mm": int(((dist[m] >= 0.5) & (dist[m] < 2)).sum()), "gap_ge_2mm": int((dist[m] >= 2).sum()),
             "gap_2_20mm": int(((dist[m] >= 2) & (dist[m] < 20)).sum()), "max_gap_below_20mm": round(float(dist[m][dist[m] < 20].max()), 1) if (dist[m] < 20).any() else 0.0}
        out[r_] = e
    return out, tot


def segment_J(a, b, R=60):
    ax = b - a
    ax = ax / np.linalg.norm(ax)
    return dict(centre=(a + b) / 2, axis=ax, R=R, name="seg", side="m")


def symmetry(rows):
    """left/right mirrored pairs -> (midline x0, outliers sorted by score)"""
    by = defaultdict(dict)
    for r in rows:
        m = re.match(r"^(.*?)(?:_([lr]))(?:#\d+)?$", r["id"])
        if m and r["side"] in ("l", "r"):
            by[(m.group(1), r["sys"])].setdefault(r["side"], r)
    pairs = [(k, d["l"], d["r"]) for k, d in by.items() if "l" in d and "r" in d]
    x0 = float(np.median([(a["centroid"][0] + b["centroid"][0]) / 2 for _, a, b in pairs if a["sys"] == "bone"])) if pairs else 0.0
    sym = []
    for k, a, b in pairs:
        ca, cb = np.asarray(a["centroid"]), np.asarray(b["centroid"])
        cbm = cb.copy(); cbm[0] = 2 * x0 - cbm[0]
        off = float(np.linalg.norm(ca - cbm))
        va, vb = a.get("vol_cm3"), b.get("vol_cm3")
        vr = (va / vb) if va and vb and min(va, vb) > 5 else None
        la, lb = a.get("length_mm"), b.get("length_mm")
        lr = (la / lb) if la and lb and min(la, lb) > 30 else None
        sa, sb = max([d["severity"] for d in a["defects"]], default=0), max([d["severity"] for d in b["defects"]], default=0)
        why = []
        if off > 25 and a["region"] in CENTRAL: why.append(f"mirrored position differs {off:.0f} mm")
        if vr is not None and not (0.6 <= vr <= 1.66): why.append(f"volume ratio L/R {vr:.2f}")
        if lr is not None and not (0.7 <= lr <= 1.43): why.append(f"length ratio L/R {lr:.2f}")
        if abs(sa - sb) >= 2: why.append(f"defect severity L {sa} vs R {sb}")
        if why:
            sym.append({"structure": k[0], "sys": k[1], "region": a["region"], "mirror_offset_mm": round(off, 1), "vol_ratio": None if vr is None else round(vr, 2), "len_ratio": None if lr is None else round(lr, 2),
                        "sev_l_r": [sa, sb], "why": "; ".join(why), "score": (off / 25 if a["region"] in CENTRAL else 0) + (abs(np.log(vr)) if vr else 0) + (abs(np.log(lr)) if lr else 0) + abs(sa - sb)})
    sym.sort(key=lambda x: -x["score"])
    return x0, sym


def main(key):
    t0 = time.time()
    kind = MODELS[key][2]
    S = load(key)
    if kind == "own":
        QA.own_classes(S)
    J, B, lev = find_joints(S)
    jc = {(j["name"], j["side"]): j for j in J}
    skin_structs = [s for s in S if s["sys"] == "skin" or s["id"] == "skin"]
    skin = SkinField(skin_structs + QA.female_sealers(key, S), 3.0, close=1 if kind == "own" else 2)
    bones = [s for s in S if s["sys"] == "bone"]
    bf = SO.BoneField(bones)
    print(key, "loaded", len(S), "structures", round(time.time() - t0), "s", flush=True)
    # ---- regions ----
    ids = list(bf.pts)
    brg = {i: bone_region(i) for i in ids}
    P = np.concatenate([bf.pts[i] for i in ids]); L = np.concatenate([np.full(len(bf.pts[i]), REGIONS.index(brg[i]), np.int16) for i in ids])
    tree = cKDTree(P)
    rng = np.random.default_rng(0)

    def region_of_point(p, nearest_only=True):
        d, ix = tree.query(np.asarray(p, float).reshape(-1, 3))
        return REGIONS[int(L[ix[0]])]

    def region_of(s):
        if s["sys"] == "bone":
            return brg.get(s["id"], bone_region(s["id"]))
        v = s["v"]
        smp = v[rng.choice(len(v), min(len(v), 120), replace=False)]
        d, ix = tree.query(smp)
        cnt = np.bincount(L[ix], minlength=len(REGIONS))
        reg = REGIONS[int(cnt.argmax())]
        c = v.mean(0)
        for (jn, sd), j in jc.items():
            if jn in JOINT_REGION and np.linalg.norm(c - j["centre"]) < JOINT_REGION[jn][1]:
                reg = JOINT_REGION[jn][0]
        return reg
    # ---- voxel field of bones, muscle overlap ----
    allv = np.concatenate([s["v"] for s in S if len(s["v"])])
    lo, hi = allv.min(0) - 8, allv.max(0) + 8
    BV = BoneVox(bones, lo, hi)
    print(key, "bone voxel field", BV.g.shape, round(time.time() - t0), "s", flush=True)
    mus = [s for s in S if s["sys"] == "muscle" and len(s["f"]) > 4]
    cnt = np.zeros(BV.g.shape, np.int8); msol = {}
    for m in mus:
        v = m["v"]
        i0 = np.maximum(np.floor((v.min(0) - 6 - BV.g.lo) / H).astype(int), 0)
        gl = Grid(BV.g.lo + i0 * H, v.max(0) + 6, H)
        try:
            sol = gl.solid(v, m["f"], close=1)
        except Exception:  # noqa
            continue
        w = np.argwhere(sol) + i0
        w = w[(w < np.asarray(BV.g.shape)).all(1)]
        if len(w):
            cnt[tuple(w.T)] += 1; msol[m["id"]] = w
    overlap = {}
    for mid, w in msol.items():
        overlap[mid] = (round(100 * float((cnt[tuple(w.T)] > 1).mean()), 1), round(len(w) * H ** 3 / 1000, 1))
    del cnt
    print(key, "muscle overlap", len(overlap), round(time.time() - t0), "s", flush=True)
    # ---- bone nearest-neighbour gaps + pair penetrations ----
    bb = {b["id"]: (b["v"].min(0), b["v"].max(0)) for b in bones}
    nn = {}
    for b in bones:
        a = b["id"]
        if SKIP_BONE_NN.search(a) and not re.search(r"temporal|mandible|cranium|occipital|frontal|parietal|zygomatic|maxilla|sphenoid", a):
            continue
        best = (np.inf, None)
        for c in bones:
            o = c["id"]
            if o == a or norm_id(o) == norm_id(a) or SKIP_BONE_NN.search(o) and not re.search(r"temporal|mandible|cranium|occipital|frontal|parietal|zygomatic|maxilla|sphenoid", o):
                continue
            lo_a, hi_a = bb[a]; lo_o, hi_o = bb[o]
            gapbox = np.maximum(0, np.maximum(lo_a - hi_o, lo_o - hi_a))
            if np.linalg.norm(gapbox) > min(best[0], 40) + 1:
                continue
            dmin = float(bf.tree[a].query(bf.pts[o][:: max(1, len(bf.pts[o]) // 4000)])[0].min())
            if dmin < best[0]:
                best = (dmin, o)
        nn[a] = best
    pens = BV.pair_penetrations(None)
    pen_by = defaultdict(list)
    for p in pens:
        pen_by[p["a"]].append({"other": p["b"], "max_depth_mm": p["max_depth_mm"], "vol_mm3": p["vol_mm3"]})
        pen_by[p["b"]].append({"other": p["a"], "max_depth_mm": p["max_depth_mm"], "vol_mm3": p["vol_mm3"]})
    print(key, "bone pairs", len(nn), "penetrating pairs", len(pens), round(time.time() - t0), "s", flush=True)
    # ---- connective points (muscle end exemption) ----
    cp = [s["v"] for s in S if s["sys"] in CONNECTIVE_SYS]
    ctree = cKDTree(np.concatenate(cp)) if cp else None
    # ---- per structure ----
    rows = []
    for k, s in enumerate(S):
        if s["sys"] == "skin" or s["id"] == "skin" or len(s["f"]) < 4:
            continue
        r = {"id": s["id"], "name": s["name"], "sys": s["sys"], "side": s["side"], "src": s.get("src"), "cls": s.get("cls"), "nv": int(len(s["v"]))}
        try:
            r["region"] = region_of(s)
            Jp = pseudo_J(s["v"], s["side"])
            bonefill = (lambda p: (np.zeros(len(p), bool), np.zeros(len(p), np.float32))) if s["sys"] == "bone" else BV.fn
            if s["sys"] in TUBE_SYS:
                q = SO.analyse_tube(s, Jp, bf, skin, bonefill)
                keep = ("islands", "max_island_gap_mm", "outside_skin_pct", "outside_skin_max_mm", "inside_bone_pct", "inside_bone_max_mm", "geodesic_len_mm")
            else:
                q = SO.analyse_belly(s, Jp, bf, skin, bonefill, expb=None)
                keep = ("islands", "max_island_gap_mm", "max_island_share_gt5mm", "main_area_share", "open_edge_frac", "open_edges", "flat_caps", "max_axial_gap_mm", "length_mm",
                        "outside_skin_pct", "outside_skin_max_mm", "inside_bone_pct", "inside_bone_max_mm", "note")
            for kk in keep:
                if kk in q:
                    r[kk] = q[kk]
            if s["sys"] == "muscle" and q.get("attach_ends_in_zone"):
                ae = {}
                for en, a in q["attach_ends_in_zone"].items():
                    ep = np.asarray(q["end_prox_mm"] if en == "prox" else q["end_dist_mm"])
                    ae[en] = {"min_any_bone_mm": a["min_any_bone_mm"], "median_any_bone_mm": a["median_any_bone_mm"], "connective_mm": round(float(ctree.query(ep)[0]), 1) if ctree is not None else 99}
                r["attach_ends"] = ae
            r["vol_cm3"] = round(mesh_volume_cm3(*weld(s["v"], s["f"])), 1) if s["sys"] != "bone" else None
            r["centroid"] = np.round(s["v"].mean(0), 1).tolist()
            if s["sys"] == "muscle" and s["id"] in overlap:
                r["overlap_pct"], r["vol_cm3"] = overlap[s["id"]]
                rec = s.get("rec") or {}
                r["part_link"] = bool(rec.get("part_of_id"))
            if s["sys"] == "bone":
                g = nn.get(s["id"])
                if g:
                    r["nn_bone_gap_mm"] = round(g[0], 2); r["nn_bone"] = g[1]
                r["penetrations"] = pen_by.get(s["id"], [])
        except Exception as ex:  # noqa
            r["error"] = repr(ex)[:200]
        r["defects"] = structure_defects(r)
        rows.append(r)
        if k % 300 == 0:
            print(key, "structure", k, "/", len(S), round(time.time() - t0), "s", flush=True)
    # part_of parents (Z): exempt parents of linked heads from overlap defects
    parents = {(s.get("rec") or {}).get("part_of_id") for s in S}
    for r in rows:
        if r["id"] in parents:
            r["part_link"] = True
            r["defects"] = structure_defects(r)
    # ---- skin ----
    sk_reg, sk_tot = skin_seams(skin_structs, kind == "own", region_of_point)
    segs = {}
    seg_def = {"thigh": ("hip", "knee"), "leg": ("knee", "ankle"), "upper_arm": ("shoulder", "elbow"), "forearm": ("elbow", "wrist")}
    for sd in ("l", "r"):
        for sn, (a, b) in seg_def.items():
            if (a, sd) in jc and (b, sd) in jc:
                Jg = segment_J(jc[(a, sd)]["centre"], jc[(b, sd)]["centre"], R=60)
                try:
                    segs[f"{sn}_{sd}"] = QA.skin_profile(skin_structs, Jg, half=min(90, 0.5 * float(np.linalg.norm(jc[(a, sd)]["centre"] - jc[(b, sd)]["centre"]))))
                except Exception as ex:  # noqa
                    segs[f"{sn}_{sd}"] = {"error": repr(ex)[:120]}
    if ("head_neck", "m") in jc and ("cervico_thoracic", "m") in jc:
        Jg = segment_J(jc[("head_neck", "m")]["centre"], jc[("cervico_thoracic", "m")]["centre"], R=60)
        try:
            segs["neck"] = QA.skin_profile(skin_structs, Jg, half=min(60, 0.5 * float(np.linalg.norm(jc[("head_neck", "m")]["centre"] - jc[("cervico_thoracic", "m")]["centre"]))))
        except Exception as ex:  # noqa
            segs["neck"] = {"error": repr(ex)[:120]}
    x0, sym = symmetry(rows)
    res = {"model": key, "n_rows": len(rows), "midline_x_mm": round(x0, 1), "voxel_mm": H, "bone_voxel_shape": list(BV.g.shape), "rows": rows, "skin_seams_by_region": sk_reg, "skin_seam_totals": sk_tot, "skin_segments": segs,
           "symmetry": sym, "bone_penetrating_pairs": pens[:80], "bone_nn": {k: [round(v[0], 2), v[1]] for k, v in nn.items()}, "joint_centres": {f"{n}_{s}": np.round(j["centre"], 1).tolist() for (n, s), j in jc.items()},
           "seconds": round(time.time() - t0)}
    (OUT / f"Q204_regions_{key}.json").write_text(json.dumps(res, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))
    print(key, "done", round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
