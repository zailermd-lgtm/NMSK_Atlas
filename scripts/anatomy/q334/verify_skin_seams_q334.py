#!/usr/bin/env python3
"""Q334: no imaginary line where two skin regions meet (Z engine, Base pages).

    python3 scripts/anatomy/q334/verify_skin_seams_q334.py /dev/shm/q334/viewer_zan_atlas [--size WxH]

Runs on a built (regen) page dir. AFTER = the page as built (if its html lacks the Q334 blocks, a patched test copy is
made); BEFORE = a test copy with the Q334 blocks stripped (`patch_seams_q334.py --hook-only`), both in /dev/shm.

The metric is measured on rendered pixels. From the page's own geometry: every border edge two skin regions share
(outer surface; the nail plate excluded, it meets the skin at a real boundary), its midpoint, the surface normal and the
in-surface direction across it. Per camera (whole body, trunk, back, shoulder, knee, face) the border points that face
the camera are projected; a point counts only when the ID pass of the solid skin names region A 4 px to one side and
region B 4 px to the other (that is also the picking check). Across each border, luminance on a 13 px profile:
    seam = max(|centre - mean(sides)|, |side A - side B|)       (centre = 3 px on the border, sides = 3..6 px out)
and the same at a control point 12 px inside region A. Ratio = mean(seam) / mean(control): ~1 = the border cannot be
told from the skin around it. A view passes at ratio <= 1.6, or when the border contrast itself is halved; in X-ray (skin
at 0.06, the profile is the bones and muscles behind) when it is no worse than before. Views: skin solid (solo), skin faded (solo, 0.3), the default view (all layers), X-ray.
Also: hide B -> its neighbour's real boundary (the wall) is drawn and the click no longer finds B; select / hover A;
frame time after <= 1.10 x before; 0 page errors. Prints OK / FAIL lines and Q334_SEAMS_OK / Q334_SEAMS_FAIL."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "scripts/anatomy/q319"))
sys.path.insert(0, str(HERE))
import verify_search_q319 as V            # noqa: E402  (serve / route / open_page / check / ERRS)
import zgeo_q334 as Z                     # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ERRS = V.ERRS
check = V.check
SKIP = re.compile(r"^nail plate", re.I)
RATIO_MAX = 1.6          # after: a border no more visible than 1.6 x the skin's own variation next to it
ZONES = [("body", None, None), ("trunk", "Umbilical region (skin)", 450), ("back", "Lumbar region (skin)", 450),
         ("shoulder", "Deltoid region (skin)", 330), ("knee", "Anterior region of knee (skin)", 330), ("face", "Buccal region (skin)", 230)]
VIEWS = ["solid", "faded", "default", "xray"]


# ------------------------------------------------------------------------------------------- geometry: the borders
def borders(page: Path):
    man, binb = Z.load(str(page))
    ms = man["meshes"]
    sk = [i for i, m in enumerate(ms) if m.get("sys") == "skin" and not SKIP.match(m.get("name", ""))]
    P, O, F, FO, off = [], [], [], [], 0
    for i in sk:
        p, ix = Z.mesh(man, binb, i)
        P.append(p); O.append(np.full(len(p), i)); F.append(ix + off); FO.append(np.full(len(ix), i)); off += len(p)
    P = np.concatenate(P); O = np.concatenate(O); F = np.concatenate(F); FO = np.concatenate(FO)
    pr = cKDTree(P).query_pairs(0.03, output_type="ndarray")
    pr = pr[O[pr[:, 0]] != O[pr[:, 1]]]
    n = len(P)
    _, lab = connected_components(coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(n, n)), directed=False)
    fn = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    fu = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
    edges = {}
    for k in range(3):
        a, b, c = F[:, k], F[:, (k + 1) % 3], F[:, (k + 2) % 3]
        ca, cb = lab[a], lab[b]
        for f in np.where(ca != cb)[0]:
            key = (min(ca[f], cb[f]), max(ca[f], cb[f]))
            edges.setdefault(key, []).append((f, a[f], b[f], c[f]))
    out = []
    for key, fs in edges.items():
        if len({FO[f] for f, *_ in fs}) < 2:
            continue
        best = None
        for i1 in range(len(fs)):
            for i2 in range(i1 + 1, len(fs)):
                f1, a1, b1, c1 = fs[i1]; f2, a2, b2, c2 = fs[i2]
                if FO[f1] == FO[f2]:
                    continue
                d = float(fu[f1] @ fu[f2])
                if abs(d) < 0.6:
                    continue
                m = (P[a1] + P[b1]) / 2; t = P[b1] - P[a1]; L = np.linalg.norm(t)
                if L < 1.0:
                    continue
                t /= L
                w1 = P[c1] - m; w1 -= t * (w1 @ t); w2 = P[c2] - m; w2 -= t * (w2 @ t)
                if w1 @ w2 >= 0:                        # the two walls: same side of the edge
                    continue
                if best is None or abs(d) > best[0]:
                    nn = fu[f1] + np.sign(d) * fu[f2]; nn /= np.linalg.norm(nn)
                    u = w1 / np.linalg.norm(w1)
                    best = (abs(d), m, nn, u, int(FO[f1]), int(FO[f2]))
        if best:
            out.append(best[1:])
    ids = [m.get("id") or m.get("name") for m in ms]
    M = np.array([o[0] for o in out]); N = np.array([o[1] for o in out]); U = np.array([o[2] for o in out])
    A = [ids[o[3]] for o in out]; B = [ids[o[4]] for o in out]
    # the outward normal of a closed outward-wound region: flip a border normal that points into the body
    ctr = P.mean(0)
    return {"M": M, "N": N, "U": U, "A": A, "B": B, "names": {ids[i]: ms[i]["name"] for i in sk}, "ctr": ctr, "ms": ms, "ids": ids, "Pall": P, "O": O}


def zone_cam(G, piece, dist):
    sel = [k for k, a in enumerate(G["A"]) if G["names"].get(G["A"][k]) == piece or G["names"].get(G["B"][k]) == piece]
    pts = G["M"][sel]
    side = np.sign(pts[:, 0].mean()) if len(pts) else 1
    sel = [k for k in sel if np.sign(G["M"][k][0]) == side or abs(G["M"][k][0]) < 1] or sel
    tgt = G["M"][sel].mean(0)
    nrm = G["N"][sel].mean(0); nrm /= np.linalg.norm(nrm)
    return {"az": float(np.arctan2(nrm[0], nrm[2])), "el": float(np.clip(np.arcsin(nrm[1]), -0.6, 0.6)), "dist": dist, "tgt": [float(x) for x in tgt]}


# ------------------------------------------------------------------------------------------------ the test copies
def make_copy(src: Path, root: Path, mode: str) -> Path:
    d = root / mode / src.name
    d.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        t = d / f.name
        if f.suffix == ".html":
            shutil.copy(f, t)
        elif not t.exists():
            os.symlink(f.resolve(), t)
    htmls = [str(x) for x in d.glob("*.html")]
    patch = [sys.executable, str(HERE / "patch_seams_q334.py")] + (["--hook-only"] if mode == "before" else []) + htmls
    subprocess.run(patch, check=True, stdout=subprocess.DEVNULL)
    return d


# ------------------------------------------------------------------------------------------------------ in the page
def open_page(pl, d: Path, w: int, h: int, timeout=300000):
    """verify_search_q319.open_page with room for a busy machine (software GL, other agents' browsers)"""
    srv, port = V.serve(d)
    b = pl.chromium.launch(args=V.ARGS, executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": w, "height": h})
    pg.on("pageerror", lambda e: ERRS.append("page error: " + str(e)))
    pg.route("**/*", V.route)
    html = sorted(d.glob("atlas_viewer*.html"))[0]
    pg.goto(f"http://127.0.0.1:{port}/{html.name}", wait_until="load", timeout=timeout)
    pg.wait_for_function("window.NMSKQ301 && window.NMSKQ298 && window.NMSKSelectCtl && window.__q334", timeout=timeout)
    try:
        pg.wait_for_selector('.mw-tile[data-mode="anat"]', timeout=timeout)
        pg.click('.mw-tile[data-mode="anat"]'); pg.wait_for_timeout(3000)
    except Exception:
        print("     (no mode wall to dismiss)")
    return srv, b, pg


def set_view(pg, view):
    if view == "solid":
        pg.evaluate("() => { __q334.preset('btn-solid'); __q334.layer('skin', 1, 'skin'); }")
    elif view == "faded":
        pg.evaluate("() => { __q334.preset('btn-solid'); __q334.layer('skin', 0.3, 'skin'); }")
    elif view == "default":
        pg.evaluate("() => __q334.defaults()")
    elif view == "xray":
        pg.evaluate("() => { __q334.preset('btn-xray'); }")
    pg.wait_for_timeout(250)


def measure(pg, G, cam, w, h):
    pg.evaluate("(c) => __q334.cam(c)", cam); pg.wait_for_timeout(200)
    st = pg.evaluate("() => __q334.cam()")
    ce, se = np.cos(st["el"]), np.sin(st["el"])
    eye = np.array(st["tgt"]) + st["dist"] * np.array([ce * np.sin(st["az"]), se, ce * np.cos(st["az"])])
    M, N, U = G["M"], G["N"], G["U"]
    vdir = eye - M; vd = vdir / np.linalg.norm(vdir, axis=1, keepdims=True)
    facing = np.where(np.abs((N * vd).sum(1)) > 0.45)[0]
    if not len(facing):
        return None
    pts = [list(map(float, M[k])) for k in facing] + [list(map(float, M[k] + U[k])) for k in facing]
    sc = pg.evaluate("(P) => P.map(p => __q334.toScreen(p))", pts)
    n = len(facing); keep = []
    for j, k in enumerate(facing):
        a, b = sc[j], sc[n + j]
        if not a or not b:
            continue
        d = np.array([b[0] - a[0], b[1] - a[1]]); L = np.linalg.norm(d)
        if L < 0.35 or not (30 < a[0] < w - 30 and 120 < a[1] < h - 60):
            continue
        keep.append((k, np.array(a[:2]), d / L))
    if not keep:
        return None
    # picking / visibility in the solid skin view
    set_view(pg, "solid")
    q = []
    for k, a, d in keep:
        q += [list(a + 4 * d), list(a - 4 * d), list(a + 12 * d)]
    got = pg.evaluate("(P) => __q334.ids(P, false)", q)
    vis, pickok, ctrl = [], 0, []
    for j, (k, a, d) in enumerate(keep):
        ga, gb, gc = got[3 * j], got[3 * j + 1], got[3 * j + 2]
        if ga in (G["A"][k], G["B"][k]) or gb in (G["A"][k], G["B"][k]):
            if ga == G["A"][k] and gb == G["B"][k]:
                pickok += 1; vis.append((k, a, d)); ctrl.append(gc == G["A"][k])
    seen = sum(1 for j in range(len(keep)) if got[3 * j] in (G["A"][keep[j][0]], G["B"][keep[j][0]]) or got[3 * j + 1] in (G["A"][keep[j][0]], G["B"][keep[j][0]]))
    res = {"n": len(vis), "pick": (pickok, seen)}
    if len(vis) < 8:
        return res
    ks = np.arange(-6, 7)
    pq = []
    for (k, a, d) in vis:
        pq += [list(a + t * d) for t in ks] + [list(a + (12 + t) * d) for t in ks]
    for view in VIEWS:
        set_view(pg, view)
        lum = np.array(pg.evaluate("(P) => __q334.sample(P)", pq), float).reshape(len(vis), 2, len(ks))

        def score(prof):
            c = prof[:, 5:8].mean(1); sa = prof[:, 9:13].mean(1); sb = prof[:, 0:4].mean(1)
            return np.maximum(np.abs(c - (sa + sb) / 2), np.abs(sa - sb))
        s, cc = score(lum[:, 0]), score(lum[:, 1])
        okc = np.array(ctrl)
        res[view] = (float(s.mean()), float(cc[okc].mean()) if okc.any() else float("nan"))
    set_view(pg, "solid")
    res["vis"] = vis
    return res


def run_page(pl, d: Path, G, w, h, tag):
    out = {}
    n0 = len(ERRS)
    srv, b, pg = open_page(pl, d, w, h)
    try:
        pg.evaluate("() => __q334.cam({})")
        st = pg.evaluate("() => __q334.cam()")
        out["seams"] = pg.evaluate("() => __q334.seams()")
        body = {"az": 0.0, "el": 0.05, "dist": st["H"] * 1.15, "tgt": [0, 0, 0]}
        for zn, piece, dist in ZONES:
            cam = body if piece is None else zone_cam(G, piece, dist)
            out[zn] = measure(pg, G, cam, w, h)
        out["hide"] = hide_select(pg, G, out, tag == "after")
    finally:
        b.close(); srv.terminate()
    out["errors"] = [e for e in ERRS[n0:] if e.startswith("page error")]
    return out


def bench(pl, before, after, w, h, rounds=2):
    """frame time, default view, whole body: ONE browser at a time (memory), before and after in turns (software GL is noisy)"""
    t = [[], []]
    for _ in range(rounds):
        for j, d in enumerate((before, after)):
            srv, b, pg = open_page(pl, d, w, h)
            try:
                pg.evaluate("() => { __q334.cam({az:0, el:0.05, dist:__q334.cam().H * 1.15, tgt:[0,0,0]}); __q334.defaults(); }")
                pg.evaluate("() => __q334.bench(2)")
                t[j].append(pg.evaluate("() => __q334.bench(4)"))
            finally:
                b.close(); srv.terminate()
    return float(np.median(t[0])), float(np.median(t[1]))


def hide_select(pg, G, out, after=True):
    r = {}
    tr = out.get("trunk") or {}
    vis = tr.get("vis") or []
    if not vis:
        return {"skip": True}
    pg.evaluate("(c) => __q334.cam(c)", zone_cam(G, "Umbilical region (skin)", 450)); set_view(pg, "solid")
    k, a, d = vis[len(vis) // 2]
    A, B = G["A"][k], G["B"][k]
    pa, pb = list(a + 4 * d), list(a - 4 * d)
    r["pair"] = (G["names"][A], G["names"][B])
    if not after:      # the page before the fix: only the select / hover look, to compare with
        pg.evaluate("(id) => __q334.select(id)", A); d1 = pg.evaluate("(P) => __q334.sample(P, true)", [pa])[0]
        pg.evaluate("() => __q334.select(null)"); pg.evaluate("(id) => __q334.hover(id)", A); d2 = pg.evaluate("(P) => __q334.sample(P, true)", [pa])[0]
        pg.evaluate("() => __q334.hover(null)"); d0 = pg.evaluate("(P) => __q334.sample(P, true)", [pa])[0]
        return {"select_d": float(np.abs(np.subtract(d1, d0)).max()), "hover_d": float(np.abs(np.subtract(d2, d0)).max())}
    pg.evaluate("(id) => __q334.hide(id, true)", B)
    ids = pg.evaluate("(P) => __q334.ids(P, false)", [pa, pb])
    r["hide_b_gone"] = ids[1] != B and ids[0] == A
    r["walls_drawn"] = pg.evaluate("() => __q334.seams().wallRunsDrawn")
    pg.evaluate("(id) => __q334.hide(id, false)", B)
    ids = pg.evaluate("(P) => __q334.ids(P, false)", [pa, pb])
    r["unhide_back"] = ids == [A, B] and pg.evaluate("() => (__q334.sample([[0,0]]), __q334.seams().wallRunsDrawn)") == 0
    def rgb():
        return np.array(pg.evaluate("(P) => __q334.sample(P, true)", [pa])[0], float)
    l0 = rgb()
    pg.evaluate("(id) => __q334.select(id)", A)
    l1 = rgb()
    ids = pg.evaluate("(P) => __q334.ids(P, false)", [pa, pb])
    r["select_d"] = float(np.abs(l1 - l0).max()); r["select_ids"] = ids == [A, B]
    pg.evaluate("() => __q334.select(null)")
    pg.evaluate("(id) => __q334.hover(id)", A)
    l2 = rgb()
    r["hover_d"] = float(np.abs(l2 - l0).max())
    pg.evaluate("() => __q334.hover(null)")
    # a cut through the trunk: the page still draws and picks
    c = G["M"][k]
    pg.evaluate("(s) => __q334.cut(s)", {"normal": [0, 0, -1], "point": [float(c[0]), float(c[1]), float(c[2]) - 30]})
    r["cut_ok"] = pg.evaluate("() => __q334.sample([[700,450]])")[0] >= 0
    pg.evaluate("() => __q334.cut(null)")
    return r


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    w, h = 1400, 900
    if "--size" in sys.argv:
        w, h = (int(v) for v in sys.argv[sys.argv.index("--size") + 1].split("x"))
        args = [a for a in args if not re.match(r"\d+x\d+$", a)]
    d = Path(args[0]).resolve() if args else Path("/dev/shm/q334/viewer_zan_atlas")
    G = borders(d)
    print(f"--- {d.name} {w}x{h}: {len(G['M'])} border edges between skin regions")
    root = Path(tempfile.mkdtemp(prefix="q334v_", dir="/dev/shm"))
    try:
        before = make_copy(d, root, "before")
        html = next(d.glob("atlas_viewer*.html")).read_text(encoding="utf-8")
        after = d if "/* Q334 weld begin */" in html else make_copy(d, root, "after")
        if after is not d:
            print("     (page lacks the Q334 blocks: measured on a patched test copy)")
        with sync_playwright() as pl:
            R0 = run_page(pl, before, G, w, h, "before")
            R1 = run_page(pl, after, G, w, h, "after")
            try:
                R0["ms"], R1["ms"] = bench(pl, before, after, w, h)
            except Exception as e:      # reported, not fatal: the seam metric above stands on its own
                R0["ms"] = R1["ms"] = None
                print("     frame-time bench failed:", str(e).splitlines()[0])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    s = R1.get("seams") or {}
    print(f"     load-time weld: {s.get('ms')} ms  {s.get('cls')}")
    for zn, *_ in ZONES:
        a, b = R0.get(zn), R1.get(zn)
        if not a or not b or a.get("n", 0) < 8:
            print(f"     {zn}: too few border points in view ({(a or {}).get('n')}/{(b or {}).get('n')})")
            continue
        p0, p1 = a["pick"], b["pick"]
        check(f"[{d.name} {zn}] picking on both sides of a border: before {p0[0]}/{p0[1]}, after {p1[0]}/{p1[1]}", p1[0] >= 0.98 * p0[0])
        for v in VIEWS:
            (s0, c0), (s1, c1) = a[v], b[v]
            r0, r1 = s0 / c0, s1 / c1
            check(f"[{d.name} {zn} {v}] seam/within-region before {s0:.1f}/{c0:.1f} = {r0:.2f}  after {s1:.1f}/{c1:.1f} = {r1:.2f}  (n={b['n']})",
                  r1 <= RATIO_MAX or s1 <= 0.5 * s0 or (v == "xray" and r1 <= r0 + 0.15))
    hd = R1.get("hide") or {}
    if not hd.get("skip"):
        check(f"[{d.name}] hide {hd['pair'][1]}: the click no longer finds it, {hd['pair'][0]} still does", hd["hide_b_gone"])
        check(f"[{d.name}] hide: the neighbour's real boundary (wall) is drawn ({hd['walls_drawn']} runs)", hd["walls_drawn"] > 0)
        check(f"[{d.name}] unhide: both regions picked again, no wall drawn", hd["unhide_back"])
        h0 = R0.get("hide") or {}
        check(f"[{d.name}] select / hover {hd['pair'][0]}: picked on both sides, drawn as before the fix (colour change select {hd['select_d']:.0f} / hover {hd['hover_d']:.0f}, before {h0.get('select_d', 0):.0f} / {h0.get('hover_d', 0):.0f})",
              hd["select_ids"] and hd["select_d"] >= h0.get("select_d", 0) - 8 and hd["hover_d"] >= h0.get("hover_d", 0) - 8)
        check(f"[{d.name}] a cut through the trunk draws", hd["cut_ok"])
    f0, f1 = R0["ms"], R1["ms"]
    if f0 is None:
        check(f"[{d.name}] frame time measured", False)
    else:
      check(f"[{d.name}] frame time (default view, whole body) before {f0:.2f} ms  after {f1:.2f} ms  ({100 * (f1 / f0 - 1):+.0f}%)", f1 <= 1.10 * f0 + 0.3)
    check(f"[{d.name}] 0 page errors (before {len(R0['errors'])}, after {len(R1['errors'])})", not R0["errors"] and not R1["errors"])
    print("Q334_SEAMS_FAIL" if ERRS else "Q334_SEAMS_OK")
    for e in ERRS:
        print("   ", e)
    return 1 if ERRS else 0


if __name__ == "__main__":
    raise SystemExit(main())
