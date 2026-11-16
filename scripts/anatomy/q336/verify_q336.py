#!/usr/bin/env python3
"""Q336: browser check of the genital-region round on built (regen) Base pages.

    python3 scripts/anatomy/q336/verify_q336.py ROOT          # ROOT/viewer_base_female and ROOT/viewer_zan_atlas

One browser at a time, deviceScaleFactor 1, 1400x900. Base · Female: skin_vulva_cvh is in the page's own mesh list, has geometry,
is picked by a real ID-pass pick at its own projected centre with the skin layer solo + opaque, carries its badge on the record;
the search finds it by 'vulva', 'labia minora', 'mons pubis', 'female perineal skin' (aliases) and still finds the CVH
perineal muscles; a text-only term ('perineal membrane') returns an explanation. Base · Male: no skin_vulva_cvh; 'labia minora',
'bulbourethral gland', 'perineal membrane' return explanations; 'testis' still found. 0 page errors on both.
Prints OK / FAIL lines and Q336_VERIFY_OK / Q336_VERIFY_FAIL."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pagehook_q336 as PH  # noqa: E402
import pagegeo_q336 as G    # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

FAIL: list[str] = []


def check(label, cond):
    print(("  OK   " if cond else "  FAIL ") + label)
    if not cond:
        FAIL.append(label)
    return bool(cond)


SEARCH = """(qs) => { const out = {}; for (const q of qs) { const ids = NMSKQ298.filter(q) || []; const r = NMSKQ298.result() || {};
  out[q] = {ids: ids.slice(0, 12), notes: (r.notes || []).map(n => n.name)}; } NMSKQ298.filter(''); return out; }"""


def page(pl, d: Path, female: bool):
    errs = []
    t = PH.test_copy(d, Path("/dev/shm/q336t") / d.name)
    srv, b, pg = PH.open_page(pl, t, 1400, 900, errs=errs)
    tag = "Base F" if female else "Base M"
    try:
        has = pg.evaluate("() => __q336.has('skin_vulva_cvh')")
        if female:
            check(f"[{tag}] skin_vulva_cvh is in the page's mesh list", has)
            man, blob, _ = G.read_page(d)
            m = G.by_id(man)["skin_vulva_cvh"]
            v, f = G.dec(m, blob)
            check(f"[{tag}] it has geometry ({len(v)} vertices, {len(f)} triangles) and is the last mesh (or the one before Q358's rule-based closing skin)",
                  len(f) > 1000 and (man["meshes"][-1]["id"] == "skin_vulva_cvh" or [m["id"] for m in man["meshes"][-2:]] == ["skin_vulva_cvh", "skin_perineum_rule_q358"]))
            rec = m.get("rec") or {}
            check(f"[{tag}] its card carries the registered-other-person badge, the source and the method",
                  "REAL SURFACE OF ANOTHER PERSON" in rec.get("procedural_badge", "") and "e0132226" in rec.get("source", "")
                  and "Q336" in rec.get("procedural_badge", ""))
            # real pick: skin solo opaque, camera in front-below, at the outer sheet's centre
            c = v[: len(v) // 2].mean(0).tolist()
            pg.evaluate("() => { __q336.defaults(); __q336.layer('skin', 1, 'skin'); }")
            pg.evaluate("(c) => __q336.cam({az: 0, el: -0.6, dist: 420, tgt: c})", c)
            pg.wait_for_timeout(500)
            hits = {}
            for dx, dy in [(0, 0), (0, 12), (0, -12), (8, 0), (-8, 0), (0, 24)]:
                s = pg.evaluate("(p) => __q336.toScreen(p)", c)
                got = pg.evaluate("(p) => __q336.pickAt(p[0], p[1])", [s[0] + dx, s[1] + dy])
                hits[got] = hits.get(got, 0) + 1
            check(f"[{tag}] a real pick at its projected centre returns skin_vulva_cvh ({hits})", hits.get("skin_vulva_cvh", 0) >= 3)
            pg.screenshot(path=str(Path("/dev/shm/q336t") / "verify_pick_f.png"))
            pg.evaluate("() => __q336.defaults()")
            qs = ["vulva", "labia minora", "mons pubis", "female perineal skin", "bulbospongiosus", "clitoris", "perineal membrane",
                  "ischioanal fossa"]
            r = pg.evaluate(SEARCH, qs)
            for q in ("vulva", "labia minora", "mons pubis", "female perineal skin"):
                check(f"[{tag}] search '{q}' -> skin_vulva_cvh (top: {r[q]['ids'][:3]})", "skin_vulva_cvh" in r[q]["ids"][:5])
            check(f"[{tag}] search 'bulbospongiosus' still finds bulbospongiosus_cvh", "bulbospongiosus_cvh" in r["bulbospongiosus"]["ids"])
            check(f"[{tag}] search 'clitoris' finds clitoris_cavernous_body", "clitoris_cavernous_body" in r["clitoris"]["ids"])
            check(f"[{tag}] 'perineal membrane' returns the Q336 explanation ({r['perineal membrane']['notes']})",
                  "Perineal membrane" in r["perineal membrane"]["notes"])
            check(f"[{tag}] 'ischioanal fossa' reaches the deep pelvic fat", "fat_deep_pelvis" in r["ischioanal fossa"]["ids"])
        else:
            check(f"[{tag}] no skin_vulva_cvh on the male page", not has)
            qs = ["labia minora", "bulbourethral gland", "perineal membrane", "anal canal", "testis"]
            r = pg.evaluate(SEARCH, qs)
            for q, n in (("labia minora", "Labia minora"), ("bulbourethral gland", "Bulbourethral gland"),
                         ("perineal membrane", "Perineal membrane"), ("anal canal", "Anal canal")):
                check(f"[{tag}] '{q}' returns the explanation ({r[q]['notes']})", n in r[q]["notes"])
            check(f"[{tag}] 'testis' still finds zan_testis_l/r", any(i.startswith("zan_testis") for i in r["testis"]["ids"]))
    finally:
        b.close(); srv.terminate()
    check(f"[{tag}] 0 page errors ({errs[:2]})", not errs)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    root = Path(argv[0])
    with sync_playwright() as pl:
        page(pl, root / "viewer_base_female", True)
        page(pl, root / "viewer_zan_atlas", False)
    print("Q336_VERIFY_" + ("OK" if not FAIL else "FAIL"), len(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
