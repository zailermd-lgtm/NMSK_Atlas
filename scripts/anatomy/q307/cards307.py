"""Q307 card text.

Three kinds of card this round writes, and nothing else:

(1) an UPPER-LIMB nerve transferred onto an Imaging page, and the three lower-limb nerves whose one-sided
    `mirror_q237` stub this round replaced. Same discipline as Q304: `method`, `error_band_mm`, a badge that
    opens by saying the structure was NOT segmented from this subject's own imaging, the source page's own badge
    quoted verbatim so the original fit's error is not lost, and a subject id the Q297 provenance audit reads.

(2) the LATERAL ANTEBRACHIAL CUTANEOUS NERVE on ALL SIX pages -- the structure the owner reported. The card
    states what Q307 measured about it, including the part that is WRONG and was not fixed: the mesh covers only
    the proximal two thirds of the forearm and has no anterior or posterior branch. Written on the card rather
    than sculpted, because no real source geometry for the missing distal third exists anywhere in this project
    (Q247's own survey: Z-Anatomy is the ceiling for licence-compatible nerve geometry and its release has no
    branch of this nerve at all), and Q297 removed a generated surface for exactly that reason.

(3) a CUTANEOUS nerve that Q307 measured inside a muscle belly deeper than the mask's own error band. The depth
    goes on its card. Nothing is moved: on the Z pages this is Z-Anatomy's own geometry and on the Imaging pages
    it is a rule-built or transferred tube, and there is no one justified direction to re-route 29 nerves without
    re-deciding their course from a source.
"""
from __future__ import annotations
import re

ZAN = ("Z-Anatomy (CC BY-SA 4.0; derived from BodyParts3D, (c) The Database Center for Life Science), the libre 3D "
       "atlas of anatomy -- third_party/z-anatomy/")
QAWASMI = ("Qawasmi F, MacLeod J, AbuHamdia A, Grindel SI, Yassin M. Anatomy of the Lateral Antebrachial Cutaneous "
           "Nerve: Landmarks for Procedures in the Cubital Fossa. J Hand Surg Am 2024;50(7):882.e1-882.e5. "
           "PMID 38934998, doi:10.1016/j.jhsa.2024.04.018 (28 fresh cadaveric upper extremities)")
KHAD = ("Khadanovich A, Benes M, Kaiser R, Herma T, Kachlik D. Clinical anatomy of the lateral antebrachial "
        "cutaneous nerve: Is there any safe zone for interventional approach? Ann Anat 2023;252:152202. "
        "PMID 38128746, doi:10.1016/j.aanat.2023.152202 (93 cadaveric forearms)")
TAGLIA = ("Tagliafico AS, Michaud J, Marchetti A, Garello I, Padua L, Martinoli C. US imaging of the "
          "musculocutaneous nerve. Skeletal Radiol 2010;40(5):609-16. PMID 20931188, doi:10.1007/s00256-010-1046-6")

WHO = {"own_m": ("his", "His"), "own_f": ("her", "Her")}
SIDEW = {"l": "left", "r": "right", "m": "midline"}


def _q195(badge):
    m = re.search(r"surface error median ([\d.]+) mm, max ([\d.]+) mm", badge or "")
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)


def is_rule(badge):
    return bool(re.match(r"\s*RULE-BASED", badge or ""))


def error_band(d):
    """the original fit's own error on the Combined page, in quadrature with THIS round's local bone residual
    (p95). Both terms stay printed in the badge so the number can be taken apart -- Q304's rule."""
    b = (d.get("rec_combined") or {}).get("procedural_badge") or ""
    med, mx = _q195(b)
    ours = float(d["local_resid"]["p95_mm"])
    if med is None:
        med = 25.0 if is_rule(b) else 8.7
    return round((med ** 2 + ours ** 2) ** 0.5, 1), med, mx, ours


def subject_of(key, d):
    body = "vhm" if key == "own_m" else "vhf"
    return (f"ct_{body}_rule_nerve_q307" if is_rule((d.get("rec_combined") or {}).get("procedural_badge") or "")
            else f"xfer_zan2{body}_nerves_q307")


def method_of(d):
    b = (d.get("rec_combined") or {}).get("procedural_badge") or ""
    if is_rule(b):
        return "rule-based tube carried from the Combined page of this body by the Q307 bone-point registration"
    if "MIRROR IMAGE" in b:
        return "Z-Anatomy mirror of the opposite side, registered onto this subject's own skeleton (not imaged here)"
    return "Z-Anatomy geometry registered onto this subject's own skeleton (not imaged here)"


