# Q233 sex-correctness audit of the six models

Generated 2026-10-13. Owner request: "You must make sure the female model is really a woman, and the male is a man.". Machine-readable twin: `data/derived/Q233_sex_audit.json`.

## Verdict per page

| Page | Declared | Body | Skeleton (core measures) | Subpubic angle | Male-only organs after Q233 | Female-only organs after Q233 | Wrong-sex structures after |
|---|---|---|---|---|---|---|---|
| Imaging-based · Male | male | Visible Human male (his CT / cryosections) | male | 70.7 deg (male) | testis, epididymis, ductus_deferens, seminal_vesicle, prostate, penis_corpora_glans, ejaculatory_duct | - | none |
| Imaging-based · Female | female | Visible Human female (her CT / cryosections) | female | 87.3 deg (female) | - | uterus, ovary, uterine_tube | none |
| Base · Male | male | Z-Anatomy male-derived body | mostly male (some measures ambiguous or female-like) | 57.2 deg (male) | testis, epididymis, ductus_deferens, seminal_vesicle, prostate, penis_corpora_glans, scrotum_urogenital_skin, ejaculatory_duct, testicular_vessels | - | none |
| Base · Female | female | the SAME Z-Anatomy male-derived body | mostly male (some measures ambiguous or female-like) | 57.2 deg (male) | - | uterus, ovary, uterine_tube | none |
| Combined · Male | male | Z male-derived body fitted to the VH male | male | 60.7 deg (male) | testis, epididymis, ductus_deferens, seminal_vesicle, prostate, penis_corpora_glans, scrotum_urogenital_skin, ejaculatory_duct, testicular_vessels | - | none |
| Combined · Female | female | Z male-derived body fitted to the VH female | mostly female (some measures ambiguous or male-like) | 62.7 deg (male) | - | uterus, ovary, uterine_tube | none |

Plain reading: **Imaging-based Male = a man** (subpubic angle 70.7 deg = male range of the verified CT series, 68.6 +- 7.6; the other core measures agree, scored against the two donors); **Imaging-based Female = a woman** (subpubic angle 87.3 deg = the verified female mean 87.4 +- 6.5; the other core measures agree) and, after Q233, carries her uterus, ovaries and tubes (HRA organs of the same donor) and no male coccyx; **Base Male / Combined Male = male**; **Base Female is NOT a woman**: it is the Z-Anatomy male-derived body (the very same skeleton as Base Male) with the male-only organs removed - its honest name is 'Base · Female (male-derived body)'; **Combined Female is mixed**: Z-Anatomy male-derived shapes fitted onto her skeleton (notch and ischiopubic index follow her, subpubic angle stays male-range).

## (a) Organ inventory by sex-specific anatomy

### Imaging-based · Male - published sources (593 structures)
- male-only present: prostate (prostate)
- female-only present: none
- surface patches: none
- wrong-sex structures: none

### Imaging-based · Male - Q233 pages (607 structures)
- male-only present: testis (testis_l, testis_r); epididymis (epididymis_l, epididymis_r); ductus_deferens (ductus_deferens_l, ductus_deferens_r); seminal_vesicle (seminal_vesicle_l, seminal_vesicle_r); prostate (prostate); penis_corpora_glans (corpus_cavernosum_penis, corpus_spongiosum_penis, glans_penis); ejaculatory_duct (ejaculatory_duct_l, ejaculatory_duct_r); male_urethra (urethra_male)
- female-only present: none
- surface patches: none
- wrong-sex structures: none
  - testis: filled from Z-Anatomy (male-derived reference model), fitted to this body: not measured
  - epididymis: filled from Z-Anatomy (male-derived reference model), fitted to this body: not measured
  - ductus_deferens: filled from Z-Anatomy (male-derived reference model), fitted to this body: not measured
  - seminal_vesicle: filled from Z-Anatomy (male-derived reference model), fitted to this body: not measured
  - prostate: measured / rule-based on this body's own CT or cryosections (subject ct_vhm_pelvis)
  - penis_corpora_glans: filled from Z-Anatomy (male-derived reference model), fitted to this body: not measured
  - ejaculatory_duct: filled from Z-Anatomy (male-derived reference model), fitted to this body: not measured
  - male_urethra: filled from Z-Anatomy (male-derived reference model), fitted to this body: not measured
- expected-but-absent (male): bulbourethral_gland, foreskin, scrotum_urogenital_skin, spermatic_cord, testicular_vessels

### Imaging-based · Female - published sources (630 structures)
- male-only present: none
- female-only present: none
- surface patches: none
- wrong-sex structures: none

### Imaging-based · Female - Q233 pages (634 structures)
- male-only present: none
- female-only present: uterus (uterus); ovary (ovary_l, ovary_r); uterine_tube (uterine_tube_l, uterine_tube_r)
- surface patches: none
- wrong-sex structures: none
  - uterus: HRA reference organ of the SAME donor (Visible Human female, CC BY 4.0), registered on the page's pelvis (Q233): not measured here
  - ovary: HRA reference organ of the SAME donor (Visible Human female, CC BY 4.0), registered on the page's pelvis (Q233): not measured here
  - uterine_tube: HRA reference organ of the SAME donor (Visible Human female, CC BY 4.0), registered on the page's pelvis (Q233): not measured here
