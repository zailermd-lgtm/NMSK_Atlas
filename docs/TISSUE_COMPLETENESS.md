# Tissue completeness across ALL types: what has geometry, what does not

*Written 2026-09-22 (Q117): generalizes `docs/MUSCLE_GAPS.md`'s own method -- matching every entity's
`id` in its `data/<type>/` record against both published viewers' bundle structure ids -- from muscles
(the only type this had ever been run for) to every other tissue-type directory the data model tracks.
Counts regenerate with `scripts/recount_tissue_gaps.py` (all types) or `scripts/recount_muscle_gaps.py`
(muscles only, unchanged, still the tool `docs/MUSCLE_GAPS.md` itself uses). Originally measured against
the LIVE published bundles (`build/viewer_m/bundle.json` male, 356 structures; `build/viewer_f/
bundle.json` female, 378 structures) -- NOT the pending Q108-Q116 rebuilds sitting unpublished in
`build/viewer_*/atlas_viewer_*.html`.*

*UPDATED 2026-09-22 (Q118): the tendons row below reflects Q118's own additive rebuild on top of
Q108-Q116's state (`build/viewer_m/bundle.json` male, now 362 structures; `build/viewer_f/bundle.json`
female, now 384) -- 6 new tendon ids (`iliopsoas_tendon`, `adductor_magnus_distal_tendon`,
`quadriceps_tendon`, each `_r`/`_l`), all PROCEDURAL/RULE-BASED connector meshes, not segmented imaging
-- see `data/tendons/lower_limb_tendons.json`'s own `procedural_geometry` blocks on those 6 records and
PROJECT_STATE.md's Q118 entry for the full disclosure and verification. Still NOT the "LIVE PUBLISHED"
sense Q117 used the phrase in (Production Deploy remains gated, unchanged since Q108) -- same
pending-but-real local build state every Q10X/Q11X item today accumulated into. All other rows are
unchanged from Q117 (this item touched only `data/tendons/`).

Full per-entity detail (which id is missing, on which body, in which region): `data/derived/Q117_full_completeness_audit.json` (tendons row there is now stale by 6 entities; re-run `scripts/recount_tissue_gaps.py --type tendons` for the current numbers, reproduced below).

## The numbers, by type

| Type | Entities | Both bodies | Either only | Neither (missing) | % missing | Distinct structures missing |
|---|---:|---:|---:|---:|---:|---:|
| Bones | 86 | 50 | 11 | 25 | 29% | 15 |
| Muscles | 433 | 202 | 32 | 199 | 46% | 110 |
| Cartilage | 36 | 10 | 0 | 26 | 72% | 17 |
| Vascular | 412 | 20 | 4 | 388 | 94% | 207 |
| Ligaments | 91 | 8 | 0 | 83 | 91% | 47 |
| Nerves | 303 | 1 | 3 | 299 | 99% | 287 |
| Fascia | 104 | 1 | 0 | 103 | 99% | 94 |
| **Tendons** | **51** | **6** (Q118) | **0** | **45** | **88%** | **23** |
| **Bursae** | **45** | **0** | **0** | **45** | **100%** | **23** |
| **Total** | **1561** | **298** (Q117: 292) | **50** | **1213** (Q117: 1219) | **78%** | -- |

`data/skeleton/joints.json` (60 records) is deliberately excluded from the "bones" row and from the
total: its entries are kinematic articulations (degree-of-freedom ranges, coordinate systems), not mesh
entities, and 0 of its 60 ids appear in either bundle *by design* -- a joint has no mesh of its own, it
is implied by its adjoining bones. Measured anyway for transparency in the JSON report's
`excluded_but_measured_for_transparency.joints` block (0/60 both, as expected).

## Is this a first-ever audit, or a refresh?

