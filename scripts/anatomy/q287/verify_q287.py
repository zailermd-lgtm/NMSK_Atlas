#!/usr/bin/env python3
"""Q287: real headless-Chromium check (desktop click 1400x900 + phone touch 390x844) of

Combined · Female (Z page):
A  her skin (skin_ct_vhf), her CT breasts and their fibroglandular tissue are in the page; at load the 249 Z skin patches + 12 HRA sculpted
   breast meshes are hidden (viewer state hidden == 261) and her two breasts faded (faded == 2); her skin and the gland are drawn
B  the structure list search finds the right fibroglandular tissue; tapping it opens its card with the HU-rule badge (Vedantham)
C  'unfade' on her breast's card and 'unhide' on an HRA nipple's card show them (defaults, not removals); reset restores the defaults
D  the pose rig covers the page (3243 entries) and thoracic flexion moves the right gland and breast; reset restores them. Her whole-body
   skin is reported, not gated: the Q241 rig weights one whole-body surface like a skin patch (pelvis / thigh segments only), so it
   does not follow trunk flexion -- the same limitation Imaging-based Female's skin has had since Q241
E  0 page errors

Imaging-based Female (own page): breast_fgt_ct_r / _l listed and drawn with the organ layer, pose rig 1050 entries, 0 page errors.

    python3 scripts/anatomy/q287/verify_q287.py ZAN_F_DIR OWN_F_DIR
"""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap, api = V.check, V.tap, V.api
NEW = ["skin_ct_vhf", "breast_ct_r", "breast_ct_l", "breast_fgt_ct_r", "breast_fgt_ct_l"]
HRA = [f"{n}_{s}" for s in "lr" for n in ("breast_fat", "mammary_gland", "lactiferous_ducts", "areola", "nipple", "breast_suspensory_ligaments")]


def open_list(pg, phone):
    """the page opens in the Q267 Model-only layout (list and card hidden on desktop): one tap on the layout pill shows them;
    on the phone the list lives in the layers sheet"""
    for _ in range(3):
        if pg.is_visible("#search"):
            return
        if not phone and pg.evaluate("() => document.body.classList.contains('lay-model')") and pg.is_visible("#t-lay3"):
            tap(pg, "#t-lay3", phone)
        elif pg.is_visible("#btn-panel"):
            tap(pg, "#btn-panel", phone)
        pg.wait_for_timeout(400)


def pick_from_list(pg, phone, query, text):
    open_list(pg, phone)
    pg.fill("#search", query); pg.wait_for_timeout(400)
    row = next((r for r in pg.query_selector_all("#list button.item") if text in r.inner_text()), None)
    if row:
        if phone:
            row.scroll_into_view_if_needed(); row.tap()
        else:       # at 1400x900 the rail's last ~60 px (the list rows) sit under the front/side/back/reset pills: keyboard, as a user would
            row.focus(); pg.keyboard.press("Enter")
        pg.wait_for_timeout(500)
    return row is not None


def card_btn(pg, phone, bid):
    if pg.is_visible("#im") and not pg.is_visible(bid):
        tap(pg, "#im", phone); pg.wait_for_timeout(300)
    tap(pg, bid, phone); pg.wait_for_timeout(400)


