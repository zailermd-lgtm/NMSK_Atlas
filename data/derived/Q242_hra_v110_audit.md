# Q242 audit: HRA 3D Reference Object Library v1.10 (CDN, June 2026) against the six pages

Generated 2026-10-15. Machine-readable twin (URLs, sha256, sizes, licences, credits, every node name with closed/open flag): `data/derived/Q242_hra_manifest.json`.
GLBs (1.21 GB) stay in the session scratchpad, not in the repo. Scripts were throw-away (scratchpad `tools/`); the numbers below are reproducible from the manifest URLs.

## 1. What exists and where it lives

- The GitHub repo `hubmapconsortium/ccf-3d-reference-object-library` is STALE (HEAD = f1a3a63, the commit Q234 used). The current library is on the CDN:
  catalog `https://cdn.humanatlas.io/digital-objects/ref-organ/` (page source holds a JSON-LD list of the 88 objects), per object
  `.../ref-organ/<name>/latest/` (JSON-LD metadata in the page: version, date, licence, creators, citation, `distribution`), `.../<name>/<ver>/assets/<file>.glb`,
  `.../assets/crosswalk.csv`, `.../<ver>/graph.{json,jsonld,ttl,xml,nt,nq}`. HRA collection `.../collection/hra/latest/` = v2.5 (2026-08-10); objects dated 2026-06-08/09.
- Downloaded: 88 objects = 87 GLB + 88 crosswalk CSV (87 per-object + the master ASCT+B crosswalk) + 88 graph.jsonld = 1.24 GB (GLB 1.21 GB). All sha256 in the manifest.
- Priority set: United Female v1.10 (2026-06-09, 374.5 MB), United Male v1.10 (2026-06-08, 241.6 MB), skin F v1.5 / M v1.4, adipose F/M v1.0, pelvis F/M v1.3, intervertebral disk F/M v1.0,
  knee F/M L/R v1.3/v1.2, blood vasculature F/M v1.3, spinal cord F/M v1.1, sternum F + manubrium F v1.0 (no male object), ovary v1.3, fallopian tube v1.2, uterus v1.2, master crosswalk v1.10.
- Not in the library (HTTP 404 on guessed catalog names): vulva, clitoris, female urethra, vagina, ligaments, breast (whole), Bartholin gland, perineum, testis, penis, scrotum.
  Vagina and the 16 ligaments exist only as nodes of United Female.

## 2. Licence and credit (verified per object, both the graph licence and the object licence)

- 88/88 objects: `https://creativecommons.org/licenses/by/4.0/` (CC BY 4.0). No other licence, no flag. Funder of all: National Institutes of Health.
- Creators: Kristen Browne + Heidi Schlehlein (66 objects incl. both United sets, skin, pelvis, knee, blood vasculature, spinal cord, uterus, ovary, tube); Heidi Schlehlein alone (14: adipose,
  intervertebral disk, sternum, manubrium, mouth, omentum, epiploic appendage, mammary gland L/R); Li Yao (lymph nodes, with Browne/Schlehlein for the sets); Kristen Browne (heart-male);
  crosswalk: Ellen M. Quardokus, Heidi Schlehlein, Bruce W. Herr II, Katy Boerner.
- Caveats to state where used: brain F/M derive from the Allen human reference atlas (Ding et al. 2016; HRA says v1.3 re-licensed them CC BY 4.0); large intestine is not image-based; breast is sculpted;
  intervertebral disks are modelled (Browne) and fitted to the spine, not segmented.
- Cite (United Female): Browne, Kristen, and Heidi Schlehlein. 2026. 3D Reference Organ Set for Female, v1.10. https://doi.org/10.48539/HBM637.DWBM.744.
- Frame of every GLB: metres, y up, +x = subject LEFT (17/17 left/right object pairs agree), +z anterior; origin inside the pelvis. Our pages use mm and +X right (scripts/anatomy/q233/hra_register.py converts).