- **Muscles**: refresh. This is the type Q62 built the method for (2026-09-14, 404 entities/154 both/250
  neither at the time) and it has been re-run after nearly every subsequent muscle-affecting item since
  (`docs/MUSCLE_GAPS.md`'s own recount log). Today's 433/202/199 matches the number already live in
  PROJECT_STATE before this item (no muscle work happened in Q117 itself).
- **Bones, cartilage, ligaments**: Q103 (2026-09-20) audited *shipped* structures of these types for
  continuity, but only inventoried what was already in the bundle (15 bones, 2 cartilage, 0 ligaments
  shipped at the time) -- it never compared against the FULL entity catalog in `data/skeleton/bones.json`
  / `data/cartilage/*.json` / `data/ligaments/*.json` the way this item does. This is the first time the
  Q62-style "does a mesh exist AT ALL for every entity the data model says should exist" check has been
  run for these three types.
- **Tendons, fascia, bursae, nerves, vascular**: first-ever. No completeness check of any kind -- Q62-style
  or Q103-style -- has been run against these five types before this item. PROJECT_STATE.md mentions
  bursae only in the context of adding the category (2026-09-06/2026-09-09) and trigger-point work, never
  a coverage count; tendons, ligaments and fascia are never mentioned in a gap/completeness context prior
  to Q117.

## Most surprising findings

1. **Tendons and bursae are at literal 0% geometry coverage.** Both directories carry richly-detailed,
   real-source-cited entity records (tendon records include `attachments`, `parts`, `has_synovial_sheath`,
   `prp_injection_approach`; bursa records include `communicates_with_joint`, `injection_approach`,
   `clinical_significance`) -- substantial content investment with zero corresponding geometry investment.
   This is a much worse gap than muscles' current 46%, and unlike muscles (which has an 8-region,
   fully-routed fill plan in `docs/MUSCLE_GAPS.md`), neither type has ever had its fill route scoped.
2. **Nerves and fascia are effectively also at 0%** (99% and 99% missing respectively) -- the ONE fascia
   entity that ships on both bodies is `skin` (the whole-body surface envelope, `data/fascia/body_surface.json`),
   not a deep fascial sheet; the one nerve that ships on both is `optic_n`. Three more nerves
   (`femoral_n`, `sciatic_n`, `tibial_n`) ship on the female only -- `sciatic_n`'s continuity was the
   subject of Q113's own fix this same day, confirming it is a genuinely modelled structure, just not yet
   on the male.
3. **Bones is, unexpectedly, the most complete non-muscle type (71% at-least-one, 58% both)** -- nobody
   had confirmed this with a full-catalog count before (Q103 only counted what already shipped). It is
   comparable to muscles' own coverage level, a real and previously unmeasured bright spot.
4. **Ligaments and cartilage never mix bodies partially**: every ligament or cartilage entity with any
   mesh at all has it on BOTH bodies (either-count = 0 for both types) -- consistent with these being
   rule-based structures generated identically for both bodies from the same joint/bone landmarks, unlike
   muscles and vascular, which carry many single-body wins from CT/cryosection work specific to one
   subject.
5. **Across all 9 types combined, 1219 of 1561 entities (78%) have no mesh on either body.** The dataset's
   overall completeness picture is far worse than the muscle-only 46% figure most prior PROJECT_STATE
   entries have quoted, because muscles are (after ~50 Q6X-Q10X items of dedicated work) the single
   best-covered non-bone type.

## What's most valuable to fill first (priority for a future completeness session)

Q117 itself was measurement-only. **Q118 (2026-09-22) acted on item 2 below** and found the honest
ceiling much narrower than hoped: of the "many named tendons" this note originally pointed to, only 6 of
51 (`iliopsoas_tendon`, `adductor_magnus_distal_tendon`, `quadriceps_tendon`, each `_r`/`_l`) actually
resolve to real, already-anchored 3D coordinates through this project's existing landmark/anchor system
-- the Achilles, patellar, pes anserinus, rotator cuff, biceps/triceps and every hand/foot tendon this
note named or implied are all blocked by one specific, fixable pipeline gap: `scripts/
audit_landmarks_vs_geometry.py:build_frames()` cannot construct a measured bone frame for `tibia`,
`tarsals`, `carpals`, `metacarpals` or `phalanges` on this session's geometry (its cartilage-mesh
filename lookups predate a naming change). See PROJECT_STATE.md's Q118 entry (full accounting of all 51)
and its "Open" item 12 (the `build_frames()` fix that would unblock most of the rest). The 6 shipped are
real, measured-length, disclosed PROCEDURAL/RULE-BASED connectors (`data/tendons/lower_limb_tendons.json`'s
own `procedural_geometry` blocks), not segmented tendon imaging -- this project has none.

