#!/usr/bin/env python3
"""Q233 sex-correctness audit of the six CURRENT models -> data/derived/Q233_sex_audit.json + Q233_sex_audit.md.
    python3 scripts/anatomy/q233/audit.py [--measures data/derived/Q233_measures.json]
Reads (never edits) the six page dirs through scripts/anatomy/q233_load.py (current published sources by default; set Q233_SRC_<key> or --final to read build/q233/<page>), the own bundles of the
Q224 (before) and Q233 (after) builds for provenance, the measurements of scripts/anatomy/q233/measure_all.py and the Q233 build reports."""
from __future__ import annotations
import argparse, datetime, json, re, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
import q233_load as Q  # noqa: E402

PAGE_META = {
    "own_m": dict(label="Imaging-based · Male", kind="own", declared="male", dir="build/q224/viewer_m_hr", bundle="build/viewer_m_hr_q224",
                  body="The Visible Human MALE (39 y, 180 cm, 90 kg): his own CT + cryosections, reconstructed (measured / rule-based / transferred / Z-filled structures, each with a Source class)."),
    "own_f": dict(label="Imaging-based · Female", kind="own", declared="female", dir="build/q224/viewer_f_hr", bundle="build/viewer_f_hr_q224",
                  body="The Visible Human FEMALE (59 y, 157 cm, 88 kg): her own CT + cryosections, reconstructed (measured / rule-based / transferred from the male / Z-filled structures, each with a Source class)."),
    "base_m": dict(label="Base · Male", kind="zan", declared="male", dir="build/q222/viewer_zan_atlas", bundle=None,
                   body="Z-Anatomy / BodyParts3D: ONE male-derived body (BodyParts3D = a single male, the 'TARO' MRI set), unadapted."),
    "base_f": dict(label="Base · Female", kind="zan", declared="female", dir="build/q222/viewer_base_female", bundle=None,
                   body="Z-Anatomy / BodyParts3D: the SAME male-derived body as Base · Male (identical skeleton and soft tissue, 2,939 shared structures) with the 27 male-only objects removed (Q196) and nothing added."),
    "comb_m": dict(label="Combined · Male", kind="zan", declared="male", dir="build/q225/viewer_zan_vhm", bundle=None,
                   body="The Z-Anatomy male body fitted bone by bone to the Visible Human MALE (his frame); male-only organs kept and fitted."),
    "comb_f": dict(label="Combined · Female", kind="zan", declared="female", dir="build/q225/viewer_zan_female", bundle=None,
                   body="The Z-Anatomy MALE-derived body fitted bone by bone to the Visible Human FEMALE's skeleton (her frame); male-only organs removed; no female organ (before Q233)."),
}
BODY_SHORT = {'own_m': 'Visible Human male (his CT / cryosections)', 'own_f': 'Visible Human female (her CT / cryosections)', 'base_m': 'Z-Anatomy male-derived body', 'base_f': 'the SAME Z-Anatomy male-derived body', 'comb_m': 'Z male-derived body fitted to the VH male', 'comb_f': 'Z male-derived body fitted to the VH female'}
MALE = {
    "testis": r"(^|_)testis(_|$)|(^|_)testes(_|$)", "epididymis": r"epididym", "ductus_deferens": r"ductus_deferens|deferent", "seminal_vesicle": r"seminal_(gland|vesicle)",
    "prostate": r"(^|_)prostate(_|$)", "bulbourethral_gland": r"bulbourethral|cowper", "penis_corpora_glans": r"penis|corpus_(cavernosum|spongiosum)|glans", "foreskin": r"prepuc|foreskin",
    "scrotum_urogenital_skin": r"scrot|urogenital_region", "spermatic_cord": r"spermatic", "ejaculatory_duct": r"ejaculatory", "male_urethra": r"(^|_)urethra(_male)?$", "testicular_vessels": r"testicular",
}
FEMALE = {
    "uterus": r"(^|_)uterus$", "cervix": r"cervix_uteri|^cervix", "ovary": r"(^|_)ovary(_|$)|ovarian", "uterine_tube": r"uterine_tube|fallopian|salping", "uterine_ovarian_ligaments": r"broad_lig|round_lig|ovarian_lig|uterosacral|cardinal_lig",
    "vagina": r"(^|_)vagina($|_)|vaginal_(wall|canal|vault)", "labia_majora": r"labium_majus|labia_majora", "labia_minora": r"labium_minus|labia_minora", "clitoris": r"clitor", "vestibular_glands_bulb": r"bartholin|vestibular_(gland|bulb)",
    "mons_pubis": r"mons_pubis", "mammary_gland": r"mammary_gland|(^|_)breast|lactiferous", "female_urethra": r"urethra_female", "ovarian_vessels": r"ovarian_(a|v|artery|vein)",
}
SKIP = re.compile(r"gonadal|nasolabial|mentolabial|labial_comm|labii|(inferior|superior)_labial|vaginal_process|cervical|cervicis|cervicalis|vestibulo|vestibular_n|vestibular_nuc|vestibule|tooth|sphenoid", re.I)
SURFACE = {"mammary_region_skin": r"skin_(in)?mammary_region", "perineal_closure_skin": r"perineal_closure"}


def _norm(x):
    return (x["id"] + " " + str(x["name"])).lower().replace(" ", "_")


def provenance_of(x):
    """what the structure is, from its subject (own pages) / record (Z pages)"""
    src = x["src"] or ""
    rec = x.get("rec") or {}
    if str(rec.get("source", "")).startswith("Chinese Visible Human") or src.startswith("xfer_cvh2"):
        return "ANOTHER PERSON'S real segmentation (Chinese Visible Human young female, Wu et al. 2015, CC BY 4.0), registered on the page's pelvis by bones (Q235): not segmented from this scan"
    if str(rec.get("source", "")).startswith("HuBMAP"):
        if "sculpted reference model" in str(rec.get("source", "")):
            return "HRA breast: reference model SCULPTED by the library author from textbook atlases (CC BY 4.0), NOT donor data; registered on the thoracic vertebrae and compressed into the page's skin envelope (Q234): not measured here"
        if "Q234" in str(rec.get("source", "")):
            return "HRA object of the Visible Human female frame (CC BY 4.0; construction not documented by the library), registered on the page's pelvis like the uterus (Q234): not measured here"
        return "HRA reference organ of the SAME donor (Visible Human female, CC BY 4.0), registered on the page's pelvis (Q233): not measured here"
    if src == "zan":
        b = str(rec.get("procedural_badge", ""))
        if "Q195" in b: return "Z-Anatomy male-derived structure fitted to the Visible Human male (estimate, not measured)"
        if "Q168" in b: return "Z-Anatomy male-derived structure fitted to the Visible Human female's skeleton (estimate, not measured)"
        return "Z-Anatomy / BodyParts3D (one male-derived body), unadapted"
    if src.startswith("xfer_zan2"): return "filled from Z-Anatomy (male-derived reference model), fitted to this body: not measured"
    if src.startswith("xfer_hrasculpt2"): return "HRA breast: reference model sculpted by the library author (CC BY 4.0), NOT donor data, fitted into her skin envelope (Q234): not measured"
    if src.startswith("xfer_hra2vhf_q234"): return "HRA object of the Visible Human female frame (vagina / ligaments, CC BY 4.0), registered on her CT pelvis (Q234): not measured"
    if src.startswith("xfer_hra2"): return "HRA reference organ of the SAME donor (Visible Human female, CC BY 4.0), registered on her CT pelvis (Q233): not measured"
    if "xfer" in src: return "transferred from the other Visible Human body (" + src + "): not measured here"
    return "measured / rule-based on this body's own CT or cryosections (subject " + src + ")"


