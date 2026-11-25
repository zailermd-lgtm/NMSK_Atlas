"""Q395: the CT / MRI simulator's four panes show the body image, as SEEN on the screen, in every 3-D render style.

Owner, 2026-11-25: "in CT and MRI [the images] disappeared". Cause: the radiographic render styles (X-ray / CT / MRI of the
3-D model) set `:root.q301-film`, whose rule painted EVERY <canvas> dark -- including the transparent overlay canvas each
pane draws its crosshair, letters and scale bar on, which then covered the image under it. getImageData of the image
canvas stayed full (that is why a canvas-level check passed); only the screen was black. So this checks both layers:
  * the image canvas: >= 15 % non-black pixels in its central 200 x 200;
  * the screen: >= 15 % non-black pixels in the central (<= 200 x 200 CSS px) part of each pane in a real screenshot;
  * the readout over a body pixel of each pane is not "Air" / "outside the body".
Scenarios: CT; MRI T1 / T2 / PD; each render style (Colour, X-ray, CT, MRI); cut slab 22.5 mm; multi-slice cross-section
(5 slices, 91 mm step, 1 mm thick: the owner's state); window resize and back; controls hidden / shown; simulator closed
and reopened. Each check first waits for the render to finish (<= 60 s under software GL).

  python3 scripts/anatomy/q395/verify_ct_mri_panes_q395.py <page dir> [<page dir> ...] [--size 1400x900 1920x1080]
      -> Q395_CTMRI_OK / Q395_CTMRI_FAIL n          (run behind `flock /tmp/nmsk_browser.lock`)
"""
import io, re, sys, json, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q321"))
import verify_quickcard_q321 as Q
from playwright.sync_api import sync_playwright
from PIL import Image

MIN_FRAC = 0.15
PANES = ("cut", "ax", "co", "sa")

IDLE = """() => new Promise(res => { const t0 = Date.now(), I = window.NMSKImaging;
  const st = () => { const e = document.querySelector('#img-root .img-status'); return e ? e.textContent : ''; };
  (function loop() { Promise.race([I.idle(), new Promise(r => setTimeout(() => r(false), 5000))]).then(ok => {
      const s = st(), all = Object.values(I.views()).filter(v => ['cut','ax','co','sa'].includes(v.key)).every(v => v.labels.length && !v.dirty && !v.partial);
      if ((ok && all && !/^Computing|^Loading|^Preparing/.test(s)) || Date.now() - t0 > 60000) res({ok: !!(ok && all), ms: Date.now() - t0, status: s.slice(0, 120)}); else setTimeout(loop, 300); }); })(); })"""

PANE_INFO = """(keys) => { const I = window.NMSKImaging, vs = I.views(), C = I.C(), out = {};
  keys.forEach(k => { const v = vs[k]; if (!v || !v.img) { out[k] = null; return; }
    const c = v.img, w = Math.min(200, c.width), h = Math.min(200, c.height); let n = 0;
    try { const d = v.ctx.getImageData((c.width - w) >> 1, (c.height - h) >> 1, w, h).data; for (let i = 0; i < d.length; i += 4) if (d[i] > 24 || d[i+1] > 24 || d[i+2] > 24) n++; } catch (e) { n = -1; }
    const r = c.getBoundingClientRect();
    /* a body pixel near the centre of the image, for the readout check */
    let body = null; const lab = v.labels.length ? v.labels[Math.min(v.mid, v.labels.length - 1)] : null;
    if (lab) { let best = 1e9; const cx = v.W / 2, cy = v.H / 2;
      for (let iy = 0; iy < v.H; iy += 3) for (let ix = 0; ix < v.W; ix += 3) { const cl = lab[iy * v.W + ix]; if (cl === C.ids.air) continue;
        const dd = (ix - cx) ** 2 + (iy - cy) ** 2; if (dd < best) { best = dd; body = [ix + 0.5, iy + 0.5]; } } }
    out[k] = {frac: w * h ? n / (w * h) : 0, rect: [r.x, r.y, r.width, r.height], W: v.W, H: v.H,
              at: body ? [r.x + body[0] / v.W * r.width, r.y + body[1] / v.H * r.height] : null}; });
  return out; }"""