- expected-but-absent (female): cervix, clitoris, female_urethra, labia_majora, labia_minora, mammary_gland, mons_pubis, ovarian_vessels, uterine_ovarian_ligaments, vagina, vestibular_glands_bulb

### Base · Male - published sources (2966 structures)
- male-only present: testis (zan_testis_l, zan_testis_r); epididymis (zan_epididymis_l, zan_epididymis_r); ductus_deferens (zan_ductus_deferens_l, zan_ductus_deferens_r); seminal_vesicle (zan_seminal_gland_l, zan_seminal_gland_r); prostate (zan_prostate); penis_corpora_glans (zan_corpus_cavernosum_of_penis, zan_corpus_spongiosum_of_penis, zan_deep_artery_of_penis_l, zan_deep_artery_of_penis_r, zan_deep_dorsal_vein_of_penis, zan_dorsal_artery_of_penis_l, zan_dorsal_artery_of_penis_r, zan_glans_penis, zan_superficial_dorsal_veins_of_penis); scrotum_urogenital_skin (zan_skin_urogenital_region_l, zan_skin_urogenital_region_r); ejaculatory_duct (zan_ejaculatory_duct_l, zan_ejaculatory_duct_r); male_urethra (zan_urethra); testicular_vessels (zan_left_testicular_vein, zan_right_testicular_vein)
- female-only present: none
- surface patches: mammary_region_skin (zan_skin_mammary_region_l, zan_skin_mammary_region_r)
- wrong-sex structures: none

### Base · Male - Q233 pages (2966 structures)
- male-only present: testis (zan_testis_l, zan_testis_r); epididymis (zan_epididymis_l, zan_epididymis_r); ductus_deferens (zan_ductus_deferens_l, zan_ductus_deferens_r); seminal_vesicle (zan_seminal_gland_l, zan_seminal_gland_r); prostate (zan_prostate); penis_corpora_glans (zan_corpus_cavernosum_of_penis, zan_corpus_spongiosum_of_penis, zan_deep_artery_of_penis_l, zan_deep_artery_of_penis_r, zan_deep_dorsal_vein_of_penis, zan_dorsal_artery_of_penis_l, zan_dorsal_artery_of_penis_r, zan_glans_penis, zan_superficial_dorsal_veins_of_penis); scrotum_urogenital_skin (zan_skin_urogenital_region_l, zan_skin_urogenital_region_r); ejaculatory_duct (zan_ejaculatory_duct_l, zan_ejaculatory_duct_r); male_urethra (zan_urethra); testicular_vessels (zan_left_testicular_vein, zan_right_testicular_vein)
- female-only present: none
- surface patches: mammary_region_skin (zan_skin_mammary_region_l, zan_skin_mammary_region_r)
- wrong-sex structures: none
  - testis: Z-Anatomy / BodyParts3D (one male-derived body), unadapted
  - epididymis: Z-Anatomy / BodyParts3D (one male-derived body), unadapted
  - ductus_deferens: Z-Anatomy / BodyParts3D (one male-derived body), unadapted
  - seminal_vesicle: Z-Anatomy / BodyParts3D (one male-derived body), unadapted
  - prostate: Z-Anatomy / BodyParts3D (one male-derived body), unadapted
  - penis_corpora_glans: Z-Anatomy / BodyParts3D (one male-derived body), unadapted
  - scrotum_urogenital_skin: Z-Anatomy / BodyParts3D (one male-derived body), unadapted
  - ejaculatory_duct: Z-Anatomy / BodyParts3D (one male-derived body), unadapted
  - male_urethra: Z-Anatomy / BodyParts3D (one male-derived body), unadapted
  - testicular_vessels: Z-Anatomy / BodyParts3D (one male-derived body), unadapted
- expected-but-absent (male): bulbourethral_gland, foreskin, spermatic_cord

### Base · Female - published sources (2940 structures)
- male-only present: none
- female-only present: none
- surface patches: mammary_region_skin (zan_skin_mammary_region_l, zan_skin_mammary_region_r); perineal_closure_skin (zan_skin_perineal_closure)
- wrong-sex structures: none

### Base · Female - Q233 pages (2945 structures)
- male-only present: none
- female-only present: uterus (uterus); ovary (ovary_l, ovary_r); uterine_tube (uterine_tube_l, uterine_tube_r)
- surface patches: mammary_region_skin (zan_skin_mammary_region_l, zan_skin_mammary_region_r); perineal_closure_skin (zan_skin_perineal_closure)
- wrong-sex structures: none
  - uterus: HRA reference organ of the SAME donor (Visible Human female, CC BY 4.0), registered on the page's pelvis (Q233): not measured here
  - ovary: HRA reference organ of the SAME donor (Visible Human female, CC BY 4.0), registered on the page's pelvis (Q233): not measured here
  - uterine_tube: HRA reference organ of the SAME donor (Visible Human female, CC BY 4.0), registered on the page's pelvis (Q233): not measured here
- expected-but-absent (female): cervix, clitoris, female_urethra, labia_majora, labia_minora, mammary_gland, mons_pubis, ovarian_vessels, uterine_ovarian_ligaments, vagina, vestibular_glands_bulb

