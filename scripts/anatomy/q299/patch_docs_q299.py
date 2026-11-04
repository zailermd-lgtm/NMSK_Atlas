"""Q299: the documentation / hub edits of this round, applied idempotently.

    python3 scripts/anatomy/q299/patch_docs_q299.py [--check]

Files touched: docs/VIEWER_README.md, docs/GEOMETRY_SOURCES.md, docs/OPEN_ITEMS_FOR_OWNER.md, viewer/atlas_hub.html.
(PROJECT_STATE.md and the Hebrew report are written by hand; the hub version chips are set by --versions.)
"""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

VIEWER_OLD = """(open sheets such as the skin patches, fascia, many tubes with open walls) gets its outline only, never a wrong fill; the count is shown under the button.
Leak statistics per page: `data/derived/Q227_cap_stats_<page>.json`. Structures drawn at less than 20 % opacity (ghosts, faded) are not cut. Shared source:
`viewer/cut_cap/`, synced by `scripts/sync_q227.py`."""
VIEWER_NEW = """(open sheets such as the skin patches, fascia, many tubes with open walls) gets its outline only, never a wrong fill; the count is shown under the button.
**Minimum drawn width** (Q299): a section too thin for the raster to show -- a 1 mm nerve, a 0.9 mm fascial sheet, a tendon cut edge-on -- and an open
sheet whose fill fails the parity test are drawn as a BAND along the structure's own contour segments instead of a 1 px line. It is a thickened outline and
never a fill: no pixel is painted that is not within half a band of a real contour segment, so a parity failure still cannot produce a wrong filled area.
The minimum is 1/500 of the section's own extent (about 2 screen px on a 900 px canvas, so it scales with what is on screen), capped at 2.5 mm and never
thinner than one raster pixel; in the shipped pages it works out at 0.29-1.36 mm, so a 1 mm nerve is drawn about its real size. The structure's own measured
section width is kept beside it (`res.items[].width_mm` against `band_mm`) and the panel states the minimum it used. Measured on 210 axial levels per page:
sections that left no pixel at all in the final cut face fell from 588 / 446 / 3,952 / 4,337 / 4,151 / 5,121 to 212 / 170 / 777 / 779 / 875 / 1,699
(Imaging M / Imaging F / Base M / Base F / Combined M / Combined F); by class, vessel sections went from 527-607 invisible per Z page to 0-5 and fascia from
1,754-1,918 to 44-105. What remains is a structure that another structure genuinely overlapping it is drawn over (the iliotibial tract under the thigh
muscles, the saphenous nerve under its vein, brain substructures inside each other); that needs non-overlapping geometry, not a drawing trick. Raising the
fascia above muscle in the painter order was measured and rejected: it made fascia visible but hid 815 muscles. Report: `data/derived/Q299_crosssection_coverage.json`.
Leak statistics per page: `data/derived/Q227_cap_stats_<page>.json`. Structures drawn at less than 20 % opacity (ghosts, faded) are not cut. Shared source:
`viewer/cut_cap/`, synced by `scripts/sync_q227.py`."""

