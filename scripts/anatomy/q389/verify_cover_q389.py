"""Q389: the optional display covering ("underwear") on a regenerated Base page.

Checks, on the page itself: off by default; the control (Systems group) with its "display covering, not anatomy" badge and note,
and the section in the circled i; Briefs on both bodies and a Top only where the page carries one; switching it on by the
checkbox draws it (pixels at the projected garment vertices change to the cloth colour, pixels away from it do not); a pick
passes through it (the ID pass names the same structure with it on and off, and a real click opens the same card); it
follows the pose (every bound vertex stays at its height above the posed skin point it is bound to; back at the model pose
it is the rest geometry again); the cut removes it with the half it removes; it stays opaque and drawn whatever the skin's
opacity; Undo / Redo and a reload keep the choice; no page errors.

  python3 scripts/anatomy/q389/verify_cover_q389.py <page dir> [--size 390x844] [--shots DIR]   -> Q389_COVER_OK / Q389_COVER_FAIL n
"""
import sys, json, math, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q321"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q334"))
import verify_quickcard_q321 as Q
import verify_skin_seams_q334 as S334
from playwright.sync_api import sync_playwright

# garment vertices (every step-th), projected: [x, y, w, px, py, pz, bound?]
PROJ = """([key, step]) => { const d = __coverDebug(key), out = []; if (!d.at) return out;
  for (let v = 0; v < d.n; v += step){ const p = d.at(v), s = __q334.toScreen(p); if (s) out.push([s[0], s[1], s[2], p[0], p[1], p[2], v < d.nb ? 1 : 0]); }
  return out; }"""
# how far each bound vertex is from the skin point it is bound to, minus its stored height (mm): must be ~0 in any pose
BOUND_ERR = """(key) => { const d = __coverDebug(key), src = d.srcIndex; let worst = 0, n = 0, moved = 0;
  const g = NMSKCover.garment(key);
  for (let v = 0; v < d.nb; v += 3){ const b = d.bindOf(v), i = g.srcIdx[g.src.indexOf(b[0])];
    const L = __poseLive(i), R = __poseRestPos(i); if (!L){ continue; }
    const wa = b[4] / 65535, wb = b[5] / 65535, wc = 1 - wa - wb, q = [0, 0, 0], r = [0, 0, 0];
    for (let j = 0; j < 3; j++){ q[j] = wa * L[3 * b[1] + j] + wb * L[3 * b[2] + j] + wc * L[3 * b[3] + j]; if (R) r[j] = wa * R[3 * b[1] + j] + wb * R[3 * b[2] + j] + wc * R[3 * b[3] + j]; }
    const p = d.at(v), dist = Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]);
    worst = Math.max(worst, Math.abs(dist - b[6] / 100)); n++;
    if (R && Math.hypot(q[0] - r[0], q[1] - r[1], q[2] - r[2]) > 5) moved++; }
  return {worst: worst, n: n, moved: moved, nan: d.nan, box: d.box}; }"""
UI = """() => { const b = document.getElementById('cv-box'), r = b ? b.getBoundingClientRect() : null;
  const vis = !!(b && r.width > 40 && r.height > 20 && getComputedStyle(b).visibility !== 'hidden');
  const badge = document.getElementById('cv-badge'), note = document.getElementById('cv-note');
  return {box: !!b, vis: vis, inView: !!(vis && r.left >= -1 && r.right <= innerWidth + 1 && r.top >= -1 && r.bottom <= innerHeight + 1),
    badge: badge ? badge.textContent : '', note: note ? note.textContent : '', briefs: !!document.getElementById('cv-briefs'), top: !!document.getElementById('cv-top'),
    checked: {briefs: !!(document.getElementById('cv-briefs') || {}).checked, top: !!(document.getElementById('cv-top') || {}).checked},
    info: !!(window.NMSKInfo && NMSKInfo.sections().indexOf('cover') >= 0), group: window.NMSKGroups ? NMSKGroups.isOpen() : null}; }"""
PRIVATE = ["ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode"]


def cloth(c):
    return c != -1 and c[2] >= c[0] - 6 and min(c) > 60 and (c[2] - c[0]) >= -6 and not (c[0] > c[2] + 12)


