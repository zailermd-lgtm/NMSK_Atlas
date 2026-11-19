"""Training patches for a learned nerve scorer, cut from the female's VERIFIED sciatic track (Q53).

    python3 scripts/cryo/vhf_nerve_patches.py --crops SCRATCH/vh_cryo_f/thigh \
        --track SCRATCH/sciatic_right.json:-85:-235 --track SCRATCH/sciatic_left.json:-83:-233 ... --out SCRATCH/nerve_patches.npz

Positives: 48 x 48 px (16 mm) RGB patches centred on the tracked blob centroid at every verified level, with
+-3 px jitter. Negatives: (a) every OTHER candidate blob the hand-crafted detector offered at that level (hard
negatives: muscle/fat edges, fascia), (b) random corridor points >= 10 mm from the nerve, (c) random points of
the whole crop >= 10 mm from the nerve (fat, muscle, gel). Rotations by 90 degrees and flips are applied at
training time. Nothing here is anatomy; it is the record of what a verified nerve section looks like on her.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo import vhf_nerve_track as nt  # noqa: E402
from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id  # noqa: E402

P = 24   # half patch


def patch(im, r, c):
    r, c = int(round(r)), int(round(c))
    if r - P < 0 or c - P < 0 or r + P > im.shape[0] or c + P > im.shape[1]:
        return None
    return im[r - P:r + P, c - P:c + P]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crops", required=True); ap.add_argument("--track", action="append", required=True, help="track.json:y_top:y_bottom")
    ap.add_argument("--bundle", default="build/viewer_f"); ap.add_argument("--out", required=True); ap.add_argument("--nerve", default="sciatic")
    a = ap.parse_args()
    bf, blob = read_bundle_dir(a.bundle); M = meshes_by_id(bf, blob); spec = nt.NERVES[a.nerve]; rng = np.random.default_rng(0)
    X, Y, meta = [], [], []
    for t in a.track:
        path, yt, yb = t.split(":"); yt, yb = float(yt), float(yb); side = "right" if "right" in Path(path).name else "left"
        crops = nt.Crops(a.crops, side); rows = [r for r in json.load(open(path))["rows"] if not r["gap"] and yt >= r["y"] >= yb]
        for r in rows:
            y = r["y"]; im = crops.image(y); pr, pc = crops.atlas_to_px(y, r["x"], r["z"])
            masks = nt.section_masks(M, spec["roof"] + spec["floor"] + spec.get("bone", []), side, y, crops, im.shape[:2])
            cor, _ = nt.corridor_mask(im, masks, spec); cands, _ = nt.candidates(im, cor, spec["area_mm2"])
            for dr, dc in ((0, 0), (3, 0), (-3, 0), (0, 3), (0, -3), (2, 2), (-2, -2)):
                p = patch(im, pr + dr, pc + dc)
                if p is not None:
                    X.append(p); Y.append(1); meta.append((side, y, "pos"))
            far = lambda rr, cc: np.hypot(rr - pr, cc - pc) >= 30      # 10 mm
            for c in cands:
                if far(*c["rc"]):
                    p = patch(im, *c["rc"])
                    if p is not None:
                        X.append(p); Y.append(0); meta.append((side, y, "hard"))
            cy, cx = np.nonzero(cor)
            if len(cy):
                for i in rng.choice(len(cy), size=min(4, len(cy)), replace=False):
                    if far(cy[i], cx[i]):
                        p = patch(im, cy[i], cx[i])
                        if p is not None:
                            X.append(p); Y.append(0); meta.append((side, y, "corridor"))
            for _ in range(3):
                rr, cc = rng.integers(P, im.shape[0] - P), rng.integers(P, im.shape[1] - P)
                if far(rr, cc):
                    X.append(patch(im, rr, cc)); Y.append(0); meta.append((side, y, "random"))
        print(path, len(rows), "levels ->", len(X), "patches", flush=True)
    X = np.stack(X).astype(np.uint8); Y = np.array(Y, np.uint8)
    np.savez_compressed(a.out, X=X, Y=Y, meta=np.array(meta, dtype=object))
    print("positives", int(Y.sum()), "negatives", int((Y == 0).sum()), "->", a.out)


if __name__ == "__main__":
    main()