def inventory(S, bundle_subject=None):
    out = dict(male_only_present={}, female_only_present={}, surface_patches={})
    for grp, pats, key in ((MALE, MALE, "male_only_present"), (FEMALE, FEMALE, "female_only_present"), (SURFACE, SURFACE, "surface_patches")):
        for item, rx in pats.items():
            hits = []
            for x in S:
                n = _norm(x)
                if SKIP.search(n):
                    continue
                if re.search(rx, x["id"].lower()) or re.search(rx, n):
                    if key == "male_only_present" and item == "male_urethra" and x["sys"] not in ("viscera", "organ"):
                        continue
                    hits.append(dict(id=x["id"], name=x["name"], system=x["sys"], source=x["src"], triangles=int(len(x["f"])), provenance=provenance_of(x)))
            if hits:
                out[key][item] = hits
    out["male_only_absent"] = sorted(set(MALE) - set(out["male_only_present"]))
    out["female_only_absent"] = sorted(set(FEMALE) - set(out["female_only_present"]))
    return out


def judge_inventory(inv, declared):
    wrong = []
    if declared == "female":
        for item, hits in inv["male_only_present"].items():
            if item == "male_urethra":
                continue
            wrong += [dict(item=item, **h, why="male-only structure on a female page") for h in hits]
    else:
        for item, hits in inv["female_only_present"].items():
            wrong += [dict(item=item, **h, why="female-only structure on a male page") for h in hits]
    return wrong


# ----------------------------------------------------------------------------- measures, references, verdicts
REFS = [
    dict(pmid="32274246", doi="10.5115/acb.19.135", cite="Mohd Ali SH et al. Anat Cell Biol 2020;53(1):27-35", used_for="subpubic angle", verified="abstract read (PubMed)",
         values="CT-based 3-D pelvis, 50 male + 50 female Malaysian adults: subpubic angle male 68.6 +- 7.6 deg, female 87.4 +- 6.5 deg; best cut-off 78.6 deg (94 % accuracy)"),
    dict(pmid="24789357", doi="10.1007/s00414-014-0999-8", cite="Franklin D et al. Int J Legal Med 2014;128(5):861-72", used_for="pelvic outlet, subpubic angle", verified="abstract read",
         values="MSCT 200 + 200 Western Australian adults; transverse pelvic outlet and subpubic angle contribute most to sex discrimination; no numbers in the abstract"),
    dict(pmid="42793678", doi="10.3390/diagnostics16182893", cite="Karaman G et al. Diagnostics 2026;16(18)", used_for="which pelvic measures discriminate", verified="abstract read",
         values="CT 101 M + 100 F: 13 of 14 pelvic measures differ by sex; most informative: acetabular width, acetabular height, subpubic angle, ischial length, transverse pelvic outlet, angle of the greater sciatic notch; no numbers in the abstract"),
    dict(pmid="39623825", doi="10.55519/JAMC-03-13148", cite="Jadoon OK et al. J Ayub Med Coll Abbottabad 2024;36(3):514-7", used_for="greater sciatic notch", verified="abstract read",
         values="70 dry pelvic bones: notch width, anterior segment and POSTERIOR ANGLE greater in females; depth, posterior segment and anterior angle greater in males; no numbers in the abstract"),
    dict(pmid="34554326", doi="10.1007/s00414-021-02700-1", cite="Knecht S et al. Int J Legal Med 2021;135(6):2603-13", used_for="greater sciatic notch", verified="abstract read",
         values="60 coxal bones; accuracy 0.92-0.97; the posterior angle with the deepest point of the notch as apex (A2) is in all models; no numbers in the abstract"),
    dict(pmid="37284374", doi="10.7759/cureus.38629", cite="Saluja S et al. Cureus 2023;15(5):e38629", used_for="sacral index", verified="abstract read",
         values="110 dry sacra: sacral length higher in males, SACRAL INDEX higher in females (p < 0.001; AUC 0.994); no numbers in the abstract"),
    dict(pmid="34964781", doi="10.1097/MD.0000000000027955", cite="Triwidodo A et al. Medicine 2021;100(47):e27955", used_for="sacrum", verified="abstract read",
         values="CT 150 M + 150 F Indonesian adults: sacrum larger in males; sacral index, curvature index and corporo-basal index differ by sex (P < .001); lumbar lordosis greater in females"),
    dict(pmid="35385483", doi="10.1371/journal.pone.0264770", cite="Krenn VA et al. PLoS One 2022;17(4):e0264770", used_for="caveat: sacrum is weakly dimorphic", verified="abstract read",
         values="164 modern humans: geometric-morphometric sex classification 72 %, anteroposterior corpus depth best linear parameter (83 %); sacral sex variation 'surprisingly low'"),
    dict(pmid="37803256", doi="10.1186/s12877-023-04254-w", cite="Jiawei L et al. BMC Geriatr 2023;23:632", used_for="femoral head diameter", verified="abstract read",
         values="CT angiography, 236 older patients (Inner Mongolia): femoral head diameter and femoral offset larger in males than females in every age group; no numbers in the abstract"),
    dict(pmid="40547822", doi="10.2147/TCRM.S521755", cite="Yang TJ, Qian W. Ther Clin Risk Manag 2025;21:905-16", used_for="femoral head diameter", verified="abstract read",
         values="CT of 247 patients: females have smaller femoral head diameter, neck length, offset; larger neck-shaft angle; no numbers in the abstract"),
    dict(pmid="41492324", doi="10.1016/j.jor.2025.12.005", cite="Sudhan S R et al. J Orthop 2025;73:116-27", used_for="femoral head diameter: population dependence", verified="abstract read",
         values="systematic review: femoral head diameter in males ranges from 31.1 +- 2.7 mm (Brazilian) to 48.50 +- 2.23 mm (Korean); Indian CT males 43.0 +- 2.6 mm; sex dimorphism < 2 % in the Brazilian series: absolute values are population dependent"),
    dict(pmid="42414653", doi="10.1007/s00414-026-03902-1", cite="Wasterlain SN et al. Int J Legal Med 2026;140(6):4473-81", used_for="femoral head diameter", verified="abstract read",
         values="202 skeletons (Coimbra): the femoral vertical head diameter is the best single discriminator (89.8 % accuracy); no numbers in the abstract"),
    dict(pmid="36713821", doi="10.7759/cureus.34224", cite="Shantanu K et al. Cureus 2023;15(1):e34224", used_for="Q angle", verified="abstract read",
         values="100 healthy adults: Q angle male 11.14 +- 1.9 (R) / 10.84 +- 1.86 (L) deg, female 13.68 +- 1.87 / 13.61 +- 2.04 deg"),
    dict(pmid="32295725", doi="10.1016/j.knee.2020.03.001", cite="Merchant AC et al. Knee 2020;27(3):934-9", used_for="Q angle", verified="abstract read",
         values="57 adults, standardized goniometer protocol: Q angle male 13.5 deg, female 15.9 deg (the 2.4 deg difference attributed to height)"),
    dict(pmid="31194851", doi="10.1371/journal.pone.0218387", cite="Khasawneh RR et al. PLoS One 2019;14(6):e0218387", used_for="Q angle", verified="abstract read",
         values="500 young Arab adults, upright weight-bearing: Q angle greater in women; correlated with femoral condylar distance; no numbers in the abstract"),
    dict(pmid="36235677", doi="10.3390/nu14194024", cite="Dang AK et al. Nutrients 2022;14(19):4024", used_for="waist-hip ratio, sex-specific thresholds", verified="abstract read",
         values="4701 Vietnamese adults: IDF-criteria WHR thresholds men 0.90, women 0.85 (a metabolic-syndrome screening cut-off, NOT a population mean)"),
    dict(pmid="18839131", doi="10.1007/s00125-008-1163-0", cite="Zillikens MC et al. Diabetologia 2008;51(12):2233-41", used_for="fat distribution", verified="abstract read",
         values="2506 people, DXA: sex-specific genetic effects on android:gynoid fat ratio and waist-hip ratio ('well-known sex differences in body composition'); no sex means in the abstract"),
    dict(pmid="22797367", doi="10.1159/000339981", cite="Hodge S et al. Obes Facts 2012;5(3):399-407", used_for="android / gynoid fat by DXA", verified="abstract read", values="DXA android, gynoid and total fat, WHR; sex differences in how fat distribution relates to serotonin; no sex means in the abstract"),
    dict(pmid="18197593", doi="10.1002/uog.5241", cite="Sokalska A, Valentin L. Ultrasound Obstet Gynecol 2008;31(2):210-7", used_for="uterus / ovary size after menopause", verified="abstract read",
         values="uterine AP diameter -22 % and ovarian volumes -45 % / -20 % (median) from 2 y before to 2 y after menopause; no absolute volumes in the abstract"),
    dict(pmid="11428180", doi=None, cite="Bar-Hava I et al. Climacteric 2001;4(2):160-5", used_for="uterus / ovary size after menopause", verified="abstract read", values="753 postmenopausal women: negative correlation of menopausal age with uterine volume and ovarian area; no absolute volumes in the abstract"),
]
INTERNAL = "internal reference = the two real donors measured by the same code (VH male, VH female); NOT a population norm (n = 1 + 1)"


