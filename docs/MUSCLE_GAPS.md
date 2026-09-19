# Muscle completeness: what has geometry, what does not, and the route for each gap

*Written 2026-09-14 after the owner: "there are a lot of missed muscles, partial or complete; compare it to Z-Anatomy". Counts regenerate with the snippet in PROJECT_STATE (Q62).*

The atlas carries **404 muscle entities** (one record per side). Meshes exist for **154** of them on both bodies and for **250** (128 distinct muscles) on neither. Z-Anatomy's structure list (read as a CHECKLIST only: its models are CC BY-SA and do not enter this repository) names 184 muscle-like structures; after removing groups and synonyms it adds about fifteen small muscles the entity list lacks (articularis genus, dartos, depressor labii inferioris, depressor septi nasi, depressor supercilii, levator anguli oris, and the auricular muscles: auricularis anterior/superior/posterior, helicis major/minor, tragicus, antitragicus, transverse and oblique muscles of the auricle). Those fifteen were added on 2026-09-14 (Q65) as literature records (Gray's / TA attachments, innervation and actions; no architecture numbers, the records say none were verified; dartos is one midline smooth-muscle record; the posterior auricular branch of the facial nerve was added as a nerve entity), so the atlas now carries 433 muscle entities. The ENTITY list is complete against that checklist; the GEOMETRY is not.

**Recount 2026-09-19, after Q96** (female viewer V37, male V50): 433 entities, meshes on BOTH bodies for
**202** (unchanged -- platysma is her-only), on at least one for **227** (was 225), on NEITHER for **206**
(was 208, 115 distinct muscles). `neck` missing-on-both dropped 16 -> 14 (both `platysma_l/r`). All other
region counts unchanged from the entry below.

