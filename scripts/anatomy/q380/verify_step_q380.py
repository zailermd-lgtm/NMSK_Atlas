"""Q380: a press on another control is its own undo step.

Real click on a structure, then -- before the click's debounced history commit has run -- a press on another control
(pointerdown + click on the Selection panel's "mark current"), then Undo. The selection and the name card must survive
the Undo; only the mark is taken back. Repeated presses on the SAME control still merge into one step.

  python3 scripts/anatomy/q380/verify_step_q380.py <page dir>      -> Q380_STEP_OK / Q380_STEP_FAIL
"""
import sys, json, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q321"))
import verify_quickcard_q321 as Q
from playwright.sync_api import sync_playwright

PRESS = """() => { const H = NMSKHistory, st = H.state(), c0 = NMSKQuick.current(), s0 = (H.snapshot().engine || {}).sel;
  const e = document.getElementById('sel-markcur'); if (!e) return {err: 'no sel-markcur'};
  e.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true})); e.click();
  const s1 = (H.snapshot().engine || {}).sel; H.undo();
  const out = {pending: st.pending, sel: [s0, s1, (H.snapshot().engine || {}).sel], card: [c0, NMSKQuick.current()]};
  let g = 0; while (H.state().idx > 1 && g++ < 6) H.undo(); return out; }"""
SAME = """() => { const H = NMSKHistory; H.commit(); const i0 = H.state().idx, e = document.getElementById('sel-markcur');
  for (let k = 0; k < 3; k++) { e.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true})); e.click(); }
  H.commit(); return {steps: H.state().idx - i0}; }"""

def main():
    src = Path(sys.argv[1]); d = Q.page_copy(src, False); bad = 0
    def say(ok, msg):
        nonlocal bad
        print(("  OK   " if ok else "  FAIL ") + msg, flush=True); bad += 0 if ok else 1
    with sync_playwright() as pl:
        srv, b, pg = Q.V.open_page(pl, d, 1400, 900)
        try:
            Q.wait_ready(pg)
            m = Q.scan(pg, r".", "muscle", grid=16)
            say(bool(m), "a muscle to click (%s)" % (m and m[2]["name"]))
            if m:
                for delay in (0, 120, 600):
                    pg.mouse.click(6, 894); pg.wait_for_timeout(1200)
                    pg.mouse.click(m[0], m[1]); pg.wait_for_timeout(delay)
                    r = pg.evaluate(PRESS)
                    ok = (not r.get("err")) and r["sel"][0] is not None and r["sel"][2] == r["sel"][0] and r["card"][0] and r["card"][1] == r["card"][0]
                    say(ok, "press %d ms after the click (commit pending: %s): Undo keeps the selection and the card  %s" % (delay, r.get("pending"), json.dumps(r)))
                    pg.wait_for_timeout(400)
                pg.mouse.click(m[0], m[1]); pg.wait_for_timeout(900)
                r = pg.evaluate(SAME)
                say(r["steps"] <= 1, "three presses on the same control are at most one step (%d)" % r["steps"])
        finally:
            b.close(); srv.terminate()
    shutil.rmtree(d, ignore_errors=True)
    print("Q380_STEP_OK" if not bad else "Q380_STEP_FAIL %d" % bad)
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
