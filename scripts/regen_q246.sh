#!/bin/bash
# Q246: test dirs build/q246/<page dir> = the current merged pages (build/q244) with the Q246 imaging + ultrasound code and tables (clinical/imaging_tool.js, clinical/ultrasound_tool.js)
# staged and pasted into the page: the same stage_clinical_files.py --ultrasound step that scripts/regen_q232.sh runs (regen_q241.sh -> regen_q232.sh). No template, no geometry is touched.
#   scripts/regen_q246.sh [PAGE_DIR ...]        default: viewer_f_hr viewer_zan_female        SRC=build/q244 (override with Q246_SRC), output build/q246 (Q246_OUT)
# The main session rebuilds the six final pages with regen_q241.sh (it calls the same staging step, so the new tool files are picked up from clinical/).
set -eu; cd "$(dirname "$0")/.."
SRC=${Q246_SRC:-build/q244}; OUT=${Q246_OUT:-build/q246}
DIRS=("$@"); [ ${#DIRS[@]} -gt 0 ] || DIRS=(viewer_f_hr viewer_zan_female)
for d in "${DIRS[@]}"; do
  rm -rf "$OUT/$d"; mkdir -p "$OUT"; cp -r "$SRC/$d" "$OUT/$d"
  python3 scripts/clinical/stage_clinical_files.py --ultrasound "$OUT/$d"
done
echo Q246_REGEN_DONE
