# Q223 anatomy audit summary (READ-ONLY, 2026-10-12)

Six CURRENT pages, the Q198 / Q204 / Q209 audit code and thresholds UNCHANGED (`scripts/zanatomy/q223_*.py` only re-point the page table and add the 13-region split + exact re-checks). Nothing rebuilt, published, fixed. Reproducibility: the two bases reproduce Q209 exactly (75/125/160, 75/125/154).

## Headline per page (Q209 -> now)

| page | dir | verdict | junction audit major/mod/minor | whole-body structures major/mod/minor | elbow L / R |
|---|---|---|---|---|---|
| Own male | build/q221/viewer_m_hr (bundle build/viewer_m_hr_q217) | partly -> partly | 18/96/82 -> 15/82/86 | 28/146/60 -> 22/153/80 | DEFECT/DEFECT -> DEFECT/DEFECT |
| Own female | build/q222/viewer_f_hr (bundle build/viewer_f_hr_q216) | no -> partly | 19/162/122 -> 16/132/116 | 33/176/78 -> 29/167/88 | DEFECT/DEFECT -> DEFECT/DEFECT |
| Z fit his | build/q221/viewer_zan_vhm | no -> no | 49/123/148 -> 37/109/119 | 75/179/211 -> 51/132/219 | DEFECT/DEFECT -> DEFECT/DEFECT |
| Z fit hers | build/q222/viewer_zan_female | no -> partly | 30/101/178 -> 25/94/153 | 73/166/185 -> 49/133/188 | DEFECT/DEFECT -> DEFECT/DEFECT |
| Base female | build/q222/viewer_base_female | partly -> partly | 26/72/95 -> 26/72/95 | 75/125/154 -> 75/125/154 | OK/OK -> OK/OK |
| Base male | build/q222/viewer_zan_atlas | partly -> partly | 26/71/97 -> 26/71/97 | 75/125/160 -> 75/125/160 | OK/OK -> OK/OK |

## Structures with a major + moderate finding per region (Q209 -> now; 12-region scheme of Q204, ankle + foot merged)

| region | Own male | Own female | Z fit his | Z fit hers | Base female | Base male |
|---|---|---|---|---|---|---|
| head_neck | 37 -> 37 | 47 -> 47 | 61 -> 51 | 60 -> 55 | 60 -> 60 | 61 -> 61 |
| shoulder | 18 -> 18 | 16 -> 15 | 10 -> 3 | 12 -> 5 | 10 -> 10 | 11 -> 11 |
| arm_elbow_forearm | 25 -> 18 | 24 -> 23 | 29 -> 17 | 17 -> 10 | 20 -> 20 | 19 -> 19 |
| wrist_hand | 7 -> 11 | 9 -> 7 | 22 -> 9 | 15 -> 11 | 11 -> 11 | 11 -> 11 |
| thorax | 22 -> 22 | 22 -> 22 | 59 -> 49 | 55 -> 46 | 43 -> 43 | 43 -> 43 |
| abdomen_pelvis | 20 -> 20 | 22 -> 21 | 29 -> 21 | 23 -> 22 | 20 -> 20 | 19 -> 19 |
| hip | 2 -> 2 | 5 -> 4 | 4 -> 4 | 9 -> 5 | 10 -> 10 | 10 -> 10 |
| thigh | 26 -> 26 | 26 -> 21 | 7 -> 7 | 7 -> 4 | 6 -> 6 | 6 -> 6 |
| knee | 1 -> 1 | 1 -> 1 | 9 -> 8 | 7 -> 6 | 6 -> 6 | 6 -> 6 |
| leg | 12 -> 12 | 19 -> 16 | 11 -> 4 | 7 -> 4 | 4 -> 4 | 4 -> 4 |
| ankle_foot | 8 -> 8 | 18 -> 19 | 13 -> 10 | 27 -> 14 | 10 -> 10 | 10 -> 10 |

## Findings by type, severity major/moderate (all regions; per region in the JSON `regions_13[...].findings_by_type`)

| type | Own male | Own female | Z fit his | Z fit hers | Base female | Base male |
|---|---|---|---|---|---|---|
| gap | 4/11 | 2/13 | 26/48 | 25/50 | 29/46 | 29/46 |
| detached_piece | 7/12 | 7/14 | 6/8 | 2/10 | 6/6 | 6/6 |
| detached_end | 0/96 | 0/89 | 0/23 | 0/23 | 0/7 | 0/7 |
| flat_cut | 9/80 | 7/70 | 0/1 | 0/3 | 0/3 | 0/3 |
| outside_skin | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| bone_penetration | 0/6 | 0/0 | 0/12 | 0/6 | 0/0 | 0/0 |
| soft_in_bone | 3/19 | 13/28 | 19/25 | 22/24 | 40/52 | 40/52 |
| muscle_in_muscle | 0/16 | 0/38 | 0/28 | 0/34 | 0/22 | 0/22 |
| ragged_boundary | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |

