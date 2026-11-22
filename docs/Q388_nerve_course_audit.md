# Q388 — nerve course audit (Base · Male, Base · Female)

Owner, 2026-11-22: *"The sciatic nerve runs very close to the ischial tuberosity, unlike reality. Verify where the nerves
run: which muscles they pass between and at what level, and how close they are to the bones."*

Scope: the two Base pages only (`build/q309/viewer_zan_atlas`, `build/q309/viewer_base_female`). Audit read-only on the
tracked data; the one fix (sciatic) is a patch script whose output sits in the scratchpad until the main thread applies it.

## How it was measured

- Geometry decoded from the page files (`scripts/anatomy/q388/lib388.py`, same page I/O as Q340/Q357). Frame (checked on
  the data): mm, +y superior, +z anterior, +x body right. Right and left measured independently, never mirrored.
- Nerve centreline: geodesic-binned centroids of the tube, smoothed (Q249 `lm.centerline`).
- "Inside a muscle / bone": generalised winding number (3-D), and for slices the 2-D winding number of the oriented
  section segments (agrees 100 % with the 3-D number on the tested grids; even-odd parity did NOT — it opened false
  "free" pockets inside the 7-body biceps meshes, an artefact that hid the problem in a first pass).
- Neighbours: first muscle / bone hit by rays from the centre posterior / anterior / medial / lateral.
- Verifier: `scripts/anatomy/q388/verify_nerve_course_q388.py` (offline, ~30 s for both pages) prints one
  `Q388_NERVES_OK|FAIL|NA` line per page × nerve × side × check with the literature tolerance and source.
  Screen of every nerve mesh: `scripts/anatomy/q388/screen_all_nerves_q388.py` (flags, not verdicts).
- Literature: PubMed (DOIs below). Owner's books as knowledge only: Mannan, *Regional Dissection and Surface Anatomy*,
  p. 228–229 (gluteal region relations), p. 539 (surface lines of the sciatic, tibial and common peroneal nerves).

## 1. Sciatic nerve — the owner is right

**Source geometry (both bodies, both sides; Z-Anatomy mesh, Base·F carried by the Q250 bone deformation).** Below the
piriformis the nerve runs on the posterior face of the ischium: at the tuberosity it lies *behind* the bone, 3.7–4.0 mm
from it, **medial to the tuberosity's lateral margin** (Base·M: nerve's medial edge 8 mm medial of the margin; Base·F:
2 mm lateral), with the hamstring origin — not quadratus femoris — directly anterior to it. Below the tuberosity its
centre lies **inside the biceps femoris mesh for ~200 mm** (Base·M y −54…−256, Base·F −49…−249), 2–10 mm deep at the
muscle's medial border. Q146 (2026-09-23, on the Z-Anatomy reference) already saw the 3-D miss (13 % of the IT–GT line vs
38 %) and attributed it to a 2-D/3-D measuring convention; measured against the tuberosity's lateral margin directly, the
miss is real.

