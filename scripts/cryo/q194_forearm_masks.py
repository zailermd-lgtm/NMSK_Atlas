"""Q194: masks of her LEFT FOREARM from her full-resolution (0.33 mm) colour cryosection photographs -> data/derived/Q194_left_forearm_photo_masks.npz.

Same photographs and frame as Q192 (scripts/cryo/q192_hand_evidence.py; data/derived/Q192_frame_calibration.json): crop rows 0:800 x cols 1500:2046 of the 1216 x 2048
photograph at cryo z -1380 .. -1640 (atlas y = z + 1850 = 470 .. 210, one slice per mm).  Per slice (all colour rules, no learned model):
  T  tissue silhouette = not blue gel, not black background (2 mm opening), the forearm component, holes filled; the left 75 px (the thigh) removed
  M  muscle-coloured tissue = value 40..150, r >= g + 8, r >= b + 8, deeper than 14 px inside T, opened (2) and closed (4)
  C  cream bone = Q192's cream rule (v > 165, saturation < 0.46, r - g < 36, b > 80, g > 0.8 r) deeper than 14 px inside T
stored as 3 x 3 block means (0.99 mm), uint8 (x 255).  The muscle rule is calibrated by eye on levels 215 .. 440 (muscle belly = dark maroon, fat = pale yellow cells, bone =
cream), see the Q194 entry of PROJECT_STATE.md.

    python3 scripts/cryo/q194_forearm_masks.py --stack left_forearm.npy --json left_forearm.json     # the cached full-res stack of the Q192 session
    python3 scripts/cryo/q194_forearm_masks.py --stream                                              # streams the slices from the NCI Imaging Data Commons mirror
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "derived" / "Q194_left_forearm_photo_masks.npz"
BOX = (0, 800, 1500, 2046)     # rows r0:r1, cols c0:c1


def slice_masks(im):
    f = im.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    v = f.max(-1)
    tissue = ~(((b > r + 15) & (b > g - 10)) | (v < 45))
    tissue = ndi.binary_opening(tissue, iterations=3)
    lab, n = ndi.label(tissue)
    if n:
        sz = ndi.sum(tissue, lab, range(1, n + 1))
        keep = [i + 1 for i in range(n) if sz[i] > 2e4]
        cand = [i for i in keep if not (lab[:, 0] == i).any()] or keep
        tissue = np.isin(lab, cand)
    tissue = ndi.binary_fill_holes(tissue)
    tissue[:, :75] = False
    inner = ndi.binary_erosion(tissue, iterations=14)
    muscle = (v < 150) & (v > 40) & (r >= g + 8) & (r >= b + 8) & inner
    muscle = ndi.binary_closing(ndi.binary_opening(muscle, iterations=2), iterations=4)
    sat = (v - f.min(-1)) / np.maximum(v, 1)
    cream = (v > 165) & (sat < 0.46) & ((r - g) < 36) & (b > 80) & (g > 0.8 * r) & inner
    return tissue, muscle, cream


def block(m, k=3):
    H, W = m.shape
    H -= H % k
    W -= W % k
    return m[:H, :W].reshape(H // k, k, W // k, k).mean((1, 3))


def build(stack, zc, out=OUT):
    T, M, C = [], [], []
    for i in range(len(zc)):
        t, m, c = slice_masks(np.asarray(stack[i]))
        m[:, :75] = False
        T.append(block(t)); M.append(block(m)); C.append(block(c))
    to8 = lambda a: (np.array(a, np.float32) * 255).round().astype(np.uint8)
    np.savez_compressed(out, T=to8(T), M=to8(M), C=to8(C), zc=np.asarray(zc), px_mm=np.float32(0.99), box_col0=np.int32(BOX[2]), box_row0=np.int32(BOX[0]),
                        note=np.array("Q194: masks of her left forearm cryosection photographs (full-res 0.33 mm px, 3x3 block mean), T=skin silhouette, M=muscle-coloured tissue, "
                                      "C=cream bone inside; frame as Q192"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stack", help="npy (S, 800, 546, 3) uint8 full-res crop, slices 1 mm apart, top (z -1380) first")
    ap.add_argument("--json", help="json with 'cryo_z' of the stack")
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    if a.stream:
        sys.path.insert(0, str(REPO))
        from scripts.cryo import q192_hand_evidence as E
        import io
        import urllib.request
        import pydicom
        work = Path("/tmp/q194_work")
        work.mkdir(exist_ok=True, parents=True)
        index = E.load_index(work)
        zs = np.array([r[2] for r in index])
        sel = [i for i in range(0, len(index), 3) if -1640 <= zs[i] <= -1380]
        stack = np.zeros((len(sel), BOX[1] - BOX[0], BOX[3] - BOX[2], 3), np.uint8)
        for j, i in enumerate(sel):
            d = urllib.request.urlopen(E.B + index[i][0]).read()
            stack[j] = pydicom.dcmread(io.BytesIO(d)).pixel_array[BOX[0]:BOX[1], BOX[2]:BOX[3]]
        zc = zs[sel]
    else:
        stack = np.load(a.stack, mmap_mode="r")
        zc = json.loads(Path(a.json).read_text())["cryo_z"]
    print("wrote", build(stack, zc, Path(a.out)))


if __name__ == "__main__":
    main()
