#!/usr/bin/env python3
"""Q308: the cited literature behind every structure this round builds. Numbers live HERE, never in the builder's body.

Every entry carries the PMID, the DOI where one is assigned, and the author's own sentence. Where two papers
disagree the disagreement is an entry of its own (`DISAGREE`) and is carried onto the card instead of being
resolved silently -- the rule Q306 applied to its seven contested groups.
"""
from __future__ import annotations

CITE = {
 # ---------------------------------------------------------------- lateral antebrachial cutaneous nerve (LACN)
 "khadanovich2023": {
   "cite": "Khadanovich A, Benes M, Kaiser R, Herma T, Kachlik D. Clinical anatomy of the lateral antebrachial "
           "cutaneous nerve: Is there any safe zone for interventional approach? Ann Anat 2023;252:152202",
   "pmid": "38128746", "doi": "10.1016/j.aanat.2023.152202", "n": "93 cadaveric forearms",
   "quotes": [
     "The LACN branched in 76 cases (81.7 %) into an anterior and posterior branch at mean distance of "
     "47.8 +/- 34.2 mm distal to the IEL.",
     "The medial border of the brachioradialis muscle was observed less than 1.8 mm from the LACN.",
     "The LACN appeared to be in a close proximity within the whole length of the brachioradialis muscle.",
     "The emerging point of the LACN was found distally, proximally or at the level of the interepicondylar line (IEL).",
     "The LACN and the SBRN intersected in 86 % of upper limbs with communications noticed in 71 % of forearms.",
     "The LACN supplying the dorsum of the hand was observed in 39.8 % of cases.",
   ]},
 "qawasmi2024": {
   "cite": "Qawasmi F, MacLeod J, AbuHamdia A, Grindel SI, Yassin M. Anatomy of the Lateral Antebrachial Cutaneous "
           "Nerve: Landmarks for Procedures in the Cubital Fossa. J Hand Surg Am 2024;50(7):882.e1-882.e5",
   "pmid": "38934998", "doi": "10.1016/j.jhsa.2024.04.018", "n": "28 fresh cadaveric upper extremities",
   "quotes": [
     "The LABCN aligns with the medial border of the BR at a mean of 68 mm distal to the interepicondylar line.",
     "It was deep to the forearm superficial fascia in all cadavers.",
     "At the level of the LE, the nerve was located at a mean of 6.3 +/- 3.1 mm medial to the BR.",
     "The mean distance from the LE to the LABCN at the interepicondylar line was 24.5 +/- 7.2 mm.",
     "At the elbow joint level, 82.1% of the specimens have two branches for the LABCN, whereas 17.9% "
     "demonstrated only a single branch.",
   ]},
 # ---------------------------------------------------------------- coracoacromial ligament (CAL)
 "vonschroeder2001": {
   "cite": "von Schroeder HP, Kuiper SD, Botte MJ. Osseous anatomy of the scapula. Clin Orthop Relat Res "
           "2001;(383):131-9",
   "pmid": "11210947", "doi": "10.1097/00003086-200102000-00015", "n": "15 pairs of cadaveric scapulas",
   "quotes": [
     "The average length of the coracoacromial ligament was 27 +/- 5 mm.",
     "The acromion measured 48 +/- 5 mm x 22 +/- 4 mm and was 9 +/- 1 mm thick.",
     "The thickness of the coracoid was 11 +/- 1 mm.",
     "The distance from the glenoid to the acromion was 16 +/- 2 mm.",
   ]},
 "hu2009": {
   "cite": "Hu X, Huang F, Zhong G, Cen S, Xiang Z, Li J. [Biomechanical study on proximally based conjoined "
           "tendon transfer for coracoacromial ligament reconstruction as anterosuperior restraint of shoulder]. "
           "Zhongguo Xiu Fu Chong Jian Wai Ke Za Zhi 2009;23(12):1469-73",
   "pmid": "20073313", "doi": None, "doi_note": "no DOI is assigned to this record; PMID only",
   "n": "9 fresh-frozen cadaveric glenohumeral joints",
   "quotes": [
     "The length of the medial and lateral bands of the CAL was (28.91 +/- 5.56) mm and (31.90 +/- 4.21) mm, "
     "respectively; the width of coracoid process and acromion attachment of the CAL was (26.80 +/- 10.24) mm "
     "and (15.86 +/- 2.28) mm, respectively; and the thickness of middle part of the CAL was (1.61 +/- 0.36) mm.",
     "CAL morphology revealed 1 Y-shaped, 4 quadrangular, and 4 broad ligaments.",
   ]},
 "nicholson1996": {
   "cite": "Nicholson GP, Goodman DA, Flatow EL, Bigliani LU. The acromion: morphologic condition and age-related "
           "changes. A study of 420 scapulas. J Shoulder Elbow Surg 1996;5(1):1-11",
   "pmid": "8919436", "doi": "10.1016/s1058-2746(96)80024-3", "n": "420 scapulas",
   "quotes": [
     "Mean acromial dimensions in men were length = 48.5 mm, width = 19.5 mm, and anterior thickness = 7.7 mm. "
     "Mean dimensions in women were length = 40.6 mm, width = 18.4 mm, and thickness = 6.7 mm.",
   ]},
 # ---------------------------------------------------------------- psoas minor
 "raja2026": {
   "cite": "Raja B, Kulkarni MM, Vaishnani H. Morphology and Morphometric Analysis of the Psoas Minor Muscle in "
           "Adult Human Cadavers at a Tertiary-Care Institution in Western India. Cureus 2026;18(6):e111450",
   "pmid": "42502531", "doi": "10.7759/cureus.111450", "pmc": "PMC13400699", "n": "30 cadavers / 60 sides",
   "quotes": [
     "The psoas minor is a slender, inconstantly present vestigial muscle of the posterior abdominal wall. "
     "Classical texts report its presence in 40-50% of individuals.",
     "The psoas minor was identified in two of 30 cadavers (6.67%; exact binomial 95% CI 0.8-22.1%), "
     "corresponding to three of 60 sides (5.00%; 95% CI 1.0-13.9%).",
     "All three muscles originated from the lateral aspect of the bodies of T12 and L1 and inserted, via a long, "
     "slender tendon, into the pecten pubis and iliopubic eminence, with the tendon also blending laterally with "
     "the iliac fascia.",
     "The mean belly length was 4.57 +/- 0.46 cm, the mean tendon length was 17.17 +/- 0.85 cm, the mean total "
     "length was 21.73 +/- 0.45 cm, and the mean belly diameter was 0.60 +/- 0.05 cm.",
   ]},
 "patra2024": {
   "cite": "Patra A, Chaudhary P, Malhotra V, Arora K. Psoas minor muscle: the most unstable muscle of the psoas "
           "group. Folia Morphol 2024;83(4):886-892",
   "pmid": None, "doi": "10.5603/fm.99128", "n": "30 cadavers",
   "doi_note": "carried from the Q306 round record (PROJECT_STATE ## Q306 section B); the DOI is the identifier held",
   "quotes": ["the most unstable muscle of the psoas group"]},
 # ---------------------------------------------------------------- anterolateral ligament of the knee (ALL)
 "kosy2016": {
   "cite": "Kosy JD, Soni A, Venkatesh R, Mandalia VI. The anterolateral ligament of the knee: unwrapping the "
           "enigma. Anatomical study and comparison to previous reports. J Orthop Traumatol 2016;17(4):303-308",
   "pmid": "26861760", "doi": "10.1007/s10195-016-0392-0", "pmc": "PMC5071230",
   "n": "11 fresh-frozen cadaveric knees",
   "quotes": [
     "The ALL was identified in ten of the 11 cadavers.",
     "The mean dimensions were: length 40.1 (+/- 5.53) mm, width 4.63 (+/- 1.39) mm, thickness 0.87 (+/- 0.18) mm.",
     "The femoral origin was posterior and proximal to the lateral collateral ligament attachment in six knees, "
     "anterior and distal in three knees, and at the same site in one knee.",
     "The tibial insertion was a mean 17.7 (+/- 2.95) mm from Gerdy's tubercle (GT) and 12.3 (+/- 3.55) mm from "
     "the fibula head (FH). This was 59.5 (+/- 5.44) % from GT to FH.",
     "Our results support the finding that the ALL is a capsular thickening with meniscal attachment.",
     "all of these described attachments exist on a line passing through the lateral femoral epicondyle and, "
     "thus, the centre of this may be an adequate approximation",
     "In cases where the ALL attaches PP to the LCL, we found the ALL superficial to the LCL.",
     "the dimensions of the ALL are variably described, with lengths from 37 to 59 mm reported",
     "the thickness of our measured ligament (0.87 mm) is less than previously described by Claes et al. and "
     "Caterine et al. It is also significantly less than the 2-3 mm described by Vincent et al.",
   ], "full_text_read": "PMC5071230, read in full this round -- which is where the lateral-femoral-epicondyle "
                        "resolution and the 37-59 mm published range come from, not from the abstract"},
 "rustagi2019": {
   "cite": "Rustagi SM, Gopal P, Ahuja MS, Arora NC, Sood N. The Anterolateral Ligament of the Knee: Descriptive "
           "Anatomy and Clinical Correlation. Indian J Orthop 2019;53(1):89-93",
   "pmid": "30905987", "doi": "10.4103/ortho.IJOrtho_137_17", "pmc": "PMC6394189",
   "n": "20 embalmed cadaveric specimens",
   "quotes": [
     "In all but one left male knee specimen (95%) ALL was observed.",
     "Its proximal attachment to the femur is anterior and distal to the attachment of the LCL.",
     "Distally the superficial fibers of the ALL inserted close to the Gerdy's tubercle at the level of the "
     "fibular head, and the deeper fibers merged with the lateral meniscus.",
     "The mean length of the ALL was 43.35 mm +/- 4.04 mm in flexion and 40.38 mm +/- 4.35 mm in extension.",
     "The average width of the ALL was 6.98 mm +/- 0.95 mm at its origin and 9.36 mm +/- 1.07 mm at its insertion.",
   ]},
 # ---------------------------------------------------------------- facet capsule (NOT built -- recorded)
 "tanno2004": {
   "cite": "Tanno I, Murakami G, Oguma H, Sato S, Lee UY, Han SH, Yamashita T. Morphometry of the lumbar "
           "zygapophyseal facet capsule and cartilage with special reference to degenerative osteoarthritic "
           "changes. J Orthop Sci 2004;9(5):468-77",
   "pmid": "15449122", "doi": "10.1007/s00776-004-0807-2", "n": "23 fresh osteoligamentous lumbar spines",
   "open_access": False,
   "quotes": ["we performed morphometric investigations of the surface areas of the joints and their capsules and "
              "measured the capsular thickness"]},
 "gacek2021": {
   "cite": "Gacek E, Bermel EA, Ellingson AM, Barocas VH. Through-thickness regional variation in the mechanical "
           "characteristics of the lumbar facet capsular ligament. Biomech Model Mechanobiol 2021;20(4):1445-1457",
   "pmid": "33788068", "doi": "10.1007/s10237-021-01455-3", "pmc": "PMC9289988",
   "quotes": ["The average elastin modulus, E, and the average collagen fiber modulus, xi, were 13.15 +/- 3.59 kPa "
              "and 18.68 +/- 13.71 MPa (95% CI), respectively."]},
}