## 3. United Female v1.10 (3d-vh-f-united.glb, 1160 nodes, 956 meshes, 7.76 M triangles)

- 956 mesh nodes: 760 node_type `mesh` + 196 `surface` (author-flagged open surfaces). Computed topology: 433 closed (45 %), 523 open. 742 have an ontology ID, 214 do not.
- Extent (m): x -0.487..0.475, y -0.793..0.865, z -0.219..0.233 (skin y span 1.658 m, graph says 1657.8 mm).
- Systems (mesh nodes): nervous 362 (Allen brain 283, spinal cord 29, eyes 46, eye nerves 4), circulatory 124 (blood vasculature 110, heart 14), digestive 84, urinary 87, skeletal 81
  (vertebral column 73, pelvis 6, +2), respiratory 70, lower limb 52, reproductive 46, integumentary 20, lymphatic 14, muscular 16.
- Keyword scan of every node name and label (case-insensitive): vulva 0, labia 0, clitoris 0, mons 0, urethra 0 (female), bartholin 0, vestibular gland 0, perineum/perineal 0,
  ovarian artery 0, ovarian vein 0. Present: ovarian ligament L/R (2, FMA:55423/55424), vagina + cervicovaginal junction (2), breast/mammary 16 nodes, internal pudendal vein L/R,
  uterine artery/vein L/R, ureteral orifices. NO female urethra, NO external genitalia, NO ovarian vessels anywhere in the 88 objects.
- The female skin (266,696 triangles, closed) is a smoothed Visible Human envelope: the midline profile and the inter-thigh arch (checked by slicing) show no mons/labial relief.
  Adipose: three skin-offset patches (umbilicus, RUQ, LUQ), closed, "sectioned out of the skin where samples are commonly taken".

### Breast: real or sculpted?

`VH_F_mammary_gland_L/R` (fat_L/R, mammary_lobes, main_lactiferous_ducts, main_lactiferous_sinuses, areola, areolar_tubercles, nipple, suspensory_ligaments; 8 per side, only the suspensory
ligaments are closed): library text "The breast was sculpted from scratch to include relevant anatomy for placement of registration blocks" (Schlehlein; Krstic 1991, Gilroy 2008). Triangle counts and bounding
boxes equal the v1.3 files used in Q234 (sha256 differs by 96/156 bytes of glTF JSON). So: NOT donor data, NO newer or real breast in the library. Nothing to change.

### Present / absent / newer against our female pages (own_f = Imaging-based F, comb_f, base_f; build/q238 tables)

"Identical" = triangle count and bbox equal to the file already registered (0.01 mm). Name-matching alone finds only 78/956 HRA nodes on own_f, 257 on comb_f, 251 on base_f (lower bound:
HRA splits organs into sub-parts, our pages carry whole organs).

