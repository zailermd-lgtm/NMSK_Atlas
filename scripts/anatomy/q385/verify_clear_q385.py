"""Q385: once structures are marked, "Clear N" sits in the control bar's second row and unmarks them all.

Marks two structures the way a user does (click on the model, "mark current"), then checks that the bar button is on
screen with the right count, that one press clears every mark and takes the button off the bar again, and that Undo
brings both the marks and the button back. With nothing marked the button must not be on the bar at all.

  python3 scripts/anatomy/q385/verify_clear_q385.py <page dir> [--size 390x844]   -> Q385_CLEAR_OK / Q385_CLEAR_FAIL
"""
import sys, json, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q321"))
import verify_quickcard_q321 as Q
from playwright.sync_api import sync_playwright

STATE = """() => { const b = document.getElementById('sel-clear-bar'), c = document.getElementById('sel-count');
  const r = b ? b.getBoundingClientRect() : null, vis = !!(b && !b.hidden && getComputedStyle(b).display !== 'none' && r.width > 20 && r.height > 20);
  const bar = document.getElementById('q301-bar'), br = bar ? bar.getBoundingClientRect() : null;
  return {n: c ? +c.textContent : -1, btn: !!b, vis: vis, text: b ? b.textContent : '', inView: !!(vis && r.left >= -1 && r.right <= innerWidth + 1 && r.top >= -1 && r.bottom <= innerHeight + 1),
          inBar: !!(vis && br && r.left >= br.left - 1 && r.right <= br.right + 1), barW: br ? Math.round(br.width) : 0, vw: innerWidth}; }"""

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
            s = pg.evaluate(STATE)
            say(s["n"] == 0 and not s["vis"], "nothing marked: no Clear button on the bar  %s" % json.dumps(s))
            ms = []
            for pat in (r"femoris|tibialis|gastro|vastus", r"deltoid|biceps|pector|glute"):
                m = Q.scan(pg, pat, "muscle", grid=16)
                if m and all(m[2]["name"] != x for x in ms):
                    pg.mouse.click(m[0], m[1]); pg.wait_for_timeout(900)
                    pg.evaluate("() => document.getElementById('sel-markcur').click()"); pg.wait_for_timeout(500)
                    ms.append(m[2]["name"])
            s = pg.evaluate(STATE)
            say(len(ms) >= 1 and s["n"] == len(ms), "marked %d structures by click + mark current (%s)" % (s["n"], ", ".join(ms)))
            say(s["vis"] and s["inView"] and s["inBar"] and s["text"].strip().endswith("Clear %d" % s["n"]), "Clear button is on the bar, inside the screen, with the count  %s" % json.dumps(s))
            say(s["barW"] <= s["vw"] + 1, "the bar is not wider than the screen (%d <= %d)" % (s["barW"], s["vw"]))
            n0 = s["n"]
            pg.click("#sel-clear-bar"); pg.wait_for_timeout(700)
            s = pg.evaluate(STATE)
            say(s["n"] == 0 and not s["vis"], "one press clears every mark and the button leaves the bar  %s" % json.dumps(s))
            pg.evaluate("() => NMSKHistory.undo()"); pg.wait_for_timeout(700)
            s = pg.evaluate(STATE)
            say(s["n"] == n0 and s["vis"], "Undo brings the %d marks and the button back  %s" % (n0, json.dumps(s)))
            say(not Q.V.ERRS, "no page errors %s" % Q.V.ERRS[:2])
        finally:
            b.close(); srv.terminate()
    shutil.rmtree(d, ignore_errors=True)
    print("Q385_CLEAR_OK" if not bad else "Q385_CLEAR_FAIL %d" % bad)
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