# ----------------------------------------------------------------------- the numbers the builder is allowed to use
LIT = {
 "lacn_division_distal_to_iel_mm": (47.8, 34.2, "khadanovich2023"),
 "lacn_division_rate_pct":         (81.7, None, "khadanovich2023"),
 "lacn_two_branch_rate_pct":       (82.1, None, "qawasmi2024"),
 "lacn_single_branch_rate_pct":    (17.9, None, "qawasmi2024"),
 "lacn_br_medial_border_max_mm":   (1.8,  None, "khadanovich2023"),
 "lacn_aligns_br_at_mm":           (68.0, None, "qawasmi2024"),
 "cal_length_mm":                  (27.0, 5.0,  "vonschroeder2001"),
 "cal_medial_band_mm":             (28.91, 5.56, "hu2009"),
 "cal_lateral_band_mm":            (31.90, 4.21, "hu2009"),
 "cal_width_coracoid_mm":          (26.80, 10.24, "hu2009"),
 "cal_width_acromion_mm":          (15.86, 2.28, "hu2009"),
 "cal_thickness_mm":               (1.61, 0.36, "hu2009"),
 "psoas_minor_belly_len_mm":       (45.7, 4.6,  "raja2026"),
 "psoas_minor_tendon_len_mm":      (171.7, 8.5, "raja2026"),
 "psoas_minor_total_len_mm":       (217.3, 4.5, "raja2026"),
 "psoas_minor_belly_diam_mm":      (6.0,  0.5,  "raja2026"),
 "psoas_minor_prevalence_classic_pct": (45.0, None, "raja2026"),
 "all_length_mm":                  (40.1, 5.53, "kosy2016"),
 "all_length_published_range_mm":  ((37.0, 59.0), None, "kosy2016"),
 "all_width_mm":                   (4.63, 1.39, "kosy2016"),
 "all_thickness_mm":               (0.87, 0.18, "kosy2016"),
 "all_tibial_frac_gt_to_fh":       (0.595, 0.0544, "kosy2016"),
 "all_tibial_from_gt_mm":          (17.7, 2.95, "kosy2016"),
 "all_tibial_from_fh_mm":          (12.3, 3.55, "kosy2016"),
}

