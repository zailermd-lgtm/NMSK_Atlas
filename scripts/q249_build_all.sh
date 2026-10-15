#!/bin/bash
# Q249 full chain (about 40-60 min on 4 cores): rule-based pelvic / perineal nerves (+ lumbar medial branches, abdominal wall nerves of the Imaging-based pages, thenar recurrent branch) of the six pages.
#   1. scripts/anatomy/q249/run_rule.py KEY     (KEY = own_f own_m comb_f comb_m base_f base_m)  -> data/derived/Q249_rule_<KEY>.{json,npz}   (reports of shipped + held + skipped nerves)
#   2. scripts/anatomy/q249/build_pages.py KEY  in-process patches of the latest page dirs (build/q248/*, build/q250/viewer_{zan,base}_female) -> build/q249_pre/ (ship diff 0 unlisted: data/derived/Q249_vertex_diff_<KEY>.json)
#   3. needle-risk tables clinical/data/risk_{vhf,vhm,zan_m,zan_f}.json regenerated from the pre-pages (the new nerves are needle-risk structures; Q188 script)
#   4. data/anatomy/calibre.json: the new nerves added (scripts/anatomy/q249/calibre_add.py, additive)
#   5. scripts/regen_q249.sh PAGE   (regen_q232 + abbreviations + calibre inject + symmetry sidecar + pose rig + titles) -> build/q249/<page dir>
# Needs: build/q248/<4 page dirs>, build/q250/viewer_{zan,base}_female, build/q248_pre/bundle_own_{f,m}, build/q248_pre/_templates_regen is NOT needed (templates: working tree).
set -eu; cd "$(dirname "$0")/.."
PRE=build/q249_pre; mkdir -p $PRE/_templates; cp viewer/atlas_viewer.template.html viewer/zan_atlas.template.html $PRE/_templates/
for k in own_f own_m comb_f comb_m base_f base_m; do python3 scripts/anatomy/q249/run_rule.py $k > build/q249_rule_$k.log 2>&1 & done; wait
for k in own_f own_m; do python3 scripts/anatomy/q249/build_pages.py $k --tpl $PRE/_templates > build/q249_build_$k.log 2>&1 & done
for k in comb_f comb_m base_f base_m; do python3 scripts/anatomy/q249/build_pages.py $k > build/q249_build_$k.log 2>&1 & done; wait
python3 scripts/clinical/risk_structures_q188.py --viewer vhf --source $PRE/bundle_own_f
python3 scripts/clinical/risk_structures_q188.py --viewer vhm --source $PRE/bundle_own_m
python3 scripts/clinical/risk_structures_q188.py --viewer zan_m --source $PRE/viewer_zan_atlas/atlas_viewer_zan_atlas.html
python3 scripts/clinical/risk_structures_q188.py --viewer zan_f --source $PRE/viewer_zan_female/atlas_viewer_zan_female.html
for pair in own_m:viewer_m_hr own_f:viewer_f_hr comb_m:viewer_zan_vhm comb_f:viewer_zan_female base_f:viewer_base_female base_m:viewer_zan_atlas; do python3 scripts/anatomy/q249/calibre_add.py ${pair%%:*} build/q249/${pair##*:}; done
for p in own_m own_f zan_m zan_f base_f base_m; do Q249_CAL_DONE=1 scripts/regen_q249.sh $p > build/q249_regen_$p.log 2>&1 & done; wait
tail -qn 1 build/q249_regen_*.log
