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
conv $T/vhf_deltoid_cryo.nii.gz vhf_deltoid ct_vhf_delt --smooth 1.0
conv $T/vhf_rotator_cuff_cryo.nii.gz vhf_rotator_cuff ct_vhf_cuff --smooth 1.0
conv $T/vhf_erector_columns.nii.gz vhf_erector ct_vhf_es --smooth 1.0
conv $T/vhf_arm_muscles_cryo.nii.gz vhf_arm_muscles ct_vhf_armm --smooth 1.0
SUBJ="--subject ct_vhf_head --subject ct_vhf_legs --subject ct_vhf --subject ct_vhf_headm --subject ct_vhf_neck --subject ct_vhf_neckbv --subject ct_vhf_orbit --subject ct_vhf_abd --subject ct_vhf_delt --subject ct_vhf_cuff --subject ct_vhf_es --subject ct_vhf_armm"   # ct_vhf_legs precedes ct_vhf so its united femur (both blocks) wins over the torso stub
[ -f $S/vhf_ts/skin_ct.nii.gz ] || python3 scripts/cryo/vhf_whole_body_skin.py   # torso + legs silhouettes on one grid
if [ -f $S/vhf_ts/skin_ct.nii.gz ]; then conv $S/vhf_ts/skin_ct.nii.gz vhm_skin ct_vhf_skin --smooth 1.5 --step 2; SUBJ="$SUBJ --subject ct_vhf_skin"; else echo "skin volume absent: bundle without depth tags"; fi
python3 scripts/export_viewer_bundle.py $SUBJ -o build/viewer_f 2>&1 | grep -E "structures from|->|Error|Trace"
python3 scripts/build_viewer_html.py --bundle build/viewer_f -o build/viewer_f/atlas_viewer_female.html 2>&1 | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/viewer_f/atlas_viewer_female.html
echo VHF_REBUILD_DONE