GEOM_NEW = """

## Q299 (2026-11-01): containment, the pelvic measurements, and the cross-section

The owner reported that the female pelvis is out of proportion with blood vessels crossing out of the body, and that a
cross-section of the male model did not show the peroneal nerve. Three measurements and two fixes came out of it.
Report: `docs/research/Q299_pelvis_containment_crosssection.md`.

**A containment test that works on these pages.** Q297 ran a ray-parity "inside the skin" test and discarded it: the Z
skin is ~250 open patches with no closed envelope, so it called even near-raw geometry 20-100 % outside. Q299 builds a
**voxelised body mask from the page's own outer tissues** instead (`scripts/anatomy/q299/contain299.py`): every triangle
of every `skin` structure plus `fat_subcut_*`, `fat_deep_*` and `soft_unlabelled_*`, area-sampled at >= 1 point / mm2
into a 2 mm grid, closed with an 8 mm morphological closing done as dilate -> flood the *outside* from the grid border
-> erode back (`binary_closing` with an iterated diamond kernel leaves the trunk unfilled: the skin patches of the back
leave 14 mm gaps), largest component. It is **validated before use**, three ways: 26 deep structures that are inside by
construction must come out inside as a group (>= 90 % of them >= 99.5 % inside, group mean >= 99 %), the mask volume must
be a plausible body volume, and the mask boundary must stay within p95 3 mm of a real skin sample. All six pages pass,
with a boundary error band of p50 0.72 / p95 1.31-1.37 / max 7.9-8.3 mm and a group mean of 99.88 %. Distances are not
read off the voxels: a point classified outside is measured against a cKDTree of the same surface samples, so the number
is true millimetres to the nearest real skin surface. Data: `data/derived/Q299_containment{,_before}.json`.

**What it found, and the fix.** On Base F the four `zan_external_pudendal_vein{s}` / `zan_superficial_external_pudendal
_artery` meshes stood up to **21.7 mm in front of the skin** of the mons pubis, with `genitofemoral_n_{l,r}` at 11.5 mm
and the HuBMAP HRA breast objects at 7.3-23.8 mm. Base M is the control and is clean: its only offenders are the six
ocular-surface meshes, because on the male page those same external pudendal vessels end *inside* the external genital
skin that the female pages no longer carry (removed in Q196/Q202 as male-only; the closure that replaced it was removed
in Q297 as generated geometry). The cause of the vessels being outside is recorded in Q250's own report: its skin guard
could not decide inside from outside against open patches and logged 1,057 vertices as "only counted" instead of
pulling them in. **Q299 re-runs that guard against the validated mask** (`fix_contain299.py`): a vertex outside the mask
is moved to the nearest point of the page's own skin / subcutaneous surface and 1.0 mm further in along the same line,
and the displacement is spread over the mesh with the same 8 mm Gaussian Q250 used, so a tube's ring translates instead
of collapsing; then a bone guard pushes back out anything the pull-in drove into a bone. Nothing is sculpted and no
vertex is invented. The four vessels went 21.6-21.7 -> **0.00 mm** with **0 flipped triangles**, area x0.946-0.958,
volume x0.870-0.894. **Policy, stated and tested:** bone is never moved (a bone outside the skin is a registration
residual or a limit of the subject's own segmentation); the ocular surface is exempt by anatomy (the cornea, iris,
sclera and chambers sit in the palpebral fissure and these pages carry no conjunctiva or eyelid-margin mesh); the two
Imaging pages are not touched (their geometry comes from a builder whose matching bundle is not on disk) and their five
offenders are put to the owner instead. The HRA breast objects lose 16-38 % of their enclosed volume when pulled in,
which is stated in full on each of their cards with the two alternatives.

**Bone penetration, measured and not fixed.** The same round tested "intersects bone or passes through the wrong
compartment". Each bone is solidified in its OWN padded bounding box and eroded by a voxel, never as one global bone
mask: a global mask closes the bony rings and its hole fill swallows the mediastinum and the pelvic cavity, which made a
first run call 53 % of Imaging M's `abdominal_aorta` "inside a bone" -- it disappears entirely with per-bone masks.
Result: 51-126 structures per page have vertices deeper than 5 mm inside a bone, nearly all of it Z-Anatomy's own mesh
overlap (muscle origins wrapping bone, psoas on the lumbar bodies) plus fit residual; **1-10 per page lie MOSTLY inside
a bone**, and those are listed in the report. The worst are `zan_calcaneal_branches_of_fibular_artery_{l,r}` at 84-100 %
inside the calcaneus on all four Z pages, `zan_posterior_circumflex_humeral_artery/vein_{l,r}` at 67-80 % inside the
humerus, and `zan_internal_thoracic_veins_{l,r}` at 64-66 % inside the sternum on Combined F. Two of the deepest cases
are anatomically CORRECT and are named as such: the hip articular cartilage lines the acetabulum and the triradiate
cartilage is inside the hip bone, so a mask built from the bone surface legitimately encloses them. **Not fixed**: an
artery that lies inside the heel bone is the source's geometry, not a residual of our fit, and there is no one justified
direction to move 16 vessels and 9 bursae without re-deciding their course from a source. Put to the owner.

**The pelvic measurements.** `scripts/anatomy/q299/pelvis299.py` -> `data/derived/Q299_pelvis.json`: 28 measures per
page (classical pelvimetry, iliac-crest and ASIS breadth, pelvic height, bi-acetabular distance, acetabular version and
inclination in the page's own anterior pelvic plane, sacral breadth / length / curvature, the pubic symphysis, the
shoulder-to-hip ratio, and femur-based stature). The reference is the **47 women of the Q250 set measured with the same
geometric rules** (TotalSegmentator v2.0.1 on Zenodo 10047292, CC BY 4.0), which removes the landmark-definition offset.
**Correction to the record:** Q292's two "out of range" verdicts for Base F do not survive. The same rule gives an inlet
transverse of 176-182 mm on the three *male* pages, where the male literature is near 125 mm, so it cannot be compared
with MR pelvimetry (doi:10.1016/j.ejrad.2018.03.024) at all; and the 47-women set contains no interspinous diameter, so
there is no verdict on that one either. Against the rule-matched reference every classical measure on all three female
pages is within 1.6 SD. Three real defects remain, all in the fit and not in her anatomy: Combined F's bi-acetabular
distance 208.8 mm (+3.64 SD; **+13.1 mm wider than her own CT pelvis**, because Q250 deformed the pelvic bones onto her
pelvis and never re-seated the femora -- its own joint check records the left hip opening 1.0 -> 5.3 mm); Combined F's
greater sciatic notch 74.8 deg (-4.37 SD, against 90.9 on her own pelvis and 92.4 on Base F); and Base F's ischial
length 90.8 mm (+2.20 SD, against her 84.2) with intertuberous 127.1 (+1.54, against her 119.5). Her own pelvis is
genuinely wide (+2.19 SD on her own CT), which is the honest part of what the owner saw; Base F is a further 3.4 % more
hip-dominant than her own body because it keeps Z-Anatomy's shoulder girdle scaled rather than registered onto her
scapulae, so its acromia sit 11.6 mm closer together than hers. All of this is now on the cards of the structures it
belongs to; the two refits that would remove it are put to the owner.

**Acetabular orientation literature read this round (PubMed):** anteversion 15.3 +- 5.7 deg overall, female 17.5 +- 5.6 /
male 13.2 +- 4.9, inclination 37.5 +- 3.9 -- Kim et al. 2021, *Medicine* 100(15):e25445, doi:10.1097/MD.0000000000025445;
anatomic anteversion female 23.4 (11.5-34.5) / male 20.0 (7.5-34.5) deg -- Sautet et al. 2017, *Orthop Traumatol Surg Res*
104(3):347-351, doi:10.1016/j.otsr.2017.10.006; anteversion 23 +- 5, abduction 39 +- 4 deg -- Stem et al. 2006,
*Skeletal Radiol* 35(6):385-9, doi:10.1007/s00256-006-0086-4. The acetabular *diameter* from this round's rule is an
over-estimate and carries no verdict.

**The cross-section.** The owner's case is a content gap, not a mechanism one: **the two Imaging pages carry no fibular
(peroneal) nerve at all** -- **0 fibular meshes against 18 on every Z page** -- so no cross-section of them can show one.
Imaging M carries 16 lower-limb nerves against 85 on Combined M (Imaging F 24 against 83), and the 71 missing include the
whole fibular system and its branches, the femoral, obturator, saphenous, sural and plantar nerves and the sided sciatic.
Inventory: `data/derived/Q299_lower_limb_nerves.json`. On the male Z pages the nerve is present, continuous past the
fibular neck (`common_fibular_n_l` spans y -476.3...-321.1 on Base M and -500.4...-340.6 on Combined M while the fibular
head is at -443.6 / -466.1), and it is drawn in a cut -- 4-6 pixels of the cut face before Q299 and 15-16 after, at the
same 0.40 mm raster.

**The mechanism defect that *was* there, and the fix.** Measured on the shipped pages over 210 axial levels each (7
regions x 30 levels, 207,457 structure sections), sections that left **no pixel at all** in the final cut face numbered
**588 / 446 / 3,952 / 4,336 / 4,155 / 5,114** (Imaging M / Imaging F / Base M / Base F / Combined M / Combined F). The
broken class is **fascia -- 72-78 % of fascial sections on every Z page painted nothing**: a fascial sheet is usually a
single-layer surface, its section is one contour segment, every row has an odd number of crossings, the parity sanity
test fails and the structure was left as a 1 px vector outline. The same for 527-608 vessel sections and 726-835 nerve
sections per Z page. The fix is a **minimum drawn width** in `viewer/cut_cap/cut_cap.js`, described in
`docs/VIEWER_README.md`: **after it, 212 / 170 / 777 / 775 / 878 / 1,701**, with vessel sections 527-608 -> 0-5 and
fascia 1,754-1,918 -> 44-105 per Z page. It only adds pixels, so the Q295 fill requirement holds: the filled area of the
whole cut face at five axial levels per female page is equal or larger after (0.0 to +1.9 %), with the same structures
cut. Report: `data/derived/Q299_crosssection_coverage.json`.
"""

