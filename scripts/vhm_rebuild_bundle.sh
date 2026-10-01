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
# Q180: his right forearm muscles flooded from one seed per visible belly on 5 photograph sections (seeds placed by Claude,
# NOT an anatomist; owner review pending; scripts/cryo/vhm_forearm_seeded_q180.py). Only muscles passing its gate carry an
# atlas_id (main piece >= 0.95, seed-jitter Dice >= 0.8, volume 0.5-2x reference); badges stamped by --stamp. Listed after
# ct_vhm_forearm (its FDS/FDP/APL keep winning) and BEFORE xfer_zan2vhm_limb_photo / xfer_zan2vhm_limb, so it replaces
# only the Z-Anatomy-transferred ids it ships.
if [ -f $T/vhm_forearm_muscles_seeded.nii.gz ] && [ ! -f build/vh/ct_vhm_forearm_seeded/manifest.json ]; then
  cp mappings/subjects/ct_vhm_forearm_seeded_volume_mapping.json build/vh/; rm -rf build/vh/ct_vhm_forearm_seeded
  python3 scripts/ingest_volume_geometry.py convert $T/vhm_forearm_muscles_seeded.nii.gz --labels vhm_forearm_muscles_seeded --subject ct_vhm_forearm_seeded --origin='-6.035,-895.476,4.787' --smooth 1.0 2>&1 | grep -E "wrote|Error|Trace"
  python3 scripts/cryo/vhm_forearm_seeded_q180.py --stamp build/vh/ct_vhm_forearm_seeded
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
# Q172d: levator_ani_r joins it (one voxel piece, split by smooth=1.0); the grep keys on it so a pre-Q172 fix subject is
# reconverted; afterwards the builder stamps its Q172 rule-based badges onto both pelvic-floor manifests (idempotent).
if [ -f mappings/subjects/ct_vhm_pfloor_fix_volume_mapping.json ] && ! grep -q levator_ani_r build/vh/ct_vhm_pfloor_fix/manifest.json 2>/dev/null; then
  cp mappings/subjects/ct_vhm_pfloor_fix_volume_mapping.json build/vh/
  python3 scripts/ingest_volume_geometry.py convert $T/vhm_pelvic_floor_cryo.nii.gz --labels vhm_pelvic_floor --subject ct_vhm_pfloor_fix --origin='-6.035,-895.476,4.787' --smooth 0.0 2>&1 | grep -E "wrote|Error|Trace"
fi
[ -f build/vh/ct_vhm_pfloor/manifest.json ] && python3 scripts/cryo/vhm_pelvic_floor_from_cryo.py --stamp-badges 2>&1 | tail -1
# Q170: his own pelvic viscera (urinary bladder, rectum, pelvic sigmoid, prostate) -- vhm_total above the torso block's
# lower edge and vhm_legs_total's pelvis slab below it, placed by the fixed Stage-2 block offset; colon cut at his
# pelvic inlet and split at the sigmoid take-off / first branch point. Same mask_surface(smooth 1.0) + his origin as
# convert; written by the script itself (ids have no entity in data/, category 'organ' carried per structure)
if [ ! -f build/vh/ct_vhm_pelvis/manifest.json ] || [ -n "${RECONVERT:-}" ]; then
  python3 scripts/vhf_pelvic_viscera.py --body vhm --origin='-6.035,-895.476,4.787' 2>&1 | tail -5