**CORRECTION (Q121, 2026-09-22)**: Q118's own claim that `build_frames()` covers only `femur`/`fibula`/
`hip_bone`/`patella` (8 bones, r/l) is INCOMPLETE -- true only of the restricted lower-limb subject list
Q118's own `male_order()`/`female_order()` loaded for its own tendon set, not a limit of `build_frames()`
itself, which also has non-cartilage-dependent fallback paths for `humerus`, `radius`, `ulna`, `clavicle`,
`scapula`, `mandible`, `hyoid` and `sternum`. Verified directly against the REAL published (pending)
bundle geometry: **19 bones resolve on the male, 17 on the female** (missing `radius_l`/`ulna_l` on her --
her left forearm is documented elsewhere, Q12/Q71/Q97, as incomplete). `tibia`, `tarsals`, `carpals`,
`metacarpals` and `phalanges` remain genuinely unresolvable (their frame-fitting keys on cartilage-mesh
filenames this session's fused cartilage naming no longer matches) -- see `data/derived/
Q121_ligament_feasibility_audit.json` for the full, re-verified bone list and method.

1. **Bursae, clinically first** (45 entities, 0% coverage): the elbow (10) and shoulder (10+6) bursae
   carry documented `injection_approach` fields already written for this atlas's own stated purpose
   (planning musculoskeletal injections) -- geometry for just these ~26 would make an already-written
   clinical use case usable for the first time. Bursae are typically small, thin synovial sacs; they may
   be recoverable as rule-based structures (a thin shell at a named position relative to two already-
   shipped bones/tendons) rather than needing new CT/cryosection segmentation, similar to how this
   atlas's cartilage/ligament rule-based structures were built -- worth investigating before assuming a
   new imaging stream is needed. **Q118 checked this directly**: every one of the 45 bursa records
   positions itself relative to a tendon-bone or bone-bone junction that is either one of the 45 tendons
   Q118 could NOT ship (the large majority), or would need a genuinely new, never-yet-written positional
   rule -- declined in full this round, not attempted against the 6 tendons Q118 DID ship (their own
   bursae -- iliopsoas bursa, etc. -- were not in the small set checked). Worth a fresh, focused pass now
   that iliopsoas/adductor-magnus/quadriceps tendons exist to potentially anchor a bursa to.
2. **Tendons, same reasoning** (51 entities, ~~0%~~ **now 12%** coverage after Q118 -- see above): many
   named tendons (Achilles, patellar, biceps, rotator cuff insertions) are the direct continuation of an
   ALREADY-SHIPPED muscle belly into an ALREADY-SHIPPED bone insertion -- a position/taper rule bridging
   the two existing meshes is a plausible first attempt, cheaper than a new imaging stream, and Q118 tried
   and honestly evaluated it (verified geometry AND documented declines, as this note asked for): the
   ceiling for a SECOND pass, once `build_frames()`'s cartilage-naming gap (Open item 12) is fixed, is
   most of the remaining 45 -- this was not a dead end, it was gated behind one specific, scoped, fixable
   infrastructure gap.
3. **Ligaments -- investigated in full by Q121 (2026-09-22), 0 of 83 unshipped ligaments qualified.**
   Checked every one against this project's own landmark/anchor system, same rigor as Q118's tendon
   investigation, generalized to bone-to-bone attachments (ligaments connect two BONE landmarks, unlike a
   tendon's muscle-to-bone span). Two independent, real blockers, plus one geometric one found only after
   actually generating a candidate:
   - **50/83 blocked by `build_frames()`'s bone-frame gap** (per the correction above: `tibia`, `tarsals`,
     `carpals`, `metacarpals`, `phalanges`, plus bones this system has never fitted at all --
     `sacrum`/vertebrae/ribs/`occipital`/`temporal` -- or an attachment to a meniscus, which has no
     coordinate in this project's data model at all).
   - **31/83 blocked by a second, independent, previously-undocumented gap**: BOTH attachment bones ARE
     frame-resolvable (this covers the shoulder and elbow ligaments the note above flagged as promising,
     plus the hip capsule and knee patellofemoral/popliteofibular ligaments, plus the pubic ligaments), but
     the ligament's own authored landmark text ("Schottle's point", "intertrochanteric line",
     "musculotendinous junction", "superior pubic ramus", "annular ligament / supinator crest", ...) does
     not match, as an exact substring, any landmark name already authored on that bone in
     `data/skeleton/bones.json`. Not resolved by interpolating between two named landmarks or reusing a
     differently-named nearby one -- per the hard constraint against approximation, declined.
   - **2/83 (`transverse_humeral_ligament_r/l`) passed BOTH checks** (greater tubercle -> lesser tubercle,
     both on the humerus) but FAILED post-generation verification: 70-77% of the generated connector's own
     vertices (95-100% of the pure straight-line midline, independent of cross-section radius) land INSIDE
     the humerus's own mesh on both bodies, because the two tubercle landmarks flank a locally convex bone
     bulge and a straight 3D chord between them cuts inward. The straight-cord method
     `generate_tendon_connectors.py` uses successfully for muscle-to-bone tendons (whose muscle end is
     clearly outside the bone) does not safely generalize to a bone-to-bone connector whose two points
     flank a convex/grooved bone region. Declined rather than shipped half-buried in bone.

   `knee_ligaments.json`'s existing 8-of-18 shipped structures (the 4 cruciate/collateral pairs) are real
   segmented geometry from the DU release, not a rule this session's method can reproduce for the rest of
   that file. **The single biggest lever for unlocking more ligaments (and tendons) is fitting
   `build_frames()`'s transverse/rotational axis** for the bones whose frame currently uses only an origin
   + long axis with the rotational axis left as "anatomical-position convention, not fitted" (`humerus`,
   `scapula`, `clavicle`, `mandible`, `hyoid`, `sternum`) -- without that fit, a landmark's position AROUND
   the bone's circumference (not just along its length) cannot be trusted, which is exactly what broke
   `transverse_humeral_ligament`. A second, purely-data lever (no code change) is aligning
   `data/skeleton/bones.json` landmark names with the phrasing ligament records already cite, which alone
   would unlock the 31 `landmark_text_mismatch` ligaments. See `data/derived/
   Q121_ligament_feasibility_audit.json` for the full per-ligament table and
   `scripts/generate_ligament_connectors.py` for the reusable generator (kept for a future session, not
   deleted, despite shipping nothing this round).
4. **Vascular and nerves are the largest remaining entity counts** (412 and 303) but are also the
   hardest: most named vessels and nerve branches below the major trunks are sub-CT-resolution and would
   need the same "literature-only, no route" honesty muscles' face/ear group already carries -- a future
   session should triage which of the 388/299 missing entities have ANY plausible CT/cryosection route at
   all before treating this as a fillable backlog rather than a mostly-permanent literature-only list.
5. **Bones' remaining 25 gaps** (mostly `cranium_face`, 23 of 25) are individually named facial/cranial
   bones under a composite `cranium` entity that already ships -- likely the cheapest remaining bone gap
   (splitting an existing composite mesh by CT label) rather than needing new segmentation.

None of the above has been attempted or verified this item -- these are measured entity counts and a
reasoned starting point, not confirmed routes.