def verdict_threshold(v, lo_male, hi_female):
    if v is None:
        return "not_measurable"
    return "male" if v < lo_male else ("female" if v > hi_female else "ambiguous")


def verdict_internal(v, male_ref, female_ref, band=0.10, female_higher=True):
    if v is None or male_ref is None or female_ref is None:
        return "not_measurable"
    mid, gap = 0.5 * (male_ref + female_ref), abs(female_ref - male_ref)
    if gap == 0:
        return "ambiguous"
    t = (v - mid) / (gap / 2)       # -1 = male donor, +1 = female donor (if female_higher)
    if not female_higher:
        t = -t
    return "female" if t > band * 2 else ("male" if t < -band * 2 else "ambiguous")


def measure_rows(m, page):
    """-> list of measure dicts for one page (m = measures of ALL pages)"""
    g = lambda p, k: m[p].get(k)
    mv, fv = "own_m", "own_f"
    rows = []
    def add(key, label, unit, v, ref_male, ref_female, status, cite, verdict, note="", reliability="ok"):
        rows.append(dict(key=key, label=label, unit=unit, value=v, reference_male=ref_male, reference_female=ref_female, reference_status=status, citation=cite, verdict=verdict, reliability=reliability, note=note))
    v = g(page, "subpubic_angle_deg")
    add("subpubic_angle", "Subpubic angle (angle between the axes of the two ischiopubic rami, 3-D)", "deg", v, "68.6 +- 7.6", "87.4 +- 6.5", "verified_abstract", "PMID 32274246 (CT, cut-off 78.6 deg)",
        verdict_threshold(v, 74.6, 82.6), f"proxy at the symphysis: {g(page, 'subpubic_proxy_symphysis_to_tuberosities_deg')} deg. Method differs from the paper's 4-landmark angle (axes of the rami, not their inferior borders): trust the sign, not the last 5 deg.", "ok")
    ratio = lambda p: (g(p, "intertuberous_mm") / g(p, "bi_iliac_breadth_mm")) if g(p, "intertuberous_mm") else None
    r = ratio(page)
    add("pelvic_outlet_transverse", "Transverse pelvic outlet (intertuberous distance) / bi-iliac breadth", "ratio", None if r is None else round(r, 3), "smaller", "larger", "direction_verified_no_number", "PMID 24789357, 42793678 (transverse outlet among the most dimorphic)",
        verdict_internal(r, ratio(mv), ratio(fv)), f"intertuberous {g(page, 'intertuberous_mm')} mm, bi-iliac {g(page, 'bi_iliac_breadth_mm')} mm; {INTERNAL}: VH male {round(ratio(mv), 3)}, VH female {round(ratio(fv), 3)}")
    v = g(page, "sciatic_notch_hull_angle_deg")
    add("greater_sciatic_notch", "Greater sciatic notch (hull-defect angle at the deepest point, lateral silhouette)", "deg", v, "smaller / deeper", "larger / wider", "direction_verified_no_number", "PMID 39623825, 34554326, 42793678",
        verdict_internal(v, g(mv, "sciatic_notch_hull_angle_deg"), g(fv, "sciatic_notch_hull_angle_deg")), f"depth {g(page, 'sciatic_notch_depth_mm')} mm. NOT the osteometric notch angle (different landmarks); {INTERNAL}: VH male {g(mv, 'sciatic_notch_hull_angle_deg')}, VH female {g(fv, 'sciatic_notch_hull_angle_deg')}", "low")
    v = g(page, "ischiopubic_index")
    add("ischiopubic_index", "Ischiopubic index (pubic length / ischial length x 100, from the femoral-head centre)", "index", v, "lower", "higher (Washburn)", "recalled_unverified_direction", "not found in a PubMed abstract this session (Washburn 1948 is not in PubMed)",
        verdict_internal(v, g(mv, "ischiopubic_index"), g(fv, "ischiopubic_index")), f"{INTERNAL}: VH male {g(mv, 'ischiopubic_index')}, VH female {g(fv, 'ischiopubic_index')}; the absolute level (>110) is above textbook values because the femoral-head centre stands in for the acetabular centre", "low")
    v = g(page, "sacral_index_breadth_over_length_pct")
    add("sacral_index", "Sacral index (breadth of the upper half / straight length x 100)", "index", v, "lower", "higher", "direction_verified_no_number", "PMID 37284374, 34964781 (caveat PMID 35385483: sacrum weakly dimorphic)",
        verdict_internal(v, g(mv, "sacral_index_breadth_over_length_pct"), g(fv, "sacral_index_breadth_over_length_pct")),
        f"{INTERNAL}: VH male {g(mv, 'sacral_index_breadth_over_length_pct')}, VH female {g(fv, 'sacral_index_breadth_over_length_pct')}. The Z-Anatomy male reads FEMALE-like here (107): the index depends on how the sacral apex / coccyx is cut in each mesh; not reliable across the six pages", "low")
    v = g(page, "sacral_curvature_index_pct")
    add("sacral_curvature", "Sacral curvature index (depth of the anterior concavity / chord x 100)", "index", v, "less curved", "more curved (varies)", "direction_verified_no_number", "PMID 34964781 (differs by sex, no direction in the abstract)", "ambiguous",
        "own male 14 % vs the five other meshes 34-37 %: a mesh / cut artefact (his sacrum is a different decimation), not diagnostic", "unreliable")
    v = g(page, "bi_iliac_breadth_mm")
    add("bi_iliac_breadth", "Bi-iliac (maximum pelvic) breadth", "mm", v, "n/a", "n/a", "not_used", "size depends on the donor", "ambiguous", "absolute size is not a sex marker without stature; the ratio to the shoulder breadth is used below", "ok")
    v = g(page, "femoral_head_diameter_r_mm")
    add("femoral_head_diameter", "Femoral head diameter (sphere fit, right)", "mm", v, "larger (Korean males 48.5 +- 2.2; Indian CT males 43.0 +- 2.6)", "smaller (no number read)", "partly_verified_abstract", "PMID 41492324, 37803256, 40547822, 42414653",
        "ambiguous", f"left {g(page, 'femoral_head_diameter_l_mm')} mm. Absolute values are population / size dependent (31 to 48.5 mm in males across studies); the two real donors read the SAME diameter (VH male {g(mv, 'femoral_head_diameter_r_mm')}, VH female {g(fv, 'femoral_head_diameter_r_mm')} mm: she is 88 kg): not diagnostic here", "ok")
    v = g(page, "bicondylar_breadth_r_mm")
    add("bicondylar_breadth", "Femoral bicondylar breadth (distal 60 mm, widest transverse extent, right)", "mm", v, "larger", "smaller", "recalled_unverified_direction", "no number read in an abstract",
        verdict_internal(v, g(mv, "bicondylar_breadth_r_mm"), g(fv, "bicondylar_breadth_r_mm"), female_higher=False), f"{INTERNAL}: VH male {g(mv, 'bicondylar_breadth_r_mm')}, VH female {g(fv, 'bicondylar_breadth_r_mm')}", "low")
    v = g(page, "shoulder_to_hip_ratio")
    add("shoulder_to_hip", "Biacromial breadth / bi-iliac breadth (skeletal, scapular acromion extremes)", "ratio", v, "larger", "smaller", "recalled_unverified_direction", "no number read in an abstract",
        verdict_internal(v, g(mv, "shoulder_to_hip_ratio"), g(fv, "shoulder_to_hip_ratio"), female_higher=False), f"biacromial {g(page, 'biacromial_mm')} mm; {INTERNAL}: VH male {g(mv, 'shoulder_to_hip_ratio')}, VH female {g(fv, 'shoulder_to_hip_ratio')}; arm position changes the scapulae", "low")
    qr, ql = g(page, "q_angle_r_deg"), g(page, "q_angle_l_deg")
    add("q_angle", "Q angle (ASIS - patella centre - tibial tuberosity, coronal projection of the bone landmarks)", "deg", dict(right=qr, left=ql), "10.8-13.5", "13.6-15.9", "verified_abstract", "PMID 36713821, 32295725, 31194851 (difference only 2-3 deg)", "ambiguous",
        "the sex difference (2-3 deg) is far below the posture error of a supine cadaver with rotated legs (values 0.7 to 37 deg across the six pages): not measurable on these meshes", "unreliable")
    add("sternum", "Sternal length / width", "mm", dict(length=g(page, "sternum_length_mm"), width=g(page, "sternum_width_mm")), "longer", "shorter", "recalled_unverified_direction", "none read",
        "ambiguous", "the Z-Anatomy 'sternum' is a different structure (119 / 108 / 95 mm vs 196 / 165 mm of the donors: manubrium + body vs the body piece): not comparable", "unreliable")
    add("breast_envelope", "Breast: skin protrusion over the ribs at the breast level minus the sternal column", "mm", g(page, "breast_bulge_mm"), "small", "large", "no_number", "none",
        "ambiguous", "supine cadaver, no gland modelled anywhere: the male donor reads 70 mm, the female donor 41 mm, the Z skin 49-64 mm: no sex signal; breast volume is NOT measurable", "unreliable")
    return rows


