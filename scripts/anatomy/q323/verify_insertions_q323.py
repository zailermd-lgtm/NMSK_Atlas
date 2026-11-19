#!/usr/bin/env python3
"""Q323: the "insertions" preset shows the ATTACHMENTS (origins AND insertions) of the structures, by tissue class, by choice.

Owner, 2026-11-14: "The INSERTION mode should already show the origins and insertions of the muscles and tendons. Make sure it
actually works. It can also show the attachments of ligaments, fasciae and other relevant tissues, all by choice."

In a real Chromium, per size (1400x900 and 390x844):
  1  press the insertions preset (DOM click on the parked #btn-insert): the attachments view turns on, its panel is on screen and
     sized to its content
  2  default = muscles & tendons only: visible origin AND insertion points, every one of them origin_part / insertion_point of a
     muscle / tendon, drawn in the two attachment colours (ring border), and the panel's counts agree with the data
  3  each class alone: a class with placed points shows only its own points (origins / insertions counted); a class without any is
     offered disabled with "no placed attachment on this body" and draws nothing
  4  Selected only: nothing marked -> nothing drawn and a hint; a marked muscle -> only that muscle's points
  5  another preset turns the view off (no attachment point left); 0 page errors

    python3 scripts/anatomy/q323/verify_insertions_q323.py <page_dir> [--no-patch] [--size 1400x900 390x844]

A built page that predates the change is copied to /dev/shm and patched with exactly what the source change makes (the parts_ui sync,
the Q323 engine glue, and the sidecar's per-part structure class "sc" from data/anatomy/structure_parts.json). Ends Q323_INSERTIONS_OK / _FAIL.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
THREE = "/tmp/three_x/package/build/three.min.js"
ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
ERRS: list[str] = []
PAGE_ERRS: list[str] = []


def check(label, cond):
    ok = bool(cond)
    print(("  OK  " if ok else "  FAIL") + " " + label, flush=True)
    if not ok:
        ERRS.append(label)
    return ok


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def page_copy(src: Path, patch: bool) -> Path:
    dst = Path("/dev/shm") / ("q323v_" + src.name)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for f in src.iterdir():
        if f.is_dir():
            continue
        if f.suffix == ".html" or f.name == "parts_data.json":
            shutil.copy(f, dst / f.name)
        else:
            os.symlink(f.resolve(), dst / f.name)
    if not patch:
        return dst
    sync = _load("s220", REPO / "scripts/sync_parts_ui_q220.py")
    glue = _load("p323", REPO / "scripts/anatomy/q323/patch_q323.py")
    for f in dst.glob("*.html"):
        t = f.read_text(encoding="utf-8")
        if "/* PARTS-UI js begin */" not in t:
            continue
        f.write_text(glue.apply(sync.render(t)), encoding="utf-8")
    pd = dst / "parts_data.json"
    if pd.exists():
        d = json.loads(pd.read_text(encoding="utf-8"))
        if any("sc" not in p for p in d["parts"]):
            cls = {p["id"]: p.get("structure_class") for p in json.loads((REPO / "data/anatomy/structure_parts.json").read_text(encoding="utf-8"))["parts"]}
            for p in d["parts"]:
                if cls.get(p["id"]):
                    p["sc"] = cls[p["id"]]
            pd.write_text(json.dumps(d, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return dst


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); return srv, p


def route(rq):
    u = rq.request.url
    if "three" in u and u.endswith(".js") and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u):
        rq.fulfill(body=open(THREE, "rb").read(), content_type="application/javascript")
    elif "fonts.g" in u:
        rq.abort()
    else:
        rq.continue_()


def until(pg, js, secs=240):
    """poll with evaluate (a wait_for_function poll can starve while the engine boots)"""
    for _ in range(secs * 2):
        try:
            if pg.evaluate(js):
                return True
        except Exception:
            pass
        pg.wait_for_timeout(500)
    return False


def settle(pg, ms=900):
    pg.wait_for_timeout(ms)
    pg.evaluate("() => { const c = window.__partsCtl; if (c && c.cullNow) c.cullNow(); }")
    pg.wait_for_timeout(500)


def att(pg):
    return pg.evaluate("""() => { const s = __partsState(), a = s.att, vis = s.markers.filter(m => m.vis);
      const dom = [...document.querySelectorAll('#pm-layer .pm')].filter(e => !e.hidden);
      return {on: a.on, scope: a.scope, cls: a.cls, shown: a.shown, classes: a.classes, panel: a.panel,
              vis: vis.map(m => [m.role, m.ac, m.part]), domO: dom.filter(e => e.classList.contains('pm-ao')).length,
              domI: dom.filter(e => e.classList.contains('pm-ai')).length, dom: dom.length}; }""")


def set_classes(pg, keep):
    """tick exactly the classes in keep, by clicking the panel's own checkboxes"""
    pg.evaluate("""(keep) => { document.querySelectorAll('#pm-att .pa-r').forEach(r => { const cb = r.querySelector('input');
        const want = keep.includes(r.dataset.k); if (!cb.disabled && cb.checked !== want) cb.click(); }); }""", keep)


