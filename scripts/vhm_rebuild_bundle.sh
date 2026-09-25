#!/bin/bash
# Rebuild the Visible Human MALE viewer bundle from what the repository holds, after a container reset wiped build/.
# His DU lower-limb STLs cannot be re-downloaded (hosts denied by the network policy) and his cryosection skin is not
# stored, so the source is the bundle recovered from his published page (data/derived/viewer_bundles/vhm_v25,
# decimated meshes) unpacked into per-subject folders, plus: his CT feet block for the LEFT metatarsals/phalanges
# (the DU left foot files metatarsal heads under phalanges) and the structures transferred from the female
# (head/neck pieces and the orbit muscles his frozen CT segmented at a fraction of their size). Idempotent.
set -u; cd /home/user/NMSK_Atlas; T=data/ct_sources/task_outputs; B=data/derived/viewer_bundles/vhm_v25; mkdir -p build/vh
# the seven tarsal pieces the bundle carries as tarsals_r/l are named (talus, calcaneus, ...) by scripts/transfer/name_tarsal_pieces.py
[ -f mappings/subjects/vhm_both_piece_names.json ] || python3 scripts/transfer/name_tarsal_pieces.py $B -o mappings/subjects/vhm_both_piece_names.json | tail -1
# subjects that have their own volume in the repo (foot, arm compartments v2, neck) are NEVER taken from the bundle:
# 2026-09-14 the bundle copy silently overwrote the v2 arm compartments (biceps 475 vs 386 cm3) because the v2.done marker survived
[ -f build/vh/vhm_both/manifest.json ] || python3 scripts/transfer/bundle_to_subjects.py $B --out build/vh --label "recovered from the published male viewer (Version 25)" --rename mappings/subjects/vhm_both_piece_names.json --skip ct_vhm_foot ct_vhm_armm ct_vhm_neck | tail -1
if ! grep -q vhm_foot_bones build/vh/ct_vhm_foot/manifest.json 2>/dev/null; then
  cp mappings/subjects/ct_vhm_foot_volume_mapping.json build/vh/
  python3 scripts/ingest_volume_geometry.py convert $T/vhm_foot_bones.nii.gz --labels vhm_foot --subject ct_vhm_foot --origin='-8.755,-202.476,5.677' --smooth 1.0 2>&1 | grep -E "wrote|Error|Trace"
fi
if [ ! -f build/vh/xfer_vhf2vhm/manifest.json ]; then
  [ -f build/viewer_f/bundle.json ] || { echo "female bundle absent: run scripts/cryo/vhf_rebuild_bundle.sh first"; exit 1; }
  python3 scripts/transfer/cross_subject_transfer.py --direction f2m --male-html $B --female-bundle build/viewer_f \
    --ids digastric_l digastric_r internal_carotid_a_l internal_carotid_a_r internal_jugular_v_l internal_jugular_v_r superior_rectus_l superior_rectus_r inferior_oblique_r inferior_rectus_l inferior_rectus_r lateral_rectus_l lateral_rectus_r levator_palpebrae_superioris_r levator_palpebrae_superioris_l medial_rectus_r optic_n superior_oblique_l superior_oblique_r \
    -o build/vh/xfer_vhf2vhm --report data/derived/transfer_report_vhf2vhm.json 2>&1 | head -1 | cut -c1-160
fi
# his upper-arm compartments v2 (scripts/cryo/vhm_arm_muscles_v2.py, label volume in the repo) replace the recovered ct_vhm_armm
if [ -f $T/vhm_arm_muscles_cryo_v2.nii.gz ] && ! grep -q vhm_arm_muscles_cryo_v2 build/vh/ct_vhm_armm/manifest.json 2>/dev/null; then
  rm -rf build/vh/ct_vhm_armm; cp mappings/subjects/ct_vhm_armm_volume_mapping.json build/vh/
  python3 scripts/ingest_volume_geometry.py convert $T/vhm_arm_muscles_cryo_v2.nii.gz --labels vhm_arm_muscles --subject ct_vhm_armm --origin='-6.035,-895.476,4.787' --smooth 1.0 2>&1 | grep -E "wrote|Error|Trace" && touch build/vh/ct_vhm_armm/v2.done
