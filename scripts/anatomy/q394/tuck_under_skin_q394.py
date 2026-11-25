#!/usr/bin/env python3
"""Q394: rule-based tuck of the structures that lie outside the skin (Base · Male / Base · Female), rest geometry.

    python3 scripts/anatomy/q394/tuck_under_skin_q394.py --page-dir DIR                     # dry run: plan + guards, writes nothing
    python3 scripts/anatomy/q394/tuck_under_skin_q394.py --page-dir DIR --write             # and write DIR (originals kept as *.q394)
    options: --json FILE (report), --allow-build (permit --write into build/: the main thread's apply step), --only ID[,ID]

The test is scripts/anatomy/q394/under_skin_q394.py (Q353 outside_count, complete, ray-parity confirmed). For each structure of the
set that has vertices outside at rest:
  move     every outside vertex is required to lie GAP mm under the skin's INNER sheet (Q353's tuck rule and GAP: the skin is
           left where it is, the structure goes under it), along the inner sheet's normal; the requirement is spread over the
           structure by Q353's Lipschitz envelope (a vertex d mm from a requirement moves by at most amp - K d, so there is no
           kink) with the Gaussian-weighted mean direction; TRIES from the most local (K 0.5) to Q353's own (K 0.15); up to ROUNDS
           re-tests. Nothing but the structure moves; vertex / triangle counts and order unchanged (the pose rig still matches).
  bone     a vertex the move would put into a bone keeps its place and the move fades in around it over BONE_R mm
           (bone_yield); a required vertex held so stays outside and the structure is NOT FIXED (no room between skin and bone).
  never    a bone is not moved (the skeleton carries the joints, the rig and the measurements: a bone outside the skin is a
           skin defect, listed open); the skin is never moved.
  guards   (a structure failing any keeps its bytes and is listed NOT FIXED with the reason): per-vertex move <= CAP;
           0 vertices outside after; volume change <= VOL_MAX % (closed manifold mesh; an open mesh: area change <= VOL_MAX %);
           flipped faces <= FLIP_MAX % of the moved faces; no moved vertex newly inside a bone (Q353 Bones); a structure with
           more than MOSTLY of its vertices outside is not tucked (that is not a poke-through, the structure is in the wrong
           place) -- listed NOT FIXED.
  card     each tucked structure's card gets a "Q394:" badge: rule-based, vertices moved, max / p95 move, volume change,
           clearance under the inner sheet.
Deterministic.
"""
from __future__ import annotations

import argparse, json, shutil, sys, time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for _p in ("q394", "q353", "q340", "q366"):
    if str(HERE.parent / _p) not in sys.path:
        sys.path.insert(0, str(HERE.parent / _p))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import under_skin_q394 as U  # noqa: E402

TAG = "Q394:"
SUFFIX = ".q394"
GAP = 0.3          # mm under the inner sheet (Q353 GAP)
TRIES = ((0.5, 4.0), (0.5, 10.0), (0.3, 4.0), (0.3, 10.0), (0.15, 4.0), (0.15, 10.0), (0.15, 1e6))
# (envelope slope K, direction sigma mm), most local first: a vertex d mm from a requirement amp moves by at most amp - K d;
# K 0.15 / sigma 4, 10, 1e6 are Q353's own tuck settings
ROUNDS = 6
CAP = 12.0         # mm per vertex
VOL_MAX = 2.0      # %
FLIP_MAX = 0.5     # % of moved faces
MOSTLY = 0.25      # fraction of vertices outside above which a structure is not tucked
NO_MOVE_SYS = ("bone",)


BONE_R = 3.0       # mm: around a vertex the move would put into a bone the move fades in over this distance


def bone_yield(v0, v, bones, rounds=4):
    """the move is held back where it would put a vertex into a bone that was not in it: the displacement is scaled by
    s(x) = min(1, dist(x, held vertices) / BONE_R) (Lipschitz, no kink), repeated while new vertices enter a bone"""
    from scipy.spatial import cKDTree
    D = v - v0
    held = np.zeros(len(v0), bool)
    in0 = bones.inside(v0)
    for _ in range(rounds):
        cur = v0 + D
        mv = np.linalg.norm(D, axis=1) > 1e-6
        bad = np.zeros(len(v0), bool)
        if mv.any():
            ib = np.zeros(len(v0), bool); ib[mv] = bones.inside(cur[mv])
            bad = ib & ~in0
        if not bad.any():
            break
        held |= bad
        d, _ = cKDTree(v0[held]).query(v0)
        D = D * np.clip(d / BONE_R, 0.0, 1.0)[:, None]
    return v0 + D


