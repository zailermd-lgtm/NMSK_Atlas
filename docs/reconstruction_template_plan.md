# Reconstruction template and accuracy plan (2026-10-14)

Purpose: (a) rank ways to make the six published models more accurate; (b) a reusable plan to turn a NEW
imaging study (CT / MRI / cryosection) into an atlas model accurately, cheaply and fast; (c) what the two
supplied papers add; (d) open risks. Written from PROJECT_STATE.md (Q1-Q234), `data/derived/Q198/Q223/Q224/Q225/Q233/Q234`
audits, the two PDFs, and a short web check (2026-10-14). Time / cost / threshold numbers marked **[est]** are
my estimates, not measurements. Nothing here has been implemented or published.

Models: Imaging-based M/F ("own", from the Visible Human CT + cryosections), Combined M/F (Z-Anatomy fitted onto
the VH skeletons, `scripts/zanatomy`), Base M/F (Z-Anatomy unfitted). Base F is the male-derived body (Q233).

## 0. What the history says (cost drivers)

- Own models are built **mesh-first, one region at a time**: 33 `mappings/subjects/ct_vhf_*` and 29 `ct_vhm_*`
  per-region volume mappings, merged by `bundle_to_subjects.py`. Every region join became a later Q-task
  (flat cuts, detached pieces, overlaps). Q223 flat-cut findings (major+moderate) own male 89 / female 77; muscle-in-muscle (moderate) 16 / 38.
- The seams are inherited from the data: the Visible Human is four cadaver blocks, 0.33 mm female / 1 mm male, arms
  clipped by the 480 mm CT field of view (VKH paper, Fig. 1 and Sec. I names exactly these defects). Q198 root causes:
  `ct_block_seam` 103 (M) / 127 (F), `bone_block_truncation` 9 / 11, `registration_mismatch` 61 / 104.
- Per-structure patches regress neighbours: Q217 raised own-male wrist findings 7 -> 11; Q224 skipped 69 muscles
  that failed guards; Q225 his wrist ligaments rejected 30-37 of 55 structures per round by containment guards.
- Stopped with nothing shipped after repeated attempts: Q166 (forearm v4 from photographed septa), Q179 / Q179a /
  Q181 / Q181b (her thigh photo-tracking), Q62 step 9 (28 HELD per body). Photo-based muscle-boundary tracking is
  research-grade here; do not budget it as a routine stage.
- Blocked / lost time: sandbox egress blocks (kaggle, nature, KISTI host, DBCLS); `trimesh.voxelized` OOM at 15 GB
  (Q105c, de-scoped); TotalSegmentator 0.75 mm tasks OOM-killed at ~12.4 GB until chunked (peak ~5.5 GB); a 2 h silent
  stall; one container reset wiped build/ (re-stream ~14 GB cryosections). Audits: Q223 ~1.5 h on 3 cores (~2.5 GB each).
- Already in repo (so NOT recommended below): TotalSegmentator `total` + open tasks ingest (`merge_totalsegmentator_masks.py`,
  chunked), marching cubes + `closed_surface` + quadric decimation, IDC DICOM / cryosection streaming, bone-frame
  registration (ICP / similarity, 1.2-1.9 mm medians), bone-anchored displacement fields (Q199/Q206), Q198/Q204/Q223
  junction audits, Q233 sex audit, source badges / Source facet / ship diffs, regen scripts (`regen_*`), headless page checks.
- Not in repo (grep of `requirements.txt` and `scripts/`): nnU-Net training, MONAI Label, ITK/SimpleITK/ANTs/elastix
  deformable registration, any statistical shape model / PCA, a generic Dice / Hausdorff module (Dice only inside rib scripts).

## A. Accuracy improvements for the six models, ranked by expected gain / effort

Gain: H = removes a whole defect class on several models. Effort: S <= 1 day, M 2-5 days, L > 1 week **[est]**.