Type key: gap = bone gap / tube gap / empty stretch; detached_piece = muscle or bone island; detached_end = muscle end off its bone; flat_cut = planar sawn face; soft_in_bone and bone_penetration use the Q204 2 mm solid (see artefacts); muscle_in_muscle = overlap > 40 / 60 %. 'Missing expected neighbours' per region: JSON `missing_expected_neighbours` (named Z muscles with no counterpart: own male 59, own female 51, mostly face / deep back / thumb; fits 0) and `junction_zone_absent_vs_z_reference`.

## Same table for the 13 regions: major/moderate structures now (head_neck, shoulder, arm, elbow, forearm, wrist_hand, thorax, abdomen_pelvis, hip, thigh, knee, leg, ankle_foot)

| region | Own male | Own female | Z fit his | Z fit hers | Base female | Base male |
|---|---|---|---|---|---|---|
| head_neck | 7/30 | 8/39 | 20/31 | 17/38 | 22/38 | 22/39 |
| shoulder | 4/14 | 1/14 | 0/3 | 1/4 | 7/3 | 7/4 |
| arm | 1/4 | 1/4 | 0/5 | 0/2 | 2/8 | 2/7 |
| elbow | 0/1 | 0/2 | 1/1 | 0/3 | 2/2 | 2/2 |
| forearm | 0/12 | 2/14 | 0/10 | 0/5 | 0/6 | 0/6 |
| wrist_hand | 0/11 | 1/6 | 2/7 | 0/11 | 4/7 | 4/7 |
| thorax | 1/21 | 4/18 | 16/33 | 17/29 | 22/21 | 22/21 |
| abdomen_pelvis | 3/17 | 1/20 | 2/19 | 2/20 | 6/14 | 6/13 |
| hip | 1/1 | 0/4 | 0/4 | 2/3 | 0/10 | 0/10 |
| thigh | 2/24 | 0/21 | 2/5 | 2/2 | 2/4 | 2/4 |
| knee | 0/1 | 0/1 | 4/4 | 4/2 | 4/2 | 4/2 |
| leg | 1/11 | 1/15 | 0/4 | 0/4 | 0/4 | 0/4 |
| ankle_foot | 2/6 | 10/9 | 4/6 | 4/10 | 4/6 | 4/6 |

## Top 15 defects (clinical / visual impact; effort S < 1 h, M ~ 1 session, L several)

