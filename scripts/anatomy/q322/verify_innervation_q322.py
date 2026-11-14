#!/usr/bin/env python3
"""Q322: the MUSCLE INNERVATION mode, measured in a real Chromium on a Z-engine Base page, at 1400x900 and 390x844.

    python3 scripts/anatomy/q322/verify_innervation_q322.py build/q309/viewer_zan_atlas [--no-patch] [--size WxH ...]

A built page that predates the change is copied to /dev/shm/q319v_q322src_<dir> (sidecars symlinked) and patched by the same
fragments the source edits make (the Q319 selection controller and the Q321 quick card if missing, the shared modes fragment,
the Q322 module), and the
page's sidecar innervation_q322.json is written next to it by scripts/anatomy/q322/build_sidecar_q322.py.
Checks: the mode registers and is entered from the switcher; colour by nerve trunk and by root level (the selection
controller's per-structure colours); a root chip marks the muscles it supplies; a nerve marks its muscles; a real click
on a muscle selects it, the quick card opens, the panel shows the sidecar's nerve / roots / IZ bands and sits beside the
model; the IZ markers of its placed bands are drawn (pixels); exit restores colours and layers; 0 page errors.
Prints OK / FAIL lines and Q322_INNERVATION_OK / Q322_INNERVATION_FAIL."""
from __future__ import annotations

import base64
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q319"))
import verify_search_q319 as V            # noqa: E402  (serve / route / open_page / check / ERRS)
from playwright.sync_api import sync_playwright  # noqa: E402

ERRS = V.ERRS
check = V.check
PAGE_KEY = {"viewer_zan_atlas": "base_m", "viewer_base_female": "base_f"}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def page_copy(src: Path, patch: bool) -> Path:
    # the Q319 patched copy (selection controller + top row + colour glue when the page predates them), made under a name of
    # this round's own so that another round's verifier on the same page dir is not disturbed: /dev/shm/q319v_q322src_<dir>
    link = Path("/dev/shm") / ("q322src_" + src.name)
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(src)
    dst = V.patched_copy(link, patch)
    sc = _load("sc322", REPO / "scripts/anatomy/q322/build_sidecar_q322.py")
    out = dst / sc.NAME
    if out.is_symlink() or out.exists():
        out.unlink()
    out.write_text(json.dumps(sc.build(PAGE_KEY[src.name]), ensure_ascii=False), encoding="utf-8")
    if patch:
        s321 = _load("s321", REPO / "scripts/sync_quickcard_q321.py")
        p321 = _load("p321", REPO / "scripts/anatomy/q321/patch_q321.py")
        smod = _load("smod", REPO / "scripts/sync_modes_q272.py")
        s322 = _load("s322", REPO / "scripts/sync_innervation_q322.py")
        for f in dst.glob("*.html"):
            t = f.read_text(encoding="utf-8")
            if "NMSKQuickCard" not in t:
                t = p321.apply(s321.render(t))
            t = s322.render(smod.render(t, "zan"))
            f.write_text(t, encoding="utf-8")
    return dst


def ov(a, b, pad=0):
    return a["l"] < b["r"] + pad and a["r"] > b["l"] - pad and a["t"] < b["b"] + pad and a["b"] > b["t"] - pad


RECT = "(e) => { if (!e) return null; const r = e.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height}; }"


def st(pg):
    return pg.evaluate("() => window.__innState()")


def sel_state(pg):
    return pg.evaluate("() => { const s = NMSKSelectCtl.state(); return {marks: s.marks, oth: s.oth, sel: s.sel, own: NMSKSelectCtl.colourState().ids}; }")


def yellow_near(pg, x, y, r=14):
    """Count marker-yellow pixels in a screenshot square around (x, y) (decoded inside the browser: no imaging library)."""
    vw, vh = pg.viewport_size["width"], pg.viewport_size["height"]
    x0, y0 = max(0, x - r), max(0, y - r)
    png = pg.screenshot(clip={"x": x0, "y": y0, "width": min(2 * r, vw - x0), "height": min(2 * r, vh - y0)})
    return pg.evaluate("""async (b64) => { const img = new Image(); img.src = 'data:image/png;base64,' + b64; await img.decode();
      const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.drawImage(img, 0, 0);
      const d = g.getImageData(0, 0, c.width, c.height).data; let n = 0;
      for (let i = 0; i < d.length; i += 4) if (d[i] > 200 && d[i + 1] > 170 && d[i + 2] < 140) n++;
      return n; }""", base64.b64encode(png).decode())


