#!/bin/bash
# Rebuild the Visible Human FEMALE viewer bundle from what the repository holds (task outputs in
# data/ct_sources/task_outputs, per-subject mappings in mappings/subjects) after a container reset wiped build/.
# The body surface (ct_vhf_skin) needs her torso CT restacked in the scratchpad (scripts/cryo/vhf_skin_and_depth.sh);
# it is skipped when that volume is absent. Idempotent: converts every subject, then exports and builds the HTML.
set -u; cd /home/user/NMSK_Atlas; S=/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad
T=data/ct_sources/task_outputs; mkdir -p build/vh
O=$(python3 scripts/ingest_volume_geometry.py inspect $T/vhf_total.nii.gz --labels totalsegmentator 2>&1 | grep -- "--origin" | head -1 | sed "s/.*--origin '\([^']*\)'.*/\1/")
[ -z "$O" ] && { echo "NO_ORIGIN"; exit 1; }; echo "origin $O"
conv(){ # volume labels subject [extra convert args]
  local vol=$1 labels=$2 sub=$3; shift 3
  [ -f "$vol" ] || { echo "missing $vol"; return; }
  [ -z "${RECONVERT:-}" ] && [ -f build/vh/$sub/manifest.json ] && { echo "have $sub"; return; }   # idempotent: RECONVERT=1 forces
  cp mappings/subjects/${sub}_volume_mapping.json build/vh/ 2>/dev/null || python3 scripts/ingest_volume_geometry.py propose $vol --labels $labels --subject $sub --force 2>&1 | grep -E "labels currently"
  python3 scripts/ingest_volume_geometry.py convert $vol --labels $labels --subject $sub --origin="$O" "$@" 2>&1 | grep -E "wrote|Error|Trace"
  cp build/vh/${sub}_volume_mapping.json mappings/subjects/
}
conv $T/vhf_total.nii.gz totalsegmentator ct_vhf --smooth 1.0
conv $T/vhf_craniofacial_structures.nii.gz totalsegmentator_craniofacial_structures ct_vhf_head --smooth 1.0
conv $T/vhf_head_muscles.nii.gz totalsegmentator_head_muscles ct_vhf_headm --smooth 1.0
conv $T/vhf_oculomotor_muscles.nii.gz totalsegmentator_oculomotor_muscles ct_vhf_orbit --smooth 1.0
conv $T/vhf_headneck_muscles_merged.nii.gz totalsegmentator_headneck_muscles ct_vhf_neck --smooth 1.0
conv $T/vhf_headneck_bones_vessels.nii.gz totalsegmentator_headneck_bones_vessels ct_vhf_neckbv --smooth 1.0
conv $T/vhf_abdominal_muscles.nii.gz totalsegmentator_abdominal_muscles ct_vhf_abd --smooth 1.0
[ -n "${STOP_BEFORE_LEGS:-}" ] && { echo CONV_DONE; exit 0; }   # torso subjects only (run while the legs volume is still being made)
conv $T/vhf_lower_limb_bones.nii.gz vhf_legs ct_vhf_legs --smooth 1.0
# her seven tarsal bones: her CT tarsal label split by the male's separately segmented tarsals transferred onto her
# (scripts/transfer/name_tarsal_pieces.py -> cross_subject_transfer m2f -> scripts/vhf_split_tarsals.py); the split volume is in the repo
if [ ! -f $T/vhf_tarsals_split.nii.gz ] || [ -n "${RECONVERT:-}" ]; then
  python3 - <<'PY'
import json,shutil,os
b=json.load(open('data/derived/viewer_bundles/vhm_v25/bundle.json')); ren=json.load(open('mappings/subjects/vhm_both_piece_names.json'))['rename']; seen={}
for e in b['structures']:
    k=seen.get(e['id'],0); seen[e['id']]=k+1; new=ren.get(e['id'],{}).get(str(k))
    if new: e['id']=new
