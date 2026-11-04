#!/usr/bin/env python3
"""Q308: the card text for every structure this round builds, and the corrections to three cards that deny
tissue which is on the screen.

Every built card carries, in words: that it is RULE-BASED, its volume, the measured numbers, the literature
they are compared against with PMID / DOI, the declared modelling choices, where the literature disagrees, the
gates it passed, and the comparison against other 3-D models. Nothing here claims "Measured on this body".
"""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import lit308 as L  # noqa: E402

SIDE_WORD = {"l": "left", "r": "right", "m": "midline"}
SUBJ = "rule_q308"
FAMILY = {
 "coracoacromial_ligament": "cal",
 "lacn_anterior_branch": "lacn_a",
 "lacn_posterior_branch": "lacn_p",
 "psoas_minor": "psoas",
 "anterolateral_ligament": "all",
}


def _cite(key):
    c = L.CITE[key]
    ident = f"PMID {c['pmid']}" if c.get("pmid") else ""
    if c.get("doi"):
        ident += (", " if ident else "") + "doi:" + c["doi"]
    elif c.get("doi_note"):
        ident += (" (" + c["doi_note"] + ")") if ident else c["doi_note"]
    return f"{c['cite']} [{ident}]"


def _common_tail(st, fam_keys, model_line):
    g = st.get("gates") or {}
    gl = "; ".join(f"{k} = {v[0]} (allowed {v[1]}..{v[2]})" for k, v in sorted(g.items())) if g else "n/a"
    return (f" VOLUME {st['volume_cm3']} cm3 (the mesh's own closed volume; checked against the independent "
            f"analytic volume {st.get('volume_analytic_cm3')} cm3, relative difference "
            f"{st.get('volume_mesh_vs_analytic_rel')}, which is a GATE -- a mesh whose two volumes disagree is "
            f"self-intersecting and is refused). {st['tris']} triangles, watertight={st['watertight']}, "
            f"dihedral mean {st['dihedral_mean_deg']} deg / median {st['dihedral_median_deg']} / max "
            f"{st['dihedral_max_deg']} (a procedural tube is smoother than a segmented surface, so this is "
            f"BELOW the CVH references 31.7 / 27.6 / 29.5 deg and is not meant to match them). "
            f"GATES PASSED: {gl}. "
            f"BONE: non-penetration is a signed SURFACE distance; a watertight bone uses the exact mesh "
            f"distance, a non-watertight bone (every bone of Imaging M, and the Z scapula) uses a voxel mask "
            f"whose own inflation was measured from the bone's own surface samples and a point counts as inside "
            f"only beyond offset + 2 mm -- Q299's instrument with Q307's correction, because signed distance on "
            f"an open mesh is invalid and once reported a psoas minor 93 mm inside a hip bone. "
            f"SOURCES: " + " | ".join(_cite(k) for k in fam_keys) + ". "
            f"AGAINST OTHER 3-D MODELS: {model_line} "
            f"AGAINST THE FIGURES IN THOSE PAPERS: not done, and not guessed -- PubMed Central does not resolve "
            f"from the build session and the full-text channel strips figure captions, so no figure could be "
            f"scaled and NO number here comes from one (data/derived/Q308_figure_comparison.json). "
            f"NOT measured on this body. data/derived/Q308_built_structures.json carries every number.")