CORE = ("subpubic_angle", "pelvic_outlet_transverse", "greater_sciatic_notch", "ischiopubic_index", "shoulder_to_hip", "bicondylar_breadth")


def overall_skeletal(rows):
    c = {r["key"]: r["verdict"] for r in rows if r["key"] in CORE}
    f, m = sum(v == "female" for v in c.values()), sum(v == "male" for v in c.values())
    if f >= 4 and m == 0: v = "female"
    elif m >= 4 and f == 0: v = "male"
    elif f > m and m <= 1 and f >= 3: v = "mostly female (some measures ambiguous or male-like)"
    elif m > f and f <= 1 and m >= 3: v = "mostly male (some measures ambiguous or female-like)"
    else: v = "mixed"
    return dict(core_verdicts=c, female=f, male=m, ambiguous=sum(x == "ambiguous" for x in c.values()), verdict=v)


def q44_transfers(bundle_dir):
    b = json.loads((REPO / bundle_dir / "bundle.json").read_text())
    out = {}
    for e in b["structures"]:
        s = e["subject"]
        if s.startswith("xfer_vhm2vhf") or s.startswith("xfer_vhf2vhm"):
            out.setdefault(s, []).append(e["id"])
    return out



FINAL_DIRS = {"own_m": "build/q233/viewer_m_hr", "own_f": "build/q233/viewer_f_hr", "base_m": "build/q233/viewer_zan_atlas", "base_f": "build/q233/viewer_base_female",
              "comb_m": "build/q233/viewer_zan_vhm", "comb_f": "build/q233/viewer_zan_female"}
# Q234: the three female pages are read from build/q234 (vagina, ligaments of the uterus / ovary, breasts added) where those dirs exist
for _k in ("own_f", "base_f", "comb_f"):
    _q = FINAL_DIRS[_k].replace("build/q233/", "build/q234/")
    if (REPO / _q).exists():
        FINAL_DIRS[_k] = _q
# Q235: the Imaging-based and Combined female pages are read from build/q235 (clitoris, vestibular bulbs / Bartholin's glands, perineal muscles, urethra, perineal body added from the Chinese Visible Human); Base female was skipped
for _k in ("own_f", "comb_f"):
    _q = FINAL_DIRS[_k].replace("build/q234/", "build/q235/")
    if (REPO / _q).exists():
        FINAL_DIRS[_k] = _q


def load_state(key, dirpath=None):
    import os
    old = os.environ.get("Q233_SRC_" + key)
    if dirpath:
        os.environ["Q233_SRC_" + key] = dirpath
    try:
        return Q.load(key)
    finally:
        if dirpath:
            if old is None: os.environ.pop("Q233_SRC_" + key, None)
            else: os.environ["Q233_SRC_" + key] = old


