#!/bin/bash
# Q236: all six pages x four viewports, two queues in parallel (about 1 h with software GL). The long flow (cut mode, persistence, timing) runs on desktop for every page and on the phone for the
# three pages of queue A. Results: data/derived/Q236_browser_check_<page>.json, build/q236_renders/*.png, log build/q236_renders/_run_<queue>.log
set -u; cd "$(dirname "$0")/../../.."
mkdir -p build/q236_renders
( for p in own_m zan_m base_m; do Q236_FULL=desktop,phone scripts/anatomy/q236/browser_check_all.sh $p; done > build/q236_renders/_run_A.log 2>&1 ) &
( for p in own_f zan_f base_f; do Q236_FULL=desktop scripts/anatomy/q236/browser_check_all.sh $p; done > build/q236_renders/_run_B.log 2>&1 ) &
wait
echo ALL_DONE