def cal_rec(key, side, st):
    lr = SIDE_WORD[side]
    badge = (
      f"RULE-BASED (Q308): no source we hold has a mesh of the coracoacromial ligament -- it is absent from the "
      f"pinned Z-Anatomy catalogue (3,572 objects), from HRA / CCF's mesh nodes, and from every other model this "
      f"project can reach -- so it is BUILT on this page's own {lr} scapula. Both attachments are found by a "
      f"geometric rule on that scapula: the ACROMION is the most lateral vertex of its superior quarter and the "
      f"CORACOID the most anterior; the ligament's medial attachment is the coracoid's LATERAL BORDER, so the "
      f"band's medial end is the point of that border nearest the acromial attachment -- a tip-to-tip span "
      f"measures 58.4 mm on Base M, about twice the literature, which is how the first rule was found to be "
      f"wrong. Attachment pair used: {st.get('attachment_pair_used')}. "
      f"MEASURED length {st['length_mm']} mm (chord {st['chord_mm']} mm) against von Schroeder 2001's "
      f"27 +- 5 mm on 30 scapulas and Hu 2009's 28.91 +- 5.56 (medial band) / 31.90 +- 4.21 mm (lateral band) "
      f"on 9 shoulders -- the length here is an OUTPUT of the page's own bone, not an input, and it is GATED to "
      f"{st['gate_band_mm'][0]}-{st['gate_band_mm'][1]} mm (von Schroeder -2 SD to Hu +2 SD); on Imaging M no "
      f"coracoid/acromion pair fell inside that band and the ligament was REFUSED on both sides rather than "
      f"shipped on one. Width {st['width_coracoid_mm']} mm at the coracoid tapering to {st['width_acromion_mm']} "
      f"mm at the acromion and thickness {st['thickness_mm']} mm are Hu 2009's own calipers; the ELLIPTICAL "
      f"CROSS-SECTION is a DECLARED MODELLING CHOICE (Q248's precedent), not a measurement. "
      f"{st.get('path_points_cleared_of_scapula', 0)} path points were cleared of the scapula and "
      f"{st.get('rings_lifted', 0)} rings lifted; the mid-section clears the bone by "
      f"{st['min_signed_dist_to_scapula_after_mm']} mm and the attachment footprints sit "
      f"{st.get('attachment_depth_in_scapula_mm')} mm into it, which is what an attachment IS and is reported "
      f"apart from penetration."
      + _common_tail(st, ["vonschroeder2001", "hu2009", "nicholson1996"],
                     "NO reachable model holds it -- not Z-Anatomy's 3,572 objects, not HRA / CCF's mesh nodes, "
                     "not BodyParts3D's 1,524 parts, not CVH, not the SPL atlases. That is why it was built "
                     "rather than imported. Zygote and BioDigital are licence-blocked and were not used."))
    return {"name": f"Coracoacromial ligament ({lr}) -- rule-based",
            "latin": "Ligamentum coracoacromiale", "folder": "ligament", "region": "shoulder",
            "source": "RULE-BASED from cited cadaveric morphometry; " + "; ".join(
                _cite(k) for k in ("vonschroeder2001", "hu2009", "nicholson1996")),
            "origin": f"scapula_{side}: lateral border of the coracoid process",
            "insertion": f"scapula_{side}: anterior undersurface of the acromion",
            "procedural_badge": badge,
            "geom_src": f"RULE-BASED (Q308) on this page's own {lr} scapula; volume {st['volume_cm3']} cm3"}