fi
# Q173: his adductor magnus (posterior surface) and biceps femoris long head / semitendinosus (anterior surfaces)
# snapped inward onto the fat plane photographed in his 0.33 mm cryosections, from the stored per-vertex moves (no
# photographs needed here; `measure` needs the re-streamed crops) -> ct_vhm_thigh_snap, listed BEFORE vhm_both so it wins
# only these six ids. Same run: his Q57 sciatic nerve translated by the measured photograph-to-atlas registration
# (vhm_nerves_cryo_reg.nii.gz) and surfaced as ct_vhm_sciatic (listed last; id unique), then badged from the report.
# Q175: his adductor longus (anterolateral face, under the femoral vessels) snapped the same way from
# vhm_thigh_snap_q175.npz; `apply` appends it to ct_vhm_thigh_snap after the six Q173 ids (their bytes unchanged).
# Q177: the faces his sciatic nerve (biceps femoris long head, adductor magnus: snapped again on the Q173 mesh) and femoral
# veins (pectineus, vastus medialis: appended) still entered, from vhm_thigh_snap_q177.npz (same apply).
if [ -f $T/vhm_thigh_snap_q173.npz ] && { [ ! -f build/vh/ct_vhm_thigh_snap/manifest.json ] || [ -n "${RECONVERT:-}" ] || \
     { [ -f $T/vhm_thigh_snap_q175.npz ] && ! grep -q adductor_longus build/vh/ct_vhm_thigh_snap/manifest.json; } || \
     { [ -f $T/vhm_thigh_snap_q177.npz ] && ! grep -q Q177 build/vh/ct_vhm_thigh_snap/manifest.json; }; }; then
  python3 scripts/cryo/vhm_thigh_fat_plane_snap.py apply 2>&1 | tail -1
fi
# Q176: the tracked outlines (sciatic; femoral/popliteal veins + tibial nerve) clipped to his photographed non-muscle
# (scripts/cryo/vhm_tracked_clip.py) -> *_clip.nii.gz, used when present (originals kept); badges get the Q176 numbers.
SCI=$T/vhm_nerves_cryo_reg.nii.gz; [ -f $T/vhm_nerves_cryo_reg_clip.nii.gz ] && SCI=$T/vhm_nerves_cryo_reg_clip.nii.gz
[ -f $T/vhm_nerves_cryo_reg_clip_interp.nii.gz ] && SCI=$T/vhm_nerves_cryo_reg_clip_interp.nii.gz   # Q178: unusable photographs y -136..-141 interpolated
if [ -f $SCI ] && { ! grep -q "/$(basename $SCI)" build/vh/ct_vhm_sciatic/manifest.json 2>/dev/null || [ -n "${RECONVERT:-}" ]; }; then
  cp mappings/subjects/ct_vhm_sciatic_volume_mapping.json build/vh/; rm -rf build/vh/ct_vhm_sciatic
  python3 scripts/ingest_volume_geometry.py convert $SCI --labels vhm_nerves --subject ct_vhm_sciatic --origin='-6.035,-895.476,4.787' --smooth 0.0 2>&1 | grep -E "wrote|Error|Trace"
  python3 scripts/cryo/vhm_thigh_fat_plane_snap.py badge-nerve >/dev/null
fi
# Q174: his femoral (artery + vein) and popliteal (vein + left tibial nerve) bundles, tracked in his 0.33 mm cryosections
# through the Q173 registration (scripts/cryo/vhm_femoral_popliteal_track.py); label volumes committed, so no photographs
# are needed here. Surfaced as ct_vhm_femoral / ct_vhm_popliteal (ids unique; listed last), then badged from the report.
Q174_NEW=""
for s in femoral popliteal; do
  V=$T/vhm_${s}_cryo.nii.gz; [ -f $T/vhm_${s}_cryo_clip.nii.gz ] && V=$T/vhm_${s}_cryo_clip.nii.gz   # Q176
  [ -f $T/vhm_${s}_cryo_clip_interp.nii.gz ] && V=$T/vhm_${s}_cryo_clip_interp.nii.gz   # Q178 (femoral veins only)
  if [ -f $V ] && { ! grep -q "/$(basename $V)" build/vh/ct_vhm_$s/manifest.json 2>/dev/null || [ -n "${RECONVERT:-}" ]; }; then
    cp mappings/subjects/ct_vhm_${s}_volume_mapping.json build/vh/; rm -rf build/vh/ct_vhm_$s
    python3 scripts/ingest_volume_geometry.py convert $V --labels vhm_$s --subject ct_vhm_$s --origin='-6.035,-895.476,4.787' --smooth 1.0 2>&1 | grep -E "wrote|Error|Trace"
    Q174_NEW=1
  fi