| # | Improvement | Targets (measured defect) | Models | Gain | Effort |
|---|---|---|---|---|---|
| 1 | Re-run the elbow verdict honestly: make the audit pose-aware (skin radius step and carry / twist angles measured along the bone axis, not on world planes), then apply the Q225 joint-congruency fit to the two untouched right elbows of the fits | All four elbows read DEFECT in Q223 / Q225 although Q211 / Q223 show the skin-step majors are a flexed-pose artefact; real left: his 1/7/9, hers 1/3/15; right elbows untouched | Own M/F, Combined M/F | M (restores a trustworthy flag) | S |
| 2 | One joint overlap resolution on a **label volume** instead of per-muscle patches: voxelize all muscles at 1 mm in z-chunks (not `trimesh.voxelized`), assign each contested voxel by signed-distance competition from non-overlapping cores, re-mesh closed; leave tendons / ligaments / vessels out | muscle_in_muscle: own 16 / 38, fits 28 / 34, bases 22 (mod.); her left forearm overlap 39 % (Q225); 69 muscles failed Q224 guards; Q215-Q217 per-muscle tiling | All six | H | M |
| 3 | Close the CT-block seams: shape-based (signed-distance) interpolation of muscle cross-sections across the missing block between the two measured stumps, Z-badged completion only where the stumps do not reach (Q224 "dome" is explicitly not the true continuation) | flat caps: own M 258 / F 277 (Q212), Q224 left 18 + 9; 166 flat-cut findings (both own models); `ct_block_seam` 103 / 127 | Own M/F | H | M-L |
| 4 | Rebuild carpal / wrist ligaments as **bone-footprint-anchored** surfaces generated between the person's own re-segmented carpals (`generate_ligament_connectors.py` family), instead of warping Z meshes into guards that reject them | his carpal ligaments 40-100 % of vertices inside his carpal bones; wrist tears still ~30 % (Q225); 30-37 of 55 wrist structures rejected per round | Own M, Combined M | M | S-M |
| 5 | Female pelvis, quick path: put HER OWN CT hip bones + sacrum + coccyx into Combined F (her bones give subpubic 87.3 deg) and carry the Z pelvic soft tissue with the existing bone-anchored field (Q206); keep the Q233 audit as the gate | Combined F subpubic 62.7 deg (male range; cut-off 78.6, female 87.4 +- 6.5, PMID 32274246); Base F 57.2 (male skeleton) | Combined F | H (sex-correctness is an owner requirement) | M |
| 6 | Female pelvis, real base: sex-specific pelvic shape model from the TotalSegmentator dataset (CC BY 4.0, ~1.2 k CT with sex in meta.csv; hip-bone labels from `total`): landmark / surface correspondences by ALPACA, GPA + PCA per sex (group by folders, GPA has no sex filter), female mean pelvis replaces Base F pelvis | Base F "is NOT a female body" (Q233); no open female skeleton exists (Q196) | Base F | H | L |
| 7 | Breast: measure HER fat-pad envelope (skin to pectoral fascia, fat HU) from her CT / cryosections; scale the HRA gland / ducts into it; badge "reference structure in measured envelope". Base F stays skipped (Z chest leaves 8 % of the volume; rule `MIN_VOLUME_RATIO = 0.25`) | HRA breast is sculpted from drawings, not donor data (Q234); her trunk skin 20-50 mm off the Z-fitted skin (Q186) | Imaging F, Combined F | M | S-M |
| 8 | His thumb ray + thumb muscles and her left-wrist re-seat from the Q205 / Q212 evidence | Q223 top-15 #2 and #5: thumb ray absent on both hands; her left wrist bones 9.0 mm apart | Own M/F | M | M |
| 9 | Fit the Z bodies as one articulated chain with congruency constraints from the first pass (not bone by bone then patched at the elbow, wrist, shoulder) | Q225: per-bone fits gave 9.1 / 6.3 / 6.2 mm penetration; ulna 20.7 mm too long | Combined M/F | M | M |
| 10 | Spike (<= 2 days, benchmark before adopting): diffeomorphic registration (ANTs SyN or elastix, both Apache-2.0) on bone + organ signed-distance maps as an alternative to the IDW bone-anchored field; accept only if Jacobian > 0.2 everywhere and error on the Q191 / Q192 left hand (photographs) beats the current field | shoulder vessel frame offsets 29-34 mm; fit vessels / nerves registration_mismatch 53-80 | Combined M/F | M (uncertain) | M |
| 11 | Freeze the Q198 / Q223 audit + Q233 sex audit as a numeric release gate (section B, G6-G8) so a fix that worsens a neighbour is rejected automatically | Q217 side effect; Q209 -> Q223 only partly improved | All six | M | S |
| 12 | Independent validation body: run the new pipeline (section B) on a third body (VKH, or one TotalSegmentator CT + atlas) and report errors vs a few hand-labelled slices; today no model has any measured accuracy against ground truth beyond bone-registration residuals | Atlas claims rest on guards and plausibility, not error figures | All | H (credibility) | M |