def run_size(pl, d: Path, w: int, h: int, tag: str, D: dict):
    print(f"--- {tag} {w}x{h}")
    n0 = len(ERRS)
    srv, b, pg = V.open_page(pl, d, w, h)
    T = f"[{tag} {w}]"
    try:
        pg.wait_for_function("window.__innState && __innState().loaded && __modesState().registered.indexOf('inn') >= 0", timeout=60000)
        check(f"{T} mode registered from the page's sidecar ({D['counts']['placed']} placed bands in it)", True)
        before = pg.evaluate("() => ({own: Object.keys(NMSKSelectCtl.colourState().ids).length, marks: NMSKSelectCtl.state().marks.length})")
        # ---- enter from the switcher
        pg.evaluate("() => NMSKModes.show()"); pg.wait_for_timeout(300)
        tile = pg.evaluate("() => { const t = document.querySelector('.mw-tile[data-mode=inn]'); return t ? {dis: t.hasAttribute('disabled'), txt: t.textContent} : null; }")
        check(f"{T} switcher tile present and enabled ({tile and tile['txt'][:20]})", tile is not None and not tile["dis"])
        pg.evaluate("() => document.querySelector('.mw-tile[data-mode=inn]').click()"); pg.wait_for_timeout(1500)
        s = st(pg)
        check(f"{T} mode entered (cur={pg.evaluate('() => __modesState().cur')}, body.mode-inn)", s["on"] and pg.evaluate("() => document.body.classList.contains('mode-inn')"))
        # ---- colour by nerve
        trunks = {t["key"]: t for t in D["trunks"]}
        bic = "biceps_brachii_l"
        col = sel_state(pg)["own"]
        want = trunks[D["muscles"]["biceps_brachii"]["trunks"][0]]["colour"]
        check(f"{T} by nerve: biceps coloured by its trunk ({col.get(bic)} == {want})", col.get(bic) == want)
        nchips = pg.evaluate("() => document.querySelectorAll('.inn-legend .inn-chip[data-kind=trunk]').length")
        n_tr = sum(1 for t in D["trunks"] if any(t["key"] in m["trunks"] for m in D["muscles"].values()))
        check(f"{T} by nerve: legend has one chip per trunk ({nchips} == {n_tr})", nchips == n_tr)
        grey = [k for k, v in col.items() if v == "#9aa3ab"]
        rec_ids = {i for m in D["muscles"].values() for i in m["structures"]}
        check(f"{T} muscles without a record stay grey ({len(grey)}), none of the recorded ones", len(grey) > 0 and not (set(grey) & rec_ids))
        # trunk chip -> its muscles marked, the rest faded
        tk = "musculocutaneous"
        pg.evaluate(f"() => document.querySelector('.inn-chip[data-key={tk}]').click()"); pg.wait_for_timeout(400)
        ss = sel_state(pg)
        exp = sorted(i for k, m in D["muscles"].items() if tk in m["trunks"] for i in m["structures"])
        got = sorted(i for i in ss["marks"] if i in exp)
        check(f"{T} trunk chip '{tk}': its {len(exp)} muscle structures marked (+{len(ss['marks']) - len(got)} nerve), others faded ({ss['oth']})", got == exp and ss["oth"] == "fade")
        pg.evaluate(f"() => document.querySelector('.inn-chip[data-key={tk}]').click()"); pg.wait_for_timeout(300)
        check(f"{T} pressing the chip again clears the marks", len(sel_state(pg)["marks"]) == 0)
        # ---- colour by root, pick a root
        pg.evaluate("() => document.querySelector('.inn-ctl [data-by=root]').click()"); pg.wait_for_timeout(500)
        col = sel_state(pg)["own"]
        rc = {r["level"]: r["colour"] for r in D["roots"]}
        ad = D["muscles"]["biceps_brachii"]["roots"]["adopted"]
        mid = ad[(len(ad) - 1) // 2]
        check(f"{T} by root: biceps ({'-'.join(ad)}) coloured by its middle level {mid} ({col.get(bic)} == {rc[mid]})", col.get(bic) == rc[mid])
        lv = "C5"
        pg.evaluate(f"() => document.querySelector('.inn-chip[data-kind=root][data-key={lv}]').click()"); pg.wait_for_timeout(400)
        ss = sel_state(pg)
        exp = sorted(i for k, m in D["muscles"].items() if lv in m["roots"]["adopted"] for i in m["structures"])
        check(f"{T} root {lv}: the {len(exp)} structures of the muscles it supplies are marked, others faded", sorted(ss["marks"]) == exp and ss["oth"] == "fade")
        names = pg.evaluate("() => [...document.querySelectorAll('.inn-panel [data-inn=mlist] button')].map(b => b.textContent)")
        check(f"{T} root {lv}: panel lists {len(names)} muscles", len(names) == len({k for k, m in D["muscles"].items() if lv in m["roots"]["adopted"]}))
        pg.evaluate("() => document.querySelector('.inn-ctl [data-by=nerve]').click()"); pg.wait_for_timeout(400)
        check(f"{T} back to colour by nerve", sel_state(pg)["own"].get(bic) == want and len(sel_state(pg)["marks"]) == 0)
        # ---- a nerve selected on the model -> its muscles marked (the page's own select, as a click on it does)
        nv = "musculocutaneous_n_l"
        pg.evaluate(f"() => NMSKInnervation.select('{nv}')")
        try:
            pg.wait_for_function("() => NMSKSelectCtl.state().marks.length > 0", timeout=4000)
        except Exception:
            pass
        pg.wait_for_timeout(300)
        ss = sel_state(pg)
        exp = sorted([i for k, m in D["muscles"].items() if (nv in m["nerve_structures"] or "musculocutaneous_n" in m["chain"]) for i in m["structures"] if i.endswith("_l")] + [nv])
        check(f"{T} nerve {nv}: marks {sorted(ss['marks'])} (expected {exp}), others faded [{st(pg)['pick']} sel={pg.evaluate('() => __modesState().selected')}]", sorted(ss["marks"]) == exp and ss["oth"] == "fade")
        check(f"{T} nerve: panel shows its muscles", st(pg)["view"] and st(pg)["view"]["kind"] == "nerve")
        # ---- a real click on a muscle: selection, quick card, panel, IZ markers
        target = "biceps_brachii_r"
        pt = pg.evaluate(f"() => NMSKInnervation.screenOf('{target}')")
        hit = None
        if pt:
            for dx, dy in [(0, 0), (0, -8), (0, 8), (-6, 0), (6, 0), (0, -16), (0, 16), (-4, -12), (4, 12)]:
                x, y = pt[0] + dx, pt[1] + dy
                if not pg.evaluate(f"() => {{ const e = document.elementFromPoint({x}, {y}); return !!e && e.tagName === 'CANVAS'; }}"):
                    continue
                pg.mouse.click(x, y); pg.wait_for_timeout(700)
                v = st(pg)["view"]
                if v and v["kind"] == "muscle" and v["key"] == "biceps_brachii":
                    hit = (x, y); break
        check(f"{T} a real click on the biceps selects it ({hit and [round(c) for c in hit]})", hit is not None)
        if hit:
            card = pg.evaluate("() => { const c = document.querySelector('.qc'); return c && !c.hidden ? c.querySelector('.qc-name').textContent : null; }")
            check(f"{T} the quick card still opens on the click ('{card}')", bool(card))
            cov = pg.evaluate("""() => [...document.querySelectorAll('.qc .qc-b')].filter(b => { const r = b.getBoundingClientRect();
              const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !(e && e.closest('.qc')); }).map(b => b.textContent)""")
            check(f"{T} nothing covers the quick card's buttons{' ' + str(cov) if cov else ''}", not cov)
            m = D["muscles"]["biceps_brachii"]
            pan = pg.evaluate("""() => { const p = document.querySelector('.inn-panel'); const q = s => { const e = p.querySelector(s); return e ? e.textContent : null; };
              return {name: q('[data-inn=muscle-name]'), nerve: q('[data-inn=nerve]'), roots: [...p.querySelectorAll('[data-inn=roots] .inn-tag')].map(e => e.textContent),
                      range: q('[data-inn=range]'), bands: p.querySelectorAll('[data-inn-band]').length, badges: [...p.querySelectorAll('.inn-band .inn-badge')].map(e => e.textContent),
                      agree: p.querySelectorAll('[data-inn=agree] li').length, cites: [...p.querySelectorAll('.inn-band .inn-cite')].map(e => e.textContent)}; }""")
            check(f"{T} panel name '{pan['name']}'", pan["name"] and pan["name"].startswith(m["name"]))
            check(f"{T} panel nerve '{pan['nerve']}'", pan["nerve"] == " + ".join(n["label"] for n in m["nerve"]))
            check(f"{T} panel roots {pan['roots']} / '{pan['range']}'", pan["roots"] == m["roots"]["adopted"] and (m["roots"]["range"] or "") in pan["range"])
            nb = [b for b in D["bands"] if b["m"] == "biceps_brachii" and b["s"] == "r"]
            check(f"{T} panel IZ bands {pan['bands']} == json {len(m['iz'])}; badges {pan['badges']}", pan["bands"] == len(m["iz"]) and
                  pan["badges"].count("rule-based") == sum(1 for b in nb if b["st"] == "placed"))
            check(f"{T} panel band citations name the source + table ({pan['cites'][:1]})", all("Table" in c for c in pan["cites"]))
            check(f"{T} panel lists the same-line sources ({pan['agree']})", pan["agree"] == sum(1 for o in m["iz_other"] if o["agreement"] != "not_comparable"))
            # beside the model, sized to content
            side = pg.evaluate(f"() => ({RECT})(document.querySelector('.inn-side'))")
            card_r = pg.evaluate(f"() => ({RECT})(document.querySelector('.inn-panel'))")
            cv = pg.evaluate(f"() => ({RECT})(document.querySelector('canvas'))")
            check(f"{T} after the click the panel's top is in view ({card_r['t']:.0f} < {h})", card_r["t"] < h - 40)
            check(f"{T} panel beside the model, not on it (panel {[round(card_r[k]) for k in 'ltrb']}, model {[round(cv[k]) for k in 'ltrb']})", not ov(card_r, cv))
            fit = pg.evaluate("() => { const p = document.querySelector('.inn-panel'); return {sh: p.scrollHeight, ch: p.clientHeight, sw: p.scrollWidth, cw: p.clientWidth}; }")
            check(f"{T} panel sized to its content (h {fit['ch']} = content {fit['sh']}, no horizontal overflow)", fit["sh"] <= fit["ch"] + 1 and fit["sw"] <= fit["cw"] + 1)
            if w >= 1000:
                check(f"{T} side column width {side['w']:.0f}px", side["w"] <= 360)
            # IZ markers
            pg.wait_for_timeout(500)
            s2 = st(pg)
            expect_drawn = len([b for b in nb if b["st"] in ("placed", "qualitative") and b.get("same_as") is None])
            check(f"{T} IZ markers drawn for the placed bands: {s2['drawn']} (expected {expect_drawn} band(s)), {s2['tags']} badge(s)", s2["drawn"]["bands"] == expect_drawn and s2["tags"] == expect_drawn)
            tags = pg.evaluate("() => [...document.querySelectorAll('.inn-mk')].filter(e => e.style.display !== 'none').map(e => ({x: parseFloat(e.style.left), y: parseFloat(e.style.top), t: e.textContent, title: e.title}))")
            if tags:
                y0 = yellow_near(pg, int(tags[0]["x"]), int(tags[0]["y"]))
                check(f"{T} marker drawn on the canvas at its dot ({y0} yellow px); badge '{tags[0]['t']}'", y0 >= 6 and "rule-based" in tags[0]["t"])
                check(f"{T} badge tooltip carries the citation", "Güvener" in tags[0]["title"] and "rule-based" in tags[0]["title"])
            pg.evaluate("() => document.querySelector('.inn-ctl [data-iz=all]').click()"); pg.wait_for_timeout(600)
            n_all = st(pg)["drawn"]["bands"]
            check(f"{T} 'All' draws every visible placed band ({n_all})", n_all > expect_drawn)
            pg.evaluate("() => document.querySelector('.inn-ctl [data-iz=sel]').click()"); pg.wait_for_timeout(300)
        # ---- exit restores the anatomy screen
        pg.evaluate("() => { const b = document.getElementById(window.innerWidth <= 760 ? 'mb-exit-x' : 'mb-exit'); b.click(); }"); pg.wait_for_timeout(1500)
        after = pg.evaluate("() => ({own: Object.keys(NMSKSelectCtl.colourState().ids).length, marks: NMSKSelectCtl.state().marks.length, on: __innState().on, cur: __modesState().cur})")
        check(f"{T} exit: colours and marks back ({after}), mode off", after["own"] == before["own"] and after["marks"] == before["marks"] and not after["on"] and after["cur"] is None)
        check(f"{T} exit: no marker left on screen", st(pg)["tags"] == 0)
    finally:
        b.close(); srv.terminate()
    check(f"{T} 0 page errors", not any(e.startswith("page error") for e in ERRS[n0:]))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sizes = [(1400, 900), (390, 844)]
    if "--size" in sys.argv:
        sizes = [tuple(int(v) for v in a.split("x")) for a in sys.argv[sys.argv.index("--size") + 1:] if re.match(r"\d+x\d+$", a)]
        args = [a for a in args if not re.match(r"\d+x\d+$", a)]
    src = Path(args[0]) if args else REPO / "build/q309/viewer_zan_atlas"
    d = page_copy(src.resolve(), "--no-patch" not in sys.argv)
    D = json.loads((d / "innervation_q322.json").read_text(encoding="utf-8"))
    with sync_playwright() as pl:
        for w, h in sizes:
            run_size(pl, d, w, h, src.name, D)
    print("Q322_INNERVATION_FAIL" if ERRS else "Q322_INNERVATION_OK")
    for e in ERRS:
        print("   ", e)
    return 1 if ERRS else 0


if __name__ == "__main__":
    raise SystemExit(main())