done
[ -n "$Q174_NEW" ] && [ -f build/vh/ct_vhm_femoral/manifest.json ] && [ -f build/vh/ct_vhm_popliteal/manifest.json ] && python3 scripts/cryo/vhm_femoral_popliteal_track.py badge >/dev/null
[ -f data/derived/Q176_vhm_tracked_clip.json ] && [ -f build/vh/ct_vhm_sciatic/manifest.json ] && [ -f build/vh/ct_vhm_femoral/manifest.json ] && \
  [ -f build/vh/ct_vhm_popliteal/manifest.json ] && python3 scripts/cryo/vhm_tracked_clip.py badge   # Q176 (idempotent)
# Q177: the sciatic_n / femoral_v residual-overlap sentence from the Q177 report (after the Q176 badge; idempotent)
[ -f data/derived/Q177_vhm_thigh_faces.json ] && [ -f build/vh/ct_vhm_sciatic/manifest.json ] && [ -f build/vh/ct_vhm_femoral/manifest.json ] && \
  python3 scripts/cryo/vhm_thigh_fat_plane_snap.py badge-q177
# Q178: the levels on his unusable photographs (y -136..-141) interpolated between the traced, clipped levels
# (scripts/cryo/vhm_dark_slice_interp.py); RULE-BASED sentence appended after the Q177 one (idempotent)
[ -f data/derived/Q178_vhm_sciatic_interp.json ] && [ -f build/vh/ct_vhm_sciatic/manifest.json ] && [ -f build/vh/ct_vhm_femoral/manifest.json ] && \
  python3 scripts/cryo/vhm_dark_slice_interp.py badge
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
[ -f build/vh/ct_vhm_thigh_snap/manifest.json ] && SUBJ="$SUBJ --subject ct_vhm_thigh_snap"   # Q173 + Q175 + Q177, before vhm_both
# Q182: his ribs_l / ribs_r re-surfaced from his own TS rib labels (scripts/ribs_from_ct_labels.py; no dilation, one
# piece per side) replace the Q105/Q109 dilated voxel remesh ct_vhm carries (12-13 mm outside the labels). Listed before ct_vhm.
[ -f build/vh/ct_vhm_ribs/manifest.json ] || python3 scripts/ribs_from_ct_labels.py build --body vhm | tail -1
# Q183: his costal_cartilage_r / _l from HIS OWN TS label 117 (split at his sternum midline; same convert as Q182) replace
# the ct_s1159 ones (another person's CT, 12-62 mm off his ribs). Listed before ct_s1159. The ct_s1159* records left (vessels,
# quadratus lumborum: no usable source of his own) get a measured NOT-HIS-GEOMETRY badge from data/derived/Q183_vhm_foreign_audit.json.
[ -f build/vh/ct_vhm_ccart/manifest.json ] || python3 scripts/costal_cartilage_from_ct_labels.py build | tail -1
[ -f data/derived/Q183_vhm_foreign_audit.json ] && python3 scripts/costal_cartilage_from_ct_labels.py stamp
# Q183b: the 18 ct_s1159* vessel / QL records, route per structure in data/derived/Q183b_vessels_ql.json
# (scripts/vessels_ql_q183b.py): (a) his own labels that passed -> ct_vhm_vessels (SVC, brachiocephalic veins) and
# ct_vhm_qlh (QL left, his hybrid-CT label); (c) her own vessels carried by the bone-driven transfer -> xfer_vhf2vhm_vessels
# (brachiocephalic trunk, right CCA); (d) the rest stay ct_s1159 with a Q183b note appended to the badge + hidden_default (Q184) (stamp, after Q183's).
{ [ -f build/vh/ct_vhm_vessels/manifest.json ] && [ -f build/vh/ct_vhm_qlh/manifest.json ]; } || python3 scripts/vessels_ql_q183b.py own-build | tail -2
if [ ! -f build/vh/xfer_vhf2vhm_vessels/manifest.json ]; then
  [ -f build/viewer_f_hr/bundle.json ] || { echo "female hi-res bundle absent: run scripts/cryo/vhf_rebuild_bundle.sh first"; exit 1; }
  MB=build/viewer_m_hr; [ -f $MB/bundle.json ] || MB=$B
  python3 scripts/vessels_ql_q183b.py transfer --male-bundle $MB | tail -2
