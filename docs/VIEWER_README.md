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
| `ct_vhf_pfloor` | female | CT labels + cryosections (1 mm frame) | **rule-based** pelvic floor: levator ani 36.3/26.4 cm3 (REVIEW: 62.7 bilateral against the 19.8-46.6 of an MRI series, the rule sheet is 10-13 mm where Gray's gives 3-5), coccygeus 4.0/2.4, external anal sphincter 19.6 midline (its top levels share voxels with puborectalis), bulbospongiosus 2.7/2.9 and ischiocavernosus 2.7/1.2 (both include their erectile bodies), deep transverse perineal 1.9/1.4. Superficial transverse perineal (0.8/0.4) is under what the frame supports and is unshipped, as are the obturator internus and perineal sinks. Checked: zero overlap with the bone and organ labels, 76-100 % of every mask on her muscle class. `vhf_pelvic_floor_cryo_report.json` |
| `ct_vhf_popliteal` | female | cryosections at full resolution (0.33 mm) | **tracked** popliteal artery (y -307..-386, median lumen 4.3 mm, 1.30 cm3), popliteal vein (-305..-360, 5.5 mm, 1.34) and tibial nerve (-340..-374, 0.94) -- both lumens under the living 5-8 and 7-11 mm because a cadaveric vessel is contracted and collapsed. Depth order verified on the label volume: artery anterior-most in every band, vein between, nerve 20 mm posterior and 16 mm lateral to the artery. The common fibular nerve was not unambiguous (13 of 32 levels) and is unshipped; the artery's division at the lower border of popliteus is not covered. `vhf_popliteal_cryo_report.json` |
| `ct_vhf_femoral` | female | cryosections at full resolution (0.33 mm) | **tracked** femoral artery (median lumen 5.7 mm, 1.65 cm3), femoral vein (7.8 mm, 2.69 cm3; a collapsed cadaveric vein, under the 9-13 mm textbook figure) and femoral nerve trunk (1.07 cm3, ends 45 mm below the inguinal ligament where it divides). Femoral triangle only, y +14 to -46 mm; the adductor canal and hiatus are NOT covered. Order verified on the meshes: nerve lateral, artery, vein medial and slightly posterior. `vhf_femoral_bundle_cryo_report.json` |
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
| `ct_vhf_breast` | female | fresh CT (Q285) | TotalSegmentator `breasts` task (Apache-2.0) on her own CT, one z-chunk; cut at her own midline (sternum), kept one voxel beneath her body silhouette (the outermost layer is skin), Q193 volume-preserving mesh; right 1004 / left 876 cm3 (13.6 % difference; 94-95 % fat-range HU). Imaging-based Female only: on Combined Female the Z-Anatomy skin is not her skin. The HRA sculpted breast set (Q234) stays on the page, hidden by default; `data/derived/Q285_vhf_breast_report.json` |
| `ct_vhf_breast_fgt` | female | fresh CT (Q287) | **rule-based**: inside her Q285 breasts, voxels at HU >= -30 minus her pectoral / `total` labels and a 2-voxel skin rim; 19.3 / 17.5 cm3, glandular fraction 1.9 / 2.0 % (breast-CT range 1.2-71.9 %, Vedantham 2012). Imaging-based Female and Combined Female. `data/derived/Q287_breast_fgt_report.json` |
| `skin_ct_vhf` on Combined Female (Q287) | female | fresh CT + cryo silhouette | her own whole-body surface replaces the 249 Z-Anatomy skin patches (hidden by default, still listed); her CT breasts added and faded by default; HRA sculpted breast hidden by default. `data/derived/Q287_comb_f_report.json` |
| `ct_vhf_uterus` | female | colour cryosections at full resolution (0.33 mm, every 1 mm), re-registered to her CT (Q288) | **photo-segmented, operator-seeded** uterus (body + cervix): 3-D random walker on the photographs' colour from interior seed discs placed by eye at 18 levels (`data/derived/Q288_seeds.json`; 6 cervix levels also carry paracervical competing seeds); 35.7 cm3 (postmenopausal means 37.1 ml > 5 y / 60.1 ml <= 5 y, Jirapinyo 1998 PMID 9676090); median 30 HU on her CT, 10.8 % fat HU; cervix boundary uncertain (no colour edge). HRA uterus hidden by default on both pages. Imaging-based Female and Combined Female. Vagina, urethra, ovaries, tubes, vestibule, clitoris and bulbs not shipped (`data/derived/Q288_not_shipped.json`). `data/derived/Q288_uterus_report.json` |
| Base Female, Q292 (`breast_ct_*`, `breast_fgt_ct_*`, `urinary_bladder`, `rectum`, `sigmoid_colon`, `uterus_cryo_vhf`, `external_anal_sphincter_ct_vhf` on the Base page) | female | her CT / cryosections, **registered onto the Base body** by the bone spline (Q292) | her own breasts **refitted by stated rules** (rigid chest-wall fit, depth kept, lateral squash beyond 145 mm x 0.35, pushes out of arm / rib cage): 639.2 / 844.1 cm3 = 73.0 / 84.2 % of her CT breasts; glands = Q287 **rule-based** HU; her bladder / rectum / pelvic sigmoid (**measured**, her CT) and uterus (cryosections); her external anal sphincter **rule-based**; chest skin patches fitted onto her skin contour; HRA sculpted breast set, Z bladder / sigmoid / anal sphincter and HRA uterus hidden by default. Card line 'Geometry: ...' names the source. `data/derived/Q292_base_f_report.json` |
| `ct_vhm_hgc` | male | frozen head CT (Q286) | TotalSegmentator `head_glands_cavities` task (Apache-2.0) on his own head-and-neck grid: only his lenses passed the checks (0.24 / 0.23 cm3). His parotid, submandibular glands, soft palate and optic nerves were held: on the frozen CT their edges show 1-4 HU of contrast (gate 5 HU) and his parotids came out 3.3 / 8.9 cm3 (0.12x / 0.32x the cited male mean); his eyeballs were held because this model and the earlier `oculomotor_muscles` model disagree on them by 1.7x. `data/derived/Q286_vhm_head_report.json` |
| `ct_vhf_hgc` | female | fresh head CT (Q286) | the same task on her own head-and-neck grid: submandibular glands 6.6 / 6.5 cm3, lenses 0.29 / 0.23 cm3, soft palate 1.7 cm3. Her parotids (17.9 / 19.5 cm3, 0.83 / 0.90x the cited female mean) were held on the edge-contrast gate (3-4 HU against a 2-voxel shell), her eyeballs because the two models disagree by 1.3x; her optic nerve stays the `ct_vhf_orbit` one. `data/derived/Q286_vhf_head_report.json` |
| `ct_vhm_disc_ts` | male | frozen CT (Q286) | TotalSegmentator `vertebrae_body` task (class `intervertebral_discs`) split by level between his own vertebrae; ships only at C6-C7 (replacing the held Q104 cylinder) and C7-T1 (no disc before), the two levels the Q185c endplate rebuild held; every other level keeps its Q185c mesh. `data/derived/Q286_vhm_spine_report.json` |
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

Since Q188 the needle tool is NOT part of the viewer page: it is the owner's PRIVATE
add-on `clinical/needle_tool.js` (licence: `clinical/LICENSE_PRIVATE.md`), published as a
separate file `clinical_needle_tool.js` next to each viewer page by
`scripts/clinical/stage_clinical_files.py`, together with `clinical_risk.json` and
`clinical_motor_points.json`. The page keeps only a generic hook (a script tag that loads the
file if present, and an anatomy API object: meshes, structure records, picking, visibility,
opacity, camera). Without the file the page is an anatomy-only atlas and shows no needle button.
Rebuilding a page with the current templates but no geometry recompute (regen_cut_q218 -> stage_clinical_files --ultrasound -> set_titles_q231 -> abbrev / calibre / pose-rig injection -> symmetry + plexus sidecars, then a byte-level check against a reference dir) is one command since Q271: `python3 scripts/regen_template_only.py all --out /dev/shm/<round> [--ref DIR]`.
The page itself keeps a general **Cut** mode (Q197, the same on all six pages, desktop and phone): orientation
presets (sagittal / axial / coronal / facing me = the camera direction when pressed) or **Place on model** (then click
or tap the model: the plane passes through that point); the plane is drawn as a translucent rectangle with an arrow to
the removed side; choose the removed side with the two side buttons or **flip side** (default: the +axis side, for
facing me the side nearer the viewer); move the plane along its normal with the mm slider, the -10/-1/+1/+10 mm
buttons, arrow keys (Shift or PageUp/PageDown = 10 mm) or the wheel over the slider; **reset cut**, **exit cut**.
The removed part is clipped for real (every material / fragment, incl. skin and the add-on's halos; the needle
trajectory itself is not clipped, so it stays visible); picking ignores the removed half. By default no cap is drawn: the cut
shows the open surfaces (**Fill cross-section**, Q227, below, fills them). **Slice thickness** (Q218): how much is kept behind the plane, from the whole rest of the body (slider at
its far end, button *all*, the default) down to a slice of 0.5-100 mm (slider, or the 2 / 5 / 10 / 25 mm buttons); the far face of
the slice is drawn as a dashed outline, rendering, picking and the add-on's halos stay inside the slab, *reset cut* and the add-on's
*Cut through target* go back to the whole rest. For the add-on `api.cut()` is unchanged (the kept half); the optional
`api.cutSlab()` (mm, 0 = all) and, on the WebGL pages, `ctx.clip2` give the far face. Shared source: `viewer/cut_mode/`, synced into both templates by `scripts/sync_cut_mode_q197.py`.

**Parts** (Q220, on the Q219 parts model): every structure that has rows in `data/anatomy/structure_parts.json` shows a *Parts* list in
its card (own viewers: the details sheet; Z viewers: the info panel): part name, a type badge (head / origin / insertion / ligament
component / MTJ / fascial passage), a one-line description, the citation (PMID / DOI links), an *unverified* badge where the row is
textbook- or owner-only, and, where the literature disagrees on how many parts there are (semimembranosus 3 / 5 / 6, deltoid 3 / 7,
tibialis posterior 1-4), the disputed counts. Parts that have a position on this body (rule-based on the person's own mesh, or the
place of a Z-Anatomy mesh; never measured) are drawn as point markers for the selected structure, or for all placed parts with the
**Parts markers** button: a hollow ring + label (hover on desktop, tap on touch: source class, error bound, method, citation) and a solid
dot that is depth-tested (hidden behind opaque tissue, visible in x-ray). Markers disappear where Cut mode removes their position
(incl. the slice thickness) and with their structure's layer. Clicking a row focuses its marker, or says *text only (no placement)*.
Data: the sidecar `parts_data.json` beside the page (public anatomy layer, built by `scripts/anatomy/q220/build_parts_sidecar.py`;
absent = no Parts section and no button, nothing else changes). Shared source: `viewer/parts_ui/`, synced into both templates by
`scripts/sync_parts_ui_q220.py`.

**Marked structures and saved selections** (Q227, all six pages, the same code in both templates): a *Marked structures* section above the structure
list. Mark with the tick at the left of every list row (search first, then **Mark list** ticks every match), **Mark selected** (the open card), a
Shift / Ctrl / Cmd-click or a long press on a structure in 3D, or the **Mark** toolbar button / **Mark by clicking** (while on, a click or tap marks
instead of selecting). Marked structures get an amber tint and a removable chip (with the count). **Show only marked** (toolbar: *Only marked* / *Show all*)
hides everything else, **Hide marked** hides the marked ones, **Ghost the rest** draws what would be hidden as faint ghosts that are not pickable.
**Reset selection** (or *Show all*) clears the marks, the isolation, the ghosting, the hover and the card and shows everything again; it does not touch the
cut plane (*reset cut* does that), the layers, X-ray or the source facet. A selection only ever adds a veto, so it composes with the layer toggles, X-ray,
the Source facet, Cut + slice thickness (and the filled cut face) and the Parts markers. **Saved selections**: name + *Save*, pick + *Load* / *Delete*;
stored in the browser (`localStorage`, key `nmsk.sel.v1:<model>`, per model because structure ids differ between models) together with the last
selection (*Remember my last selection*, on by default). Where storage is blocked (private window, embedded page) the sets live in memory for the session
and the panel says so; **Export / Import** moves them as copyable JSON text and **Copy link** makes a `#nmsksel=...` address that opens the same marks
(for the same model only). Shared source: `viewer/selection/`, synced into both templates by `scripts/sync_q227.py`.

**Invert and display states** (Q232, same six pages): **Invert** (toolbar *Invert*, key **I**) swaps the selection: the marked set becomes everything else that is shown (layers, default-hidden flags, the Source facet, the side filter, a solo layer; the cut plane is not considered) and the old marks are listed as *not ...* chips; Invert again swaps back. Marked structures (*Selected*) and all others (*Others*) each get a display state: **Show**, **Fade** (opacity from the *Fade opacity* slider, default 15 %, 0 % = not drawn), **Hide**, **Ghost** (very faint, picked last), **X-ray** (the X-ray look for that group only) and, for the selected group, **Highlight** (solid colour, *Highlight colour*). Presets: *Isolate selected*, *Fade others*, *Fade selected*, *Hide selected*, *Highlight selected*; the Q227 buttons *Show only marked*, *Hide marked*, *Ghost the rest* are the same model (Show / Hide / Ghost). *Mark all visible*, *Mark layer* / *Unmark layer*, *Clear marks*. Keys while something is marked (never while typing): **I** invert, **F** fade the others (Shift+F the selected), **H** hide the selected (Shift+H hide the others); without marks the Z pages' own i / f / h keys (isolate box, fade, hide the open structure) work as before. A hidden structure is not drawn, not pickable and has no cut face; a faded one stays pickable (Z: like any faded structure, when nothing solid is under the pointer) and its cut face is drawn at its opacity (below 20 % none); the needle / ultrasound add-ons read `api.visible(i)` (hidden = not visible, faded / ghost / X-ray = visible), the imaging add-on draws every tissue regardless. Saved sets store the *inverse of* the left-out structures (re-evaluated against what is shown when loaded) plus the states; export, import and the link (`#nmsksel=model~mode~ghost~ids~states`, the last field is new) carry them too; Q227 sets and links still load.

**Filled cut face** (Q227): in Cut mode, **Fill cross-section** fills the cut surface of every shown structure in its own display colour (current tissue /
Source-facet colour, X-ray opacity, layer, hide and selection state) at the cut plane and, when a slice thickness is set, at the far face too, with a
1 px outline per structure, so neighbouring structures are easy to tell apart in a cross-section. It is a real cross-section of the meshes computed in the
browser (signed distance of the vertices, triangle / plane segments, even-odd scanline fill into an id raster, small organs / vessels / nerves painted over
large muscle and fat), shown as a textured quad in the plane; it follows the plane while you drag it (hidden while it is stale, rebuilt in well under half
a second) and every layer / X-ray / selection change. Clicking the cut face selects the structure under the cursor (its card opens), hovering names it,
**Look at the cut face** turns the camera to look straight at the plane. The meshes are not watertight: gaps of the contour up to 1 mm are closed, rows
with an odd number of crossings are repaired from the nearest good row when they are few, and a structure whose fill fails the parity sanity test
(open sheets such as the skin patches, fascia, many tubes with open walls) gets its outline only, never a wrong fill; the count is shown under the button.
**Minimum drawn width** (Q299): a section too thin for the raster to show -- a 1 mm nerve, a 0.9 mm fascial sheet, a tendon cut edge-on -- and an open
sheet whose fill fails the parity test are drawn as a BAND along the structure's own contour segments instead of a 1 px line. It is a thickened outline and
never a fill: no pixel is painted that is not within half a band of a real contour segment, so a parity failure still cannot produce a wrong filled area.
The minimum is 1/500 of the section's own extent (about 2 screen px on a 900 px canvas, so it scales with what is on screen), capped at 2.5 mm and never
thinner than one raster pixel; in the shipped pages it works out at 0.40-1.36 mm, so a 1 mm nerve is drawn about its real size. The structure's own measured
section width is kept beside it (`res.items[].width_mm` against `band_mm`) and the panel states the minimum it used. Measured on 210 axial levels per page:
sections that left no pixel at all in the final cut face fell from 588 / 446 / 3,952 / 4,336 / 4,155 / 5,114 to 212 / 170 / 777 / 775 / 878 / 1,701
(Imaging M / Imaging F / Base M / Base F / Combined M / Combined F); by class, vessel sections went from 527-608 invisible per Z page to 0-5 and fascia from
1,754-1,918 to 44-105. What remains is a structure that another structure genuinely overlapping it is drawn over (the iliotibial tract under the thigh
muscles, the saphenous nerve under its vein, brain substructures inside each other); that needs non-overlapping geometry, not a drawing trick. Raising the
fascia above muscle in the painter order was measured and rejected: it made fascia visible but hid 815 muscles. Report: `data/derived/Q299_crosssection_coverage.json`.
Leak statistics per page: `data/derived/Q227_cap_stats_<page>.json`. Structures drawn at less than 20 % opacity (ghosts, faded) are not cut. Shared source:
`viewer/cut_cap/`, synced by `scripts/sync_q227.py`.

**Imaging** (Q226, PRIVATE add-on, phase 1 = CT + MRI): a second optional file `clinical_imaging_tool.js` (+ `clinical_imaging_tissues.json`) next to the
page adds an **Imaging** button that opens a split screen -- the 3D model with its Cut plane / slab on one side, simulated images of that plane on
the other (tablet portrait: stacked; phone: tabs 3D / Image). It is a **simulation computed from the segmented meshes -- not a scan**, badged on
screen and inside every image: the cut plane (and slab) is intersected with every mesh, each pixel takes the tissue class of the top-most structure,
CT = literature HU per class (windows soft / bone / lung / brain / MSK), MRI = spin-echo / inversion-recovery / gradient-echo equations on literature
T1 / T2 / PD at 1.5 T (T1, T2, PD, PD fat-sat, T2 fat-sat, STIR, FLAIR, T2* GRE, T1 GRE, T1 +/- gadolinium; editable TR / TE / TI / flip angle). Slab
thickness combines sub-slices as average, MIP or MinIP; views = the cut plane plus axial / coronal / sagittal through a crosshair (MPR). The Info panel
lists every tissue class with its source and verification status. Without the files the page is the plain atlas. Details and the exact stage commands:
PROJECT_STATE.md "## Q226".

With the add-on present, the **Needle** button opens its panel. The original measurement is kept:
the first click on any structure sets the entry point (normally the skin, so switch its system on
first); the second sets the target, looking through the entry structure. The panel reports:

- the path length in mm and both points in the viewer's frame (atlas mm for the specimen viewers:
  +X subject's right, +Y superior, +Z anterior);
- every visible structure the segment passes through, in order from the entry, with the depth
  range along the path (mm from the entry) at which the segment is inside that mesh -- found by
  casting the segment against each shown mesh from both ends and pairing the entry and exit hits
  (an entry is a face whose normal points against the path);
- the depth of the target below the skin (Z-Anatomy has no skin: the outermost model surface).

Further modes (entry + direction + length; target first on a cut face or a motor point), the 3-D
needle, motor points, risk halos and safer pathways are documented in PROJECT_STATE.md "## Q188".
Everything is measured on the decimated viewing meshes, along the path rather than perpendicular
to the skin. It is a planning / education aid, not a clinical recommendation of an approach,
angle or depth.


## Clinical reference panel

Muscles that carry the owner's compiled clinical block (`clinical` in `data/muscles`, Q60: shoulder, elbow,
wrist and hand intrinsic references, 2026-09) show a "Clinical reference (owner's compilation)" section in
the inspector: the function paragraph, trigger points with their referred-pain pattern, what refers pain
into the muscle, the clinical tests with sensitivity/specificity where a primary study gives one, his
evidence caveat verbatim, and the sources (collapsed). The bundle keys one compact block per muscle, shared
by both sides (`bundle.clinical[base_id]`). It is the owner's reading of the literature he cites, not a
measurement; the caveat in every block says what the referral maps are (expert consensus).