### Combined · Male - published sources (2966 structures)
- male-only present: testis (zan_testis_l, zan_testis_r); epididymis (zan_epididymis_l, zan_epididymis_r); ductus_deferens (zan_ductus_deferens_l, zan_ductus_deferens_r); seminal_vesicle (zan_seminal_gland_l, zan_seminal_gland_r); prostate (zan_prostate); penis_corpora_glans (zan_corpus_cavernosum_of_penis, zan_corpus_spongiosum_of_penis, zan_deep_artery_of_penis_l, zan_deep_artery_of_penis_r, zan_deep_dorsal_vein_of_penis, zan_dorsal_artery_of_penis_l, zan_dorsal_artery_of_penis_r, zan_glans_penis, zan_superficial_dorsal_veins_of_penis); scrotum_urogenital_skin (zan_skin_urogenital_region_l, zan_skin_urogenital_region_r); ejaculatory_duct (zan_ejaculatory_duct_l, zan_ejaculatory_duct_r); male_urethra (zan_urethra); testicular_vessels (zan_left_testicular_vein, zan_right_testicular_vein)
- female-only present: none
- surface patches: mammary_region_skin (zan_skin_mammary_region_l, zan_skin_mammary_region_r)
- wrong-sex structures: none

### Combined · Male - Q233 pages (2966 structures)
- male-only present: testis (zan_testis_l, zan_testis_r); epididymis (zan_epididymis_l, zan_epididymis_r); ductus_deferens (zan_ductus_deferens_l, zan_ductus_deferens_r); seminal_vesicle (zan_seminal_gland_l, zan_seminal_gland_r); prostate (zan_prostate); penis_corpora_glans (zan_corpus_cavernosum_of_penis, zan_corpus_spongiosum_of_penis, zan_deep_artery_of_penis_l, zan_deep_artery_of_penis_r, zan_deep_dorsal_vein_of_penis, zan_dorsal_artery_of_penis_l, zan_dorsal_artery_of_penis_r, zan_glans_penis, zan_superficial_dorsal_veins_of_penis); scrotum_urogenital_skin (zan_skin_urogenital_region_l, zan_skin_urogenital_region_r); ejaculatory_duct (zan_ejaculatory_duct_l, zan_ejaculatory_duct_r); male_urethra (zan_urethra); testicular_vessels (zan_left_testicular_vein, zan_right_testicular_vein)
- female-only present: none
- surface patches: mammary_region_skin (zan_skin_mammary_region_l, zan_skin_mammary_region_r)
- wrong-sex structures: none
  - testis: Z-Anatomy male-derived structure fitted to the Visible Human male (estimate, not measured)
  - epididymis: Z-Anatomy male-derived structure fitted to the Visible Human male (estimate, not measured)
  - ductus_deferens: Z-Anatomy male-derived structure fitted to the Visible Human male (estimate, not measured)
  - seminal_vesicle: Z-Anatomy male-derived structure fitted to the Visible Human male (estimate, not measured)
  - prostate: Z-Anatomy male-derived structure fitted to the Visible Human male (estimate, not measured)
  - penis_corpora_glans: Z-Anatomy male-derived structure fitted to the Visible Human male (estimate, not measured)
  - scrotum_urogenital_skin: Z-Anatomy male-derived structure fitted to the Visible Human male (estimate, not measured)
  - ejaculatory_duct: Z-Anatomy male-derived structure fitted to the Visible Human male (estimate, not measured)
  - male_urethra: Z-Anatomy male-derived structure fitted to the Visible Human male (estimate, not measured)
  - testicular_vessels: Z-Anatomy male-derived structure fitted to the Visible Human male (estimate, not measured)
- expected-but-absent (male): bulbourethral_gland, foreskin, spermatic_cord

### Combined · Female - published sources (2942 structures)
- male-only present: none
- female-only present: none
- surface patches: mammary_region_skin (zan_skin_mammary_region_l, zan_skin_mammary_region_r); perineal_closure_skin (zan_skin_perineal_closure)
- wrong-sex structures: none

### Combined · Female - Q233 pages (2947 structures)
- male-only present: none
- female-only present: uterus (uterus); ovary (ovary_l, ovary_r); uterine_tube (uterine_tube_l, uterine_tube_r)
- surface patches: mammary_region_skin (zan_skin_mammary_region_l, zan_skin_mammary_region_r); perineal_closure_skin (zan_skin_perineal_closure)
- wrong-sex structures: none
  - uterus: HRA reference organ of the SAME donor (Visible Human female, CC BY 4.0), registered on the page's pelvis (Q233): not measured here
  - ovary: HRA reference organ of the SAME donor (Visible Human female, CC BY 4.0), registered on the page's pelvis (Q233): not measured here
  - uterine_tube: HRA reference organ of the SAME donor (Visible Human female, CC BY 4.0), registered on the page's pelvis (Q233): not measured here
- expected-but-absent (female): cervix, clitoris, female_urethra, labia_majora, labia_minora, mammary_gland, mons_pubis, ovarian_vessels, uterine_ovarian_ligaments, vagina, vestibular_glands_bulb

## (b) Skeletal / body dimorphism measured on the meshes

internal reference = the two real donors measured by the same code (VH male, VH female); NOT a population norm (n = 1 + 1)