OPEN_NEW = """

## Q299 (1 Nov 2026) -- חמש החלטות בשבילך

הסבב הזה מדד את האגן הנשי, מצא את כלי הדם שיוצאים מחוץ לגוף ותיקן אותם, ותיקן את מנגנון החתך. הפירוט המלא:
`docs/research/Q299_pelvis_containment_crosssection.md`. חמישה דברים לא נעשו בכוונה, כי הם דורשים החלטה שלך.

1. **עצבי הגפה התחתונה חסרים בעמודי ה‑Imaging — זו הסיבה שלא ראית את ה‑peroneal nerve.** בעמוד
   Imaging‑based · Male יש 16 עצבי גפה תחתונה; בעמוד Combined · Male יש 85. **71 חסרים**, וביניהם **כל מערכת
   ה‑fibular — 18 מֶשים בכל עמוד Z מול 0 בכל עמוד Imaging** — וגם ה‑femoral, ה‑obturator, ה‑saphenous, ה‑sural
   וה‑plantar. בעמודים הנשיים: 24 מול 83, 64 חסרים. אין
   שום דבר לתקן במנגנון החתך: העצב פשוט לא קיים בעמוד. בעמודי ה‑Z הגבריים (Base · Male ו‑Combined · Male) הוא כן
   קיים, כן עובר סביב צוואר ה‑fibula, וכן נצבע בחתך — בדוק שם. **מה שאפשר לעשות:** להעביר את העצבים האלה מעמוד
   Combined · Male, שהוא אותו גוף בדיוק (מֶשים של Z‑Anatomy שהותאמו ל‑CT שלו), אל עמוד ה‑Imaging — מֶש אמיתי שעבר
   רישום, עם badge שאומר זאת. לא עשיתי זאת בסבב הזה כי ה‑bundle שמתאים לעמודי ה‑Imaging הנוכחיים אינו על הדיסק
   (קיים רק זה שקודם לתוספות השומן של Q295), ולכן זה דורש הרצה מחדש של שרשרת הבנייה של אותם עמודים. **להעביר?**
2. **שתי התאמות מחדש באגן הנשי, שתיהן נמדדו ושתיהן בסדר גודל של Q250.** (i) **Combined · Female: ראשי הפמור לא
   יושבים בשקע.** המרחק בין מרכזי ראשי הפמור הוא 208.8 מ"מ — 13.1 מ"מ יותר מהאגן שלה עצמה, +3.64 סטיות תקן מ‑47
   נשים שנמדדו באותם כללים. הסיבה: Q250 עיוות את עצמות האגן אל האגן שלה ולא החזיר את הפמורים לשקע (בדיקת המפרקים
   של Q250: מפרק הירך השמאלי נפתח מ‑1.0 ל‑5.3 מ"מ). התיקון מחייב להזיז כל פמור עם כל השרשרת הדיסטלית ועם רקמת
   הגפה הרכה. (ii) **Base · Female: חגורת הכתפיים לא נרשמה אליה.** ה‑clavicle שם 151.5 מ"מ כשאצלה 140.4, ה‑scapula
   171.8 כשאצלה 178.4 / 184.7, ושני ה‑acromia 11.6 מ"מ קרובים מדי — ולכן היחס אגן/כתפיים יוצא 0.921 במקום 0.891
   שהוא היחס של הגוף שלה עצמה. התיקון מחייב להריץ מחדש את שלב ה‑thin‑plate של Q250 עם הנשיאה של הרקמה הרכה.
   **לעשות אחת מהן? שתיהן? להשאיר ולרשום כמגבלה?**
3. **אובייקטי השד של HuBMAP HRA לא מתאימים לעור החזה של Base · Female.** הם בלטו 7.3–23.8 מ"מ מחוץ לגוף. Q299 החזיר
   אותם פנימה, והם איבדו נפח: `breast_fat_l` ×0.616, `breast_fat_r` ×0.743, `mammary_gland_l` ×0.811, רצועות
   התלייה ×0.789 / ×0.798 — הכול כתוב על הכרטיסים. **שתי אלטרנטיבות עדיפות:** (א) להריץ מחדש את הרמת עור החזה של
   Q250 כך שתכסה אותם; (ב) להוריד את אובייקטי ה‑HRA ולהשאיר רק את תווית ה‑CT שלה עצמה (`breast_ct_{l,r}`, שנמצאת
   בתוך הגוף ואינה בולטת בכלל). **מה עדיף לך?**
4. **16 כלי דם ו‑9 בורסות יושבים בתוך עצם.** המדידה (מסכת עצם נפרדת לכל עצם): `zan_calcaneal_branches_of_fibular_artery_{l,r}`
   נמצאים **84–100 % בתוך עצם העקב בכל ארבעת עמודי ה‑Z**; `zan_posterior_circumflex_humeral_artery/vein_{l,r}`
   67–80 % בתוך ה‑humerus; `zan_internal_thoracic_veins_{l,r}` 64–66 % בתוך ה‑sternum ב‑Combined F; וכן
   `zan_subtendinous_bursa_of_teres_major_muscle`, `zan_subtendinous_bursa_of_iliacus_muscle`,
   `zan_plantar_tendon_sheath_of_fibularis_longus_muscle` ו‑`zan_lateral_talocalcaneal_ligament`. זו הגיאומטריה של
   Z‑Anatomy עצמה, לא שארית של התאמה שלנו, ולכן **לא נגעתי בה**: אין כיוון מוצדק אחד להזיז אליו עורק בלי להחליט
   מחדש על מסלולו מתוך מקור. אפשר לדחוף כל קודקוד אל פני העצם הקרובים — זה היה מדביק את העורק על העצם, מה שנכון
   לענף פריאוסטאלי אבל שגוי לכלי שעובר בתוך תעלה. **לדחוף אל פני העצם, להסתיר, או להשאיר ולרשום כמגבלה?**
   (שני המקרים העמוקים ביותר ברשימה **נכונים** ואינם צריכים כלום: סחוס מפרקי מרפד את האצטבולום, וה‑triradiate
   cartilage הוא לוחית הגדילה שבתוך עצם האגן.)
5. **חמש חריגות בעמודי ה‑Imaging שלא נגעתי בהן.** `phalanges_hand_l` ב‑Imaging F בולט 16.4 מ"מ (תווית ה‑CT שלה
   ממזגת את כל האצבעות — Q297 כימת זאת); ב‑Imaging M `deltoid_r_zfill203` 10.5 מ"מ, `dorsal_n_penis_r` 8.7 מ"מ,
   `rectus_abdominis_r_zfill203s` 5.7 מ"מ ו‑`extensor_indicis_r` 5.4 מ"מ. העצם אינה מוזזת לפי מדיניות; שלושת
   האחרים הם חלקי מילוי שנוצרו לפי כלל (Q203) ועצב שנבנה לפי כלל (Q249), וכן ניתן להחזיר אותם פנימה — אבל רק אחרי
   הרצה מחדש של שרשרת הבנייה של עמודי ה‑Imaging (אותה סיבה כמו בסעיף 1). **לעשות את זה יחד עם סעיף 1?**
"""