fi
# ct_vhm_neck from his own volume (not the recovered bundle): the pharyngeal constrictors are split at the midline (2026-09-14)
grep -q constrictor_r build/vh/ct_vhm_neck/manifest.json 2>/dev/null || { cp mappings/subjects/ct_vhm_neck_volume_mapping.json build/vh/; rm -rf build/vh/ct_vhm_neck
  python3 scripts/ingest_volume_geometry.py convert $T/vhm_headneck_muscles_merged.nii.gz --labels totalsegmentator_headneck_muscles --subject ct_vhm_neck --origin='-6.035,-895.476,4.787' --smooth 1.0 2>&1 | grep -E "wrote|Error|Trace"; }
# shoulder girdle split (Q62): infraspinatus / teres minor / teres major / rhomboid major + minor by rule from his cuff and rhomboid labels; listed BEFORE ct_vhm_cuff and ct_vhm_pmr
if [ -f $T/vhm_shoulder_split_cryo.nii.gz ] && ! grep -q vhm_shoulder_split build/vh/ct_vhm_shsp/manifest.json 2>/dev/null; then
  cp mappings/subjects/ct_vhm_shsp_volume_mapping.json build/vh/; rm -rf build/vh/ct_vhm_shsp
  python3 scripts/ingest_volume_geometry.py convert $T/vhm_shoulder_split_cryo.nii.gz --labels vhm_shoulder_split --subject ct_vhm_shsp --origin='-6.035,-895.476,4.787' --smooth 1.0 2>&1 | grep -E "wrote|Error|Trace"
fi
# Q62 step 1: his right forearm from the full-resolution crops (scripts/cryo/vhm_forearm_muscles_from_cryo.py); only FDS, FDP, APL shipped by name
if [ -f $T/vhm_forearm_muscles_cryo.nii.gz ] && ! grep -q vhm_forearm_muscles build/vh/ct_vhm_forearm/manifest.json 2>/dev/null; then
  cp mappings/subjects/ct_vhm_forearm_volume_mapping.json build/vh/; rm -rf build/vh/ct_vhm_forearm
  python3 scripts/ingest_volume_geometry.py convert $T/vhm_forearm_muscles_cryo.nii.gz --labels vhm_forearm_muscles --subject ct_vhm_forearm --origin='-6.035,-895.476,4.787' --smooth 1.0 2>&1 | grep -E "wrote|Error|Trace"
fi
# Q62 step 6: diaphragm + intercostal sheets from his total-task labels (scripts/trunk_wall_from_ct.py --body m; geometric rule only, his frozen HU overlap)
if [ -f $T/vhm_trunk_wall.nii.gz ] && ! grep -q vhm_trunk_wall build/vh/ct_vhm_twall/manifest.json 2>/dev/null; then
  cp mappings/subjects/ct_vhm_twall_volume_mapping.json build/vh/; rm -rf build/vh/ct_vhm_twall
  python3 scripts/ingest_volume_geometry.py convert $T/vhm_trunk_wall.nii.gz --labels vhm_trunk_wall --subject ct_vhm_twall --origin='-6.035,-895.476,4.787' --smooth 1.0 2>&1 | grep -E "wrote|Error|Trace"
fi
# Q62: her deep-neck / suboccipital and floor-of-mouth muscles carried onto him (he has none of them; badged as transferred)
# Q91: genioglossus_r/l EXCLUDED here -- replaced by his own CT-derived version, ct_vhm_ggl below
# Q92: styloglossus_r/l ALSO EXCLUDED here -- replaced by his own CT-derived version, ct_vhm_sgl below
# (mylohyoid/geniohyoid/hyoglossus stay on the transfer -- Q92 found their rules need cryo photograph
# texture that his CT alone cannot supply; see scripts/cryo/vhm_styloglossus_from_ct.py's docstring)
if [ ! -f build/vh/xfer_vhf2vhm_neck/manifest.json ]; then
  [ -f build/viewer_f/bundle.json ] || { echo "female bundle absent: run scripts/cryo/vhf_rebuild_bundle.sh first"; exit 1; }
  IDS=$(python3 -c "import json;print(' '.join(s['atlas_id'] for f in ('ct_vhf_dneck','ct_vhf_hyoid') for s in json.load(open(f'build/vh/{f}/manifest.json'))['structures'] if s['atlas_id'] not in ('genioglossus_r','genioglossus_l','styloglossus_r','styloglossus_l')))")
  python3 scripts/transfer/cross_subject_transfer.py --direction f2m --male-html $B --female-bundle build/viewer_f \
    --ids $IDS -o build/vh/xfer_vhf2vhm_neck --report data/derived/transfer_report_vhf2vhm_neck.json 2>&1 | head -1 | cut -c1-160
