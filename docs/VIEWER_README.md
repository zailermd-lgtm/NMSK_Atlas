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