# ------------------------------------------------------- where the literature disagrees: shipped + recorded, not resolved
DISAGREE = {
 "all_femoral_origin": {
   "what": "where the ALL attaches on the femur relative to the fibular (lateral) collateral ligament",
   "shipped": "the CENTRE OF THE LATERAL FEMORAL EPICONDYLE, which is the resolution Kosy 2016's own full text "
              "offers for the dispute",
   "why_shipped": "Kosy 2016 (read in full, PMC5071230): 'all of these described attachments exist on a line "
                  "passing through the lateral femoral epicondyle and, thus, the centre of this may be an "
                  "adequate approximation'. Taking the authors' own approximation is better than picking a side "
                  "in their disagreement with Rustagi, and it removes an offset we would otherwise have had to "
                  "declare ourselves.",
   "against": "the dispute itself remains unsettled and is NOT resolved by shipping the midpoint: Kosy 2016 "
              "found the origin posterior and proximal to the LCL in 6 of 11 knees, anterior and distal in 3 "
              "and at the same site in 1, while Rustagi 2019 (20 specimens) reports it as 'anterior and distal "
              "to the attachment of the LCL' in all of theirs. A reader who needs the variant, rather than the "
              "central approximation, will not find it here.",
   "sources": ["kosy2016", "rustagi2019"]},
 "all_thickness": {
   "what": "the ALL's thickness",
   "shipped": "0.87 +- 0.18 mm (Kosy 2016)",
   "why_shipped": "the thinnest and most recent careful dissection of the two studies this round read in full; "
                  "it is also the value whose measurement method is described",
   "against": "Kosy 2016 says so itself: 'the thickness of our measured ligament (0.87 mm) is less than "
              "previously described by Claes et al. and Caterine et al. It is also significantly less than the "
              "2-3 mm described by Vincent et al.' -- so the shipped band is at the THIN end of a 0.87-3 mm "
              "published spread, and the ligament may be up to 3.4x thicker than drawn here.",
   "sources": ["kosy2016"]},
 "all_width": {
   "what": "the ALL's width",
   "shipped": "4.63 +/- 1.39 mm (uniform)",
   "why_shipped": "the only study of the two that measured a single width for the whole ligament",
   "against": "Rustagi 2019 measures it tapering the other way and larger: 6.98 +/- 0.95 mm at the origin and "
              "9.36 +/- 1.07 mm at the insertion",
   "sources": ["kosy2016", "rustagi2019"]},
 "all_existence": {
   "what": "whether the ALL is a discrete ligament at all",
   "shipped": "built as a discrete band, which is how both studies measured it",
   "why_shipped": "both studies isolated and calipered it (Kosy 10/11, Rustagi 19/20)",
   "against": "Kosy 2016 itself concludes it is not a free ligament: 'Our results support the finding that the "
              "ALL is a capsular thickening with meniscal attachment' -- so a discrete band OVERSTATES its "
              "separateness from the capsule",
   "sources": ["kosy2016", "rustagi2019"]},
 "psoas_minor_prevalence": {
   "what": "how often the psoas minor is present",
   "shipped": "built, but HIDDEN by default and labelled 'not demonstrated on this body'",
   "why_shipped": "the owner asked for it to exist; hiding it by default means the page does not assert it is "
                  "present in these two particular bodies",
   "against": "Raja 2026 found it in 6.67 % of 30 cadavers (5.00 % of 60 sides) against the 40-50 % that "
              "classical texts report -- so its prevalence is itself unsettled",
   "sources": ["raja2026", "patra2024"]},
 "cal_length": {
   "what": "the CAL's length",
   "shipped": "the measured length of the band this round builds on each page's own scapula, reported against both",
   "why_shipped": "the course is fixed by the page's own coracoid and acromion, so length is an OUTPUT here, "
                  "not an input",
   "against": "von Schroeder 2001 gives 27 +/- 5 mm (30 scapulas); Hu 2009 gives two bands, 28.91 +/- 5.56 mm "
              "medial and 31.90 +/- 4.21 mm lateral (9 shoulders)",
   "sources": ["vonschroeder2001", "hu2009"]},
}

