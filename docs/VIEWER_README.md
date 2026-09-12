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
| `ct_vhm_skin` | male | cryosections | tissue silhouette |
| `ct_s1159`, `ct_s1159_abd` | a third body (TotalSegmentator case s1159, CC BY 4.0) | clinical CT | TotalSegmentator; fills only what the male lacks (vessels, quadratus lumborum) |
| `ct_vhf`, `ct_vhf_*` | female | fresh CT | TotalSegmentator free tasks |
| `ct_vhf_skin` | female | CT | body silhouette (HU > -300) |
| `ct_vhf_delt` | female | colour cryosections registered to her CT (+-9 mm in height; her frozen block's pose differs from the fresh scan) | **rule-based**: the male's deltoid rule (superficial, within 55 mm of the proximal humerus, lateral to the scapula); deep boundary approximate |
| `ct_vhf_armm` | female | colour cryosections registered to her CT (+-9 mm in height) | **rule-based**: the male's compartment rules around her humerus (biceps over-inclusive, brachialis, triceps) |
| `ct_vhf_cuff` | female | colour cryosections registered to her CT (+-9 mm in height) | **rule-based**: the male's scapular-surface rules (supraspinatus, infraspinatus + teres minor, subscapularis) |
| `ct_vhf_es` | female | CT (model labels) | **rule-based**: erector spinae columns by distance from the vertebral midline (20 / 50 mm) |
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