| level (right side; left mirrors within 1 mm) | Base·M source | Base·M patched | Base·F source | Base·F patched | literature |
|---|---|---|---|---|---|
| below piriformis (exit) | deep to GMax, on obturator internus 7.5 mm | same (fixed end) | deep to GMax, on OI 11.6 mm | same (fixed end) | below piriformis, Beaton–Anson type a 74 % (Wan-Ae-Loh 2020) |
| sup. gemellus / OI tendon / inf. gemellus | posterior to them, 7–11 mm; 7–10 mm from hip bone, **posteromedial, by the ischial spine** | posterior to sup. gemellus 7.6, OI 9.3, inf. gemellus 5.1 mm; 8–11 mm from bone, lateral of the ischium | posterior to them 11–15 mm | posterior 7–12 mm | over the gemelli and OI tendon (Mannan p. 228–229) |
| quadratus femoris / ischial tuberosity | anterior neighbour **biceps (hamstring origin) 2.6 mm**; hip bone 7.0 mm; femur 43.6 mm | anterior neighbour **quadratus femoris 5.8 mm**; hip bone 12.1; femur 18.4 | anterior **biceps 3.0 mm**; hip 4.0; femur 38.9 | **QF 5.9 mm**; hip 15.7; femur 13.3 | on QF, lateral to the tuberosity (Mannan p. 228–229; Ripani 2006 MRI/cryosection) |
| gluteal fold (IT −40 mm) | **inside biceps femoris** | outside; ST 2.4 posterior, biceps 1.3 lateral, SM 2.2 medial | **inside biceps** | outside; same neighbours | at the ventral end of the long head's medial-border tendon (Bruhn 2009) |
| mid-thigh (50 % femur) | **inside biceps** (30 mm of it posterior) | centre at the SM/biceps junction, ≤ 1.5 mm into SM | **inside biceps** | same, ≤ 1.5 mm into SM | on adductor magnus, crossed posteriorly by the long head (Mannan) |
| distal thigh (70 % femur) | between biceps (lat 10.6) and SM (med 6.6), AM anterior 8.0 | unchanged | same pattern | unchanged | between biceps and semimembranosus |