## Zooming with two fingers (Q290)

Every picture zooms like a page in a phone browser, without opening a menu; the menus themselves never move or scale.

- **3-D model (all six pages, both engines):** pinch to zoom toward the point between your fingers (not the
  screen centre); drag with two fingers to pan -- the anatomy stays under the fingers. One finger still rotates and
  taps still select. On a laptop trackpad, the pinch (which the browser sends as Ctrl + wheel) zooms toward the
  cursor; the plain mouse wheel is unchanged (zoom about the centre), as are mouse drag, right-drag and Shift-drag.
  The cross-section stack, the Learn view and Quick view results live on this 3-D view, so they zoom the same way.
- **Ultrasound image (panel, the US mode and both halves of the full-screen split), CT / MRI slice panes, the
  reference image:** pinch zooms that one image about the point between the fingers and two fingers pan it. The US
  image is magnified (1x to 8x, it never uncovers its frame) while its text -- header, orientation letters, depth
  numbers, the "simulated" badge and the full-screen watermark -- keeps its normal size on the visible part. A CT / MRI
  pane is re-rendered at the new field of view, so its labels stay crisp; a first finger no longer moves the
  crosshair when a second one follows (the crosshair moves on lift-off or on a one-finger drag).
- **Back to 1:1:** a small "2.4x | 1:1" chip appears only while a picture is zoomed; tap it, or double-tap empty
  space (on the US / CT image: anywhere in the image). Home / reset view and the CT field-of-view buttons also clear it.