fi
# Q91: genioglossus from his OWN CT tongue label, anchored on his mandibular symphysis midline (scripts/cryo/vhm_genioglossus_from_ct.py)
if [ -f $T/vhm_genioglossus_ct.nii.gz ] && ! grep -q vhm_genioglossus_ct build/vh/ct_vhm_ggl/manifest.json 2>/dev/null; then
  cp mappings/subjects/ct_vhm_ggl_volume_mapping.json build/vh/; rm -rf build/vh/ct_vhm_ggl
  python3 scripts/ingest_volume_geometry.py convert $T/vhm_genioglossus_ct.nii.gz --labels vhm_genioglossus_ct --subject ct_vhm_ggl --origin='-6.035,-895.476,4.787' --smooth 1.0 2>&1 | grep -E "wrote|Error|Trace"
fi
# Q92: styloglossus (intralingual portion only) from his OWN CT tongue label (scripts/cryo/vhm_styloglossus_from_ct.py)
if [ -f $T/vhm_styloglossus_ct.nii.gz ] && ! grep -q vhm_styloglossus_ct build/vh/ct_vhm_sgl/manifest.json 2>/dev/null; then
  cp mappings/subjects/ct_vhm_sgl_volume_mapping.json build/vh/; rm -rf build/vh/ct_vhm_sgl
  python3 scripts/ingest_volume_geometry.py convert $T/vhm_styloglossus_ct.nii.gz --labels vhm_styloglossus_ct --subject ct_vhm_sgl --origin='-6.035,-895.476,4.787' --smooth 1.0 2>&1 | grep -E "wrote|Error|Trace"
fi
# Q149: the abdominal wall volume was surfaced mirrored (cryo-order voxels, CT-direction affine);
# mirror it back onto the spine. Idempotent (manifest records mirror_x_fix).
[ -f build/vh/ct_vhm_abw/manifest.json ] && python3 scripts/mirror_subject_x.py build/vh/ct_vhm_abw --c 100.4 --note "Q149: cryo-order voxels under a CT-direction affine; labels correct, geometry mirrored"
# Q153: the 6 male ct_vhm_abw ids (rectus_abdominis_l/r, external_oblique_l/r,
# internal_oblique_l, transversus_abdominis_l) Q152b left UNRESOLVED, plus the
# stray top-slice strip on the left obliques (y~340-345, reaching x~-236..-241
# into the arm -- a rule artefact of the lateral-wall mask touching arm tissue
# on the top slice). NOT a voxel reconversion: `convert
# data/ct_sources/task_outputs/vhm_abdominal_wall_cryo.nii.gz --origin=
# '-6.035,-895.476,4.787'` (every other VHM cryo/CT subject's origin) + this
# script's own mirror above was tried directly and does NOT reproduce the
# shipped build/vh/ct_vhm_abw (~21% short on vertex count, mirrored X bbox
# [-61.6,257.4] vs the shipped [-241.1,208.1] -- Y/Z match exactly, so the repo
# copy of the source volume is not the exact bytes that built the shipped
# mesh); per this project's own standing rule (derive_origin: never guess an
# origin or borrow another subject's constant), no voxel-space fix is
# attempted. Applied in MESH SPACE only instead (scripts/apply_q153_abw_contfix.py,
# same drop_mesh_islands mechanism as the Q152b subjects above -- needs no
# origin, can only remove already-correctly-placed triangles). internal_oblique_r/
# transversus_abdominis_r are untouched (Q152 already diagnosed both ANATOMICAL).
# Listed BEFORE ct_vhm_abw below so it wins only these 6 ids.
[ -f build/vh/ct_vhm_abw/manifest.json ] && [ ! -f build/vh/ct_vhm_abw_contfix/manifest.json ] && python3 scripts/apply_q153_abw_contfix.py 2>&1 | tail -10
# Q147: forearm/hand/foot soft tissue (muscles, tendons, ligaments, retinacula) that his own
# imaging never covered, transferred from Z-Anatomy with a PER-BONE (radius vs ulna kept
# separate, carpus/tarsus block, never the broad multi-bone spatial blend Q142 used)
# registration onto his OWN bones (scripts/transfer/limb_per_bone_transfer.py); fills gaps
# only -- real ct_vhm_forearm/ct_vhm_arm etc. always win, this subject is listed LAST below.
# Reads the PRIOR build/viewer_m (this script's own previous output) for his bones/skin, the
# same self-referential pattern already used below for xfer_vhf2vhm/xfer_vhf2vhm_neck.
# 25.4mm median / 75.3mm max: centroid error validating this exact method on his own real
# ct_vhm_forearm muscles (flexor_digitorum_superficialis_r/flexor_digitorum_profundus_r/
# abductor_pollicis_longus_r), n=3 -- see PROJECT_STATE.md Q147 and data/derived/
# Q147_validation_male.json. NOTE: this idempotent check only ever fires once, from a state
# where build/viewer_m does not yet carry xfer_zan2vhm_limb -- re-running it by hand against an
# ALREADY-built build/viewer_m (e.g. only to change the badge text) silently ships 0 structures,
# because default_ids() sees every one of them as "already present" and skips them all; Q150 hit
# this rebuilding the badge with a max-error figure and worked around it with a one-off
# pre-transfer bundle (export_viewer_bundle.py on the SUBJ list below, minus this subject).
if [ ! -f build/vh/xfer_zan2vhm_limb/manifest.json ] && [ -f build/viewer_m/bundle.json ]; then
  python3 scripts/transfer/limb_per_bone_transfer.py --direction zan2m --male-html build/viewer_m \
    --badge-error-mm 25.4 --badge-max-error-mm 75.3 -o build/vh/xfer_zan2vhm_limb --report data/derived/transfer_report_zan2vhm_limb.json 2>&1 | tail -1 | cut -c1-200