| Measure | Imaging-based · Male | Imaging-based · Female | Base · Male | Base · Female | Combined · Male | Combined · Female | male ref | female ref | ref status |
|---|---|---|---|---|---|---|---|---|---|
| Subpubic angle (angle between the axes of the two ischiopubic rami, 3-D) [deg] | 70.7 (male) | 87.3 (female) | 57.2 (male) | 57.2 (male) | 60.7 (male) | 62.7 (male) | 68.6 +- 7.6 | 87.4 +- 6.5 | verified_abstract: PMID 32274246 (CT, cut-off 78.6 deg) |
| Transverse pelvic outlet (intertuberous distance) / bi-iliac breadth [ratio] | 0.369 (male) | 0.403 (female) | 0.321 (male) | 0.321 (male) | 0.327 (male) | 0.387 (ambiguous) | smaller | larger | direction_verified_no_number: PMID 24789357, 42793678 (transverse outlet among the most dimorphic) |
| Greater sciatic notch (hull-defect angle at the deepest point, lateral silhouette) [deg] | 80.3 (male) | 90.9 (female) | 62.4 (male) | 62.4 (male) | 64.7 (male) | 88.7 (female) | smaller / deeper | larger / wider | direction_verified_no_number: PMID 39623825, 34554326, 42793678 |
| Ischiopubic index (pubic length / ischial length x 100, from the femoral-head centre) [index] | 114.4 (male) | 124.2 (female) | 118.8 (ambiguous) | 118.8 (ambiguous) | 115.5 (male) | 136.2 (female) | lower | higher (Washburn) | recalled_unverified_direction: not found in a PubMed abstract this session (Washburn 1948 is not in PubMed) |
| Sacral index (breadth of the upper half / straight length x 100) [index] | 91.0 (male) | 105.8 (female) | 107.1 (female) | 107.1 (female) | 115.0 (female) | 112.1 (female) | lower | higher | direction_verified_no_number: PMID 37284374, 34964781 (caveat PMID 35385483: sacrum weakly dimorphic) |
| Sacral curvature index (depth of the anterior concavity / chord x 100) [index] | 14.1 (ambiguous) | 35.2 (ambiguous) | 35.3 (ambiguous) | 35.3 (ambiguous) | 34.2 (ambiguous) | 36.9 (ambiguous) | less curved | more curved (varies) | direction_verified_no_number: PMID 34964781 (differs by sex, no direction in the abstract) |
| Bi-iliac (maximum pelvic) breadth [mm] | 280.2 (ambiguous) | 296.2 (ambiguous) | 269.8 (ambiguous) | 269.8 (ambiguous) | 285.9 (ambiguous) | 290.4 (ambiguous) | n/a | n/a | not_used: size depends on the donor |
| Femoral head diameter (sphere fit, right) [mm] | 48.7 (ambiguous) | 47.2 (ambiguous) | 51.3 (ambiguous) | 51.3 (ambiguous) | 50.8 (ambiguous) | 45.8 (ambiguous) | larger (Korean males 48.5 +- 2.2; Indian CT males 43.0 +- 2.6) | smaller (no number read) | partly_verified_abstract: PMID 41492324, 37803256, 40547822, 42414653 |
| Femoral bicondylar breadth (distal 60 mm, widest transverse extent, right) [mm] | 91.4 (male) | 81.7 (female) | 84.5 (female) | 84.5 (female) | 89.5 (male) | 78.7 (female) | larger | smaller | recalled_unverified_direction: no number read in an abstract |
| Biacromial breadth / bi-iliac breadth (skeletal, scapular acromion extremes) [ratio] | 1.37 (male) | 1.106 (female) | 1.287 (male) | 1.287 (male) | 1.284 (male) | 1.09 (female) | larger | smaller | recalled_unverified_direction: no number read in an abstract |
| Q angle (ASIS - patella centre - tibial tuberosity, coronal projection of the bone landmarks) [deg] | right 7.8, left 1.8 (ambiguous) | right 36.0, left 14.1 (ambiguous) | right 0.7, left 0.7 (ambiguous) | right 0.7, left 0.7 (ambiguous) | right 2.5, left 8.3 (ambiguous) | right 37.2, left 27.6 (ambiguous) | 10.8-13.5 | 13.6-15.9 | verified_abstract: PMID 36713821, 32295725, 31194851 (difference only 2-3 deg) |
| Sternal length / width [mm] | length 195.8, width 68.2 (ambiguous) | length 165.2, width 54.2 (ambiguous) | length 119.3, width 49.3 (ambiguous) | length 119.3, width 49.3 (ambiguous) | length 107.7, width 44.4 (ambiguous) | length 95.0, width 39.1 (ambiguous) | longer | shorter | recalled_unverified_direction: none read |
| Breast: skin protrusion over the ribs at the breast level minus the sternal column [mm] | 69.9 (ambiguous) | 40.7 (ambiguous) | 59.6 (ambiguous) | 64.2 (ambiguous) | 53.5 (ambiguous) | 47.1 (ambiguous) | small | large | no_number: none |

Notes per measure and reliability are in the JSON (`pages.<page>.before_q233.measures[].note / reliability`). Core measures for the skeleton verdict: subpubic_angle, pelvic_outlet_transverse, greater_sciatic_notch, ischiopubic_index, shoulder_to_hip, bicondylar_breadth.

