# The viewers: what you are looking at

Two published pages, two bodies, never mixed:

- **Visible Human male** -- https://claude.ai/code/artifact/c5d01522-087e-41aa-88d4-5c26db2dea76
  The atlas's primary body. Lower limb from the Denver (DU) release of the
  same cadaver; everything above the hip from his frozen CT and his colour
  cryosections (both NLM Visible Human Project, public domain). About 300
  structures.
- **Visible Human female** -- https://claude.ai/code/artifact/0651399d-2651-4513-9b56-756a84d55e2e
  A second, model-segmented body: her fresh-cadaver CT, vertex to
  mid-thigh, segmented by TotalSegmentator's free tasks. About 155
  structures. No rule-based muscles here: what the model did not find is
  simply absent.

## The badge on every structure

Each structure carries the subject it came from. The subject id tells you
the source and the method:

| badge prefix | body | source | method |
|---|---|---|---|
| `vhm_both` | male | DU lower-extremity release | manual segmentation by the DU team (their meshes) |
| `ct_vhm`, `ct_vhm_head/headm/neck/neckbv/orbit` | male | frozen CT | TotalSegmentator free tasks |
| `ct_vhm_abd` | male | frozen CT with soft-tissue contrast restored from the cryosections ("hybrid CT") | TotalSegmentator `abdominal_muscles` |
| `ct_vhm_arm` | male | CT + cryosections | HU threshold + marker watershed; elbow region walked through the photographs; hands grouped by planes |
| `ct_vhm_armm` | male | colour cryosections (his arm levels re-streamed from IDC; registered to his CT per slice by whole-body centroid, 12.9 mm median residual between the bone found in the photograph and his CT humerus) | **rule-based** v2: posterior of the coronal plane through the photographed humerus = triceps; anterior within 22 mm of the bone in the distal 65 % = brachialis; proximal 40 %, medial, within 15 mm = coracobrachialis; the rest = biceps; his deltoid, cuff and CT-labelled trunk muscles and the forearm origins lateral of the bone excluded; the brachialis band is 32 mm on him (calibrated to his fascia-traced v1 boundary, 133/189 cm3; hers is 22 mm, the arms having the same radius) -- label volumes biceps 386 / 361, brachialis 140 / 176, coracobrachialis 48 / 41, triceps 549 / 602 cm3; still a compartment rule |
| `ct_vhm_foot` | male | frozen CT feet block | left metatarsals and toe phalanges by planes along the foot axis; used because the DU release files ~22 cm3 of his left metatarsals under 'phalanges' (16.4 / 35.3 cm3 vs his CT 44.9 / 7.2 and the DU right 38.8 / 6.8) |
| `vhm_both` (tarsals) | male | DU release via the recovered bundle | the seven tarsal pieces the release ships separately are named talus, calcaneus, cuboid, navicular, cuneiform medial/intermediate/lateral by a size-and-position rule (`scripts/transfer/name_tarsal_pieces.py`); the order matches the release's alphabetical file order on both sides |
| `ct_vhm_skin` | male | cryosections | tissue silhouette |
| `ct_s1159`, `ct_s1159_abd` | a third body (TotalSegmentator case s1159, CC BY 4.0) | clinical CT | TotalSegmentator; fills only what the male lacks (vessels, quadratus lumborum) |
| `ct_vhf`, `ct_vhf_*` | female | fresh CT | TotalSegmentator free tasks |
| `ct_vhf_skin` | female | CT, plus the photographs for the arms the CT clips (above the pelvis) | body silhouette (HU > -300) united with the cryosection silhouette |
| `ct_vhf_delt` | female | colour cryosections registered to her CT (height corrected 2026-09-13, 0 +- 5 mm) | **rule-based**: the male's deltoid rule adapted to her -- muscle within 55 mm of the humerus, within 25 mm of the outer surface of the muscle compartment (not 40 mm of the skin: her fat is thicker), window 113 mm (his 130 scaled to her scapula), and below the humeral head only the lateral +-80 deg wedge within 40 mm; 226 / 282 cm3 (his rule value 232 / 180), the left still above the lean-section expectation |
| `ct_vhf_armm` | female | colour cryosections registered to her CT (height corrected 2026-09-13, 0 +- 5 mm) | **rule-based**: the male's compartment rules (posterior of the coronal plane through the humerus = triceps; anterior within 22 mm of the bone in the distal 65 % = brachialis; proximal medial = coracobrachialis; the rest = biceps) with, since v2, the humerus located in the photograph (the round hole in the muscle compartment nearest the shifted CT label) and the arm island cut off the trunk; biceps 267 / 224, brachialis 117 / 120, triceps 303 / 337 cm3 |
| `ct_vhf_forearm` | female | cryosections at full resolution (0.33 mm) | **rule-based** right forearm muscles: bones tracked in the photographs, markers by position rules in the radius-ulna frame, boundaries by a marker watershed on the pale fascial lines; twelve muscles shipped, the superficial flexors (PT/FCR/PL/FDS), ECRL/ECRB and supinator/anconeus stay merged and unshipped; FCU and brachioradialis flagged for review (volumes above expectation); volumes in `vhf_forearm_muscles_cryo_report.json` |
| `ct_vhm_forearm` | male | cryosections at full resolution (0.33 mm) | **rule-based** right forearm by her method (bone discs tracked, position rules, pale-line watershed): only flexor digitorum superficialis (54 cm3), profundus (58) and abductor pollicis longus (13) shipped by name; FCU (139), PQ (57), PL (35), ECU, EDM, EI, EPL, EPB came out more than twice the adult expectation and stay in the label volume unshipped, as do the merged radial-flexor, mobile-wad and ED/supinator/anconeus compartments; `vhm_forearm_muscles_cryo_report.json` |
| `xfer_vhf2vhm_neck` | male | transferred from the female | her 16 deep-neck/suboccipital and 10 floor-of-mouth muscles carried onto his bones by the piecewise affine map (he has none of them: his frozen CT cannot separate them and his 1 mm photographs are gone). Doubly derived -- rule-based on her, then transferred -- and badged as such; `data/derived/transfer_report_vhf2vhm_neck.json` records each structure's volume before and after |
| `xfer_vhm2vhf_rhom` | female | transferred from the male | his rhomboid minor (26.0 and 13.6 cm3 after the map) carried onto her, because her own rhomboid mass could not be split; badged as transferred. The forearm and hand transfers were measured and rejected -- that map distorts limb volumes 2-3x, see `docs/GEOMETRY_SOURCES.md` |
| `ct_vhf_hand` | female | cryosections at full resolution (0.33 mm) | **rule-based** right hand intrinsics: adductor pollicis 10.5 cm3 (REVIEW, 1.3x expectation), abductor digiti minimi 5.1, flexor digiti minimi brevis 2.7, opponens digiti minimi 4.9 (hypothenar total 12.7, in range), dorsal interossei 10.5 and palmar interossei 6.9 as groups (about 2.6 and 2.3 cm3 per space). The thenar group (11.3 cm3) is not split: the watershed gave abductor/flexor/opponens pollicis on only 16-23 of the 44 first-metacarpal levels, so it stays merged and unshipped, as do the lumbricals and palmaris brevis. `vhf_hand_muscles_cryo_report.json` |
| `ct_vhf_hyoid` | female | cryosections (1 mm frame) + CT labels | **rule-based** floor of the mouth and extrinsic tongue: mylohyoid (10.4/10.1 cm3, REVIEW: 1.7x expectation), geniohyoid (2.0/2.9), genioglossus (9.1/10.2), hyoglossus (4.2/7.1, left flagged), styloglossus (1.8/1.5). Sternohyoid (1.0) and omohyoid (0.9/0.4) came out as fragments and are unshipped; the stylohyoid corridor carries the posterior digastric belly and stays merged; intrinsic tongue, palate and larynx are beyond 1 mm. `vhf_hyoid_muscles_cryo_report.json` |
| `ct_vhf_dneck` | female | cryosections (1 mm frame) + CT labels | **rule-based** deep neck: semispinalis capitis (35/41 cm3 r/l) and cervicis (15/16), rectus capitis posterior minor (2.2/2.5) and major (2.8/2.6), obliquus capitis inferior (7.4/7.7) and superior (0.5/0.3), longus colli (3.8/2.6) and capitis (2.4/3.6); splenius (one sheet, capitis + cervicis, 79/68) and the lateral erector sink are not shipped; rectus capitis anterior/lateralis and semispinalis thoracis unshipped with reasons in `vhf_deep_neck_cryo_report.json` |
| `ct_vhf_twall` / `ct_vhm_twall` | both | CT labels (total task) | **rule-based** diaphragm (4 mm sheet between lungs/heart and the closed abdominal viscera, costal apposition, crura on L1-L3; 290 cm3 her, 338 him, i.e. 307/359 g against 250-350 g adult) and intercostal sheets between adjacent ribs shipped on `external_intercostals_r/l` standing for all three layers (her 182/172 cm3 HU-gated; his 307/307 geometric only, above expectation); reports `vh{f,m}_trunk_wall_report.json` |
| `ct_vhf_shsp` / `ct_vhm_shsp` | both | cryosections (her) / CT labels (him) | **rule-based split** of the cuff's merged posterior mass into infraspinatus, teres minor and teres major by scapular landmarks (lateral border, inferior angle, glenoid level; her boundaries refined on the fascial lines), plus his rhomboids major/minor cut at the T1-to-spine-root line; her rhomboid mass was unusable and stays unshipped; volumes in `*_shoulder_split_cryo_report.json` (teres minor 44-52, teres major 74-94, infraspinatus 216-248 cm3) |
| `ct_vhf_tarsal` | female | fresh CT | **rule-based split**: her TotalSegmentator tarsal label given voxel by voxel to the deepest of the male's seven transferred tarsal bones (talus, calcaneus, cuboid, navicular, cuneiforms); outer surfaces hers, joint surfaces his shapes on her; volumes in `vhf_tarsals_split_report.json` (calcaneus 56/60, talus 31/33 cm3; the intermediate cuneiform is under-assigned at 0.8/1.4) |
| `ct_vhf_nerve` | female | colour cryosections at full resolution (0.33 mm) registered to her CT | **rule-based tracking**: a nerve is found as a bundle of fascicles (pale honeycomb texture) in the connective tissue between the muscles that bound it, seeded by a landmark rule and chained level by level (Viterbi, jumps <= 8 mm); the montage of every level is the check; ends where the fascicles could not be followed (the sciatic nerve: gluteal fold to the distal thigh, see GEOMETRY_SOURCES) |
| `ct_vhf_pmr` | female | colour cryosections registered to her CT (height corrected 2026-09-13, 0 +- 5 mm) | **rule-based**: pectoralis minor by position (deep to pec major, on the chest wall); her rhomboids are not shipped |
| `ct_vhf_cuff` | female | colour cryosections registered to her CT (height corrected 2026-09-13, 0 +- 5 mm) | **rule-based**: the male's scapular-surface rules (supraspinatus, infraspinatus + teres minor, subscapularis) |
| `ct_vhf_es` | female | CT (model labels) | **rule-based**: erector spinae columns by distance from the vertebral midline (20 / 50 mm) |
| `xfer_vhm2vhf` | female | **transferred from the male**, not measured on her | his structure carried onto her bones by piecewise affine maps; lower-limb muscles re-placed inside her measured muscle compartment and scaled to her measured muscle cross-section (GEOMETRY_SOURCES 'Cross-subject transfer'); boundaries between muscles are his |
| `xfer_vhm2vhf_sep` | female | **transferred from the male**, boundaries refined on her photographs | the 57 thigh/leg muscles of the transfer with the walls between neighbouring bellies moved to her own septa (marker watershed on her cryosections, GEOMETRY_SOURCES 'Boundaries refined to her own septa'); muscle set, attachments and rough shape still his |
| `xfer_vhf2vhm` | male | **transferred from the female**, not measured on him | her structure carried onto his bones by piecewise affine maps (digastric, internal carotid/jugular, and 12 orbit pieces: his frozen-CT orbit segmentation gave 0.08-0.37 cm3 for rectus muscles that are 0.6-0.9 cm3 on her; his three plausible pieces -- left levator, left inferior oblique, left medial rectus -- stay his) |
| `ct_vhf_armb` | female | CT (the arms are clipped by its field of view) | marker watershed: right radius, ulna (partial), hand grouped by planes; no left forearm |
| `ct_vhf_legs` | female | fresh CT, femur-to-toes block registered to her torso block by continuity (+-4 mm in height) | HU threshold split at the joints by a distance-transform watershed; femur united from both blocks; foot bones grouped by planes (not separated) |

