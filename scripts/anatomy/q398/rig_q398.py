#!/usr/bin/env python3
"""Q398: pose-rig weights of structures that come out through the skin in a pose, taken from the skin over them.

    python3 scripts/anatomy/q398/rig_q398.py --page-dir DIR --targets T.json [--rig RIG.json] --out OUT.json

Measured (Q394 census, Base pages, after the Q394 rig fix): the remaining pose-only entries are mostly fat / soft-tissue
compartments (Q295) whose weights came from the nearest bone or, after Q394, from the nearest non-fat structures (KNN 4) --
at a contact (the arm against the flank, the thigh against the abdomen in hip flexion) those donors belong to the other body
part, and the compartment leaves its own skin. Rule (a display rule, like Q384's / Q392's / Q394's; no anatomy source): what lies
just under the skin moves with the skin over it. Each vertex of a target structure takes
    W = s * W_skin + (1 - s) * W_knn,      s = 1 at depth <= S_NEAR mm under the skin's inner sheet, 0 at >= S_FAR, linear between
W_skin = the barycentric blend of the weights the viewer gives the three vertices of the closest inner-sheet triangle of the
skin (its own skin: the arm's fat is under the arm's skin, never under the flank's, which lies beyond two skin sheets);
W_knn = Q394's donor rule (inverse-square KNN 4 over the vertices of every non-fat structure other than itself). Then the 3
largest influences renormalised (the viewer's quantisation) and the structure re-encoded with every vertex a control vertex
(q392 encode_all); a structure that the rig had as rigid gets a skin entry. Every other structure's bytes are kept. Rest pose
untouched. Acceptance is done by the caller (the census per state; a structure is kept only if no state got worse). Only
fat / fascia / lymph structures (RIG_SYS): on muscles, long vessels and nerves the rule passed the census but the browser pose
verifier (q384) found kinks and origins leaving their bones.
"""
from __future__ import annotations

import argparse, base64, json, sys, zlib
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
for _p in ("q394", "q392"):
    sys.path.insert(0, str(HERE.parent / _p))
import under_skin_q394 as U  # noqa: E402
import rig_weights_q392 as R  # noqa: E402

KNN = 4
RIG_SYS = ("fat", "fascia", "lymph")   # only these: skin weights kinked muscles / long vessels and nerves (q384 verifier) and
                                      # pulled origins off their bones; the skeleton stays rigid
S_NEAR, S_FAR = 6.0, 20.0


def dense_of(o, n, nseg):
    M = np.zeros((n, nseg), np.float64)
    if o[0] == "rigid":
        M[:, o[1]] = 1.0
    else:
        sg, w = o[1], o[2]
        for j in range(sg.shape[1]):
            np.add.at(M, (np.arange(n), sg[:, j].astype(int)), w[:, j])
    return M