**Recount 2026-09-19 08:30** (female viewer V36, male V48, now V49 after Q91's genioglossus swap below --
re-run `scripts/recount_muscle_gaps.py` after Q91 and the numbers below are unchanged, since it replaced an
already-shipped structure rather than closing a new gap; regenerated with `scripts/recount_muscle_gaps.py`, a now-committed tool -- matches each `data/muscles/**/*.json` entity's `id` against each `build/viewer_*/bundle.json`'s structure `id`s; run it again any time either viewer is re-exported): 433 entities, meshes on BOTH bodies for **202**, on at least one for **225**, on neither for **208** (116 distinct muscles). Against the 2026-09-16 baseline of 195/219 the gap has closed by another 7 entities in the three days since, almost entirely from his new pelvic floor (Q83/Q86: `levator_ani`, `coccygeus`, `external_anal_sphincter`, `deep_transverse_perineal` each newly match an atlas entity ALREADY on her side from her own 2026-09-16 pelvic-floor ship, so each is a "both bodies" gain, not just a "one body" one). By region, missing-on-both entities now break down: **head 88** (by far the largest remaining gap -- face, ear, larynx, palate, intrinsic tongue; still 88 after Q90 investigated it directly and characterized the now-available head cryosection data precisely, but shipped zero muscles -- see "Hyoid, tongue, palate, pharynx, larynx" below for the full finding, including two entities, `stapedius`/`tensor_tympani`, now confirmed permanently out of scope for this dataset rather than pending on a future stream), upper_limb 41 (both forearms partially shipped but many individual muscles still over/under-sized and unshipped -- see the Forearm section below; Q71's attempt at her LEFT forearm specifically did not ship), trunk 31 (the deep spinal muscles under CT resolution, the abdominal wall's still-fragmented internal_oblique/transversus from Q78/81/84, is not itself a "missing" gap since it IS shipped, just imperfect), lower_limb 30 (mostly the foot, still blocked on Q59/Q85's DU release), neck 16, wrist_hand 2. The single largest remaining block is still the **head region (88 entities)**: Q90 (below) found and characterized the head-region cryosection data (his whole-body stream already covers it, no new stream needed) but shipped nothing, since the 1 mm downsample does not resolve any individual named muscle there and native resolution is an unstarted next step -- see "Hyoid, tongue, palate, pharynx, larynx" below for the full finding.

**Recount 2026-09-16 12:00** (female viewer V31, male V39): 433 entities, meshes on BOTH bodies for 195, on at least one for 214, on neither for 219 (122 distinct muscles). Against the 2026-09-14 baseline of 154/250 the gap has closed by 31 more entities: her deep neck and floor of mouth (also carried onto him), the diaphragm and intercostals on both, her hand intrinsics, both forearms and his rhomboid minor onto her. Still open by region: face and ear (16), larynx, palate and intrinsic tongue (beyond 1 mm), foot (waiting on the Denver release, Q59), the left limbs, and the deep spinal muscles that are under CT resolution.

**Recount 2026-09-14 18:55** (from the published bundles, female V26 / male V38): 433 entities, meshes on both bodies for 167, on at least one for 198, on neither for 235 (127 distinct muscles; of the ORIGINAL 250 gaps, 44 are now filled or partly filled). Shipped today: her right forearm (12), his right forearm (3, the rest over-sized and unshipped), her deep neck and suboccipitals (8 per side), the diaphragm and intercostal sheets on both bodies, teres minor/major and his rhomboids, the tarsals as bones. In progress: her hand intrinsics, her supra/infrahyoid and extrinsic tongue muscles.

## Missing on both bodies, by group, with the real-source route

### Forearm -- 20 missing

`brachioradialis`, `anconeus`, `pronator_teres`, `pronator_quadratus`, `supinator`, `flexor_carpi_radialis`, `flexor_carpi_ulnaris`, `palmaris_longus`, `flexor_digitorum_superficialis`, `flexor_digitorum_profundus`, `flexor_pollicis_longus`, `extensor_carpi_radialis_longus`, `extensor_carpi_radialis_brevis`, `extensor_digitorum`, `extensor_digiti_minimi`, `extensor_carpi_ulnaris`, `abductor_pollicis_longus`, `extensor_pollicis_brevis`, `extensor_pollicis_longus`, `extensor_indicis`

Route: HER full-resolution cryosection crops of both forearms are on disk (elbow to fingertips, 491 levels): flexor/extensor compartments by the interosseous membrane, then each muscle by a marker watershed on the fascial lines with markers placed by position rules relative to radius and ulna (as the septa refinement did for the thigh). Him: the DU release does not cover the arm; his arm cryosections at 1 mm (re-streamable) give the same rules at lower resolution. Her CT has only the RIGHT radius/ulna; the left forearm needs its bones first (the Q30 lesson: seeds from an independent modality).

### Hand intrinsics -- 11 missing

`abductor_pollicis_brevis`, `flexor_pollicis_brevis`, `opponens_pollicis`, `adductor_pollicis`, `abductor_digiti_minimi_hand`, `flexor_digiti_minimi_brevis_hand`, `opponens_digiti_minimi`, `palmaris_brevis`, `lumbricals_hand`, `dorsal_interossei_hand`, `palmar_interossei`

Route: her hand crops (same stream) at 0.33 mm: thenar, hypothenar, interossei and lumbricals by compartment rules relative to the metacarpals (her right hand bones are in the CT).

### Shoulder girdle -- 4 missing

`teres_major`, `teres_minor`, `subclavius`, `rhomboid_minor`

Route: teres major and minor by position rules on her cryosections (the cuff rule carries infraspinatus + teres minor merged: split at the scapular lateral border); subclavius and rhomboid minor are thin -- the rhomboid label exists as one mass on both bodies (vhf/vhm_pecminor_rhomboids) and can be split major/minor at the C7-T1 spinous level.

### Foot -- 14 missing

`fibularis_brevis`, `fibularis_tertius`, `extensor_digitorum_brevis`, `extensor_hallucis_brevis`, `abductor_hallucis`, `flexor_digitorum_brevis`, `abductor_digiti_minimi_foot`, `quadratus_plantae`, `lumbricals_foot`, `flexor_hallucis_brevis`, `adductor_hallucis`, `flexor_digiti_minimi_brevis_foot`, `plantar_interossei`, `dorsal_interossei_foot`

Route: the DU FEMALE release (Q59) is the honest source for the foot; until it arrives, her foot is not yet streamed at full resolution (a stream like the arm crops, ~500 levels).

### Deep neck and suboccipital -- 13 missing

`longus_colli`, `longus_capitis`, `rectus_capitis_anterior`, `rectus_capitis_lateralis`, `splenius_capitis`, `splenius_cervicis`, `semispinalis_capitis`, `semispinalis_cervicis`, `semispinalis_thoracis`, `rectus_capitis_posterior_major`, `rectus_capitis_posterior_minor`, `obliquus_capitis_superior`, `obliquus_capitis_inferior`

Route: TotalSegmentator's head/neck task labels only the scalenes, SCM, trapezius, levator scapulae, thyrohyoid, platysma and constrictors; splenius, semispinalis, longus and the suboccipitals need position rules on the cryosections (her 1 mm frame covers the neck) between the vertebral labels of the total task.

### Trunk wall and back -- 14 missing

`diaphragm`, `external_intercostals`, `internal_intercostals`, `innermost_intercostals`, `subcostales`, `transversus_thoracis`, `levatores_costarum`, `serratus_posterior_superior`, `serratus_posterior_inferior`, `rotatores`, `interspinales`, `intertransversarii`, `pyramidalis`, `cremaster`

Route: diaphragm and intercostals are sheets 2-5 mm thick: the 1 mm frames show them but need dedicated rules (the diaphragm as the muscular dome between the lung bases and the liver/spleen, both labelled by the total task); rotatores, interspinales and intertransversarii are under the CT's resolution and stay literature-only.

### Pelvic floor and perineum -- 7 missing

`levator_ani`, `coccygeus`, `external_anal_sphincter`, `bulbospongiosus`, `ischiocavernosus`, `deep_transverse_perineal`, `superficial_transverse_perineal`

Route: her 1 mm frame covers the pelvis; levator ani is visible as the sling around the rectum -- a rule between the pelvic viscera labels (total task) and obturator internus. Literature-only until then.

### Hyoid, tongue, palate, pharynx, larynx -- 28 missing

`sternohyoid`, `omohyoid`, `stylohyoid`, `mylohyoid`, `geniohyoid`, `hyoglossus`, `styloglossus`, `palatoglossus`, `superior_longitudinal_tongue`, `inferior_longitudinal_tongue`, `transverse_tongue`, `vertical_tongue`, `levator_veli_palatini`, `tensor_veli_palatini`, `musculus_uvulae`, `palatopharyngeus`, `salpingopharyngeus`, `stylopharyngeus`, `superior_pharyngeal_constrictor`, `middle_pharyngeal_constrictor`, `inferior_pharyngeal_constrictor`, `cricothyroid`, `posterior_cricoarytenoid`, `lateral_cricoarytenoid`, `transverse_arytenoid`, `oblique_arytenoid`, `thyroarytenoid`, `vocalis`

**Q91 (2026-09-19) correction: `genioglossus` removed from this list -- it is not missing.** It has actually
been shipped on BOTH bodies since 2026-09-16 (her native `ct_vhf_hyoid`, 9.1/10.5 cm3; his cross-body-
transferred `xfer_vhf2vhm_neck`, 13.4/13.9 cm3) and this list simply went stale after that ship (the
recount tool's aggregate numbers were already correct throughout; only this per-muscle enumeration wasn't
refreshed). NOTE for a future pass: `mylohyoid`, `geniohyoid`, `hyoglossus`, `styloglossus`,
`middle_pharyngeal_constrictor` and `inferior_pharyngeal_constrictor` are ALSO already shipped on at least
one body (same 2026-09-16 ship, plus the constrictors from the head/neck CT task) and likely belong in the
"partial" section below rather than here -- not fully re-audited this pass, flagged rather than fixed to
keep this pass's scope to the genioglossus finding below.

Route: the pharyngeal constrictors are DONE today from the head/neck task (middle and inferior on her, all three on him; the superior on her is 196 voxels and not shipped). The rest are small; tongue and larynx muscles are beyond CT and need the head cryosections at full resolution.

**Q90 (2026-09-19) head cryosection characterization -- pilot investigated, zero muscles shipped.** The premise that "no body has a head cryosection stream" turned out to be wrong: his whole-body cryosection stream re-derived this session for Q79/80 (`scripts/cryo/stream_vhm_cryosections.py`, 1878 slices, 1 mm downsample) starts at the vertex (raw cryo index 0) and runs continuously down through the head, neck and into the thorax -- there is no missing head block, it was already sitting in the same stream the arm work used. Cross-checked precisely against his CT head/neck labels (`vhm_craniofacial_structures.nii.gz`, `vhm_oculomotor_muscles.nii.gz`, `vhm_head_muscles.nii.gz`, `vhm_headneck_bones_vessels.nii.gz`) via the existing `cryo_idx = -16 - z_ras` mapping from `scripts/cryo/resample_cryo_to_ct_frame.py` (fit for the trunk registration but, per this check, holding up visually all the way to the vertex): frontal sinus/forehead cryo idx ~43-95, orbits (eyeballs) ~94-118, maxillary sinus/cheek ~115-167, upper teeth ~159-183, mandible (whole bone) ~128-232, tongue body ~165-211, lower teeth ~175-205, hyoid ~222-232, thyroid cartilage (larynx) ~231-272, cricoid cartilage ~258-280 -- verified by rendering the actual cryo slices at each predicted index and confirming the anatomy (eyeballs visible at idx ~90-110, nasal cavities at ~130, dental arches and tongue at ~160-210, laryngeal cartilage/vertebra at ~250-280, unambiguous rib/thorax cross-sections by idx ~290-310). **No new "head" resample branch is needed**: the existing "torso" branch of `resample_cryo_to_ct_frame.py` already spans this whole range (cryo idx ~4-847) with no gap where it meets the neck/thorax, and the already-computed `cryo_torso_frame_rgb.npy` in the scratchpad (from earlier this session) was checked directly at k=741 (predicted orbit level) and k=615 (predicted larynx/neck level) and shows correctly-aligned eyeballs and a laryngeal/vertebral cross-section respectively -- a future head script can read that frame directly, the same way `vhf_pelvic_floor_from_cryo.py` reads its own body's frame, with no new registration step.
Resolution finding: at the streamed 1 mm downsample, gross structures (tongue body, mandible, dental arches, orbits, larynx cartilages) are clearly identifiable and well contrasted, but nothing finer separates cleanly -- checked directly by zooming on the tongue (idx 160-210: the median lingual septum, a genuine fibrous midline structure, is faintly visible as a pale line, but no boundary separates any of the 15 named tongue muscles, and none should exist for the 4 intrinsic layers, which are defined by fibre orientation with no fascial plane even at full dissection) and on the perioral/chin skin (idx 158-190: no discrete muscle band resolves out of the general subcutaneous layer). Fetched three native-resolution DICOM frames directly from the IDC series (1216x2048, ~3x finer than the streamed 1 mm downsample) at the same tongue/chin levels: the median septum shows much more clearly as a converging-fibre pattern, and there is a subtle, unconfirmed color/texture patch in the chin consistent with (but not verified as) the mentalis -- a real, actionable lead for a future session with time budgeted to re-stream just the head slices at native resolution and register them precisely to `vhm_craniofacial_structures.nii.gz`'s finer (0.5273 mm) grid, but not pursued further this pilot per the "don't force something implausible" rule.
**`stapedius`/`tensor_tympani` -- confirmed out of scope for this dataset, not a route-forward gap.** Rendered the temporal-bone region directly (cryo idx ~105-157, the styloid-process/petrous level from `vhm_headneck_bones_vessels.nii.gz`): the petrous temporal bone shows as dense, uniform pale bone with no internal muscle-colored texture at any resolution available here, as expected -- these two muscles are a few millimetres long, fully embedded in the air-filled middle-ear cavity, and are only ever seen by micro-dissection or micro-CT, never by gross cross-sectional photography. Marked literature-only, permanently, rather than "needs head cryosections" like the rest of this section.
Net result: zero muscles shipped this pilot (tongue's real, unshipped CT boundary -- `vhm_head_muscles.nii.gz` label 9, currently `no_atlas_entity` in `mappings/subjects/ct_vhm_headm_volume_mapping.json` -- would misrepresent any of the 15 named tongue-muscle entities if assigned to it whole, since none of them is "the whole tongue"; shipping a left/right split at the septum would still not correspond to any single named muscle either). This is deliberately a documented negative, not a forced/implausible ship. The most promising concrete next step is native-resolution genioglossus specifically, anchored on its mandibular-symphysis origin the way `vhf_hyoid_muscles_from_cryo.py` anchors on bone, rather than the whole tongue or the perioral face.

**Q91 (2026-09-19) followed up: male genioglossus, from his own CT after all -- no native cryo stream needed.**
Tried the recommended next step and found, before writing any native-resolution stream, that
genioglossus_r/l were already shipped on the male (not from this pilot -- from an EARLIER cross-body
transfer, `xfer_vhf2vhm_neck`, 2026-09-16: 13.4/13.9 cm3, warped from the female's own native genioglossus
onto his mandible/hyoid). So the task became "can his own tissue beat a cross-body warp," not "close a
gap." Read `vhf_hyoid_muscles_from_cryo.py` in full per the task's instruction: her genioglossus's
TONGUE-region portion (`tongue_rules()`) is a PURELY POSITIONAL rule inside her own CT tongue label
(paramedian fan dx < 10 mm of the midline, AP fraction > 0.25, below the dorsum's top 8 mm) -- her cryo
photographs refine OTHER parts of her pipeline (the floor-of-mouth compartment, septum watersheds) but not
this specific rule. The male has the exact same CT ingredient (`vhm_head_muscles.nii.gz` label 9, the
undifferentiated tongue mask this document earlier called unshippable whole -- correctly, for the 15-way
split, but genioglossus alone has a real geometric signature the position rule can recover). New script
`scripts/cryo/vhm_genioglossus_from_ct.py` replicates that rule directly in native CT voxel space, anchored
on the mandible's own midline (its mental-spine/symphysis axis) rather than the tongue label's own
per-slice centroid. No cryo texture needed anywhere in this pipeline. RESULT: genioglossus_r 11.25 cm3
(voxel) / 11.13 cm3 (mesh), genioglossus_l 12.17 / 12.04 cm3, out of 45.1 cm3 total CT tongue-label volume
-- between the female's own native value (9.1/10.5 cm3) and the previously-transferred value (13.4/13.9
cm3), as expected (this rule only captures the intralingual portion, not her rule's separate
floor-of-mouth extension down to the mandible, which sits outside the CT tongue label and was not
attempted, matching the instruction to exclude rather than re-derive the already-shipped mylohyoid/
geniohyoid). Sleep-apnea MRI genioglossus volumetry literature recalled from training commonly reports
adult per-side volumes around 8-16 cm3; this falls inside that range but is NOT verified against one
specific citation. Verification: 1 connected component per side at both voxel (`scipy.ndimage.label`) and
mesh (`scipy.sparse`+`csgraph`) level; 0.0 fraction of genioglossus vertices found inside the mandible/
teeth or the already-shipped mylohyoid_r/l, geniohyoid_r/l meshes (`trimesh` signed distance; nearest
surface distances 0.9-9.8 mm, adjacent not overlapping); Playwright render QA shows a plausible fan/wedge
seated directly against the mandible at the midline. SHIPPED, replacing the transferred copy: new subject
`ct_vhm_ggl`; the `xfer_vhf2vhm_neck` transfer step no longer carries genioglossus. Male viewer bundle
re-exported (357 structures) and republished (Version 49). One reusable finding for the rest of this
section: several of the OTHER "missing" entries listed above (mylohyoid, geniohyoid, hyoglossus,
styloglossus) may be similarly recoverable from CT position rules alone, without native cryo, now that this
pilot has shown the technique transfers from her pipeline to his CT directly -- not attempted this pass.

**Q92 (2026-09-19) followed up Q91's own note: checked all four candidates, shipped one (styloglossus),
left three on the transfer with a documented reason each.** Read `vhf_hyoid_muscles_from_cryo.py`'s
`floor_rules()` and `tongue_rules()` in full for mylohyoid, geniohyoid, hyoglossus and styloglossus and
checked, per muscle, whether its rule needs only CT-visible position or fundamentally needs cryosection
photograph texture:
- **mylohyoid, geniohyoid: NOT recoverable from CT alone, left on the transfer.** Both live entirely in her
  `floor_rules()`'s "floor of mouth" compartment below the tongue, and that compartment itself
  (`floor_compartment()`) is `M["dark"]` (her cryo photograph's dark-muscle colour class) intersected with
  a CT-geometric box -- nothing in the male's CT labels (`total`, `head_muscles`, `headneck_bones_vessels`,
  `headneck_muscles_merged`, `craniofacial_structures`) segments the submandibular/sublingual glands or fat
  that also fill that space (her own script's data list doesn't have a gland CT label either -- her
  exclusion of them is entirely from the cryo photograph's pale colour class). 0% of either muscle falls
  inside his CT tongue label (the one CT-native "this is already a muscle" mask), so there is nothing to
  split positionally the way genioglossus was split. Confirmed present on him only via `xfer_vhf2vhm_neck`.
- **hyoglossus: NOT recoverable from CT alone (checked quantitatively), left on the transfer.** Its rule
  has TWO sources: `floor_rules()`'s "hg" sheet (same cryo-dark floor-compartment dependency as
  mylohyoid/geniohyoid) plus `tongue_rules()`'s "hg" (purely positional, inside the tongue label). Probed
  her OWN CT tongue label with the exact `tongue_rules()` hg formula and compared to her actual shipped
  hyoglossus_r/l (4.0 + 5.4 = 9.4 cm3): the tongue-only portion is 1.98 cm3, ~21% of her real muscle. The
  other ~79% needs cryo texture. Shipping just that CT-tongue fragment for the male would be a small,
  unrepresentative sliver at the tongue's postero-lateral margin, not a recognizable hyoglossus (a flat
  quadrilateral sheet whose bulk sits BELOW the tongue) -- would degrade, not improve on, the transfer.
- **styloglossus: recoverable from CT alone, and SHIPPED.** Same two-source structure as hyoglossus (a
  cryo-dependent CORRIDOR from the styloid process, plus a positional `tongue_rules()` "sg" portion), but
  the same probe on her data gives the opposite answer: her tongue-only sg is 3.53 cm3 vs her actual shipped
  total 3.3 cm3 -- i.e. essentially ALL of her styloglossus volume is already inside the CT tongue label
  (the extralingual corridor is a slender cord contributing little bulk; the muscle fans out and
  interdigitates with the tongue's intrinsic fibres over most of its length). New script
  `scripts/cryo/vhm_styloglossus_from_ct.py` replicates `tongue_rules()`'s sg criterion (dxT >= 15 mm of
  the tongue label's OWN per-slice centroid -- not the mandibular midline genioglossus uses, which
  collapsed styloglossus to ~0 cm3 when tried first; the mandible axis is right for genioglossus
  specifically because that muscle originates there, but styloglossus/hyoglossus are positioned relative to
  the bulk of the tongue, which is what her original centroid-based dxT measures) directly in his CT, using
  the ALREADY-SHIPPED `ct_vhm_ggl` mask (loaded, not recomputed) as the "not genioglossus" exclusion so
  there is zero overlap by construction, plus a matching hyoglossus-shaped exclusion zone (not shipped)
  so styloglossus does not eat into where hyoglossus would be. His styloid process IS present in his own
  CT (`vhm_headneck_bones_vessels.nii.gz` labels 7/8, same ids as her file) but that landmark ended up not
  needed, same as genioglossus's floor-of-mouth extension was not needed for Q91. RESULT: styloglossus_r
  0.68 cm3 (mesh) / 0.75 cm3 (voxel), styloglossus_l 1.33 / 1.41 cm3 -- same order of magnitude as her own
  native value (1.8/1.5 cm3) and smaller than the previously-transferred value (2.19/1.48 cm3); the R/L
  asymmetry is larger than hers and traced to the tongue label's own lateral extent being asymmetric right
  at the 15 mm threshold band -- noted as a limitation, not hidden. Verification: 1 connected component per
  side at both voxel and mesh level (after keeping only the largest voxel component, which dropped a single
  stray fragment adding <0.001 cm3); 0.0 fraction of vertices found inside the mandible, genioglossus or
  geniohyoid (both watertight, `trimesh` containment check); nearest-surface distances to mandible (6.6-7.9
  mm), mylohyoid (20.3-20.4 mm), geniohyoid (25.0-26.1 mm) and the transferred hyoglossus (8.5-8.6 mm) all
  positive -- adjacent, not overlapping; Playwright render QA (headless Chromium, local three.js) shows a
  plausible rounded muscle mass seated at the tongue's postero-lateral margin, correctly positioned among
  the other head muscles. Does NOT include the extralingual (styloid-to-tongue corridor) part of the
  muscle -- same partial-but-honest ship style as Q91's genioglossus. SHIPPED, replacing the transferred
  copy: new subject `ct_vhm_sgl`; `xfer_vhf2vhm_neck` no longer carries styloglossus (mylohyoid, geniohyoid
  and hyoglossus still do, correctly, per the findings above). Male viewer bundle re-exported (357
  structures, unchanged count -- a swap, not a new gap closed) and republished (Version 50).

### Face and ear -- 15 missing

`occipitofrontalis`, `frontalis`, `orbicularis_oculi`, `procerus`, `nasalis`, `orbicularis_oris`, `buccinator`, `zygomaticus_major`, `zygomaticus_minor`, `levator_labii_superioris`, `depressor_anguli_oris`, `mentalis`, `risorius`, `stapedius`, `tensor_tympani`

`platysma` REMOVED from this list (Q96): shipped on HER from CT alone (TotalSegmentator's `headneck_muscles` task labels it directly, a reviewed-but-declined mapping entry reversed on new mesh-topology evidence -- see PROJECT_STATE Q96). His own platysma is a genuine CT dead end (0.01 cm3 on the same task, essentially undetected), so this is a female-only, CT-only win, not a precedent for the rest of this list -- the other 15 have no CT task labelling them at all and still need his head cryosections at native resolution (Q90's characterized-but-unshipped route).

Route: beyond CT; his head cryosections (now streamed and characterized, Q90 above) at full resolution for the larger ones (orbicularis oculi/oris, buccinator) -- the 1 mm downsample does not resolve them, native resolution (0.33 mm, fetchable per-slice from the same IDC series) shows a promising but unconfirmed lead and is the next step. `stapedius`/`tensor_tympani` are confirmed out of scope for any photographic or CT source (Q90) and stay literature-only permanently, not pending on a future stream.

## "Partial" muscles (present but truncated)

A mesh can exist and still be incomplete: every structure taken from a CT block is cut where the block ends (her torso CT ends at mid-thigh, so gluteus maximus/medius/minimus and the hip rotators on her are the torso block's; her legs block re-supplies the long bones but not the muscles), the male's frozen CT could not separate fat from muscle above the hip (his trunk muscles come from rules and from the third body s1159), and rule-based structures carry their own bands (deltoid, cuff, arm compartments). The badge on every structure names its source; `data/derived/cross_subject_scale_audit.json` lists the shared structures whose volume ratio between the bodies is off, the fastest way to find a truncated one.

## Order of work (Q62)

1. Forearm compartments and muscles on her (crops on disk), then on him.
2. Shoulder girdle: teres major/minor split, rhomboid major/minor split, subclavius.
3. Deep neck and suboccipital rules on her 1 mm frame.
4. Hand intrinsics from her hand crops.
5. Foot: the DU female release (Q59), or her foot streamed at full resolution.
6. Diaphragm, intercostals, pelvic floor rules.
7. Head and larynx from head cryosections at full resolution.
8. The ~15 Z-Anatomy-named small muscles as entities (literature records) so the list is complete.