Not fixable honestly (keep as stated in Q233 / Q234): vagina / vulva / clitoris / vestibular glands / ovarian vessels (no open
mesh source; cryosections show one dark mass at 1 mm), Z-derived skeletons of Base F, vessel bridges beyond measured stumps.

## B. Template: turning a NEW imaging study into an atlas model

Principle changes vs today: (1) **label volume first, mesh last**: one multi-label NIfTI per body is the single source of
truth (non-overlapping by construction); meshes are derived in one pass; (2) every structure is classed
measured / reference-same-donor / transferred / template-fitted / rule-based from day one (the existing Source facet);
(3) gates are numeric and automated; (4) humans correct only what the gates flag, ranked by severity x volume.

| Stage | Work | Tools (licence) | Time **[est]** | Compute **[est]** | Gate |
|---|---|---|---|---|---|
| S0 Data + licence | identify study, obtain terms in writing, check de-identification, redistribution of derived meshes | owner | 1-14 days elapsed | - | G0 |
| S1 Ingest + QC | DICOM -> NIfTI, orientation (RAS), spacing, HU / intensity sanity, field-of-view and block map, cryosection colour-patch / fiducial check, stitch blocks once | pydicom, nibabel, numpy (permissive; existing scripts) | 0.5-1 day | 1 CPU, 8 GB; streaming for > 100 GB cryo sets | G1 |
| S2 Auto-segmentation | CT: TotalSegmentator `total` + open tasks (headneck / head / abdominal muscles, craniofacial, vertebrae); MRI: `total_mr`; compare with MRSegmentator on a pilot; chunk any 0.75 mm task | TotalSegmentator (Apache-2.0 code; open tasks Apache-2.0); MRSegmentator (code Apache per PyPI, **weights licence unverified**) | CPU 15-40 min per 1.5 mm body; GPU 2-5 min; 0.5 day incl. setup | CPU 4 cores + 16 GB (chunked, peak ~5.5 GB measured); optional GPU 12-16 GB VRAM, rented ~$0.5-1.5 / h | G2 |
| S3 Interactive correction | rank structures by gate severity x volume; fix with Slicer Segment Editor (Grow from seeds, Fill between slices, Joint smoothing); optional MONAI Label (DeepEdit) loop that fine-tunes on corrected slices; **budget**: label every 10th slice (1-2 mm CT) of each flagged structure + interpolate; stop at gate pass or the cap | 3D Slicer (BSD-style + research-use clause); MONAI Label (Apache-2.0 code; per-model weights: check each); nnU-Net (Apache-2.0 code; weights licence not stated) | 8-40 expert-hours per body (cap 40) **[est]**; hand-seg precedent: VKH 11 organs x 8590 images took 1 year in Photoshop | 1 workstation; GPU optional | G2 re-run |
| S4 Template registration (what imaging cannot show: ligaments, fascia, small nerves / vessels, retinacula, sex-specific organs) | fit reference parts (Z-Anatomy CC BY-SA 4.0; HRA 3D library CC BY 4.0) via bone / organ landmarks; existing bone-anchored field first, SyN / ALPACA only if the spike (A10) passes; anchor ligaments to the person's bone footprints; minimum volume-ratio rule 0.25 | existing code; ANTs (Apache-2.0), elastix >= 4.8 (Apache-2.0), SimpleITK (Apache-2.0), SlicerMorph ALPACA / GPA (BSD-2-Clause) | 1-3 days | CPU 3-6 h | G5 |
| S5 Mesh generation | marching cubes per label on a sub-voxel-smoothed volume, half-voxel normal shift (existing `closed_surface`), joint multi-label smoothing, quadric decimation, closed + manifold check | scikit-image, trimesh, fast-simplification (permissive, already in requirements.txt); VTK windowed-sinc if shrinkage is an issue | 0.5 day | 30-90 min CPU; use voxel-first, never `trimesh.voxelized` on full bodies | G3 |
| S6 Validation | full junction + overlap + sex audit, held-out-slice Dice / HD95, ship diff | existing Q198 / Q223 / Q233 code + a small Dice / HD module (numpy / scipy, to write) | 0.5 day + automated 1.5 h on 3 cores | 2.5 GB per job | G1-G8 |
| S7 Badging / provenance | per-structure source class, parent label, tool + weights version + licence, guard numbers on the card | existing badge + `third_party/*/NOTICE.md` pattern | automated | - | G7 |
| S8 Build / publish | regen pages from template, headless page check, hub text, publish (owner decision) | existing `regen_*.sh`, Chromium swiftshader check | 10-30 min + review | 5 min per Q233-type rebuild measured | G8 |