HUB_PARA = """    <div><b>Since Q299 (1 Nov 2026)</b> nothing on any page stands outside the body any more, except where being outside is the anatomically correct answer. A containment test was built that actually works on these pages &mdash; a voxelised body mask from each page's own skin and subcutaneous tissue, validated against 26 structures that are inside by construction, with its own error band measured (p95 1.3&nbsp;mm) &mdash; because the ray-parity test Q297 tried is meaningless against ~250 open skin patches. It found that on Base&nbsp;&middot;&nbsp;Female the <b>external pudendal veins and arteries stood up to 21.7&nbsp;mm in front of the skin</b> of the mons pubis, with the genitofemoral nerves at 11.5&nbsp;mm and the HuBMAP&nbsp;HRA breast objects at 7&ndash;24&nbsp;mm. Base&nbsp;&middot;&nbsp;Male is clean, which is the whole explanation: on the male page those vessels end <i>inside</i> the external genital skin the female pages no longer carry. The fix is Q250's own skin guard re-run against a mask it can trust &mdash; the guard had logged 1,057 vertices as &ldquo;only counted&rdquo; because it could not tell inside from outside &mdash; and the four vessels went to <b>0.00&nbsp;mm with no flipped triangle</b>. Bone is never moved and the ocular surface is exempt, both stated. The pelvis itself was re-measured against <b>47 women segmented from CT and measured with the same geometric rules</b>: her own pelvis really is wide (+2.2&nbsp;SD), which is her and not a defect, but three fit defects are now stated on the cards &mdash; Combined&nbsp;&middot;&nbsp;Female's femoral heads sit 13&nbsp;mm too far apart because Q250 never re-seated them, its sciatic notch is 16&deg; too narrow, and Base&nbsp;&middot;&nbsp;Female's ischium is 8&nbsp;mm too wide for her. And the cross-section: a section too thin for the raster, or an open sheet that fails the parity test, is now drawn as a band of a <b>minimum drawn width</b> (1/500 of the section, capped at 2.5&nbsp;mm, the true millimetres kept on record) &mdash; measured over 210 axial levels per page, invisible vessel sections fell from 527&ndash;607 per Z page to 0&ndash;5 and fascia from 1,754&ndash;1,918 to 44&ndash;105. The peroneal nerve the owner could not find in a cross-section of the male model is a <b>content</b> gap, not a drawing one: the Imaging pages carry no fibular nerve at all (12 lower-limb nerves against 81 on Combined&nbsp;&middot;&nbsp;Male), which is now written down and put to the owner as a decision.</div>
"""


