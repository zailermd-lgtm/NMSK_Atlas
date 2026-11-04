"""Q304 card text: what every structure this round touches says on its own card.

Two kinds of card:

(1) a lower-limb nerve TRANSFERRED onto an Imaging page. Provenance is the whole point of this round: these are
    Z-Anatomy meshes (or, for 12-18 of them, Q259 rule-built tubes) arriving on a page labelled "imaging-based".
    Each card therefore carries
      * `method`           -> rendered by both templates since Q300, as a warning tag / a "Method" row
      * `error_band_mm`    -> rendered beside it as "+-N mm"
      * a `procedural_badge` that opens by saying it was NOT segmented from this subject's own imaging
      * the Combined page's own badge quoted verbatim, so the ORIGINAL fit's error is not lost
      * the subject id -> `xfer_zan2vh{m,f}_nerves_q304` (the viewer prints "Filled from Z-Anatomy (reference
        model), fitted to this body -- not measured here") or `ct_vh{m,f}_rule_nerve_q304` for the rule-built ones
        (the viewer prints the rule-based class). Q297's audit reads the same ids, so neither can print
        "Measured on this body".

(2) the SCIATIC NERVE on all six pages, which gets the Q304 Part B calibre comparison against SPARC dataset 692
    (DOI 10.26275/1jdc-qiiv, CC BY 4.0) appended to its existing badge. No geometry is changed by that; the reason
    is stated on the card.
"""
from __future__ import annotations

import re

ZAN = ("Z-Anatomy (CC BY-SA 4.0; derived from BodyParts3D, (c) The Database Center for Life Science), the libre 3D "
       "atlas of anatomy -- third_party/z-anatomy/")
SPARC = ("SPARC dataset 692 v1, *Mapping the fascicular morphology and organization of the human sciatic nerve via "
         "high-resolution microCT imaging*, DOI 10.26275/1jdc-qiiv, CC BY 4.0, Case Western Reserve University with "
         "NIH SPARC (OT2OD025349, 75N98022C00018), VA 1I21RX005151 and AFOSR FA9550-23-F-0014; subject sub-SC001, "
         "Homo sapiens, male, 41 years, embalmed cadaver, both sciatic nerves, phosphotungstic-acid stained, microCT "
         "at 11.4 um isotropic. Required citation: the dataset, and Zhang J, Lapierre-Landry M, Kalpatthi H, "
         "Jenkins MW, Wilson DL, Pelot NA, Shoffstall AJ (2026), J Neural Eng 23, 16010, doi:10.1088/1741-2552/ae33f6. "
         "Licence text, attribution and the subject description: third_party/sparc_692_sciatic/")

WHO = {"own_m": ("his", "His", "the Visible Human male"), "own_f": ("her", "Her", "the Visible Human female")}
REGION = [
    (r"plantar|dorsal_digital|digital_branches|muscular_branches_of_deep_fibular", "foot"),
    (r"fibular|peroneal|sural|saphenous_n_medial_crural|tibial_n_branch_to_(gastrocnemius|soleus|popliteus|plantaris)|calcaneal", "leg"),
    (r"saphenous|femoral_n_branch|sciatic_n_branch|tibial_n|sciatic", "thigh"),
    (r"obturator|gluteal|genitofemoral|pudendal|lumbosacral|femoral_n", "pelvis"),
]


def region_of(sid):
    s = re.sub(r"^zan_", "", sid)
    for rx, r in REGION:
        if re.search(rx, s):
            return r
    return "lower_limb"


def _q195(badge):
    m = re.search(r"surface error median ([\d.]+) mm, max ([\d.]+) mm(?: \(n=(\d+)\))?", badge or "")
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)


def is_rule(badge):
    return bool(re.match(r"\s*RULE-BASED", badge or ""))


def error_band(d):
    """the honest total: the ORIGINAL fit's own error on the Combined page, in quadrature with THIS round's local
    bone-registration residual (p95). Both terms are printed in the badge, so the number can be taken apart."""
    b = (d.get("rec_combined") or {}).get("procedural_badge") or ""
    med, mx = _q195(b)
    ours = float(d["local_resid"]["p95_mm"])
    if med is None:
        med = 25.0 if is_rule(b) else 8.7      # a Q259 rule tube states its own waypoint bound (about 25 mm);
    return round((med ** 2 + ours ** 2) ** 0.5, 1), med, mx, ours


def method_of(d):
    b = (d.get("rec_combined") or {}).get("procedural_badge") or ""
    if is_rule(b):
        return "rule-based tube (Q259) carried from the Combined page of this body by the Q304 bone-point registration"
    if "MIRROR IMAGE" in b:
        return "Z-Anatomy mirror of the opposite side, registered onto this subject's own skeleton (not imaged here)"
    return "Z-Anatomy geometry registered onto this subject's own skeleton (not imaged here)"


