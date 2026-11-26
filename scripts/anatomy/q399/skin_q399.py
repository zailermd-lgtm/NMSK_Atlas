#!/usr/bin/env python3
"""Q399: the outward skin offset of Q398, per digit and for the mouth, judged with Q399's completed test in every pose state.

    python3 scripts/anatomy/q399/skin_q399.py --page-dir DIR --ref-page REFDIR --ref-census REF.json [--json REP] [--cache C]
                                              [--groups g1,g2] [--write]

DIR: the page after Q399's structure step (fix_q399.py); CUR.json: a census of it (or of the page before that step); REFDIR: the page after Q394 (its skin = the source fit before any
offset); REF.json: the verifier's --json of REFDIR (the Q394 values every structure must not exceed).
Rule (Q398's, owner's delegate 2026-11-25): only in SKIN_REGIONS (digits of hand / foot, perionyx, the mouth's pieces), the skin is
moved OUTWARD along its own oriented normal (refit_q398.skin_offset: both sheets together, smooth falloff, held at folds and where
a moved vertex would enter the next digit), so that what lies outside gets GAP mm under the inner sheet; total offset per vertex,
Q398's included, <= SKIN_MAX (4 mm). New here:
  - per DIGIT, not per skin piece: the requirements of one digit (its structures' vertices outside, by the per-digit test) move only
    the skin of that digit (the skin vertices whose nearest digit axis is that digit), fading to 0 over FADE_R mm towards any other
    skin; the mouth is one group.
  - judged with the completed test in all eight states: a group is tried at scale 1, 1/2, 1/4 and kept at the first scale at which
    no structure near it ends worse than max(its Q394 value, its value now) in any state and the total (depth + 0.02 x count, over
    the states) falls; else it does not move.
Skin cards get a "Q399:" badge (vertices moved, max move, added volume). Vertex / triangle counts and order unchanged.
"""
from __future__ import annotations

import argparse, json, re, sys, time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import eval_q399 as EV  # noqa: E402
import refit_q398 as R  # noqa: E402
import conform_palm_q340 as C340  # noqa: E402

U = EV.U
TAG = "Q399:"
SUFFIX = ".q399s"
GAP = 0.3
SKIN_MAX = 4.0
FADE_R = 3.0
NEAR_MM = 12.0
MOUTH_RE = re.compile(r"philtrum|tubercle_of_upper_lip|oral_region|angle_of_mouth|labial_commissure|mentolabial_sulcus")
DIGIT_PIECE_RE = re.compile(r"digits_of_(hand|foot)|perionyx|distal_transverse_arch_of_foot")
EPS = 0.005


def tot(c, states):
    return sum(c[s][1] + 0.02 * c[s][0] for s in states)


