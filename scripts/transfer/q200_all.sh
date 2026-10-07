#!/bin/bash
# Q200 pipeline, one step at a time (memory): builds -> pages -> Q198 audits (elbow) -> before/after table -> separation audit -> vertex diff -> renders.
set -eu; cd "$(dirname "$0")/../.."
for b in vhm vhf; do python3 scripts/transfer/q200_elbow_repair.py --body $b --rows data/derived/Q200_rows_$b.json > /tmp/q200_$b.log 2>&1; tail -1 /tmp/q200_$b.log; done
scripts/transfer/q200_build_pages.sh
python3 scripts/transfer/q200_audit.py own_m | tail -1
python3 scripts/transfer/q200_audit.py own_f | tail -1
python3 scripts/transfer/q200_compare.py > /tmp/q200_compare.txt
python3 scripts/audit_q189_model_separation.py --m build/viewer_m_hr_q200 --f build/viewer_f_hr_q200 --out data/derived/Q200_model_separation_audit.json | grep -E "^male|^female"
python3 scripts/transfer/q200_vertex_diff.py
mkdir -p build/q200_renders
for m in own_m own_f; do
  b=$([ $m = own_m ] && echo viewer_m_hr || echo viewer_f_hr)
  python3 scripts/transfer/q200_render.py build/${b}_q200 build/q200_renders/after $m | tail -1
  python3 scripts/transfer/q200_montage.py build/q200_renders/after/$m build/q200_renders/${m}_elbows_after.png "$m AFTER (Q200; blue = filled from Z-Anatomy; vessels red/blue, nerves yellow)"
done