def lacn_rec(key, side, st, which):
    lr = SIDE_WORD[side]
    nm = "Anterior" if which == "anterior" else "Posterior"
    badge = (
      f"RULE-BASED (Q308): the {which} branch of the lateral antebrachial cutaneous nerve. The OWNER reported "
      f"this nerve as being in the wrong place; Q307 measured that its trunk stops 53.8-73.5 mm short of the "
      f"distal radius and that NO page carried either of its branches, while Khadanovich 2023 found the "
      f"division in 76 of 93 forearms (81.7 %) and Qawasmi 2024 found two branches in 82.1 % of 28 limbs "
      f"(17.9 % had a single branch -- so in roughly one forearm in six this division does not exist at all). "
      f"BUILT, not imported: no reachable model holds either branch. The division point is placed on THIS "
      f"page's own lateral antebrachial cutaneous nerve centreline, {st['division_distal_to_iel_mm']} mm distal "
      f"to the interepicondylar line built from THIS page's own humeral condyles, against Khadanovich's "
      f"47.8 +- 34.2 mm -- and that +- 34.2 mm standard deviation spans 13.6 to 82.0 mm, so the single "
      f"position drawn here is the MEAN of a very wide distribution and a given forearm may divide anywhere "
      f"along it. The branch then follows {st['rail']} and ends {st['short_of_distal_radius_mm']} mm short of "
      f"the distal radius (t {st['t_start_on_radius']} to {st['t_end_on_radius']} on the radius' own axis), "
      f"which is what closes Q307's finding. Khadanovich measured the nerve «less than 1.8 mm» from the "
      f"brachioradialis' medial border along the whole muscle; this branch's median distance to that border is "
      f"{st['d_br_medial_border_p50_mm']} mm"
      + (" -- LARGER than that 1.8 mm, and the reason is measured: the branch must simultaneously stay OUT of "
         "the muscle belly (a cutaneous nerve does not lie inside a muscle, Q307 section 5) and be "
         "subcutaneous, «deep to the forearm superficial fascia» in all of Qawasmi's cadavers, so its offset "
         "was turned outward from the radius' axis to satisfy both and that increased its distance from the "
         "border. This is a stated DISCREPANCY, not a match."
         if which == "anterior" else
         " -- the posterior branch is not expected to lie on the MEDIAL border at all, since it supplies the "
         "dorso-radial forearm, so this distance is correct rather than a defect; Khadanovich's 1.8 mm bound "
         "applies to the nerve at the medial border, which is the anterior branch's rail.")
      + f" Its deepest point inside the brachioradialis is {st['max_depth_in_brachioradialis_mm']} mm, gated at "
      f"or below 1.8 mm. Diameter {st['diameter_mm']} mm = 60 % of this page's own trunk's measured "
      f"{st['trunk_diameter_mm']} mm: that 60 % is a DECLARED MODELLING CHOICE, because the PubMed searches "
      f"this round ran found no published calibre for the branches."
      + (f" {st['border_rail_extrapolated_pct']} % of the guiding rail is extrapolated along this page's own "
         f"radius, because the page's brachioradialis is a partial CT segmentation and its border stops short "
         f"of the wrist." if st.get("border_rail_extrapolated_pct") else "")
      + f" The branch clears this page's own radius by {st['min_signed_dist_to_radius_after_mm']} mm."
      + _common_tail(st, ["khadanovich2023", "qawasmi2024"],
                     "NO reachable model holds either branch of this nerve. Z-Anatomy carries the anterior and "
                     "posterior branches of the MEDIAL antebrachial cutaneous nerve and none for the lateral "
                     "-- a distinction that produced a false positive in this round's own first search pass and "
                     "is recorded there. Zygote and BioDigital are licence-blocked and were not used."))
    return {"name": f"{nm} branch of lateral antebrachial cutaneous nerve ({lr}) -- rule-based",
            "latin": ("Ramus anterior nervi cutanei antebrachii lateralis" if which == "anterior"
                      else "Ramus posterior nervi cutanei antebrachii lateralis"),
            "folder": "nerve", "region": "upper_limb",
            "source": "RULE-BASED from cited cadaveric morphometry; " + "; ".join(
                _cite(k) for k in ("khadanovich2023", "qawasmi2024")),
            "origin": "lateral antebrachial cutaneous nerve, at its division",
            "insertion": ("volar-radial forearm skin to the wrist" if which == "anterior"
                          else "dorso-radial forearm skin to the wrist"),
            "nerve": ["musculocutaneous_n"],
            "procedural_badge": badge,
            "geom_src": f"RULE-BASED (Q308) on this page's own LACN, radius and brachioradialis; "
                        f"volume {st['volume_cm3']} cm3"}