Whole study **[est]**: 2-4 weeks elapsed, 40-80 person-hours, < $50 cloud compute when a GPU is rented for S2 / S3 only. This
project's own history (234 queue items for six models) is the counter-estimate for what happens without the gates and the
label-first rule; treat the table as a target, not a promise.

### Validation gates (thresholds are my proposals; items marked "precedent" are numbers already achieved or published here)

| Gate | Pass criterion |
|---|---|
| G0 Licence | written terms read; derived-mesh redistribution allowed; NC / unknown items listed and excluded from the public build |
| G1 Ingest / registration | every voxel grid RAS, spacing recorded; bone-to-bone registration CT<->cryo or block<->block residual median <= 2 mm, p90 <= 5 mm (precedent: HRA onto her hip bones median 1.24, p90 3.5; Q168 fits median 1.9); no unlabelled block gap > 1 slice; arms inside the field of view or flagged |
| G2 Segmentation | on >= 20 hand-labelled slices per structure class: Dice >= 0.90 bones / large organs, >= 0.80 muscles, >= 0.70 small structures (reported, not gated); HD95 <= 2 mm bones, <= 3 mm soft; unreviewed structures are badged "automatic, unreviewed" |
| G3 Mesh | 0 open edges for solids; 1 component unless anatomically paired (main_frac >= 0.99, Q105c reasoning); volume change after smoothing <= 2 % (precedent: closed_surface sphere test within 2 %); surface-to-label p95 <= 0.75 voxel; decimation deviation <= 0.25 mm |
| G4 Anatomical plausibility | sex-diagnostic skeletal measures within the donor's sex range (subpubic angle vs 78.6 deg cut-off; Q233 six measures 6/6); organ volumes inside published range or flagged; no male-only structure on a female model and vice versa |
| G5 Template-fitted parts | landmark-bone residual median <= 2 mm, p90 <= 5 mm; volume ratio fitted / source >= 0.25; inside skin; 0.5 mm exact bone penetration <= 1 mm (precedent: Q225 <= 0.7 mm); Jacobian > 0.2 if a deformable fit is used; always badged reference / transferred |
| G6 Overlap / continuity (audit) | muscle-pair overlap <= 2 % of the smaller muscle; 0 flat caps > 100 mm2 (precedent: Q224 61 -> 0); muscle ends <= 5 mm from their bone footprint; vessels / nerves with no gap inside the field of view; skin sealed |
| G7 Regression | Q198 / Q223 major count and wrist / elbow counts not higher than the last published build (Q217 side-effect rule); ship diff has 0 unlisted entries |
| G8 Provenance / UI | every structure has source class, tool + weights licence, guard numbers; headless page check 0 errors, no horizontal scroll |