def subject_of(key, d):
    body = "vhm" if key == "own_m" else "vhf"
    return (f"ct_{body}_rule_nerve_q304" if is_rule((d.get("rec_combined") or {}).get("procedural_badge") or "")
            else f"xfer_zan2{body}_nerves_q304")


def transferred_rec(key, d, reg_stats, val, pair_label):
    """the card of one transferred nerve."""
    who, Who, body = WHO[key]
    rc = d.get("rec_combined") or {}
    eb, med, mx, ours = error_band(d)
    rule = is_rule(rc.get("procedural_badge") or "")
    v = val["structures"].get(d["id"], {})
    loc = d["local_resid"]
    name = rc.get("name") or d["id"].replace("zan_", "").replace("_", " ").capitalize()
    origin = ("a Q259 RULE-BASED tube built on the Combined page's own landmarks" if rule
              else "a Z-Anatomy mesh fitted onto this body's own skeleton in Q195")
    head = ("Q304 NOT SEGMENTED FROM THIS SUBJECT'S OWN IMAGING. "
            + ("RULE-BASED: " if rule else "")
            + f"This structure is {origin}, carried onto this page from {pair_label} by one bone-point "
              f"registration. {Who} imaging does not resolve it, so the page had no mesh of it at all before this "
              f"round (Q299 measured the gap: the two Imaging pages carried 0 fibular / peroneal nerves against 24 "
              f"on each Z page, and 71 lower-limb nerves fewer than the Combined page of the same body).")
    how = (f" REGISTRATION: identity plus a thin-plate-spline correction field fitted to closest-point "
           f"displacements on the bones the two pages share in the lower limb and the lumbar spine "
           f"({reg_stats['kept_pairs']} bone-point pairs over {reg_stats.get('bone_groups', 0)} bone groups, "
           f"{reg_stats['control_points']} control points, {reg_stats['iters']} passes). Bone-surface residual over "
           f"the whole lower limb: median {reg_stats['median_mm']} mm, p95 {reg_stats['p95_mm']} mm, max "
           f"{reg_stats['max_mm']} mm (before the fit: median {reg_stats['before']['median_mm']}, p95 "
           f"{reg_stats['before']['p95_mm']} mm -- the Combined page was already fitted to this skeleton, which is "
           f"why the correction is small). Beside THIS structure the residual is median {loc['median_mm']} mm, "
           f"p95 {loc['p95_mm']} mm, max {loc['max_mm']} mm (the bone points within {loc['radius_mm']:.0f} mm of its "
           f"own vertices, n={loc['n']}). This mesh itself moved median {d['moved_median_mm']} mm, at most "
           f"{d['moved_max_mm']} mm.")
    err = (f" ERROR BAND +-{eb} mm = the original fit's own error ({med} mm"
           + (f", max {mx} mm" if mx else "") + ") in quadrature with this round's local residual "
           f"({ours} mm). The original error dominates: this round did not make the placement better than the "
           f"Combined page's fit, it carried it across without adding much.")
    geom = (f" Volume {abs(d['cm3']):.4f} cm3 (on the Combined page {abs(d['cm3_combined']):.4f} cm3), "
            f"{d['tris']} triangles, mean dihedral {d['dihedral_mean_deg']} deg (the CVH reference meshes are "
            f"31.7 / 27.6 / 29.5 deg), defect edges {v.get('defect_edges_pct', 0)} %, extent "
            f"{d['bbox_mm'][0]} x {d['bbox_mm'][1]} x {d['bbox_mm'][2]} mm.")
    if d["cm3"] < 0:
        geom += (" Its triangle winding is inverted, exactly as on the Combined page it came from (an inherited "
                 "property of that mesh, not introduced here); the volume above is the absolute value.")
    checks = (f" CHECKS against this page's own geometry (Q299's validated body mask and per-bone boxes): "
              f"{v.get('out_n', 0)} of {v.get('n_samples', 0)} surface samples outside the body"
              + (f", at most {v.get('out_max_mm')} mm" if v.get("out_n") else "")
              + f"; {v.get('bone_in_n', 0)} inside a bone"
              + (f", at most {v.get('bone_depth_max_mm')} mm deep ({', '.join(b[0] for b in (v.get('bones') or [])[:3])})"
                 if v.get("bone_in_n") else "") + ".")
    g = d.get("guards") or {}
    if g:
        parts = []
        if "skin_pull" in g:
            s = g["skin_pull"]
            parts.append("the Q299 pull-inside guard was " + ("applied" if s["applied"] else
                         "REFUSED by the mesh guard (it would have flipped %.2f %% of the triangles) and the "
                         "structure was left where it is" % s["flipped_pct"]))
        if "bone_push" in g:
            s = g["bone_push"]
            parts.append("the Q299 bone guard moved it out of this page's own bones (%.1f %% of its volume inside "
                         "before, %.1f %% after; on the Combined page %.1f %%)"
                         % (100 * s["in_bone_frac_before"], 100 * s["in_bone_frac_after"], 100 * s["in_bone_frac_combined"])
                         if s["applied"] else "the bone guard was refused by the mesh guard")
        how2 = " GUARDS: " + "; ".join(parts) + "."
    else:
        how2 = ""
    dup = d.get("already_on_page_same_nerve") or []
    dups = ""
    if dup and v.get("duplicates"):
        bits = "; ".join(f"{o['id']} -- {o['within_3mm_pct']} % of this mesh's surface within 3 mm of it, "
                         f"nearest {o['min_mm']} mm, median separation {o['median_mm']} mm" for o in v["duplicates"])
        dups = (f" THIS PAGE ALSO CARRIES {', '.join(dup)} for the same nerve, from {who} own imaging. The two are "
                f"measured against each other rather than assumed to be duplicates: {bits}. They are kept as two "
                f"separate structures because they are two different statements about the same nerve -- one traced "
                f"on this body, one Z-Anatomy's course fitted to this body.")
    orig = (" THE SOURCE PAGE'S OWN BADGE, QUOTED SO ITS ERROR IS NOT LOST: " + (rc.get("procedural_badge") or "")) \
        if rc.get("procedural_badge") else ""
    rec = {"name": name, "folder": "nerves", "region": region_of(d["id"]),
           "method": method_of(d), "error_band_mm": eb,
           "source": (rc.get("source") or "") + ("  Geometry: " + ZAN if not rule else "  Geometry: rule-built tube (Q259) on the Combined page's own meshes; " + ZAN),
           "procedural_badge": head + how + err + geom + checks + how2 + dups + orig,
           "geom_src": (f"Q304 transfer from {pair_label} by bone-point registration: "
                        f"{abs(d['cm3']):.4f} cm3, {d['tris']} triangles, error band +-{eb} mm"
                        f"{' (RULE-BASED tube, Q259)' if rule else ' (Z-Anatomy geometry, not this body)'}")}
    for k in ("latin", "notes", "targets", "part_of"):
        if rc.get(k):
            rec[k] = rc[k]
    return rec


