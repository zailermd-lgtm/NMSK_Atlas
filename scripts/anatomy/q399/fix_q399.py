#!/usr/bin/env python3
"""Q399: what Q398 made worse, and what the completed test still finds outside (Base · Male / Base · Female).

    python3 scripts/anatomy/q399/fix_q399.py --page-dir DIR --ref-page REFDIR --ref-census REF.json --cur-census CUR.json
                                             [--json REP] [--cache C] [--only a,b] [--write]

DIR is a private copy of the page as published after Q398; REFDIR the same page as it was after Q394 (the `.q398` originals);
REF.json / CUR.json the verifier's --json of both (scripts/anatomy/q394/verify_under_skin_q394.py, the Q399 test: single-sheet
completion and per-digit test). For every structure that is outside in some state of CUR (bones and cartilage excepted: never
moved), candidates, each rule-based and each judged by the same census in all eight states against the page's skin and rig:
  cur        as it is (Q398)
  q394       its geometry before Q398 (Q398's refit undone) -- only where Q398 changed it
  refit      Q398's depth-remap refit (scripts/anatomy/q398/refit_q398.py refit_one, its guards: move, volume / area, flips, bone)
             applied to `cur` against the completed test
  refit394   the same applied to `q394`
The kept candidate is the first by (number of states worse than its Q394 value, sum over states of depth + 0.02 x vertices outside),
`cur` on a tie. "Worse than Q394" = more vertices outside, or deeper by > 0.005 mm, than REF in that state. Vertex / triangle counts
and order unchanged; each changed card gets a "Q399:" badge (an undone refit takes back its Q394 card record). Deterministic.
"""
from __future__ import annotations

import argparse, json, pickle, sys, time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import eval_q399 as EV  # noqa: E402
import refit_q398 as R  # noqa: E402
import conform_skin_q353 as Q  # noqa: E402
import conform_palm_q340 as C340  # noqa: E402

TAG = "Q399:"
SUFFIX = ".q399"
NO_MOVE = ("bone", "cartilage")
EPS = 0.005


def load_geo(d):
    d = Path(d); stem = C340.stem_of(d)
    man, blob, _ = C340.read_page(d, stem)
    return {m["id"]: C340.dec(m, blob)[0] for m in man["meshes"]}, {m["id"]: m.get("rec") for m in man["meshes"]}


def score(c, ref, states):
    viol = [s for s in states if c[s][0] > ref[s][0] or c[s][1] > ref[s][1] + EPS]
    return len(viol), round(sum(c[s][1] + 0.02 * c[s][0] for s in states), 4), viol