def transferred_rec(key, d, reg_stats, val, pair_label, gates):
    who, Who = WHO[key]
    rc = d.get("rec_combined") or {}
    eb, med, mx, ours = error_band(d)
    rule = is_rule(rc.get("procedural_badge") or "")
    loc = d["local_resid"]
    name = rc.get("name") or d["id"].replace("zan_", "").replace("_", " ").capitalize()
    replaced = d["why"].startswith("replaced")
    origin = ("a RULE-BASED tube built on the Combined page's own landmarks" if rule
              else "a Z-Anatomy mesh fitted onto this body's own skeleton in Q195")
    if replaced:
        head = ("Q307 NOT SEGMENTED FROM THIS SUBJECT'S OWN IMAGING, AND IT REPLACES A STUB. "
                + ("RULE-BASED: " if rule else "")
                + f"Before this round the {SIDEW[d['side']]} side of this nerve on this page was a MIRROR of the "
                  f"opposite side's traced segment and only {d['why'].split('a ')[1].split(' mm')[0]} mm long, "
                  f"while the other side already carried the full nerve Q304 transferred -- so the page showed a "
                  f"full-length nerve on one side and a stub on the other UNDER THE SAME NAME, and this nerve's own "
                  f"branches hung hundreds of millimetres away from it (the plantar nerves were 436.6 mm from their "
                  f"parent on Imaging M and 370.4 mm on Imaging F). The cause is on record: Q304's selector read "
                  f"`x[\"id\"] not in oS`, so it added only the side whose id the page did not already carry. What "
                  f"stands here now is {origin}, carried onto this page from {pair_label} by one bone-point "
                  f"registration. Nothing traced on {who} own imaging was removed: the segment this body's own "
                  f"imaging DOES resolve is still on the page as its own structure, with its own badge.")
    else:
        head = ("Q307 NOT SEGMENTED FROM THIS SUBJECT'S OWN IMAGING. "
                + ("RULE-BASED: " if rule else "")
                + f"This structure is {origin}, carried onto this page from {pair_label} by one bone-point "
                  f"registration. {Who} imaging does not resolve it, so the page had no mesh of it at all before "
                  f"this round. Q307 measured the gap after the owner reported the lateral antebrachial cutaneous "
                  f"nerve as out of place: each Imaging page was missing 96 nerves the Combined page of the SAME "
                  f"body carries, 33 of them in the upper limb and shoulder girdle.")
    how = (f" REGISTRATION: identity plus a thin-plate-spline correction field fitted to closest-point "
           f"displacements on the bones the two pages share in this structure's own region "
           f"({reg_stats['kept_pairs']} bone-point pairs, {reg_stats['control_points']} control points, "
           f"{reg_stats['iters']} passes). Residual over that whole region: median {reg_stats['median_mm']} mm, "
           f"p95 {reg_stats['p95_mm']} mm, max {reg_stats['max_mm']} mm (before the fit: median "
           f"{reg_stats['before']['median_mm']}, p95 {reg_stats['before']['p95_mm']} mm). Beside THIS structure "
           f"the residual is median {loc['median_mm']} mm, p95 {loc['p95_mm']} mm, max {loc['max_mm']} mm (the "
           f"bone points within {loc['radius_mm']:.0f} mm of its own vertices, n={loc['n']}). This mesh moved "
           f"median {d['moved_median_mm']} mm, at most {d['moved_max_mm']} mm.")
    gate = (f" WHY IT WAS ALLOWED ONTO THE PAGE AT ALL: the upper limb does not correspond between these two pages "
            f"as well as the lower limb did. Measured per bone group before the correction field, the medians run "
            f"0.14-10.29 mm against Q304's lower-limb 0.79-2.79, with Imaging M's right metacarpals at median "
            f"10.29 / p95 54.87 / max 63.86 mm. So every candidate had to pass a gate on the residual beside its "
            f"OWN vertices (median <= {gates['median_mm']} mm, p95 <= {gates['p95_mm']} mm), had to not gain more "
            f"than 25 % of its volume inside this page's own bones over what it already had on the Combined page, "
            f"and had to pass on BOTH sides or neither -- a round called in to fix a one-sided nerve must not "
            f"create another. {gates['n_refused']} of {gates['n_candidates']} candidates were refused on this page "
            f"and each refusal is named with its numbers in data/derived/Q307_nerve_transfer.json.")
    err = (f" ERROR BAND +-{eb} mm = the original fit's own error ({med} mm"
           + (f", max {mx} mm" if mx else "") + f") in quadrature with this round's local residual ({ours} mm). "
           f"The original error dominates: this round carried the placement across, it did not make it better.")
    geom = (f" Volume {d['cm3']:.4f} cm3 absolute (on the Combined page {d['cm3_combined']:.4f} cm3), {d['tris']} "
            f"triangles, length {d['axis_len_mm']} mm along its own axis, mean dihedral {d['dihedral_mean_deg']} deg "
            f"(the CVH reference meshes are 31.7 / 27.6 / 29.5 deg), extent {d['bbox_mm'][0]} x {d['bbox_mm'][1]} x "
            f"{d['bbox_mm'][2]} mm.")
    if d.get("cm3_signed", 0) < 0:
        geom += (" Its triangle winding is inverted, as on the Combined page it came from (inherited, not "
                 "introduced here), so only the absolute enclosed volume above means anything.")
    ob = (val["checks"]["leaves_the_body"] or {}).get(d["id"])
    ib = (val["checks"]["in_bone_frac_over_5pct"] or {}).get(d["id"])
    checks = (" CHECKS against this page's own geometry, with Q299's validated body mask and per-bone boxes: "
              + (f"{ob['n_outside']} vertices leave the body, at most {ob['worst_mm']} mm" if ob
                 else "no vertex leaves the body")
              + "; " + (f"{100 * ib:.1f} % of its volume lies inside one of this page's bones "
                        f"({100 * (d['in_bone_frac_combined'] or 0):.1f} % on the Combined page it came from)"
                        if ib else "under 5 % of its volume lies inside any bone") + ".")
    g = d.get("guards") or {}
    parts = []
    if "skin_pull" in g:
        s = g["skin_pull"]
        parts.append("Q299's pull-inside guard was " + ("applied" if s["applied"] else
                     f"REFUSED by the mesh guard (it would have flipped {s['flipped_pct']} % of the triangles) and "
                     "the structure was left where it is"))
    if "bone_push" in g:
        s = g["bone_push"]
        parts.append((f"Q299's bone guard moved it out of this page's own bones ({100 * s['in_bone_frac_before']:.1f} % "
                      f"of its volume inside before, {100 * s['in_bone_frac_after']:.1f} % after; "
                      f"{100 * s['in_bone_frac_combined']:.1f} % on the Combined page)") if s["applied"]
                     else "Q299's bone guard was refused by the mesh guard")
    guards = (" GUARDS: " + "; ".join(parts) + ".") if parts else ""
    orig = ((" THE SOURCE PAGE'S OWN BADGE, QUOTED SO ITS ERROR IS NOT LOST: " + rc["procedural_badge"])
            if rc.get("procedural_badge") else "")
    rec = {"name": name, "folder": "nerves", "method": method_of(d), "error_band_mm": eb,
           "source": (rc.get("source") or "") + ("  Geometry: rule-built tube on the Combined page's own meshes; "
                                                 + ZAN if rule else "  Geometry: " + ZAN),
           "procedural_badge": head + how + gate + err + geom + checks + guards + orig,
           "geom_src": (f"Q307 transfer from {pair_label} by bone-point registration: {d['cm3']:.4f} cm3, "
                        f"{d['tris']} triangles, error band +-{eb} mm"
                        f"{' (RULE-BASED tube)' if rule else ' (Z-Anatomy geometry, not this body)'}")}
    for k in ("latin", "notes", "targets", "part_of"):
        if rc.get(k):
            rec[k] = rc[k]
    return rec


