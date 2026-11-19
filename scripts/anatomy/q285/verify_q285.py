#!/usr/bin/env python3
"""Q285: real headless-Chromium check of her CT breasts on Imaging-based Female (desktop click 1400x900 + phone touch 390x844).

A  the page lists breast_ct_r / breast_ct_l, drawn with the organ layer on; the twelve HRA sculpted breast meshes are hidden by default
B  picking breast_ct_r from the structure list opens its card, whose badge names the TotalSegmentator `breasts` task and her midline
C  picking an HRA breast from the list still shows it (hidden_default is a default, not a removal)
D  the pose rig covers the new structures (1043 entries, 631 skinned; skinned to the thoracic vertebrae) and thoracic flexion moves them; reset restores them
E  0 page errors

    python3 scripts/anatomy/q285/verify_q285.py PAGE_DIR      (the regenerated viewer_f_hr)
"""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap, api = V.check, V.tap, V.api
NEW = ["breast_ct_r", "breast_ct_l"]
HRA = [f"{n}_{s}" for s in "rl" for n in ("breast_fat", "mammary_gland", "lactiferous_ducts", "areola", "nipple", "breast_suspensory_ligaments")]


def run(page_dir: Path, errs: list):
    html = V.html_of(page_dir)
    srv, port = V.serve(page_dir)
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            for (w, h), phone in ((1400, 900), False), ((390, 844), True):
                T = f"own_f_{w}"
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page(); page_errs = []
                pg.on("pageerror", lambda e: page_errs.append(str(e)))
                pg.route("**/*", V.route)
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=90000)
                V.ready(pg)
                idx = api(pg, "Object.fromEntries(api.list().filter(r => " + str(NEW + HRA) + ".includes(r.id)).map(r => [r.id, r.i]))")
                check(f"{T}: A all fourteen breast entries in the page ({sorted(idx)})", all(k in idx for k in NEW + HRA), errs)
                api(pg, "api.setCategoryOn('organ', true)"); api(pg, "api.setCategoryOn('ligament', true)")
                vis = {k: api(pg, f"api.visible({idx[k]})") for k in NEW + HRA}
                check(f"{T}: A CT breasts drawn {[vis[k] for k in NEW]}", all(vis[k] for k in NEW), errs)
                check(f"{T}: A HRA sculpted breasts hidden by default {[vis[k] for k in HRA]}", not any(vis[k] for k in HRA), errs)
                # B: through the real structure list (search box + row), not the API
                if phone and pg.is_visible("#m-list"):
                    tap(pg, "#m-list", phone); pg.wait_for_timeout(300)
                for _ in range(2):                       # the page opens in the Q267 "Model only" layout: one tap on the layout pill shows the list
                    if pg.is_visible("#q") or not pg.is_visible("#t-lay3"):
                        break
                    tap(pg, "#t-lay3", phone); pg.wait_for_timeout(300)
                    if phone and pg.is_visible("#m-list") and not pg.is_visible("#q"):
                        tap(pg, "#m-list", phone); pg.wait_for_timeout(300)
                pg.fill("#q", "from her CT"); pg.wait_for_timeout(400)
                rows = pg.query_selector_all("#list .row")
                names = [r.inner_text() for r in rows]
                hit = next((r for r in rows if "Breast (right)" in r.inner_text()), None)
                check(f"{T}: B the list search finds the CT breasts ({[n.split(chr(10))[0] for n in names][:4]})", hit is not None, errs)
                if hit:
                    hit.scroll_into_view_if_needed()
                    (hit.tap() if phone else hit.click()); pg.wait_for_timeout(500)
                sel = api(pg, "api.selectedId()")
                card = pg.evaluate("() => (document.getElementById('i-name').textContent || '') + ' | ' + (document.getElementById('i-tags').textContent || '') + ' | ' + (document.getElementById('i-body').textContent || '')")
                check(f"{T}: B card open for {sel}", sel == "breast_ct_r", errs)
                check(f"{T}: B badge names TotalSegmentator `breasts` on her own CT and her midline",
                      "breasts" in card and "TotalSegmentator" in card and "midline" in card, errs)
                src = pg.evaluate("() => document.getElementById('i-src').textContent || ''")
                check(f"{T}: B subject chip shows its SUBJECT_LABELS description and the Source line says measured ({src[:40]!r})",
                      "TotalSegmentator breasts task, Q285" in card and src.startswith("Measured on this body"), errs)
                # C
                if phone and not pg.is_visible("#q") and pg.is_visible("#m-list"):
                    tap(pg, "#m-list", phone); pg.wait_for_timeout(300)
                pg.fill("#q", "fat pad (right)"); pg.wait_for_timeout(400)
                r2 = next((r for r in pg.query_selector_all("#list .row") if "fat pad (right)" in r.inner_text()), None)
                if r2:
                    r2.scroll_into_view_if_needed(); (r2.tap() if phone else r2.click()); pg.wait_for_timeout(400)
                check(f"{T}: C picking breast_fat_r from the list shows it", api(pg, f"api.visible({idx['breast_fat_r']})"), errs)
                # D
                st = api(pg, "api.pose().stats()")
                rig = api(pg, "(r => ({count: r.count, skinned: r.skin.length, joints: r.joints.map(j => j.id || j.name || j[0])}))(api.pose().rig())")
                check(f"{T}: D pose rig covers the page (count {rig['count']}, skinned {rig['skinned']})", rig["count"] == 1043 and rig["skinned"] == 631 and not st.get("failed"), errs)
                i = idx["breast_ct_r"]
                s0 = api(pg, f"(p => {{ let s = 0; for (let k = 0; k < p.length; k++) s += p[k]; return s; }})(api.geometry({i}).pos)")
                ok = bool(api(pg, "api.pose().setRegion('thoracic', 'flex', 25)"))
                pg.wait_for_timeout(500)
                s1 = api(pg, f"(p => {{ let s = 0; for (let k = 0; k < p.length; k++) s += p[k]; return s; }})(api.geometry({i}).pos)")
                api(pg, "api.pose().reset()"); pg.wait_for_timeout(500)
                s2 = api(pg, f"(p => {{ let s = 0; for (let k = 0; k < p.length; k++) s += p[k]; return s; }})(api.geometry({i}).pos)")
                check(f"{T}: D thoracic flexion 25 deg (set {ok}) moves the right CT breast (vertex sum {s0:.1f} -> {s1:.1f}) and reset restores it ({s2:.1f})",
                      ok and abs(s1 - s0) > 1.0 and abs(s2 - s0) < 1e-3 * max(1.0, abs(s0)), errs)
                check(f"{T}: E 0 page errors ({page_errs[:2]})", not page_errs, errs)
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main():
    errs = []
    run(Path(sys.argv[1]), errs)
    print("ALL OK" if not errs else f"FAILED {len(errs)}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
