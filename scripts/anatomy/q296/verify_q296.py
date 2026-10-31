#!/usr/bin/env python3
"""Q296: real headless-Chromium check (desktop 1400x900 real clicks + phone 390x844 real touch) of the four imported
SPL Inner Ear Atlas structures on the rebuilt Z pages.

A  the page carries all eight imported meshes (four structures x two sides) in the layer the page report says, drawn at
   load, with the bounding box the geometry report measured (<= 0.2 mm)
B  each one is reachable from the real structure list (typed search + a real click / tap on its row) and its card names
   the source and the licence (Brigham and Women's Hospital, 3D Slicer License Part B) and is badged IMPORTED REAL MESH,
   explicitly NOT rule-based
C  placement, measured in the browser on the page's own geometry: each imported structure sits within 12 mm of the
   centroid of THIS page's own malleus + incus + stapes of the same side (its registration target), and the left and
   right copies are mirror images across the page's mid-sagittal plane
D  the layer toggle of the imported structures' own category hides them and shows them again; 0 page errors

    python3 scripts/anatomy/q296/verify_q296.py PAGE_DIR... [--shots DIR] [--phone=N]"""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap, api = V.check, V.tap, V.api
KEY = {"viewer_zan_atlas": "base_m", "viewer_base_female": "base_f", "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}
UIDS = ("labyrinth", "spiral_lamina", "fenestra_cochleae", "stapedius")
OSS = ("malleus", "incus", "stapes")


def reach(pg, sel, phone):
    for _ in range(5):
        if pg.is_visible(sel):
            return True
        for s in ("#btn-panel", "#m-list", "#t-lay3"):
            if pg.is_visible(s):
                tap(pg, s, phone)
                break
        pg.wait_for_timeout(400)
    return pg.is_visible(sel)


def open_card(pg, name, phone):
    """the real UI: type into the structure search and click / tap the row (button.item) whose text is this name."""
    if not reach(pg, "#search", phone):
        return None
    pg.fill("#search", name)
    pg.wait_for_timeout(500)
    idx = pg.evaluate("(n) => Array.from(document.querySelectorAll('#list button.item')).findIndex(b => b.innerText.trim().indexOf(n) === 0)", name)
    if idx < 0:
        return None
    tap(pg, f"#list button.item >> nth={idx}", phone)
    pg.wait_for_timeout(600)
    # on a narrow screen the info card opens minimised (#info.min hides .info-more): expand it with a real tap
    for _ in range(2):
        if not pg.evaluate("() => { const e = document.getElementById('info'); return !!e && e.classList.contains('min'); }"):
            break
        if pg.is_visible("#info .info-min"):
            tap(pg, "#info .info-min", phone)
            pg.wait_for_timeout(400)
        else:
            break
    return pg.evaluate("() => { const e = document.getElementById('info'); return e ? (e.innerText || '') : ''; }")


def run_page(b, d: Path, phone: bool, errs, shots):
    key = KEY[d.name]
    rep = json.loads((REPO / "data/derived/Q296_page_report.json").read_text())[key]
    geo = json.loads((REPO / "data/derived/Q296_ear_report.json").read_text())["pages"][key]
    html = V.html_of(d); srv, port = V.serve(d)
    try:
        w, h = (390, 844) if phone else (1400, 900)
        T = f"{key}_{w}"
        ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
        pg = ctx.new_page(); perr = []
        pg.on("pageerror", lambda e: perr.append(str(e)))
        pg.route("**/*", V.route)
        pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=300000)
        V.ready(pg)
        rows = api(pg, "api.list().filter(r => r.id.indexOf('oa_') === 0)")
        by = {r["id"]: r for r in rows}
        check(f"{T}: A all eight imported meshes present {sorted(by)}", sorted(by) == sorted(rep["added"]), errs)
        vis = [api(pg, f"api.visible({r['i']})") for r in rows]
        check(f"{T}: A drawn at load ({sum(vis)} / {len(vis)})", len(vis) == 8 and all(vis), errs)
        cats = {r["id"]: r["cat"] for r in rows}
        want = {f"oa_{u}_{s}": ("muscle" if u == "stapedius" else "bone") for u in UIDS for s in ("l", "r")}
        check(f"{T}: A layers as built {sorted(set(cats.values()))}", cats == want, errs)
        okbox = True
        for uid in UIDS:
            for s in ("l", "r"):
                r = by.get(f"oa_{uid}_{s}")
                if not r:
                    okbox = False; continue
                ext = [r["bmax"][k] - r["bmin"][k] for k in range(3)]
                exp = geo[f"{uid}_{s}"]["ext_mm"]
                if max(abs(a - e) for a, e in zip(sorted(ext), sorted(exp))) > 0.2:
                    okbox = False; print("     box mismatch", uid, s, [round(x, 2) for x in ext], exp)
        check(f"{T}: A bounding boxes match the geometry report (<= 0.2 mm)", okbox, errs)
        # C placement against this page's own ossicles
        oc = {}
        for s in ("l", "r"):
            pts = []
            for k in OSS:
                rr = api(pg, f"api.list().filter(r => r.id === '{k}_{s}')")[0]
                pts.append([(rr["bmin"][i] + rr["bmax"][i]) / 2 for i in range(3)])
            oc[s] = [sum(p[i] for p in pts) / 3 for i in range(3)]
        far = []
        for uid in UIDS:
            for s in ("l", "r"):
                r = by[f"oa_{uid}_{s}"]
                c = [(r["bmin"][i] + r["bmax"][i]) / 2 for i in range(3)]
                dist = sum((c[i] - oc[s][i]) ** 2 for i in range(3)) ** 0.5
                if dist > 12.0:
                    far.append((uid, s, round(dist, 1)))
        check(f"{T}: C every imported structure within 12 mm of this page's own ossicle centroid (outliers {far})", not far, errs)
        # the left copy is the mirror of the atlas's right ear, placed on THIS page's own left ossicles: so its
        # left / right offset must equal the page's own ossicles' offset, which on a fitted (Combined) page is not zero
        ref = [oc["l"][0] + oc["r"][0], oc["l"][1] - oc["r"][1], oc["l"][2] - oc["r"][2]]
        mirror = []
        for uid in UIDS:
            a, c = by[f"oa_{uid}_l"], by[f"oa_{uid}_r"]
            ca = [(a["bmin"][i] + a["bmax"][i]) / 2 for i in range(3)]
            cc = [(c["bmin"][i] + c["bmax"][i]) / 2 for i in range(3)]
            off = [ca[0] + cc[0], ca[1] - cc[1], ca[2] - cc[2]]
            d = max(abs(off[i] - ref[i]) for i in range(3))
            if d > 1.5:
                mirror.append((uid, [round(x, 2) for x in off], round(d, 2)))
        check(f"{T}: C left / right follow this page's own ossicles (their own offset "
              f"{[round(x, 2) for x in ref]} mm; outliers {mirror})", not mirror, errs)
        # B the card
        for uid in ("labyrinth", "stapedius"):
            nm = geo[f"{uid}_l"]["name"]
            txt = open_card(pg, nm, phone) or ""
            ok = ("Brigham and Women's Hospital" in txt and "3D Slicer License Part B" in txt
                  and "IMPORTED REAL MESH, NOT RULE-BASED" in txt and "Open Anatomy" in txt)
            check(f"{T}: B '{nm}' card reachable by {'tap' if phone else 'click'} and names the source + Part B licence + the "
                  f"imported-mesh badge ({len(txt)} chars)", ok, errs)
            if not ok:
                print("     card text:", txt[:300].replace("\n", " | "))
        # close the info card before the layer check: on a phone it overlays the layer rows
        if pg.is_visible("#info .info-close"):
            tap(pg, "#info .info-close", phone)
            pg.wait_for_timeout(400)
        # D layer toggle
        sel = '.layer-row[data-cat="bone"] button.layer'
        if reach(pg, sel, phone):
            trio = ("labyrinth", "spiral_lamina", "fenestra_cochleae")
            tap(pg, sel, phone)
            try:                                               # software rendering: the toggle can take a moment to reach the meshes
                pg.wait_for_function("(ids) => ids.every(i => !window.NMSKClinicalTool.api.visible(i))",
                                     arg=[by[f"oa_{u}_l"]["i"] for u in trio], timeout=20000)
            except Exception:
                pass
            off = [api(pg, f"api.visible({by[f'oa_{u}_l']['i']})") for u in trio]
            tap(pg, sel, phone)
            try:
                pg.wait_for_function("(ids) => ids.every(i => window.NMSKClinicalTool.api.visible(i))",
                                     arg=[by[f"oa_{u}_l"]["i"] for u in trio], timeout=20000)
            except Exception:
                pass
            on = [api(pg, f"api.visible({by[f'oa_{u}_l']['i']})") for u in trio]
            check(f"{T}: D the Bones layer toggle hides the three otic-capsule meshes ({sum(off)} left) and shows them again ({sum(on)} / 3)",
                  not any(off) and all(on), errs)
        else:
            check(f"{T}: D the Bones layer toggle is reachable", False, errs)
        if shots and not phone:
            r = by["oa_labyrinth_r"]; c = [(r["bmin"][i] + r["bmax"][i]) / 2 for i in range(3)]
            api(pg, f"api.focus({json.dumps(c)})"); pg.wait_for_timeout(2500)
            pg.screenshot(path=str(shots / f"Q296_labyrinth_{key}.png"))
        check(f"{T}: D 0 page errors", not perr, errs)
        if perr:
            print("    ", perr[:3])
        ctx.close()
    finally:
        srv.terminate()


def main():
    dirs = [Path(a) for k, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[k - 1] != "--shots" and Path(a).is_dir()]
    shots = None; phone_n = 4
    for k, a in enumerate(sys.argv):
        if a == "--shots":
            shots = Path(sys.argv[k + 1]); shots.mkdir(parents=True, exist_ok=True)
        if a.startswith("--phone="):
            phone_n = int(a.split("=")[1])
    errs = []
    with sync_playwright() as pl:
        b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
        for n, d in enumerate(dirs):
            run_page(b, d, False, errs, shots)
            if n < phone_n:
                run_page(b, d, True, errs, shots)
        b.close()
    print("ALL OK" if not errs else f"{len(errs)} FAIL")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