## How much to trust a rule-based muscle

`docs/GEOMETRY_SOURCES.md`, section "Rule-based structures", lists every
rule with the measured volume against a textbook range, and
`data/derived/male_rules_vs_female_model.json` puts the male's rule-based
volumes beside the female's model-segmented ones. Read a rule-based muscle
as "this is where the muscle is and roughly how big it is", not as a
traced boundary. The slice renders that would let a reviewer correct each
rule are reproducible from `scripts/cryo/`.

## Depth below the skin

`data/derived/skin_depth_vhm.json` and `skin_depth_vhf.json` give, for
every structure, the shallowest, median and deepest distance of its
surface from the body surface -- the number an injection plan starts from.

For a NERVE the inspector adds "Depth below skin along the course": one row
per 20 mm band of atlas y (the superior axis, y = 0 at the hip-joint midpoint)
with the shallowest point of the nerve in that band and its distance to the
skin mesh of that body. `show` marks that point and the skin point nearest to
it; `needle` lays the needle-path tool from the skin point to the nerve point,
so the report gives the structures the straight path would cross. It is a
measurement on this body's meshes, not a block technique or a recommended
approach (Q58, exporter `depth_profile`).

Page size: an artifact page must stay under 16 MB, so the exporter takes
`--budget-scale` (every triangle budget multiplied; the female chain ships at
0.85 since its 21st subject). The full-resolution meshes are untouched; only
the viewing copies get coarser.