def run_zan(page_dir: Path, errs: list, b):
    html = V.html_of(page_dir)
    srv, port = V.serve(page_dir)
    try:
        for (w, h), phone in ((1400, 900), False), ((390, 844), True):
            T = f"comb_f_{w}"
            ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
            pg = ctx.new_page(); page_errs = []
            pg.on("pageerror", lambda e: page_errs.append(str(e)))
            pg.route("**/*", V.route)
            pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=120000)
            V.ready(pg)
            idx = api(pg, "Object.fromEntries(api.list().filter(r => " + str(NEW + HRA + ["zan_skin_perineal_closure"]) + ".includes(r.id)).map(r => [r.id, r.i]))")
            check(f"{T}: A new + HRA entries in the page ({len(idx)})", all(k in idx for k in NEW + HRA + ["zan_skin_perineal_closure"]), errs)
            st = pg.evaluate("() => window.__viewerState()")
            check(f"{T}: A hidden {st['hidden']} (249 Z skin + 12 HRA) / faded {st['faded']} (her 2 breasts) at load",
                  st["hidden"] == 261 and st["faded"] == 2, errs)
            vis = {k: api(pg, f"api.visible({idx[k]})") for k in idx}
            check(f"{T}: A her skin + glands drawn, breasts faded, HRA + Z perineal closure not drawn "
                  f"{[vis[k] for k in NEW]} {[vis[k] for k in HRA][:3]} {vis['zan_skin_perineal_closure']}",
                  vis["skin_ct_vhf"] and vis["breast_fgt_ct_r"] and vis["breast_fgt_ct_l"] and not vis["breast_ct_r"]
                  and not any(vis[k] for k in HRA) and not vis["zan_skin_perineal_closure"], errs)
            ok = pick_from_list(pg, phone, "fibroglandular", "(right)")
            sel = api(pg, "api.selectedId ? api.selectedId() : null") if api(pg, "typeof api.selectedId") == "function" else None
            card = pg.evaluate("() => (document.getElementById('info') || {}).textContent || ''")
            check(f"{T}: B list search + tap opens the right gland's card (row {ok}, sel {sel})",
                  ok and "Breast fibroglandular tissue (right)" in card, errs)
            check(f"{T}: B badge states the HU rule and the cited range", "HU >= -30" in card and "Vedantham" in card, errs)
            pick_from_list(pg, phone, "Breast (right), from her CT", "Breast (right)")
            card_btn(pg, phone, "#a-fade")
            check(f"{T}: C 'unfade' on her right breast draws it", api(pg, f"api.visible({idx['breast_ct_r']})"), errs)
            pick_from_list(pg, phone, "nipple", "ipple")
            card_btn(pg, phone, "#a-hide")
            shown = [k for k in ("nipple_r", "nipple_l") if api(pg, f"api.visible({idx[k]})")]
            check(f"{T}: C 'unhide' on an HRA nipple card draws it ({shown})", len(shown) == 1, errs)
            if phone and not pg.is_visible("#btn-reset"):
                pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
            pg.evaluate("() => document.getElementById('btn-reset').click()"); pg.wait_for_timeout(400)
            st = pg.evaluate("() => window.__viewerState()")
            check(f"{T}: C reset restores hidden {st['hidden']} / faded {st['faded']}", st["hidden"] == 261 and st["faded"] == 2, errs)
            rig = api(pg, "(r => ({count: r.count, skinned: r.skin.length}))(api.pose().rig())")
            okp = bool(api(pg, "api.pose().setRegion('thoracic', 'flex', 25)")); pg.wait_for_timeout(600)
            dbg = pg.evaluate("() => window.__poseDebug()")
            mv = {k: dbg["moved"].get(k) for k in ("breast_fgt_ct_r", "breast_ct_r", "skin_ct_vhf")}
            api(pg, "api.pose().reset()"); pg.wait_for_timeout(600)
            back = pg.evaluate("() => window.__poseDebug()")["moved"]
            check(f"{T}: D rig count {rig['count']} (skinned {rig['skinned']}); thoracic flexion 25 deg moves gland / breast / skin by {mv} mm "
                  f"(bad {dbg['bad']}, overflow {len(dbg['overflow'])}); reset back to {[back.get(k) for k in mv]}",
                  rig["count"] == 3243 and okp and mv["breast_fgt_ct_r"] > 1.0 and mv["breast_ct_r"] > 1.0 and not dbg["bad"] and not dbg["overflow"]
                  and all(not back.get(k) for k in mv), errs)
            check(f"{T}: E 0 page errors ({page_errs[:2]})", not page_errs, errs)
            ctx.close()
    finally:
        srv.terminate()


def run_own(page_dir: Path, errs: list, b):
    html = V.html_of(page_dir)
    srv, port = V.serve(page_dir)
    try:
        for (w, h), phone in ((1400, 900), False), ((390, 844), True):
            T = f"own_f_{w}"
            ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
            pg = ctx.new_page(); page_errs = []
            pg.on("pageerror", lambda e: page_errs.append(str(e)))
            pg.route("**/*", V.route)
            pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=90000)
            V.ready(pg)
            ids = ["breast_fgt_ct_r", "breast_fgt_ct_l", "breast_ct_r"]
            idx = api(pg, "Object.fromEntries(api.list().filter(r => " + str(ids) + ".includes(r.id)).map(r => [r.id, r.i]))")
            api(pg, "api.setCategoryOn('organ', true)")
            vis = [api(pg, f"api.visible({idx[k]})") for k in ids if k in idx]
            rig = api(pg, "api.pose().rig().count")
            check(f"{T}: glands listed + drawn {vis}, rig {rig}", len(idx) == 3 and all(vis) and rig == 1050, errs)
            check(f"{T}: 0 page errors ({page_errs[:2]})", not page_errs, errs)
            ctx.close()
    finally:
        srv.terminate()


def main():
    errs = []
    with sync_playwright() as pl:
        b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
        run_zan(Path(sys.argv[1]), errs, b)
        run_own(Path(sys.argv[2]), errs, b)
        b.close()
    print("ALL OK" if not errs else f"FAILED {len(errs)}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