def area(v, f):
    return float(np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1).sum() / 2)


def outside_of(sk, v):
    out, so, si, own, tang, q = sk.test(v)
    c = np.where(out)[0]
    if len(c):
        conf = sk.confirm(v[c])
        out[c[~conf]] = False
    return out, so, si


def tuck_one(pg, sk, k, bones, Q):
    v0 = pg.V[k].copy(); f = pg.F[k]
    out0, so0, si0 = outside_of(sk, v0)
    n0 = int(out0.sum())
    res = dict(sys=pg.sys[k], nv=len(v0), before=dict(n=n0, max_mm=round(float(so0[out0].max()), 3) if n0 else 0.0))
    if n0 == 0:
        res.update(status="clean"); return res, None
    if pg.sys[k] in NO_MOVE_SYS:
        res.update(status="NOT FIXED", reason="a bone is not moved (skin defect over the bone)"); return res, None
    if n0 > MOSTLY * len(v0):
        res.update(status="NOT FIXED", reason=f"mostly outside ({n0}/{len(v0)} > {MOSTLY:.0%}): not a poke-through"); return res, None
    tries = []
    for K, sig in TRIES:
        v = v0.copy()
        for _ in range(ROUNDS):
            o, so, si = outside_of(sk, v)
            if not o.any():
                break
            si_, _, ti, _ = sk.inner.query(v[o])
            dirs = sk.inner.N[ti]                  # into the body
            req = GAP - si_
            v = v + Q.envelope(v, v[o], req, dirs, K=K, sig=sig)
        v = bone_yield(v0, v, bones)
        o, so, si = outside_of(sk, v)
        D = v - v0; dn = np.linalg.norm(D, axis=1); mv = dn > 1e-6
        fg = Q.face_guards(v0, v, f)
        dv = Q.vol_change(fg)
        da = abs(area(v, f) - area(v0, f)) / max(area(v0, f), 1e-9) * 100
        b0 = int(bones.inside(v0[mv]).sum()); b1 = int(bones.inside(v[mv]).sum())
        fails = []
        if dn.max() > CAP:
            fails.append(f"move {dn.max():.2f} mm > cap {CAP:g}")
        if o.any():
            fails.append(f"{int(o.sum())} vertices still outside")
        if fg["flipped_pct_moved_faces"] > FLIP_MAX:
            fails.append(f"flipped {fg['flipped_pct_moved_faces']} % of moved faces")
        if b1 > b0:
            fails.append(f"moved vertices inside bone {b0} -> {b1}")
        if dv is not None and dv > VOL_MAX:
            fails.append(f"volume change {dv:.2f} %")
        if dv is None and da > VOL_MAX:
            fails.append(f"area change {da:.2f} % (open mesh)")
        t = dict(slope=K, sigma_mm=sig, moved=int(mv.sum()), max_mm=round(float(dn.max()), 3),
                 p95_mm=round(float(np.percentile(dn[mv], 95)), 3) if mv.any() else 0.0,
                 volume_change_pct=None if dv is None else round(dv, 3), area_change_pct=round(da, 3),
                 closed_manifold=fg["closed_manifold"], flipped_pct=fg["flipped_pct_moved_faces"], inside_bone=[b0, b1],
                 after_outside=int(o.sum()), fails=fails)
        tries.append(t)
        if not fails:
            res.update(status="FIXED", tries=tries, **{x: t[x] for x in ("slope", "sigma_mm", "moved", "max_mm", "p95_mm", "volume_change_pct",
                                                                           "area_change_pct", "closed_manifold")})
            return res, v
    res.update(status="NOT FIXED", reason="; ".join(tries[-1]["fails"]), tries=tries)
    return res, None