class Run:
    def __init__(self, a):
        self.a = a
        self.E = E = EV.Eval(Path(a.page_dir).resolve(), cache=a.cache)
        self.pg = pg = E.pg
        self.states = E.states
        self.cls = pg.cls()
        G394, _ = load_geo(a.ref_page)
        self.skin_all = list(pg.skin_ids) + [k for k in pg.ids if R.NAIL_RE.search(k)]
        self.V0 = {k: pg.V[k].copy() for k in self.skin_all}
        # Q398's offset so far (per vertex), counted against the 4 mm cap
        self.cum0 = {k: np.linalg.norm(pg.V[k] - G394[k], axis=1) for k in self.skin_all if k in G394}
        self.ref = json.loads(Path(a.ref_census).read_text())["states"]
        self.inc, _ = pg.tested()
        self.extra = [k for k in pg.ids if U.PHAL_RE.match(k) or (U.SKIN_SKIP.search(k) and pg.sys.get(k) == "skin")]

    def raw_of(self, k):
        """the sheet labels of skin piece k as the verifier computes them on the page as it would be written (Q353 sheets of its
        CURRENT geometry, Q394 patch vote, Q399 single-sheet candidates; the parity confirmation is global, done after)"""
        pg = self.pg; g = pg.g
        g.V0[k] = (pg.V[k], pg.F[k]); g._sheet.pop(k, None)
        c = U.sheet_vote(pg.V[k], pg.F[k], g.sheets(k)[0], g)[0]
        if U.SINGLE and not U.EAR_RE.search(k) and not U.NO_SINGLE_RE.search(k):
            c = U.single_sheet(pg.V[k], pg.F[k], c, g)
        return c

    def set_skin(self, Vs):
        """move skin pieces and re-label the moved pieces' sheets exactly as the verifier will (a skin offset can change Q353's
        0.8..6 mm partner window, so labels are never carried over from the unmoved skin)"""
        pg, E = self.pg, self.E
        if not hasattr(self, "raw"):
            import hashlib, pickle
            h = hashlib.sha1(b"".join(np.ascontiguousarray(pg.V[k]).tobytes() for k in pg.skin_ids)).hexdigest()[:16]
            cf = Path(self.a.cache or ".") / f"raw399{U.CLS_VER}_{pg.d.name}_{h}.pkl"
            if cf.exists():
                self.raw = pickle.load(open(cf, "rb"))
            else:
                self.raw = {k: self.raw_of(k) for k in pg.skin_ids}
                pickle.dump(self.raw, open(cf, "wb"))
        for k, v in Vs.items():
            if not np.array_equal(pg.V[k], v):
                pg.V[k] = v
                if k in self.raw:
                    self.raw[k] = self.raw_of(k)
        self.cls = U.confirm_single(pg.skin_ids, pg.V, pg.F, self.raw)
        for s in self.states:
            pos = pg.posed(s, ids=pg.skin_ids + self.extra)
            E.sk[s] = U.Skin(pg.skin_ids, pos, pg.F, self.cls)
            E.dg[s] = U.Digits(pg, pos, self.cls) if U.DIGITS else None

    def near(self, new):
        """structures with a vertex within NEAR_MM of a skin vertex that moves"""
        pg = self.pg
        mv = np.vstack([pg.V[k][np.linalg.norm(new[k] - pg.V[k], axis=1) > 1e-6] for k in new])
        t = cKDTree(mv); lo, hi = mv.min(0) - NEAR_MM, mv.max(0) + NEAR_MM
        out = []
        for k in self.inc:
            v = pg.V[k]; b = ((v >= lo) & (v <= hi)).all(1)
            if b.any() and np.isfinite(t.query(v[b], distance_upper_bound=NEAR_MM)[0]).any():
                out.append(k)
        return out

    def violations(self, ev, ids):
        st = self.states; out = set()
        for k in ids:
            for s in st:
                rf = (self.ref[s][k]["n"], self.ref[s][k]["max_mm"]) if k in self.ref[s] else (0, 0.0)
                if ev[k][s][0] > rf[0] or ev[k][s][1] > rf[1] + EPS:
                    out.add((k, s))
        return out

    def evaluate(self, ids):
        return {k: self.E.struct(k) for k in ids}

    def reqs(self, ids, digit=None):
        """requirement points / outward amounts at rest: the outside vertices of `ids`; for a digit only the vertices the per-digit
        test puts in that digit"""
        E, sk = self.E, self.E.sk["rest"]
        P, Rq = [], []
        dg = E.dg["rest"]
        for k in ids:
            v = self.pg.V[k]
            out, so, si, hid, sown = E.test("rest", v)
            if not out.any():
                continue
            m = out.copy()
            if digit is not None:
                m &= dg.assign(v, U.DIG_R) == digit
            if not m.any():
                continue
            # the skin moves along its normal by what it takes for the vertex to be GAP under the inner sheet: depth outside (so)
            # plus the slab's thickness at the closest outer point
            _, q, _, _ = sk.outer.query(v[m])
            th = np.abs(sk.inner.query(q)[0])
            P.append(v[m]); Rq.append(so[m] + th + GAP + R.SKIN_MARGIN)
        if not P:
            return None, None
        return np.vstack(P), np.concatenate(Rq)


