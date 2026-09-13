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
| `ct_vhm_armm`, `ct_vhm_delt`, `ct_vhm_cuff`, `ct_vhm_pmr`, `ct_vhm_es`, `ct_vhm_abw` | male | cryosections (+ CT labels as anchors) | **rule-based**: textbook position rules applied to the muscle mass; boundaries are rules, not traced fascia |
| `ct_vhm_foot` | male | frozen CT feet block | left metatarsals and toe phalanges by planes along the foot axis; used because the DU release files ~22 cm3 of his left metatarsals under 'phalanges' (16.4 / 35.3 cm3 vs his CT 44.9 / 7.2 and the DU right 38.8 / 6.8) |
| `ct_vhm_skin` | male | cryosections | tissue silhouette |
| `ct_s1159`, `ct_s1159_abd` | a third body (TotalSegmentator case s1159, CC BY 4.0) | clinical CT | TotalSegmentator; fills only what the male lacks (vessels, quadratus lumborum) |
| `ct_vhf`, `ct_vhf_*` | female | fresh CT | TotalSegmentator free tasks |
| `ct_vhf_skin` | female | CT, plus the photographs for the arms the CT clips (above the pelvis) | body silhouette (HU > -300) united with the cryosection silhouette |
| `ct_vhf_delt` | female | colour cryosections registered to her CT (height corrected 2026-09-13, 0 +- 5 mm) | **rule-based**: the male's deltoid rule adapted to her -- muscle within 55 mm of the humerus, within 25 mm of the outer surface of the muscle compartment (not 40 mm of the skin: her fat is thicker), window 113 mm (his 130 scaled to her scapula), and below the humeral head only the lateral +-80 deg wedge within 40 mm; 226 / 282 cm3 (his rule value 232 / 180), the left still above the lean-section expectation |
| `ct_vhf_armm` | female | colour cryosections registered to her CT (height corrected 2026-09-13, 0 +- 5 mm) | **rule-based**: the male's compartment rules around her humerus (biceps over-inclusive, brachialis, triceps) |
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