def note(kind, k, ref, cur, new, states, fit=None):
    def tot(c):
        return sum(c[s][0] for s in states), max(c[s][1] for s in states)
    a, b = tot(cur), tot(new)
    what = {"q394": "Q398's refit of this structure was undone (it made it lie further outside the skin in some state than before)",
            "refit": "moved inward under the skin by Q398's rule-based depth remap, judged with Q399's completed outside test",
            "refit394": "Q398's refit undone and the rule-based depth remap applied again, judged with Q399's completed outside test"}[kind]
    fx = ""
    if fit:
        vc = (f"volume change {fit['volume_signed_pct']:+.2f} %" if fit.get("volume_signed_pct") is not None
              else f"open surface, area change {fit.get('area_change_pct', 0):.2f} %")
        fx = f" ({fit.get('moved', 0)} vertices moved, max {fit.get('max_mm', 0):.1f} mm; {vc})"
    return (f"{TAG} {what}{fx}. Vertices outside the skin over the eight checked pose states: {a[0]} (deepest {a[1]:.1f} mm) -> "
            f"{b[0]} (deepest {b[1]:.1f} mm). Rule-based correction, not measured.")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--ref-page", required=True)
    ap.add_argument("--ref-census", required=True)
    ap.add_argument("--cur-census", required=True)
    ap.add_argument("--rig")
    ap.add_argument("--json")
    ap.add_argument("--cache")
    ap.add_argument("--only")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--checkpoint")
    ap.add_argument("--again", action="store_true", help="a second pass on a page Q399 already changed (after skin_q399.py)")
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    if a.write and "/build/" in str(d):
        raise SystemExit("refusing to write into build/")
    t0 = time.time()
    E = EV.Eval(d, a.rig, cache=a.cache)
    pg = E.pg
    for m in pg.g.man["meshes"] if not a.again else []:
        if TAG in json.dumps(m.get("rec") or {}):
            raise SystemExit(f"{m['id']}: already carries a {TAG} note (run on the original page)")
    states = E.states
    G394, REC394 = load_geo(a.ref_page)
    ref = json.loads(Path(a.ref_census).read_text())["states"]
    cur = json.loads(Path(a.cur_census).read_text())["states"]
    todo = sorted({k for s in cur for k in cur[s]})
    if a.only:
        todo = a.only.split(",")
    log = lambda s: print(s, flush=True)  # noqa: E731
    log(f"{pg.d.name}: {len(todo)} structures outside in some state; loaded in {time.time() - t0:.0f}s")
    lo = np.min([pg.V[k].min(0) for k in pg.ids if pg.sys[k] != "skin"], 0) - 20
    hi = np.max([pg.V[k].max(0) for k in pg.ids if pg.sys[k] != "skin"], 0) + 20
    bones = Q.Bones(pg.g, lo, hi)
    sk = E.sk["rest"]
    done = {}
    if a.checkpoint and Path(a.checkpoint).exists():
        done = pickle.load(open(a.checkpoint, "rb"))
    for i, k in enumerate(todo):
        if k in done:
            continue
        rf = {s: ((ref[s][k]["n"], ref[s][k]["max_mm"]) if k in ref[s] else (0, 0.0)) for s in states}
        v_cur = pg.V[k].copy()
        cands, fits = {"cur": v_cur}, {}
        if k in G394 and not np.array_equal(G394[k], v_cur) and G394[k].shape == v_cur.shape:
            cands["q394"] = G394[k]
        if pg.sys[k] not in NO_MOVE:
            for nm, base in (("refit", "cur"), ("refit394", "q394")):
                if base not in cands:
                    continue
                pg.V[k] = cands[base].copy()
                try:
                    r, v = R.refit_one(pg, sk, k, bones, Q)
                finally:
                    pg.V[k] = v_cur
                if v is not None:
                    cands[nm] = v; fits[nm] = {x: r.get(x) for x in ("status", "moved", "max_mm", "volume_signed_pct", "area_change_pct", "reason")}
        ev = {}
        for nm, v in cands.items():
            ev[nm] = E.struct(k) if nm == "cur" else E.struct(k, v, E.entry(k, v))
        sc = {nm: score(ev[nm], rf, states) for nm in ev}
        best = min(ev, key=lambda nm: (sc[nm][0], sc[nm][1], nm != "cur"))
        if sc[best][:2] == sc["cur"][:2]:
            best = "cur"
        done[k] = dict(ref=rf, eval={nm: {s: list(ev[nm][s]) for s in states} for nm in ev}, score={nm: list(sc[nm]) for nm in sc},
                       fits=fits, best=best, _v=None if best == "cur" else cands[best])
        log(f"  [{i + 1}/{len(todo)}] {k:58s} {pg.sys[k]:9s} -> {best:8s} " +
            " ".join(f"{nm}:{sc[nm][0]}/{sc[nm][1]:.1f}" for nm in sc))
        if a.checkpoint and i % 10 == 0:
            pickle.dump(done, open(a.checkpoint, "wb"))
    if a.checkpoint:
        pickle.dump(done, open(a.checkpoint, "wb"))
    changed = {k: x for k, x in done.items() if x["best"] != "cur"}
    rep = dict(schema="nmsk.q399.fix.v1", page=pg.d.name, generated=time.strftime("%Y-%m-%d"), states=states,
               structures={k: {x: y for x, y in v.items() if x != "_v"} for k, v in done.items()}, changed=sorted(changed), written=False)
    if a.write and changed:
        import despike_q366 as D
        man, blob, files = pg.g.man, pg.g.blob, pg.g.files
        repl = {}
        for k, x in changed.items():
            rec = REC394.get(k) if x["best"] in ("q394", "refit394") else (pg.g.M[k].get("rec") or {})
            ev = x["eval"]
            rec = C340.badge_add(rec, note(x["best"], k, x["ref"], ev["cur"], ev[x["best"]], states, x["fits"].get(x["best"])))
            repl[k] = (x["_v"], pg.F[k], rec)
        man2, blob2 = C340.repack(man, blob, repl)
        old = D.SUFFIX
        try:
            D.SUFFIX = SUFFIX
            rep["files_changed"] = D.write_page(d, pg.g.stem, man, man2, blob2, files, C340)
        finally:
            D.SUFFIX = old
        rep["written"] = True
        man3, blob3, _ = C340.read_page(d, pg.g.stem)
        qr = {}
        for m in man3["meshes"]:
            if m["id"] in changed:
                P3, F3 = C340.dec(m, blob3)
                qr[m["id"]] = round(float(np.abs(P3 - changed[m["id"]]["_v"]).max()), 5)
                assert np.array_equal(F3, pg.F[m["id"]])
        rep["quantisation_residual_mm"] = qr
        assert [m["vc"] for m in man3["meshes"]] == [m["vc"] for m in man["meshes"]]
        assert [m["id"] for m in man3["meshes"]] == [m["id"] for m in man["meshes"]]
        log("  wrote: " + ", ".join(rep["files_changed"]) + f" (originals kept as *{SUFFIX})")
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else (
            float(o) if isinstance(o, np.floating) else int(o) if isinstance(o, np.integer) else str(o))) + "\n", encoding="utf-8")
    nv = sum(1 for x in done.values() if x["score"][x["best"]][0] > 0)
    by = ", ".join(f"{b} {sum(1 for x in changed.values() if x['best'] == b)}" for b in ("q394", "refit", "refit394"))
    log(f"Q399 FIX {'WRITTEN' if rep['written'] else 'DRY RUN'} {pg.d.name}: {len(done)} structures, changed {len(changed)} "
        f"({by}); "
        f"still worse than Q394 in some state: {nv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