def sciatic_note(page, rows, levels):
    """the Q304 Part B paragraph appended to a sciatic nerve's badge on any page."""
    if not rows:
        return ""
    def fmt(r):
        return (f"{r['side'].upper()} {r['level']}: ours {r['ours_mm']} mm against "
                f"{r['sparc_mm']} mm ({'+' if r['diff_mm'] >= 0 else ''}{r['diff_mm']} mm, x{r['ratio']})")
    body = "; ".join(fmt(r) for r in rows if r.get("ratio"))
    miss = [f"{r['side'].upper()} {r['level']}" for r in rows if not r.get("ratio")]
    s = (" Q304 CALIBRE VALIDATED AGAINST A REAL MEASURED HUMAN SCIATIC NERVE, GEOMETRY UNCHANGED. "
         + SPARC +
         " Only the CALIBRE is used and never the shape: Q302 measured why -- the six samples are about 9 cm "
         "segments that were excised and laid straight in the scanner (the traced centreline of SCL2 spans 84.76 mm "
         "axially with an 85.09 mm arc length and 1.0 x 1.3 mm of lateral wander), so the dataset carries no in-body "
         "trajectory at all. The quantity compared is the one SPARC reports, the equivalent diameter 2*sqrt(area/pi) "
         "of a cross-section cut perpendicular to the nerve's own local axis, at the dataset's own bone-referenced "
         "levels (formation from the sacral roots, the level of the lesser trochanter of the femur, and +7 / +14 / "
         "+21 cm below it), placed on THIS page's own femur and sacrum by one geometric rule used identically on all "
         "six pages. On this page: " + body + ".")
    if miss:
        s += (" Not measurable on this page's own mesh at " + ", ".join(miss) +
              " (the mesh does not reach that level).")
    s += (" THE GEOMETRY WAS DELIBERATELY NOT CHANGED. Two reasons, both stated rather than assumed: the SPARC "
          "specimen is an embalmed, phosphotungstic-acid-stained, EXCISED nerve, so fixation and staining shrinkage "
          "make it a lower bound on a living nerve's calibre -- rescaling our mesh to match it would swap one bias "
          "for another; and it is one subject (n=1), while this mesh's calibre would have to be rescaled along its "
          "whole course, which is a sculpting operation and not a measurement. What the comparison does establish is "
          "recorded here instead: in the mid and distal thigh (+7 / +14 / +21 cm below the lesser trochanter) our "
          "sciatic nerve is within about a quarter of the measured calibre, and at the proximal levels (formation "
          "and the lesser trochanter) it is 1.4 to 2.3 times too thick on the Z-Anatomy pages. "
          "data/derived/Q304_sparc692_comparison.json carries every number.")
    return s
