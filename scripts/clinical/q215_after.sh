#!/bin/bash
# Q215 post-build pipeline (run after scripts/transfer/q215_fill.py wrote build/viewer_f_hr_q215): own female page from the new bundle, regenerated motor points of the own female viewer (merged
# into clinical/data/motor_points.json + the Q187 coverage; the other viewers stay byte for byte), clinical files staged into the page / bundle dirs, risk check, Q204 before / after audit, model
# separation audit, page check.  The Z-fitted female page is not touched.
set -u; cd "$(dirname "$0")/../.."
L=build/q215; mkdir -p $L build/q215_raw
THREE=${THREE:-/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/three.min.js}
bash scripts/transfer/q215_build_pages.sh > $L/after_pages.log 2>&1
python3 scripts/clinical/q215_run_motor_points.py --viewers vhf --jobs 1 > $L/after_mp.log 2>&1
python3 scripts/clinical/stage_clinical_files.py build/q215/viewer_f_hr --viewer vhf > $L/after_stage.log 2>&1
python3 scripts/clinical/stage_clinical_files.py build/viewer_f_hr_q215 --viewer vhf >> $L/after_stage.log 2>&1
mkdir -p $L/risk_after
python3 scripts/clinical/risk_structures_q188.py --viewer vhf --source build/viewer_f_hr_q215 --out-dir $L/risk_after > $L/after_risk.log 2>&1
python3 scripts/zanatomy/q215_run.py q204_regions own_f > $L/q204_own.log 2>&1 &
python3 scripts/zanatomy/q215_run.py q204_regions before_f > $L/q204_before.log 2>&1 &
python3 scripts/audit_q189_model_separation.py --m build/viewer_m_hr_q214 --f build/viewer_f_hr_q215 --out data/derived/Q215_model_separation_audit.json > $L/after_sep.log 2>&1
python3 scripts/transfer/q215_pagecheck.py build/q215/viewer_f_hr atlas_viewer_female.html "$THREE" data/derived/Q215_model_separation_audit.json female > $L/pagecheck_own.log 2>&1
wait
python3 scripts/zanatomy/q215_compare.py > $L/compare.log 2>&1
echo PIPELINE_DONE > $L/after_done.flag