def bary(P, A, B, C):
    v0, v1, v2 = B - A, C - A, P - A
    d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1); d20 = (v2 * v0).sum(1); d21 = (v2 * v1).sum(1)
    den = np.where(np.abs(d00 * d11 - d01 * d01) < 1e-18, 1e-18, d00 * d11 - d01 * d01)
    v = (d11 * d20 - d01 * d21) / den; w = (d00 * d21 - d01 * d20) / den
    b = np.clip(np.stack([1 - v - w, v, w], 1), 0, None)
    return b / np.maximum(b.sum(1, keepdims=True), 1e-12)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--targets", required=True)
    ap.add_argument("--rig")
    ap.add_argument("--cache")
    ap.add_argument("--out", required=True)
    ap.add_argument("--s-near", type=float, default=S_NEAR)
    ap.add_argument("--s-far", type=float, default=S_FAR)
    a = ap.parse_args(argv)
    pg = U.Page(a.page_dir, a.rig, a.cache)
    rig, Wd, _ = pg.rig()
    src = json.loads(pg.rig_path.read_text(encoding="utf-8"))
    blob = zlib.decompress(base64.b64decode(src["weights_zlib_b64"]))
    nseg = len(rig["segs"])
    targets = sorted(set(json.loads(Path(a.targets).read_text(encoding="utf-8"))))
    skipped = [k for k in targets if pg.sys.get(k) not in RIG_SYS]
    targets = [k for k in targets if pg.sys.get(k) in RIG_SYS]
    if skipped:
        print(f"not re-weighted (system not in {RIG_SYS}): {len(skipped)}")
    tset = set(targets)
    # skin: merged inner sheet with the owner (piece, local vertex) of every merged vertex
    cls = pg.cls()
    sk = U.Skin(pg.skin_ids, pg.V, pg.F, cls)
    offs = np.r_[0, np.cumsum([len(pg.V[k]) for k in pg.skin_ids])]
    skinW = {}

    def skin_rows(gidx):
        out = np.zeros((len(gidx), nseg))
        piece = np.searchsorted(offs, gidx, "right") - 1
        for p in np.unique(piece):
            k = pg.skin_ids[p]
            if k not in skinW:
                skinW[k] = dense_of(Wd[pg.idx[k]], len(pg.V[k]), nseg)
            m = piece == p
            out[m] = skinW[k][gidx[m] - offs[p]]
        return out
    # KNN donors: every non-fat structure
    P, Wrows, owner = [], [], []
    for k in pg.ids:
        if pg.sys[k] == "fat":
            continue
        v = pg.V[k]
        P.append(v); Wrows.append(dense_of(Wd[pg.idx[k]], len(v), nseg).astype(np.float32)); owner.append(np.full(len(v), pg.idx[k]))
    P = np.vstack(P); Wall = np.vstack(Wrows); owner = np.concatenate(owner)
    kd = cKDTree(P)
    changed, report = {}, {}
    for k in targets:
        n = pg.idx[k]; v = pg.V[k]
        d, nn = kd.query(v, k=KNN + 8)
        own = owner[nn] == n                      # never its own vertices as donors
        d = np.where(own, np.inf, d)
        o = np.argsort(d, 1)[:, :KNN]
        d = np.take_along_axis(d, o, 1); nn = np.take_along_axis(nn, o, 1)
        d = np.maximum(d, 1e-3); ww = 1.0 / (d * d); ww[~np.isfinite(d)] = 0; ww /= np.maximum(ww.sum(1, keepdims=True), 1e-12)
        Wk = (Wall[nn] * ww[:, :, None]).sum(1).astype(np.float64)
        si, q, ti, _ = sk.inner.query(v)
        F = sk.inner.F[ti]
        b = bary(q, sk.inner.V[F[:, 0]], sk.inner.V[F[:, 1]], sk.inner.V[F[:, 2]])
        Ws = sum(b[:, j:j + 1] * skin_rows(F[:, j]) for j in range(3))
        s = np.clip((a.s_far - si) / max(a.s_far - a.s_near, 1e-9), 0, 1)
        Rr = s[:, None] * Ws + (1 - s[:, None]) * Wk
        top, qq = R.quant3(Rr)
        W2 = np.zeros_like(Rr); np.put_along_axis(W2, top, qq / 255.0, 1)
        Wold = dense_of(Wd[n], len(v), nseg)
        dl = np.abs(W2 - Wold).sum(1) / 2
        changed[n] = W2
        report[k] = dict(vertices=len(v), s_near_far_mm=[a.s_near, a.s_far], was_rigid=Wd[n][0] == "rigid", skin_share_mean=round(float(s.mean()), 3),
                         weight_change_mean=round(float(dl.mean()), 3), weight_change_max=round(float(dl.max()), 3),
                         leading_segment_changed=int((np.argmax(Wold, 1) != np.argmax(W2, 1)).sum()))
    # re-encode: skin entries in their order; structures that were rigid get a new skin entry and leave their rigid group
    chunks, off, new_skin = [], 0, []
    have = set()
    for e in rig["skin"]:
        n = e[0]; have.add(n)
        if n in changed:
            pal, K, b = R.encode_all(changed[n])
            new_skin.append([n, e[1], K, pal, off, e[1]])
        else:
            _, _, _, ln = R.parse_skin(e, blob)
            b = blob[e[4]:e[4] + ln]
            new_skin.append([n, e[1], e[2], e[3], off, e[5]])
        chunks.append(b); off += len(b)
    rigid = [[g[0], [i for i in g[1] if not (i in changed and i not in have)]] for g in rig["rigid"]]
    rigid = [g for g in rigid if g[1]]
    for n in sorted(changed):
        if n in have:
            continue
        pal, K, b = R.encode_all(changed[n])
        nv = len(pg.V[pg.ids[n]])
        new_skin.append([n, nv, K, pal, off, nv]); chunks.append(b); off += len(b)
    rig2 = dict(rig); rig2["skin"] = new_skin; rig2["rigid"] = rigid
    rig2["q398"] = dict(rule="structures that came out of the skin in a pose take the weights of the skin over them (barycentric, "
                             f"closest inner-sheet triangle) blended by depth ({a.s_near:g}..{a.s_far:g} mm) with Q394's KNN-4 donors",
                        structures=sorted(report))
    out = dict(src); out["rig"] = rig2
    blob2 = b"".join(chunks)
    out["weights_zlib_b64"] = base64.b64encode(zlib.compress(blob2, 9)).decode("ascii")
    Path(a.out).write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    bad = 0
    for e in new_skin:
        if e[0] in changed:
            ctrl, pi, wq, _ = R.parse_skin(e, blob2)
            Wd2 = R.decode(pg.V[pg.ids[e[0]]], ctrl, R.dense_controls(pi, wq, e[3], nseg))
            bad += int(np.abs(Wd2 - changed[e[0]]).max() > 1.5 / 255)
    Path(a.out).with_suffix(".report.json").write_text(json.dumps(dict(structures=report, roundtrip_mismatch=bad), indent=1) + "\n")
    print(f"Q398_RIG {'OK' if not bad else 'MISMATCH'}: {len(report)} structures re-weighted -> {a.out}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