def edits():
    return [
        (REPO / "docs/VIEWER_README.md", VIEWER_OLD, VIEWER_NEW, "**Minimum drawn width** (Q299)"),
        (REPO / "docs/GEOMETRY_SOURCES.md", None, GEOM_NEW, "## Q299 (2026-11-01): containment, the pelvic measurements"),
        (REPO / "docs/OPEN_ITEMS_FOR_OWNER.md", None, OPEN_NEW, "## Q299 (1 Nov 2026)"),
    ]


def hub_para(text):
    """insert the Q299 paragraph at the TOP of the hub footer's round list (newest first)"""
    if "Since Q299" in text:
        return text, 0
    for n in (298, 297, 296, 295):
        anchor = '    <div><b>Since Q%d (' % n
        i = text.find(anchor)
        if i >= 0:
            return text[:i] + HUB_PARA + text[i:], 1
    raise SystemExit("hub: no 'Since Q29x' footer paragraph to insert before")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    missing = 0
    for p, old, new, marker in edits():
        t = p.read_text(encoding="utf-8")
        if marker in t:
            print(f"{p.name}: up to date"); continue
        missing += 1
        if a.check:
            print(f"{p.name}: MISSING"); continue
        if old is None:
            t = t.rstrip("\n") + "\n" + new
        else:
            assert t.count(old) == 1, f"{p.name}: anchor not found exactly once"
            t = t.replace(old, new)
        p.write_text(t, encoding="utf-8")
        print(f"{p.name}: patched")
    hp = REPO / "viewer/atlas_hub.html"
    t = hp.read_text(encoding="utf-8")
    t2, n = hub_para(t)
    if n and not a.check:
        hp.write_text(t2, encoding="utf-8"); print("atlas_hub.html: Q299 footer paragraph added")
    elif n:
        print("atlas_hub.html: MISSING"); missing += 1
    else:
        print("atlas_hub.html: up to date")
    if a.check:
        sys.exit(0 if missing == 0 else 1)


if __name__ == "__main__":
    main()