| HRA group (mesh nodes) | Verdict on our pages |
|---|---|
| vagina (1) + cervicovaginal junction | PRESENT (Q234), identical geometry, open surfaces |
| 16 ligaments (round, uterosacral, cardinal, broad, ovarian, suspensory, mesosalpinx, mesovarium) | PRESENT 15/16, identical; uterovesical pouch deliberately not used; 8/16 closed |
| uterus (10 parts: fundus, body, cervix, 2 os, ant/post wall, lower segment, cornua, ostium) | whole organ PRESENT, identical; parts NEW as sub-structures (only walls closed) |
| ovary L/R | PRESENT, identical (closed) |
| fallopian tube (4 segments per side: ampulla, isthmus, infundibulum, fimbria) | whole tube PRESENT, identical; segments NEW as sub-structures; all open |
| urinary bladder (dome, base, neck muscle, trigone; + 2 ureteral orifices) | whole bladder PRESENT, identical (our file = same 6 meshes); parts NEW |
| uterine artery L/R, uterine vein L/R | ABSENT on all pages, NEW (blood-vasculature-female v1.3), open tubes |
| internal iliac v, internal pudendal v, middle/inferior/superior rectal v, median sacral v, sup. rectal a | ABSENT on own_f (own_f has only common iliac a/v), NEW |
| breast (16) | PRESENT (sculpted), identical |
| subcutaneous abdominal adipose, 3 areas | ABSENT on own_f, NEW (2025-12 era object), closed |
| skin (1) | PRESENT as our own CT/cryosection skin; HRA skin is a different, smoothed surface |
| spinal cord segments C1..S4 (29, all open) | ABSENT as segments; NEW |
| intervertebral disks (24) + nucleus pulposus (24) | disks PRESENT on own_f from CT (23, C2-S1); nucleus pulposus NEW (47/48 closed); HRA names six lumbar vertebrae and disks L1..L6 (our open item Q185k2) |
| vertebral column (73), pelvis (6), sternum, manubrium | bones PRESENT on all pages (own CT / Z); pelvis identical to VH_F_Pelvis; sternum/manubrium only as separate female objects |
| Allen brain (283), eyes (46), eye muscles (12), mouth (21), larynx (7), trachea/bronchi (36) | own_f: brain/eye/mouth as single structures; comb_f has Z-Anatomy equivalents (65 of 283 brain nodes name-match) |
| liver segments (26), biliary tree (8), pancreas (5), small intestine (9), colon (10), spleen (5) | whole organs present; segment/sub-part level NEW on own_f |
| upper urinary tract (81: capsule, cortex, columns, 21 pyramids, 21 papillae, 27 calyces, 2 renal pelvis) | kidneys whole on all pages; internals NEW |
| heart (14), lungs (27), thymus (2), lymph node (7, Yao mouse-based Ce3D model) | whole organs present; sub-parts NEW; lymph node is a generic model |
| knee (F/M L/R, 20 nodes: femur, tibia, fibula, patella, meniscus, cartilage + 13 open landmark surfaces such as ACL/PCL entheses) | bones PRESENT; landmark surfaces NEW (open) |
| placenta set (8) | ABSENT, not relevant to a non-pregnant model |
| vulva, clitoris, female urethra, vestibular glands/bulbs, ovarian vessels, real breast | ABSENT FROM THE LIBRARY (our Q235 CVH clitoris/bulbs/Bartholin/urethra stay the only source) |

## 4. United Male v1.10 (1129 nodes, 918 meshes, 6.88 M triangles; 445 closed, 709 with ID, 209 without)

- Male-only nodes: vas deferens L/R, seminal vesicle, ejaculatory duct, prostatic utricle, seminal colliculus (verumontanum), prostate base/apex, peripheral/transition/central zone L/R,
  anterior fibromuscular stroma L/R, prostate ducts, prostatic urethra, "other urethra" (no label/ID, open), bladder neck/dome/base/trigone. No testis, epididymis, penis, scrotum, foreskin, spermatic cord.
- Gaps for the male pages: none of significance. Our pages already carry testis/epididymis/penis (Z-Anatomy). NEW: prostate zonal anatomy (peripheral, transition, central, AFMS; 6 of 8 closed),
  prostatic utricle, verumontanum, bladder trigone, SAT areas. Skin M 829,184 triangles, closed.

## 5. Left/right consistency (every paired node: name token L/R vs world x of the area centroid)

| Object | Paired nodes | Left at larger x | Mismatch |
|---|---|---|---|
| United Female | 321 | 179 | 142 = 141 Allen brain pairs + the round ligament pair |
| United Male | 297 | 153 | 144 = 141 Allen brain + vas deferens, renal arteries, thymus lobes |
| 17 single-organ L/R object pairs | 17 | 17 | none |