- **Browser zoom:** the pages no longer forbid the browser's own pinch zoom (the Z-Anatomy pages carried
  `user-scalable=no`). The pictures keep `touch-action: none`, so a pinch on a picture is the picture's zoom and a
  pinch on a panel is the browser's. When the page is opened on its own and the browser zoom is on, the main
  toolbars are redrawn at 1:1 on the visible part of the screen and a chip offers 1:1 (Chrome honours it; on iOS pinch
  out). Inside the claude.ai artifact frame the browser zooms the surrounding page, which this page cannot see --
  the in-picture zoom above is the one that always works.


## Ultrasound frequency, 1 to 18 MHz (Q291)

The private ultrasound add-on chooses the transmit frequency in whole MHz from **1 to 18**, the same way everywhere:
a compact **− / N MHz / +** stepper in the panel's Probe tab, the same buttons around a slider in the US mode card,
and in the full-screen CINE view's ⋯ sheet. It works while CINE plays.

- **Defaults per probe:** linear 10 MHz, convex 4 MHz, sector 3 MHz. The "joint / bursa" diagnostic preset now uses 8 MHz
  (was 7.5); the other presets keep 12 MHz.
- **Typical band (a hint, never a limit):** linear 4-18 MHz (GE ML6-15-D 4-15 MHz; Philips eL18-4, nominal 18-4 MHz,
  broadband rated 2-22 MHz on its product page), convex 1-6 MHz (GE C1-6-D 1-6 MHz; Philips C5-1 5-1 MHz), sector
  1-5 MHz (Philips S5-1 5-1 MHz). Outside the band a short note appears under the stepper; the image is still simulated
  with the same physics. The sources are in `clinical/data/ultrasound_tissues.json` (`freq_band_src` per probe).
- **What changes with frequency:** wavelength 1.54 mm / f (0.086 mm at 18 MHz), axial resolution about 1.25 wavelengths,
  lateral beam width 1.2 λ F / D, and attenuation 0.6 dB/cm/MHz each way. At 15-18 MHz the far field darkens quickly,
  which is the real physics. The probe / depth mismatch note now also gives the highest frequency that still reaches the
  set depth with under 90 dB round-trip loss (for example 18 MHz to 5 cm: "≤ 15 MHz").
- **Display limit:** the image cannot show detail finer than its raster. The axial speckle grain therefore stays at least
  two sample steps long once 1.4 wavelengths is shorter than that, instead of aliasing into pixel noise.

## Learn: simulating a muscle's action, both heads of rectus femoris, fingers (Q293)

- **A two-joint muscle moves both joints at once.** "All together" on a muscle's card now plays every cited action of the
  muscle -- including its parts' (the long head of biceps flexes the shoulder while the muscle flexes the elbow) -- in one
  movement; a direction the parts pull against each other (anterior vs posterior deltoid) is left out, as before.
- **Start position, then the action.** When a joint is already at the end of its range in the cited direction (the model's
  knee is straight, so knee *extension* has no room), the joint is first SET to a start position on the other side -- shown
  for a moment and named in the panel ("Start position (set, not part of the action): Knee flex 60°") -- and then the action
  runs as one movement in the cited direction only. Before Q293 that start position was *animated*, so rectus femoris
  visibly flexed the knee before extending it. The release afterwards returns to the model pose.
- **Heads.** A multi-headed muscle's card lists every head with its origin (Terminologia Anatomica / Gray's Anatomy for
  Students / Moore), and says whether this page draws that head as a structure of its own or as part of the muscle's mesh.
  Rectus femoris has its **reflected (indirect) head** on all six pages since Q293: a RULE-BASED mesh built on each page's
  own hip bone from cadaveric dimensions (its card gives the footprint, length, volume and the sources).
- **Fingers on the Combined pages** were re-articulated in Q293 (each finger bone sits on its parent's joint; Combined ·
  Male's right index finger lies on his own CT index finger); posing the fingers keeps the joints closed.
- Audit of every muscle's attachments, nerves and simulated directions: `docs/research/Q293_muscle_attachment_action_audit.md` (Hebrew).

## Undo / redo, reset, measuring, part slices, less text (Q294)

All of this works the same on the three.js pages (Imaging M / F, Base F) and the Z-Anatomy pages (Base M, Combined M / F),
on a desktop and on a phone.

- **Undo / Redo (60 steps):** the round buttons at the 3-D view's bottom-right corner (and in a workspace mode's bar), or
  Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z or Ctrl+Y. Every change you make is one step: marks, hide / show, display and opacity, the
  selection, Cut mode and the cross-section stack, part slices, measurements and the mode's settings. Moving the camera
  is not a step (Reset view brings it back).