### Fat distribution (own pages)

her thigh fat fraction is more than twice his (49 vs 23 %), trunk 52 / 35 vs 45 / 28 %: a female (gynoid-leaning, obese) fat pattern; the Z pages have no body-composition evidence (generic Z-Anatomy soft tissue).

Evidence: data/derived/subject_anthropometrics.json (Q44, cryosection colour classes, same method on both donors). direction only: sex differences in android:gynoid fat and waist-hip ratio exist (PMID 18839131, 22797367); IDF WHR thresholds men 0.90 / women 0.85 are screening cut-offs, not means (PMID 36235677).

### Skull

Skull dimorphism (mastoid, glabella, mental eminence, orbital margin) was NOT scored: the skull meshes exist (own pages: cranium, mandible, temporal, zygomatic; Z pages: frontal, occipital, maxilla, temporal, zygomatic, mandible) but automatic landmarking on 7,500-vertex decimated shells is not reliable; qualitative review of renders is left to the owner.

## Q44 cross-sex transfers (what was carried between the two donors)

- own_f: `xfer_vhm2vhf_rhom` x2: rhomboid_minor_l, rhomboid_minor_r
- own_f: `xfer_vhm2vhf_sep_q215` x27: adductor_brevis_l, obturator_internus_r, semimembranosus_r, tensor_fasciae_latae_r, adductor_longus_l, adductor_magnus_r, biceps_femoris_l, biceps_femoris_r, gracilis_l, rectus_femoris_r, sartorius_r, semitendinosus_l ...
- own_f: `xfer_vhm2vhf_sep_contfix` x6: extensor_digitorum_longus_r, extensor_hallucis_longus_r, gastrocnemius_r, gracilis_r, popliteus_l, tibialis_anterior_l
- own_f: `xfer_vhm2vhf_sep` x20: fibularis_longus_l, fibularis_longus_r, flexor_digitorum_longus_r, flexor_hallucis_longus_l, flexor_hallucis_longus_r, gastrocnemius_l, gemellus_inferior_l, obturator_externus_l, obturator_externus_r, pectineus_l, pectineus_r, plantaris_r ...
- own_f: `xfer_vhm2vhf` x26: ankle_articular_cartilage_l, ankle_articular_cartilage_r, anterior_cruciate_ligament_l, anterior_cruciate_ligament_r, coccyx, coracobrachialis_l, coracobrachialis_r, fibular_collateral_ligament_l, fibular_collateral_ligament_r, gemellus_inferior_r, gemellus_superior_l, gemellus_superior_r ...
- own_m: `xfer_vhf2vhm_neck_contfix_mesh` x3: semispinalis_capitis_l, semispinalis_cervicis_l, obliquus_capitis_inferior_l
- own_m: `xfer_vhf2vhm` x19: digastric_l, digastric_r, internal_carotid_a_l, internal_carotid_a_r, internal_jugular_v_l, internal_jugular_v_r, superior_rectus_l, superior_rectus_r, inferior_oblique_r, inferior_rectus_l, inferior_rectus_r, lateral_rectus_l ...
- own_m: `xfer_vhf2vhm_neck` x19: semispinalis_capitis_r, semispinalis_cervicis_r, rectus_capitis_posterior_minor_r, rectus_capitis_posterior_major_r, obliquus_capitis_inferior_r, obliquus_capitis_superior_r, longus_colli_r, longus_capitis_r, rectus_capitis_posterior_minor_l, rectus_capitis_posterior_major_l, obliquus_capitis_superior_l, longus_colli_l ...
- own_m: `xfer_vhf2vhm_vessels` x2: brachiocephalic_trunk_r, common_carotid_a_r

Sex-specific review:

- own_f: `coccyx` (REMOVED in Q233); `hip_bone_l_zfill203s` (kept (a seam fill of 4 mm, badged; replacing needs her missing crest evidence)); `levator_ani_*_zfill203s / zfill212, coccygeus_*_zfill203s` (kept, badged)
- own_m: `(none)` (his transfers come from HER body (xfer_vhf2vhm*: digastric, internal carotid / jugular, extra-ocular and neck muscles, semispinalis...): none sex-specific)

## Z-Anatomy / BodyParts3D female search (owner: 'Z-Anatomy HAS a female model')

NO, in everything reachable from the sandbox: Z-Anatomy and BodyParts3D publish one male-derived body and no female reproductive organ. The Z-Anatomy repository's own TO-DO file lists 'CREATE A FEMALE HUMAN MODEL' under MIDTERM goals (not done).