MODELLING_CHOICES = {
 "cal_cross_section": "elliptical, 26.8 -> 15.9 mm wide and 1.61 mm thick: the WIDTHS and the THICKNESS are "
                      "Hu 2009's calipers, the elliptical SHAPE is a modelling choice (Q248's declared precedent "
                      "for rule-based ligaments).",
 "all_cross_section": "elliptical, 4.63 x 0.87 mm from Kosy 2016's calipers; the elliptical shape is a modelling "
                      "choice. Rustagi 2019's wider, tapering width is recorded as a disagreement, not averaged in.",
 "all_femoral_origin": "the centre of the lateral femoral epicondyle, which is Kosy 2016's own stated "
                       "approximation -- NOT a modelling choice, and it replaces the 6 mm posterior / 6 mm "
                       "proximal offset this round would otherwise have had to declare.",
 "lacn_branch_calibre": "each branch is given 60 % of the measured diameter of this page's own LACN trunk. No "
                        "published calibre for the branches was found by the PubMed searches this round ran, so "
                        "the 60 % is a DECLARED MODELLING CHOICE and not a measurement.",
 "psoas_minor_section": "round, 6.0 mm through the belly (Raja 2026) tapering to 2.0 mm through the tendon; the "
                        "tendon diameter is a modelling choice -- Raja 2026 calipers the belly only.",
}