os.makedirs('build/vhm_named',exist_ok=True); json.dump(b,open('build/vhm_named/bundle.json','w')); shutil.copy('data/derived/viewer_bundles/vhm_v25/bundle.bin','build/vhm_named/bundle.bin')
PY
  python3 scripts/transfer/cross_subject_transfer.py --direction m2f --male-html build/vhm_named --ids calcaneus_r talus_r cuboid_r navicular_r cuneiform_medial_r cuneiform_intermediate_r cuneiform_lateral_r calcaneus_l talus_l cuboid_l navicular_l cuneiform_medial_l cuneiform_intermediate_l cuneiform_lateral_l -o build/vh/xfer_tarsals --report data/derived/transfer_report_tarsals.json 2>&1 | grep -v Deprec | tail -1 | cut -c1-160
  python3 scripts/vhf_split_tarsals.py --xfer build/vh/xfer_tarsals 2>&1 | grep -v Deprec | tail -3
fi
conv $T/vhf_tarsals_split.nii.gz vhf_tarsals ct_vhf_tarsal --smooth 1.0
conv $T/vhf_arm_bones_ct.nii.gz vhf_arm_bones ct_vhf_armb --smooth 1.0
conv $T/vhf_deltoid_cryo.nii.gz vhf_deltoid ct_vhf_delt --smooth 1.0
# shoulder girdle split (Q62): infraspinatus / teres minor / teres major out of the cuff's merged mass (scripts/cryo/split_shoulder_girdle.py); listed BEFORE the cuff so the split wins
conv $T/vhf_shoulder_split_cryo.nii.gz vhf_shoulder_split ct_vhf_shsp --smooth 1.0
conv $T/vhf_rotator_cuff_cryo.nii.gz vhf_rotator_cuff ct_vhf_cuff --smooth 1.0
conv $T/vhf_erector_columns.nii.gz vhf_erector ct_vhf_es --smooth 1.0
conv $T/vhf_arm_muscles_cryo.nii.gz vhf_arm_muscles ct_vhf_armm --smooth 1.0
# Q62 step 1: her right forearm muscles from the full-resolution crops (rule-based; twelve muscles, the rest merged/unshipped)
conv $T/vhf_forearm_muscles_cryo.nii.gz vhf_forearm_muscles ct_vhf_forearm --smooth 1.0
# Q62 step 3: deep neck + suboccipitals from her 1 mm frame (rule-based; splenius and erector_cervical sinks unshipped)
conv $T/vhf_deep_neck_cryo.nii.gz vhf_deep_neck ct_vhf_dneck --smooth 1.0
# Q62 step 6: diaphragm + intercostal sheets from her total-task labels (rule-based, 4 mm sheet)
conv $T/vhf_trunk_wall.nii.gz vhf_trunk_wall ct_vhf_twall --smooth 1.0
# Q62 step 7a: suprahyoid + extrinsic tongue muscles from her 1 mm frame (rule-based; the straps are fragments and unshipped)
conv $T/vhf_hyoid_muscles_cryo.nii.gz vhf_hyoid_muscles ct_vhf_hyoid --smooth 1.0
# Q62 step 4: her right hand intrinsics from the full-resolution crops (rule-based; the thenar group stays merged and unshipped)
conv $T/vhf_hand_muscles_cryo.nii.gz vhf_hand_muscles ct_vhf_hand --smooth 1.0
# Q55: the femoral artery, vein and nerve trunk tracked in her full-resolution anterior-thigh crops (triangle only)
conv $T/vhf_femoral_bundle_cryo.nii.gz vhf_femoral_bundle ct_vhf_femoral --smooth 1.0
# Q56: the popliteal artery, vein and the tibial nerve in her popliteal fossa, same tracker
conv $T/vhf_popliteal_cryo.nii.gz vhf_popliteal ct_vhf_popliteal --smooth 1.0
conv $T/vhf_pecminor_rhomboids_cryo.nii.gz vhf_pecminor_rhomboids ct_vhf_pmr --smooth 1.0
# nerves tracked through her FULL-RESOLUTION cryosections (scripts/cryo/vhf_nerve_track.py + vhf_nerve_volume.py; 0.5 mm label volume in the repo)
[ -f $T/vhf_nerves_cryo.nii.gz ] && conv $T/vhf_nerves_cryo.nii.gz vhf_nerves ct_vhf_nerve --smooth 1.0
SUBJ="--subject ct_vhf_head --subject ct_vhf_legs --subject ct_vhf_tarsal --subject ct_vhf_armb --subject ct_vhf --subject ct_vhf_headm --subject ct_vhf_neck --subject ct_vhf_neckbv --subject ct_vhf_orbit --subject ct_vhf_abd --subject ct_vhf_shsp --subject ct_vhf_delt --subject ct_vhf_cuff --subject ct_vhf_es --subject ct_vhf_armm --subject ct_vhf_forearm --subject ct_vhf_dneck --subject ct_vhf_hyoid --subject ct_vhf_hand --subject ct_vhf_femoral --subject ct_vhf_popliteal --subject ct_vhf_twall --subject ct_vhf_pmr --subject xfer_vhm2vhf_rhom"
[ -f build/vh/ct_vhf_nerve/manifest.json ] && SUBJ="$SUBJ --subject ct_vhf_nerve"   # ct_vhf_legs precedes ct_vhf so its united femur (both blocks) wins over the torso stub
[ -f $S/vhf_ts/skin_ct.nii.gz ] || python3 scripts/cryo/vhf_whole_body_skin.py   # torso + legs silhouettes on one grid
SKIN=$S/vhf_ts/skin_ct.nii.gz; [ -f $S/vhf_ts/skin_union.nii.gz ] && SKIN=$S/vhf_ts/skin_union.nii.gz   # CT silhouette united with the photograph silhouette (arms) when available
if [ -f $SKIN ]; then conv $SKIN vhm_skin ct_vhf_skin --smooth 1.5 --step 2; SUBJ="$SUBJ --subject ct_vhf_skin"; else echo "skin volume absent: bundle without depth tags"; fi
# cross-subject transfer: everything the male has and she lacks (lower-limb muscles, ligaments, cartilage, ...) carried onto
# her bones and inside her measured muscle compartment; badged subject, listed LAST so her own structures always win
if [ ! -f build/vh/xfer_vhm2vhf/manifest.json ] || [ -n "${RECONVERT:-}" ]; then
  python3 scripts/transfer/cross_subject_transfer.py --direction m2f --male-html data/derived/viewer_bundles/vhm_v25 \
    --envelope-src data/derived/lean_envelope_vhm.json --envelope-dst data/derived/lean_envelope_vhf.json \
    --skin-nii $SKIN --skin-origin="$O" -o build/vh/xfer_vhm2vhf --report data/derived/transfer_report_vhm2vhf.json 2>&1 | grep -v Deprec | head -1 | cut -c1-200
