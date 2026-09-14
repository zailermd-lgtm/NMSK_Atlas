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
    --ids digastric_l digastric_r internal_carotid_a_l internal_carotid_a_r internal_jugular_v_l internal_jugular_v_r superior_rectus_l superior_rectus_r inferior_oblique_r inferior_rectus_l inferior_rectus_r lateral_rectus_l lateral_rectus_r levator_palpebrae_superioris_r medial_rectus_r optic_n superior_oblique_l superior_oblique_r \
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
SUBJ=""; for s in ct_vhm_foot vhm_both ct_vhm_arm ct_vhm_armm ct_vhm_forearm ct_vhm_shsp ct_vhm_delt ct_vhm_cuff ct_vhm_pmr ct_vhm_es ct_vhm_head ct_vhm ct_vhm_headm ct_vhm_neck ct_vhm_neckbv xfer_vhf2vhm ct_vhm_orbit ct_vhm_abd ct_vhm_abw ct_vhm_twall ct_s1159_abd ct_s1159 ct_vhm_skin; do SUBJ="$SUBJ --subject $s"; done
python3 scripts/export_viewer_bundle.py $SUBJ -o build/viewer_m --budget-scale 0.9 2>&1 | grep -E "structures from|->|Error|Trace"
python3 scripts/build_viewer_html.py --bundle build/viewer_m -o build/viewer_m/atlas_viewer_male.html 2>&1 | tail -1
echo VHM_REBUILD_DONE