1. **Own pages: veins not continuous (a stretch of the vessel is missing)** [real, severity 3, thigh / head_neck] own_m: femoral_v_r 62.0 mm, femoral_v_l 35.0 mm, internal_jugular_v_r 51.8 mm, internal_jugular_v_l 43.8 mm; own_f: internal_jugular_v_r 42.5 mm, internal_jugular_v_l 36.0 mm. Fix: bridge each vein across the gap with a centreline loft between the facing ends at the traced calibre, badged 'interpolated' (S). Render: `data/derived/Q223_render_1_own_male_femoral_vein_r.png`.
2. **Own male: thumb ray absent on both hands (no first metacarpal / phalanges; Z-fit thumb on his evidence lies 18-53 mm from the nearest own hand bone) and the thumb muscles are missing** [real, severity 3, wrist_hand] own_m: first_metacarpal+phalanges_l/r 18-53 mm from nearest own hand bone, abductor_pollicis_brevis_l/r absent, flexor_pollicis_brevis_l/r absent, opponens_pollicis_r absent; own_f: opponens_pollicis_l absent, flexor_pollicis_brevis_r absent. Fix: place the Q205 evidence-fitted thumb chain (his CT torso block shows it) and the Q213 thumb muscles on the own male page (M). Render: `data/derived/Q223_render_5_own_male_left_thumb.png`.
3. **Own pages: muscles sawn off flat at the CT block edges (166 flat-cut findings, 16 major)** [real, severity 3, thorax / shoulder / head_neck / abdomen_pelvis / arm / leg] own_f: longissimus_l 1308 mm2 z=-110.2, internal_oblique_r 833 mm2 x=147.4, iliocostalis_r 554 mm2, external_anal_sphincter 453 mm2 y=-38.2, semispinalis_capitis_l 450 mm2 y=589.8, infraspinatus_l 422 mm2; own_m: rhomboid_minor_l 1149 mm2 y=619.9, genioglossus_r 737 mm2 x=17.9, trapezius_r 585 mm2 z=-122.5, triceps_brachii_l 576 mm2 y=272.1 (left elbow), teres_major_r/l 544 / 422 mm2, deep_transverse_perineal_r/l 449 / 539 mm2 y=-38, tibialis_posterior_r 487 mm2 z=-54. Fix: complete each muscle across its plane with badged Z (Q200 method), perineal plane + shoulder girdle + erector spinae first (M-L). Render: `data/derived/Q223_render_2_own_female_longissimus_l_flat_cut.png`.
4. **Both Z-fitted pages: bones of the LEFT elbow interpenetrate (introduced by the fit; no elbow bone pair appears in the unfitted base penetration list); all four elbows still DEFECT** [real, severity 3, elbow] z_male_fit: ulna_l into humerus_l 9.4 mm (13 % of vertices > 1 mm), humerus_l / radius_l 6.7 mm, radius_l / ulna_l 6.2 / 5.0 mm; z_female_fit: humerus_l / radius_l 7.7 / 7.2 mm. Fix: re-seat radius + ulna on the humerus by joint congruency (trochlear notch on the trochlea), then re-carry the Q217 soft tissue with the twist map (M). Render: `data/derived/Q223_render_4_zfit_male_left_elbow_bones.png`.
5. **Own female: left wrist bones 9.0 mm apart (forearm -> carpals; Z completion not seated); her left humerus is cut flat at x=-239.8 (166 mm2)** [real, severity 3, wrist_hand / elbow] own_f: wrist_l bone gap 9.01 mm, humerus_l flat cut 166 mm2 x=-239.8. Fix: re-seat carpals on the distal radius / ulna (Q200 chain) and finish the humerus end (S-M).
6. **Own pages carry a grouped / superseded bone mesh on top of the individual bones** [real, severity 2, ankle_foot / wrist_hand] own_f: tarsals_r / tarsals_l vs calcaneus 14.9 / 14.1 mm, tarsals vs cuboid 11.4 / 10.0 mm, tarsals vs talus 8.1 / 6.4 mm, tarsals vs navicular 6.9 / 6.5 mm; own_m: carpals_l / carpals_r vs carpals_*_q212 6.2 / 5.8 mm, radius_/ulna_*_distal_q212 into carpals 5.8-5.9 mm, cuneiform_medial_l into metatarsals_l 7.2 mm. Fix: remove the superseded group mesh (tarsals_l/r, carpals_l/r) and re-run (S). Render: `data/derived/Q223_render_3_own_female_tarsals_group_mesh.png`.
7. **Own pages: muscles in two pieces (detached piece with 31-46 % of the surface)** [real, severity 3, head_neck / thorax / shoulder / arm / foot] own_m: longus_capitis_r 59.1 mm, 37 %, pectoralis_minor_r 57.2 mm, 36 %, longus_colli_r 35.0 mm, 34 %, trapezius_r 17.2 mm, 46 %, plantar_interossei_r 7.5 mm, 34 %; own_f: longus_colli_r 38.0 mm, 35 %, brachialis_l 29.1 mm, 31 %, geniohyoid_r 16.3 mm, 35 %, plantar_interossei_l/r 11.4 / 9.2 mm, extensor_carpi_ulnaris_r 5.8 mm, 46 %. Fix: loft-bridge the pieces (Q216 sartorius method) or merge them (S-M).
8. **Z-fitted pages: soft tissue not carried with the fitted bones at wrist / hand, shoulder, ankle** [real, severity 3, wrist_hand / shoulder / ankle_foot] z_male_fit: wrist L / R pairs touching in the base > 5 mm apart 76.5 % (max 87.0 mm) / 61.2 % (42.4 mm), zan_subscapular_artery_l/r vs humerus 29.0 / 34.0 mm frame offset, abductor_pollicis_brevis_l 29.8 mm frame offset, ankle L / R touching pairs > 5 mm 17.6 % / 9.1 % (26.9 mm); z_female_fit: wrist R / L touching pairs > 5 mm 57.3 % (30.5 mm) / 29.7 % (21.2 mm), zan_subscapular_artery_l/r 29.1 / 33.5 mm, cervico-thoracic touching pairs 21.4 % (20.9 mm). Fix: carry the wrist / hand ligaments, fascia, small muscles, vessels and the shoulder vessels with the bone-anchored field (Q199 / Q205 / Q217 method) (M).
9. **Own pages: muscle ends far from their bone (hamstrings, gastrocnemius; rectus abdominis ends at costal cartilage = partly artefact)** [real (hamstrings) / partly artefact, severity 2, thigh / leg / thorax] own_m: semimembranosus_r / _l 78.9 / 73.8 mm, semitendinosus_l 58.2 mm, gastrocnemius_l 48.6 mm, biceps_femoris_l 43.8 mm; own_f: rectus_abdominis_r 90.0 mm (cartilage), semimembranosus_r / _l 73.2 / 65.4 mm, semitendinosus_l / _r 57.6 / 53.9 mm. Fix: Q194 / Q214 bone-driven end pull + model the tendons (L).
10. **Muscle-in-muscle (muscles not tiled): right forearm of the own male, both female forearms, her Z fit, trunk** [real, severity 2, forearm / wrist_hand / shoulder / thorax] own_m: extensor_digiti_minimi_r 80 %, extensor_carpi_radialis_longus_r 76 %, internal_oblique_r 78 %; own_f: rhomboid_minor_r / _l 95 / 94 %, extensor_digiti_minimi_l 90 %, abductor_pollicis_longus_l 89 %; z_female_fit: flexor_digitorum_profundus_r 76 %, pronator_quadratus_r 77 %, supinator_l 69 %; z_male_fit: pectoralis_minor_r 79 %, semispinalis_thoracis_r / _l 75 / 74 %. Fix: apply the Q217 twist-map tiling + 1 mm separator to the remaining forearms (M).
11. **Z-fitted pages: patellae and floating ribs float off their bones (base < 6 mm)** [real (minor), severity 1, knee / thorax / head_neck / shoulder] z_male_fit: patella_l / _r 11.8 / 11.4 mm from femur, eleventh / twelfth ribs 8.9-10.8 mm, knee_l bone gap 3.6 mm; z_female_fit: patella_l / _r 9.0 / 11.4 mm, eleventh / twelfth ribs 8.3-11.6 mm, second_rib_l 6.4 mm from T2, cervico_thoracic / head_neck / left shoulder gap 4.5 / 3.6 / 4.0 mm. Fix: re-snap patellae, ribs 2/11/12 and the cervical / shoulder bones onto their joint surfaces (S).
12. **Own bones sawn flat at CT block edges (10 per page, 150-400 mm2)** [real (mostly hidden), severity 2, thorax / head_neck / thigh / shoulder] own_m: ribs_r 402 mm2 z=-96.1, ribs_l 225 mm2, scapula_r 229 mm2, femur_r 216 mm2 y=-457.5, cranium 155 mm2; own_f: ribs_r 399 mm2 z=-95.1, cranium 260 / 248 / 229 / 204 mm2, femur_l 235 mm2 y=24.2, femur_r 196 mm2, humerus_l 166 mm2. Fix: Z-badged bone completion or accept (hidden inside the body) (M).
13. **Z source defects (identical in the unfitted bases): vessels / nerves / muscles in separate pieces** [source quirk, severity 3, head_neck / thorax / foot] all four Z pages: zan_superficial_temporal_artery_l/r 54-57 mm, zan_apical_segmental_artery_of_right_lung 36-54 mm, spinalis_l/r 52-53 mm pieces, plantar_interossei 9-17 mm, posterior_femoral_cutaneous_n 133-148 mm (base 211), sural_n / lateral_femoral_cutaneous_n 12.5-17 mm. Fix: bridge / merge once in the base and re-fit, or accept as source (L / accept).
14. **Soft tissue really inside bone (exact 0.5 mm solid, >= 3 mm and >= 8 % of vertices > 1 mm)** [real (small), severity 2, forearm / foot / thorax] own_m: extensor_carpi_ulnaris_r 9.9 mm, flexor_digitorum_profundus_l 5.4 mm; own_f: fibularis_longus_l 6.4 mm, extensor_hallucis_brevis_r 6.4 mm, extensor_digitorum_brevis_r 6.0 mm, palmar_interossei_r 5.1 mm; z_male_fit: flexor_carpi_ulnaris_l 7.6 mm, extensor_hallucis_brevis_l 6.6 mm, zan_internal_intercostal_muscles_r 5.4 mm; z_female_fit: zan_internal_intercostal_muscles_l 5.2 mm, superficial_fibular_n_medial_dorsal_cutaneous_n_r 5.7 mm. Fix: push out of the bone with the Q213 field (S per page).
15. **Z-fitted skin patch borders: her feet (43 more border gaps than the base, max 23.1 vs 12.3 mm), source border gaps in both Z skins** [real (hers) / source, severity 1, ankle_foot / head_neck] z_female_fit: foot border gaps 2-20 mm 43 (base 0), max 18.9 mm; all Z pages: foot border vertices without a partner patch within 20 mm 272-274 (identical in base), head_neck border gaps 2-12 mm 78-79 (identical in base). Fix: weld the shared border vertices (Q202 / Q205 rule) (S).

