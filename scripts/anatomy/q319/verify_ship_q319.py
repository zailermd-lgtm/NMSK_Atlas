#!/usr/bin/env python3
"""Q319: does Pose still start on the two repaired Base pages, as WRITTEN to disk?

    python3 scripts/anatomy/q319/verify_ship_q319.py build/q309/viewer_zan_atlas build/q309/viewer_base_female

Real headless Chromium (the serve / launch pattern of scripts/anatomy/q319/verify_spine_pose_q319.py), once on the
engine page and once on index.html of each directory. Checks: no page error; window.__poseApi.ready() true and
failed() empty -- pose.js disables Pose entirely when rig.count !== E.count(), which is what a structure-count change
breaks; the embedded rig's count equals the page's mesh count; both opponens_digiti_minimi_foot_l/r exist as their
own structures; and the Pose button is enabled."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_spine_pose_q319 as V   # noqa: E402  serve(), route(), ARGS -- reused, not re-derived

JS = r"""() => {
  const P = window.__poseApi, man = window.__ANATOMY_MANIFEST__;
  const ids = man.meshes.map(m => m.id), rig = P.rig ? P.rig() : null;
  const btn = document.getElementById('btn-pose');
  return {ready: P.ready(), failed: P.failed(), stats: P.stats ? P.stats() : null,
          meshes: ids.length, rig_count: rig ? rig.count : null,
          foot_r: ids.indexOf('opponens_digiti_minimi_foot_r'), foot_l: ids.indexOf('opponens_digiti_minimi_foot_l'),
          hand_r: ids.indexOf('opponens_digiti_minimi_r'), hand_l: ids.indexOf('opponens_digiti_minimi_l'),
          btn_enabled: btn ? !btn.disabled : null, btn_title: btn ? btn.title : null};
}"""


def main(dirs) -> int:
    errs = []
    out = {}
    with sync_playwright() as pl:
        b = pl.chromium.launch(args=V.ARGS, executable_path="/opt/pw-browsers/chromium")
        for d in dirs:
            d = Path(d) if Path(d).is_absolute() else V.REPO / d
            srv, port = V.serve(d)
            try:
                for name in [p.name for p in sorted(d.glob("atlas_viewer*.html"))] + ["index.html"]:
                    pe = []
                    pg = b.new_page(viewport={"width": 1400, "height": 950})
                    pg.on("pageerror", lambda e, pe=pe: pe.append(str(e)))
                    pg.route("**/*", V.route)
                    pg.goto(f"http://127.0.0.1:{port}/{name}", wait_until="load", timeout=120000)
                    pg.wait_for_function("window.__poseApi", timeout=120000)
                    pg.wait_for_function("window.__poseApi.ready() || window.__poseApi.failed()", timeout=120000)
                    r = pg.evaluate(JS)
                    r["page_errors"] = pe
                    key = f"{d.name}/{name}"
                    out[key] = r
                    ok = (r["ready"] and not r["failed"] and r["rig_count"] == r["meshes"]
                          and r["foot_r"] >= 0 and r["foot_l"] >= 0 and r["btn_enabled"] and not pe)
                    print(("  OK  " if ok else "  FAIL") + f" {key}: ready={r['ready']} failed={r['failed']!r} "
                          f"rig.count={r['rig_count']} meshes={r['meshes']} foot_r@{r['foot_r']} foot_l@{r['foot_l']} "
                          f"Pose button enabled={r['btn_enabled']} page errors={len(pe)}")
                    if not ok:
                        errs.append(key)
                    pg.close()
            finally:
                srv.terminate()
        b.close()
    print(json.dumps(out, indent=1)[:3000])
    print("VERIFY_SHIP_OK" if not errs else "VERIFY_SHIP_FAIL " + ", ".join(errs))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