- **Reset (⟲ beside them):** puts everything in the current module back to its start without leaving it -- Undo brings it
  back.
- **Marked / Display:** the top of the Marked-structures section now says in one line what is marked and how the marked
  and the other structures are drawn, plus a count of what is shown, hidden and faded in the scene. One tap each:
  Everything, Only marked, Fade others, Highlight, Hide marked, Fade marked. The per-group settings and "Mark more" are
  folded underneath.
- **Slices of one part:** the "Slices" button opens a short panel: choose a part (a finger, the forearm, the marked
  structures or the open card), the slice thickness, the interval along the part's own long axis, and a display-only
  spread (×1-×5). The spread only moves the drawn slices apart; the true positions and every measurement stay where they
  are. Example: the index finger, 1 mm every 10 mm.
- **Abbreviations and help text:** hover (mouse) or tap a short label to see its full name in a small popup. Explanations in
  the panels sit behind small "i" buttons; status lines stay visible.
- **Measure:** the ruler button (toolbar, or the small ruler on each CT / MRI / ultrasound pane) opens Distance, 3-point
  angle, Angle between two lines and Cobb angle. Tap the points on the 3-D model or on a 2-D pane; the result is a small chip
  (mm or degrees, in that pane's own millimetres). Measurements can be undone and cleared.

### Ultrasound: sheets at their true thickness, re-simulated zoom, probe handling, per-bundle fibres (Q294)

- **Why fascia looked too thick when zoomed (root cause):** a thin sheet (fascia, septum, aponeurosis, retinaculum,
  capsule, dura) was drawn into the simulated image ONE raster pixel wide. Its thickness in millimetres therefore followed
  the pixel -- the depth setting, the quality tier (the live CINE tier is coarser) -- and the Q290 zoom only magnified
  those pixels (4× zoom = a 4× thicker band). Now every sheet is drawn at its typical physical thickness
  (`clinical/data/ultrasound_tissues.json`, `sheet_thickness`: deep limb fascia 0.9 mm -- crural fascia 924 µm, Stecco
  2009, PMID 19242635; fascia lata / iliotibial band 1.0 mm; thoracolumbar fascia 1.0 mm, Langevin 2009, PMID 19958536;
  plantar fascia 3.0 mm; dura 0.5 mm, rule-based) as a disc swept along the sheet, so the band is the same in every
  direction. The only widening is the real one: a sheet cut obliquely is wider in the image by 1 / cos of the angle
  between its surface and the image plane (capped at 3×).
- **Zoom:** a zoomed ultrasound image is re-simulated for the visible window at the finer pixel (the panel, the US mode
  and the full-screen split), so the sheet stays its thickness in mm instead of growing.
- **Placing the probe:** grab the probe on the 3-D view and drag it; it slides over the skin with its axis on the skin
  normal, and the image follows. No "Place on skin" step is needed (that button still works for a jump). A small pad
  beside the probe rotates it 15° (⟲ ⟳) and tilts it 5° per tap toward the marker / away, heel / toe (◀ ▶ ▲ ▼); ⊙ puts it
  upright. The tilt now also applies in the tilt-star mode (the star is taken around the tilted probe). In the US mode on a
  phone the 3-D view is a thumbnail: one tap on its skin moves the probe, and ⛶ (full-screen split) gives the large view
  with the drag and the pad.
- **The transducer:** each type has its own shape: linear (flat face, array + 2.5 mm rim by 13 mm), convex (curved face on
  the array's radius, 20 mm deep), sector / phased (small flat face). The face sits exactly on the skin line where the image
  starts; a ridge on the housing marks the marker end (image left).
- **Fibres per bundle:** deltoid (clavicular / acromial / spinal parts), pectoralis major (clavicular / sternocostal /
  abdominal heads), trapezius (descending / transverse / ascending parts) and rectus femoris (straight and reflected heads)
  each have their own fibre axis and their own cited pennation, in the image and in the 3-D fibre lines. The axis runs
  from the bundle's placed origin marker to its insertion marker where those exist; otherwise from the bundle's origin side
  to the muscle's insertion side (rule-based, stated in the badge). On the Z-Anatomy pages each part mesh is its own
  bundle.

## Fat & unlabelled soft tissue (Q295)

- **A new system on every page, "Fat & unlabelled soft tissue".** Subcutaneous fat, deep fat (visceral and retroperitoneal, ischioanal,
  orbital / buccal, intermuscular, popliteal, heel pad, ...) and unlabelled soft tissue, 51 structures per page, measured from the body's
  own imaging (her CT HU, his colour cryosections; Base pages through a registration onto the Combined page of the same body). Each card
  states the source, the volume, the triangles and, for unlabelled soft tissue, what the Imaging page of the same body segments there.
- **Faint, not hidden.** The system is on at load at 12 % opacity (own engine: the system's opacity slider; Z engine: the layer slider),
  so it does not occlude; its toggle hides / shows it like any other system.
- **Solid in cross-sections.** "Fill cross-section" in Cut mode (and the multi-slice cross-sections, which use the same cut-face kernel)
  fill the fat in its own colour at full opacity even while it is faint in 3-D, so the section shows filling instead of holes. Seams of
  ~2-4 mm between structures remain.
- Imaging and ultrasound: fat maps to the fat class, unlabelled soft tissue to generic soft tissue.
- Audit, before / after per region, montages: `docs/research/Q295_fat_and_voids_audit.md` (Hebrew).

## Inner and middle ear from the SPL Inner Ear Atlas (Q296)

- **Four structures the atlas had no counterpart for, on the four Z pages** (Base · Male / Female, Combined · Male / Female): the
  **bony labyrinth** (cochlea, vestibule and the three semicircular canals as one cavity, ~0.17-0.20 cm3), the **osseous spiral lamina**,
  the **round window (fenestra cochleae)** and the **stapedius** muscle — eight meshes per page (both sides), ~25,000 triangles.
  The three otic-capsule structures sit in the Bones layer beside the page's own malleus, incus and stapes; the stapedius is in Muscles.
- **Imported real meshes, not rule-based.** They come from the SPL Inner Ear Atlas of the Open Anatomy Project (flat-panel CT of a human
  temporal bone, about 140 um), licensed under the 3D Slicer License Part B. Each card names the atlas, its authors, the required
  citation and the licence, and states plainly that the mesh is a MODIFIED version of the atlas model: registered by a similarity fit of
  the atlas's own three ossicles onto THIS page's three ossicles (residual ~0.20 mm median, ~0.57 mm p95), rescaled (the atlas's model
  coordinates are about 3.15x life size), decimated to 40 % of the atlas triangle count, and — on the left side — mirrored, because the
  atlas ear is a right ear.
- **The two Imaging pages are unchanged.** Neither her 1.5 mm CT nor his 1 mm cryosections resolve the ossicles, so those pages have no
  registration target and nothing was added to them.
- Licence, attributions and the full list of modifications: `third_party/openanatomy_spl/` (LICENSE, NOTICE, README.md).
- Survey of all seven Open Anatomy atlases and why nothing else was imported: `docs/research/Q296_openanatomy_survey.md` (Hebrew).

## Provenance audit of every shipped mesh (Q297)

- Every one of the **15,155 meshes** on the six pages was classified: **(a) measured from that subject's own imaging 803 ·
  (b) a real third-party mesh registered onto the page 12,899 · (c) rule-based with a citation 1,451 · (d) unaccounted 0**
  (2 before this round). Script `scripts/anatomy/q297/audit297.py`, data `data/derived/Q297_provenance_audit.json`
  (and `_before.json`), Hebrew report with the per-structure tables `docs/research/Q297_provenance_audit.md`.
- **The female perineum is now shown open.** The patch that used to span it, `zan_skin_perineal_closure`, was geometry
  this project generated (a smooth minimal surface over the rim loop left when Z-Anatomy's male-only urogenital skin was
  removed for a female body) with no anatomical source — 8.33 cm³ on Base F, 16.43 cm³ on Combined F, and on Base F it
  was drawn at page load. It was removed from both pages. No source we hold contains female perineal skin. The
  perineal **muscles** and the **perineal body** are still there and are real (Chinese Visible Human, Wu et al. 2015).
  Select any skin patch around the gap and its card says so.
- **Every rule-based structure is badged and has a volume on file.** Two sets had slipped through: the 68 rule-built
  brachial-plexus meshes on the Imaging pages were printing "Measured on this body", and the 16 brachial cords on the Z
  pages printed the Z-Anatomy geometry line. Both fixed. The viewer renders neither `rec.method` nor `rec.error_band_mm`,
  so a badge must be in `procedural_badge` or in the subject's `SUBJECT_LABELS` description to reach the page at all.
  Volumes for all 1,451: `data/derived/Q297_rule_based_volumes.json`.
- **Breasts**: measured, no mesh defect. The shape is her supine cadaver CT, and on Base F the bone warp doubles the
  left/right difference (27.7 % against her CT's 13.6 %) and flattens the HRA nipple and areola to near zero. Each
  breast card now carries that page's own numbers.
- **Fingertips**: Z-Anatomy ships no nail, nail bed or digital pulp, so there is 0.7–3.3 mm of skin in front of the
  distal phalanx where a real pulp and nail take 3–8 mm; on the Combined pages the Q293 re-seating pushed two tips past
  the skin front. Measured per finger on each card. Nothing was sculpted to hide it.

## Finding a structure by any name, marking several, and the three expansions (Q298)

- **The search defect, stated plainly.** Before this round each engine matched your query as **one contiguous substring
  of one field** — the Z pages `name.toLowerCase().indexOf(q)` on the display name alone, the Imaging pages the same over
  `name + " " + id`. So an abbreviation could never match (no page name contains the letters "itb"), a multi-word query
  failed unless those words were contiguous and in that order (**"iliotibial band" missed "Iliotibial (IT) tract/band"**,
  which contains both words), the Latin / Terminologia name, the group, the system and the part-of parent were never
  searched at all, one typo returned nothing, and the results came back in the page's draw order (Imaging) or
  alphabetically (Z) — never by how well they matched. The structure was there all along, labelled **Iliotibial tract**.
- **Now**: type `ITB`, `IT band`, `iliotibial band`, `tractus iliotibialis` or `הרצועה האיליוטיביאלית` and you reach it,
  and the row tells you which name matched — `Iliotibial tract (ITB)` — so you learn the canonical name. Matching is
  case- and punctuation-blind, folds accents, searches the name, the Latin name, the id, the system, the group and the
  part-of parent, and falls back to one or two typos' worth of edit distance when nothing else matches. Ranking is
  exact alias → exact name → word start → substring → fuzzy, and a whole structure always outranks one of its parts.
- **The data is a real file**: `data/anatomy/synonyms_q298.json` — abbreviations (each a published one; nothing invented),
  English and Latin second names, lay terms, **Hebrew names for every entry** (a project-supplied translation, said so in
  the file: Terminologia Anatomica has no Hebrew edition), and the eponyms this project already cites. Resolved against
  each page's own structure list at build time by `scripts/anatomy/q298/build_search_q298.py`, so nothing is guessed in
  the browser: `data/derived/Q298_search_<page>.json` records exactly what resolved and what did not.
- **Ambiguous abbreviations are not silently resolved.** `GM` is gluteus maximus, gluteus medius and (in EMG) the medial
  gastrocnemius: all are offered and each is named. `TA` offers tibialis anterior and transversus abdominis.
- **Names we cite but do not ship** say so instead of returning nothing: Colles' fascia, Scarpa's fascia, Gerdy's
  tubercle and the pectineal ligament of Cooper each return a line explaining where the project cites them and why no
  mesh carries them. Cooper's ligaments **of the breast** are shipped, on the three female pages.
- **Marking several at once.** Under the search box: **Mark all N** marks every match of the current search — the whole
  result set, not the 260 / 400 the list truncates to — in **one undo step**. **Range** marks a run of rows (tap the
  first, then the last; Shift-click on a desktop does the same without arming anything; a long press on a phone arms it).
  **On model** turns on the engine's own mark-by-tapping mode, which has existed since Q294 behind the Mark button but
  was not discoverable — Shift/Ctrl-click and a long press on the model still work at any time. Everything goes through
  the marked-structures controller, so it composes with the Marked / Display summary and with undo exactly as before.
- **After you pick one structure, three one-tap expansions**, each adding to the marked set as a single undo step:
  - **Adjacent** — *measured on that page's own meshes*: every structure's surface is rasterised into a shared **2 mm**
    voxel grid (sampled at ≤ 1 mm, because 69 % of the triangles on a Z page are longer than 3 mm across and a
    vertex-to-vertex test would miss most real contacts) and two structures are adjacent when their voxels touch — a
    surface-to-surface separation of at most **3.46 mm**. It is a measurement, not an anatomical claim, and the status
    line says so with the count and the threshold.
  - **Related** — the same muscle's other heads and parts, its tendon / aponeurosis / sheath, its bursae, its nerve
    supply, an artery whose own record says it supplies it, the bones it attaches to, the structures of the joints it
    crosses, and its antagonists at a shared joint. Built from the project's own cited data (the Q283 action and
    attachment records, the Q293 heads and audit, the plexus data, each card's own fields). Each kind shows its own
    source; the four that are a rule of this project rather than a cited list — tendon and bursa *by name*, which page
    structures count as a joint, and calling a pair antagonists — are labelled **inferred**.
  - **Functional group** — the named textbook groups (`data/anatomy/muscle_groups_q283.json`), the groups derived from the
    cited action data (every muscle whose own record gives this motion at this joint), and the few extra groups in
    `data/anatomy/relations_q298.json`: the **tensors of the iliotibial tract** (tensor fasciae latae and gluteus
    maximus), the contributors to the calcaneal and patellar tendons, the pes anserinus and the carpal-tunnel contents.
    More than one group normally applies, so the button opens a short menu; one group is one tap.
- Searching a group name (`hamstrings`, `rotator cuff`, `quads`, `calf`, `peroneals`) offers the **group itself** as one
  selectable chip under the search box, with its member count and its source.
- Shared modules, so both engines behave identically: `viewer/q298/` spliced into both templates by
  `scripts/sync_q298.py`; the per-page data rides in the page's `nmsk-q298` block.

## Getting back out, a reset of the model, and a skeleton you can see (Q300)

- **The dead-end problem, stated plainly.** Between them the two engines could make a structure vanish **nine different
  ways**, and each one's way back was somewhere else: the Isolate button in a toolbar that wraps on a phone; the Z pages'
  per-layer **solo**, whose only exit is a button inside a layer row that is gone when the panel is folded; **Marked /
  Others → Hide**, inside a panel you have to open; a structure's own card **hide**, reachable only from that card; the
  **side filter**; the **cut**, the **cross-section** and **part slices**; layers, the source facet and the
  hidden-by-default flag; an opacity low enough to be invisible but counted as hidden nowhere; and worst of all a **Z
  preset**, which quietly assigns opacity 0 to *every tissue it does not name* — so `skeleton`, `nervous`, `vessels` and
  `organs` each erase everything else, and the way back was a button labelled `all`. Nothing on screen said what was
  hidden, and nothing said "show everything". That is the owner's complaint, and it was fair.
- **Now**: the moment anything is hidden, a row of chips appears at the bottom-left of the 3-D view — `isolated: Femur ✕`,
  `solo: muscle ✕`, `hidden: 23 structures ✕`, `preset: bones (9 tissues at zero) ✕`, `side: right only ✕`, `cut ✕` —
  each with its own **✕** that undoes **only that one**, beside a single **Show everything** button that ends all of them
  at once. **Esc** on a desktop does the same, and because it only fires while something is hidden, a second Esc still
  deselects as it always did. Each exit, single or all, is **one undo step**: Ctrl/Cmd+Z puts you straight back where you
  were. When nothing is hidden the row is not rendered at all, so it costs no screen.
- **This is not a list of nine special cases.** Each hiding path registers itself with the shared controller as
  `{key, label, active, clear, drive}`. A path added in a later round that forgets to register is caught by
  `tests/test_q300.py`, which asserts the set per engine and that every entry has both a `clear` and a `drive` — not by a
  user who gets stuck. The pattern is taken from the Human viewer, whose Reset "is hidden by default but appears when one
  of the Explore Tools (i.e., Hide, Isolate, or Fade) has been used"; see `docs/research/Q300_interface_benchmark.md`.
- **Two resets, and the difference is written down.** Q294's circular arrow resets **the module you are in** to its own
  defaults. The new button beside it (a circular arrow with a dot) resets **the model**: pose, camera, which structures
  are shown, isolation and solo, every opacity and fade, the marked structures, the cut and the cross-sections, part
  slices, measurements and labels all go back to **how the page loaded** — one tap, you stay in the module, and one
  Ctrl+Z brings your work back. It leaves alone the module you are in, the work mode, anything saved in this browser
  (saved poses, saved mark sets), the page's browser zoom and the structure cards. The "i" beside the two buttons says
  exactly this. It is exact rather than approximate because it restores the history's own snapshot of the page as it
  loaded, so a provider added in a later round is covered without anyone remembering to add it.
- **Pose is now part of the history**, which it was not before: posing the model is undoable like everything else.
- **Why the skeleton could not be seen in X-ray and in Fade — measured, not guessed.** Three separate causes, all found
  by reading the renderers and confirmed in pixels. (1) On the Imaging pages every soft tissue was drawn at opacity 0.5
  (muscle 0.34) over opaque bone; what survives of the bone is the **product** of (1 − opacity) over everything in front
  of it, so four layers left the bone at about **8 %** of the pixel. (2) On the Z pages the per-tissue X-ray table is
  well judged, but the translucent pass runs with back-face culling off, so every closed shell blends **twice** and the
  product becomes (1 − opacity)² per shell — a few percent through a thick region. (3) In the fade view **one flat 0.15
  was applied to every tissue class**, so bone faded exactly as hard as skin.
- **The fix.** The Imaging pages get a per-tissue X-ray table (bone and nerve solid, cartilage 0.85, vessel 0.8, organ
  0.25, muscle 0.22, other 0.12, fat 0.05) — the one the Z pages already had and these never did. The fade view keeps a
  **floor per tissue class** on both engines — bone 0.55, cartilage 0.40 — so fading the others still leaves you the
  skeleton to orient by, which is what every atlas in the benchmark does. And both engines can draw the bone once more
  after the soft tissue with the depth test off, so its share of the pixel is that pass's strength whatever lies in
  front. Nothing about the geometry changed.
- **What the measurement said, including where it contradicted the plan.** Contrast is the Michelson contrast between
  the mean luminance of the bone pixels and of the soft-tissue pixels around them, read out of the rendered frame.
  On the **Imaging** pages the table is the fix and the pass adds a little on top: X-ray **0.465 → 0.617 → 0.638**,
  fade **0.465 → 0.494 → 0.506**. On the **Base and Combined** pages it turned out the opposite way: their table was
  always right, so against their light background the bone is already the darkest thing on screen (**0.236** in X-ray),
  and painting its own pale colour back over it moves it *toward* the tissue luminance — the pass there *lowers*
  contrast (0.236 → 0.176). So the starting step is **per engine, chosen by measurement and not by symmetry**: the
  Imaging pages start on Clear, the Base and Combined pages on Off, where the control is still there for a structure
  genuinely buried behind something. Every figure is in `data/derived/Q300_browser_check.json`.
- **A strength control, three taps, and only when it is relevant.** While X-ray or Fade is on, a small **Bone: Off ·
  Clear · Strong** control appears (Strong is for a thick region like the pelvis or the shoulder). It is taps rather
  than a slider, it is undoable like everything else, and it is not on screen at all otherwise.
- **A structure's provenance can no longer hide.** Q297 found that neither template ever rendered `rec.method` or
  `rec.error_band_mm`, which is how 68 rule-built meshes came to print the green "Measured on this body". Both now
  render: the Imaging cards carry `rule-based` and `±8 mm` as tags, the Z cards a **Method** line with the error band.

## One control, groups that unfold, and X-ray / CT / MRI on the model itself (Q301)

**The control.** Everything that used to be scattered now sits in one bar at the bottom of the 3-D view, in the thumb
zone, and it never folds away: **Undo · Redo · Reset module · Reset model · ⓘ**, each with its name printed under the
icon. They are the same four the rest of the page uses — the bar mounts Q294's history and Q300's model reset rather
than copying them, and Q294's floating group is switched off so there is one place for them and not two. Above them is
one row of **labelled groups**: View · Layers · Imaging · Cut · Mark · Learn · Measure. One opens at a time; the
others' buttons are not on the screen at all. A group carries a dot while anything inside it is active, so you can see
what is on without opening anything. The groups **adopt the engines' own buttons** — the real DOM nodes are moved in,
keeping their ids and their listeners — so no behaviour exists twice and the old crowded bars empty themselves. The one
thing deliberately kept out of a group is the long tissue-layer table with its own sliders and solo buttons: the group
offers the button that opens that panel instead. On a 390 px phone the group row wraps and every target is at least
44 px; nothing scrolls off the side.

**Which actions combine, and which do not.** Stated in one table and checked in a real browser, never assumed. Cut and
the radiographic styles are combinable and are *shown* as combinable: open the group and the row reads
`+ Cut and the radiographic styles work together: the cut face is drawn in the style's own grey.` An incompatible pair
is disabled with its reason **printed under it**, not hidden in a tooltip a phone never shows — for instance
`⊘ A radiographic style replaces the colour, so colour-by-source has nothing left to colour.` The rule behind the table
is simple: two actions combine when each writes a different piece of state; they do not when they write the same piece,
or when one empties the other's input. There is a third case, written as *"yes, one leads"*: both are allowed and one
quietly takes precedence. The only pair in it is a radiographic style and Q300's extra bone pass — a style sets the
bone's brightness from its own attenuation, so the pass is paused while a style is on and comes back with the colour.
That pair exists because Q300 ships the bone pass **on** on the two Imaging pages: calling it incompatible would have
left the X-ray button disabled the moment those pages loaded. The control that gives way is marked with a downward
arrow and the reason, and neither control is ever disabled.

**X-ray / CT / MRI on the model itself.** This is not the 2-D slice panes: it re-skins the whole model, and one tap on
**Colour** returns. Every number comes from the tissue table the page already ships (`clinical_imaging_tissues.json`,
33 tissue classes with CT attenuation in Hounsfield units and MRI pools at 1.5 T, each value carrying its own
verification status); nothing is retyped in the viewer, and a test fails if it ever is.

- **X-ray** is a digitally reconstructed radiograph. Each structure is drawn translucent with
  `alpha = 1 − exp(−µ·d)`, and ordinary alpha compositing over black accumulates `1 − ∏(1 − alphaᵢ) = 1 − exp(−Σ µᵢd)` —
  which *is* Beer–Lambert's attenuation. `µ/µ_water = 1 + HU/1000` is the definition of the Hounsfield unit, so the
  attenuation itself is not a choice of ours. Two properties make it work on surface geometry: the product does not care
  about draw order, so nothing has to be depth-sorted, and every closed shell is crossed twice, front and back, exactly
  as a real beam crosses it. Bone (µ 2.30) separates from fat (µ 0.89) on its own, so this style does **not** use
  Q300's extra bone pass, and the table says the two cannot be combined.
- **CT** paints each structure the grey its own HU gives through a real window,
  `grey = (HU − (L − W/2)) / W` clipped: **MSK** W1000/L250, **Soft tissue** W400/L40, **Bone** W1800/L400.
- **MRI** paints each structure its spin-echo signal, `S = PD·(1 − e^(−TR/T1))·e^(−TE/T2)`, summed over the class's
  water and fat pools, with the fat pool scaled by the table's own fat-suppression residual: **T1** (TR 500/TE 15),
  **T2** (TR 4000/TE 100), **PD fat-sat** (TR 2500/TE 30).

Each style has three taps of its own, and the right answers come out: cortical bone is white and fat dark in CT, fat is
the brightest thing on T1, free fluid the brightest on T2, and fat is suppressed on PD fat-sat. Measured in rendered
pixels: switching to any style drops the picture's colour saturation from 28–57 to 0–2 and makes 100 % of its pixels
pure grey, and the three styles' mean luminances sit tens of grey levels apart.

**What is ours rather than measured**, all of it also in the ⓘ: the **path length per crossing** in X-ray (a surface
atlas has no thickness along the ray — the three steps were chosen by measuring where the picture's own contrast peaks,
and because the Z pages carry 3,252 meshes against ~950 on the Imaging pages, they start one step softer); the
**flattening of the shading** in CT and MRI, so the renderer's diffuse term does not swamp the grey the table dictates;
the **normalisation** of the MRI greys across the page's classes; the **MSK window**, which the data file itself marks
as a convention and not a citation; and the fact that a bone is one shell, so it is drawn throughout as cortical bone —
the mesh has no inside. Fifteen of the 33 classes carry a CT value the table itself marks `recalled_unverified`; the ⓘ
says how many sit at each status rather than implying all of them are measured.

**All the general prose behind a small circled ⓘ.** One at the side of the 3-D view and one in the control bar, both
opening the same drawer: what this page is and is not, how each style is computed and what in it is convention, the
compatibility table, the layer order, the two resets, and the fat. The licence sheet and the per-structure source panel
are **moved** into the drawer rather than copied, so there is never a second version to fall out of date. The structure
card keeps saying where its own geometry comes from — Q297 found cards that once got that wrong, so per-structure
provenance stays exactly where you are looking, it just stops taking the screen.

**Fat is off when the page loads.** Q295 built the fat and unlabelled-soft-tissue meshes from each body's own imaging in
the space no segmented structure covers, and shipped them on but faint. They are now **off at load** and one tap away in
the Layers group — and either way they **keep filling the cut faces and the cross-sections**, because a section drawn
without them reads as hollow, which was the whole reason Q295 built them. No mesh was added or removed. All six pages
carry 51 such structures, and the control counts them off the page rather than from a number in the code.

**Gradual reveal by layers.** Beside the per-system controls, which are unchanged, there is one **Depth** control that
peels the body inward in taps — `▲ Out` / `▼ In` / `Whole body` — with the layer name and number always on the screen
(Primal Pictures' pattern; Zygote Body's order, "beginning with the skin and working inward towards the skeleton").
The order is this page's own tissue categories and is exactly the order asked for:
**skin → fat / superficial fascia → deep fascia → muscle → ligament → vessels and nerves → organs**, leaving
**bone and cartilage** (7 steps on the Z pages, 6 on the Imaging pages, which carry no `skin` category; a step with
nothing to peel is not offered). The **fat step is the superficial fascia**, by the structures' own Latin names: 17 of
the 51 subcutaneous-fat meshes are labelled *Panniculus adiposus (tela subcutanea)*. What the atlas does not carry is a
separate **membranous (Scarpa's) layer**, and the pages' own search data already says so in as many words — *"No page
ships it as a mesh: the abdominal wall on these pages carries `Investing abdominal fascia` and the subcutaneous fat, not
a separate membranous layer."* — so the peel does not offer one, and a test asserts that absence against the shipped
pages rather than taking it on trust. One grouping is our convention and is named as such in the ⓘ: **vessels, nerves
and lymphatics come off together**, because the data holds no depth rank for a single vessel and real vessels cross
every layer.

Every one of these states is a **single Undo step**, is reached by Q300's **Show everything** (a greyscale model and a
peeled body both get their own chip with its own ✕), and is put back by the **model reset**.

## Q303 — imaging that goes where you already pointed, four views of one model, and nerves you can see

**Imaging centres itself on what you already chose.** Entering CT / MR, the probe, a cut, the cross-sections or one
of Q301's radiographic styles no longer drops you somewhere else and makes you navigate back. The target is decided in
one place and in one fixed order: **the marked structures** (their combined bounding box), then **the structure whose
card is open**, then **the result you picked out of a search**. With none of those, **nothing moves at all** — it never
jumps when there is nothing to jump to, and that is asserted by measuring that the slice point, the probe, the plane and
the camera are byte-identical before and after. The pattern is 3D Slicer's *Jump slices — centered*, which its Markups
module offers as an explicit choice against *offset*; so it is a choice here too, with **Follow what I chose** in the
View group, on by default and remembered in this browser. What "centred" means is written in each mode's own terms: the
**CT / MR** slice point becomes the centre and every pane's own in-plane centre is released so it follows it, which is
the slice level and the in-plane position in one move; **the probe** (the private sonography add-on, which the public
layer may not name, so this round finds both clinical tools by their shape rather than by their name) is seated on the
skin where a ray from
the camera through the centre meets it, falling back to the six anatomical directions when no skin lies along that ray;
the **cut plane keeps the orientation you chose** and only slides along its own normal; the **cross-section stack** is
centred on that same plane, or in part mode takes the structures you chose as its part; and a **radiographic style**
frames the camera on them. A line on the screen says what it centred on and why, each centring is a **single Undo
step**, and both resets undo it.

**Four views of the same model at once.** One **Four views** button in the View group turns the 3-D view into four
panes — **Anterior · Lateral · Superior · 3-D** — each with its own camera. The set is 3D Slicer's *Four-Up* convention
(three orthogonal slice views plus the 3-D view; for a surface model the equivalent of a slice normal is looking along
that anatomical axis), and Visible Body's own single-view presets are the same directions. We found no documentation for
a four-pane layout in any commercial anatomy atlas, so the grid is Slicer's idea and **which quadrant holds which pane
is ours** — the free view sits where Slicer puts the 3-D one, and the ⓘ says so. It is **one model seen four ways, not
four models**: selection, marking, hiding, the layers, the depth peel, the radiographic style and the cut are the
engine's single state, and the panes are four viewports over that one scene, so they cannot disagree. The pane you touch
owns the camera, so dragging, the wheel and pinch act on it alone; tapping a pane's square shows only that pane, and
restore brings the four back. Entering, expanding and restoring are each **one Undo step**, and the model reset returns
a single view. **At 390 px it stays 2×2, and that was decided by measuring:** each pane is **195 × 422 CSS px**, every
pane's square is 25 × 24 px and hit-testable, a real touch inside a pane picks the structure under that pane's own
camera, and there is no horizontal scroll — so no 2-up fallback was needed. While four panes are on, the overlays that
are drawn for *one* camera over the whole canvas — the structure labels, the axis gnomon, the scale bar, the cut
outline, the part markers and the measuring chips — **stand down** rather than being drawn in the wrong place; expanding
a pane brings them straight back, and Measure is marked incompatible with four panes for exactly that reason, with the
line *"Tap a pane's square to show only that pane, then measure there"* printed under it.

**"Facing me", and views you can name.** **Facing me** turns the selected structure to face you. The rule is one line,
and it is one rule rather than two on purpose: **the camera looks along the structure's own axis of least spread** — the
minor principal axis of its vertices. For a flat structure that axis *is* the surface normal, so the broad face turns
toward you; for a tube it lies across the shaft, so the long axis runs across the screen at full length instead of
pointing at you. Blender's *Align View to Active* is the precedent and uses two rules for these two cases (an object
axis, or a face normal in Edit Mode); the single rule was chosen because it becomes each of them, and because it is
measurably the largest view of the structure there is — the silhouette's area goes as the square root of the product of
the other two eigenvalues, so looking along the smallest wins by √(λ₁/λ₃), and the per-structure figure is reported.
The camera ends **within 2° of that axis** (measured: 0.000°; the only limit is the pole of the az/el parameterisation,
which both engines share, so the arithmetic is identical in both). The sign is chosen to keep the camera on the side it
is already on, so it never swings round the body. Beside it, **Save this view** remembers where the camera is now under
a name and brings it back **in one tap** — the pattern Visible Body documents as storing a view on a key and pressing
that key again. Up to eight, kept in this browser only; a saved view holds the **camera and the pane layout and nothing
else** (deliberately not the model's visibility, which would quietly reopen the door Q300 closed), and neither reset
touches the list. The standard views — front / side / back and each engine's own reset — are unchanged.

**The nerves, including the small ones.** Why they were invisible was measured before anything was changed, not guessed.
The pages already carry their own calibre table (Q240 — every artery, vein and nerve's diameter measured off the mesh),
and it says what the problem is: the **median nerve diameter is 1.0 mm on the four Z pages** (0.13–7.8 mm) and 1.4–1.8 mm
on the two Imaging pages, while a whole-body view puts the body's full height into the height of the 3-D view, which is
about **1.9 mm per pixel**. So most nerves are drawn **well under one pixel wide** — at that scale **357 of the 439** nerves on Base M, **111 of 201** on Imaging M, about **81 %** of them on a Z page. Nothing is wrong with the mesh, the
decimation or the draw order — the structure is simply sub-pixel, and no colour or opacity rescues a line thinner than a
pixel. The answer is the pattern this project has already proven twice rather than a third invention: Q299's **minimum
drawn width** for a thin section, and Q300's **extra pass after the translucent one** so a structure's share of the pixel
does not depend on how many layers lie in front of it. **Nerves** in the View group is three taps — **Off · Clear ·
Strong** — and draws an extra pass over the nerves' own vertices, after everything, on the camera-facing half of the
model, each vertex a round dot whose width is `max(the step's minimum in pixels, the nerve's true width in pixels)`. A
nerve already wider than the minimum is **not touched**. **Which structures it covers is the page's own answer, not
ours:** every structure the calibre table records as a nerve — 439 of the 552 nerve-category meshes on a Z page, and
on the two Imaging pages 201 and 244 when this was written, 272 and 308 after Q304 added their lower-limb nerves — the
trunks and every named branch, the small ones included. The rest of the nerve and
`cns` categories is the spinal dura, the cord, its tracts and its nuclei (`Lateral fasciculus proprius`,
`Intermediolateral nucleus` and the like); none of those is a peripheral nerve you would want widened, they are more
than half the vertices in those two categories, and the control says how many it is leaving as they are. The shader is one GLSL string carried byte-identical by both
templates — compiled by the Z engine into a tiny program of its own and by the own engine into a `RawShaderMaterial` —
so the two engines run the same arithmetic, which is the rule Q301 set when it refused to ship physics they would have
computed differently. **The honesty rule:** no mesh is changed and no geometry is written; the **true calibre stays the
record** and is what the structure's card and the vessel / nerve legend print, the control states how many nerves carry
a measured diameter and how many have none, and the emphasis is labelled a **display aid** everywhere it appears. It
composes with what is already there: it switches the **nerve system toggle** on rather than fighting it, it is clipped
by the cut, it survives the depth peel and Q300's fade, and the motor points / NMJ markers follow the needle tool's own
*Emphasize motor points*, which this control switches on with it rather than drawing a second set that could fall out of
step. With a **radiographic style** on it is marked incompatible, per Q301's own rule, and says what to use instead: a
greyscale picture has no highlight colour. And where a page simply does not carry a nerve, the control **says so** — when this was written the
two Imaging pages shipped no fibular (peroneal) nerve at all, which was Q299's finding; Q304 carried 18 onto each of
them, and the sentence on the screen shrank by itself because the probe reads the page's own list. Emphasis still
cannot show a nerve that is not there.

Every one of these is a **single Undo step** and is put back by the **model reset**. Three of them needed state that
Q294's history deliberately does not watch — the camera, the clinical tools' slice point and probe pose, and the four
panes' cameras — so they go through one small module that keeps a **counter** in the history and the values beside it:
one history entry per action, one press of Undo to go back, and no unrelated Undo ever moves the camera. The first draft
published a "before" value and committed it, which produced two entries and a second Undo press that did nothing
visible; this round's own standalone harness caught that before either template was touched.

## Q304 — the lower-limb nerves the Imaging pages did not have, and a calibre you can check

The owner reported that he could not see the **peroneal nerve** in a cross-section of the male model. Q299
measured why and did not fix it: the two **Imaging-based** pages carried **no fibular (peroneal) nerve at all**
— 0 meshes against 24 on each Z page — and 71 lower-limb nerves fewer than the Combined page of the *same*
body. Q304 carries them across. 71 structures onto Imaging · Male and 64 onto Imaging · Female: the whole
fibular system (18 per page), the femoral, obturator, saphenous, sural and plantar nerves, the sided sciatic and
their named muscular branches. A cross-section at the level of the common fibular nerve now shows it — measured
in the browser on the page's own cut-face kernel, 13 pixels of the final raster carrying the nerve's own code,
with Q303's nerve emphasis both off and on.

**They are not his imaging, and the page says so on every one of them.** These are Z-Anatomy meshes (and, for
18 and 12 of them, Q259 rule-built tubes) that had already been fitted to that subject's own skeleton on the
Combined page in Q195, registered onto the Imaging page by the documented bone-point method: identity plus a
thin-plate-spline correction field fitted to closest-point displacements on the bones the two pages share, with
a bone-surface residual of median 0.79 / p95 3.03 mm (Male) and 0.86 / 3.54 mm (Female). Each card carries the
`Method` row and the `±N mm` error band that Q300 made both templates render, a badge that opens
**"NOT SEGMENTED FROM THIS SUBJECT'S OWN IMAGING"**, and the source page's own badge quoted verbatim so the
original fit's error is still on the card. The source line reads "Filled from Z-Anatomy (reference model),
fitted to this body — not measured here". Nothing this round adds can print "Measured on this body", and the
Q297 provenance audit after the change still reports 0 such cards and 0 structures in the unaccounted class.

**The nerve emphasis control now says less, because there is less to say.** Q303's on-screen list of
conventional major nerves a page does not carry is computed from the page's own structures, so it shrank by
itself from 15 names to 10 on Imaging · Male. One matching bug came out with it and is fixed: a pattern ending
in a word boundary (`/\btibial\b/`) could never match an id like `tibial_n`, because "_" is a word character,
so the screen claimed the page carried no tibial and no sural nerve while it carried both.

**And a calibre you can check against a real measurement.** The sciatic nerve's card on all six pages now
carries a comparison against **SPARC dataset 692** (DOI `10.26275/1jdc-qiiv`, CC BY 4.0, an embalmed 41-year-old
male cadaver's own sciatic nerves at 11.4 µm), at that dataset's own bone-referenced levels. Calibre only, never
shape — the samples were excised and laid straight, so there is no in-body trajectory in them. Our nerve is
within about a quarter of the measured diameter in the mid and distal thigh and 1.4–2.3× too thick proximally.
**No geometry was changed**: the specimen is fixed, stained and excised, so it is a lower bound on a living
nerve, and it is one subject; the card says that, and says that the discrepancy is reported rather than
sculpted away.

## Q305 — moving the boxes on the screen where you want them

Owner (translated from Hebrew): *"let the various boxes on the screen be moved around."*

**Every box that floats over the model carries a small handle** — six dots, at one corner. Drag the handle and
the box goes where you put it; it is still there the next time you open that page in that browser. The box's
**body** is never a drag, and that is deliberate: the model is dragged to turn it, a pinch zooms any picture and
two fingers pan it (Q290), the ultrasound probe is dragged over the skin (Q294), and a long press on a list row
picks a range (Q294/Q298). A box that moved when its body was dragged would take one of those away. The market
has one documented precedent for a movable panel — 3D Slicer's module panel, undocked by dragging its *panel
chrome*, i.e. its title bar — and the title bars of these boxes are full of buttons, so the handle is its own
target instead. The handle is drawn 26 px on a desktop and 34 px where the pointer is coarse, with its touch
area padded out to 44 px **inwards only**, so it can never reach past its own box onto the model.

**What is movable:** the control bar (its open group travels with it), the "what is hidden" bar, the information
drawer, the cut / cross-section panel, the structure card, the side panel, the top row of buttons, the
measurement bar, the part-slices panel, the structure-expansion strip, and the labels panel and legend. A box
that is not on the page you are looking at is simply never given a handle.

**What is not, and why:** the zoom chip reports the zoom *of the picture it sits on*, so where it is is what it
means; a four-pane label names the quadrant it is in; the imaging and ultrasound views are **panes** whose
rectangle the page's own layout computes (Model only / Split / Compare), not boxes; and on the Imaging pages the
structure list and the structure card are **columns of the page's grid** — moving one would leave an empty strip
behind it and cover the model it had just made room for. Those two already collapse, and the layout already
cycles.

**On a phone the boxes dock instead of floating, and that was measured rather than chosen.** At 390×844 the
control bar has **−8 px** of horizontal freedom and the side panel **−24 px**: dragging them sideways is not a
feature. So an axis with less than one thumb (48 px) of travel is given a few **slots** instead of free drag — a
wide box gets three bands (top / middle / bottom), a small one the four corners — and a drop snaps to the
nearest one.

**It cannot take a control away from you.** `document.elementFromPoint` at the centre of each control that must
stay reachable — Undo, Redo, both resets, the circled i, Show everything, the control bar's group buttons and
the open group's own controls — runs after every drop. A drop that would cover one of them is **refused**: the
box goes back where it was and one line says which control it was. Those are the controls two earlier rounds
really did lose to an overlap, which is why they are watched by name.

**Putting it back.** **Restore layout** returns every box to where it started: one tap, one Undo step, and
**Reset model** does it too, because the layout is part of what the page loaded in. It is in the **View** group
of the control bar and, because that group's sheet scrolls, also in the circled **i**. On a keyboard the arrow
keys move the box whose handle has focus and **Home** puts that one box back.

**Accessibility, stated plainly.** WCAG 2.2 **SC 2.5.7 "Dragging Movements"** asks that anything done by
dragging have another way to do it without dragging. Three are provided — the arrow keys on the focused handle,
**Home** on that one box, and the one-tap **Restore layout** — and WCAG evaluates keyboard and pointer
independently, so the keyboard path stands on its own. What is *not* provided is a pointer-only "tap the handle,
then tap the destination", so **full coverage of that SC is not claimed**; it is written up as an owner decision
in `docs/OPEN_ITEMS_FOR_OWNER.md` rather than asserted here. The handle's hit area is 44 px (SC 2.5.8 asks 24 px
as the minimum; 44 px is the project's own rule), with the drawn graphic deliberately smaller.

**One inherited defect fixed on the way.** In the control bar's **View** group, the Z pages' bottom pill row
(`#foot`) was adopted into the group's sheet but stayed pinned to the bottom of the screen, painting over every
row listed below it — including **Restore layout** itself. The cause was CSS specificity, not layout: an id
(`#foot{position:fixed}`) outranks the two classes the group styles its adopted rows with. One declaration
scoped to the sheet fixes it, and the pill row in its own place at the bottom of the screen is untouched. It only
ever affected the Base and Combined pages; the Imaging pages have no such row.
