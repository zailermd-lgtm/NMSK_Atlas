#!/usr/bin/env python3
"""Q286: real headless-Chromium check of the new CT structures on the Imaging-based pages (desktop click 1400x900 + phone touch 390x844).

A  every shipped Q286 item (build/vh/<subject>/items.json) is in the page under its Q286 subject; added ones are drawn with their layer on
B  one new structure is found through the real structure list (search box + row) and its card shows the Q286 badge and 'Measured on this body'
C  replaced items (male optic nerve, held-level discs) carry the new subject, not the old one
D  the pose rig covers the page (count = committed + added) and cervical flexion moves a new head structure; reset restores it exactly
E  0 page errors

    python3 scripts/anatomy/q286/verify_q286.py own_m|own_f PAGE_DIR
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap, api = V.check, V.tap, V.api
SUBJ = {"own_m": ["ct_vhm_hgc", "ct_vhm_disc_ts"], "own_f": ["ct_vhf_hgc", "ct_vhf_disc_ts"]}


def items(key):
    out = []
    for s in SUBJ[key]:
        f = REPO / "build/vh" / s / "items.json"
        if f.exists():
            out += [dict(it, subject=s) for it in json.loads(f.read_text())]
    return out


def run(key, page_dir: Path, errs: list):
    its = items(key)
    added = [it for it in its if not it["replace"]]
    probe = next(it for it in added if it["rec"]["region"] == "head")
    rig_c = json.loads((REPO / f"data/anatomy/pose_rig_{key}.json").read_text())["rig"]["count"]
    html = V.html_of(page_dir)
    srv, port = V.serve(page_dir)
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            for (w, h), phone in ((1400, 900), False), ((390, 844), True):
                T = f"{key}_{w}"
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page(); page_errs = []
                pg.on("pageerror", lambda e: page_errs.append(str(e)))
                pg.route("**/*", V.route)
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=90000)
                V.ready(pg)
                ids = [it["id"] for it in its]
                rows = api(pg, "Object.fromEntries(api.list().filter(r => " + json.dumps(ids) + ".includes(r.id)).map(r => [r.id, [r.i]]))")
                check(f"{T}: A all {len(ids)} Q286 items in the page", all(i in rows for i in ids), errs)
                for c in ("organ", "nerve", "cartilage"):
                    api(pg, f"api.setCategoryOn('{c}', true)")
                vis = [api(pg, f"api.visible({rows[it['id']][0]})") for it in added if it["id"] in rows]
                check(f"{T}: A added items drawn {vis}", all(vis), errs)
                # B: through the real list
                if phone and pg.is_visible("#m-list"):
                    tap(pg, "#m-list", phone); pg.wait_for_timeout(300)
                for _ in range(2):
                    if pg.is_visible("#q") or not pg.is_visible("#t-lay3"):
                        break
                    tap(pg, "#t-lay3", phone); pg.wait_for_timeout(300)
                    if phone and pg.is_visible("#m-list") and not pg.is_visible("#q"):
                        tap(pg, "#m-list", phone); pg.wait_for_timeout(300)
                pg.fill("#q", probe["rec"]["name"]); pg.wait_for_timeout(400)
                hit = next((r for r in pg.query_selector_all("#list .row") if probe["rec"]["name"] in r.inner_text()), None)
                check(f"{T}: B the list search finds {probe['rec']['name']!r}", hit is not None, errs)
                if hit:
                    hit.scroll_into_view_if_needed(); (hit.tap() if phone else hit.click()); pg.wait_for_timeout(500)
                sel = api(pg, "api.selectedId()")
                card = pg.evaluate("() => (document.getElementById('i-name').textContent || '') + ' | ' + (document.getElementById('i-tags').textContent || '') + ' | ' + (document.getElementById('i-body').textContent || '')")
                src = pg.evaluate("() => document.getElementById('i-src').textContent || ''")
                check(f"{T}: B card open for {sel}", sel == probe["id"], errs)
                check(f"{T}: B badge names the Q286 task and the Source line says measured ({src[:30]!r})",
                      "Q286" in card and "head_glands_cavities" in card and src.startswith("Measured on this body"), errs)
                # C
                rep = [it for it in its if it["replace"]]
                got = {}
                for it in rep:                           # through the real list, as for B
                    if phone and not pg.is_visible("#q") and pg.is_visible("#m-list"):
                        tap(pg, "#m-list", phone); pg.wait_for_timeout(300)
                    pg.fill("#q", it["rec"]["name"]); pg.wait_for_timeout(400)
                    r2 = next((r for r in pg.query_selector_all("#list .row") if it["rec"]["name"] in r.inner_text()), None)
                    if r2:
                        r2.scroll_into_view_if_needed(); (r2.tap() if phone else r2.click()); pg.wait_for_timeout(400)
                    got[it["id"]] = api(pg, "api.selectedId()") == it["id"] and "Q286" in pg.evaluate("() => (document.getElementById('i-tags').textContent || '') + (document.getElementById('i-body').textContent || '')")
                check(f"{T}: C replaced items show the Q286 badge {got}", all(got.values()), errs)
                # D
                rig = api(pg, "(r => ({count: r.count, skinned: r.skin.length}))(api.pose().rig())")
                check(f"{T}: D pose rig count {rig['count']} = committed {rig_c}", rig["count"] == rig_c, errs)
                i = rows[probe["id"]][0]
                s = "(p => { let s = 0; for (let k = 0; k < p.length; k++) s += p[k]; return s; })(api.geometry(%d).pos)" % i
                s0 = api(pg, s); ok = bool(api(pg, "api.pose().setRegion('cervical', 'flex', 25)")); pg.wait_for_timeout(500)
                s1 = api(pg, s); api(pg, "api.pose().reset()"); pg.wait_for_timeout(500); s2 = api(pg, s)
                check(f"{T}: D cervical flexion 25 deg (set {ok}) moves {probe['id']} ({s0:.1f} -> {s1:.1f}) and reset restores it ({s2:.1f})",
                      ok and abs(s1 - s0) > 1.0 and abs(s2 - s0) < 1e-3 * max(1.0, abs(s0)), errs)
                check(f"{T}: E 0 page errors ({page_errs[:2]})", not page_errs, errs)
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main():
    errs = []
    run(sys.argv[1], Path(sys.argv[2]), errs)
    print("ALL OK" if not errs else f"FAILED {len(errs)}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