def note(r):
    vc = (f"volume change {r['volume_change_pct']:.2f} %" if r["volume_change_pct"] is not None
          else f"open surface, area change {r['area_change_pct']:.2f} %")
    return (f"{TAG} rule-based tuck under the skin: {r['before']['n']} of its {r['nv']} vertices lay outside the skin surface (up to "
            f"{r['before']['max_mm']:.1f} mm); they were moved to {GAP:g} mm under the skin's inner sheet and the move faded over the "
            f"neighbouring vertices ({r['moved']} moved, max {r['max_mm']:.1f} mm, p95 {r['p95_mm']:.1f} mm; {vc}). The skin did not move; "
            f"the shape here is a rule-based correction, not measured.")


def main(argv=None):
    import conform_skin_q353 as Q
    import conform_palm_q340 as C340
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--allow-build", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--only")
    ap.add_argument("--cache")
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    if a.write and "/build/" in str(d) and not a.allow_build:
        raise SystemExit("refusing to write into build/ without --allow-build")
    pg = U.Page(d, cache_dir=a.cache)
    for m in pg.g.man["meshes"]:
        if TAG in json.dumps(m.get("rec") or {}):
            raise SystemExit(f"{m['id']}: already carries a {TAG} note (refused: run on the original page)")
    sk = U.Skin(pg.skin_ids, pg.V, pg.F, pg.cls())
    inc, exc = pg.tested()
    t0 = time.time()
    c = U.census(pg, "rest", ids=inc)
    c.pop("__suspect__", None)
    todo = sorted(c) if not a.only else [x for x in a.only.split(",")]
    print(f"{pg.d.name}: {len(c)} structures outside at rest ({time.time() - t0:.0f}s)", flush=True)
    lo = np.min([pg.V[k].min(0) for k in todo], 0) - 20; hi = np.max([pg.V[k].max(0) for k in todo], 0) + 20
    bones = Q.Bones(pg.g, lo, hi)
    out, newv = {}, {}
    for k in todo:
        r, v = tuck_one(pg, sk, k, bones, Q)
        out[k] = r
        if v is not None:
            newv[k] = v
        print(f"   {k:58s} {r['before']['n']:5d} max {r['before']['max_mm']:6.2f} -> {r['status']}"
              + (f" (move max {r['max_mm']:.2f}, vol {r['volume_change_pct']}, area {r['area_change_pct']:.2f} %)" if r["status"] == "FIXED"
                 else f" ({r.get('reason', '')})"), flush=True)
    rep = dict(schema="nmsk.q394.tuck.v1", page=pg.d.name, generated=time.strftime("%Y-%m-%d"),
               parameters=dict(gap_mm=GAP, tries=TRIES, rounds=ROUNDS, cap_mm=CAP, vol_max_pct=VOL_MAX,
                               flip_max_pct=FLIP_MAX, mostly=MOSTLY, no_move_sys=NO_MOVE_SYS),
               structures=out, fixed=sorted(newv), not_fixed=sorted(k for k, r in out.items() if r["status"] == "NOT FIXED"),
               written=False)
    if a.write and newv:
        import despike_q366 as D
        man, blob, files = pg.g.man, pg.g.blob, pg.g.files
        repl = {k: (newv[k], pg.F[k], C340.badge_add(pg.g.M[k].get("rec") or {}, note(out[k]))) for k in newv}
        man2, blob2 = C340.repack(man, blob, repl)
        old = D.SUFFIX
        try:
            D.SUFFIX = SUFFIX
            rep["files_changed"] = D.write_page(d, pg.g.stem, man, man2, blob2, files, C340)
        finally:
            D.SUFFIX = old
        rep["written"] = True
        man3, blob3, _ = C340.read_page(d, pg.g.stem)
        for m in man3["meshes"]:
            if m["id"] in newv:
                P3, F3 = C340.dec(m, blob3)
                rep["structures"][m["id"]]["quantisation_residual_mm"] = round(float(np.abs(P3 - newv[m["id"]]).max()), 5)
                assert np.array_equal(F3, pg.F[m["id"]])
        assert [m["vc"] for m in man3["meshes"]] == [m["vc"] for m in man["meshes"]]
        print("  wrote: " + ", ".join(rep["files_changed"]) + f" (originals kept as *{SUFFIX})")
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else (
            float(o) if isinstance(o, np.floating) else int(o) if isinstance(o, np.integer) else str(o))) + "\n", encoding="utf-8")
    print(f"Q394 TUCK {'WRITTEN' if rep['written'] else 'DRY RUN'} {pg.d.name}: fixed {len(newv)}, not fixed {len(rep['not_fixed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
