"""Q258: the PROXIMAL brachial plexus (roots C5-T1, trunks, divisions, cords) for the two own pages (Imaging-based F/M).
build(key) -> list of dict(id, name, latin, side, V, F, d, report, status, held, rec) -- same shape as q249's rule_nerves output,
consumed by collect258.py / build_pages.py the same way.

Method (same family as Q249's pelvic nerves, Q248's ligaments): a smooth spline through waypoints measured on THIS page's own
cervical/T1 vertebrae, scalenus anterior / medius (the owner's named interscalene location), clavicle and pectoralis minor
(scripts/anatomy/q258/neck_lm.py), pushed clear of bone (clearance = radius + 0.3 mm), round tube (nervelib.tube_round),
closed end caps.  No geometry is taken from a segmentation or from Z-Anatomy.  The final 20-35 % of each cord's course is
pulled toward the proximal end of the ALREADY-SHIPPED terminal nerve it anatomically continues into (median_n_lateral_root
for the lateral cord, ulnar_n for the medial cord, radial_n for the posterior cord) purely for visual continuity -- those
nerves are themselves Z-Anatomy per-bone transfers (position estimate), so this is a soft blend (not a hard snap) and is
reported per cord.

Sources (same as data/nerves/brachial_plexus.json): Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.7;
Moore, Dalley, Agur, Clinically Oriented Anatomy, 8th ed., brachial plexus chapter; Terminologia Anatomica (FICAT 1998).
Diameters are a MODELLING CHOICE (no page-specific calibre measurement exists for this unsegmented deep structure), matched
to the THIN, STYLISED mesh convention the Z pages already ship for this same plexus (brachial_trunk_superior_l measures
~3.0 mm, brachial_cord_posterior_l ~2.0 mm as shipped there -- real calibre is larger, but named trunks/cords are promoted
to calibre level 1 regardless of mesh diameter, Q240's own convention): root ~2.2-2.6 mm, trunk ~2.5-2.8 mm, division
~2.1-2.4 mm, cord ~2.2-2.9 mm -- not a specific cited caliper study, stated plainly rather than inventing one.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts/anatomy/q248"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q249"))
import neck_lm as NK                 # noqa: E402
import nervelib as NL                # noqa: E402
import guards as GD                  # noqa: E402

SOURCE = ("Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.7; Moore KL, Dalley AF, Agur AMR, Clinically Oriented Anatomy, "
          "8th ed. -- brachial plexus chapter; Terminologia Anatomica (FICAT 1998).")
NAME = {
    "brachial_root_c5": "Ventral ramus C5", "brachial_root_c6": "Ventral ramus C6", "brachial_root_c7": "Ventral ramus C7",
    "brachial_root_c8": "Ventral ramus C8", "brachial_root_t1": "Ventral ramus T1",
    "brachial_trunk_superior": "Superior trunk", "brachial_trunk_middle": "Middle trunk", "brachial_trunk_inferior": "Inferior trunk",
    "brachial_div_superior_ant": "Superior trunk, anterior division", "brachial_div_superior_post": "Superior trunk, posterior division",
    "brachial_div_middle_ant": "Middle trunk, anterior division", "brachial_div_middle_post": "Middle trunk, posterior division",
    "brachial_div_inferior_ant": "Inferior trunk, anterior division", "brachial_div_inferior_post": "Inferior trunk, posterior division",
    "brachial_cord_lateral": "Lateral cord", "brachial_cord_medial": "Medial cord", "brachial_cord_posterior": "Posterior cord",
}
# trunk / division formation points: height above the clavicle's own superior surface (mm), + a small lateral fan
# (mm, away from the midline) reflecting the normal slight postero-lateral spread of the three trunks as they
# approach the clavicle (Moore & Dalley, Clinically Oriented Anatomy: superior trunk highest / most posterior,
# inferior trunk lowest, lying on the first rib) -- all three stay ON the same measured interscalene-gap trajectory
# (neck_lm.Neck.plexus_point), not jumped onto an unrelated clavicle-fraction track.
TRUNK_Y = {"superior": 32.0, "middle": 24.0, "inferior": 12.0}
TRUNK_FAN = {"superior": 2.0, "middle": 6.0, "inferior": 11.0}
DIV_Y = {"superior": 6.0, "middle": 2.0, "inferior": -4.0}
DIV_FAN = {"superior": 3.0, "middle": 8.0, "inferior": 14.0}
# wider, honestly-stated error band for the inferior trunk / medial cord: this page has no first-rib or axillary-artery
# mesh of its own (the real anatomical references for that part of the course), unlike the Z pages (Q247).
ERR_MM = {"superior": 8.0, "middle": 8.0, "inferior": 15.0}


def _tube(path, d0, d1, ctx):
    path = NL.push_out_bones(ctx, path, max(d0, d1) / 2.0, loops=10)
    V, F, c0, c1, d = NL.tube_round(path, d0, d1)
    V, pb = NL.finish_bones(ctx, V, F, c0, c1, iters=12, tol=0.3)
    return V, F, c0, c1, d, pb


def build(key):
    NKo = NK.Neck(key)
    ctx = NKo.ctx
    gd = GD.Guards(NKo.E)
    out = []

    for s in ("l", "r"):
        clav_y = NKo.clavicle_top_y(s)
        root_end = {}
        for lvl, trunk_of in (("c5", "superior"), ("c6", "superior"), ("c7", "middle"), ("c8", "inferior"), ("t1", "inferior")):
            p0 = NKo.vertebra_lateral(lvl, s)
            y0 = p0[1]
            trunk_origin = NKo.plexus_point(s, clav_y + TRUNK_Y[trunk_of], lateral_fan=TRUNK_FAN[trunk_of])
            p1 = NKo.gap_point(s, y0, clamp_note=f"{lvl}_{s} root")
            p_mid = NKo.gap_point(s, (y0 + trunk_origin[1]) / 2.0, clamp_note=f"{lvl}_{s} root mid")
            path = NL.spline([p0, p1, p_mid, trunk_origin], n=40)
            V, F, c0, c1, d, pb = _tube(path, 2.2, 2.6, ctx)
            rep = NL.measure_tube(ctx, gd, V, F, c0, c1, path, d, gate_soft=False, min_skin=0.0)
            rep["pushed_out_of_bone"] = pb
            rep["length_mm"] = round(NL.path_len(path), 1)
            rec = dict(method="rule-based", course=f"vertebra lateral extent -> interscalene gap (between scalenus anterior and scalenus medius, the owner's named location) -> {trunk_of} trunk origin, {TRUNK_Y[trunk_of]:.0f} mm above the clavicle's own superior surface",
                       error_band_mm=ERR_MM[trunk_of], source=SOURCE)
            out.append(dict(id=f"brachial_root_{lvl}_{s}", name=NAME[f"brachial_root_{lvl}"], latin=NAME[f"brachial_root_{lvl}"], side=s,
                             V=V, F=F, d=d, status="ship", report=rep, rec=rec, cat="nerve"))
            root_end.setdefault(trunk_of, []).append(trunk_origin)

        trunk_end = {}
        for trunk_of in ("superior", "middle", "inferior"):
            origin = np.mean(root_end[trunk_of], axis=0)
            div_origin = NKo.plexus_point(s, clav_y + DIV_Y[trunk_of], lateral_fan=DIV_FAN[trunk_of])
            path = NL.spline([origin, div_origin], n=24)
            V, F, c0, c1, d, pb = _tube(path, 2.8, 2.5, ctx)
            rep = NL.measure_tube(ctx, gd, V, F, c0, c1, path, d, gate_soft=False, min_skin=0.0)
            rep["pushed_out_of_bone"] = pb; rep["length_mm"] = round(NL.path_len(path), 1)
            rec = dict(method="rule-based", course=f"union of its root(s) -> division point {DIV_Y[trunk_of]:+.0f} mm relative to the clavicle's superior surface, along the interscalene-gap trajectory",
                       error_band_mm=ERR_MM[trunk_of], source=SOURCE)
            out.append(dict(id=f"brachial_trunk_{trunk_of}_{s}", name=NAME[f"brachial_trunk_{trunk_of}"], latin=NAME[f"brachial_trunk_{trunk_of}"], side=s,
                             V=V, F=F, d=d, status="ship", report=rep, rec=rec, cat="nerve"))
            trunk_end[trunk_of] = div_origin

        div_end = {}
        for trunk_of in ("superior", "middle", "inferior"):
            origin = trunk_end[trunk_of]
            for half, dz in (("ant", 10.0), ("post", -10.0)):
                far = origin + np.array([0.0, -22.0, dz])
                err = ERR_MM[trunk_of]
                path = NL.spline([origin, far], n=18)
                V, F, c0, c1, d, pb = _tube(path, 2.4, 2.2, ctx)
                rep = NL.measure_tube(ctx, gd, V, F, c0, c1, path, d, gate_soft=False, min_skin=0.0)
                rep["pushed_out_of_bone"] = pb; rep["length_mm"] = round(NL.path_len(path), 1)
                rec = dict(method="rule-based", course=f"{trunk_of} trunk bifurcation (at/just distal to the clavicle) -> {'anterior' if half == 'ant' else 'posterior'} division, toward the axilla",
                           error_band_mm=err, source=SOURCE)
                nid = f"brachial_div_{trunk_of}_{half}"
                out.append(dict(id=f"{nid}_{s}", name=NAME[nid], latin=NAME[nid], side=s, V=V, F=F, d=d, status="ship", report=rep, rec=rec, cat="nerve"))
                div_end[(trunk_of, half)] = far

        pm_lat = NKo.pecminor_point(s, frac=0.85, medial=False)
        pm_med = NKo.pecminor_point(s, frac=0.75, medial=True)
        pm_deep = (pm_lat + pm_med) / 2.0 + np.array([0.0, 0.0, -14.0])

        def cord(nid, origin_pts, target_pt, anchor_id, offset_frac, d0, d1):
            origin = np.mean(origin_pts, axis=0)
            anchor, full = NKo.nerve_anchor(anchor_id, s)
            end = target_pt if anchor is None else (1 - offset_frac) * target_pt + offset_frac * anchor
            path = NL.spline([origin, (origin + end) / 2.0, end], n=30)
            V, F, c0, c1, d, pb = _tube(path, d0, d1, ctx)
            rep = NL.measure_tube(ctx, gd, V, F, c0, c1, path, d, gate_soft=False, min_skin=0.0)
            rep["pushed_out_of_bone"] = pb; rep["length_mm"] = round(NL.path_len(path), 1)
            rep["continuity_target"] = dict(nerve=full, used=anchor is not None, blend_fraction=offset_frac if anchor is not None else None)
            rec = dict(method="rule-based", course="see docstring (lateral-border-of-pectoralis-minor landmark, named by position relative to the axillary artery per the cited textbooks)",
                       error_band_mm=max(ERR_MM.values()) if nid == "brachial_cord_medial" else 10.0, source=SOURCE)
            out.append(dict(id=f"{nid}_{s}", name=NAME[nid], latin=NAME[nid], side=s, V=V, F=F, d=d, status="ship", report=rep, rec=rec, cat="nerve"))

        cord("brachial_cord_lateral", [div_end[("superior", "ant")], div_end[("middle", "ant")]], pm_lat, "median_n_lateral_root", 0.4, 2.8, 2.4)
        cord("brachial_cord_medial", [div_end[("inferior", "ant")]], pm_med, "ulnar_n", 0.4, 2.6, 2.2)
        cord("brachial_cord_posterior", [div_end[("superior", "post")], div_end[("middle", "post")], div_end[("inferior", "post")]], pm_deep, "radial_n", 0.4, 2.9, 2.4)

    return out, NKo.notes