fi
[ -f data/derived/Q183b_vessels_ql.json ] && python3 scripts/vessels_ql_q183b.py stamp
# Q185a: badge his skin with its CT field-of-view cut (x = -233 / +247 mm; arms beyond it have no skin) -- no skin is made up
[ -f build/vh/ct_vhm_skin/manifest.json ] && [ -f data/derived/Q185a_skin_fov_vhm.json ] && python3 scripts/vhm_skin_fov_q185a.py stamp
for s in ct_vhm_foot vhm_both ct_vhm_arm ct_vhm_armm ct_vhm_forearm ct_vhm_shsp ct_vhm_delt ct_vhm_cuff ct_vhm_pmr ct_vhm_es ct_vhm_head ct_vhm_ribs ct_vhm_ccart ct_vhm ct_vhm_headm ct_vhm_neck ct_vhm_neckbv xfer_vhf2vhm xfer_vhf2vhm_neck ct_vhm_ggl ct_vhm_sgl ct_vhm_pfloor ct_vhm_orbit ct_vhm_abd ct_vhm_abw ct_vhm_twall ct_vhm_vessels ct_vhm_qlh xfer_vhf2vhm_vessels ct_s1159_abd ct_s1159 ct_vhm_skin; do SUBJ="$SUBJ --subject $s"; done
# Q180 HELD (main session 2026-09-30): not shipped by default -- the seeded bellies drop the tendons the transferred
# meshes carry, contact boundaries follow septa no better than Q165 (0.20-0.51), and 38/63 seeds are low confidence.
# Set Q180_SHIP=1 to include it once the owner has reviewed/corrected the seeds on the click page.
[ -n "${Q180_SHIP:-}" ] && [ -f build/vh/ct_vhm_forearm_seeded/manifest.json ] && SUBJ="$SUBJ --subject ct_vhm_forearm_seeded"   # Q180
[ -f build/vh/xfer_zan2vhm_limb_photo/manifest.json ] && SUBJ="$SUBJ --subject xfer_zan2vhm_limb_photo"
[ -f build/vh/xfer_zan2vhm_limb/manifest.json ] && SUBJ="$SUBJ --subject xfer_zan2vhm_limb"
[ -f build/vh/ct_vhm_pelvis/manifest.json ] && SUBJ="$SUBJ --subject ct_vhm_pelvis"   # Q170 pelvic viscera (ids unique; listed last so no other structure moves)
# Q185c: intervertebral discs filled between his own adjacent vertebral-body endplates (scripts/discs_from_vertebrae_q185c.py;
# held levels carry the Q104 mesh re-badged). The Q104 cylinders in ct_vhm are dropped at export, C1/C2 (no disc there) included.
[ -f build/vh/ct_vhm_discs/manifest.json ] || python3 scripts/discs_from_vertebrae_q185c.py build --body vhm | tail -1
EXCL=(); [ -f build/vh/ct_vhm_discs/manifest.json ] && { SUBJ="$SUBJ --subject ct_vhm_discs"; EXCL=(--exclude 'ct_vhm:intervertebral_disc_*'); }
[ -f build/vh/ct_vhm_sciatic/manifest.json ] && SUBJ="$SUBJ --subject ct_vhm_sciatic"   # Q57 + Q173 registration (id unique; listed last)
for s in ct_vhm_femoral ct_vhm_popliteal; do [ -f build/vh/$s/manifest.json ] && SUBJ="$SUBJ --subject $s"; done   # Q174 (ids unique; listed last)
# Q62 step 7b: head / neck / larynx muscles (+ foot lumbricals) he had no mesh for, Z-Anatomy carried by the Q168
# per-bone fits onto HIS skeleton (data/derived/Q168_zan_to_vhm.json, `zan_to_vhf_whole_body.py --target vhm`; larynx
# refitted onto his CT thyroid + cricoid cartilages), same gates as her Q62 steps 5/7 (zan_to_vhf_head_neck.py /
# zan_to_vhf_foot_intrinsics.py --target vhm; reports data/derived/Q62s7b_vhm_*.json). Ids unique; listed last.
if [ -d build/zanatomy ] && [ -f build/vh/ct_vhm_skin/manifest.json ] && [ -f build/viewer_m_hr/bundle.json ]; then
  [ -f build/vh/xfer_zan2vhm_head/manifest.json ] || python3 scripts/transfer/zan_to_vhf_head_neck.py --target vhm 2>&1 | grep -v Deprec | tail -2
  # foot lumbricals r/l: both HELD 2026-10-01 (12.6/18.8 % inside his adductor hallucis) -> no subject; rerun only
  # when its report is absent (delete data/derived/Q62s7b_vhm_foot_lumbricals.json to retry)
  [ -f build/vh/xfer_zan2vhm_foot/manifest.json ] || [ -f data/derived/Q62s7b_vhm_foot_lumbricals.json ] || python3 scripts/transfer/zan_to_vhf_foot_intrinsics.py --target vhm 2>&1 | grep -v Deprec | tail -2