def lacn_note(page, per_side):
    """the Q307 paragraph on the lateral antebrachial cutaneous nerve's card, on every page that carries it."""
    if not per_side:
        return ""
    rows = []
    for s in ("l", "r"):
        m = per_side.get(s)
        if not m or not m.get("t_along_the_forearm"):
            continue
        t = m["t_along_the_forearm"]
        bits = [f"{SIDEW[s].upper()}: the mesh spans {t[0]:+.3f} to {t[1]:+.3f} of the way from the radial head to "
                f"the distal radius on this page's own radius, so it stops {100 * (1 - t[1]):.0f} % of the forearm "
                f"short of the wrist"]
        if m.get("distal_end_short_of_the_wrist_mm") is not None:
            bits[-1] += f" ({m['distal_end_short_of_the_wrist_mm']} mm)"
        if m.get("radial_coord_p50_mm") is not None:
            bits.append(f"it runs {m['radial_coord_p50_mm']:+.1f} mm radial of the radius' own axis with the ulna's "
                        f"axis at {m['ulna_axis_radial_coord_p50_mm']:+.1f} mm, so it is on the lateral side")
        if m.get("d_brachioradialis_surface_p50_mm") is not None:
            bits.append(f"its distance to the brachioradialis surface is a median "
                        f"{m['d_brachioradialis_surface_p50_mm']} mm")
        if m.get("d_musculocutaneous_nerve_mm") is not None:
            bits.append(f"its nearest approach to this page's own musculocutaneous nerve is "
                        f"{m['d_musculocutaneous_nerve_mm']} mm")
        if m.get("proximal_end_mm_distal_to_the_IEL") is not None and not m.get("nerve_crosses_the_IEL_plane", True):
            bits.append(f"its proximal end lies {m['proximal_end_mm_distal_to_the_IEL']} mm distal to the "
                        f"interepicondylar line and never crosses it")
        rows.append("; ".join(bits) + ".")
    s = (" Q307 MEASURED PLACEMENT, INCLUDING WHAT IS STILL WRONG. The owner reported this nerve as out of place. "
         "Measured against two cadaveric studies read for this round, what is RIGHT is the compartment, the side "
         "and the depth, and what is WRONG is the EXTENT. " + " ".join(rows))
    if per_side.get("l", {}).get("new_in_q307") or per_side.get("r", {}).get("new_in_q307"):
        s += (" THIS NERVE DID NOT EXIST ON THIS PAGE BEFORE Q307 -- it was 0 of the structures this page's own "
              "calibre table records as nerves -- and it is here now only because Q307 carried it from the "
              "Combined page of the same body.")
    s += (" AGAINST THE LITERATURE: " + KHAD + " found 'The medial border of the brachioradialis muscle was "
          "observed less than 1.8 mm from the LACN' and that it stays close 'within the whole length of the "
          "brachioradialis muscle', which is what the distances above show, and " + QAWASMI + " found 'It was deep "
          "to the forearm superficial fascia in all cadavers', in the same deep-fascia plane as the antebrachial "
          "vein -- so this nerve NOT lying in the subcutaneous fat is correct and is not a defect. Its parent is "
          "the musculocutaneous nerve (" + TAGLIA + ": the musculocutaneous nerve 'can be reliably identified from "
          "the axilla through the elbow, including the lateral antebrachial cutaneous (LAbC) nerve').")
    s += (" THE TWO DEFECTS THAT REMAIN, AND WHY THEY WERE NOT SCULPTED AWAY. (1) The distal third of the course "
          "is missing: the nerve should reach the wrist and the thenar region, and Khadanovich found it supplying "
          "the dorsum of the hand in 39.8 % of 93 forearms and intersecting the superficial branch of the radial "
          "nerve in 86 % of limbs. (2) It has no anterior and no posterior branch on any page, where Khadanovich "
          "found that division in 76 of 93 forearms (81.7 %), a mean 47.8 +- 34.2 mm distal to the "
          "interepicondylar line; this page carries the anterior AND posterior branches of the MEDIAL antebrachial "
          "cutaneous nerve and none for the lateral. No real source geometry for either exists in this project: "
          "Q247's own survey of 23 candidate sources concluded that Z-Anatomy is the ceiling for "
          "licence-compatible nerve geometry, and its release carries no branch of this nerve. Authoring the "
          "missing third ourselves would be sculpting, and Q297 removed a generated surface for exactly that, so "
          "it is stated here instead and put to the owner. data/derived/Q307_lacn_measurements.json carries every "
          "number and both papers' own figures.")
    return s


