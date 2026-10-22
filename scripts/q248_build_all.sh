#!/bin/bash
# Q248 full chain (~50 min on 4 cores): ligament audit of the Q244 pages, Z-Anatomy ligaments carried onto the Imaging-based pages (Combined source, Base source as fallback), CVH ligaments, rule-based ligaments of all six
# pages, the pre-pages (in-process patches of build/q244, ship diff 0 unlisted), the page dirs build/q248/<page> (scripts/regen_q248.sh = regen_q232 + abbreviations + calibre + symmetry sidecar + pose rigs), the audit "after".
#   scripts/q248_build_all.sh            (only the last steps after a template change: scripts/regen_q248.sh)
# Needs: build/q244/<six page dirs>, build/viewer_f_hr_q243, build/viewer_m_hr_q237 (own bundles), data/derived/Q235_cvh_to_vhf_transform.json, third_party/cvh_wu2015.
set -eu; cd "$(dirname "$0")/.."
Q=scripts/anatomy/q248
python3 $Q/lig_audit.py --before build/q244 -o data/derived/Q248_ligament_audit_before.md --json data/derived/Q248_ligament_audit_before.json | tail -7
python3 $Q/transfer.py own_f comb_f > build/q248_xfer_own_f.log 2>&1 &
python3 $Q/transfer.py own_m comb_m > build/q248_xfer_own_m.log 2>&1 &
python3 $Q/rule_run.py base_f > build/q248_rule_base_f.log 2>&1 &
wait
python3 $Q/transfer.py own_f base_f > build/q248_xfer_own_f_base.log 2>&1 &
python3 $Q/transfer.py own_m base_m > build/q248_xfer_own_m_base.log 2>&1 &
(for k in base_m comb_f comb_m own_f own_m; do python3 $Q/rule_run.py $k; done; for k in own_f comb_f; do python3 $Q/cvh_lig.py $k; done) > build/q248_rule_rest.log 2>&1 &
wait
TPL=build/q248_pre/_templates_regen; mkdir -p $TPL
git show HEAD:viewer/atlas_viewer.template.html > $TPL/atlas_viewer.template.html; git show HEAD:viewer/zan_atlas.template.html > $TPL/zan_atlas.template.html
python3 scripts/sync_subjects_q248.py --dir $TPL | tail -1
for k in own_f own_m comb_f comb_m base_f base_m; do python3 $Q/build_pages.py $k --tpl $TPL; done
scripts/regen_q248.sh own_f own_m zan_f zan_m base_f base_m
python3 $Q/report_md.py
python3 $Q/lig_audit.py --before build/q244 --after build/q248 -o data/derived/Q248_ligament_audit.md --json data/derived/Q248_ligament_audit.json | tail -7
echo Q248_BUILD_DONE