## Needle path

The **Needle path** button in the tool bar turns the two clicks after it
into a straight-line measurement. The first click on any structure sets
the entry point (the exact hit on that surface -- normally the skin, so
switch its system on first); the second sets the target. The target click
looks through the entry structure, so the skin can stay on while you pick
what lies beneath it; hide any other system in the way. The path is drawn
as a thin rod with a green entry bead and an orange target bead, and the
panel above the inspector reports:

- the path length in mm and both points in atlas mm (+X subject's right,
  +Y superior, +Z anterior; origin at the midpoint of the hip joint centres);
- every visible structure the segment passes through, in order from the
  entry, with the depth range along the path (mm from the entry) at which
  the segment is inside that mesh -- e.g. `skin 0.0-38.6, rectus_femoris_r
  20.6-26.8, vastus_intermedius_r 29.1-38.6, femur_r 38.6 (surface
  reached)`. It is found by casting the segment against each shown mesh
  from both ends and pairing the entry and exit hits (an entry is a face
  whose normal points against the path); the skin here is the whole body
  silhouette, so it spans the path from a skin entry, and unmodelled
  tissue (subcutaneous fat) appears as a gap;
- the depth of the target below the skin: the path length when the entry
  is on the skin, otherwise the distance from the target back to the
  nearest skin crossing along the path, skin hidden or not.

A third click starts a new path; **Clear** or Esc removes it; switching
the tool off removes the drawing. Everything is measured on the decimated
viewing meshes the page carries, not on the full-resolution atlas meshes,
and along the path rather than perpendicular to the skin. It is a
geometric measurement for orientation, not a clinical recommendation of
an approach, angle or depth.


## Clinical reference panel

Muscles that carry the owner's compiled clinical block (`clinical` in `data/muscles`, Q60: shoulder, elbow,
wrist and hand intrinsic references, 2026-09) show a "Clinical reference (owner's compilation)" section in
the inspector: the function paragraph, trigger points with their referred-pain pattern, what refers pain
into the muscle, the clinical tests with sensitivity/specificity where a primary study gives one, his
evidence caveat verbatim, and the sources (collapsed). The bundle keys one compact block per muscle, shared
by both sides (`bundle.clinical[base_id]`). It is the owner's reading of the literature he cites, not a
measurement; the caveat in every block says what the referral maps are (expert consensus).