def in_muscle_note(page, sid, rows, cutaneous_rule):
    """the Q307 depth statement on a cutaneous nerve measured inside a muscle belly."""
    if not rows:
        return ""
    worst = sorted(rows.items(), key=lambda kv: -kv[1]["p95_mm"])
    bits = "; ".join(f"{m.replace('zan_', '').replace('_', ' ')}: {100 * r['frac']:.0f} % of its surface samples, "
                     f"p95 depth {r['p95_mm']} mm, deepest {r['max_mm']} mm" for m, r in worst[:4])
    return (" Q307 MEASURED DEPTH: this nerve's name makes it a CUTANEOUS nerve, which in Terminologia Anatomica "
            "means a nerve that pierces the deep fascia to supply skin, so it should not lie inside a muscle "
            "belly -- and part of it does. " + bits + ". Depth is measured below each muscle's OWN surface and "
            "only past that muscle's own measured mask inflation plus 2 mm, because an inside/outside flag alone "
            "calls a nerve LYING ON a muscle 'inside it': on base_m brachioradialis the voxel solid is 116.7 cm3 "
            "against the mesh's own 93.8 cm3, about one 1.5 mm voxel all round. NOT MOVED: " + cutaneous_rule +
            " data/derived/Q307_placement_" + page + ".json carries every structure's numbers.")


NOT_MOVED = ("on the Z pages this is Z-Anatomy's own geometry and on the Imaging pages it is a rule-built or "
             "transferred tube, and there is no one justified direction to re-route a nerve without re-deciding "
             "its course from a source, which this round has none for. Reported rather than papered over, the "
             "same policy Q299 took for the 16 vessels and 9 bursae that lie mostly inside a bone.")
