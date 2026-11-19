#!/bin/bash
# Q224 post-build pipeline (run after scripts/transfer/q224_fix.py --phase final wrote build/viewer_{m,f}_hr_q224): pre-pages from the bundles (template-only), risk tables regenerated (the veins changed),
# motor points of both own viewers regenerated + merged, clinical files staged, then the cut-slice + parts regeneration (scripts/regen_cut_q218.sh, Q218_OUT=build/q224) into the final page dirs.
# The Z pages / templates are not touched.
set -u; cd "$(dirname "$0")/../.."
L=build/q224_logs; mkdir -p $L build/q224_pre/viewer_m_hr build/q224_pre/viewer_f_hr
python3 scripts/build_viewer_html.py --bundle build/viewer_m_hr_q224 -o build/q224_pre/viewer_m_hr/atlas_viewer_male.html --external-bin | tail -1
python3 scripts/build_viewer_html.py --bundle build/viewer_f_hr_q224 -o build/q224_pre/viewer_f_hr/atlas_viewer_female.html --external-bin | tail -1
sed -i 's/<title>NMSK Atlas Viewer<\/title>/<title>NMSK Atlas Viewer (VH female)<\/title>/' build/q224_pre/viewer_f_hr/atlas_viewer_female.html
python3 scripts/clinical/risk_structures_q188.py --viewer vhm --source build/viewer_m_hr_q224 --out-dir clinical/data > $L/risk_m.log 2>&1
python3 scripts/clinical/risk_structures_q188.py --viewer vhf --source build/viewer_f_hr_q224 --out-dir clinical/data > $L/risk_f.log 2>&1
python3 scripts/clinical/q224_run_motor_points.py --viewers vhm,vhf --jobs 2 > $L/motor_points.log 2>&1
for d in build/q224_pre/viewer_m_hr build/viewer_m_hr_q224; do python3 scripts/clinical/stage_clinical_files.py $d --viewer vhm >> $L/stage.log 2>&1; done
for d in build/q224_pre/viewer_f_hr build/viewer_f_hr_q224; do python3 scripts/clinical/stage_clinical_files.py $d --viewer vhf >> $L/stage.log 2>&1; done
Q218_OUT=build/q224 SRC_own_m=build/q224_pre/viewer_m_hr SRC_own_f=build/q224_pre/viewer_f_hr scripts/regen_cut_q218.sh own_m own_f > $L/regen.log 2>&1
echo PIPELINE_DONE > $L/after_done.flag
