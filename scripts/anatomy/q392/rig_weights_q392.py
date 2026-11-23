#!/usr/bin/env python3
"""Q392: pose-rig weights of MOVED nerve vertices (Q388 sciatic re-route + Q392 nerve patch) set from the nearest UNMOVED
nerve vertices, instead of being left at the weights of the place they were moved away from.

    python3 scripts/anatomy/q392/rig_weights_q392.py --rig data/anatomy/pose_rig_base_m.json \
        --before build/q309/viewer_zan_atlas --after DIR/viewer_zan_atlas [--orig DIR_PRE_Q388/viewer_zan_atlas] --out OUT.json

--before: the page the rig's weights were made on (geometry the stored control weights belong to); --after: the patched page;
--orig (optional): a page from before an earlier move whose weights were never refreshed (Q388: the rig was built on the
pre-Q388 sciatic). A nerve vertex is "moved" when it differs by > 0.05 mm between --orig/--before and --after.

Rule (a display rule, like Q384's; no anatomy source): the viewer reconstructs a vertex's weights from control vertices
(pose.js decodeSkin = make_pose_rig.decode_weights). For every nerve structure with moved vertices: unmoved vertices keep the
weights the viewer gave them before (decoded at their old rest position); a moved vertex takes the inverse-square-distance
average of the decoded weights of the KNN=4 nearest UNMOVED vertices of ANY nerve at its new position, then the 3 largest
influences renormalised (the viewer's own quantisation). Such a structure is re-encoded with every vertex a control vertex,
so the viewer reproduces exactly these weights. Every other structure's bytes are kept (offsets shifted). Muscles moved by
the Q392 contact correction (<= 6 mm) keep their stored weights: the viewer re-derives non-control vertices at the new rest
position. Checked: the patched page's vertex counts equal the rig's `nv`.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import zlib
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q388"))
import lib388 as L  # noqa: E402

KNN = 4


def parse_skin(entry, blob):
    i, nv, K, pal, off, nc = entry
    p = off
    mb = (nv + 7) >> 3
    ctrl = np.unpackbits(np.frombuffer(blob[p:p + mb], np.uint8))[:nv].astype(bool); p += mb
    pi = np.stack([np.frombuffer(blob[p + k * nc:p + (k + 1) * nc], np.uint8) for k in range(K)], 1); p += K * nc
    wq = np.stack([np.frombuffer(blob[p + k * nc:p + (k + 1) * nc], np.uint8) for k in range(K - 1)], 1) if K > 1 else np.zeros((nc, 0), np.uint8)
    p += (K - 1) * nc
    return ctrl, pi, wq, p - off


def dense_controls(pi, wq, pal, nseg):
    nc, K = pi.shape
    W = np.zeros((nc, nseg), np.float64)
    sw = wq.astype(np.float64).sum(1) if wq.shape[1] else np.zeros(nc)
    palv = np.asarray(pal)
    for k in range(1, K):
        np.add.at(W, (np.arange(nc), palv[pi[:, k]]), wq[:, k - 1] / 255.0)
    np.add.at(W, (np.arange(nc), palv[pi[:, 0]]), (255.0 - sw) / 255.0)
    return W


def quant3(R):
    """the viewer's reconstruction step: 3 largest influences, renormalised, uint8-quantised (weight 0 = 255 - rest)."""
    top = np.argsort(-R, axis=1, kind="stable")[:, :3]
    tw = np.take_along_axis(R, top, 1)
    tw = tw / np.maximum(tw.sum(1, keepdims=True), 1e-9)
    q = np.round(tw * 255).astype(np.int32)
    q[:, 0] += 255 - q.sum(1)
    return top, np.clip(q, 0, 255)


def decode(V, ctrl, Wc):
    """make_pose_rig.decode_weights, dense: -> (nv, nseg) weights (3 largest, renormalised)."""
    cv = np.where(ctrl)[0]
    k = min(KNN, len(cv))
    d, nn = cKDTree(V[cv]).query(V, k=k)
    d = np.maximum(d.reshape(len(V), k), 1e-3); nn = nn.reshape(len(V), k)
    ww = 1.0 / (d * d); ww /= ww.sum(1, keepdims=True)
    R = (Wc[nn] * ww[:, :, None]).sum(1)
    R[cv] = Wc
    top, q = quant3(R)
    out = np.zeros_like(R)
    np.put_along_axis(out, top, q / 255.0, 1)
    return out


