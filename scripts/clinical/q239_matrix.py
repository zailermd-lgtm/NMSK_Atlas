#!/usr/bin/env python3
"""Q239 -- the verification matrix: six pages x (desktop 1366x768, phone 390x844) under the strictest hosting mimic (inline only), plus the other hosting
conditions on two pages. Results data/derived/q239/matrix.json, screenshots data/derived/q239/*.png (strict run only).
    python3 scripts/clinical/q239_matrix.py [--jobs 2] [--root build/q239]"""
from __future__ import annotations

import concurrent.futures as cf
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAGES = [("viewer_m_hr", "atlas_viewer_male.html", "own", "own_m"), ("viewer_f_hr", "atlas_viewer_female.html", "own", "own_f"),
         ("viewer_zan_atlas", "atlas_viewer_zan_atlas.html", "zan", "base_m"), ("viewer_base_female", "atlas_viewer_base_female.html", "zan", "base_f"),
         ("viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "comb_m"), ("viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "comb_f")]
VPS = ["1366x768", "390x844"]
OUT = REPO / "data" / "derived" / "q239"


def job(root, d, page, kind, tag, cond, vp, shots, quick):
    js = OUT / "runs" / f"{tag}_{cond}_{vp}.json"
    cmd = [sys.executable, str(REPO / "scripts/clinical/q239_check.py"), str(REPO / root / d), page, kind, "--cond", cond, "--vp", vp, "--tag", tag, "--json", str(js)]
    if shots:
        cmd += ["--shots-dir", str(OUT)]
    if quick:
        cmd += ["--quick"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1500)
    try:
        j = json.loads(js.read_text())
    except Exception:
        j = {"ok": False, "errors": ["no result: " + r.stderr[-300:]], "checks": {}}
    return {"tag": tag, "cond": cond, "vp": vp, "ok": j["ok"], "errors": j["errors"], "failed": [k for k, v in j["checks"].items() if not v], "seconds": j.get("seconds")}


def main():
    a = sys.argv[1:]
    jobs = int(a[a.index("--jobs") + 1]) if "--jobs" in a else 2
    root = a[a.index("--root") + 1] if "--root" in a else "build/q239"
    OUT.mkdir(parents=True, exist_ok=True)
    plan = [(root, d, p, k, t, "strict", vp, True, False) for (d, p, k, t) in PAGES for vp in VPS]
    for (d, p, k, t) in (PAGES[0], PAGES[5]):
        for cond in ("base", "plain", "nosniff", "nosib", "sbx"):
            plan.append((root, d, p, k, t, cond, "1366x768", False, True))
    plan.append((root, *PAGES[0], "sbx", "390x844", False, True))
    res = []
    with cf.ThreadPoolExecutor(jobs) as ex:
        for r in ex.map(lambda x: job(*x), plan):
            print(json.dumps(r), flush=True); res.append(r)
    (OUT / "matrix.json").write_text(json.dumps(res, indent=1) + "\n")
    return 0 if all(r["ok"] for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