Compute envelope that this container really has: 15 GB RAM, 3-4 CPU cores, no GPU, outbound HTTPS through an allowlist
(pypi, GitHub releases, IDC reachable; kaggle, nature, KISTI host not). Whole-body 0.2 mm cryosections are 146 GB for VKH
(197.5 GB with segmentation): stream crops, do not stage.

### Licences (verified 2026-10-14 by README / repo page via WebFetch unless marked)

| Item | Licence | Flag |
|---|---|---|
| TotalSegmentator code; tasks `total` (117 classes), `total_mr` (50), `body`, `head_muscles`, `headneck_muscles`, `headneck_bones_vessels`, `abdominal_muscles`, `craniofacial_structures`, `vertebrae_mr`, `breasts`, `trunk_cavities` | Apache-2.0 ("openly available for any usage") | ok; some open tasks are marked "not trained on the full dataset" |
| TotalSegmentator `appendicular_bones(_mr)`, `tissue_types(_mr)`, `tissue_4_types`, `thigh_shoulder_muscles(_mr)`, `face(_mr)`, `brain_structures`, `heartchambers_highres`, `coronary_arteries`, `aortic_sinuses` | free for non-commercial; commercial licence from the author | **NC: not for a public / commercial build without a licence** (already recorded in PROJECT_STATE line 3323) |
| TotalSegmentator `brain_aneurysm` | CC BY-NC 4.0, no commercial licence | **NC, excluded** |
| TotalSegmentator training dataset (CT cases, Zenodo 10047292) | CC BY 4.0 (per PROJECT_STATE) | ok, cite |
| nnU-Net code | Apache-2.0 | pretrained-weight licences not stated on the repo page: check each download; weights trained by us on CC BY data are ours, on NC data inherit the restriction |
| MONAI Label code | Apache-2.0 | model-zoo / SAM weights per model: check each |
| MRSegmentator | code Apache-2.0 (PyPI badge only; secondary source); article CC BY 4.0 | **weights licence not found: unverified, treat as NC until read** |
| 3D Slicer | "BSD-style" Slicer Contribution and Software License (research use, "clinical applications neither recommended nor advised", no endorsement use of names, preserve notices) | ok for building the atlas; keep the not-for-clinical wording we already have |
| SlicerMorph (GPA, PCA, ALPACA / MALPACA, PseudoLMGenerator) | BSD-2-Clause | ok |
| ANTs | Apache-2.0 (repo page) | ok |
| elastix >= 4.8, SimpleITK (SimpleElastix) | Apache-2.0 (search result; older elastix BSD) | ok |
| scikit-image, trimesh, nibabel, numpy, shapely, VTK, pydicom | permissive (BSD / MIT) from my memory, not re-verified this session | verify at release |
| Blender, MeshLab | GPL (tools only; exported meshes are not encumbered by the tool) from memory | ok as tools, do not embed code |
| BodyParts3D (Safir Fig. 1 shows "CC BY-SA 2.1 Japan"), Z-Anatomy | CC BY-SA | derivatives stay CC BY-SA (existing repo policy) |
| HuBMAP HRA 3D Reference Object Library | CC BY 4.0 (repo) | ok, notice in `third_party/hra_vh_f/` |
| Visible Human (NLM) | NLM licence agreement (search result: recipients may distribute applications containing the data, no royalties) | repo already relies on IDC-hosted copies |
| **Visible Korean Human (KISTI)** | **not verified**: paper says "distributed worldwide free of charge"; a ~2017 report says obtainable without charge or registration; the KISTI site was unreachable from the sandbox and no current terms page was found | **owner must request the data and read the agreement; do not assume rights to redistribute derived meshes or the colour images** |

