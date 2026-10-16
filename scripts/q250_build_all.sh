#!/bin/bash
# Q250 full chain (~60 min on 4 cores, run A and B in parallel):
#   A. Base · Female: Z-Anatomy deformed onto a female skeleton (q250_base_f.py), female chest envelope (q250_chest_skin.py), the HRA / CVH female structures RE-REGISTERED on the new pelvis by the unchanged
#      Q233 / Q234 / Q235 / Q243 patch scripts, finalize (stale card sentences, ship diff), parts sidecar, page dir.
#   B. Combined · Female with HER OWN pelvis (q250_comb_f.py), finalize, parts sidecar, page dir.
# then (optional, when the Q248 ligaments exist as build/q248/<dir>) the Q248 structures carried with the same field:  python3 scripts/zanatomy/q250_finalize.py base_f --q248 (and comb_f), then regen again.
# The earlier patch scripts write their reports into data/derived/Q233_|Q234_|Q235_|Q243_*_base_f.json: copied to data/derived/Q250_chain_* and the committed originals restored.
# Needs: build/q244/<page dirs> (the published pages), third_party/hra_vh_f, third_party/cvh_wu2015, build/viewer_f_hr_q243 (own bundle, for the HRA organs' own scripts), the TotalSegmentator reference ranges
# (data/derived/Q250_ts_women_pelvis_measures.json; fetch with scripts/anatomy/q250/ts_fetch.py + ts_pelvis.py, not needed to rebuild the pages).
#   scripts/q250_build_all.sh
set -eu; cd "$(dirname "$0")/.."
PRE=build/q250_pre; TPL=$PRE/_templates; mkdir -p $TPL $PRE/c233 $PRE/c234 $PRE/c235 build/q250_work
git show ${Q250_TEMPLATE_REF:-HEAD}:viewer/atlas_viewer.template.html > $TPL/atlas_viewer.template.html; git show ${Q250_TEMPLATE_REF:-HEAD}:viewer/zan_atlas.template.html > $TPL/zan_atlas.template.html
export Q233_ZAN_TEMPLATE=$PWD/$TPL/zan_atlas.template.html
run_a() {
  python3 scripts/zanatomy/q250_base_f.py --pelvis her                       # Z-only deformed page -> $PRE/viewer_base_zonly, data/derived/Q250_base_f_warp_report_her.json
  python3 scripts/zanatomy/q250_chest_skin.py                                # female chest envelope  -> $PRE/viewer_base_zonly_chest
  export Q233_SRC_base_f=$PWD/$PRE/viewer_base_zonly_chest
  python3 scripts/zanatomy/q233_z_female.py base_f --src $PRE/viewer_base_zonly_chest --out $PRE/c233/viewer_base_female | tail -3   # uterus, ovaries, tubes on the new pelvis
  python3 scripts/zanatomy/q234_z_female.py base_f --src $PRE/c233/viewer_base_female --out $PRE/c234/viewer_base_female | tail -3   # vagina, ligaments, breasts
  SRC=$PRE/c234/viewer_base_female
  python3 scripts/zanatomy/q235_z_female.py base_f --src $SRC --out $PRE/c235/viewer_base_female | tail -3 || true                   # CVH perineal structures (guards decide)
  [ -f $PRE/c235/viewer_base_female/atlas_viewer_base_female.html ] && SRC=$PRE/c235/viewer_base_female
  python3 scripts/zanatomy/q243_z.py base_f --src $SRC --out $PRE/viewer_base_female | tail -3                                      # pelvic vessels
  for n in Q233_report_base_f Q233_vertex_diff_base_f Q234_report_base_f Q234_vertex_diff_base_f Q235_report_base_f Q235_vertex_diff_base_f Q243_report_base_f Q243_vertex_diff_base_f; do
    if [ -f data/derived/$n.json ]; then cp data/derived/$n.json data/derived/Q250_chain_${n}.json; git checkout -- data/derived/$n.json; fi
  done
  for f in build/q244/viewer_base_female/clinical_*; do cp $f $PRE/viewer_base_female/; done
  python3 scripts/zanatomy/q250_finalize.py base_f
  python3 scripts/anatomy/q250/parts_sidecar.py base_f $PRE/viewer_base_female $PRE/viewer_base_female/parts_data.json
  scripts/regen_q250.sh base_f | tail -3
}
run_b() {
  python3 scripts/zanatomy/q250_comb_f.py
  python3 scripts/zanatomy/q250_finalize.py comb_f
  python3 scripts/anatomy/q250/parts_sidecar.py comb_f $PRE/viewer_zan_female $PRE/viewer_zan_female/parts_data.json
  scripts/regen_q250.sh zan_f | tail -3
}
run_a > build/q250_work/runA.log 2>&1 & PA=$!
run_b > build/q250_work/runB.log 2>&1 & PB=$!
wait $PA; wait $PB
python3 scripts/anatomy/q250/joint_check.py build/q244/viewer_base_female build/q250/viewer_base_female atlas_viewer_base_female data/derived/Q250_joint_check_base_f.json
python3 scripts/anatomy/q250/joint_check.py build/q244/viewer_zan_female build/q250/viewer_zan_female atlas_viewer_zan_female data/derived/Q250_joint_check_comb_f.json
python3 scripts/anatomy/q250/verify.py | tail -3                              # data/derived/Q250_sex_indicators.{json,md}
python3 scripts/anatomy/q233/audit.py | tail -3                               # sex audit (Q233_sex_audit.*) with the Q250 block