def encode_all(W):
    """every vertex a control: -> (ctrl, pal, K, bytes)."""
    nv = len(W)
    top, q = quant3(W)
    used = np.unique(top[q > 0])
    pal = sorted(int(s) for s in used)
    pm = {s: n for n, s in enumerate(pal)}
    K = max(1, int((q > 0).any(0).nonzero()[0].max() + 1))
    pi = np.zeros((nv, K), np.uint8)
    for k in range(K):
        pi[:, k] = [pm.get(int(s), 0) for s in top[:, k]]
        if k:
            pi[q[:, k] == 0, k] = pi[q[:, k] == 0, 0]
    ctrl = np.ones(nv, bool)
    b = np.packbits(ctrl).tobytes() + b"".join([pi[:, k].tobytes() for k in range(K)] + [q[:, k].astype(np.uint8).tobytes() for k in range(1, K)])
    return pal, K, b


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rig", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--orig")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    src = json.loads(Path(a.rig).read_text(encoding="utf-8"))
    rig = src["rig"]
    blob = zlib.decompress(base64.b64decode(src["weights_zlib_b64"]))
    B, A = L.LazyPage(a.before), L.LazyPage(a.after)
    O = L.LazyPage(a.orig) if a.orig else None
    ids = list(A.meta.keys())
    assert [len(B[k]["V"]) for k in ids[:1]] and rig["count"] == len(ids), "structure count differs from the rig"
    nseg = len(rig["segs"])
    skin = {e[0]: e for e in rig["skin"]}
    nerves = [n for n, k in enumerate(ids) if A.meta[k]["sys"] == "nerve" and n in skin]
    # rest positions the stored weights belong to (pre-move) and after
    old, new, moved = {}, {}, {}
    for n in nerves:
        k = ids[n]
        Va = A[k]["V"].astype(float); Vb = B[k]["V"].astype(float)
        Vo = O[k]["V"].astype(float) if O is not None and k in O else Vb
        assert len(Va) == rig["nv"][n], f"{k}: vertex count differs from the rig"
        m = (np.linalg.norm(Va - Vb, axis=1) > 0.05) | (np.linalg.norm(Va - Vo, axis=1) > 0.05)
        old[n] = Vo if (np.linalg.norm(Vb - Vo, axis=1) > 0.05).any() else Vb
        new[n] = Va; moved[n] = m
    W, ctrlinfo = {}, {}
    for n in nerves:
        ctrl, pi, wq, _ = parse_skin(skin[n], blob)
        Wc = dense_controls(pi, wq, skin[n][3], nseg)
        W[n] = decode(old[n], ctrl, Wc)
    ref_P = np.vstack([new[n][~moved[n]] for n in nerves])
    ref_W = np.vstack([W[n][~moved[n]] for n in nerves])
    kd = cKDTree(ref_P)
    changed = {}
    report = {}
    for n in nerves:
        if not moved[n].any():
            continue
        Wn = W[n].copy()
        P = new[n][moved[n]]
        d, nn = kd.query(P, k=KNN)
        d = np.maximum(d, 1e-3); ww = 1.0 / (d * d); ww /= ww.sum(1, keepdims=True)
        R = (ref_W[nn] * ww[:, :, None]).sum(1)
        top, q = quant3(R)
        R2 = np.zeros_like(R); np.put_along_axis(R2, top, q / 255.0, 1)
        before = Wn[moved[n]]
        Wn[moved[n]] = R2
        changed[n] = Wn
        dl = np.abs(R2 - before).sum(1) / 2
        report[ids[n]] = dict(moved_vertices=int(moved[n].sum()), weight_change_mean=round(float(dl.mean()), 3),
                              weight_change_max=round(float(dl.max()), 3), nearest_unmoved_mm=round(float(d[:, 0].max()), 1))
    # rebuild the blob
    chunks, off, new_skin = [], 0, []
    for e in rig["skin"]:
        n = e[0]
        if n in changed:
            pal, K, b = encode_all(changed[n])
            new_skin.append([n, e[1], K, pal, off, e[1]])
        else:
            _, _, _, ln = parse_skin(e, blob)
            b = blob[e[4]:e[4] + ln]
            new_skin.append([n, e[1], e[2], e[3], off, e[5]])
        chunks.append(b); off += len(b)
    rig2 = dict(rig); rig2["skin"] = new_skin
    rig2["q392"] = dict(rule="moved nerve vertices take the weights of the nearest unmoved nerve vertices (KNN 4, inverse-square)",
                        structures=sorted(report))
    out = dict(src); out["rig"] = rig2
    out["weights_zlib_b64"] = base64.b64encode(zlib.compress(b"".join(chunks), 9)).decode("ascii")
    Path(a.out).write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    # round trip: decode the re-encoded structures at their new rest positions == the intended weights
    blob2 = b"".join(chunks); bad = 0
    for e in new_skin:
        if e[0] in changed:
            ctrl, pi, wq, _ = parse_skin(e, blob2)
            Wd = decode(new[e[0]], ctrl, dense_controls(pi, wq, e[3], nseg))
            bad += int(np.abs(Wd - changed[e[0]]).max() > 1.5 / 255)
    Path(a.out).with_suffix(".report.json").write_text(json.dumps(dict(structures=report, roundtrip_mismatch=bad), indent=1))
    print(f"Q392_RIG {'OK' if not bad else 'MISMATCH'}: {len(report)} nerve structures re-weighted -> {a.out}")
    for k, v in sorted(report.items()):
        print(" ", k, v)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
