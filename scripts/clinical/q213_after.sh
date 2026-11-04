#!/bin/bash
# Q213 post-build pipeline (run after scripts/transfer/q213_own_female.py and scripts/zanatomy/q213_zfit.py): own page from the new bundle, regenerated motor points of the two female
# viewers (merged into clinical/data/motor_points.json + the Q187 coverage), clinical files staged into the page / bundle dirs, risk check, Q204 after-audit, ranking after, page checks.
set -u; cd "$(dirname "$0")/../.."
L=build/q213
THREE=${THREE:-/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/three.min.js}
bash scripts/transfer/q213_build_pages.sh > $L/after_pages.log 2>&1
python3 scripts/clinical/q213_run_motor_points.py --viewers vhf,zan_f --jobs 2 > $L/after_mp.log 2>&1
python3 scripts/clinical/stage_clinical_files.py build/q213/viewer_f_hr --viewer vhf > $L/after_stage.log 2>&1
python3 scripts/clinical/stage_clinical_files.py build/q213/viewer_zan_female --viewer zan_f >> $L/after_stage.log 2>&1
python3 scripts/clinical/stage_clinical_files.py build/viewer_f_hr_q213 --viewer vhf >> $L/after_stage.log 2>&1
mkdir -p $L/risk_after
python3 scripts/clinical/risk_structures_q188.py --viewer vhf --source build/viewer_f_hr_q213 --out-dir $L/risk_after > $L/after_risk.log 2>&1
python3 scripts/clinical/risk_structures_q188.py --viewer zan_f --source build/q213/viewer_zan_female/atlas_viewer_zan_female.html --out-dir $L/risk_after >> $L/after_risk.log 2>&1
python3 scripts/zanatomy/q213_run.py q204_regions own_f > $L/q204_own.log 2>&1 &
python3 scripts/zanatomy/q213_run.py q204_regions q213_f > $L/q204_zf.log 2>&1 &
python3 scripts/audit_q189_model_separation.py --m build/viewer_m_hr_q212 --f build/viewer_f_hr_q213 --out data/derived/Q213_model_separation_audit.json > $L/after_sep.log 2>&1
python3 scripts/transfer/q213_pagecheck.py build/q213/viewer_f_hr atlas_viewer_female.html "$THREE" data/derived/Q213_model_separation_audit.json female > $L/pagecheck_own.log 2>&1
python3 scripts/zanatomy/q195_pagecheck.py build/q213/viewer_zan_female atlas_viewer_zan_female.html $L/pagecheck_z "$THREE" > $L/pagecheck_z.log 2>&1
wait
python3 scripts/clinical/q213_audit.py --after --out data/derived/Q213_target_muscle_audit_after.json > $L/audit_after.log 2>&1
python3 scripts/clinical/q213_rank.py --after > $L/rank_after.log 2>&1
echo PIPELINE_DONE > $L/after_done.flag
