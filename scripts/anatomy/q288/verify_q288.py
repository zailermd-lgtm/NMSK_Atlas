#!/usr/bin/env python3
"""Q288: real headless-Chromium check (desktop click 1400x900 + phone touch 390x844) of her cryosection uterus on

Combined · Female (Z page):
A  uterus_cryo_vhf and the HRA `uterus` are in the page; at load hidden == 262 (Q287's 261 + the HRA uterus), faded == 2; hers is drawn,
   the HRA one is not
B  the structure list search finds her uterus; tapping it opens its card with the method (random walker, seeds) and the cited volume
C  'unhide' on the HRA uterus card draws it (a default, not a removal); reset restores 262 / 2
D  the pose rig covers the page (3244 entries); her uterus is rigid on the PELVIS segment (the rig's root), so a lumbar flexion moves the
   trunk but not her uterus, and reset restores everything
E  0 page errors

Imaging-based Female (own page):
A  uterus_cryo_vhf drawn with the organ layer, HRA `uterus` hidden by default (Q184 hidden_default)
B  list search + tap opens her uterus card: badge (random walker, Jirapinyo) + Source line 'Measured on this body' + subject chip text
C  picking the HRA uterus from the list shows it
D  rig 1051 entries, her uterus rigid on the pelvis segment: lumbar flexion leaves it in place, reset restores it exactly
E  0 page errors

    python3 scripts/anatomy/q288/verify_q288.py ZAN_F_DIR OWN_F_DIR
"""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q283")); sys.path.insert(0, str(HERE.parent / "q287"))
import verify_q283 as V  # noqa: E402
import verify_q287 as V7  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap, api = V.check, V.tap, V.api
IDS = ["uterus_cryo_vhf", "uterus"]
RIG = "(r => ({count: r.count, root: r.segs[0][0], root_rigid: (r.rigid.find(g => g[0] === 0) || [0, []])[1]}))(api.pose().rig())"
VSUM = "(p => { let s = 0; for (let k = 0; k < p.length; k++) s += p[k]; return s; })(api.geometry(%d).pos)"


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
            idx = api(pg, "Object.fromEntries(api.list().filter(r => " + str(IDS) + ".includes(r.id)).map(r => [r.id, r.i]))")
            check(f"{T}: A both uteri in the page ({idx})", all(k in idx for k in IDS), errs)
            st = pg.evaluate("() => window.__viewerState()")
            check(f"{T}: A hidden {st['hidden']} (261 + HRA uterus) / faded {st['faded']} at load", st["hidden"] == 262 and st["faded"] == 2, errs)
            vis = {k: api(pg, f"api.visible({idx[k]})") for k in idx}
            check(f"{T}: A hers drawn, HRA not ({vis})", vis["uterus_cryo_vhf"] and not vis["uterus"], errs)
            ok = V7.pick_from_list(pg, phone, "her own, from her cryosections", "Uterus, with cervix")
            card = pg.evaluate("() => (document.getElementById('info') || {}).textContent || ''")
            check(f"{T}: B list search + tap opens her uterus card (row {ok})", ok and "Uterus, with cervix (her own" in card, errs)
            check(f"{T}: B badge states the method and the cited volume", "random walker" in card and "Jirapinyo" in card and "seed" in card, errs)
            V7.pick_from_list(pg, phone, "Uterus (with cervix)", "Uterus (with cervix)")
            V7.card_btn(pg, phone, "#a-hide")
            check(f"{T}: C 'unhide' on the HRA uterus card draws it", api(pg, f"api.visible({idx['uterus']})"), errs)
            if phone and not pg.is_visible("#btn-reset"):
                pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
            pg.evaluate("() => document.getElementById('btn-reset').click()"); pg.wait_for_timeout(400)
            st = pg.evaluate("() => window.__viewerState()")
            check(f"{T}: C reset restores hidden {st['hidden']} / faded {st['faded']}", st["hidden"] == 262 and st["faded"] == 2, errs)
            rig = api(pg, RIG)
            okp = bool(api(pg, "api.pose().setRegion('lumbar', 'flex', 25)")); pg.wait_for_timeout(600)
            dbg = pg.evaluate("() => window.__poseDebug()")
            mv = dbg["moved"].get("uterus_cryo_vhf"); nmv = sum(1 for v in dbg["moved"].values() if v)
            api(pg, "api.pose().reset()"); pg.wait_for_timeout(600)
            back = sum(1 for v in pg.evaluate("() => window.__poseDebug()")["moved"].values() if v)
            check(f"{T}: D rig count {rig['count']}, uterus rigid on {rig['root']} ({idx['uterus_cryo_vhf'] in rig['root_rigid']}); lumbar flexion 25 deg "
                  f"(set {okp}) moves {nmv} structures, her uterus {mv} (bad {dbg['bad']}, overflow {len(dbg['overflow'])}); after reset {back} moved",
                  rig["count"] == 3244 and rig["root"] == "pelvis" and idx["uterus_cryo_vhf"] in rig["root_rigid"] and okp and nmv > 10 and not mv
                  and not dbg["bad"] and not dbg["overflow"] and back == 0, errs)
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
            idx = api(pg, "Object.fromEntries(api.list().filter(r => " + str(IDS) + ".includes(r.id)).map(r => [r.id, r.i]))")
            api(pg, "api.setCategoryOn('organ', true)")
            vis = {k: api(pg, f"api.visible({idx[k]})") for k in idx}
            check(f"{T}: A hers drawn, HRA uterus hidden by default ({vis})", len(idx) == 2 and vis["uterus_cryo_vhf"] and not vis["uterus"], errs)
            if phone and pg.is_visible("#m-list"):
                tap(pg, "#m-list", phone); pg.wait_for_timeout(300)
            for _ in range(2):
                if pg.is_visible("#q") or not pg.is_visible("#t-lay3"):
                    break
                tap(pg, "#t-lay3", phone); pg.wait_for_timeout(300)
                if phone and pg.is_visible("#m-list") and not pg.is_visible("#q"):
                    tap(pg, "#m-list", phone); pg.wait_for_timeout(300)
            pg.fill("#q", "her cryosections"); pg.wait_for_timeout(400)
            hit = next((r for r in pg.query_selector_all("#list .row") if "Uterus, with cervix" in r.inner_text()), None)
            if hit:
                hit.scroll_into_view_if_needed(); (hit.tap() if phone else hit.click()); pg.wait_for_timeout(500)
            sel = api(pg, "api.selectedId()")
            card = pg.evaluate("() => (document.getElementById('i-name').textContent || '') + ' | ' + (document.getElementById('i-tags').textContent || '') + ' | ' + (document.getElementById('i-body').textContent || '')")
            src = pg.evaluate("() => document.getElementById('i-src').textContent || ''")
            check(f"{T}: B list search + tap opens her uterus card (sel {sel})", hit is not None and sel == "uterus_cryo_vhf", errs)
            check(f"{T}: B badge + subject chip + Source 'Measured on this body' ({src[:40]!r})",
                  "random walker" in card and "Jirapinyo" in card and "colour cryosections (Q288)" in card and src.startswith("Measured on this body"), errs)
            if phone and not pg.is_visible("#q") and pg.is_visible("#m-list"):
                tap(pg, "#m-list", phone); pg.wait_for_timeout(300)
            pg.fill("#q", "Uterus (with cervix)"); pg.wait_for_timeout(400)
            r2 = next((r for r in pg.query_selector_all("#list .row") if "Uterus (with cervix)" in r.inner_text()), None)
            if r2:
                r2.scroll_into_view_if_needed(); (r2.tap() if phone else r2.click()); pg.wait_for_timeout(400)
            check(f"{T}: C picking the HRA uterus from the list shows it", r2 is not None and api(pg, f"api.visible({idx['uterus']})"), errs)
            rig = api(pg, RIG)
            i = idx["uterus_cryo_vhf"]
            s0 = api(pg, VSUM % i); okp = bool(api(pg, "api.pose().setRegion('lumbar', 'flex', 25)")); pg.wait_for_timeout(500)
            s1 = api(pg, VSUM % i); api(pg, "api.pose().reset()"); pg.wait_for_timeout(500); s2 = api(pg, VSUM % i)
            check(f"{T}: D rig {rig['count']}, uterus rigid on {rig['root']} ({i in rig['root_rigid']}); lumbar flexion (set {okp}) vertex sum {s0:.1f} -> {s1:.1f}, reset {s2:.1f}",
                  rig["count"] == 1051 and rig["root"] == "pelvis" and i in rig["root_rigid"] and okp and abs(s1 - s0) < 1e-3 * max(1.0, abs(s0))
                  and abs(s2 - s0) < 1e-3 * max(1.0, abs(s0)), errs)
            check(f"{T}: E 0 page errors ({page_errs[:2]})", not page_errs, errs)
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