def diff(a, b):
    return 999 if a == -1 or b == -1 else abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def main():
    a = sys.argv[1:]; src = Path(a[0]); w, h = 1400, 900
    if "--size" in a: w, h = [int(x) for x in a[a.index("--size") + 1].split("x")]
    shots = Path(a[a.index("--shots") + 1]) if "--shots" in a else None
    female = "female" in src.name
    d = Q.page_copy(src, False); bad = 0
    tag = "%s_%dx%d" % (src.name, w, h)

    def say(ok, msg):
        nonlocal bad
        print(("  OK   " if ok else "  FAIL ") + msg, flush=True); bad += 0 if ok else 1

    with sync_playwright() as pl:
        srv, b, pg = S334.open_page(pl, d, w, h)
        try:
            Q.wait_ready(pg)
            pg.wait_for_function("window.NMSKCover && NMSKCover.ready() && NMSKCover.state().mounted", timeout=60000)
            st = pg.evaluate("() => NMSKCover.state()")
            keys = [g["key"] for g in st["garments"]]
            say(st["ready"] and not st["failed"] and not any(st["on"].values()), "ready, off by default  %s" % json.dumps(st["on"]))
            say(keys == (["briefs", "top"] if female else ["briefs"]), "garments on this page: %s (a top only on the female body)" % keys)
            say(all(g["bound"] > 300 and g["tris"] > 500 for g in st["garments"]), "garment sizes %s" % [(g["key"], g["bound"], g["pouch"], int(g["tris"])) for g in st["garments"]])

            # the control
            pg.evaluate("() => NMSKGroups.open('systems')"); pg.wait_for_timeout(500)
            u = pg.evaluate(UI)
            say(u["box"] and u["vis"] and u["group"] == "systems", "the control is in the Systems group  %s" % json.dumps({k: u[k] for k in ("box", "vis", "inView", "group")}))
            say("display covering" in u["badge"] and "not anatomy" in u["badge"], "badge on the control: '%s'" % u["badge"])
            say("not an anatomical structure" in u["note"] and "hides nothing from measurements" in u["note"], "the note says it is not anatomy and hides nothing from measurements")
            say(u["briefs"] and u["top"] == female, "checkboxes: briefs %s, top %s" % (u["briefs"], u["top"]))
            say(u["info"], "a section in the circled i")
            txt = (u["badge"] + " " + u["note"]).lower()
            say(not any(p in txt for p in PRIVATE), "no private word in the control's text")
            if shots:
                shots.mkdir(parents=True, exist_ok=True); pg.screenshot(path=str(shots / (tag + "_control.png")))

            # switch on by the checkbox
            pg.evaluate("() => { const c = document.getElementById('cv-briefs'); c.scrollIntoView({block: 'center'}); }")
            pg.click("#cv-briefs"); pg.wait_for_timeout(700)
            on1 = pg.evaluate("() => NMSKCover.state().on")
            say(on1["briefs"] is True, "the checkbox switches the briefs on  %s" % json.dumps(on1))
            pg.evaluate("() => NMSKGroups.close()"); pg.wait_for_timeout(300)

            # front view on the pelvis; pixels with it on and off
            box = pg.evaluate("() => __coverDebug('briefs').box")
            ctr = [(box[0][k] + box[1][k]) / 2 for k in range(3)]
            pg.evaluate("(c) => { const H = __q334.cam().H; __q334.cam({az: 0, el: 0, dist: H * 0.75, tgt: c}); }", ctr); pg.wait_for_timeout(400)

            def images(key, step):
                P = pg.evaluate(PROJ, [key, step])
                P = [p for p in P if 5 < p[0] < w - 5 and 5 < p[1] < h - 5]
                pts = [[p[0], p[1]] for p in P]
                on = pg.evaluate("(pts) => __q334.sample(pts, true)", pts)
                pg.evaluate("(k) => { const o = {}; o[k] = false; NMSKCover.set(o); }", key)
                off = pg.evaluate("(pts) => __q334.sample(pts, true)", pts)
                pg.evaluate("(k) => { const o = {}; o[k] = true; NMSKCover.set(o); }", key)
                return P, pts, on, off

            P, pts, on, off = images("briefs", 5)
            ch = [i for i in range(len(P)) if diff(on[i], off[i]) > 40]
            cl = [i for i in ch if cloth(on[i])]
            say(len(P) > 100 and len(ch) > 0.3 * len(P) and len(cl) > 0.9 * len(ch), "drawn: %d of %d projected garment vertices change the picture, %d of them to the cloth colour" % (len(ch), len(P), len(cl)))
            dr = pg.evaluate("() => (__q334.sample([[5, 5]]), __coverDebug().drawn)")
            say(dr == 1, "the engine drew 1 garment (%s)" % dr)
            # away from it nothing changes: points one garment height above and below the band, on the body's midline column
            far = [[w / 2, 4], [8, h / 2]] + [[p[0], p[1]] for p in P[:: max(1, len(P) // 40)]]
            ys = [p[1] for p in P]; top_y, bot_y = min(ys), max(ys)
            away = [[x, top_y - 25] for x in range(int(w * 0.3), int(w * 0.7), 23)] + [[x, bot_y + 25] for x in range(int(w * 0.3), int(w * 0.7), 23)]
            away = [p for p in away if 2 < p[1] < h - 2]
            a_on = pg.evaluate("(pts) => __q334.sample(pts, true)", away)
            pg.evaluate("() => NMSKCover.set({briefs: false})")
            a_off = pg.evaluate("(pts) => __q334.sample(pts, true)", away)
            pg.evaluate("() => NMSKCover.set({briefs: true})")
            say(all(diff(x, y) <= 6 for x, y in zip(a_on, a_off)), "outside the band the picture is the same with it on and off (%d points)" % len(away))

            # a pick passes through it
            vis = [pts[i] for i in cl][:: max(1, len(cl) // 60)]
            ids_on = pg.evaluate("(pts) => pts.map(p => __q334.pickAt(p[0], p[1]))", vis)
            pg.evaluate("() => NMSKCover.set({briefs: false})")
            ids_off = pg.evaluate("(pts) => pts.map(p => __q334.pickAt(p[0], p[1]))", vis)
            pg.evaluate("() => NMSKCover.set({briefs: true})")
            named = sum(1 for x in ids_on if x)
            say(ids_on == ids_off and named > 0.5 * len(vis), "a pick passes through: the ID pass names the same structure at %d garment points, on and off (%d name one)" % (len(vis), named))
            cr = Q.canvas_rect(pg)
            pick = next((p for p, i in zip(vis, ids_on) if i and pg.evaluate("(q) => { const e = document.elementFromPoint(q[0], q[1]); return !!e && e.tagName === 'CANVAS'; }", [p[0] + cr["l"], p[1] + cr["t"]])), None)
            if pick:
                pg.mouse.click(pick[0] + cr["l"], pick[1] + cr["t"]); pg.wait_for_timeout(900)
                c_on = Q.card_info(pg)
                pg.evaluate("() => NMSKCover.set({briefs: false})"); pg.wait_for_timeout(700)
                pg.mouse.click(pick[0] + cr["l"], pick[1] + cr["t"]); pg.wait_for_timeout(900)
                c_off = Q.card_info(pg)
                pg.evaluate("() => NMSKCover.set({briefs: true})"); pg.wait_for_timeout(300)
                say(bool(c_on) and bool(c_off) and c_on["name"] == c_off["name"], "a real click on the garment opens the card of the structure under it: '%s' (off: '%s')" % (c_on and c_on["name"], c_off and c_off["name"]))
                pg.keyboard.press("Escape")
            else:
                say(False, "no clickable garment point found for the click test")
            if shots:
                pg.screenshot(path=str(shots / (tag + "_front.png")))
                pg.evaluate("() => __q334.cam({az: Math.PI})"); pg.wait_for_timeout(500); pg.screenshot(path=str(shots / (tag + "_back.png")))
                pg.evaluate("() => __q334.cam({az: 1.2, el: -0.5})"); pg.wait_for_timeout(500); pg.screenshot(path=str(shots / (tag + "_below.png")))
                pg.evaluate("() => __q334.cam({az: 0, el: 0})"); pg.wait_for_timeout(300)

            # whatever the skin's opacity, and with the skin off
            for a_, name in ((1, "opaque skin"), (0, "skin off")):
                pg.evaluate("(a) => __q334.layer('skin', a)", a_)
                s2 = pg.evaluate("(pts) => __q334.sample(pts, true)", [pts[i] for i in cl[:200]])
                say(sum(1 for c in s2 if cloth(c)) > 0.9 * len(s2), "%s: the garment is still drawn opaque (%d of %d points)" % (name, sum(1 for c in s2 if cloth(c)), len(s2)))
            pg.evaluate("() => __q334.defaults()")

            # the pose
            e0 = pg.evaluate(BOUND_ERR, "briefs")
            pg.evaluate("() => { __poseApi.set('hip_r', 'flex', 70); __poseApi.set('hip_l', 'abd', 25); }"); pg.wait_for_timeout(900)
            e1 = pg.evaluate(BOUND_ERR, "briefs")
            say(e1["n"] > 100 and e1["moved"] > 30 and e1["worst"] < 0.02 and not e1["nan"], "posed (hip flexion 70, abduction 25): %d bound vertices checked, %d on skin that moved > 5 mm, worst height error %.4f mm" % (e1["n"], e1["moved"], e1["worst"]))
            P2, pts2, on2, off2 = images("briefs", 5)
            ch2 = [i for i in range(len(P2)) if diff(on2[i], off2[i]) > 40]
            # (the flexed thigh's translucent skin now lies in front of part of it, so not every changed pixel is plain cloth)
            say(len(ch2) > 0.3 * len(P2) and sum(1 for i in ch2 if cloth(on2[i])) > 0.6 * len(ch2), "posed: drawn at its new place (%d of %d projected vertices change the picture, %d plain cloth)" % (len(ch2), len(P2), sum(1 for i in ch2 if cloth(on2[i]))))
            if shots:
                pg.screenshot(path=str(shots / (tag + "_posed.png")))
            pg.evaluate("() => __poseApi.reset()"); pg.wait_for_timeout(900)
            box3 = pg.evaluate("() => __coverDebug('briefs').box")
            back = max(abs(box3[i][k] - box[i][k]) for i in range(2) for k in range(3))
            say(back < 0.5, "back at the starting pose the garment is where it was (box differs by %.3f mm)" % back)

            # the cut
            pg.evaluate("() => document.getElementById('t-cut').click()"); pg.wait_for_timeout(1500)
            cp = pg.evaluate("() => __coverDebug().clip")
            if cp:
                # look ALONG the cut plane (the eye in it): the removed half-space is then one side of a line on the screen, where
                # nothing is left to draw -- neither anatomy nor, if it takes the plane, the garment
                n = cp[:3]; ln = math.sqrt(sum(x * x for x in n)); n = [x / ln for x in n]; wq = cp[3] / ln
                dist0 = sum(n[k] * ctr[k] for k in range(3)) + wq
                tgt = [ctr[k] - n[k] * dist0 for k in range(3)]
                up = [0, 1, 0] if abs(n[1]) < 0.9 else [1, 0, 0]
                dv = [n[1] * up[2] - n[2] * up[1], n[2] * up[0] - n[0] * up[2], n[0] * up[1] - n[1] * up[0]]
                dl = math.sqrt(sum(x * x for x in dv)); dv = [x / dl for x in dv]
                pg.evaluate("([az, el, t]) => __q334.cam({az: az, el: el, tgt: t})", [math.atan2(dv[0], dv[2]), math.asin(max(-1, min(1, dv[1]))), tgt]); pg.wait_for_timeout(600)
                P3, pts3, on3, off3 = images("briefs", 3)
                side = [P3[i][3] * n[0] + P3[i][4] * n[1] + P3[i][5] * n[2] + wq for i in range(len(P3))]
                gone = [i for i in range(len(P3)) if side[i] > 12]
                kept = [i for i in range(len(P3)) if side[i] < -12]
                g_ch = sum(1 for i in gone if diff(on3[i], off3[i]) > 40)
                k_ch = sum(1 for i in kept if diff(on3[i], off3[i]) > 40 and cloth(on3[i]))
                say(len(gone) > 30 and g_ch == 0, "cut: on the removed side nothing of the garment is drawn (%d of %d of its points change the picture)" % (g_ch, len(gone)))
                say(len(kept) > 30 and k_ch > 0.3 * len(kept), "cut: on the kept side it is still there (%d of %d points)" % (k_ch, len(kept)))
                if shots:
                    pg.screenshot(path=str(shots / (tag + "_cut.png")))
            else:
                say(False, "cut mode did not give a clip plane")
            pg.evaluate("() => document.getElementById('t-cut').click()"); pg.wait_for_timeout(900)
            pg.evaluate("() => __q334.cam({az: 0, el: 0})")

            # the top (female)
            if female:
                pg.evaluate("() => NMSKCover.set({top: true})"); pg.wait_for_timeout(400)
                boxt = pg.evaluate("() => __coverDebug('top').box")
                pg.evaluate("(c) => __q334.cam({az: 0, el: 0, tgt: c})", [(boxt[0][k] + boxt[1][k]) / 2 for k in range(3)]); pg.wait_for_timeout(400)
                Pt, ptst, ont, offt = images("top", 23)
                cht = [i for i in range(len(Pt)) if diff(ont[i], offt[i]) > 40]
                say(len(Pt) > 100 and len(cht) > 0.3 * len(Pt) and sum(1 for i in cht if cloth(ont[i])) > 0.9 * len(cht), "top: drawn (%d of %d projected vertices change the picture)" % (len(cht), len(Pt)))
                say(pg.evaluate("() => (__q334.sample([[5, 5]]), __coverDebug().drawn)") == 2, "both garments drawn")
                pg.evaluate("() => { __poseApi.set('shoulder_r', 'abd', 80); }"); pg.wait_for_timeout(900)
                et = pg.evaluate(BOUND_ERR, "top")
                say(et["n"] > 100 and et["worst"] < 0.02 and not et["nan"], "top, arm abducted 80: %d bound vertices, %d on moved skin, worst height error %.4f mm" % (et["n"], et["moved"], et["worst"]))
                if shots:
                    pg.screenshot(path=str(shots / (tag + "_top_posed.png")))
                pg.evaluate("() => { __poseApi.set('shoulder_r', 'abd', 0); }"); pg.wait_for_timeout(600)
                if shots:
                    pg.evaluate("(c) => { const H = __q334.cam().H; __q334.cam({az: 0.5, el: 0.1, dist: H * 1.1, tgt: [0, c, 0]}); }", (boxt[0][1] + box[1][1]) / 2); pg.wait_for_timeout(500)
                    pg.screenshot(path=str(shots / (tag + "_both.png")))
                pg.evaluate("() => NMSKCover.set({top: false})")

            # history
            pg.evaluate("() => NMSKHistory.commit(0)"); pg.wait_for_timeout(500)
            snap = pg.evaluate("() => NMSKHistory.snapshot()")
            snap = json.loads(snap) if isinstance(snap, str) else snap
            say("cover" in snap and snap["cover"].get("briefs") is True, "the choice is part of the history snapshot  %s" % json.dumps(snap.get("cover")))
            pg.evaluate("() => NMSKCover.set({briefs: false})"); pg.wait_for_timeout(600)
            pg.evaluate("() => NMSKHistory.undo()"); pg.wait_for_timeout(600)
            u1 = pg.evaluate("() => NMSKCover.state().on.briefs")
            pg.evaluate("() => NMSKHistory.redo()"); pg.wait_for_timeout(600)
            u2 = pg.evaluate("() => NMSKCover.state().on.briefs")
            say(u1 is True and u2 is False, "Undo brings it back on, Redo takes it off again (%s, %s)" % (u1, u2))

            # remembered over a reload
            pg.evaluate("() => NMSKCover.set({briefs: true})"); pg.wait_for_timeout(300)
            Q.reload(pg)
            pg.wait_for_function("window.NMSKCover && NMSKCover.ready()", timeout=60000); pg.wait_for_timeout(500)
            r = pg.evaluate("() => ({on: NMSKCover.state().on, drawn: (__q334.sample([[5, 5]]), __coverDebug().drawn)})")
            say(r["on"]["briefs"] is True and r["drawn"] >= 1, "after a reload it is still on and drawn  %s" % json.dumps(r))
            pg.evaluate("() => NMSKCover.set({briefs: false})"); pg.wait_for_timeout(300)
            say(pg.evaluate("() => (__q334.sample([[5, 5]]), __coverDebug().drawn)") == 0, "switched off: nothing of it is drawn")
            say(not Q.V.ERRS and not S334.ERRS, "no page errors %s" % (Q.V.ERRS + S334.ERRS)[:2])
        finally:
            b.close(); srv.terminate()
    shutil.rmtree(d, ignore_errors=True)
    print("Q389_COVER_OK" if not bad else "Q389_COVER_FAIL %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
