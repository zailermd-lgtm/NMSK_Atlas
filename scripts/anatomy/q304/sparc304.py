#!/usr/bin/env python3
"""Q304 Part B: validate and calibrate our sciatic nerve's CALIBRE against SPARC dataset 692.

    python3 -I scripts/anatomy/q304/sparc304.py fetch   [--dl /dev/shm/q304_sparc]
    python3 -I scripts/anatomy/q304/sparc304.py measure [--dl /dev/shm/q304_sparc]

Dataset: *Mapping the fascicular morphology and organization of the human sciatic nerve via high-resolution
microCT imaging*, SPARC/Pennsieve dataset 692 version 1, DOI 10.26275/1jdc-qiiv, CC BY 4.0, Case Western
Reserve University / NIH SPARC. Subject `sub-SC001`: Homo sapiens, male, 41 years, embalmed cadaver; both
sciatic nerves, phosphotungstic-acid stained, microCT at 11.4 um isotropic.

CALIBRE ONLY, NEVER SHAPE. Q302 measured why: the six samples are ~9 cm segments that were EXCISED and laid
straight in the scanner (`SCL2`'s traced centreline is 7,465 points over an 84.76 mm axial span with an 85.09 mm
arc length and 1.0 x 1.3 mm of lateral wander -- a straight line in scan space). There is no in-body trajectory
in this dataset, so nothing here may touch the course of any mesh. What it does carry is a real human sciatic
nerve's cross-sectional size, per slice, at named anatomical levels.

The whole dataset is 369.7 GB. This script downloads only the per-slice morphology products and the level
annotations -- about 10 MB -- from the dataset's own public S3 bucket (the one its Pennsieve record names in
`uri`), into its OWN empty directory, and keeps only the derived numbers on disk.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, subprocess, sys, urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data/derived/Q304_sparc692_calibre.json"
BUCKET = "https://sparc-prod-aod-discover-publish50-use1.s3.amazonaws.com/692"
DOI = "10.26275/1jdc-qiiv"
SAMPLES = [("SCL2", "left"), ("SCL3", "left"), ("SCL4", "left"), ("SCR2", "right"), ("SCR3", "right"), ("SCR4", "right")]
VOX_MM = 0.0114          # 11.4 um isotropic: the NerveMorphology columns are in VOXELS, not mm
LEVELS = ["level of formation of sciatic nerve from sacral roots",
          "level of lesser trochanter of femur on sciatic nerve",
          "level of 7 cm inferior to lesser trochanter of femur on sciatic nerve",
          "level of 14 cm inferior to lesser trochanter of femur on sciatic nerve",
          "level of 21 cm inferior to lesser trochanter of femur on sciatic nerve"]
SHORT = ["formation", "lesser_trochanter", "lt+7cm", "lt+14cm", "lt+21cm"]

def paths():
    out = ["files/README.md", "files/dataset_description.xlsx", "files/samples.xlsx", "files/subjects.xlsx", "manifest.json"]
    for s, side in SAMPLES:
        out.append(f"files/derivative/sub-SC001/NerveMorphology/SC001-SciaticTrunks/SC001-{side}_sciatic_nerve/"
                   f"SC001-{s}-{side}_sciatic_nerve-NerveMorphology.csv")
        out.append(f"files/primary/sub-SC001/sam-SC001-{s}/SC001-{s}-Annotations/SC001-{s}-sciatic_levels.csv")
        out.append(f"files/primary/sub-SC001/sam-SC001-{s}/SC001-{s}-Annotations/SC001-{s}-{side}_sciatic_nerve.csv")
    return out


def fetch(dl: Path):
    dl.mkdir(parents=True, exist_ok=True)
    got = []
    for p in paths():
        dst = dl / p.replace("/", "__")
        if not dst.exists() or dst.stat().st_size == 0:
            u = BUCKET + "/" + urllib.parse.quote(p)
            r = subprocess.run(["curl", "-sS", "--max-time", "300", "-o", str(dst), u], capture_output=True, text=True)
            if r.returncode:
                print("FAILED", p, r.stderr[-200:]); continue
        b = dst.read_bytes()
        got.append(dict(path=p, bytes=len(b), sha256=hashlib.sha256(b).hexdigest()))
        print(f"{len(b):10d}  {hashlib.sha256(b).hexdigest()[:16]}  {p}", flush=True)
    (dl / "_fetched.json").write_text(json.dumps(got, indent=1), encoding="utf-8")
    print("total bytes", sum(g["bytes"] for g in got))


def read_csv(p: Path):
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def measure(dl: Path):
    import numpy as np
    res = {"dataset": dict(id=692, version=1, doi=DOI, license="CC BY 4.0",
                           name="Mapping the fascicular morphology and organization of the human sciatic nerve via "
                                "high-resolution microCT imaging",
                           subject="sub-SC001 (Homo sapiens, male, 41 years, embalmed cadaver)",
                           voxel_um=11.4, bucket=BUCKET),
           "files": json.loads((dl / "_fetched.json").read_text()), "samples": {}}
    for s, side in SAMPLES:
        mp = dl / (f"files/derivative/sub-SC001/NerveMorphology/SC001-SciaticTrunks/SC001-{side}_sciatic_nerve/"
                   f"SC001-{s}-{side}_sciatic_nerve-NerveMorphology.csv").replace("/", "__")
        lp = dl / (f"files/primary/sub-SC001/sam-SC001-{s}/SC001-{s}-Annotations/SC001-{s}-sciatic_levels.csv").replace("/", "__")
        rows = read_csv(mp)
        cols = list(rows[0]) if rows else []
        def col(name):
            for c in cols:
                if c.strip().lower() == name:
                    return c
            for c in cols:
                if name in c.strip().lower():
                    return c
            return None
        ed, sl = col("eq_diameter"), col("slice")
        ar = col("area")
        d = np.array([float(r[ed]) for r in rows if r.get(ed) not in (None, "")]) * VOX_MM
        z = np.array([float(r[sl]) for r in rows if r.get(sl) not in (None, "")]) if sl else np.arange(len(d), dtype=float)
        a = np.array([float(r[ar]) for r in rows if r.get(ar) not in (None, "")]) * VOX_MM * VOX_MM if ar else np.zeros(0)
        lev = read_csv(lp) if lp.exists() else []
        res["samples"][s] = dict(
            side=side, n_slices=int(len(d)), columns=cols,
            eq_diameter_mm=dict(min=round(float(d.min()), 3), max=round(float(d.max()), 3),
                                mean=round(float(d.mean()), 3), median=round(float(np.median(d)), 3),
                                p05=round(float(np.quantile(d, 0.05)), 3), p95=round(float(np.quantile(d, 0.95)), 3),
                                sd=round(float(d.std(ddof=1)), 3)),
            area_mm2=(dict(mean=round(float(a.mean()), 3), median=round(float(np.median(a)), 3)) if len(a) else None),
            slice_range=[float(z.min()), float(z.max())], levels=lev,
            note="the NerveMorphology columns are in VOXELS of the 11.4 um isotropic scan; every value here is "
                 "converted with 0.0114 mm per voxel")
    D = []
    for s, side in SAMPLES:
        D.append(res["samples"][s]["eq_diameter_mm"]["mean"])
    res["levels"] = level_table(dl)
    res["pooled"] = dict(n_samples=len(SAMPLES),
                         mean_of_sample_means_mm=round(float(sum(D) / len(D)), 3),
                         min_sample_mean_mm=round(min(D), 3), max_sample_mean_mm=round(max(D), 3))
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res["pooled"], indent=1))
    for s, _ in SAMPLES:
        v = res["samples"][s]
        print(f"  {s} {v['side']:5s} n={v['n_slices']:6d} eq_diameter mean {v['eq_diameter_mm']['mean']:5.2f} "
              f"median {v['eq_diameter_mm']['median']:5.2f} range {v['eq_diameter_mm']['min']:5.2f}-{v['eq_diameter_mm']['max']:5.2f} mm"
              f"  levels {len(v['levels'])}")
    print("->", OUT)


# ---------------------------------------------------------------------------- SPARC levels -> a diameter per level
def level_table(dl: Path):
    """{side: {short level name: {slice, eq_diameter_mm, windowed mean, sample}}} from the dataset's own level
    annotations. `axis-0` of a level annotation is the slice index along that sample's scan, so the diameter at a
    named anatomical level is the NerveMorphology row at that slice (and, because a single 11.4 um slice is noise,
    the mean over a +-2 mm window of slices, which is stated with it)."""
    import numpy as np
    out = {"left": {}, "right": {}}
    win = int(round(2.0 / VOX_MM))
    for s, side in SAMPLES:
        mp = dl / (f"files/derivative/sub-SC001/NerveMorphology/SC001-SciaticTrunks/SC001-{side}_sciatic_nerve/"
                   f"SC001-{s}-{side}_sciatic_nerve-NerveMorphology.csv").replace("/", "__")
        lp = dl / (f"files/primary/sub-SC001/sam-SC001-{s}/SC001-{s}-Annotations/SC001-{s}-sciatic_levels.csv").replace("/", "__")
        rows = read_csv(mp)
        idx = np.array([float(r["index"]) for r in rows])
        d = np.array([float(r["eq_diameter"]) for r in rows]) * VOX_MM
        a = np.array([float(r["area"]) for r in rows]) * VOX_MM * VOX_MM
        for lr in (read_csv(lp) if lp.exists() else []):
            nm = lr["name"]
            short = None
            for L, sh in zip(LEVELS, SHORT):
                if nm.strip().lower() == (side + " " + L):
                    short = sh
            if short is None:
                continue
            z = float(lr["axis-0"])
            j = int(np.argmin(np.abs(idx - z)))
            m = np.abs(idx - z) <= win
            out[side][short] = dict(sample=s, slice=z, nearest_slice=float(idx[j]),
                                    eq_diameter_mm=round(float(d[j]), 3),
                                    eq_diameter_window_mean_mm=round(float(d[m].mean()), 3),
                                    eq_diameter_window_sd_mm=round(float(d[m].std(ddof=1)), 3) if m.sum() > 1 else 0.0,
                                    area_mm2=round(float(a[j]), 3), window_slices=int(m.sum()),
                                    annotation=nm)
    return out


# ---------------------------------------------------------------------------- our own sciatic nerve, same quantity
def ours(keys=None, src=None):
    """Our sciatic nerve's equivalent diameter at the SAME bone-referenced levels, on each page's own meshes.

    The levels are placed on the page's OWN femur, by one geometric rule used identically on all six pages:
      * the femoral head centre and the shaft axis come from the project's own `q233/dimorphism.femur_metrics`
        (a trimmed sphere fit on the medial-superior cap; the shaft axis is the femur's first principal axis);
      * the LESSER TROCHANTER is the vertex of maximum MEDIAL offset from the shaft axis among the vertices in the
        proximal 25 % of the femur, with the head and neck excluded (anything within the head radius + 8 mm of the
        head centre) and the lateral half excluded (that is the greater trochanter). Its position along the shaft
        axis is the "level of the lesser trochanter"; the rule is validated by the head-centre-to-lesser-trochanter
        distance, which the literature puts near 45-60 mm, and that number is reported with every measurement.
      * +7 / +14 / +21 cm are that level moved 70 / 140 / 210 mm DISTALLY ALONG THE SHAFT AXIS. SPARC measures those
        distances along the nerve; in the thigh the sciatic nerve runs close to parallel to the femur, so this is an
        approximation and is stated as one.
      * the "level of formation from the sacral roots" is the most PROXIMAL end of the page's own sciatic mesh,
        because that is where the page's own geometry starts; its y is reported so it can be checked against the
        sacrum.
    The quantity measured is the one SPARC reports: the cross-sectional area of the nerve in the plane
    perpendicular to the femoral shaft axis, as an equivalent diameter 2*sqrt(A/pi).
    """
    import numpy as np
    import trimesh
    sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
    sys.path.insert(0, str(REPO / "scripts/anatomy/q237"))
    import model as MD                                   # noqa: E402
    from scripts.anatomy.q233 import dimorphism as DM    # noqa: E402
    import core as C                                     # noqa: E402
    import os
    KEYS = keys or ["own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"]
    res = {}
    for key in KEYS:
        if src:
            # model.page_dir reads Q241_SRC_<key>; Model.__init__ then OVERWRITES Q237_SRC_<key> from it, so
            # setting Q237_SRC_ here would be silently undone (it was, on the first run of this round).
            os.environ["Q241_SRC_" + key] = str(Path(src) / MD.SRC[key].split("/")[-1])
        M = MD.Model(key)
        S = M.S
        byid = {}
        for x in S:
            byid.setdefault(x["id"], []).append(x)
        page = {"levels": {}, "nerves": {}}
        for side in ("l", "r"):
            fm = DM.femur_metrics(S, side)
            fb = M.bones().get(f"femur_{side}")
            if not fm or fb is None:
                continue
            v = fb["v"]
            ax = np.linalg.svd(v - v.mean(0), full_matrices=False)[2][0]
            if ax[1] < 0:
                ax = -ax                                  # +ax points superiorly
            t = (v - v.mean(0)) @ ax
            hc = np.array(fm["head_centre"], float); hr = fm["femoral_head_diameter_mm"] / 2.0
            t_hc0 = float((hc - v.mean(0)) @ ax)
            # The lesser trochanter is sought in a STATED anatomical window -- 15 to 80 mm distal to the femoral head
            # centre along the shaft axis -- and found inside it by measurement: the vertex of greatest MEDIAL radial
            # offset from the shaft axis (the greater trochanter is lateral, the neck is superior). A first version
            # searched the whole proximal quarter of the bone and was unstable: on Imaging M it gave 54.4 mm on the
            # left femur and 32.6 mm on the right of the same man, because without the window it can settle on the
            # medial calcar of the neck. The window is prior anatomical knowledge and is declared; where inside it
            # the point lands is measured, and the distance is reported with every value so it can be checked.
            band = (t > t_hc0 - 80.0) & (t < t_hc0 - 15.0)
            prox = v[band]
            prox = prox[np.linalg.norm(prox - hc, axis=1) > hr + 8.0]
            if not len(prox):
                prox = v[band] if band.any() else v[t > t.max() - 0.25 * float(np.ptp(t))]
            sgn = -1.0 if side == "r" else 1.0            # medial = toward the midline
            off = prox - (v.mean(0) + np.outer((prox - v.mean(0)) @ ax, ax))
            med = sgn * off[:, 0]
            k = int(np.argmax(med))
            lt = prox[k]
            t_lt = float((lt - v.mean(0)) @ ax)
            t_hc = float((hc - v.mean(0)) @ ax)
            page["levels"][side] = dict(
                shaft_axis=np.round(ax, 4).tolist(), femur_centroid=np.round(v.mean(0), 2).tolist(),
                femur_length_mm=fm["femur_length_mm"], femoral_head_diameter_mm=fm["femoral_head_diameter_mm"],
                head_centre=fm["head_centre"], lesser_trochanter=np.round(lt, 1).tolist(),
                head_to_lesser_trochanter_mm=round(t_hc - t_lt, 1),
                lesser_trochanter_medial_offset_mm=round(float(med[k]), 1), t_lt=round(t_lt, 2))
            for sh, dz in (("lesser_trochanter", 0.0), ("lt+7cm", 70.0), ("lt+14cm", 140.0), ("lt+21cm", 210.0)):
                page["levels"][side][sh + "_t"] = round(t_lt - dz, 2)
        # the level of formation from the sacral roots, referenced to the page's own sacrum: the sciatic nerve is
        # formed from the lumbosacral plexus just below the sacrum, so the bone reference used here is the INFERIOR
        # END of the page's own sacrum, as a y (superior-inferior) level. Stated as the approximation it is.
        sac = M.bones().get("sacrum")
        page["formation_y"] = round(float(sac["v"][:, 1].min()), 1) if sac is not None else None

        # the sciatic meshes of this page
        for sid, xs in sorted(byid.items()):
            if not C_match(sid):
                continue
            Vall, Fall = C.merge(S, [x["idx"] for x in xs])
            side = "r" if sid.endswith("_r") else ("l" if sid.endswith("_l") else None)
            rec = {"id": sid, "nv": int(len(Vall)), "tris": int(len(Fall)),
                   "y_range": [round(float(Vall[:, 1].min()), 1), round(float(Vall[:, 1].max()), 1)],
                   "sides": sorted({side} if side else {"l", "r"}), "levels": {}, "split_by_side": side is None}
            for sd in (rec["sides"]):
                # An UNSIDED mesh (the Imaging pages carry `sciatic_n` as one mesh covering both legs) is split by
                # the page's own midsagittal plane before anything is measured: otherwise the band at a level holds
                # vertices from both thighs and its centroid lands between the legs.
                if side is None:
                    cen = Vall[Fall].mean(1)
                    keep = (cen[:, 0] > 0) if sd == "r" else (cen[:, 0] < 0)
                    if keep.sum() < 4:
                        rec["levels"][f"{sd}:unavailable"] = dict(reason="no faces on this side")
                        continue
                    Fk = Fall[keep]
                    used, Fi = np.unique(Fk, return_inverse=True)
                    V = Vall[used]; F = Fi.reshape(-1, 3)
                else:
                    V, F = Vall, Fall
                m = trimesh.Trimesh(V, F, process=False)
                L = page["levels"].get(sd)
                if not L:
                    continue
                ax = np.array(L["shaft_axis"], float); o = np.array(L["femur_centroid"], float)
                for sh in ("lesser_trochanter", "lt+7cm", "lt+14cm", "lt+21cm"):
                    tt = L[sh + "_t"]
                    rec["levels"][f"{sd}:{sh}"] = nerve_section(V, F, m, sel=((V - o) @ ax), at=tt,
                                                                plane_normal=ax, plane_origin=o + ax * tt)
                if page.get("formation_y") is not None:
                    yax = np.array([0.0, 1.0, 0.0])
                    yl = float(page["formation_y"])
                    rec["levels"][f"{sd}:formation"] = nerve_section(V, F, m, sel=V[:, 1], at=yl,
                                                                     plane_normal=yax, plane_origin=np.array([0.0, yl, 0.0]))
                    rec["levels"][f"{sd}:formation"]["note"] = ("the inferior end of this page's own sacrum, y = %.1f mm"
                                                                % yl)
            page["nerves"][sid] = rec
        res[key] = page
        print(key, "sciatic meshes:", sorted(page["nerves"]), flush=True)
        for sd, L in page["levels"].items():
            print(f"   femur_{sd}: head->lesser trochanter {L['head_to_lesser_trochanter_mm']} mm, "
                  f"medial offset {L['lesser_trochanter_medial_offset_mm']} mm, femur {L['femur_length_mm']} mm", flush=True)
    p = REPO / "data/derived/Q304_our_sciatic_calibre.json"
    p.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("->", p)
    return res


def C_match(sid):
    import re
    return bool(re.match(r"^(zan_)?sciatic_n(erve)?(_[lr])?$", sid))


def section_eq_diameter(m, origin, normal):
    """the area of the mesh's cross-section in the plane (origin, normal) and its equivalent diameter -- the same
    quantity SPARC's `eq_diameter` is (2*sqrt(area/pi)); several disjoint pieces are summed and also reported."""
    import numpy as np
    try:
        sec = m.section(plane_origin=origin, plane_normal=normal)
        if sec is None:
            return dict(area_mm2=None, eq_diameter_mm=None, pieces=0)
        pl, _ = sec.to_planar()
        areas = [abs(float(p.area)) for p in pl.polygons_full] if len(pl.polygons_full) else []
        if not areas:
            return dict(area_mm2=None, eq_diameter_mm=None, pieces=0)
        A = float(sum(areas))
        return dict(area_mm2=round(A, 3), eq_diameter_mm=round(2.0 * float(np.sqrt(A / np.pi)), 3),
                    pieces=len(areas), largest_piece_eq_diameter_mm=round(2.0 * float(np.sqrt(max(areas) / np.pi)), 3))
    except Exception as e:                                 # a plane that misses the mesh entirely
        return dict(area_mm2=None, eq_diameter_mm=None, pieces=0, error=str(e)[:80])


def nerve_section(V, F, m, sel, at, plane_normal, plane_origin, half=4.0, tan_half=15.0):
    """The cross-section of the nerve at a level, cut PERPENDICULAR TO THE NERVE'S OWN LOCAL AXIS.

    This is the comparison that is apples to apples. SPARC's `eq_diameter` is computed on slices perpendicular to
    the scan axis, and the scan axis IS the excised nerve's own axis because the segment was laid straight. A plane
    perpendicular to the femoral shaft instead cuts the nerve obliquely wherever the nerve is not parallel to the
    femur -- which in the gluteal region it is not -- and inflates the area. So: the level selects a band of the
    nerve's own vertices (within `half` mm of the level along the selector), the centroid of that band is the
    centreline point, the nerve's local axis is the first principal axis of its vertices within `tan_half` mm, and
    the section is taken in the plane through the centroid perpendicular to that axis. The oblique
    (femoral-axis / axial) section is kept beside it as `oblique_eq_diameter_mm`, so the difference is on record.
    """
    import numpy as np
    sel = np.asarray(sel, float)
    # The Z sciatic mesh carries about 600 vertices over half a metre of nerve, so a fixed 4 mm band can be empty.
    # The band is widened in stated steps until it holds at least 6 vertices, and the width used is recorded.
    for half in (half, 6.0, 10.0, 15.0, 25.0):
        band = np.abs(sel - at) <= half
        if band.sum() >= 6:
            break
    out = dict(level_selector=round(float(at), 2), band_vertices=int(band.sum()), band_half_mm=float(half))
    ob = section_eq_diameter(m, plane_origin, np.asarray(plane_normal, float))
    out["oblique_eq_diameter_mm"] = ob.get("eq_diameter_mm")
    out["oblique_area_mm2"] = ob.get("area_mm2")
    if band.sum() < 6:
        out.update(area_mm2=None, eq_diameter_mm=None, pieces=0, reason="the mesh does not reach this level")
        return out
    c = V[band].mean(0)
    near = np.abs(sel - at) <= max(tan_half, 2.0 * half)
    P = V[near] if near.sum() >= 12 else V[band]
    u, sv, vt = np.linalg.svd(P - P.mean(0), full_matrices=False)
    tan = vt[0]
    r = section_eq_diameter(m, c, tan)
    out.update(r)
    out["centreline_point"] = np.round(c, 1).tolist()
    out["local_axis"] = np.round(tan, 4).tolist()
    out["axis_vs_plane_normal_deg"] = round(float(np.degrees(np.arccos(min(1.0, abs(float(tan @ (np.asarray(plane_normal, float) /
                                       np.linalg.norm(plane_normal)))))))), 1)
    return out


def compare():
    """our numbers against SPARC's, per page, per sided mesh, per level."""
    import numpy as np
    sp = json.loads(OUT.read_text())
    ours_ = json.loads((REPO / "data/derived/Q304_our_sciatic_calibre.json").read_text())
    lev = sp["levels"]
    rows = []
    for key, page in sorted(ours_.items()):
        for sid, rec in sorted(page["nerves"].items()):
            for lk, v in sorted(rec["levels"].items()):
                sd, sh = lk.split(":")
                if sh == "unavailable":
                    continue
                ref = lev["left" if sd == "l" else "right"].get(sh)
                if not ref or v.get("eq_diameter_mm") is None:
                    rows.append(dict(page=key, id=sid, side=sd, level=sh,
                                     ours_mm=v.get("largest_piece_eq_diameter_mm") or v.get("eq_diameter_mm"),
                                     sparc_mm=(ref or {}).get("eq_diameter_window_mean_mm"), diff_mm=None, ratio=None,
                                     pieces=v.get("pieces", 0)))
                    continue
                o = v.get("largest_piece_eq_diameter_mm") or v["eq_diameter_mm"]
                r = ref["eq_diameter_window_mean_mm"]
                rows.append(dict(page=key, id=sid, side=sd, level=sh, ours_mm=o, sparc_mm=r,
                                 diff_mm=round(o - r, 2), ratio=round(o / r, 3), pieces=v["pieces"],
                                 ours_all_pieces_mm=v.get("eq_diameter_mm"),
                                 oblique_mm=v.get("oblique_eq_diameter_mm"),
                                 band_half_mm=v.get("band_half_mm"), sparc_sample=ref["sample"]))
    good = [r for r in rows if r["ratio"]]
    out = dict(doi=DOI, license="CC BY 4.0", n_comparisons=len(good), rows=rows,
               summary=dict(ratio_median=round(float(np.median([r["ratio"] for r in good])), 3),
                            ratio_min=min(r["ratio"] for r in good), ratio_max=max(r["ratio"] for r in good),
                            diff_median_mm=round(float(np.median([r["diff_mm"] for r in good])), 2),
                            diff_min_mm=min(r["diff_mm"] for r in good), diff_max_mm=max(r["diff_mm"] for r in good)))
    by = {}
    for r in good:
        by.setdefault(r["page"], []).append(r["ratio"])
    out["by_page_ratio_median"] = {k: round(float(np.median(v)), 3) for k, v in sorted(by.items())}
    byl = {}
    for r in good:
        byl.setdefault(r["level"], []).append(r["ratio"])
    out["by_level_ratio_median"] = {k: round(float(np.median(v)), 3) for k, v in sorted(byl.items())}
    p = REPO / "data/derived/Q304_sparc692_comparison.json"
    p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
    print("->", p)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["fetch", "measure", "ours", "compare"])
    ap.add_argument("--dl", default="/dev/shm/q304_sparc")
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--src", default=None)
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(Path(a.dl))
    elif a.cmd == "measure":
        measure(Path(a.dl))
    elif a.cmd == "ours":
        ours(a.keys or None, a.src)
    else:
        compare()


if __name__ == "__main__":
    main()