def rj(name):
    p = REPO / "data/derived" / name
    return json.loads(p.read_text()) if p.exists() else None


ZAN_SEARCH = dict(
    question="Does Z-Anatomy (or BodyParts3D, which it derives from) publish a FEMALE body or female organs we could use? (owner, 2026-10-13: 'Z-Anatomy HAS a female model. Take it!')",
    answer="NO, in everything reachable from the sandbox: Z-Anatomy and BodyParts3D publish one male-derived body and no female reproductive organ. The Z-Anatomy repository's own TO-DO file lists 'CREATE A FEMALE HUMAN MODEL' under MIDTERM goals (not done).",
    checked=[
        dict(what="github.com/Z-Anatomy/models-of-human-anatomy, HEAD e214005da8dc0a226176165f0a4d4e32f2155e0f (2026-10-13), shallow clone through the session git proxy (LFS skipped, nothing needed from LFS)",
             result="files: Z-Anatomy.zip (87 MB, application template with Startup.blend, Blender 3.5, 306 MB), Z-Biomechanics.7z, TA2.csv (terminology only), Readme.md, 'TO DO List'. Startup.blend parsed block by block (7,184 objects, 2,910 meshes, 188 materials): "
                    "NO object named uterus, ovary, uterine tube, vagina, vulva, labium, clitoris, vestibular gland, mons pubis, mammary gland / breast, hymen or cervix. Male-only objects present: testis, epididymis, ductus deferens, ejaculatory duct, seminal gland, prostate, "
                    "corpora cavernosa / spongiosum, glans penis, penis, urethra, testicular vessels. Only 'Mammary region' / 'Inframammary region' skin patches (male contour) exist. The female terms appear only in the label / definition database (TA2 terminology), with no mesh."),
        dict(what="github.com/LluisV/Z-Anatomy branches PC-Version 6c7f9016 (the pinned source of all Z pages, Q186 inventory of 7,013 objects in 9 FBX) and Mobile-Version 7ad7758 (2022, VisceralSystem25.fbx etc., 4,682 files shallow clone)",
             result="same male organs only; no female organ object in any FBX (strings of every FBX scanned: VisceralSystem25.fbx lists penis, testis, epididymis, ductus deferens, seminal gland, prostate)."),
        dict(what="BodyParts3D parts list (github.com/Kevin-Mattheus-Moerman/BodyParts3D, assets/BodyParts3D_data/parts_list_e.txt, 1,894 files listed) and Zenodo 22727173 / 4953712",
             result="parts list: testis, epididymis, seminal vesicle, prostate, penis (+ corpora, glans), scrotum; NO uterus, ovary, uterine tube, vagina, vulva, breast. One body (the male 'TARO' MRI set)."),
        dict(what="z-anatomy.com (web atlas / app), api.github.com, dbarchive.biosciencedbc.jp, lifesciencedb.jp, www.z-anatomy.com", result="blocked by the egress proxy (CONNECT 403) or not served: whether the live web app carries a female model could NOT be checked here"),
        dict(what="Zenodo search (reachable): visible human female organs, female pelvis uterus ovary, BodyParts3D female, Z-Anatomy", result="no female organ mesh set (Zenodo 15882019 = Visible Human MALE organs; 11047831 = male-derived torso organs)"),
        dict(what="HuBMAP Human Reference Atlas 3D Reference Object Library (github.com/hubmapconsortium/ccf-releases, commit b036a91a, public, served by the git proxy; the cdn.humanatlas.io host stays blocked)",
             result="FOUND: Visible Human FEMALE reference organs, CC BY 4.0: VH_F_Uterus, VH_F_Ovary_L/R, VH_F_Fallopian_Tube_L/R, VH_F_Urinary_Bladder, VH_F_Ureter_L/R, VH_F_Pelvis (v1.3, one body frame), mammary glands 3d-vh-f-mammary-gland-l/r (v1.3; sculpted from atlases, "
                    "NOT from the donor: not used in Q233, used in Q234 as a badged REFERENCE MODEL), VH_F_Skin; no vulva / labia / clitoris. Used for the uterus, ovaries, tubes (third_party/hra_vh_f). "
                    "Q234 (2026-10-14): the library repository github.com/hubmapconsortium/ccf-3d-reference-object-library (commit f1a3a63f) also holds VH_F_Vagina and VH_F_Ligaments_Uterus_Ovaries (v1.2, objects of the "
                    "same frame, construction not documented): used for the vagina and the ligaments of the uterus / ovary."),
    ],
    what_the_owner_would_need_to_provide="If a Z-Anatomy female model exists, the exact file is needed: an export (FBX / OBJ / .blend) of that female body or of its female genital collection, or the release URL (the live atlas https://www.z-anatomy.com/ and the Z-Anatomy/The-app repository are not reachable from the sandbox; The-app answers 'not found' to anonymous git). "
                                          "For a vagina / vulva / clitoris / labia, any CC BY / CC BY-SA mesh set of the female external genitalia + vagina would do.")


CLAIMS = [
    dict(where="hub viewer/atlas_hub.html, 'Base · Female'", text="No open female atlas exists to download: Z-Anatomy and BodyParts3D ship one male-derived body. This is that body in its own frame with the male-only organs removed. No female organs are shown and none are invented; nothing is fitted.",
         verdict="accurate before Q233 about the source; the NAME 'Base · Female' still overstates (the skeleton, chest skin and proportions are male-derived, measured below); the 'no female organs' sentence is OUTDATED after Q233 (HRA uterus / ovaries / tubes added)", fix="page title, h1 and sources panel rewritten (data / builder wording, not template code); hub text for the owner to update: see replacement text in PROJECT_STATE Q233"),
    dict(where="hub viewer/atlas_hub.html, 'Combined · Female'", text="The Z-Anatomy body fitted onto the Visible Human female's own skeleton, bone by bone. ... Male-only organs are left out.",
         verdict="true but incomplete: it does not say that the shapes are male-derived (subpubic angle 62.7 deg = male range) and that there was no female organ", fix="page wording now says it; hub text to update"),
    dict(where="hub, 'Imaging-based · Female'", text="Rebuilt from the Visible Human female's CT and cryosections, with her own bladder and rectum.", verdict="accurate; before Q233 she had NO uterus / ovaries / tubes and a male coccyx transferred from the male body (Q44)", fix="uterus, ovaries, tubes added (same-donor HRA organs), male coccyx removed"),
    dict(where="Combined female page, sources panel (builder VHF_WORDING)", text="No female reproductive organs are shown: Z-Anatomy's reproductive organs are male and her own scans carry no uterus or ovary label, so nothing was invented.",
         verdict="accurate before Q233; replaced", fix="builder wording VHF_WORDING"),
    dict(where="Base female page, sources panel (NATIVE_FEMALE_WORDING) + stat line", text="The source has no female body ... This page is the generic Z-Anatomy body ... No female reproductive organs are shown and none were invented ... body proportions, breasts and pelvis are the source's.",
         verdict="accurate and already honest about the body; incomplete about measured dimorphism; replaced", fix="builder wording NATIVE_FEMALE_WORDING, name 'Base · Female (male-derived body)' in scripts/set_titles_q231.py"),
    dict(where="Combined female page, manifest data", text="'female_pelvic_organs': 'none found -- no label ... exists' (Q168 report)", verdict="accurate about HER labels; the page now carries HRA organs instead", fix="none needed (history record)"),
]