def psoas_rec(key, side, st):
    lr = SIDE_WORD[side]
    badge = (
      f"RULE-BASED (Q308), AND HIDDEN BY DEFAULT. **NOT DEMONSTRATED ON THIS BODY.** The psoas minor is absent "
      f"in a large share of people: the classical texts report it present in 40-50 % of individuals, and Raja "
      f"2026 found it in only 2 of 30 cadavers (6.67 %, 95 % CI 0.8-22.1) and 3 of 60 sides (5.00 %). Drawing "
      f"it VISIBLE on a named body would be a claim about THAT body which nothing here can support, so it is "
      f"hidden until you ask for it. It is also absent from every model this project can reach -- 0 of the "
      f"3,572 objects in the pinned Z-Anatomy catalogue, and the string occurs nowhere else in this project -- "
      f"so it is BUILT on this page's own bones. Origin: the lateral aspect of the bodies of T12 and L1 "
      f"({st['levels_how']}); insertion: the pecten pubis / iliopubic eminence, placed "
      f"{st['insertion_from_symphyseal_surface_mm']} mm along the pecten from this page's own symphyseal "
      f"surface, which is the adult pecten's own length and is GATED to 15-45 mm -- an earlier rule took the "
      f"hip bone's lowest medial point, which is the symphyseal surface or the inferior ramus, and made the "
      f"muscle 30 mm too long. MEASURED total length {st['total_length_mm']} mm, belly {st['belly_length_mm']} "
      f"mm at {st['belly_diameter_mm']} mm across, tendon {st['tendon_length_mm']} mm. "
      f"**THIS IS LONGER THAN THE LITERATURE AND THE DIFFERENCE IS THE SKELETON'S, NOT THE CONSTRUCTION'S**: "
      f"Raja 2026 measured 217.3 +- 4.5 mm total (belly 45.7 +- 4.6, tendon 171.7 +- 8.5, belly diameter "
      f"6.0 +- 0.5), but this page's own T12-to-symphysis vertical span is "
      f"{st['page_own_t12_to_symphysis_vertical_span_mm']} mm where a 217.3 mm muscle implies about 210 mm, so "
      f"that length CANNOT be reproduced on this skeleton. What is gated instead is the construction's own "
      f"quality: this muscle is only {st['excess_over_straight_line_pct']} % longer than the straight line its "
      f"own T12 origin and its own pecten insertion define, i.e. it is as short as the bone allows, and the "
      f"geometry was NOT bent to reach the published figure. Across the pages this span runs 298-344 mm, which "
      f"independently corroborates Q299's finding on pelvic proportion. The ROUND cross-section tapering from "
      f"the cited 6.0 mm belly to a 2.0 mm tendon is a DECLARED MODELLING CHOICE for the tendon -- Raja "
      f"calipers the belly only. The tendon «blends laterally with the iliac fascia» (Raja 2026); that blending "
      f"is not drawn. Mid-section clearance from this page's own hip bone "
      f"{st['min_signed_dist_to_hip_bone_after_mm']} mm, with the insertion footprint "
      f"{st.get('attachment_depth_in_hip_bone_mm')} mm into it."
      + _common_tail(st, ["raja2026", "patra2024"],
                     "NO reachable model holds it: 0 of Z-Anatomy's 3,572 objects, none of HRA / CCF's mesh "
                     "nodes, none in BodyParts3D, CVH or the SPL atlases. Zygote and BioDigital are "
                     "licence-blocked and were not used."))
    return {"name": f"Psoas minor ({lr}) -- rule-based, not demonstrated on this body",
            "latin": "Musculus psoas minor", "folder": "muscle", "region": "abdomen",
            "source": "RULE-BASED from cited cadaveric morphometry; " + "; ".join(
                _cite(k) for k in ("raja2026", "patra2024")),
            "origin": "lateral aspect of the bodies of T12 and L1",
            "insertion": "pecten pubis and iliopubic eminence",
            "nerve": ["lumbar_plexus_L1"],
            "procedural_badge": badge,
            "geom_src": f"RULE-BASED (Q308) on this page's own T12, L1 and hip bone; "
                        f"volume {st['volume_cm3']} cm3; hidden by default"}


