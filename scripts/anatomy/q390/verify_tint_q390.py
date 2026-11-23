"""Q390: one click on a structure tints it at once and subtly; the tint is the "From now on" colour of the Settings control and goes
away when the selection clears (Esc, click on empty space).

  python3 scripts/anatomy/q390/verify_tint_q390.py <page dir> [--size 390x844]   -> Q390_TINT_OK / Q390_TINT_FAIL
"""
import sys, io, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q321"))
import verify_quickcard_q321 as Q
from playwright.sync_api import sync_playwright
from PIL import Image

R = 10


def patch(pg, x, y):
    im = Image.open(io.BytesIO(pg.screenshot(clip={"x": x - R, "y": y - R, "width": 2 * R, "height": 2 * R}))).convert("RGB")
    px = list(im.getdata()); n = len(px)
    return tuple(sum(p[i] for p in px) / n for i in range(3))


def dist(a, b):
    return sum(abs(a[i] - b[i]) for i in range(3)) / 3


def away(pg):
    pg.mouse.move(2, pg.viewport_size["height"] - 2); pg.wait_for_timeout(350)


def esc(pg):
    for _ in range(3):                      # the first Esc may be taken by "show everything" (hidden structures), the next one deselects
        pg.keyboard.press("Escape"); pg.wait_for_timeout(250)


def main():
    a = sys.argv[1:]; src = Path(a[0]); w, h = 1400, 900
    if "--size" in a: w, h = [int(x) for x in a[a.index("--size") + 1].split("x")]
    d = Q.page_copy(src, False); bad = 0
    def say(ok, msg):
        nonlocal bad
        print(("  OK   " if ok else "  FAIL ") + msg, flush=True); bad += 0 if ok else 1
    with sync_playwright() as pl:
        srv, b, pg = Q.V.open_page(pl, d, w, h)
        try:
            Q.wait_ready(pg)
            best = None
            for rx in (r"femoris|tibialis|gastro|vastus", r"deltoid|biceps|pector", r"glute|rectus|oblique|trapez|latissimus"):
                m = Q.scan(pg, rx, "muscle", grid=16)
                if not m or not Q.free(pg, m[0], m[1]):          # the point must stay on the model after the card opens (phone: a docked card can cover it)
                    continue
                x, y = m[0], m[1]
                esc(pg); away(pg); pg.wait_for_timeout(300)
                A = patch(pg, x, y)
                pg.mouse.click(x, y); pg.wait_for_timeout(500); away(pg)
                B = patch(pg, x, y)
                if Q.free(pg, x, y) and (best is None or dist(A, B) > best[0]):
                    best = (dist(A, B), x, y, A, B)
                if best and best[0] >= 8:
                    break
            say(best is not None, "found a muscle to click")
            if not best: raise SystemExit
            dB, x, y, A, B = best
            say(5 <= dB <= 80, "click tints the picked structure at once: delta %.1f (want 5..80, subtle)  %s -> %s" % (dB, tuple(round(v) for v in A), tuple(round(v) for v in B)))
            esc(pg); away(pg); pg.mouse.click(x, y); pg.wait_for_timeout(500); away(pg)
            pg.evaluate("() => NMSKSelectCtl.setUserColour('#ff00ff', 'next')"); pg.wait_for_timeout(300)
            esc(pg); away(pg); pg.mouse.click(x, y); pg.wait_for_timeout(500); away(pg)
            C = patch(pg, x, y)
            say(dist(B, C) >= 4 and C[0] - B[0] + C[2] - B[2] > 0 and C[1] - B[1] < 0, "tint colour follows the Settings colour (magenta): %s -> %s" % (tuple(round(v) for v in B), tuple(round(v) for v in C)))
            say(dist(A, C) <= 90, "still subtle with a strong colour chosen: delta %.1f" % dist(A, C))
            pg.evaluate("() => NMSKSelectCtl.setUserColour(null, 'next')")
            esc(pg); away(pg); pg.wait_for_timeout(300)
            D = patch(pg, x, y)
            say(dist(A, D) <= 3, "Esc clears the tint: delta %.1f" % dist(A, D))
            pg.mouse.click(x, y); pg.wait_for_timeout(500); away(pg)
            say(dist(A, patch(pg, x, y)) >= 5, "tint is back after a fresh click")
            cr = Q.canvas_rect(pg)
            ex, ey = cr["l"] + 6, cr["t"] + 6
            if Q.free(pg, ex, ey):
                pg.mouse.click(ex, ey); pg.wait_for_timeout(500); away(pg)
                say(dist(A, patch(pg, x, y)) <= 3, "click on empty space clears the tint: delta %.1f" % dist(A, patch(pg, x, y)))
            say(not Q.V.ERRS, "no page errors %s" % Q.V.ERRS[:2])
        except SystemExit:
            pass
        finally:
            b.close(); srv.terminate()
    shutil.rmtree(d, ignore_errors=True)
    print("Q390_TINT_OK" if not bad else "Q390_TINT_FAIL %d" % bad)
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