fi
# Q155 (owner decision 2026-09-25): ship the Q151b photograph-gradient watershed refinement of
# his RIGHT forearm compartments even though it misses the 15mm/30mm ship bar, because it is
# clearly better than xfer_zan2vhm_limb's own raw Z-Anatomy transfer for these same ids (worst
# case 61.2mm median/91mm-class outliers on unrefined ids -> 19.9mm median/25.8mm max here) --
# each shipped id badged with this exact honest leave-one-out number (data/derived/
# Q151b_validation_male.json). Q112 gate: any refined id whose own main_frac < 0.98 is dropped by
# q155_finalize_photo_ship.py so xfer_zan2vhm_limb (listed below, still carrying every one of
# these ids) supplies it unrefined instead -- extensor_carpi_radialis_brevis_r/_longus_r and
# extensor_carpi_ulnaris_r failed this gate this run (0.96/0.76/0.42) and stay on Q147. Listed
# BEFORE xfer_zan2vhm_limb so it wins only the ids it actually ships. Needs his own re-acquired
# forearm cryosection photographs (SCRATCH/vh_cryo_m_forearm_q151, public-domain source imagery,
# never committed -- see .gitignore); silently skipped if that scratch dir is absent, same as
# this file's other real-imaging gates.
if [ -d SCRATCH/vh_cryo_m_forearm_q151 ] && [ -f build/vh/xfer_zan2vhm_limb/manifest.json ] && [ ! -f build/vh/xfer_zan2vhm_limb_photo/manifest.json ]; then
  python3 scripts/transfer/refine_transfer_photo_watershed.py --specimen m \
    --cryo-dir SCRATCH/vh_cryo_m_forearm_q151 \
    --volume $T/vhm_forearm_muscles_cryo.nii.gz \
    --labels mappings/vhm_forearm_muscles_labels.json \
    --mapping build/vh/ct_vhm_forearm_volume_mapping.json --origin='-6.035,-895.476,4.787' \
    --target build/viewer_m --xfer build/vh/xfer_zan2vhm_limb \
    --out build/vh/xfer_zan2vhm_limb_photo --report data/derived/Q155_ship_male_forearm.json 2>&1 | tail -3
  python3 scripts/transfer/q155_finalize_photo_ship.py build/vh/xfer_zan2vhm_limb_photo \
    --median 19.9 --max 25.8 --report data/derived/Q155_finalize_male_forearm.json 2>&1 | tail -6