def all_rec(key, side, st):
    lr = SIDE_WORD[side]
    d = L.DISAGREE
    badge = (
      f"RULE-BASED (Q308), AND **CONTESTED** -- three separate disagreements in the literature are carried here "
      f"rather than resolved silently. (1) THE FEMORAL ORIGIN. Kosy 2016 found it posterior and proximal to the "
      f"lateral collateral ligament in 6 of 11 knees, anterior and distal in 3 and at the same site in 1; "
      f"Rustagi 2019 reports «anterior and distal» in all 20 of theirs. This mesh uses neither side but the "
      f"authors' OWN resolution, from Kosy's full text: «all of these described attachments exist on a line "
      f"passing through the lateral femoral epicondyle and, thus, the centre of this may be an adequate "
      f"approximation» -- so the origin is the centre of THIS page's own lateral femoral epicondyle, "
      f"{st['femoral_origin_to_fcl_femoral_end_mm']} mm from this page's own fibular collateral ligament's "
      f"femoral end. A reader who needs the VARIANT rather than the central approximation will not find it "
      f"here. (2) THE WIDTH: {st['width_mm']} mm uniform (Kosy 2016) against Rustagi 2019's 6.98 mm at the "
      f"origin widening to 9.36 mm at the insertion. Not averaged. (3) WHETHER IT IS A DISCRETE LIGAMENT AT "
      f"ALL: Kosy 2016 concludes «the ALL is a capsular thickening with meniscal attachment», so drawing it as "
      f"a free band OVERSTATES its separateness from the capsule; and its thickness here, {st['thickness_mm']} "
      f"mm from Kosy, is at the thin end of a published 0.87-3 mm spread -- Kosy says of his own figure that it "
      f"«is significantly less than the 2-3 mm described by Vincent et al.», so the real ligament may be up to "
      f"3.4x thicker than drawn. "
      f"THE TIBIAL INSERTION sits at {st['tibial_frac_gt_to_fh']} of the way from Gerdy's tubercle to the "
      f"fibular head, against Kosy's 59.5 +- 5.44 %; that FRACTION is what is gated, not the millimetres, "
      f"because Kosy's two distances (17.7 +- 2.95 mm from the tubercle, 12.3 +- 3.55 mm from the head) imply a "
      f"span of about 30.0 mm while this page's own span is "
      f"{st['page_own_gerdy_to_fibular_head_span_mm']} mm (ratio {st['span_ratio_page_over_kosy']}), so the "
      f"absolute distances scale with the knee and are reported, not judged: ours are "
      f"{st['tibial_from_gerdy_mm']} mm and {st['tibial_from_fibular_head_mm']} mm. Gerdy's tubercle is found "
      f"by a geometric rule on this page's own tibia (the most antero-lateral vertex of its proximal 15 %)"
      + (f", and that rule lands {st['gerdy_rule_vs_itb_most_distal_vertex_mm']} mm from this page's own "
         f"iliotibial tract's most distal vertex, which inserts there -- an independent check"
         if st.get("gerdy_rule_vs_itb_most_distal_vertex_mm") is not None else "")
      + f". MEASURED length {st['length_mm']} mm against Kosy's 40.1 +- 5.53 mm and against the "
      f"{st['lit_length_published_range_mm']} that Kosy's own review of the other studies reports. "
      f"**A DISCREPANCY REPORTED, NOT HIDDEN**: Kosy writes «we found the ALL superficial to the LCL», and "
      f"measured here this mesh's mean lateral coordinate is {st['all_mean_lateral_coord_mm']} mm against the "
      f"fibular collateral ligament's {st['fcl_mean_lateral_coord_mm']} mm, so superficial="
      f"{st['is_superficial_to_the_fcl']} -- in 11 of the 12 knees built this round that depth relationship is "
      f"NOT reproduced. The elliptical cross-section is a DECLARED MODELLING CHOICE. Mid-section clearance: "
      f"femur {st['min_signed_dist_to_femur_after_mm']} mm, tibia {st['min_signed_dist_to_tibia_after_mm']} mm."
      + _common_tail(st, ["kosy2016", "rustagi2019"],
                     "**HRA / CCF HOLDS THIS LIGAMENT FOR REAL, ON THIS VERY DONOR FAMILY.** The "
                     "'3D Reference Organ Set for United, Female/Male' v1.10, CC BY 4.0, carries "
                     "VH_F_anterolateral_ligament_of_knee_L/R (1,680 triangles, 9.0 x 56.9 x 14.2 mm) and "
                     "VH_M_anterolateral_ligament_of_knee_L/R (790 triangles, 12.6 x 54.0 x 21.7 mm), both "
                     "closed meshes, UBERON:0014899 -- on the same two Visible Human donors as this project's "
                     "Imaging pages. THIS RULE-BASED MESH SHOULD GIVE WAY TO THAT ONE, and it is put to the "
                     "owner as a decision; importing it is a round of its own because those GLBs are kept "
                     "outside the repository. HRA's 56.9 / 54.0 mm is a BOUNDING-BOX extent, not a centreline "
                     "length, so it is an upper bound and not directly our measured length. No earlier round "
                     "found it because this ligament only became a recorded absence in Q306, after Q296 and "
                     "Q302 surveyed HRA against a different gap list. Zygote and BioDigital are licence-blocked "
                     "and were not used."))
    return {"name": f"Anterolateral ligament of the knee ({lr}) -- rule-based, contested",
            "latin": "Ligamentum anterolaterale genus", "folder": "ligament", "region": "lower_limb",
            "source": "RULE-BASED from cited cadaveric morphometry, with the disagreements recorded; "
                      + "; ".join(_cite(k) for k in ("kosy2016", "rustagi2019")),
            "origin": f"femur_{side}: centre of the lateral femoral epicondyle",
            "insertion": f"tibia_{side}: 59.5 % of the way from Gerdy's tubercle to the fibular head",
            "procedural_badge": badge,
            "geom_src": f"RULE-BASED (Q308) on this page's own femur, tibia, fibula and fibular collateral "
                        f"ligament; volume {st['volume_cm3']} cm3; CONTESTED"}