NOT_BUILT = {
 "facet_joint_capsules": {
   "what": "the zygapophysial (facet) joint capsules",
   "why": "the construction needs ONE number the bone does not give -- the capsular thickness -- and it is not "
          "citable from anything reachable. The only morphometric study of the lumbar facet capsule, Tanno 2004, "
          "states that it 'measured the capsular thickness' but publishes no value in its abstract and is not "
          "open access; Gacek 2021 and Claeson 2015 are mechanical, not geometric (moduli, not millimetres). "
          "Z-Anatomy's pinned catalogue holds 16 articular capsules and NONE of them is spinal. Building the "
          "capsules would mean choosing their thickness ourselves, on 46+ joints per page.",
   "sources": ["tanno2004", "gacek2021"]},
 "female_perineal_skin": {
   "what": "female perineal skin",
   "why": "no source we hold has it (Z-Anatomy none; HRA 1.10 none; Open Anatomy none across all seven atlases; "
          "BodyParts3D's `perineum` was MEASURED by Q302 at 368 faces and 11.5 x 21.8 x 21.3 mm -- an area "
          "marker, and from a male body). A literature-fitted vulval surface is a SHAPE no paper specifies. "
          "Q297 removed exactly such a surface (8.33 cm3 in Base F) and the region stays open.",
   "sources": []},
 "nail_bed_matrix_pulp": {
   "what": "the nail bed, the nail matrix and the digital pulp",
   "why": "no source we hold has them: 0 nail objects in the pinned Z-Anatomy catalogue beyond the four `Nail "
          "plate` meshes that already ship, and 0 in BodyParts3D. The 3-8 mm figure for pulp is a THICKNESS, "
          "not a shape. The cause is upstream: Z-Anatomy's fingertip is bone plus a thin skin patch (Base M, "
          "nearly unfitted, measures 0.68 mm at the middle finger), and the Imaging pages carry no separate "
          "distal phalanges at all (4-14 fragments where 14 per hand are needed). The real fix is a hand atlas "
          "that contains nails.",
   "sources": []},
 "refused_hand_nerves": {
   "what": "the 18 nerve candidates Q307's gates refused (12 on Imaging M, 6 on Imaging F)",
   "why": "this is REAL geometry that already exists on the Combined page of the same body -- it was refused "
          "because the hand-bone fit between Combined and Imaging is 10.29 mm median, 54.87 p95 and 63.86 mm "
          "max on `metacarpals_r`. Bringing them over needs Q293's hand work redone on the Imaging pages first. "
          "Forcing them past the gate would plant nerves centimetres from their bones.",
   "sources": []},
}

LICENCE_BLOCKED = ("Zygote and BioDigital remain licence-blocked and were NOT used in this round: Zygote is paid "
                   "and proprietary and its Reproductive and Nervous sets are additionally sculpted from atlases "
                   "(Q302), and BioDigital is a hosted viewer/API with no mesh delivery.")