## C. What each source paper contributes

**Park JS, Chung MS et al., "Visible Korean Human", IEEE Trans Med Imaging 24(3):352-360, 2005** (read in full, 9 pp).
- Body: one Korean male, 33 y, 1640 mm, 55 kg, died of leukaemia; chosen from dozens of cadavers by anatomists and
  radiologists; **nothing perfused** (formalin makes tissue white, red gelatin stains muscle red: both avoided).
- Acquisition: whole body MR (GE Signa 1.5 T, T1, TR 800 / TE 8 ms, 1.0 mm slices, 0 gap, 1718 images, FOV 480 mm, 512 x 512
  cropped to 505 x 276, ~1.0 mm pixels) and CT (GE HighSpeed Advantage, 120 kV, 280 mAs, 1.0 mm, 1718 images, standard
  algorithm), head-to-knee and knee-to-toe series aligned after. Body frozen at -70 C in an immobilising box, then embedded in blue
  gelatin (30 g gelatin + 0.5 g methylene blue per 1 l) with four polyacetylene alignment rods; blue gel poured into air cavities
  > 1 mm to avoid artefacts; sectioned **feet to head** so section orientation equals the MR / CT without flipping.
- Sectioning: purpose-built 15 t cryomacrotome, moving error +- 1 um (estimate), 360 mm blade with 20 teeth at 628 rpm, 20.8 mm / s;
  0.2 mm intervals, **8590 colour images, 3040 x 2008, 24 bit, 0.2 mm pixel** (146.4 GB; total with MR / CT / labels 197.5 GB); Kodak DSC 560,
  50 mm macro, polarising filter, two strobes at 45 deg, F10 1/250 s, grey + colour patch in every frame; 5 months of sectioning.
- Labels: **semi-automatic**, Photoshop 7 magnetic-lasso, 11 organs (skin, bones, liver, lungs, kidneys, bladder, heart, brain; lumen of
  digestive tract, respiratory tract, arteries) on all 8590 images, **1 year** of work; 8-bit label images published free of charge.
- Verification: smoothness of alignment rods and contours in re-sliced coronal / sagittal planes, and 3D reconstructions
  examined against anatomical knowledge. **There are no numeric segmentation or registration error figures** in the paper.
- Why accurate / fast: no missing blocks, 0.2 mm isotropic sections, neutral posture (arms at the sides, pillow under the head, so
  the head is not extended), field of view wide enough for the arms, fiducial rods, constant lighting with colour patch,
  frozen hard (dry ice, cold season) to keep faces clean, publish labels so others skip segmentation.
- Directly applicable: (i) the data itself is the ideal third body: **no block seams, no arm clipping, one frame** (our `ct_block_seam` +
  `bone_block_truncation` classes are VHP properties) and MR + CT at 1 mm co-registered; (ii) the acquisition checklist
  (posture, fiducials, colour patch, no perfusion, feet-to-head) becomes gate G1 for any study we can influence; (iii) the semi-automatic
  principle (expert draws, tool fills) matches S3; (iv) its 11 labels give a free ground truth to test S2 / S4 on an independent body.
  Caveats: it has no muscles, nerves or ligaments, labels cover 11 organs only, and the female data are described as "ongoing"
  (a 2020 report found by search says a female whole-body segmentation exists; not verified).

**Safir AH, Bird MM, Orczykowski ME, "Development of effective 3D digital models for first-time learners of musculoskeletal
anatomy", Anat Sci Educ 19:1060-1071, 2026** (read in full; CC BY).
- Method: MRI-derived BodyParts3D 4.3i OBJ files (CC BY-SA 2.1 JP) imported into Blender at scale 0.010, sorted into skin / bone /
  muscle / cartilage collections, one material and label per muscle, 21 hip and knee muscles kept; superficial muscles fly away by
  keyframed scale / position so deep layers show; skin opacity 10 %; FBX -> Sketchfab (free, browser, private link). No cost,
  no modelling skill needed.