fi
# Q150/Q150b: a forearm-compartment refinement onto his OWN segmented tissue was TRIED
# (scripts/transfer/refine_limb_transfer.py) but a lead review found the first cut's leave-one-
# out validation leaked ground truth (a held-out id was searched for inside its OWN already-
# known true label, scoring a fraudulent ~1mm median); the CORRECTED validation (neighbouring
# real labels folded into the open competitive region too, both specimens, both a "neighbor" and
# a stricter "whole_limb" variant -- data/derived/Q150_validation_male.json) measures median
# 20.9-21.8mm / max 21.8mm, over the 15mm median bar -- NOT shipped. xfer_zan2vhm_limb above (its
# badge now also discloses its own max error) stands as this specimen's forearm/hand/foot
# estimate, unchanged.
# Q116: coccygeus_l only, reconverted at --smooth 0.0 (ct_vhm_pfloor_fix); listed BEFORE
# ct_vhm_pfloor so it wins just this one atlas_id. Q152b: this had only a "use it if
# present" check, never a real build step -- on a truly fresh container (build/ wiped)
# it would silently never be produced at all. Real regeneration: his own known origin
# constant (used throughout this script, e.g. ct_vhm_shsp/ct_vhm_forearm/ct_vhm_neck
# above) verified to reproduce the already-shipped mesh to 0.000mm -- see PROJECT_STATE
# Q152b.
if [ -f mappings/subjects/ct_vhm_pfloor_fix_volume_mapping.json ] && ! grep -q coccygeus_l build/vh/ct_vhm_pfloor_fix/manifest.json 2>/dev/null; then
  cp mappings/subjects/ct_vhm_pfloor_fix_volume_mapping.json build/vh/
  python3 scripts/ingest_volume_geometry.py convert $T/vhm_pelvic_floor_cryo.nii.gz --labels vhm_pelvic_floor --subject ct_vhm_pfloor_fix --origin='-6.035,-895.476,4.787' --smooth 0.0 2>&1 | grep -E "wrote|Error|Trace"
fi
SUBJ=""; [ -f build/vh/ct_vhm_pfloor_fix/manifest.json ] && SUBJ="--subject ct_vhm_pfloor_fix"
# Q152: continuity repair on his OWN subjects (mesh-space island drops; his own arm/forearm/
# deltoid raw sources are one-piece so nothing of his needed a voxel-space gap bridge except
# where ct_vhm_armm itself did -- see apply_continuity_repairs_q152.py). His forearm/hand/foot
# transfer (xfer_zan2vhm_limb) and shared-with-her ids (via xfer_vhf2vhm/xfer_vhf2vhm_neck) are
# fixed at the FEMALE source instead (scripts/cryo/vhf_rebuild_bundle.sh) -- those two transfers
# must be regenerated against her already-fixed bundle for him to inherit the fix (this script's
# own idempotent check skips regenerating them if already present from before this task; run
# `rm -rf build/vh/xfer_vhf2vhm build/vh/xfer_vhf2vhm_neck` once before this script to force it).
[ -f build/vh/ct_vhf_dneck_contfix/manifest.json ] || python3 scripts/apply_continuity_repairs_q152.py 2>&1 | tail -30
# Q152b: 3 new mesh-space island drops from the resumed diagnosis sweep
# (infraspinatus/teres_major on his shoulder-girdle split, trapezius on his
# neck subject, diaphragm on his trunk wall) -- same pattern as the 4 above,
# listed BEFORE their own base subjects (ct_vhm_shsp/ct_vhm_neck/ct_vhm_twall,
# further below) so each wins only the ids it repairs.
for s in ct_vhm_armm_contfix_mesh ct_vhm_armm_contfix ct_vhm_delt_contfix_mesh ct_vhm_forearm_contfix_mesh \
         xfer_vhf2vhm_neck_contfix_mesh ct_vhm_shsp_contfix_mesh ct_vhm_neck_contfix_mesh \
         ct_vhm_twall_contfix_mesh ct_vhm_abw_contfix; do
  [ -f build/vh/$s/manifest.json ] && SUBJ="$SUBJ --subject $s"
done
for s in ct_vhm_foot vhm_both ct_vhm_arm ct_vhm_armm ct_vhm_forearm ct_vhm_shsp ct_vhm_delt ct_vhm_cuff ct_vhm_pmr ct_vhm_es ct_vhm_head ct_vhm ct_vhm_headm ct_vhm_neck ct_vhm_neckbv xfer_vhf2vhm xfer_vhf2vhm_neck ct_vhm_ggl ct_vhm_sgl ct_vhm_pfloor ct_vhm_orbit ct_vhm_abd ct_vhm_abw ct_vhm_twall ct_s1159_abd ct_s1159 ct_vhm_skin; do SUBJ="$SUBJ --subject $s"; done
[ -f build/vh/xfer_zan2vhm_limb_photo/manifest.json ] && SUBJ="$SUBJ --subject xfer_zan2vhm_limb_photo"
[ -f build/vh/xfer_zan2vhm_limb/manifest.json ] && SUBJ="$SUBJ --subject xfer_zan2vhm_limb"
python3 scripts/export_viewer_bundle.py $SUBJ -o build/viewer_m --budget-scale 0.9 2>&1 | grep -E "structures from|->|Error|Trace"
python3 scripts/build_viewer_html.py --bundle build/viewer_m -o build/viewer_m/atlas_viewer_male.html 2>&1 | tail -1
echo VHM_REBUILD_DONE
