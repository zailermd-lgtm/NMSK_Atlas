#!/usr/bin/env python3
"""Q389: an offline picture of the display covering on the page's skin (no browser): front, back, side and from below.
Called through make_cover_q389.py --preview OUT.png DIR.  A development aid; the page itself is checked by verify_cover_q389.py."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_cover_q389 as mk  # noqa: E402


def rest_mesh(g):
    """the garment's rest geometry: positions, triangles, a colour class per triangle (0 body, 1 rim, 2 pouch)"""
    P = g["pos0"] + g["nrm"] * g["h"][:, None]
    tris = [g["tri"]["body"], g["tri"]["rim"]]
    cls = [np.zeros(len(tris[0]), int), np.ones(len(tris[1]), int)]
    if "fix_pos" in g and len(g["fix_pos"]):
        tris.append(g["fix_tri"] + len(P))
        cls.append(np.full(len(g["fix_tri"]), 2))
        P = np.vstack([P, g["fix_pos"]])
    return P, np.concatenate(tris), np.concatenate(cls)


def raster(img, zb, P2, depth, tri, col, light):
    H, W = zb.shape
    for t in range(len(tri)):
        a, b, c = P2[tri[t]]
        x0, x1 = int(max(0, np.floor(min(a[0], b[0], c[0])))), int(min(W - 1, np.ceil(max(a[0], b[0], c[0]))))
        y0, y1 = int(max(0, np.floor(min(a[1], b[1], c[1])))), int(min(H - 1, np.ceil(max(a[1], b[1], c[1]))))
        if x1 < x0 or y1 < y0:
            continue
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-9:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        w1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        w2 = 1 - w0 - w1
        m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not m.any():
            continue
        d = depth[tri[t]]
        z = w0 * d[0] + w1 * d[1] + w2 * d[2]
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        m &= z > sub
        sub[m] = z[m]
        img[y0:y1 + 1, x0:x1 + 1][m] = np.clip(np.asarray(col[t]) * light[t], 0, 255)


VIEWS = {"front": ([1, 0, 0], [0, 1, 0], [0, 0, 1]), "back": ([-1, 0, 0], [0, 1, 0], [0, 0, -1]), "right": ([0, 0, -1], [0, 1, 0], [1, 0, 0]),
         "left": ([0, 0, 1], [0, 1, 0], [-1, 0, 0]), "below": ([1, 0, 0], [0, 0, 1], [0, -1, 0]), "front-below": ([1, 0, 0], [0, 0.8, 0.6], [0, -0.6, 0.8]),
         "back-below": ([-1, 0, 0], [0, 0.8, -0.6], [0, -0.6, -0.8])}


def coverage(html, scale=1.0):
    """How much of the skin a garment is there to cover can still be SEEN with it on, in pixels per view (orthographic, rest
    pose): for the briefs the genital skin pieces, for the top the mammary pieces.  {garment: {view: [seen, seen without it]}}"""
    ctx, gs, doc = mk.build(Path(html))
    man, binb, M = ctx["man"], ctx["bin"], ctx["M"]
    out = {}
    for key, (_, g) in gs.items():
        rx = mk.GENITAL if key == "briefs" else mk.MAMMARY
        lo, hi = g["band"][0] - 120, g["band"][1] + 120
        SP, ST, SC, base = [], [], [], 0
        for i in ctx["skin"]:
            r = M[i]
            if r["min"][1] + r["span"][1] < lo or r["min"][1] > hi:
                continue
            p, f = mk.mesh(man, binb, i)
            SP.append(p); ST.append(f + base); base += len(p)
            SC.append(np.full(len(f), 1 if rx.search(r["name"]) else 0))
        SP, ST, SC = np.vstack(SP), np.vstack(ST), np.concatenate(SC)
        GP, GT, _ = rest_mesh(g)
        res = {}
        for name, (ax, ay, az) in VIEWS.items():
            ax, ay, az = np.array(ax, float), np.array(ay, float), np.array(az, float)
            ay = ay / np.linalg.norm(ay); az = az / np.linalg.norm(az)
            seen = []
            for with_cover in (True, False):
                P = np.vstack([SP, GP]) if with_cover else SP
                T = np.vstack([ST, GT + len(SP)]) if with_cover else ST
                C = np.concatenate([SC, np.full(len(GT), 2)]) if with_cover else SC
                X, Y, Z = P @ ax, P @ ay, P @ az
                W_, H_ = int((X.max() - X.min()) * scale) + 4, int((Y.max() - Y.min()) * scale) + 4
                P2 = np.column_stack([(X - X.min()) * scale + 2, (Y.max() - Y) * scale + 2])
                img = np.zeros((H_, W_, 3), np.uint8)
                zb = np.full((H_, W_), -1e9)
                col = np.array([[10, 10, 10], [255, 0, 0], [0, 0, 255]])[C]
                raster(img, zb, P2, Z, T, col, np.ones(len(T)))
                seen.append(int(((img[:, :, 0] == 255) & (img[:, :, 2] == 0)).sum()))
            res[name] = seen
        out[key] = res
    return out