## Audit artefacts, not defects

- **Q204 inside_bone 2 mm solid**: the 2 mm voxel solid is 20-40 % fatter than the bone meshes (Q217); exact 0.5 mm re-measure of every severity >= 2 inside_bone finding: Own male 20 of 22; Own female 35 of 41; Z fit his 35 of 44; Z fit hers 38 of 46; Base female 87 of 92; Base male 87 of 92 are artefact (exact < 3 mm or < 8 % of vertices > 1 mm)
- **Q204 bone-bone penetration at elbows / sinus**: own male left elbow humerus/radius 9.8 mm -> exact 0.0 mm, humerus/ulna 6.0 -> 1.0, radius/ulna 6.0 -> 1.4; sphenoid / sphenoid sinus 7.5-8.0 -> 1.0 mm (all pages); teeth in maxilla are sockets
- **flexed-pose elbow metrics (pose-unaware section planes)**: skin cross-section radius jumps 33.9-36.5 mm at t = 59-74 mm on all four Z-fit elbows (the section plane cuts the flexed forearm obliquely; the same as the Q205 neck step); own male left 'forearm leaves the hinge plane 43.6 deg'; own female ulna twist 56-58 deg (pronated forearm), her Z fit 42 deg; none is a tear
- **Z multi-piece vessels / nerves in elbow zones**: posterior_femoral_cutaneous_n (133-186 mm, base 211), radial_n 27-39 mm, muscular branches of median / ulnar n 37-62 mm are listed as 'continuity gaps' at the elbow: identical in the unfitted base (by design: separate branch pieces)
- **muscle end-off-bone for broad muscles / cartilage insertions**: rectus abdominis (costal cartilage), tensor fasciae latae (iliotibial tract), trapezius / latissimus PCA ends: Q204 caps these at moderate; 23 Z-fit and 74-78 own findings are mostly this
- **2 mm grid alignment**: the bone voxel grid is aligned to the bone bounding box: +-2 structures flip between runs (own male thigh 24 vs 26, leg 10 vs 12 compared with the Q217 run); compare only differences larger than 3
- **Q204 unfitted-base source quirks counted on the fitted pages**: 47 severity-3 and 84-92 severity-2 findings on each Z-fit page are also in the unfitted base (in_unfitted_base tag in the JSON)