- github.com/Z-Anatomy/models-of-human-anatomy, HEAD e214005da8dc0a226176165f0a4d4e32f2155e0f (2026-10-13), shallow clone through the session git proxy (LFS skipped, nothing needed from LFS): files: Z-Anatomy.zip (87 MB, application template with Startup.blend, Blender 3.5, 306 MB), Z-Biomechanics.7z, TA2.csv (terminology only), Readme.md, 'TO DO List'. Startup.blend parsed block by block (7,184 objects, 2,910 meshes, 188 materials): NO object named uterus, ovary, uterine tube, vagina, vulva, labium, clitoris, vestibular gland, mons pubis, mammary gland / breast, hymen or cervix. Male-only objects present: testis, epididymis, ductus deferens, ejaculatory duct, seminal gland, prostate, corpora cavernosa / spongiosum, glans penis, penis, urethra, testicular vessels. Only 'Mammary region' / 'Inframammary region' skin patches (male contour) exist. The female terms appear only in the label / definition database (TA2 terminology), with no mesh.
- github.com/LluisV/Z-Anatomy branches PC-Version 6c7f9016 (the pinned source of all Z pages, Q186 inventory of 7,013 objects in 9 FBX) and Mobile-Version 7ad7758 (2022, VisceralSystem25.fbx etc., 4,682 files shallow clone): same male organs only; no female organ object in any FBX (strings of every FBX scanned: VisceralSystem25.fbx lists penis, testis, epididymis, ductus deferens, seminal gland, prostate).
- BodyParts3D parts list (github.com/Kevin-Mattheus-Moerman/BodyParts3D, assets/BodyParts3D_data/parts_list_e.txt, 1,894 files listed) and Zenodo 22727173 / 4953712: parts list: testis, epididymis, seminal vesicle, prostate, penis (+ corpora, glans), scrotum; NO uterus, ovary, uterine tube, vagina, vulva, breast. One body (the male 'TARO' MRI set).
- z-anatomy.com (web atlas / app), api.github.com, dbarchive.biosciencedbc.jp, lifesciencedb.jp, www.z-anatomy.com: blocked by the egress proxy (CONNECT 403) or not served: whether the live web app carries a female model could NOT be checked here
- Zenodo search (reachable): visible human female organs, female pelvis uterus ovary, BodyParts3D female, Z-Anatomy: no female organ mesh set (Zenodo 15882019 = Visible Human MALE organs; 11047831 = male-derived torso organs)
- HuBMAP Human Reference Atlas 3D Reference Object Library (github.com/hubmapconsortium/ccf-releases, commit b036a91a, public, served by the git proxy; the cdn.humanatlas.io host stays blocked): FOUND: Visible Human FEMALE reference organs, CC BY 4.0: VH_F_Uterus, VH_F_Ovary_L/R, VH_F_Fallopian_Tube_L/R, VH_F_Urinary_Bladder, VH_F_Ureter_L/R, VH_F_Pelvis (v1.3, one body frame), mammary glands 3d-vh-f-mammary-gland-l/r (v1.3; sculpted from atlases, NOT from the donor: not used), VH_F_Skin; no vagina / vulva / labia / clitoris. Used for the uterus, ovaries, tubes (third_party/hra_vh_f).