- Round ligament (F): `VH_F_left_round_ligament_of_uterus` at x -65 mm, right at +29 mm: the swap found in Q234 is STILL in v1.10 (we keep our Q234 fix).
- Male: `VH_M_vas_deferens_L/R` (-20/+16 mm), `VH_M_left/right_renal_artery` (-19/+38 mm, also in blood-vasculature-male), `VH_M_thymus_lobe_L/R` (-16/-3 mm, weak) swapped.
- Allen brain, both sexes: all 141 L/R pairs have the L-named structure on the subject's right (HRA says the structures were mirrored to make a whole brain); do not trust brain sidedness.
- Label vs node name: `VH_F_pulmonary_vein_R_inf` carries the label "left inferior pulmonary vein" and `_L_inf` "right inferior ..." (united-female and blood-vasculature-female);
  the geometry agrees with the node names, the crosswalk labels are swapped.
- Not defects: left hepatic branches, right ventricle, right coronary artery sit on the other side of the midline by anatomy.
- Other: 0 duplicate node names, 0 mirrored (negative-determinant) transforms, 0 empty meshes. Typos in names (`fibria`, `opthalmic`, `eigth`, `perichondular`, `transition_zone__of_prostate_L`),
  non-standard IDs `UBERON:8410025-27` (prostate zones), 214/209 mesh nodes without an ontology ID (segments, surfaces, areas).

## 6. ASCT+B -> 3D crosswalk (asct-b-3d-models-crosswalk.csv, v1.10, 2026-06-15, DOI 10.48539/HBM626.BRWN.943)

- 2295 node rows (1410 mesh, 464 surface, 419 organizational); columns anatomical_structure_of, source_spatial_entity, node_name, label, OntologyID, representation_of, node_type, glb file of single organs,
  Ref/1, Ref/1/ID. Ontology IDs: 1730 rows (75.4 %): UBERON 1109, FMA 621; 565 rows have none. The ASCT+B reference columns (Ref/1, Ref/1/ID) are EMPTY in all rows: it maps nodes to ontology IDs, not to ASCT+B tables.
- Each object also ships its own `crosswalk.csv` (node_name, OntologyID, label; United Female 875 rows = only the 875 nodes of 1160 that have a label/ID, 874 with an ID; the same IDs are embedded in the GLB `extras.ontologyid`).
- Coverage of OUR legend (distinct base names after dropping side and brackets, exact normalised match to a crosswalk label or node name): Imaging-based F 54/332 = 16.3 %, Imaging-based M 40/286 = 14.0 %,
  Combined/Base F and M 7.7-8.4 % (about 140 of ~1670 names). A 0.8-Jaccard fuzzy pass adds only 6 (Z pages). The ceiling is set by the library, not by naming: the unmatched are muscles, nerves, arteries,
  limb and skull bones, CVH composites, which HRA does not model. The crosswalk can therefore supply UBERON/FMA IDs for a minority of the legend (organs, ligaments, breast parts, knee bones, eye muscles, sacrum);
  an alias table (disc/disk, side words, "intervertebral disc C2-C3" -> disk of axis) is needed to go beyond the 16 %.

## 7. Recommendation for the next integration step (Q243)

1. Do NOT re-register geometry we already hold (pelvis, uterus, ovaries, tubes, bladder, vagina, ligaments, breast are identical); only refresh the NOTICE to the v1.10 DOIs.
2. Register on own_f and comb_f with the Q233 pelvis transform: uterine artery/vein L/R, internal iliac and internal pudendal veins L/R, middle/inferior/superior rectal veins, median sacral vein, superior rectal artery
   (from `blood-vasculature-female` v1.3; open tubes, so no volumes) and the uterus/tube/bladder sub-part nodes as selectable children of the existing organs (no new geometry placement).
3. Then own_f spine: nucleus pulposus (24) and spinal cord segments (29) on the own CT spine (HRA numbers six lumbar vertebrae L1..L6: adopt it with the Q185k2 decision).
4. Keep Q235 (CVH) for clitoris, vestibular bulbs, Bartholin glands, urethra; vulva (labia, mons, vulvar skin) and ovarian vessels need a different source (not in HRA 3D library v1.10).
5. Use the crosswalk to add ontology IDs only for the matched names (about 54 on own_f) via an alias table; swap the round-ligament and pulmonary-vein labels if the HRA nodes are ever imported by name.