LIMITS = [
    "Skeletal measurements use simple geometric landmark rules on decimated meshes of supine cadavers (not hand-placed osteometric landmarks): trust the sign of each difference, not the last digits.",
    "Only the subpubic angle has a verified numeric reference (PMID 32274246); the other measures have a verified DIRECTION (PubMed abstracts) and are scored against the two real donors measured identically (n = 1 + 1, not a norm).",
    "Skull dimorphism (mastoid, glabella, mental eminence, orbital margin) was NOT scored: the skull meshes exist (own pages: cranium, mandible, temporal, zygomatic; Z pages: frontal, occipital, maxilla, temporal, zygomatic, mandible) but automatic landmarking on 7,500-vertex decimated shells is not reliable; qualitative review of renders is left to the owner.",
    "Obturator foramen shape was not measured (the foramen is a thin hole in a decimated shell; two attempts gave no stable outline). The pelvic inlet transverse / AP ratio was attempted by sectioning the P-SU plane and failed (the plane cuts the iliac blades, not the arcuate lines): reported as not measured instead of a wrong number.",
    "Breast volume and gynoid / android fat could not be measured from the skin envelope (supine cadavers with arms on the trunk; the breasts added in Q234 are a sculpted reference model compressed into the skin envelope, not a measurement): the only fat-distribution evidence is the cryosection fat fractions of Q44 (below).",
]
FAT = dict(source="data/derived/subject_anthropometrics.json (Q44, cryosection colour classes, same method on both donors)",
           own_m=dict(thigh_fat_pct=23, thigh_muscle_cm2=442, trunk_fat_pct_levels="45 / 28", bmi=27.8, age=39, stature_cm=180.3, mass_kg=90),
           own_f=dict(thigh_fat_pct=49, thigh_muscle_cm2=219, trunk_fat_pct_levels="52 / 35", bmi=36.0, age=59, stature_cm=157.5, mass_kg=88),
           reading="her thigh fat fraction is more than twice his (49 vs 23 %), trunk 52 / 35 vs 45 / 28 %: a female (gynoid-leaning, obese) fat pattern; the Z pages have no body-composition evidence (generic Z-Anatomy soft tissue).",
           literature="direction only: sex differences in android:gynoid fat and waist-hip ratio exist (PMID 18839131, 22797367); IDF WHR thresholds men 0.90 / women 0.85 are screening cut-offs, not means (PMID 36235677)")


def page_overall(k, pages_before, pages_after):
    b, a = pages_before[k], pages_after[k]
    d = PAGE_META[k]["declared"]
    sk = b["skeletal_overall"]["verdict"]
    sub = [r for r in b["measures"] if r["key"] == "subpubic_angle"][0]
    org_m = [i for i in a["inventory"]["male_only_present"] if i != "male_urethra"]
    org_f = list(a["inventory"]["female_only_present"])
    return dict(declared_sex=d, skeleton=sk, subpubic_angle=dict(value=sub["value"], verdict=sub["verdict"]), male_only_organs_after=org_m, female_only_organs_after=org_f, wrong_sex_after=[w["id"] for w in a["wrong_sex_structures"]])


