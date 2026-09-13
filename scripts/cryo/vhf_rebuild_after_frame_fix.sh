#!/bin/bash
# Re-derive every female structure that was read off her cryosection frame, after the frame's height
# correction (scripts/cryo/vhf_correct_frame_z.py), then rebuild the bundle twice: once to get her new
# skin/arm structures exported, once more so the lean envelopes (which read her skin mesh) and the
# male-to-female transfer are rebuilt on top of them. Logs to the scratchpad. Idempotent per step.
set -u; cd /home/user/NMSK_Atlas; S=/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad
T=data/ct_sources/task_outputs; MH=data/derived/viewer_bundles/vhm_v25
echo "== rule scripts on the corrected frame $(date -u +%H:%M)"
python3 scripts/cryo/vhf_skin_union.py 2>&1 | tail -2
python3 scripts/cryo/vhf_deltoid_from_cryo.py 2>&1 | tail -3
python3 scripts/cryo/vhf_rotator_cuff_from_cryo.py 2>&1 | tail -3
python3 scripts/cryo/vhf_arm_muscles_from_cryo.py 2>&1 | tail -3
python3 scripts/cryo/vhf_pecminor_rhomboids.py 2>&1 | tail -3
echo "== copy task outputs $(date -u +%H:%M)"
cp $S/vhf_ts/deltoid_cryo.nii.gz $T/vhf_deltoid_cryo.nii.gz; cp $S/vhf_ts/deltoid_cryo_report.json $T/vhf_deltoid_cryo_report.json 2>/dev/null
cp $S/vhf_ts/rotator_cuff_cryo.nii.gz $T/vhf_rotator_cuff_cryo.nii.gz; cp $S/vhf_ts/rotator_cuff_cryo_report.json $T/vhf_rotator_cuff_cryo_report.json 2>/dev/null
cp $S/vhf_ts/arm_muscles_cryo.nii.gz $T/vhf_arm_muscles_cryo.nii.gz; cp $S/vhf_ts/arm_muscles_cryo_report.json $T/vhf_arm_muscles_cryo_report.json 2>/dev/null
cp $S/vhf_ts/pecminor_rhomboids_cryo.nii.gz $T/vhf_pecminor_rhomboids_cryo.nii.gz; cp $S/vhf_ts/pecminor_rhomboids_cryo_report.json $T/vhf_pecminor_rhomboids_cryo_report.json 2>/dev/null
ls $S/vhf_ts/*report.json
rm -rf build/vh/ct_vhf_delt build/vh/ct_vhf_cuff build/vh/ct_vhf_armm build/vh/ct_vhf_pmr build/vh/ct_vhf_skin build/vh/xfer_vhm2vhf
echo "== rebuild pass 1 $(date -u +%H:%M)"
bash scripts/cryo/vhf_rebuild_bundle.sh 2>&1 | grep -v "^have " | tail -12
echo "== envelopes + anthropometrics on the new bundle $(date -u +%H:%M)"
python3 scripts/transfer/build_envelopes.py --male-html $MH --female-cryo-cls $S/vh_cryo_f/cryo_frame_cls.npy 2>&1 | grep -E "^right|^left|y +-(20|220|420|620) "
python3 scripts/transfer/subject_anthropometrics.py --male-html $MH --ct-male $S/vh_idc/nii/vhm_torso_0937.nii.gz --origin-male='-6.035,-895.476,4.787' --ct-female $S/vh_idc/nii/vhf_torso_0937.nii.gz --origin-female='7.769,-885.229,14.137' --male-cryo-dir $S/vh_cryo_m10 --female-cryo-cls $S/vh_cryo_f/cryo_frame_cls.npy 2>&1 | grep "cryo classes" | cut -c1-600
rm -rf build/vh/xfer_vhm2vhf
echo "== rebuild pass 2 (transfer + export) $(date -u +%H:%M)"
bash scripts/cryo/vhf_rebuild_bundle.sh 2>&1 | grep -v "^have " | tail -6
echo "VHF_AFTER_FRAME_FIX_DONE $(date -u +%H:%M)"