fi
for s in xfer_zan2vhm_head xfer_zan2vhm_foot; do [ -f build/vh/$s/manifest.json ] && SUBJ="$SUBJ --subject $s"; done
# Q62 step 9: trunk + small lower-limb muscles he had no mesh for, same route onto HIS skeleton
# (scripts/transfer/zan_to_vh_trunk_leg.py --target vhm; data/derived/Q62s9_vhm_trunk_leg.json). Ids unique; listed last.
# 2026-10-01: nothing passed on either body (all held: carrier/overlap/lung). Q182 (ribs from the CT labels + rib refit):
# subclavius passes (her _r, his _r/_l), the rest still held (overlap/lung) -> subject written; reruns only when its
# report is absent (delete data/derived/Q62s9_vhm_trunk_leg.json to retry).
if [ ! -f build/vh/xfer_zan2vhm_trunk/manifest.json ] && [ ! -f data/derived/Q62s9_vhm_trunk_leg.json ] && [ -d build/zanatomy ] && [ -f build/vh/ct_vhm_skin/manifest.json ] \
   && [ -f build/viewer_m_hr/bundle.json ]; then
  # Q182: carried by the Q168 fit REFITTED onto the label-derived ribs (only ribs_l/ribs_r fits differ from Q168's report;
  # the Q168 Z-Anatomy viewer keeps its own report). Regenerated from this bundle when absent.
  [ -f data/derived/Q182_q168_ribrefit_vhm.json ] || python3 scripts/transfer/zan_to_vhf_whole_body.py --target vhm --report data/derived/Q182_q168_ribrefit_vhm.json | tail -1
  python3 scripts/transfer/zan_to_vh_trunk_leg.py --target vhm --q168 data/derived/Q182_q168_ribrefit_vhm.json 2>&1 | grep -v Deprec | tail -2
fi
[ -f build/vh/xfer_zan2vhm_trunk/manifest.json ] && SUBJ="$SUBJ --subject xfer_zan2vhm_trunk"
# Q170: output dir overridable (the hi-res page lives in build/viewer_m_hr: VHM_OUT=build/viewer_m_hr); the transfer
# steps above still read build/viewer_m as their input bundle, unchanged
OUT=${VHM_OUT:-build/viewer_m}; mkdir -p "$OUT"
# Q185 d/e/h/i/j: soft structures inside this body's OWN bone (TS bone labels + own bone meshes) carved out in place
# on the exact records the exporter ships (same --subject / --exclude list); bounded (<= 4 mm push, tendons trimmed at
# the bone, cartilage only if <= 3 mm median), fold-guarded, gated; originals kept as vertices.preq185.f32 (idempotent).
python3 scripts/bone_carve_q185.py --body vhm $SUBJ ${EXCL[@]+"${EXCL[@]}"} 2>&1 | grep -E "Q185 bone carve|Error|Trace"
python3 scripts/export_viewer_bundle.py $SUBJ ${EXCL[@]+"${EXCL[@]}"} -o $OUT --budget-scale 2.5 --hires 2>&1 | grep -E "structures from|->|Error|Trace"
python3 scripts/build_viewer_html.py --bundle $OUT -o $OUT/atlas_viewer_male.html --external-bin 2>&1 | tail -1
echo VHM_REBUILD_DONE