def build(measures_path):
    M = json.loads(Path(measures_path).read_text())
    before, after = {}, {}
    for k, meta in PAGE_META.items():
        for store, dirpath in ((before, None), (after, REPO / FINAL_DIRS[k])):
            if dirpath is not None and not (dirpath / "index.html").exists():
                S = load_state(k)          # the Q233 page dirs not built yet: describe the published page twice
            else:
                S = load_state(k, str(dirpath) if dirpath else None)
            inv = inventory(S)
            rows = measure_rows(M, k)
            store[k] = dict(label=meta["label"], declared_sex=meta["declared"], source_dir=(meta["dir"] if dirpath is None else FINAL_DIRS[k]), what_the_body_is=meta["body"], structures=len(S), inventory=inv,
                            wrong_sex_structures=judge_inventory(inv, meta["declared"]), measures=rows, skeletal_overall=overall_skeletal(rows),
                            raw_measures={a_: b_ for a_, b_ in M[k].items() if a_ != "skull_meshes_present"}, skull_meshes=M[k].get("skull_meshes_present"))
    pages = {}
    for k in PAGE_META:
        pages[k] = dict(label=PAGE_META[k]["label"], declared_sex=PAGE_META[k]["declared"], what_the_body_is=PAGE_META[k]["body"], before_q233=before[k], after_q233=after[k], overall=page_overall(k, before, after))
    t44 = {"own_f": q44_transfers("build/viewer_f_hr_q224"), "own_m": q44_transfers("build/viewer_m_hr_q224")}
    sexspec = dict(own_f=[dict(id="coccyx", subject="xfer_vhm2vhf", sex_specific=True, why="the coccyx of the MALE body carried onto her (Q44); weakly dimorphic skeletal element and a SECOND coccyx 13 mm below her own (her CT sacrum label already contains it; the HRA VH_F coccyx lies within 2.1 mm of it)", action="REMOVED in Q233"),
                           dict(id="hip_bone_l_zfill203s", subject="xfer_zan2vhf_seams_q203", sex_specific=True, why="a 952-vertex strip of the iliac crest filled from the male-derived Z-Anatomy pelvis (badged 'Filled from Z-Anatomy')", action="kept (a seam fill of 4 mm, badged; replacing needs her missing crest evidence)"),
                           dict(id="levator_ani_*_zfill203s / zfill212, coccygeus_*_zfill203s", subject="xfer_zan2vhf_seams_*", sex_specific=False, why="pelvic-floor muscle continuations from the male-derived Z model (muscle form differs only slightly between the sexes)", action="kept, badged")],
                   own_m=[dict(id="(none)", sex_specific=False, why="his transfers come from HER body (xfer_vhf2vhm*: digastric, internal carotid / jugular, extra-ocular and neck muscles, semispinalis...): none sex-specific")])
    rep = {n: rj(f"Q233_report_{n}.json") for n in ("own_f", "own_m", "comb_f", "base_f")}
    fixes = []
    if rep["own_f"]:
        r = rep["own_f"]
        fixes.append(dict(page="Imaging-based · Female", what="ADDED uterus (with cervix), ovary L / R, uterine tube L / R", source="HuBMAP HRA 3D reference organs of the SAME donor (Visible Human female), CC BY 4.0, registered on her own CT pelvis: scale x%s, surface residual median %s mm (p90 %s)" % (r["registration"]["scale"], r["registration"]["residual_mm"]["median"], r["registration"]["residual_mm"]["p90"]),
                          class_on_page="Source facet class 'Transferred' (template maps subject xfer_* to it; the card badge states 'reference organ of the SAME donor, not measured'): a dedicated class needs a template line (proposal in PROJECT_STATE)",
                          volumes_cm3={k: v["gates"]["volume_cm3"] for k, v in r["organs"].items()}, held=[k for k, v in r["organs"].items() if v.get("held")]))
        fixes.append(dict(page="Imaging-based · Female", what="REMOVED the male coccyx (xfer_vhm2vhf, Q44)", source="her own coccyx is in her CT sacrum mesh; card note added to the sacrum"))
    if rep["comb_f"]:
        fixes.append(dict(page="Combined · Female", what="ADDED the same five organs in her coordinates (her frame)", source="HRA same-donor organs, same transform as the Imaging-based female", volumes_cm3={k: v["gates"]["volume_cm3"] for k, v in rep["comb_f"]["organs"].items()},
                          soft_overlap_flags=[k for k, v in rep["comb_f"]["organs"].items() if v["gates"].get("soft_overlap_flag_gt10pct")], note="overlaps with the Z-Anatomy external iliac vessels / colon / bladder are reported on each card (those are fit estimates, error ~10 mm)"))
    if rep["base_f"]:
        r = rep["base_f"]
        fixes.append(dict(page="Base · Female", what="ADDED the same organs registered on the Z-Anatomy pelvis; renamed 'Base · Female (male-derived body)'; wording and card notes say plainly that the body is male-derived",
                          registration=dict(scale=r["registration"]["scale"], residual_mm=r["registration"]["residual_mm"]), volumes_cm3={k: v["gates"]["volume_cm3"] for k, v in r["organs"].items()}))
    for k, lab in (("own_f", "Imaging-based · Female"), ("comb_f", "Combined · Female"), ("base_f", "Base · Female (male-derived body)")):
        r = rj(f"Q234_report_{k}.json")
        if r:
            st = r["structures"]
            fixes.append(dict(page=lab, what="Q234: ADDED the vagina, the ligaments of the uterus and ovary (HRA objects of the Visible Human female frame, same pelvis registration as the uterus) and both breasts "
                              "(HRA sculpted reference model, registered on the thoracic vertebrae, compressed into the page's skin envelope)",
                              pelvis_registration=dict(scale=r["pelvis_registration"]["scale"], residual_mm=r["pelvis_registration"]["residual_mm"]),
                              thorax_registration=dict(scale=r["thorax_registration"]["scale"], residual_mm=r["thorax_registration"]["residual_mm"]),
                              added=sorted(x for x, v in st.items() if not v.get("held")), held=sorted(x for x, v in st.items() if v.get("held")),
                              volumes_cm3={x: v["gates"].get("volume_cm3") for x, v in st.items() if v["gates"].get("volume_cm3") is not None}))
    for k, lab in (("own_f", "Imaging-based · Female"), ("comb_f", "Combined · Female"), ("base_f", "Base · Female (male-derived body)")):
        r = rj(f"Q235_report_{k}.json")
        if r:
            st = r["structures"]
            if r.get("skipped_page"):
                fixes.append(dict(page=lab, what="Q235: NOTHING added: " + r["skipped_page"], held=sorted(r.get("held", []))))
                continue
            reg = r.get("registration", {})
            fixes.append(dict(page=lab, what="Q235: ADDED the clitoris (cavernous body), vestibular bulbs, Bartholin's glands, bulbospongiosus, ischiocavernosus, superficial and deep transverse perineal muscles, the layers and lumen of the female "
                              "urethra and the perineal body from the Chinese Visible Human young female (Wu et al. 2015, CC BY 4.0; another person's real segmentation, registered onto the page's pelvis by bones: rigid + uniform scale)",
                              registration_scale=(reg.get("scale") or (reg.get("transform") or {}).get("scale")), added=sorted(r["shipped"]), held=sorted(r.get("held", [])),
                              volumes_cm3_page={x: v["volume_page_cm3"] for x, v in st.items() if x in r["shipped"]}))
    if rep["own_m"]:
        r = rep["own_m"]
        fixes.append(dict(page="Imaging-based · Male", what="ADDED the male genital organs his scans do not give (testes, epididymides, deferent ducts, seminal vesicles, penis corpora + glans, male urethra, ejaculatory ducts) as badged Z-Anatomy fills",
                          source="Z-Anatomy male fitted to him (Combined · Male page, his frame), inside his CT skin, out of his bones and pelvic organs", added=[k for k, v in r["organs"].items() if not v.get("held")], held=[k for k, v in r["organs"].items() if v.get("held")]))
    cannot = [
        "Labia majora / minora, mons pubis, vulvar skin surface, ovarian vessels: no open mesh source reached (not in Z-Anatomy, BodyParts3D, the HRA set, the Chinese Visible Human set of Q235; the clitoris, vestibular bulbs / glands, female urethra and perineal muscles of the Imaging-based and Combined female pages are from the Chinese Visible Human, another person, since Q235; Base female has none: its male-derived pelvis does not accept them); her own cryosection photographs show the vaginal and urethral walls and the vestibular erectile tissue as one dark mass (mappings/vhf_pelvic_floor_labels.json 'perineal_other') that cannot be separated at 1 mm. Not built, not invented. (Q234 added the vagina and the ligaments of the uterus / ovary from HRA objects.)",
        "Breasts: the Z-Anatomy chest skin is the male contour (all three Z female-side pages) and her own CT chest is flat (supine cadaver). Q234 added the HRA breasts (a reference model SCULPTED by its author from textbook atlases, NOT donor data) registered on the thoracic vertebrae and compressed into each page's skin envelope: a badged reference model, not a measured breast and not her tissue.",
        "Z-Anatomy-derived skeletons (Base female, Combined female) keep the male-derived pelvis / sacrum / skull shape: Combined female's bones follow hers within ~2 mm median but its subpubic angle reads 62.7 deg (male range) against her 87.3 deg. Replacing those bones with her own would break the fitted ligament / muscle attachments: not done.",
        "Imaging-based male: scrotal / penile SKIN comes from his CT skin (present); his testes etc. are Z fills, not measured; seminal vesicles are not separable on his frozen CT.",
    ]
    return dict(schema="q233_sex_audit_v1", task="Q233 sex-correctness audit of the six current models", generated=datetime.date.today().isoformat(), owner_request="You must make sure the female model is really a woman, and the male is a man.",
                pages=pages, references=REFS, fat_distribution=FAT, q44_transfers=dict(listing=t44, sex_specific_review=sexspec), zanatomy_female_search=ZAN_SEARCH, claims_audit=CLAIMS, fixes_applied=fixes, cannot_be_fixed=cannot, limits=LIMITS,
                honest_names=dict(base_f="Base · Female (male-derived body)", rationale="The Base female page IS the Base male body (identical skeleton: subpubic angle 57.2 deg, same meshes) minus 27 male-only objects, plus HRA organs: it is not a woman's body; it is the male-derived Z-Anatomy body labelled female only by what it lacks and what was added.",
                                  comb_f="Combined · Female (male-derived shapes fitted to her)" , comb_f_note="kept as 'Combined · Female' in the title; the page text states the male-derived shapes"),
                verdict_scheme=dict(values=["male", "female", "ambiguous", "not_measurable", "unreliable"], core_measures=list(CORE), internal_reference=INTERNAL))