def run_size(pl, d: Path, w: int, h: int, tag: str):
    print(f"--- {tag} {w}x{h}", flush=True)
    srv, port = serve(d)
    b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
    try:
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, has_touch=w < 600, is_mobile=w < 600)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: PAGE_ERRS.append(f"[{tag} {w}] " + str(e)[:200]))
        pg.route("**/*", route)
        html = sorted(d.glob("atlas_viewer*.html"))[0]
        pg.goto(f"http://127.0.0.1:{port}/{html.name}", wait_until="load", timeout=180000)
        if not check(f"[{tag} {w}] page boots, parts data loaded", until(pg, "() => !!(window.__partsState && __partsState().loaded && document.getElementById('btn-insert'))")):
            return
        if until(pg, "() => !!document.querySelector('.mw-tile[data-mode=\"anat\"]')", 20):
            pg.evaluate("() => document.querySelector('.mw-tile[data-mode=\"anat\"]').click()"); pg.wait_for_timeout(1500)
        pg.evaluate("() => { try { localStorage.removeItem('nmsk.att.v1'); } catch (e) {} }")
        a0 = att(pg)
        check(f"[{tag} {w}] before the preset: view off, no attachment point drawn", not a0["on"] and a0["domO"] + a0["domI"] == 0)

        # 1 press the preset
        pg.evaluate("() => document.getElementById('btn-insert').click()"); settle(pg, 1500)
        a = att(pg)
        check(f"[{tag} {w}] insertions preset turns the attachments view on, panel open", a["on"] and a["panel"])
        r = pg.evaluate("() => { const e = document.getElementById('pm-att'), q = e.getBoundingClientRect(); return {l:q.left, t:q.top, r:q.right, b:q.bottom, w:q.width, h:q.height, sw:e.scrollWidth, cw:e.clientWidth}; }")
        check(f"[{tag} {w}] panel inside the viewport ({r['w']:.0f}x{r['h']:.0f} at {r['l']:.0f},{r['t']:.0f})", r["l"] >= 0 and r["t"] >= 0 and r["r"] <= w and r["b"] <= h)
        check(f"[{tag} {w}] panel sized to its content (width <= 300, no sideways scroll)", r["w"] <= 301 and r["sw"] <= r["cw"] + 1)
        ov = pg.evaluate("""() => { const p = document.getElementById('pm-att').getBoundingClientRect(), out = [];
            document.querySelectorAll('.sa-bar, #sa-all, #ms-bar, #q301-bar, #topright').forEach(e => { if (e.hidden) return; const r = e.getBoundingClientRect();
              if (r.width > 0 && r.height > 0 && r.left < p.right && r.right > p.left && r.top < p.bottom && r.bottom > p.top) out.push(e.id || e.className); });
            return out; }""")
        check(f"[{tag} {w}] panel clear of the top bars and the bottom chips" + (f" (overlaps {ov})" if ov else ""), not ov)
        cl = a["classes"]
        print("     per class on this body (placed O / I points both sides, structures placed / in data, text-only parts, structures on body, with wording):", flush=True)
        for k, c in cl.items():
            print(f"       {k:4s} {c['label']:<24s} O {c['o']:3d}  I {c['i']:3d}  structs {c['structuresPlaced']:3d}/{c['structuresInData']:3d}  text-only {c['textOnly']:3d}  on body {c['onBody']}  wording {c['withText']}", flush=True)

        # 2 default: muscles & tendons
        check(f"[{tag} {w}] default classes = muscles & tendons only", a["cls"].get("mt") is True and not any(v for k, v in a["cls"].items() if k != "mt"))
        o = sum(1 for v in a["vis"] if v[0] == "o"); i = sum(1 for v in a["vis"] if v[0] == "i")
        check(f"[{tag} {w}] muscles & tendons: origins AND insertions visible (O {o}, I {i})", o > 0 and i > 0)
        check(f"[{tag} {w}] every visible point is a muscle/tendon origin or insertion", all(v[0] in ("o", "i") and v[1] == "mt" for v in a["vis"]))
        check(f"[{tag} {w}] rings carry the origin / insertion colour classes (O {a['domO']}, I {a['domI']})", a["domO"] > 0 and a["domI"] > 0)
        col = pg.evaluate("""() => { const f = c => { const e = document.querySelector('#pm-layer .pm.' + c + ':not([hidden]) .pm-ring'); return e ? getComputedStyle(e).borderTopColor : null; };
          return [f('pm-ao'), f('pm-ai')]; }""")
        check(f"[{tag} {w}] origin and insertion rings differ in colour ({col[0]} / {col[1]})", col[0] and col[1] and col[0] != col[1])
        check(f"[{tag} {w}] panel status agrees with the drawn points", a["shown"]["o"] == o and a["shown"]["i"] == i)
        ct = pg.evaluate("() => { const r = document.querySelector('#pm-att .pa-r[data-k=\"mt\"] .pa-ct'); return r ? r.textContent.replace(/\\s+/g, ' ').trim() : ''; }")
        check(f"[{tag} {w}] muscles & tendons row states its counts ('{ct}')", ct == f"{cl['mt']['o']} {cl['mt']['i']}")

        # 3 each class alone
        rows = pg.evaluate("() => [...document.querySelectorAll('#pm-att .pa-r')].map(r => [r.dataset.k, r.querySelector('input').disabled, r.querySelector('.pa-sub').textContent])")
        for k, dis, sub in rows:
            c = cl[k]
            has = c["o"] + c["i"] > 0
            if not has:
                check(f"[{tag} {w}] {k}: no placed attachment -> offered disabled and says so ('{sub[:60]}')", dis and "no placed attachment" in sub)
                continue
            set_classes(pg, [k]); settle(pg)
            s = att(pg)
            so = sum(1 for v in s["vis"] if v[0] == "o"); si = sum(1 for v in s["vis"] if v[0] == "i")
            only = all(v[1] == k and v[0] in ("o", "i") for v in s["vis"])
            check(f"[{tag} {w}] {k} alone: O {so} / I {si} visible (placed O {c['o']} / I {c['i']}), only its own points",
                  only and so + si > 0 and so <= c["o"] and si <= c["i"])
        set_classes(pg, [k for k, dis, _ in rows if not dis]); settle(pg)
        s = att(pg)
        check(f"[{tag} {w}] all classes with data on: {len(s['vis'])} points (O {s['shown']['o']}, I {s['shown']['i']})", len(s["vis"]) >= len(a["vis"]))
        set_classes(pg, ["mt"]); settle(pg)

        # 4 selected only
        pg.evaluate("() => document.querySelector('#pm-att .pp-seg button[data-s=\"sel\"]').click()"); settle(pg)
        s = att(pg)
        hint = pg.evaluate("() => document.querySelector('#pm-att .pa-hint').textContent")
        check(f"[{tag} {w}] Selected only, nothing marked: no point drawn, hint '{hint}'", s["scope"] == "sel" and len(s["vis"]) == 0 and "Select" in hint)
        mid = pg.evaluate("""() => { const st = __partsState(); const m = st.markers.find(m => m.role && m.ac === 'mt' && m.side === 'r' && /^biceps_brachii\\./.test(m.part)) ||
            st.markers.find(m => m.role && m.ac === 'mt' && m.side === 'r'); return m ? m.part : null; }""")
        # the carriers of that part are the structure's own meshes: mark the first right-side carrier
        car = pg.evaluate("""(pid) => { const s = __partsState(); const m = s.markers.find(x => x.part === pid && x.side === 'r'); return m ? m.j : null; }""", mid) if mid else None
        carrier = None
        if car is not None:
            carrier = json.loads((d / "parts_data.json").read_text(encoding="utf-8"))["placed"][car]["car"][0]
        if carrier:
            how = pg.evaluate("(id) => { if (window.NMSKSelectCtl && NMSKSelectCtl.mark) { NMSKSelectCtl.mark(id, true); return 'marked'; } __partsCtl.select(id); return 'selected'; }", carrier); settle(pg)
            s = att(pg)
            st = mid.split(".")[0]
            own = all(v[2].split(".")[0] == st for v in s["vis"])
            check(f"[{tag} {w}] Selected only, {carrier} {how}: {len(s['vis'])} points, all of {st}", len(s["vis"]) > 0 and own)
            pg.evaluate("(id) => { if (window.NMSKSelectCtl && NMSKSelectCtl.mark) NMSKSelectCtl.mark(id, false); else __partsCtl.select(null); }", carrier); settle(pg)
        else:
            check(f"[{tag} {w}] a muscle with placed attachments found to mark", False)
        pg.evaluate("() => document.querySelector('#pm-att .pp-seg button[data-s=\"all\"]').click()"); settle(pg)
        s = att(pg)
        check(f"[{tag} {w}] back to All: points again ({len(s['vis'])})", len(s["vis"]) == len(a["vis"]))

        # 5 another preset ends the view
        pg.evaluate("() => document.getElementById('btn-bones').click()"); settle(pg)
        s = att(pg)
        check(f"[{tag} {w}] another preset turns the view off: panel closed, no attachment point", not s["on"] and not s["panel"] and s["domO"] + s["domI"] == 0)
        pg.evaluate("() => document.getElementById('btn-insert').click()"); settle(pg)
        pg.evaluate("() => document.querySelector('#pm-att .pp-x').click()"); settle(pg)
        s = att(pg)
        check(f"[{tag} {w}] the panel's close button ends the view", not s["on"] and s["domO"] + s["domI"] == 0)
        if "--shot" in sys.argv:
            pg.evaluate("() => document.getElementById('btn-insert').click()"); settle(pg, 1500)
            out = Path(os.environ.get("Q323_SHOTS", "/dev/shm")) / f"q323_{tag}_{w}.png"
            pg.screenshot(path=str(out)); print("     shot", out, flush=True)
        mine = [e for e in PAGE_ERRS if e.startswith(f"[{tag} {w}]")]
        check(f"[{tag} {w}] 0 page errors" + (f" ({mine[0]})" if mine else ""), not mine)
    finally:
        b.close(); srv.terminate()


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--") and not re.match(r"\d+x\d+$", a)]
    sizes = [(1400, 900), (390, 844)]
    if "--size" in sys.argv:
        sizes = [tuple(int(v) for v in a.split("x")) for a in sys.argv[1:] if re.match(r"\d+x\d+$", a)]
    src = Path(args[0]) if args else REPO / "build/q309/viewer_zan_atlas"
    d = page_copy(src, "--no-patch" not in sys.argv)
    with sync_playwright() as pl:
        for w, h in sizes:
            run_size(pl, d, w, h, src.name)
    print("Q323_INSERTIONS_FAIL" if ERRS else "Q323_INSERTIONS_OK")
    for e in ERRS:
        print("   ", e)
    return 1 if ERRS else 0


if __name__ == "__main__":
    raise SystemExit(main())