READ = "() => { const e = document.querySelector('#img-root .img-read'); return e ? e.textContent : ''; }"
STATE = "() => { const s = NMSKImaging.state(); return {mod: s.modality, seq: s.seq, thick: s.thick, open: s.open, lay: s.lay, film: document.documentElement.classList.contains('q301-film'), style: window.NMSKRenderStyle && NMSKRenderStyle.mode ? NMSKRenderStyle.mode() : '?'}; }"


def screen_frac(png, rect, vw, vh):
    im = Image.open(io.BytesIO(png)).convert("RGB")
    sx, sy = im.width / vw, im.height / vh
    x, y, w, h = rect; s = min(200.0, w, h); cx, cy = x + w / 2, y + h / 2
    box = (int((cx - s / 2) * sx), int((cy - s / 2) * sy), int((cx + s / 2) * sx), int((cy + s / 2) * sy))
    raw = im.crop(box).tobytes(); n = len(raw) // 3
    return sum(1 for i in range(0, 3 * n, 3) if max(raw[i], raw[i + 1], raw[i + 2]) > 24) / max(1, n)


def run(src, w, h, say):
    d = Q.page_copy(src, False)
    with sync_playwright() as pl:
        srv, b, pg = Q.V.open_page(pl, d, w, h)
        try:
            pg.wait_for_function("window.NMSKModes && window.NMSKImaging && window.NMSKRenderStyle", timeout=180000)
            pg.wait_for_timeout(2500)
            pg.evaluate("() => { const c = document.getElementById('mw-close'); if (c && c.offsetParent) c.click(); }"); pg.wait_for_timeout(600)
            T = "%s %dx%d" % (src.name, w, h)

            def click_text(t, scope="document"):
                return pg.evaluate("([t, s]) => { const root = s === 'document' ? document : document.querySelector(s); if (!root) return false;"
                                   " const b = [...root.querySelectorAll('button')].find(x => x.textContent.trim() === t && x.offsetParent); if (!b) return false; b.click(); return true; }", [t, scope])

            def style(m):
                ok = pg.evaluate("(m) => { const b = document.getElementById('rs-' + m); if (b && b.offsetParent) { b.click(); return 'click'; }"
                                 " if (window.NMSKRenderStyle && NMSKRenderStyle.set) { NMSKRenderStyle.set(m); return 'api'; } return ''; }", m)
                pg.wait_for_timeout(1500); return ok

            def check(label):
                r = pg.evaluate(IDLE)
                st = pg.evaluate(STATE)
                info = pg.evaluate(PANE_INFO, list(PANES))
                png = pg.screenshot()
                vw, vh = pg.viewport_size["width"], pg.viewport_size["height"]
                parts, ok = [], r["ok"]
                for k in PANES:
                    p = info.get(k)
                    if not p:
                        ok = False; parts.append("%s:missing" % k); continue
                    sf = screen_frac(png, p["rect"], vw, vh)
                    rd = ""
                    if p["at"]:
                        pg.mouse.move(p["at"][0], p["at"][1]); pg.wait_for_timeout(250); rd = pg.evaluate(READ)
                    air = (not p["at"]) or rd.startswith("Air") or "outside the body" in rd or rd.startswith("Move over")
                    good = p["frac"] >= MIN_FRAC and sf >= MIN_FRAC and not air
                    ok = ok and good
                    parts.append("%s canvas %.0f%% screen %.0f%% read '%s'%s" % (k, 100 * p["frac"], 100 * sf, rd.split("|")[0].strip()[:34], "" if good else " <-- BAD"))
                say(ok, "%s | %s | render %s in %.1f s | %s | %s" % (T, label, "done" if r["ok"] else "NOT DONE", r["ms"] / 1000, json.dumps(st), "; ".join(parts)))
                if not ok:
                    open(str(Path("/tmp") / ("q395_fail_%s_%dx%d_%s.png" % (src.name, w, h, re.sub(r"\W+", "_", label)))), "wb").write(png)

            # open the simulator the way a user does: Imaging tab, then "ct / mri"
            click_text("Imaging"); pg.wait_for_timeout(1200)
            if not pg.evaluate("() => { const b = document.getElementById('t-imaging'); if (b && b.offsetParent) { b.click(); return true; } return false; }"):
                pg.evaluate("() => NMSKImaging.open()")
            pg.wait_for_function("NMSKImaging.state().open && NMSKImaging.views().cut.labels.length > 0", timeout=180000)
            check("CT, Colour style")
            mr = lambda seq: (click_text("MRI", "#img-root"), pg.evaluate("(q) => NMSKImaging.set({seq: q})", seq), pg.wait_for_timeout(400))
            for seq, nm in (("t1_se", "T1"), ("t2_se", "T2"), ("pd_se", "PD")):
                mr(seq); check("MRI %s, Colour style" % nm)
            for m in ("xray", "ct", "mri", "colour", "ct"):
                style(m); check("MRI PD, %s style" % m)
            mr("t1_se")
            click_text("CT", "#img-root"); pg.wait_for_timeout(300); check("CT, CT style")
            mr("t1_se"); check("MRI T1, CT style (owner)")
            # owner's cut slab: 22.5 mm, through the Cut panel's own slider
            pg.evaluate("() => { const s = document.getElementById('cut-thsl'); if (s) { s.value = '22.5'; s.dispatchEvent(new Event('input', {bubbles: true})); s.dispatchEvent(new Event('change', {bubbles: true})); } }")
            pg.wait_for_timeout(800)
            if abs(pg.evaluate("() => NMSKImaging.state().thick") - 22.5) > 0.6:
                pg.evaluate("() => NMSKImaging.set({thick: 22.5})")
            check("MRI T1, CT style, slab 22.5 mm")
            # owner's multi-slice stack: 5 slices, 91 mm apart, 1 mm thick
            pg.evaluate("() => { const b = document.getElementById('xsec-on'); if (b && b.getAttribute('aria-pressed') !== 'true') b.click(); }"); pg.wait_for_timeout(800)
            pg.evaluate("() => { [['xsec-n','5'],['xsec-sp','91'],['xsec-th','1']].forEach(([i, v]) => { const e = document.getElementById(i); if (e) { e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); } }); }")
            pg.wait_for_timeout(1500)
            check("MRI T1, CT style, slab 22.5, multi-slice 5 x 91 mm (owner's state)")
            style("mri"); check("MRI T1, MRI style, multi-slice")
            # window resize and back
            o = (w, h); alt = (1920, 1080) if (w, h) != (1920, 1080) else (1400, 900)
            pg.set_viewport_size({"width": alt[0], "height": alt[1]}); pg.wait_for_timeout(2000); check("resized to %dx%d" % alt)
            pg.set_viewport_size({"width": o[0], "height": o[1]}); pg.wait_for_timeout(2000); check("resized back")
            # panels: hide / show the controls, close and reopen the simulator
            pg.evaluate("() => document.getElementById('img-ctlbtn').click()"); pg.wait_for_timeout(1200); check("controls hidden")
            pg.evaluate("() => document.getElementById('img-ctlbtn').click()"); pg.wait_for_timeout(1200); check("controls shown")
            pg.evaluate("() => NMSKImaging.close()"); pg.wait_for_timeout(1500)
            if not pg.evaluate("() => { const b = document.getElementById('t-imaging'); if (b && b.offsetParent) { b.click(); return true; } return false; }"):
                pg.evaluate("() => NMSKImaging.open()")
            pg.wait_for_function("NMSKImaging.state().open", timeout=60000); pg.wait_for_timeout(1500)
            check("closed and reopened (MRI style)")
            say(not [e for e in Q.V.ERRS if e.startswith("page error")], "%s no page errors %s" % (T, Q.V.ERRS[:2]))
        finally:
            b.close(); srv.terminate()
    shutil.rmtree(d, ignore_errors=True)


def main():
    a = sys.argv[1:]; sizes = [(1400, 900), (1920, 1080)]
    if "--size" in a:
        i = a.index("--size"); sizes = [tuple(int(v) for v in s.split("x")) for s in a[i + 1:] if re.match(r"\d+x\d+$", s)]
        a = [s for s in a[:i]] + [s for s in a[i + 1:] if not re.match(r"\d+x\d+$", s)]
    pages = [Path(p) for p in a if not p.startswith("--")]
    bad = 0
    def say(ok, msg):
        nonlocal bad
        print(("  OK   " if ok else "  FAIL ") + msg, flush=True); bad += 0 if ok else 1
    for p in pages:
        for (w, h) in sizes:
            try:
                run(p, w, h, say)
            except Exception as e:
                say(False, "%s %dx%d crashed: %s" % (p.name, w, h, str(e)[:300]))
    print("Q395_CTMRI_OK" if not bad else "Q395_CTMRI_FAIL %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