BUILDERS = {"coracoacromial_ligament": lambda k, s, st: cal_rec(k, s, st),
            "lacn_anterior_branch": lambda k, s, st: lacn_rec(k, s, st, "anterior"),
            "lacn_posterior_branch": lambda k, s, st: lacn_rec(k, s, st, "posterior"),
            "psoas_minor": lambda k, s, st: psoas_rec(k, s, st),
            "anterolateral_ligament": lambda k, s, st: all_rec(k, s, st)}
CAT = {"coracoacromial_ligament": ("ligament", "ligament"),
       "lacn_anterior_branch": ("nerve", "nerve"),
       "lacn_posterior_branch": ("nerve", "nerve"),
       "psoas_minor": ("muscle", "muscle"),
       "anterolateral_ligament": ("ligament", "ligament")}


def rec_for(sid, st, key):
    base, side = sid.rsplit("_", 1)
    return BUILDERS[base](key, side, st), CAT[base], side


# --------------------------------------------------------------------- the three cards that denied real tissue
TIER_A_NOTE = {
 "pubic_symphysis_disc":
   (" Q308 CORRECTION: this mesh IS the pubic symphysis's fibrocartilage -- TA `Discus interpubicus`, the "
    "interpubic disc. Until this round the search answered `pubic symphysis` with an explanation saying no page "
    "ships one, while this was on the screen. The cause was that the guard tested whether the clinical term "
    "RESOLVED through the alias table rather than whether the structure was PRESENT on the page, and no alias "
    "connected the clinical name to the TA one. `pubic symphysis`, `symphysis pubis` and `symphysis pubica` now "
    "reach this mesh. The two Imaging pages genuinely do not ship it, and there the explanation remains."),
 "zan_subtendinous_calcaneal_bursa":
   (" Q308 CORRECTION: this IS the RETROCALCANEAL bursa. TA calls it `bursa subtendinea calcanei`, the "
    "subtendinous bursa of the calcaneal tendon, and it lies between the calcaneal tendon and the calcaneus. "
    "Until this round the search answered `retrocalcaneal bursa` with an explanation saying it is absent from "
    "every page AND from every source we hold -- both wrong: this mesh ships on all four Z pages and the pinned "
    "Z-Anatomy catalogue holds 39 bursae including it. A NAMING gap, not a geometry gap -- the same failure "
    "mode as `ligamenta flava` in Q306. `retrocalcaneal bursa` and `bursa tendinis calcanei` now reach it."),
 "zan_articular_disc_of_distal_radio_ulnar_joint":
   (" Q308 CORRECTION: this is the CENTRAL ARTICULAR DISC of the TRIANGULAR FIBROCARTILAGE COMPLEX (TFCC) -- "
    "its principal, load-bearing component, spanning the sigmoid notch of the radius to the ulnar fovea. Until "
    "this round the search answered `TFCC` with an explanation saying the complex is absent, while this and the "
    "dorsal ulnocarpal ligament were on the screen; the project also already held a cited registry entry for it "
    "in data/cartilage/tfcc_disc.json (Palmer & Werner 1981; Bednar 1991 for the vascular zonation). `TFCC` and "
    "`triangular fibrocartilage` now reach it. What genuinely does NOT ship is the MENISCUS HOMOLOGUE and the "
    "volar / dorsal radioulnar ligaments as separate meshes, and the Imaging pages carry none of the complex."),
 "zan_dorsal_ulnocarpal_ligament":
   (" Q308: this is a component of the TRIANGULAR FIBROCARTILAGE COMPLEX (TFCC), which the search claimed until "
    "this round was absent from every page. It is reachable by `TFCC` now. The complex's central articular disc "
    "ships beside it; its meniscus homologue does not."),
 "zan_lateral_antebrachial_cutaneous_nerve":
   (" Q308 UPDATE, SUPERSEDING THE PARAGRAPH ABOVE: this page now also carries the nerve's ANTERIOR and "
    "POSTERIOR BRANCH, built rule-based from Khadanovich 2023 and Qawasmi 2024 and badged as such, so the "
    "statement that no page carries either branch is no longer true. The branches run from a division point on "
    "THIS nerve's own centreline 46.5-48.8 mm distal to this page's own interepicondylar line and reach to "
    "within 0.3-15.0 mm of the distal radius, which closes the 53.8-73.5 mm shortfall Q307 measured. The trunk "
    "itself was NOT changed and still ends where it did. Also corrected: Q307 stated that the superficial "
    "branch of the radial nerve is not present on the Z pages -- it is, on all six pages, as "
    "`radial_n_superficial_branch_l/r`."),
}


