#!/usr/bin/env python3
"""Q319.4.iii: a ligament that the literature divides into sub-ligaments is really marked that way on the model.

The owner's example is the ulnar collateral ligament of the thumb MCP joint, "PROPER + ACCESSORY".  The division was
already recorded as cited knowledge in data/anatomy/structure_parts.json, but until this round nothing of the thumb
collaterals was MARKED on any body: the two components sat in `text_only` with "no geometry rule defined for this
part".  Q319 added the `collateral_layer_split` rule (scripts/anatomy/q219/build_geometry.py), which separates the
dorsal proper band from the volar accessory band of this body's own collateral mesh at the published dorso-volar
level of the proper footprint (Carlson 2012).  This script checks, on a BUILT page in headless Chromium, that the
result actually reaches the screen:

  offered   selecting the pooled Z collateral mesh through the page's own list and search shows a Parts row for the
            thumb UCL's proper AND accessory component, each with the `ligament_component` type badge, the "marker"
            badge, and its citations as live PubMed / DOI links -- rendered by the page's own parts UI, not by this
            script;
  badged    the page's own marker records call both placements `rule_based` and carry an error bound, on both sides;
  placed    the two markers are at distinct positions, and the PROPER one is DORSAL to the ACCESSORY one.  The
            dorso-volar sense for that last test is rebuilt here from the page's own served geometry by a
            construction the rule does not use -- the extensor-minus-flexor direction of the thumb's own tendons at
            the joint, with the metacarpal shaft component removed -- so the ordering is not checked against the
            same axis that produced it.  Both an extensor/flexor pollicis longus and an extensor/flexor pollicis
            brevis axis are measured, and both must agree.
  focus     a click on the proper row opens its marker card (the row does not say "text only").

    python3 scripts/anatomy/q319/verify_subligaments_q319.py [build/q309/viewer_zan_atlas ...]

With no argument it checks every restored Base page it finds (build/q309/viewer_zan_atlas = Base male,
build/q309/viewer_base_female = Base female).  `build/` is gitignored: if a page is missing, fetch it back and
restore it with scripts/restore_built_page.py -- this script says so rather than passing silently.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q219"))
import geomlib as G  # noqa: E402

THREE = "/tmp/three_x/package/build/three.min.js"
ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]

PAGES = {"viewer_zan_atlas": "zbase_m", "viewer_base_female": "zbase_f"}
GEOFILE = {"zbase_m": "Q220_parts_zbase_m.json", "zbase_f": "Q220_parts_zbase_f.json"}
POOL = "zan_collateral_metacarpophalangeal_ligaments"
LIST_NAME = "Collateral metacarpophalangeal ligaments"
PROPER = "thumb_mcp_ucl.proper_collateral"
ACCESSORY = "thumb_mcp_ucl.accessory_collateral"
# the thumb's own dorsal / volar structures at the joint; each pair gives one dorso-volar axis
AXES = [("zan_extensor_pollicis_longus", "zan_tendon_sheath_of_flexor_pollicis_longus"),
        ("extensor_pollicis_brevis", "flexor_pollicis_brevis")]


def serve(d: Path):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return srv, p


def route(rq):
    u = rq.request.url
    if "three" in u and u.endswith(".js") and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u):
        if Path(THREE).is_file():
            rq.fulfill(body=open(THREE, "rb").read(), content_type="application/javascript")
        else:
            rq.abort()
    elif "fonts.g" in u:
        rq.abort()
    else:
        rq.continue_()


def check(label, cond, errs):
    ok = bool(cond)
    print(("  OK  " if ok else "  FAIL") + " " + label)
    if not ok:
        errs.append(label)
    return ok


# the page's own Parts card, read out of the DOM the page's own module built
CARD = """(arg) => {
  const sec = document.querySelector('#info .pm-sec');
  if (!sec) return {err: 'the selected structure shows no Parts section'};
  const rows = Array.prototype.map.call(sec.querySelectorAll('.pm-row'), r => ({
    name: (r.querySelector('.pm-nm') || {}).textContent || '',
    type: (r.querySelector('.pm-ty') || {}).className || '',
    typeText: (r.querySelector('.pm-ty') || {}).textContent || '',
    marker: !!r.querySelector('.pm-pl'),
    unverified: !!r.querySelector('.pm-unv'),
    desc: (r.querySelector('.pm-d') || {}).textContent || '',
    cites: Array.prototype.map.call(r.querySelectorAll('.pm-c .pm-ref'), c => c.textContent.trim()),
    links: Array.prototype.map.call(r.querySelectorAll('.pm-c a'), a => a.href),
    pi: +r.getAttribute('data-pi')
  }));
  return {mesh: sec.getAttribute('data-pm-mesh'), rows: rows,
          setNote: Array.prototype.map.call(sec.querySelectorAll('.pm-set'), p => p.textContent.trim())};
}"""

SELECT = """(arg) => {
  const s = document.getElementById('search');
  if (!s) return {err: 'no search box on this page'};
  s.value = arg.q; s.dispatchEvent(new Event('input'));
  const items = Array.prototype.filter.call(document.querySelectorAll('#list .item'),
      b => (b.querySelector('.t') || {}).textContent.trim().toLowerCase() === arg.name.toLowerCase());
  if (!items.length) return {err: 'the page\\'s own structure list has no item named ' + arg.name};
  items[0].click();
  return {clicked: items.length};
}"""

ROWCLICK = """(arg) => {
  const sec = document.querySelector('#info .pm-sec');
  const row = sec && sec.querySelector('.pm-row[data-pi="' + arg.pi + '"]');
  if (!row) return {err: 'row gone'};
  row.click();
  return {msg: (row.querySelector('.pm-msg') || {}).textContent || '', on: row.classList.contains('pm-on')};
}"""


def dorsal_axes(page: Path, jc: np.ndarray, side: str, radius: float = 15.0):
    """Dorso-volar unit axes at the thumb MCP joint, from the PAGE's own served geometry and NOT from the rule's own
    construction: for each (dorsal structure, volar structure) pair, the direction between their local centroids with
    the first metacarpal's shaft component removed.  -> [(name, axis)], and the shaft axis used."""
    m = G.load_zan(page)
    mc = m.get(f"zan_first_metacarpal_bone_{side}")
    pp = m.get(f"zan_proximal_phalanx_of_first_finger_of_hand_{side}")
    if mc is None or pp is None:
        return [], None
    shaft = G.unit(pp["v"].mean(axis=0) - mc["v"].mean(axis=0))
    out = []
    for dn, vn in AXES:
        dm, vm = m.get(f"{dn}_{side}"), m.get(f"{vn}_{side}")
        if dm is None or vm is None:
            continue
        dl = dm["v"][np.linalg.norm(dm["v"] - jc, axis=1) <= radius]
        vl = vm["v"][np.linalg.norm(vm["v"] - jc, axis=1) <= radius]
        if len(dl) < 5 or len(vl) < 5:
            continue
        v = dl.mean(axis=0) - vl.mean(axis=0)
        v = v - (v @ shaft) * shaft
        n = float(np.linalg.norm(v))
        if n < 1e-6:
            continue
        out.append((f"{dn} minus {vn}", v / n))
    return out, shaft


def one(d: Path, errs: list[str]) -> None:
    body = PAGES[d.name]
    print(f"\n=== {d.name} ({body}) ===")
    geo = json.loads((REPO / "data/derived" / GEOFILE[body]).read_text())
    split = [p for p in geo["placed"] if p["rule"] == "collateral_layer_split"]
    print(f"     {GEOFILE[body]}: {len(split)} collateral_layer_split placements, "
          f"{len({p['part_id'] for p in split})} parts")
    pages = sorted(d.glob("atlas_viewer*.html"))
    if not pages:
        errs.append(f"{d.name}: no built page")
        print("  FAIL no atlas_viewer*.html here")
        return
    srv, port = serve(d)
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
            pg = b.new_page(viewport={"width": 1400, "height": 950})
            pg.on("pageerror", lambda e: errs.append(f"{d.name}: page error: {e}"))
            pg.route("**/*", route)
            pg.goto(f"http://127.0.0.1:{port}/{pages[0].name}", wait_until="load", timeout=120000)
            pg.wait_for_function("window.__partsState && window.__partsState().loaded", timeout=120000)
            pg.wait_for_timeout(1500)
            st = pg.evaluate("() => window.__partsState()")
            print(f"     the page's own parts data: {st['parts']} parts, {st['placements']} placed markers")

            # ---- offered: the page's own list -> the page's own Parts card
            r = pg.evaluate(SELECT, {"q": "collateral metacarpophalangeal", "name": LIST_NAME})
            if r.get("err"):
                print("  FAIL " + r["err"]); errs.append(f"{d.name}: {r['err']}"); b.close(); return
            pg.wait_for_timeout(1200)
            card = pg.evaluate(CARD)
            if card.get("err"):
                print("  FAIL " + card["err"]); errs.append(f"{d.name}: {card['err']}"); b.close(); return
            sel = pg.evaluate("() => window.__partsState().sel")
            side = sel["side"]
            print(f"     selected {card['mesh']} (side {side}) -> {len(card['rows'])} Parts rows")
            fromfile = {(p["part_id"], p["side"]): p for p in split}
            rows = {}
            for pid, want in ((PROPER, "proper"), (ACCESSORY, "accessory")):
                row = next((x for x in card["rows"] if f": {want}" in x["name"].lower()
                            and "ulnar collateral" in x["name"].lower()), None)
                rows[pid] = row
                if row:
                    print(f"     row: {row['name']!r}  [{row['typeText']}]"
                          f"{'  marker' if row['marker'] else ''}{'  unverified' if row['unverified'] else ''}")
                    for c in row["cites"]:
                        print(f"            cites {c}")
            check("the thumb UCL's proper AND accessory components are both offered as parts of this mesh",
                  all(rows.values()), errs)
            if not all(rows.values()):
                b.close(); return
            check("both carry the ligament_component type badge the parts UI styles",
                  all("pm-ty-ligament_component" in x["type"] for x in rows.values()), errs)
            check("both carry the 'marker' badge, i.e. the page has a placement for them",
                  all(x["marker"] for x in rows.values()), errs)
            check("both cite their sources on the card, with live PubMed links",
                  all(x["cites"] and any("pubmed" in u for u in x["links"]) for x in rows.values()), errs)
            # the page's own part_set record for this mesh: the UI prints a visible note only where the sources
            # DISAGREE on the count, and they do not here (Patel 2019: two, proper + accessory), so the membership is
            # read from the controller's own `partsFor` rather than from a note that is correctly absent.
            pf = pg.evaluate("(m) => window.__partsCtl.partsFor(m)", card["mesh"])
            mem = [x for x in pf if x["id"] in (PROPER, ACCESSORY)]
            print("     part set on the page: "
                  + "; ".join(f"{x['id'].split('.')[-1]} -> {x['set']} ({x['setName']})" for x in mem))
            check("the page records both as the two members of one cited component set",
                  len(mem) == 2 and len({x["set"] for x in mem}) == 1 and mem[0]["set"] == "thumb_ucl.parts"
                  and all(x["placed"] for x in mem), errs)
            check("and the card says which is dorsal and which is volar",
                  "dorsal" in rows[PROPER]["desc"].lower() and "volar" in rows[ACCESSORY]["desc"].lower()
                  and "palmar" in rows[ACCESSORY]["desc"].lower(), errs)

            # ---- badged: the page's own marker records
            mk = {}
            for m in pg.evaluate("() => window.__partsState().markers"):
                if m["part"] in (PROPER, ACCESSORY):
                    mk.setdefault(m["part"], {})[m["side"]] = m
            print("     markers the page itself reports:")
            for pid in (PROPER, ACCESSORY):
                for sd, m in sorted(mk.get(pid, {}).items()):
                    print(f"       {pid:<36} {sd}  {m['cls']:<10} +/-{m['e']} mm  {m['xyz']}")
            check("the page reports a marker for each component on both sides",
                  all(set(mk.get(p, {})) == {"r", "l"} for p in (PROPER, ACCESSORY)), errs)
            check("every one is badged rule_based (never 'measured') and carries an error bound",
                  all(m["cls"] == "rule_based" and m["e"] and m["e"] > 0
                      for p in (PROPER, ACCESSORY) for m in mk.get(p, {}).values()), errs)
            check("the page's positions are the ones in the placement file",
                  all((p, s) in fromfile and np.allclose(mk[p][s]["xyz"], fromfile[(p, s)]["position_mm"], atol=0.02)
                      for p in (PROPER, ACCESSORY) for s in ("r", "l")), errs)

            # ---- placed: distinct, and the right way round
            for sd in ("r", "l"):
                pr = np.array(mk[PROPER][sd]["xyz"], float)
                ac = np.array(mk[ACCESSORY][sd]["xyz"], float)
                sep = float(np.linalg.norm(pr - ac))
                check(f"[{sd}] the two components sit at distinct positions ({sep:.2f} mm apart)", sep > 1.0, errs)
                axes, _ = dorsal_axes(pages[0], (pr + ac) / 2, sd)
                if not axes:
                    print("  FAIL no independent dorso-volar axis could be built from this page's own geometry")
                    errs.append(f"{d.name}[{sd}]: no independent dorso-volar axis")
                    continue
                vals = []
                for nm, ax in axes:
                    v = float(ax @ (pr - ac))
                    vals.append(v)
                    print(f"       [{sd}] along the '{nm}' dorsal axis: proper is {v:+.2f} mm of the accessory")
                check(f"[{sd}] the PROPER component is dorsal to the ACCESSORY one, on every independent axis "
                      f"({', '.join(f'{v:+.2f}' for v in vals)} mm)", all(v > 0.25 for v in vals), errs)

            # ---- focus: a real row click finds the marker rather than saying "text only"
            rc = pg.evaluate(ROWCLICK, {"pi": rows[PROPER]["pi"]})
            pg.wait_for_timeout(900)
            after = pg.evaluate("() => window.__partsState()")
            print(f"     clicking the proper row: message {rc.get('msg','')!r}, focused marker index {after['focus']}")
            check("clicking the proper component's row focuses its marker (not 'text only')",
                  "text only" not in (rc.get("msg") or "").lower() and after["focus"] >= 0, errs)
            b.close()
    finally:
        srv.terminate()


def main() -> int:
    args = sys.argv[1:]
    dirs = [Path(a) if Path(a).is_absolute() else REPO / a for a in args] or \
        [REPO / "build/q309" / n for n in PAGES]
    errs: list[str] = []
    for d in dirs:
        if d.name not in PAGES:
            print(f"  (skipping {d}: not one of the Base pages this check knows)")
            continue
        if not d.is_dir() or not sorted(d.glob("atlas_viewer*.html")):
            print(f"\n=== {d.name} ===\n  NOT CHECKED: no built page in {d}. `build/` is gitignored; fetch the page "
                  f"back from its published artifact and run scripts/restore_built_page.py {d}.")
            errs.append(f"{d.name}: no built page, so this page was NOT checked")
            continue
        one(d, errs)
    print()
    if errs:
        print(f"Q319_SUBLIGAMENTS_FAIL {len(errs)}")
        for e in errs:
            print("  - " + e)
        return 1
    print("Q319_SUBLIGAMENTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
