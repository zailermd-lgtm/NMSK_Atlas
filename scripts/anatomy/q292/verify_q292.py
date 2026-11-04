#!/usr/bin/env python3
"""Q292: real headless-Chromium check (desktop click 1400x900 + phone touch 390x844) of Base · Female with her own breasts, chest skin
contour and pelvic organs.

A  every Q292 structure is in the page; hidden / faded at load = the page report's hd / fd sets; her breasts faded (glands drawn), her
   bladder / rectum / uterus drawn, the HRA sculpted breast set, the Z bladder / sigmoid / external anal sphincter and the HRA uterus not
B  list search + tap opens her right breast's card: the REFITTED / RULE-BASED wording, her CT volume, and the card's geometry line names
   her CT (not Z-Anatomy); the fibroglandular card says RULE-BASED; her bladder's card says MEASURED on her own CT
C  'unhide' on the HRA breast fat card draws it (a default, not a removal); reset restores the load state
D  the pose rig covers the page; thoracic flexion moves her breast and gland, reset restores them
E  0 page errors; screenshots of the chest and pelvis (desktop) for the report

    python3 scripts/anatomy/q292/verify_q292.py BASE_F_DIR [--shots DIR]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283")); sys.path.insert(0, str(HERE.parent / "q287"))
import verify_q283 as V  # noqa: E402
import verify_q287 as V7  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap, api = V.check, V.tap, V.api


def run(page_dir: Path, errs: list, b, shots: Path | None):
    rep = json.loads((REPO / "data/derived/Q292_page_report.json").read_text())
    hd, fd, added = rep["hidden_default"], rep["faded_default"], rep["added"]
    probe = sorted(set(added) | {"breast_fat_r", "nipple_r", "zan_urinary_bladder", "zan_sigmoid_colon", "external_anal_sphincter", "uterus"})
    html = V.html_of(page_dir)
    srv, port = V.serve(page_dir)
    try:
        for (w, h), phone in ((1400, 900), False), ((390, 844), True):
            T = f"base_f_{w}"
            ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
            pg = ctx.new_page(); page_errs = []
            pg.on("pageerror", lambda e: page_errs.append(str(e)))
            pg.route("**/*", V.route)
            pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=180000)
            V.ready(pg)
            idx = api(pg, "Object.fromEntries(api.list().filter(r => " + json.dumps(probe) + ".includes(r.id)).map(r => [r.id, r.i]))")
            check(f"{T}: A all Q292 entries in the page ({len(idx)} / {len(probe)})", all(k in idx for k in probe), errs)
            st = pg.evaluate("() => window.__viewerState()")
            check(f"{T}: A hidden {st['hidden']} (report {len(hd)}) / faded {st['faded']} (report {len(fd)}) at load",
                  st["hidden"] == len(hd) and st["faded"] == len(fd), errs)
            vis = {k: api(pg, f"api.visible({idx[k]})") for k in idx}
            drawn = ["breast_fgt_ct_r", "breast_fgt_ct_l", "urinary_bladder", "rectum", "uterus_cryo_vhf", "external_anal_sphincter_ct_vhf"]
            notd = ["breast_ct_r", "breast_fat_r", "nipple_r", "zan_urinary_bladder", "zan_sigmoid_colon", "external_anal_sphincter", "uterus"]
            check(f"{T}: A drawn {[vis.get(k) for k in drawn]}, not drawn {[vis.get(k) for k in notd]}",
                  all(vis.get(k) for k in drawn) and not any(vis.get(k) for k in notd), errs)
            if shots and not phone:
                api(pg, "api.setCategoryOn ? 0 : 0")
                for name, js in (("front", "document.getElementById('btn-front') && document.getElementById('btn-front').click()"),):
                    pg.evaluate("() => { " + js + " }"); pg.wait_for_timeout(1500)
                    pg.screenshot(path=str(shots / f"Q292_browser_base_f_{name}.png"))
            ok = V7.pick_from_list(pg, phone, "Breast (right), from her CT", "Breast (right)")
            card = pg.evaluate("() => (document.getElementById('info') || {}).textContent || ''")
            check(f"{T}: B list search + tap opens her right breast card (row {ok})", ok and "Breast (right), from her CT" in card, errs)
            check(f"{T}: B card: REFITTED + RULE-BASED + her volume + geometry line = her CT",
                  "REFITTED" in card and "RULE-BASED" in card and "of her CT breast" in card and "Geometry: her own CT" in card
                  and "Geometry from Z-Anatomy" not in card, errs)
            V7.pick_from_list(pg, phone, "fibroglandular", "(right)")
            card = pg.evaluate("() => (document.getElementById('info') || {}).textContent || ''")
            check(f"{T}: B gland card says RULE-BASED", "RULE-BASED" in card and "Breast fibroglandular tissue (right)" in card, errs)
            V7.pick_from_list(pg, phone, "her own, CT", "Urinary bladder (her own")
            card = pg.evaluate("() => (document.getElementById('info') || {}).textContent || ''")
            check(f"{T}: B her bladder card says MEASURED on her own CT", "MEASURED on her own CT" in card and "Geometry: her own CT" in card, errs)
            V7.pick_from_list(pg, phone, "fat pad", "fat pad (right)")
            V7.card_btn(pg, phone, "#a-hide")
            shown = [k for k in ("breast_fat_r",) if api(pg, f"api.visible({idx[k]})")] + \
                    [k for k in ("breast_fat_l",) if k in idx and api(pg, f"api.visible({idx[k]})")]
            check(f"{T}: C 'unhide' on an HRA breast fat card draws it ({shown})", len(shown) >= 1, errs)
            if phone and not pg.is_visible("#btn-reset"):
                pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
            pg.evaluate("() => document.getElementById('btn-reset').click()"); pg.wait_for_timeout(500)
            st = pg.evaluate("() => window.__viewerState()")
            check(f"{T}: C reset restores hidden {st['hidden']} / faded {st['faded']}", st["hidden"] == len(hd) and st["faded"] == len(fd), errs)
            rig = api(pg, "(r => ({count: r.count, skinned: r.skin.length}))(api.pose().rig())")
            okp = bool(api(pg, "api.pose().setRegion('thoracic', 'flex', 25)")); pg.wait_for_timeout(800)
            dbg = pg.evaluate("() => window.__poseDebug()")
            mv = {k: dbg["moved"].get(k) for k in ("breast_fgt_ct_r", "breast_ct_r")}
            api(pg, "api.pose().reset()"); pg.wait_for_timeout(800)
            back = pg.evaluate("() => window.__poseDebug()")["moved"]
            check(f"{T}: D rig count {rig['count']} (page {rep['meshes']}); thoracic flexion 25 deg moves gland / breast by {mv} mm "
                  f"(bad {dbg['bad']}, overflow {len(dbg['overflow'])}); reset back to {[back.get(k) for k in mv]}",
                  rig["count"] == rep["meshes"] and okp and (mv["breast_fgt_ct_r"] or 0) > 1.0 and (mv["breast_ct_r"] or 0) > 1.0
                  and not dbg["bad"] and not dbg["overflow"] and all(not back.get(k) for k in mv), errs)
            check(f"{T}: E 0 page errors ({page_errs[:2]})", not page_errs, errs)
            ctx.close()
    finally:
        srv.terminate()


def main():
    errs = []
    shots = None
    if "--shots" in sys.argv:
        shots = Path(sys.argv[sys.argv.index("--shots") + 1]); shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pl:
        b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
        run(Path(sys.argv[1]), errs, b, shots)
        b.close()
    print("ALL OK" if not errs else f"FAILED {len(errs)}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