def md(A):
    L = ["# Q233 sex-correctness audit of the six models", "", f"Generated {A['generated']}. Owner request: \"{A['owner_request']}\". Machine-readable twin: `data/derived/Q233_sex_audit.json`.", "",
         "## Verdict per page", "", "| Page | Declared | Body | Skeleton (core measures) | Subpubic angle | Male-only organs after Q233 | Female-only organs after Q233 | Wrong-sex structures after |", "|---|---|---|---|---|---|---|---|"]
    for k, p in A["pages"].items():
        o = p["overall"]
        L.append(f"| {p['label']} | {o['declared_sex']} | {BODY_SHORT[k]} | {o['skeleton']} | {o['subpubic_angle']['value']} deg ({o['subpubic_angle']['verdict']}) | {', '.join(o['male_only_organs_after']) or '-'} | {', '.join(o['female_only_organs_after']) or '-'} | {', '.join(o['wrong_sex_after']) or 'none'} |")
    L += ["", "Plain reading: **Imaging-based Male = a man** (subpubic angle 70.7 deg = male range of the verified CT series, 68.6 +- 7.6; the other core measures agree, scored against the two donors); **Imaging-based Female = a woman** (subpubic angle 87.3 deg = the verified female mean 87.4 +- 6.5; the other core measures agree) and, after Q233, carries her uterus, ovaries and tubes (HRA organs of the same donor) and no male coccyx; "
          "**Base Male / Combined Male = male**; **Base Female is NOT a woman**: it is the Z-Anatomy male-derived body (the very same skeleton as Base Male) with the male-only organs removed - its honest name is 'Base · Female (male-derived body)'; "
          "**Combined Female is mixed**: Z-Anatomy male-derived shapes fitted onto her skeleton (notch and ischiopubic index follow her, subpubic angle stays male-range).", ""]
    L += ["## (a) Organ inventory by sex-specific anatomy", ""]
    for k, p in A["pages"].items():
        for st in ("before_q233", "after_q233"):
            s = p[st]; inv = s["inventory"]
            L.append(f"### {p['label']} - {'published sources' if st == 'before_q233' else 'Q233 pages (Q234 for the three female pages)'} ({s['structures']} structures)")
            L.append(f"- male-only present: " + ("; ".join(f"{i} ({', '.join(h['id'] for h in hs)})" for i, hs in inv["male_only_present"].items()) or "none"))
            L.append(f"- female-only present: " + ("; ".join(f"{i} ({', '.join(h['id'] for h in hs)})" for i, hs in inv["female_only_present"].items()) or "none"))
            L.append(f"- surface patches: " + ("; ".join(f"{i} ({', '.join(h['id'] for h in hs)})" for i, hs in inv["surface_patches"].items()) or "none"))
            L.append(f"- wrong-sex structures: " + (", ".join(w["id"] for w in s["wrong_sex_structures"]) or "none"))
            if st == "after_q233":
                for item, hs in list(inv["female_only_present"].items()) + list(inv["male_only_present"].items()):
                    if p["declared_sex"] == "female" and item in inv["female_only_present"] or p["declared_sex"] == "male" and item in inv["male_only_present"]:
                        L.append(f"  - {item}: {hs[0]['provenance']}")
                L.append(f"- expected-but-absent ({p['declared_sex']}): " + ", ".join(inv["female_only_absent"] if p["declared_sex"] == "female" else inv["male_only_absent"]))
            L.append("")
    L += ["## (b) Skeletal / body dimorphism measured on the meshes", "", INTERNAL, "", "| Measure | " + " | ".join(p["label"] for p in A["pages"].values()) + " | male ref | female ref | ref status |", "|---|" + "---|" * (len(A["pages"]) + 3)]
    keys = [r["key"] for r in next(iter(A["pages"].values()))["before_q233"]["measures"]]
    for key in keys:
        cells, ref = [], None
        for p in A["pages"].values():
            r = [x for x in p["before_q233"]["measures"] if x["key"] == key][0]; ref = r
            v = r["value"]; v = (", ".join(f"{a} {b}" for a, b in v.items()) if isinstance(v, dict) else v)
            cells.append(f"{v} ({r['verdict']})")
        L.append(f"| {ref['label']} [{ref['unit']}] | " + " | ".join(cells) + f" | {ref['reference_male']} | {ref['reference_female']} | {ref['reference_status']}: {ref['citation']} |")
    L += ["", "Notes per measure and reliability are in the JSON (`pages.<page>.before_q233.measures[].note / reliability`). Core measures for the skeleton verdict: " + ", ".join(CORE) + ".", "",
          "### Fat distribution (own pages)", "", FAT["reading"], "", f"Evidence: {FAT['source']}. {FAT['literature']}.", "", "### Skull", "", LIMITS[2], "",
          "## Q44 cross-sex transfers (what was carried between the two donors)", ""]
    for body, d in A["q44_transfers"]["listing"].items():
        for sub, ids in d.items():
            L.append(f"- {body}: `{sub}` x{len(ids)}: {', '.join(ids[:12])}{' ...' if len(ids) > 12 else ''}")
    L += ["", "Sex-specific review:", ""] + [f"- {body}: " + "; ".join(f"`{x['id']}` ({x.get('action', x.get('why'))})" for x in lst) for body, lst in A["q44_transfers"]["sex_specific_review"].items()]
    L += ["", "## Z-Anatomy / BodyParts3D female search (owner: 'Z-Anatomy HAS a female model')", "", A["zanatomy_female_search"]["answer"], ""] + [f"- {c['what']}: {c['result']}" for c in A["zanatomy_female_search"]["checked"]]
    L += ["", "What the owner would need to provide: " + A["zanatomy_female_search"]["what_the_owner_would_need_to_provide"], "", "## (c) Declared claims", ""] + [f"- **{c['where']}**: \"{c['text']}\" -> {c['verdict']}. Fix: {c['fix']}" for c in A["claims_audit"]]
    L += ["", "## Fixes applied in Q233", ""] + [f"- **{f['page']}**: {f['what']} ({f.get('source', '')})" for f in A["fixes_applied"]]
    L += ["", "## Cannot be fixed honestly", ""] + [f"- {c}" for c in A["cannot_be_fixed"]] + ["", "## Limits of the measurements", ""] + [f"- {c}" for c in A["limits"]]
    L += ["", "## References (PubMed abstracts read)", ""] + [f"- PMID {r['pmid']}{' doi:' + r['doi'] if r['doi'] else ''}: {r['cite']} - {r['values']} (used for: {r['used_for']})" for r in A["references"]]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--measures", default=str(REPO / "data/derived/Q233_measures.json")); a = ap.parse_args()
    A = build(a.measures)
    (REPO / "data/derived/Q233_sex_audit.json").write_text(json.dumps(A, indent=1, default=float) + "\n")
    (REPO / "data/derived/Q233_sex_audit.md").write_text(md(A))
    for k, p in A["pages"].items():
        print(k, p["overall"]["skeleton"], "| subpubic", p["overall"]["subpubic_angle"], "| wrong after:", p["overall"]["wrong_sex_after"], "| female organs after:", p["overall"]["female_only_organs_after"], "| male organs after:", p["overall"]["male_only_organs_after"])