## Elbow audit (Q198 code), L / R major/moderate/minor

| page | L | R | verdict |
|---|---|---|---|
| Own male | 1/2/2 | 0/9/4 | DEFECT/DEFECT (Q209 DEFECT/DEFECT) |
| Own female | 2/4/5 | 1/3/13 | DEFECT/DEFECT (Q209 DEFECT/DEFECT) |
| Z fit his | 1/9/4 | 1/5/12 | DEFECT/DEFECT (Q209 DEFECT/DEFECT) |
| Z fit hers | 1/5/8 | 2/4/10 | DEFECT/DEFECT (Q209 DEFECT/DEFECT) |
| Base female | 0/0/3 | 0/0/4 | OK/OK (Q209 OK/OK) |
| Base male | 0/0/3 | 0/0/4 | OK/OK (Q209 OK/OK) |

Skin: own skins sealed (0 open edges); forearm vs trunk skin crossing on the Z male fit 0 deep pairs (`Q223_forearm_trunk.json`; Q209 1083, Q210 0).

## Files
`data/derived/Q223_audit_{own_m,own_f,z_male_fit,z_female_fit,z_base_f,z_male}.json` (per page: 13 regions x types x severity, Q209 comparison, junction table, elbow statements, exact re-checks), `Q223_anatomy_audit.json` (full Q204-style aggregate), `Q223_exact_checks.json`, `Q223_top15.json`, `Q223_forearm_trunk.json`, `Q223_render_*.png` (5 worst places; full size in git-ignored `build/q223_renders/`). Page key -> dir: own_m build/q221/viewer_m_hr (bundle build/viewer_m_hr_q217); own_f build/q222/viewer_f_hr (bundle build/viewer_f_hr_q216); z_male_fit build/q221/viewer_zan_vhm; z_female_fit build/q222/viewer_zan_female; z_base_f build/q222/viewer_base_female; z_male build/q222/viewer_zan_atlas.
