#!/usr/bin/env python3
"""Q336: apply the genital-region round to a page ROOT, in the one order that keeps the shared data files in step with the pages.

    python3 scripts/anatomy/q336/apply_q336.py --root build/q309            # the build pages + the shared data files
    python3 scripts/anatomy/q336/apply_q336.py --root /dev/shm/x --private  # a private copy: rig / report to the scratch files given

ROOT holds viewer_base_female/ (and viewer_zan_atlas/ for step 3). Steps:
  1. scripts/anatomy/q336/vulva_skin_q336.py --page-dir ROOT/viewer_base_female --write
       geometry: + skin_vulva_cvh (appended, last mesh), 10 neighbouring skin cards + 17 CVH cards get a Q336 sentence;
       files: atlas_viewer_base_female_geo_03.txt, atlas_viewer_base_female.html, index.html (backups *.q336 beside them);
       rig:   data/anatomy/pose_rig_base_f.json -- ONE rigid entry appended in the pelvis segment, count / nv updated, every
              other entry and the weights blob kept byte for byte (the Q319 / Q338 splice rule); refuses if the rig does not
              describe the page as it was before the write;
  2. scripts/anatomy/q336/records_q336.py --write   -> data/anatomy/synonyms_q306.json (search explanations; refuses unless
       step 1 is on the page, because one of them says the vulvar skin ships on Base · Female);
  3. scripts/anatomy/q306/build_search_q306.py --src ROOT base_m base_f -> data/derived/Q306_search_base_{m,f}.json.
Then the usual regen (the injectors read those committed files).
Idempotent: a second run rebuilds the same structure in place (same index) and changes nothing else.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=REPO)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", required=True)
    ap.add_argument("--private", action="store_true", help="private copy: needs --rig-file and --report")
    ap.add_argument("--rig-file")
    ap.add_argument("--report")
    ap.add_argument("--skip-search", action="store_true", help="steps 1-2 only")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if a.private and not (a.rig_file and a.report):
        raise SystemExit("--private needs --rig-file and --report (never the shared files for a private copy)")
    cmd = [sys.executable, str(HERE / "vulva_skin_q336.py"), "--page-dir", str(root / "viewer_base_female"), "--write"]
    if a.rig_file:
        cmd += ["--rig-file", a.rig_file]
    if a.report:
        cmd += ["--report", a.report]
    run(cmd)
    run([sys.executable, str(HERE / "records_q336.py"), "--write", "--require-page", str(root / "viewer_base_female")])
    if not a.skip_search:
        run([sys.executable, str(REPO / "scripts/anatomy/q306/build_search_q306.py"), "--src", str(root), "base_m", "base_f"])
    print("Q336_APPLY_OK", root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