fi
# the transferred lower-limb muscles with their boundaries refined to HER septa (scripts/transfer/refine_transfer_to_septa.py,
# label volume in the repo); listed BEFORE xfer_vhm2vhf so the refined muscle wins and the unrefined transfer supplies the rest
if [ -f $T/vhf_xfer_lowerlimb_septa.nii.gz ]; then
  conv $T/vhf_xfer_lowerlimb_septa.nii.gz vhf_xfer_septa xfer_vhm2vhf_sep --smooth 1.0
  [ -f build/vh/xfer_vhm2vhf_sep/manifest.json ] && SUBJ="$SUBJ --subject xfer_vhm2vhf_sep"
fi
[ -f build/vh/xfer_vhm2vhf/manifest.json ] && SUBJ="$SUBJ --subject xfer_vhm2vhf"
# his rhomboid minor carried onto her (her own rhomboid mass was unusable, Q62 step 2); the forearm/hand transfer was
# measured and REJECTED (see docs/GEOMETRY_SOURCES.md): that map distorts limb volumes by 2-3x
if [ ! -f build/vh/xfer_vhm2vhf_rhom/manifest.json ]; then
  python3 scripts/transfer/cross_subject_transfer.py --direction m2f --male-html build/viewer_m/atlas_viewer_male.html --female-bundle build/viewer_f \
    --ids rhomboid_minor_l rhomboid_minor_r -o build/vh/xfer_vhm2vhf_rhom --report data/derived/transfer_report_vhm2vhf_rhom.json 2>&1 | tail -1 | cut -c1-140
fi
python3 scripts/export_viewer_bundle.py $SUBJ -o build/viewer_f --budget-scale 0.85 2>&1 | grep -E "structures from|->|Error|Trace"
python3 scripts/build_viewer_html.py --bundle build/viewer_f -o build/viewer_f/atlas_viewer_female.html 2>&1 | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/viewer_f/atlas_viewer_female.html
echo VHF_REBUILD_DONE