| check (verifier) | Base·M src R / L | patched R / L | Base·F src R / L | patched R / L | tolerance — source | verdict (source → patched) |
|---|---|---|---|---|---|---|
| nerve medial edge − tuberosity lateral margin | −8.0 / −8.0 | 12.9 / 12.4 | 2.3 / 2.3 | 15.4 / 15.6 | 8–16 mm (12 ± 2, mean ± 2 SD) — Miller 2007 | **off by 16–20 mm (M), 6 mm (F) → OK** |
| min. nerve–hip bone distance at the tuberosity | 3.7 / 3.7 | 9.2 / 9.3 | 4.0 / 4.0 | 11.6 / 11.6 | 3–27 mm (15 ± 6) — Leite 2022 | OK → OK (borderline before) |
| anterior neighbour at QF level | biceps / biceps | QF / QF | biceps / GMax | QF / QF | quadratus femoris — Mannan p. 228–229 | **wrong compartment → OK** |
| crossing of IT–GT line (posterior view, % from IT) | 19.2 / 19.6 | 43.1 / 43.6 | 20.6 / 20.8 | 47.2 / 46.6 | 21.3–54.4 % (37.9 ± 8.3) — Wan-Ae-Loh 2020; "just medial to the midpoint" — Mannan p. 539 | **off by 2 % pts below −2 SD → OK** |
| thigh stations with centre > 1.5 mm inside a muscle | 24 / 24 | 0 / 0 | 24 / 23 | 0 / 0 | ≤ 1 — Mannan; Bruhn 2009 | **wrong compartment → OK** |
| division above the knee joint line | 110.6 / 114.4 | 111.7 / 113.6 | 100.4 / 103.1 | 101.5 / 103.2 | 0–180 mm (60.5 ± 27, 0–115, above the crease — Vloka 2001; 50–180 — Saleh 2009) | OK (1.9 SD above Vloka's mean; crease taken at the joint line — our convention) |
| nerve–femur at the lesser-trochanter level | 38.7 / 38.7 | 26.0 / 26.9 | 40.0 / 40.0 | 25.9 / 23.4 | 0–25 mm (11 ± 7) — Leite 2022 | **off by 14–15 mm → off by ≤ 2 mm (3 of 4 sides just outside)** |

**Fix (rule-based, not sculpted):** `scripts/anatomy/q388/reroute_sciatic_q388.py`. The Z-Anatomy tube keeps its own
cross-section, calibre and vertex/triangle counts (pose-rig contract); each ring is translated by the displacement of its
centreline station. Fixed: the stretch above the inferior border of piriformis (all plexus contacts) and the last 12 mm
before the division (tibial and common fibular start there). Ideal course per station: exit → tuberosity level along a
straight line on the posterior face of the gemelli / OI (Mannan p. 539 "downwards and slightly outwards"); at the
tuberosity the medial edge 12 mm lateral of the tuberosity's lateral margin, on the posterior face of QF (Miller 2007);
below, blended back to the source course over 150 mm. The chain through free space is a Viterbi path (as the Q53 cryo
nerve tracker): unary cost = distance to the ideal + overlap with muscle + depth inside muscle; transition cost = step
between stations. Guards (all pass, every side): centre ≤ 1.5 mm into any muscle and never in bone; no vertex > 1 mm in
bone; tube length +3.1 to +5.3 % (≤ 6 %); max move 32.7–34.1 mm (≤ 45); max turning angle 12–19° (source raw centreline
zig-zags to 146°). Attached rule-based stubs follow (weight 1 at the sciatic, 0 at the far end): the three hamstring
branches (both sides) and the nerve to obturator internus; every nerve that touched the sciatic still touches it
(≤ 3.0 mm; Base·F inferior gluteal L 0.3 → 3.0 mm). Each moved structure's card gets a `Q388` rule-based badge with the
sources. Stated error: ±2 mm at the tuberosity (the cited SD); elsewhere the 0.75 mm grid of the free-space projection.

Not changed and why: the thigh nerve was **not** pushed anteriorly onto adductor magnus. In this model the long head of
biceps abuts adductor magnus; putting the nerve between them would move it ~30 mm deeper, while its skin depth is already
50–57 mm, against ≈ 28 ± 8 mm in Bruhn's volunteers (the nerve lies at the ventral end of a tendon 14–28 mm deep). It sits instead at the biceps / semitendinosus /
semimembranosus junction — Bruhn's "ventral end of the medial-border tendon of the long head". Mid-thigh it still
touches semimembranosus (≤ 1.5 mm overlap), because the source muscles leave no free space there.

**Patched data:** `$S/q388n/patched/viewer_zan_atlas/` and `$S/q388n/patched/viewer_base_female/` (page html,
index.html, four geo files each), reports `Q388_sciatic_<dir>.json`, source checksums `SOURCE_SHA256.txt`.

## 2. Other named nerves (verifier checks)

Values: Base·M R / L, Base·F R / L. The patch does not touch these.

| nerve | landmark / check | Base·M | Base·F | literature (tolerance) | verdict |
|---|---|---|---|---|---|
| common fibular | crosses the fibular neck, below the head tip | 23.3 / 23.3 mm, 1.9 mm from bone | 21.9 / 21.9, 1.9 mm | 20.7 ± 1.0 (Teo 2020, doi:10.1186/s43019-020-00039-2); 14–50 corroborating (Baruah 2018, Dearden 2015, Fongsri 2026); against the bone (Mannan p. 539) | OK (2.6 / 1.2 mm off Teo's mean, inside the corroborating range) |
| radial | contact with the posterior humerus 10.9–17.1 cm above the lateral epicondyle | 0.9 mm (contact 15.8 → 1.0 cm above LE) | 0.9 mm (14.4 → 0.9 cm) | Carlan 2007, doi:10.1016/j.jhsa.2006.07.001 | OK |
| ulnar | behind the medial epicondyle | 8.1 / 8.2 mm posterior to ME, 2.5 mm from bone | 6.7 / 6.9, 1.6–2.1 mm | retro-epicondylar groove (Gray's, knowledge) | OK |
| ulnar | division into superficial/deep branches from the pisiform | 7.2 / 7.2 mm | 7.0 / 7.0 | 8.9 ± 2.5 (Punja 2022, doi:10.1016/j.amsu.2022.103259) | OK |
| median (lateral-root mesh = the page's only median course, runs to the hand) | passage at pronator teres below the interepicondylar line | 40.1 / 42.8 mm | 38.0 / 38.8 | 50.4 ± 10.7 (Gurses 2016, doi:10.1016/j.otsr.2016.08.016) | OK (−1 SD) |
| median (same mesh) | arm: centre inside biceps brachii | 134 / 140 mm | 123 / 128 mm | medial bicipital groove, outside the muscle (Gray's) | **wrong compartment** — but the brachial artery is also 7–10 of 55 stations inside biceps: the biceps mesh overlaps the neurovascular bundle (muscle-side cause, not a nerve re-route) |
| musculocutaneous | pierces coracobrachialis | never enters CB (closest 9.6–10.1 mm; 6.9–7.1 on F); runs 140–160 mm inside biceps and brachialis | same | enters CB 7.7 ± 2.5 cm from the coracoid (Macchi 2007, doi:10.1002/ca.20402); 55.7 mm (Clavert 2009, doi:10.1007/s00276-008-0426-2) | **wrong compartment** (variant "MCN not piercing CB" exists but is the minority; the course inside biceps is not a variant) |
| axillary | intra-deltoid part below the acromion | 46.6 / 45.5 mm | **36.2 / 35.3** | 48.7–60.8 (Cetik 2006, doi:10.2106/JBJS.E.01375; Samart 2014) ± 10 → 40–70 | M OK (low end); **F too high by ~5 mm beyond tolerance, ~13–25 mm above the cited means** |
| femoral | lateral to the femoral artery under the inguinal ligament | 13.5 / 13.5 mm lateral (centres) | 15.1 / 14.6 | lateral (Gray's); FN–FA 3.8 ± 1.8 mm edge gap in adolescents (Gurbuz 2025, doi:10.1186/s12871-025-03020-2) | OK (side right; spacing plausible) |
| tibial | popliteal fossa: posterior to the popliteal artery | 0.8 mm posterior | 0.4 mm | most superficial of the bundle (Gray's) | OK (barely) |
| tibial | ankle: between medial malleolus and calcaneal tendon | 0.6 of the way | 0.6 | midway (Mannan p. 539) | OK |
| tibial | ankle: posterior to the posterior tibial artery | 3.2 mm | 3.1 mm | Gray's | OK |
| deep fibular | with the anterior tibial artery, mid-leg | **11.2 mm** surface gap | **10.7** | accompanies the artery (Gray's); ≤ 6 mm is our stated convention | **off by ~5 mm** |
| saphenous | with the femoral artery in the adductor canal | 0.9 mm | 0.8 mm | Gray's (≤ 10 mm convention) | OK |
| brachial plexus roots | between scalenus anterior and medius | in the groove at 4–6 of 21–22 levels (the upper ones); lower levels 9–29 mm from SA, against or inside scalenus medius | same | interscalene groove (Gray's) | **wrong compartment for the lower roots** (source Z-Anatomy; SA–SM gap there only 4–8 mm) |

## 3. Screen of every nerve mesh (flags; `screen_all_nerves_q388.py`)

Longest mid-course runs with the centre inside a muscle (right side, Base·M / Base·F; left within ±20 mm):

| nerve | run inside | judgement |
|---|---|---|
| sciatic | 199 / 183 mm (biceps femoris, GMax) | wrong — fixed by the patch (0 stations after) |
| obturator | 181 / 166 mm (pectineus, adductor longus, sartorius) | wrong: the divisions run *between* adductor longus/brevis and brevis/magnus; candidate for the next re-route |
| musculocutaneous | 161 / 144 mm (biceps, brachialis) | wrong: lies between biceps and brachialis |
| posterior interosseous | 128–147 / 139 mm (supinator, APL, ECRB…) | partly legitimate (supinator ≈ 4–5 cm); the APL stretch (73–77 mm) is not |
| median (lateral-root mesh) | 121–141 / 125 mm (biceps, PT, FDP) | biceps part wrong (see above); PT and FDS/FDP contact partly legitimate |
| medial antebrachial cutaneous | 117 / 111–113 mm (biceps) | wrong (superficial, medial to the brachial artery) |
| lateral femoral cutaneous | 116 / 140 mm (transversus abdominis) | wrong: crosses iliacus deep to its fascia |
| tibial | 32–100 / 38–92 mm (plantaris, popliteus, soleus, FDL) | partly wrong: passes deep to soleus, not through it |
| superficial fibular | 92–98 mm (fibularis longus/brevis) | partly legitimate (intermuscular / intraseptal course, Valisena 2021 doi:10.1177/10711007211002508) |
| anterior interosseous | 85–90 mm (FDP) | wrong-ish: lies on the interosseous membrane between FDP and FPL |
| deep fibular | 64–81 mm (tibialis anterior distally) | wrong: between TA and EHL |
| femoral anterior cutaneous branches | 79–97 mm (sartorius, pectineus) | partly legitimate (they pierce sartorius) |
| ulnar (arm) | 50–66 mm (coracobrachialis, biceps) | wrong; same biceps-mesh overlap as the median |
| pudendal | 35–46 mm (coccygeus, iliococcygeus) | acceptable at the ischial spine / Alcock's canal level, not verified numerically |

## 4. What could not be verified

- No literature number was found quickly for: sciatic mediolateral position in the mid-thigh, pudendal–ischial-spine
  distance, obturator nerve in the obturator canal, femoral nerve–artery spacing in adults (child data only), deep
  fibular–artery spacing; those rows use Gray's relations with a stated geometric convention.
- The popliteal crease is taken at the knee joint line (no skin-crease landmark on the pages).
- The real Visible Human cryosection sciatic tracks (`data/ct_sources/task_outputs/vh{f,m}_nerves_cryo.nii.gz`) are in the
  imaging pages' own frames, not the Base frames, so they were not used as a direct comparison.
- Only the sciatic was fixed. Obturator, musculocutaneous, LFCN, deep fibular, lower plexus roots and the axillary nerve
  (Base·F) are proposed for the same Viterbi re-route (`reroute_sciatic_q388.py` generalises: ideal course from sourced
  landmarks, free-space chain, same guards); the arm bundle inside biceps brachii needs the muscle mesh checked first.
- Nothing was verified in a browser; the patch has not been regenerated into a page. Pose: vertex counts and order are
  unchanged, so the rig applies as before, but the moved sciatic vertices keep their old skin weights (they stay in the
  hip/thigh segments they had).

## Sources (PubMed, numbers from the abstracts)

Miller SL, Gill J, Webb GR 2007, J Bone Joint Surg Am 89:44–48, doi:10.2106/JBJS.F.00094 · Leite MJ et al. 2022, Hip Int
32:510–515, doi:10.1177/1120700020966255 · Wan-Ae-Loh P et al. 2020, Folia Morphol 79:681–689, doi:10.5603/FM.a2019.0140 ·
Vloka JD et al. 2001, Anesth Analg 92:215–217, doi:10.1097/00000539-200101000-00041 · Saleh HA et al. 2009, Folia Morphol
68:256–259 (PMID 19950076) · Bruhn J et al. 2009, Acta Anaesthesiol Scand 53:921–925, doi:10.1111/j.1399-6576.2009.01982.x ·
Ripani M et al. 2006, J Sports Med Phys Fitness 46:468–475 (PMID 16998454) · Teo HLT et al. 2020, doi:10.1186/s43019-020-00039-2 ·
Carlan D et al. 2007, doi:10.1016/j.jhsa.2006.07.001 · Punja R et al. 2022, doi:10.1016/j.amsu.2022.103259 · Gurses IA et al.
2016, doi:10.1016/j.otsr.2016.08.016 · Macchi V et al. 2007, doi:10.1002/ca.20402 · Clavert P et al. 2009,
doi:10.1007/s00276-008-0426-2 · Cetik O et al. 2006, doi:10.2106/JBJS.E.01375 · Samart et al. 2014, J Med Assoc Thai 97 S8:S27
(PMID 25518290) · Gurbuz 2025, doi:10.1186/s12871-025-03020-2 · Valisena S et al. 2021, doi:10.1177/10711007211002508.
Books (knowledge only): Mannan, *Regional Dissection and Surface Anatomy*, p. 228–229, 539; Gray's Anatomy relations.
