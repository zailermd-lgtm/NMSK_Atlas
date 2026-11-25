#!/usr/bin/env python3
"""Q394: pose-rig weights of the fat / unlabelled soft-tissue compartments (Q295 `fat_*`, `soft_unlabelled_*`) taken from the
tissue around them, for the compartments that come out through the skin in a pose.

    python3 scripts/anatomy/q394/rig_fat_q394.py --page-dir DIR --census AFTER.json [--rig RIG.json] --out OUT.json

Measured (Base pages, the Q394 census in the pose states): the hand's and forearm's subcutaneous fat are weighted largely to
the PELVIS and the lower thoracic vertebrae (Base·F fat_subcut_hand_l: 308 of its vertices with the pelvis as the leading
segment; fat_subcut_forearm_l 705 pelvis + 536 T12) -- at rest the hand hangs beside the hip and the rig builder took the
nearest bone. With the shoulder flexed the skin goes up with the arm and that fat stays by the hip, up to 400 mm "outside".
Rule (a display rule, like Q384's / Q392's; no anatomy source): fat fills the space between the structures around it and
moves with them. For every compartment (sys `fat`) that has a vertex outside the skin in a pose state and not at rest
(--census = under_skin_q394 per-state census of DIR), each vertex takes the inverse-square-distance average (KNN 4) of the
weights the viewer gives the nearest vertices of every NON-fat structure (skin, muscle, bone, vessel, nerve, fascia, organ...),
decoded at their rest positions, then the 3 largest influences renormalised (the viewer's quantisation); the compartment is
re-encoded with every vertex a control vertex (scripts/anatomy/q392/rig_weights_q392.encode_all), so the viewer reproduces
exactly these weights. Every other structure's bytes are kept. Round trip checked. Acceptance (two passes): the first pass
re-weights every such compartment; the pose census is re-run with it, and only compartments that got no worse in ANY state
(vertices outside and depth) are kept (--keep): at a contact (the arm hanging against the flank) the nearest donors can belong
to the other body part, and there the new weights are worse. Rest positions are untouched (the rest
pose is bit-exact: the rig moves nothing at rest).
"""
from __future__ import annotations

import argparse, base64, json, sys, zlib
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "q392"))
import under_skin_q394 as U  # noqa: E402
import rig_weights_q392 as R  # noqa: E402

KNN = 4
FAT_SYS = ("fat",)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--census", required=True)
    ap.add_argument("--rig")
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep", help="JSON list: re-weight only these (the compartments a first pass improved in every state)")
    a = ap.parse_args(argv)
    pg = U.Page(a.page_dir, a.rig)
    rig, Wd, _ = pg.rig()
    src = json.loads(pg.rig_path.read_text(encoding="utf-8"))
    blob = zlib.decompress(base64.b64decode(src["weights_zlib_b64"]))
    nseg = len(rig["segs"])
    C = json.loads(Path(a.census).read_text(encoding="utf-8"))
    rest = set(C.get("rest", {}))
    targets = set()
    for s, cs in C.items():
        if s == "rest":
            continue
        for k, e in cs.items():
            if k.startswith("__") or pg.sys.get(k) not in FAT_SYS:
                continue
            if k not in rest or set(e["verts"]) - set(C["rest"][k]["verts"]):
                targets.add(k)
    skin = {e[0]: e for e in rig["skin"]}
    targets = sorted(k for k in targets if pg.idx[k] in skin)
    if a.keep:
        keep = set(json.loads(Path(a.keep).read_text(encoding="utf-8")))
        targets = [k for k in targets if k in keep]
    # donors: every vertex of every non-fat structure, with the weights the viewer gives it
    P, Wrows = [], []
    for k in pg.ids:
        if pg.sys[k] in FAT_SYS:
            continue
        o = Wd[pg.idx[k]]; v = pg.V[k]
        M = np.zeros((len(v), nseg), np.float32)
        if o[0] == "rigid":
            M[:, o[1]] = 1.0
        else:
            sg, w = o[1], o[2]
            for j in range(sg.shape[1]):
                np.add.at(M, (np.arange(len(v)), sg[:, j].astype(int)), w[:, j])
        P.append(v); Wrows.append(M)
    P = np.vstack(P); Wall = np.vstack(Wrows)
    kd = cKDTree(P)
    changed, report = {}, {}
    for k in targets:
        n = pg.idx[k]; v = pg.V[k]
        d, nn = kd.query(v, k=KNN)
        d = np.maximum(d, 1e-3); ww = 1.0 / (d * d); ww /= ww.sum(1, keepdims=True)
        Rr = (Wall[nn] * ww[:, :, None]).sum(1).astype(np.float64)
        top, q = R.quant3(Rr)
        W2 = np.zeros_like(Rr); np.put_along_axis(W2, top, q / 255.0, 1)
        # old weights (dense) for the report
        ctrl, pi, wq, _ = R.parse_skin(skin[n], blob)
        Wold = R.decode(v, ctrl, R.dense_controls(pi, wq, skin[n][3], nseg))
        dl = np.abs(W2 - Wold).sum(1) / 2
        lead_old = np.argmax(Wold, 1); lead_new = np.argmax(W2, 1)
        changed[n] = W2
        report[k] = dict(vertices=len(v), weight_change_mean=round(float(dl.mean()), 3), weight_change_max=round(float(dl.max()), 3),
                         leading_segment_changed=int((lead_old != lead_new).sum()), donor_distance_p95_mm=round(float(np.percentile(d[:, 0], 95)), 2))
    chunks, off, new_skin = [], 0, []
    for e in rig["skin"]:
        n = e[0]
        if n in changed:
            pal, K, b = R.encode_all(changed[n])
            new_skin.append([n, e[1], K, pal, off, e[1]])
        else:
            _, _, _, ln = R.parse_skin(e, blob)
            b = blob[e[4]:e[4] + ln]
            new_skin.append([n, e[1], e[2], e[3], off, e[5]])
        chunks.append(b); off += len(b)
    rig2 = dict(rig); rig2["skin"] = new_skin
    rig2["q394"] = dict(rule="fat / unlabelled soft-tissue compartments that came out of the skin in a pose take the weights of the "
                             "nearest vertices of the non-fat structures around them (KNN 4, inverse-square)", structures=sorted(report))
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
    print(f"Q394_RIG {'OK' if not bad else 'MISMATCH'}: {len(report)} fat compartments re-weighted -> {a.out}")
    for k, v in sorted(report.items()):
        print(" ", k, v)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