def main(out_png, page_dir):
    from PIL import Image
    d = Path(page_dir)
    html = [f for f in sorted(d.glob("atlas_viewer*.html"))][0]
    ctx, gs, doc = mk.build(html)
    print(doc["stats"])
    man, binb, M = ctx["man"], ctx["bin"], ctx["M"]
    ys = [b for _, g in gs.values() for b in g["band"]]
    ylo, yhi = min(ys) - 160, max(ys) + 160
    # the skin around: every skin piece in the range, all its faces
    SP, ST, base = [], [], 0
    for i in ctx["skin"]:
        r = M[i]
        if r["min"][1] + r["span"][1] < ylo or r["min"][1] > yhi or abs(r["min"][0] + r["span"][0] / 2) > 190:
            continue
        p, f = mk.mesh(man, binb, i)
        SP.append(p); ST.append(f + base); base += len(p)
    SP, ST = np.vstack(SP), np.vstack(ST)
    GP, GT, GC = [], [], []
    gb = len(SP)
    for key, (_, g) in gs.items():
        P, T, C = rest_mesh(g)
        GP.append(P); GT.append(T + gb); GC.append(C + (3 if key == "top" else 0)); gb += len(P)
    P = np.vstack([SP] + GP)
    T = np.vstack([ST] + GT)
    pal = np.array([[70, 120, 190], [40, 70, 130], [60, 105, 170], [70, 120, 190], [40, 70, 130]])
    col = np.vstack([np.tile([[222, 184, 150]], (len(ST), 1)), pal[np.concatenate(GC)]])
    views = {"front": ([1, 0, 0], [0, 1, 0], [0, 0, 1]), "back": ([-1, 0, 0], [0, 1, 0], [0, 0, -1]), "right": ([0, 0, -1], [0, 1, 0], [1, 0, 0]),
             "below": ([1, 0, 0], [0, 0, 1], [0, -1, 0]), "front-below": ([1, 0, 0], [0, 0.8, 0.6], [0, -0.6, 0.8])}
    sc = 0.9
    tiles = []
    for name, (ax, ay, az) in views.items():
        ax, ay, az = np.array(ax, float), np.array(ay, float), np.array(az, float)
        X, Y, Z = P @ ax, P @ ay, P @ az
        W_, H_ = int((X.max() - X.min()) * sc) + 20, int((Y.max() - Y.min()) * sc) + 20
        P2 = np.column_stack([(X - X.min()) * sc + 10, (Y.max() - Y) * sc + 10])
        n = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
        n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
        light = 0.45 + 0.55 * np.abs(n @ az)
        img = np.full((H_, W_, 3), 255, np.uint8)
        zb = np.full((H_, W_), -1e9)
        raster(img, zb, P2, Z, T, col, light)
        tiles.append(img)
    Hm = max(t.shape[0] for t in tiles)
    canvas = np.full((Hm, sum(t.shape[1] for t in tiles) + 10 * len(tiles), 3), 255, np.uint8)
    x = 0
    for t in tiles:
        canvas[:t.shape[0], x:x + t.shape[1]] = t
        x += t.shape[1] + 10
    Image.fromarray(canvas).save(out_png)
    print("wrote", out_png, canvas.shape)
    return 0