- Evidence: n = 81 (39 3D vs 42 textbook), 21-question pre / post test after 10 min: +9.26 points (+44.08 %) vs +5.05 (+24.04 %),
  t = 4.924, p < 0.0001; 100 % vs 45 % said it helped visualise spatial relations; baselines equal (p = 0.58).
- Limits (theirs): single 10-minute session, one cohort, no long-term retention, cannot isolate which feature helped.
- **Contributes nothing on geometric accuracy** (no error figures; it consumes BP3D as given). Applicable only as (i) a design
  confirmation for features we already have (per-tissue colour, layer fade / ghost, Cut mode, search); (ii) an optional
  learner-evidence protocol (pre / post test, 10 min) if the owner wants to show educational value; (iii) a licence reminder:
  BP3D derivatives must stay CC BY-SA.

**Slicer discourse thread "Fcsv landmark verileri ile grup bazli PCA" (44949)**: the page itself was unreachable from the sandbox
(DNS error); only search snippets were read. Related threads state: GPA / PCA take .fcsv or markups JSON with identical
landmark counts and order; the GPA module cannot subset by group, so put each group (e.g. female / male) in its own
folder; covariate files only colour the plot; MergeMarkups combines fixed and semilandmark files; use current Slicer +
SlicerMorph (5.8.1 cited). Use: improvement A6 (per-sex pelvic shape model) and stage S4 (landmark correspondence). PCA needs tens
of specimens: with our two bodies it is meaningless, so shape models must come from many CT cases.

## D. Open risks

1. **Licences / terms**: VKH terms unknown; NC TotalSegmentator tasks and MRSegmentator weights unverified; BP3D / Z-Anatomy CC BY-SA
   propagation; owner must decide what is public.
2. **No ground truth**: today's accuracy claims are residuals and guard checks. A fast pipeline that is wrong faster is worse; hence A12 and G2.
3. **Domain shift**: TotalSegmentator / nnU-Net were trained on living-patient CT / MRI; cadaver CT (frozen, unperfused) and
   cryosection photographs are out of distribution. There is no open RGB cryosection model I know of; expect to label cryosections by hand
   or train one (unvalidated).
4. **Cryosection photo segmentation has failed repeatedly here** (Q166, Q179, Q181): keep it a research item, not a pipeline stage.
5. **Thresholds are mine**; audit measures have artefacts (Q204 2 mm solid vs 0.5 mm exact leaves 2-9 of 22-44 findings; flexed-pose skin
   step). Calibrate gates on the six current models before enforcing; avoid tuning to the audit.
6. **Deformable registration may fold or hide error** (SyN on label maps); every fitted structure must keep a reference badge and Jacobian check.
7. **Single bodies, cadaveric posture**: sex-specific claims (Q angle, breast volume, soft-tissue shape of a supine donor) rest on n = 2;
   postmenopausal 59-year-old female donor.
8. **Compute**: 15 GB RAM caps full-resolution volumes; the voxel-first rewrite (A2, S5) must stay chunked; GPU only by rental.
9. **Estimates**: all time / cost figures in B are untested estimates; web checks were single standard searches, license text taken from
   README summaries (verify the LICENSE files before relying on them); Slicer thread not read in full.
10. **Scope creep**: A2 and A3 change published geometry on all six pages; ship them behind the G7 regression gate and the existing
    ship-diff discipline, one model family at a time.

## Owner decisions needed

(1) Obtain the VKH data and terms (KISTI) and decide whether the third body is worth it; (2) accept the label-volume-first rewrite
for new bodies (A2 / S5) or keep patching meshes; (3) female pelvis: quick path (own hip bones into Combined F, A5) and/or a
shape-model base (A6); (4) approve TotalSegmentator commercial licence only if NC tasks are wanted in a public build; (5) budget
for an annotator or accept agent-only correction with the gates.