def tier_a_notes(structure_ids):
    """{id: note} for the shipping structures whose cards must stop denying, or stop being superseded."""
    out = {}
    for sid in structure_ids:
        for stem, note in TIER_A_NOTE.items():
            if sid == stem or sid == stem + "_l" or sid == stem + "_r":
                out[sid] = note
    return out


ATTRIBUTION = (
  "Rule-based structures (Q308): the coracoacromial ligament, the anterior and posterior branches of the "
  "lateral antebrachial cutaneous nerve, the psoas minor (hidden by default, and NOT demonstrated on this "
  "body) and the knee's anterolateral ligament (contested) are NOT segmented from any body. They are built on "
  "this page's own bones from cited cadaveric morphometry -- Khadanovich 2023 doi:10.1016/j.aanat.2023.152202; "
  "Qawasmi 2024 doi:10.1016/j.jhsa.2024.04.018; von Schroeder 2001 doi:10.1097/00003086-200102000-00015; "
  "Hu 2009 PMID 20073313; Nicholson 1996 doi:10.1016/s1058-2746(96)80024-3; Raja 2026 "
  "doi:10.7759/cureus.111450; Patra 2024 doi:10.5603/fm.99128; Kosy 2016 doi:10.1007/s10195-016-0392-0; "
  "Rustagi 2019 doi:10.4103/ortho.IJOrtho_137_17 -- each with its volume, its measured numbers and its "
  "literature comparison on its own card, and each refusal recorded with its number in "
  "data/derived/Q308_built_structures.json. No figure of any of those papers was used: PubMed Central is not "
  "reachable from the build session, so no figure could be scaled and none was guessed at. HRA / CCF holds the "
  "anterolateral ligament as a real mesh on these same donors and the rule-based one should give way to it. "
  "Zygote and BioDigital remain licence-blocked and were not used."
)
