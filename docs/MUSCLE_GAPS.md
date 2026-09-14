# Muscle completeness: what has geometry, what does not, and the route for each gap

*Written 2026-09-14 after the owner: "there are a lot of missed muscles, partial or complete; compare it to Z-Anatomy". Counts regenerate with the snippet in PROJECT_STATE (Q62).*

The atlas carries **404 muscle entities** (one record per side). Meshes exist for **154** of them on both bodies and for **250** (128 distinct muscles) on neither. Z-Anatomy's structure list (read as a CHECKLIST only: its models are CC BY-SA and do not enter this repository) names 184 muscle-like structures; after removing groups and synonyms it adds about fifteen small muscles the entity list lacks (articularis genus, dartos, depressor labii inferioris, depressor septi nasi, depressor supercilii, levator anguli oris, and the auricular muscles: auricularis anterior/superior/posterior, helicis major/minor, tragicus, antitragicus, transverse and oblique muscles of the auricle). Those fifteen were added on 2026-09-14 (Q65) as literature records (Gray's / TA attachments, innervation and actions; no architecture numbers, the records say none were verified; dartos is one midline smooth-muscle record; the posterior auricular branch of the facial nerve was added as a nerve entity), so the atlas now carries 433 muscle entities. The ENTITY list is complete against that checklist; the GEOMETRY is not.

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

### Hyoid, tongue, palate, pharynx, larynx -- 29 missing

`sternohyoid`, `omohyoid`, `stylohyoid`, `mylohyoid`, `geniohyoid`, `genioglossus`, `hyoglossus`, `styloglossus`, `palatoglossus`, `superior_longitudinal_tongue`, `inferior_longitudinal_tongue`, `transverse_tongue`, `vertical_tongue`, `levator_veli_palatini`, `tensor_veli_palatini`, `musculus_uvulae`, `palatopharyngeus`, `salpingopharyngeus`, `stylopharyngeus`, `superior_pharyngeal_constrictor`, `middle_pharyngeal_constrictor`, `inferior_pharyngeal_constrictor`, `cricothyroid`, `posterior_cricoarytenoid`, `lateral_cricoarytenoid`, `transverse_arytenoid`, `oblique_arytenoid`, `thyroarytenoid`, `vocalis`

Route: the pharyngeal constrictors are DONE today from the head/neck task (middle and inferior on her, all three on him; the superior on her is 196 voxels and not shipped). The rest are small; tongue and larynx muscles are beyond CT and need the head cryosections at full resolution.

### Face and ear -- 16 missing

`occipitofrontalis`, `frontalis`, `orbicularis_oculi`, `procerus`, `nasalis`, `orbicularis_oris`, `buccinator`, `zygomaticus_major`, `zygomaticus_minor`, `levator_labii_superioris`, `depressor_anguli_oris`, `mentalis`, `risorius`, `platysma`, `stapedius`, `tensor_tympani`

Route: beyond CT; her head cryosections at full resolution for the larger ones (orbicularis oculi/oris, buccinator, platysma); the ear muscles stay literature-only.

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