What the owner would need to provide: If a Z-Anatomy female model exists, the exact file is needed: an export (FBX / OBJ / .blend) of that female body or of its female genital collection, or the release URL (the live atlas https://www.z-anatomy.com/ and the Z-Anatomy/The-app repository are not reachable from the sandbox; The-app answers 'not found' to anonymous git). For a vagina / vulva / clitoris / labia, any CC BY / CC BY-SA mesh set of the female external genitalia + vagina would do.

## (c) Declared claims

- **hub viewer/atlas_hub.html, 'Base · Female'**: "No open female atlas exists to download: Z-Anatomy and BodyParts3D ship one male-derived body. This is that body in its own frame with the male-only organs removed. No female organs are shown and none are invented; nothing is fitted." -> accurate before Q233 about the source; the NAME 'Base · Female' still overstates (the skeleton, chest skin and proportions are male-derived, measured below); the 'no female organs' sentence is OUTDATED after Q233 (HRA uterus / ovaries / tubes added). Fix: page title, h1 and sources panel rewritten (data / builder wording, not template code); hub text for the owner to update: see replacement text in PROJECT_STATE Q233
- **hub viewer/atlas_hub.html, 'Combined · Female'**: "The Z-Anatomy body fitted onto the Visible Human female's own skeleton, bone by bone. ... Male-only organs are left out." -> true but incomplete: it does not say that the shapes are male-derived (subpubic angle 62.7 deg = male range) and that there was no female organ. Fix: page wording now says it; hub text to update
- **hub, 'Imaging-based · Female'**: "Rebuilt from the Visible Human female's CT and cryosections, with her own bladder and rectum." -> accurate; before Q233 she had NO uterus / ovaries / tubes and a male coccyx transferred from the male body (Q44). Fix: uterus, ovaries, tubes added (same-donor HRA organs), male coccyx removed
- **Combined female page, sources panel (builder VHF_WORDING)**: "No female reproductive organs are shown: Z-Anatomy's reproductive organs are male and her own scans carry no uterus or ovary label, so nothing was invented." -> accurate before Q233; replaced. Fix: builder wording VHF_WORDING
- **Base female page, sources panel (NATIVE_FEMALE_WORDING) + stat line**: "The source has no female body ... This page is the generic Z-Anatomy body ... No female reproductive organs are shown and none were invented ... body proportions, breasts and pelvis are the source's." -> accurate and already honest about the body; incomplete about measured dimorphism; replaced. Fix: builder wording NATIVE_FEMALE_WORDING, name 'Base · Female (male-derived body)' in scripts/set_titles_q231.py
- **Combined female page, manifest data**: "'female_pelvic_organs': 'none found -- no label ... exists' (Q168 report)" -> accurate about HER labels; the page now carries HRA organs instead. Fix: none needed (history record)

## Fixes applied in Q233

- **Imaging-based · Female**: ADDED uterus (with cervix), ovary L / R, uterine tube L / R (HuBMAP HRA 3D reference organs of the SAME donor (Visible Human female), CC BY 4.0, registered on her own CT pelvis: scale x0.95043, surface residual median 1.24 mm (p90 3.53))
- **Imaging-based · Female**: REMOVED the male coccyx (xfer_vhm2vhf, Q44) (her own coccyx is in her CT sacrum mesh; card note added to the sacrum)
- **Combined · Female**: ADDED the same five organs in her coordinates (her frame) (HRA same-donor organs, same transform as the Imaging-based female)
- **Base · Female**: ADDED the same organs registered on the Z-Anatomy pelvis; renamed 'Base · Female (male-derived body)'; wording and card notes say plainly that the body is male-derived ()
- **Imaging-based · Male**: ADDED the male genital organs his scans do not give (testes, epididymides, deferent ducts, seminal vesicles, penis corpora + glans, male urethra, ejaculatory ducts) as badged Z-Anatomy fills (Z-Anatomy male fitted to him (Combined · Male page, his frame), inside his CT skin, out of his bones and pelvic organs)

## Cannot be fixed honestly

- Vagina, vulva (labia majora / minora), clitoris, vestibular glands / bulbs, mons pubis, female urethra differences, ligaments of the uterus / ovary, ovarian vessels: no open mesh source reached (not in Z-Anatomy, BodyParts3D, the HRA set); her own cryosection photographs show the vaginal and urethral walls and the vestibular erectile tissue as one dark mass (mappings/vhf_pelvic_floor_labels.json 'perineal_other') that cannot be separated at 1 mm. Not built, not invented.
- Breasts: the Z-Anatomy chest skin is the male contour (all three Z female-side pages); the HRA mammary glands are sculpted from atlas drawings (not from the donor) and were not used; her own CT skin carries her breast contour only on the Imaging-based female page.
- Z-Anatomy-derived skeletons (Base female, Combined female) keep the male-derived pelvis / sacrum / skull shape: Combined female's bones follow hers within ~2 mm median but its subpubic angle reads 62.7 deg (male range) against her 87.3 deg. Replacing those bones with her own would break the fitted ligament / muscle attachments: not done.
- Imaging-based male: scrotal / penile SKIN comes from his CT skin (present); his testes etc. are Z fills, not measured; seminal vesicles are not separable on his frozen CT.

## Limits of the measurements

- Skeletal measurements use simple geometric landmark rules on decimated meshes of supine cadavers (not hand-placed osteometric landmarks): trust the sign of each difference, not the last digits.
- Only the subpubic angle has a verified numeric reference (PMID 32274246); the other measures have a verified DIRECTION (PubMed abstracts) and are scored against the two real donors measured identically (n = 1 + 1, not a norm).
- Skull dimorphism (mastoid, glabella, mental eminence, orbital margin) was NOT scored: the skull meshes exist (own pages: cranium, mandible, temporal, zygomatic; Z pages: frontal, occipital, maxilla, temporal, zygomatic, mandible) but automatic landmarking on 7,500-vertex decimated shells is not reliable; qualitative review of renders is left to the owner.
- Obturator foramen shape was not measured (the foramen is a thin hole in a decimated shell; two attempts gave no stable outline). The pelvic inlet transverse / AP ratio was attempted by sectioning the P-SU plane and failed (the plane cuts the iliac blades, not the arcuate lines): reported as not measured instead of a wrong number.
- Breast volume and gynoid / android fat could not be measured from the skin envelope (supine cadavers with arms on the trunk; no mammary gland modelled): the only fat-distribution evidence is the cryosection fat fractions of Q44 (below).

## References (PubMed abstracts read)

- PMID 32274246 doi:10.5115/acb.19.135: Mohd Ali SH et al. Anat Cell Biol 2020;53(1):27-35 - CT-based 3-D pelvis, 50 male + 50 female Malaysian adults: subpubic angle male 68.6 +- 7.6 deg, female 87.4 +- 6.5 deg; best cut-off 78.6 deg (94 % accuracy) (used for: subpubic angle)
- PMID 24789357 doi:10.1007/s00414-014-0999-8: Franklin D et al. Int J Legal Med 2014;128(5):861-72 - MSCT 200 + 200 Western Australian adults; transverse pelvic outlet and subpubic angle contribute most to sex discrimination; no numbers in the abstract (used for: pelvic outlet, subpubic angle)
- PMID 42793678 doi:10.3390/diagnostics16182893: Karaman G et al. Diagnostics 2026;16(18) - CT 101 M + 100 F: 13 of 14 pelvic measures differ by sex; most informative: acetabular width, acetabular height, subpubic angle, ischial length, transverse pelvic outlet, angle of the greater sciatic notch; no numbers in the abstract (used for: which pelvic measures discriminate)
- PMID 39623825 doi:10.55519/JAMC-03-13148: Jadoon OK et al. J Ayub Med Coll Abbottabad 2024;36(3):514-7 - 70 dry pelvic bones: notch width, anterior segment and POSTERIOR ANGLE greater in females; depth, posterior segment and anterior angle greater in males; no numbers in the abstract (used for: greater sciatic notch)
- PMID 34554326 doi:10.1007/s00414-021-02700-1: Knecht S et al. Int J Legal Med 2021;135(6):2603-13 - 60 coxal bones; accuracy 0.92-0.97; the posterior angle with the deepest point of the notch as apex (A2) is in all models; no numbers in the abstract (used for: greater sciatic notch)
- PMID 37284374 doi:10.7759/cureus.38629: Saluja S et al. Cureus 2023;15(5):e38629 - 110 dry sacra: sacral length higher in males, SACRAL INDEX higher in females (p < 0.001; AUC 0.994); no numbers in the abstract (used for: sacral index)
- PMID 34964781 doi:10.1097/MD.0000000000027955: Triwidodo A et al. Medicine 2021;100(47):e27955 - CT 150 M + 150 F Indonesian adults: sacrum larger in males; sacral index, curvature index and corporo-basal index differ by sex (P < .001); lumbar lordosis greater in females (used for: sacrum)
- PMID 35385483 doi:10.1371/journal.pone.0264770: Krenn VA et al. PLoS One 2022;17(4):e0264770 - 164 modern humans: geometric-morphometric sex classification 72 %, anteroposterior corpus depth best linear parameter (83 %); sacral sex variation 'surprisingly low' (used for: caveat: sacrum is weakly dimorphic)
- PMID 37803256 doi:10.1186/s12877-023-04254-w: Jiawei L et al. BMC Geriatr 2023;23:632 - CT angiography, 236 older patients (Inner Mongolia): femoral head diameter and femoral offset larger in males than females in every age group; no numbers in the abstract (used for: femoral head diameter)
- PMID 40547822 doi:10.2147/TCRM.S521755: Yang TJ, Qian W. Ther Clin Risk Manag 2025;21:905-16 - CT of 247 patients: females have smaller femoral head diameter, neck length, offset; larger neck-shaft angle; no numbers in the abstract (used for: femoral head diameter)
- PMID 41492324 doi:10.1016/j.jor.2025.12.005: Sudhan S R et al. J Orthop 2025;73:116-27 - systematic review: femoral head diameter in males ranges from 31.1 +- 2.7 mm (Brazilian) to 48.50 +- 2.23 mm (Korean); Indian CT males 43.0 +- 2.6 mm; sex dimorphism < 2 % in the Brazilian series: absolute values are population dependent (used for: femoral head diameter: population dependence)
- PMID 42414653 doi:10.1007/s00414-026-03902-1: Wasterlain SN et al. Int J Legal Med 2026;140(6):4473-81 - 202 skeletons (Coimbra): the femoral vertical head diameter is the best single discriminator (89.8 % accuracy); no numbers in the abstract (used for: femoral head diameter)
- PMID 36713821 doi:10.7759/cureus.34224: Shantanu K et al. Cureus 2023;15(1):e34224 - 100 healthy adults: Q angle male 11.14 +- 1.9 (R) / 10.84 +- 1.86 (L) deg, female 13.68 +- 1.87 / 13.61 +- 2.04 deg (used for: Q angle)
- PMID 32295725 doi:10.1016/j.knee.2020.03.001: Merchant AC et al. Knee 2020;27(3):934-9 - 57 adults, standardized goniometer protocol: Q angle male 13.5 deg, female 15.9 deg (the 2.4 deg difference attributed to height) (used for: Q angle)
- PMID 31194851 doi:10.1371/journal.pone.0218387: Khasawneh RR et al. PLoS One 2019;14(6):e0218387 - 500 young Arab adults, upright weight-bearing: Q angle greater in women; correlated with femoral condylar distance; no numbers in the abstract (used for: Q angle)
- PMID 36235677 doi:10.3390/nu14194024: Dang AK et al. Nutrients 2022;14(19):4024 - 4701 Vietnamese adults: IDF-criteria WHR thresholds men 0.90, women 0.85 (a metabolic-syndrome screening cut-off, NOT a population mean) (used for: waist-hip ratio, sex-specific thresholds)
- PMID 18839131 doi:10.1007/s00125-008-1163-0: Zillikens MC et al. Diabetologia 2008;51(12):2233-41 - 2506 people, DXA: sex-specific genetic effects on android:gynoid fat ratio and waist-hip ratio ('well-known sex differences in body composition'); no sex means in the abstract (used for: fat distribution)
- PMID 22797367 doi:10.1159/000339981: Hodge S et al. Obes Facts 2012;5(3):399-407 - DXA android, gynoid and total fat, WHR; sex differences in how fat distribution relates to serotonin; no sex means in the abstract (used for: android / gynoid fat by DXA)
- PMID 18197593 doi:10.1002/uog.5241: Sokalska A, Valentin L. Ultrasound Obstet Gynecol 2008;31(2):210-7 - uterine AP diameter -22 % and ovarian volumes -45 % / -20 % (median) from 2 y before to 2 y after menopause; no absolute volumes in the abstract (used for: uterus / ovary size after menopause)
- PMID 11428180: Bar-Hava I et al. Climacteric 2001;4(2):160-5 - 753 postmenopausal women: negative correlation of menopausal age with uterine volume and ovarian area; no absolute volumes in the abstract (used for: uterus / ovary size after menopause)
