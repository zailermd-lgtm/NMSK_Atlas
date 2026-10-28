"""Q292 validation: the shipped Base · Female breasts / pelvis against cited literature dimensions, non-penetration, and mesh realness.

    python3 scripts/anatomy/q292/build_q292.py measure --page DIR      # DIR = page dir viewer_base_female -> data/derived/Q292_validation.json

Landmarks are geometric rules on this page's meshes (stated per value), not hand-placed osteometric points. Frame: mm, +X subject right, +Y up, +Z anterior.
Literature (PubMed abstracts read in Q292; full list in docs/research/Q292_female_breast_pelvis_sources.md):
  breast  : SN-N 19.8 cm, N-N 20.3 cm, N-IMF 7.7 cm (Al-Qattan 2019, doi:10.1097/GOX.0000000000002326, 54 nulliparous women 20-25 y);
            SN-N 21.9 / 22.3 cm, N-N 21.7 cm (Archibong 2022, doi:10.4103/jwas.jwas_81_22, 370 women 18-32 y);
            IMF over the 5th-6th rib interspace (doi:10.1016/j.bjps.2023.04.020, 60 chests); medial fascial border 2.1 cm lateral to the
            sternal border (MRI) / 4.8 cm from the midline (cadaver); lateral border 3.9 cm (MRI) / 4.5 cm (cadaver) medial to latissimus
            dorsi (doi:10.1097/PRS.0000000000011550); pectoralis major width / breast width 0.82-0.85 (doi:10.1002/ca.22834);
            volume: cohort means 637-771 mL (doi:10.1007/s12282-024-01647-6; doi:10.1007/s00266-026-06058-w).
  pelvis  : MR pelvimetry (vaginal-delivery group, doi:10.1016/j.ejrad.2018.03.024): inlet transverse 134.7 +- 7.5, obstetric conjugate
            126.9 +- 8.3, interspinous 113.4 +- 8.2, intertuberous 127.1 +- 10.4 mm; subpubic angle F 87.4 +- 6.5 deg (PMID 32274246);
            uterus 37.1 mL (> 5 y postmenopausal) / 60.1 mL (<= 5 y) (PMID 9676090); vagina cervix-introitus 62.7 mm (doi:10.1093/humrep/del022);
            ovary 2.6 cm3 (50-59 y) / 1.0 cm3 (60-69 y) (doi:10.1006/gyno.2000.5783); urethra 22 +- 3 mm (nulliparous pregnant,
            doi:10.1016/j.ejrad.2010.08.046) to 37.9 +- 4.7 mm (doi:10.1038/s41598-026-35587-2); perineal body 21.7 +- 4.9 mm
            (doi:10.1093/asjof/ojaf072); cardinal ligament 59 +- 9 mm, deep uterosacral 36 +- 11 mm at rest (doi:10.1007/s00192-013-2211-y).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts/anatomy/q219")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import geomlib as GL  # noqa: E402
import lib292 as L  # noqa: E402
from scripts.anatomy.q233 import dimorphism as DM  # noqa: E402

OUT = REPO / "data/derived/Q292_validation.json"
CVH_REF = ["22_Bartholin_s_gland.ply", "37_Bulbospongiosus_muscle.ply", "24_Perineal_body.ply"]


def dihedral(v, f):
    m = trimesh.Trimesh(v, f, process=True)
    if len(m.face_adjacency) == 0:
        return None
    a = np.degrees(m.face_adjacency_angles)
    return dict(mean_deg=round(float(a.mean()), 1), std_deg=round(float(a.std()), 1), faces=int(len(m.faces)))


def pca_len(v):
    c = v - v.mean(0); e = np.linalg.svd(c, full_matrices=False)[2][0]; t = c @ e
    return float(t.max() - t.min())


def rib_y_at(B, name, x, side):
    k = f"zan_{name}_rib_{side}"
    if k not in B:
        return None
    v = B[k][0]; m = (np.abs(v[:, 0] - x) < 6) & (v[:, 2] > 20)
    return float(np.median(v[m, 1])) if m.any() else None


def breast_metrics(B):
    out = {}
    st = B["sternum"][0]; top = st[st[:, 1] > st[:, 1].max() - 4]; SN = np.array([0.0, st[:, 1].max(), float(top[:, 2].max())])
    out["sternal_notch_rule"] = "top of the sternum mesh, its most anterior point, x = 0"
    wall = [k for k in B if re.search(r'_rib_[lr]$|costal_cartilage|^sternum$|intercostal_(muscles|membrane)', k)]
    apex = {}
    ribs = ["second", "third", "fourth", "fifth", "sixth", "seventh"]
    for s in "lr":
        V, F = B["breast_ct_" + s][:2]; lo = V.min(0) - 40; hi = V.max(0) + 40
        sw = L.SDF([B[k][:2] for k in wall if (B[k][0].max(0) > lo).all() and (B[k][0].min(0) < hi).all()], lo, hi, fill=True)
        h = -sw.at(V); a = V[np.argmax(V[:, 2])]; apex[s] = a      # nipple proxy: the most anterior point of the breast (no nipple object)
        foot = V[h < 12]
        sg = 1 if s == "r" else -1
        medial = float(np.abs(foot[:, 0]).min()); lateral = float(np.abs(foot[:, 0]).max())
        top_y, bot_y = float(foot[:, 1].max()), float(foot[:, 1].min())
        xc = float(np.median(foot[:, 0]))
        levels = {r: rib_y_at(B, r, xc, s) for r in ribs}
        def level(y):
            above = [r for r in ribs if levels[r] is not None and levels[r] >= y]
            below = [r for r in ribs if levels[r] is not None and levels[r] < y]
            return (f"between the {above[-1]} and {below[0]} ribs" if above and below else (f"below the {above[-1]} rib" if above else f"above the {below[0]} rib"))
        ld = B.get("latissimus_dorsi_" + s)
        ldx = None
        if ld is not None:
            lv = ld[0]; m = (np.abs(lv[:, 1] - (top_y + bot_y) / 2) < 30) & (lv[:, 2] > -40)
            ldx = float(np.abs(lv[m, 0]).min()) if m.any() else None
        pm = [B[k][0] for k in B if "pectoralis_major" in k and k.endswith("_" + s)]
        pmv = np.vstack(pm); mid = (np.abs(pmv[:, 1] - (top_y + bot_y) / 2) < 15)
        pm_w = float(np.ptp(pmv[mid, 0])) if mid.any() else None
        width = lateral - medial
        sternal_edge = float(np.abs(st[:, 0]).max())
        out[s] = dict(volume_cm3=round(L.mesh_volume(V, F), 1),
                      apex_nipple_proxy=np.round(a, 1).tolist(), apex_rule="most anterior breast vertex (supine shape; no nipple object)",
                      projection_max_above_rib_cage_mm=round(float(h[np.abs(V[:, 0]) < 125].max()), 1),
                      footprint_rule="breast vertices within 12 mm of the rib cage (ribs, cartilages, sternum, intercostal layers)",
                      footprint_superior_y=round(top_y, 1), footprint_inferior_imf_y=round(bot_y, 1), footprint_height_mm=round(top_y - bot_y, 1),
                      footprint_medial_from_midline_mm=round(medial, 1), footprint_medial_from_sternal_edge_mm=round(medial - sternal_edge, 1),
                      footprint_lateral_from_midline_mm=round(lateral, 1), base_width_mm=round(width, 1),
                      superior_border_level=level(top_y), imf_level=level(bot_y), rib_anterior_y_at_breast_centre=levels,
                      lateral_border_to_latissimus_mm=round(ldx - lateral, 1) if ldx else None,
                      pectoralis_major_width_over_breast_width=round(pm_w / width, 2) if pm_w else None,
                      sn_to_apex_mm=round(float(np.linalg.norm(a - SN)), 1),
                      apex_to_imf_mm=round(float(np.linalg.norm(a - min(V[np.abs(V[:, 0] - a[0]) < 15], key=lambda p: p[1]))), 1),
                      imf_rule="lowest breast vertex within 15 mm of the apex's x")
        fv, ff = B["breast_fgt_ct_" + s][:2]
        out[s]["fgt_volume_cm3"] = round(L.mesh_volume(fv, ff), 1)
        out[s]["volumetric_glandular_fraction_pct"] = round(100 * L.mesh_volume(fv, ff) / L.mesh_volume(V, F), 1)
    out["apex_to_apex_mm"] = round(float(np.linalg.norm(apex["l"] - apex["r"])), 1)
    out["sternal_notch"] = np.round(SN, 1).tolist()
    return out


def pelvis_metrics(B):
    S = [{"id": k, "sys": c, "v": v, "f": f} for k, (v, f, c) in B.items() if c == "bone"]
    out = {}
    out.update(DM.inlet(S)); out.update({k: v for k, v in DM.outlet_and_subpubic(S).items() if not k.startswith("tuber")})
    L_, hl, hr, sa = DM.pelvis_landmarks(S)
    # ischial spines: on each hip bone, the most medial vertex of the posterior half within 20-70 mm above the ischial tuberosity
    sp = []
    for h in (hl, hr):
        v = h.vertices; ty = v[:, 1].min()
        zmid = np.median(v[:, 2])
        m = (v[:, 1] > ty + 20) & (v[:, 1] < ty + 70) & (v[:, 2] < zmid)
        c = v[m]; sp.append(c[np.argmin(np.abs(c[:, 0]))])
    out["interspinous_mm"] = round(float(abs(sp[0][0] - sp[1][0])), 1)
    out["interspinous_rule"] = "most medial hip-bone vertex of its posterior half, 20-70 mm above the ischial tuberosity, each side"
    # obstetric conjugate: promontory to the nearest point of the posterior surface of the symphysis
    P = L_["P"]; pub = np.vstack([hl.vertices, hr.vertices]); near = pub[np.abs(pub[:, 0]) < 12]
    out["obstetric_conjugate_mm"] = round(float(np.linalg.norm(near - P, axis=1).min()), 1)
    org = {}
    for k in ["uterus_cryo_vhf", "urinary_bladder", "rectum", "sigmoid_colon", "vagina", "ovary_l", "ovary_r", "urethra_female_lumen", "perineal_body",
              "cardinal_ligament_uterus_l", "cardinal_ligament_uterus_r", "uterosacral_ligament_l", "uterosacral_ligament_r", "external_anal_sphincter_ct_vhf"]:
        if k in B:
            v, f = B[k][:2]
            try:
                vol = round(L.mesh_volume(v, f), 2)
            except Exception:
                vol = None
            org[k] = dict(volume_cm3=vol, long_axis_mm=round(pca_len(v), 1), extent_mm=np.round(np.ptp(v, 0), 1).tolist())
    out["organs"] = org
    return out


def realness(B, ids):
    ref = {}
    for n in CVH_REF:
        m = trimesh.load(REPO / "third_party/cvh_wu2015/meshes" / n, process=False)
        ref[n] = dihedral(np.asarray(m.vertices), np.asarray(m.faces))
    shipped = {k: dihedral(*B[k][:2]) for k in ids if k in B}
    return dict(cvh_reference=ref, shipped=shipped)


def run(page):
    page = Path(page)
    B = {k: (d["v"], d["f"], d["cat"]) for k, d in GL.load_zan(page / "atlas_viewer_base_female.html").items()}
    prep = json.loads((REPO / "data/derived/Q292_page_report.json").read_text())
    ids = prep["added"] + [k for k in prep["replaced"] if k.startswith("zan_skin_")][:6] + ["zan_sternocostal_head_of_pectoralis_major_muscle_l"]
    res = {"_README": ["Q292 validation of the Base · Female page; scripts/anatomy/q292/measure_q292.py"],
           "breast": breast_metrics(B), "pelvis": pelvis_metrics(B), "realness_dihedral": realness(B, ids)}
    OUT.write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    print(json.dumps(res, indent=1, default=float)[:6000])