def load_geo(d):
    d = Path(d); stem = C340.stem_of(d)
    man, blob, _ = C340.read_page(d, stem)
    return {m["id"]: C340.dec(m, blob)[0] for m in man["meshes"]}, {m["id"]: m.get("rec") for m in man["meshes"]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--ref-page", required=True)
    ap.add_argument("--ref-census", required=True)
    ap.add_argument("--cur-census", required=True, help="the verifier's --json of DIR or of the page before the structure step "
                    "(only its rest entries are used, re-measured here)")
    ap.add_argument("--json")
    ap.add_argument("--cache")
    ap.add_argument("--groups")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--no-revert", action="store_true")
    ap.add_argument("--no-offset", action="store_true")
    a = ap.parse_args(argv)
    if a.write and "/build/" in str(Path(a.page_dir).resolve()):
        raise SystemExit("refusing to write into build/")
    log = lambda s: print(s, flush=True)  # noqa: E731
    t0 = time.time()
    run = Run(a)
    pg, E, st = run.pg, run.E, run.states
    log(f"{pg.d.name}: loaded ({time.time() - t0:.0f}s)")
    dg = E.dg["rest"]
    allowed = {k for k in pg.skin_ids if R.SKIN_REGIONS.search(k)}
    # skin vertices per digit (nearest digit axis) for the per-digit mask
    groups = {}
    for i, dk in enumerate(dg.keys):
        groups[f"digit_{dk[0]}_{dk[1]}_{dk[2]}"] = ("digit", i)
    groups["mouth"] = ("mouth", None)
    if a.groups:
        groups = {g: groups[g] for g in a.groups.split(",")}
    # census now (rest) -> which structures to use as requirements
    cur = {}
    for k in json.loads(Path(a.cur_census).read_text())["states"]["rest"]:
        r = E.struct(k, states=["rest"])
        if r["rest"][0]:
            cur[k] = r["rest"]
    log(f"  outside at rest now: {len(cur)} structures ({time.time() - t0:.0f}s)")
    cum = {k: v.copy() for k, v in run.cum0.items()}
    rep = dict(schema="nmsk.q399.skin.v1", page=pg.d.name, groups={}, skin={}, reverts={})
    # phase 0: Q398's skin offset, group by group (Q398's groups), undone where that removes (state, structure) entries that are
    # worse than their Q394 value (net: fewer such entries after than before)
    G394, REC394 = load_geo(a.ref_page)
    moved = [k for k in run.skin_all if k in G394 and not np.array_equal(G394[k], pg.V[k])]
    rg = {}
    for k in moved:
        m_ = re.search(r"(digits_of_hand|perionyx(?!_foot)|nail_plate(?!_foot)).*_([lr])$", k)
        m2 = re.search(r"(digits_of_foot|perionyx_foot|nail_plate_foot|distal_transverse_arch_of_foot).*_([lr])$", k)
        g = f"hand_{m_.group(2)}" if m_ else f"foot_{m2.group(2)}" if m2 else "mouth" if MOUTH_RE.search(k) else k
        rg.setdefault(g, []).append(k)
    if not a.no_revert:
        for g in sorted(rg):
            ks = rg[g]
            back = {k: G394[k] for k in ks}
            judge = run.near(back)
            base = run.evaluate(judge); vb = run.violations(base, judge)
            Vb = {k: pg.V[k].copy() for k in ks}
            run.set_skin(back)
            now = run.evaluate(judge); vn = run.violations(now, judge)
            keep = len(vn) < len(vb)      # fewer (state, structure) entries worse than Q394 (those it adds go to the structure step)
            if not keep:
                run.set_skin(Vb)
            else:
                for k in ks:
                    cum[k] = np.zeros(len(pg.V[k]))
            rep["reverts"][g] = dict(pieces=ks, judged=len(judge), removed=sorted(map(list, vb - vn)), added=sorted(map(list, vn - vb)),
                                     undone=keep)
            log(f"  revert {g}: {len(ks)} pieces, judged {len(judge)}: worse-than-Q394 entries {len(vb)} -> {len(vn)} "
                f"(removed {len(vb - vn)}, added {len(vn - vb)}) -> {'UNDONE' if keep else 'kept'} ({time.time() - t0:.0f}s)")
    if a.no_offset:
        groups = {}
    for g, (kind, di) in groups.items():
        Vbase = {k: pg.V[k].copy() for k in run.skin_all}
        if kind == "digit":
            near_ids = [k for k in cur if (dg.assign(pg.V[k], U.DIG_R) == di).any()]
            pieces = {k for k in allowed if DIGIT_PIECE_RE.search(k)}
        else:
            pieces = {k for k in allowed if MOUTH_RE.search(k)}
            lo = np.min([pg.V[k].min(0) for k in pieces], 0) - 5; hi = np.max([pg.V[k].max(0) for k in pieces], 0) + 5
            near_ids = [k for k in cur if ((pg.V[k] >= lo) & (pg.V[k] <= hi)).all(1).any()]
        if not near_ids or not pieces:
            continue
        P, Rq = run.reqs(near_ids, di if kind == "digit" else None)
        if P is None:
            continue
        new, srep = R.skin_offset(pg, E.sk["rest"], P, Rq, cum={k: c.copy() for k, c in cum.items()}, allowed=pieces, cls=run.cls)
        if kind == "digit" and new:
            for k in list(new):
                v0 = pg.V[k]; D = new[k] - v0
                lab = dg.assign(v0, U.TUBE_R)
                own = lab == di
                if not own.any():
                    del new[k]; continue
                others = np.vstack([pg.V[x][(dg.assign(pg.V[x], U.TUBE_R) != di)] for x in pg.skin_ids if x in pieces or x == k])
                fade = np.clip(cKDTree(others).query(v0)[0] / FADE_R, 0, 1) if len(others) else np.ones(len(v0))
                new[k] = v0 + D * (own * fade)[:, None]
        new = {k: v for k, v in new.items() if np.abs(v - pg.V[k]).max() > 1e-6}
        if not new:
            log(f"  {g}: nothing to move"); continue
        # the structures near the moved skin, all states
        judge = run.near(new)
        base = run.evaluate(judge)
        kept, tried = 0.0, []
        for sc in (1.0, 0.5, 0.25):
            run.set_skin({k: Vbase[k] + sc * (new[k] - Vbase[k]) for k in new})
            now = run.evaluate(judge)
            worse = []
            for k in judge:
                for s in st:
                    rf = (run.ref[s][k]["n"], run.ref[s][k]["max_mm"]) if k in run.ref[s] else (0, 0.0)
                    lim_n, lim_m = max(rf[0], base[k][s][0]), max(rf[1], base[k][s][1])
                    if now[k][s][0] > lim_n or now[k][s][1] > lim_m + EPS:
                        worse.append((k, s, base[k][s][:2], now[k][s][:2]))
            gain = sum(tot(base[k], st) - tot(now[k], st) for k in judge)
            tried.append(dict(scale=sc, gain=round(gain, 3), worse=[list(map(str, w)) for w in worse[:12]], n_worse=len(worse)))
            if not worse and gain > 1e-3:
                kept = sc
                break
            run.set_skin(Vbase)
        if kept:
            for k in new:
                c = cum.setdefault(k, np.zeros(len(pg.V[k])))
                c += np.linalg.norm(pg.V[k] - Vbase[k], axis=1)
        rep["groups"][g] = dict(kept_scale=kept, tried=tried, requirements=int(len(P)), judged=len(judge))
        log(f"  {g}: {len(P)} requirement points, {len(judge)} structures judged -> kept scale {kept:g} "
            + " ".join(f"[{t['scale']:g}: gain {t['gain']:.2f}, worse {t['n_worse']}]" for t in tried) + f" ({time.time() - t0:.0f}s)")
    changed = {k: pg.V[k] for k in run.skin_all if not np.array_equal(pg.V[k], run.V0[k])}
    REV = {k for g in rep["reverts"].values() if g["undone"] for k in g["pieces"]}
    for k, v in changed.items():
        D = np.linalg.norm(v - run.V0[k], axis=1)
        tot_ = np.linalg.norm(v - G394[k], axis=1) if k in G394 else D
        rep["skin"][k] = dict(moved=int((D > 1e-6).sum()), max_mm=round(float(D.max()), 3), total_offset_max_mm=round(float(tot_.max()), 3))
        assert tot_.max() <= SKIN_MAX + 1e-3, (k, tot_.max())
    if a.write and changed:
        import despike_q366 as D
        man, blob, files = pg.g.man, pg.g.blob, pg.g.files
        repl = {}
        for k, v in changed.items():
            s = rep["skin"][k]
            txt = (f"{TAG} rule-based local skin offset OUTWARD, per digit / at the mouth (Q399; the source-fitted skin here lies closer "
                   f"than the structures it must cover): {s['moved']} vertices moved outward along the skin normal, max {s['max_mm']:.2f} mm "
                   f"(with Q398's offset at most {s['total_offset_max_mm']:.2f} mm, cap {SKIN_MAX:g}), smooth falloff. Not measured.")
            if k in REV and np.allclose(v, G394[k]):
                txt = f"{TAG} Q398's outward skin offset of this piece was undone (it made structures under it read further outside than before Q398)."
                repl[k] = (v, pg.F[k], C340.badge_add(REC394.get(k) or {}, txt))
            else:
                repl[k] = (v, pg.F[k], C340.badge_add(pg.g.M[k].get("rec") or {}, txt))
        man2, blob2 = C340.repack(man, blob, repl)
        old = D.SUFFIX
        try:
            D.SUFFIX = SUFFIX
            rep["files_changed"] = D.write_page(pg.d, pg.g.stem, man, man2, blob2, files, C340)
        finally:
            D.SUFFIX = old
        man3, _, _ = C340.read_page(pg.d, pg.g.stem)
        assert [m["vc"] for m in man3["meshes"]] == [m["vc"] for m in man["meshes"]]
        log("  wrote: " + ", ".join(rep["files_changed"]))
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    log(f"Q399 SKIN {'WRITTEN' if a.write and changed else 'DRY RUN'} {pg.d.name}: groups kept "
        f"{sum(1 for g in rep['groups'].values() if g['kept_scale'])} of {len(rep['groups'])}; skin pieces moved {len(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
