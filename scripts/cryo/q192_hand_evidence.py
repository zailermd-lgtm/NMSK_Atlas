"""Q192: bone evidence for her LEFT hand (and the right hand, as validation) from her FULL-RESOLUTION (0.33 mm) colour cryosection photographs.

Her CT has no left hand (the 480 mm field of view clips the arms); the photographs of the frozen block do show the carpals / metacarpals / phalanges as cream
blocks.  This script is the data side of scripts/zanatomy/q192_left_hand.py: it streams the hand levels from the public NCI Imaging Data Commons mirror
(Visible Human Project female cryosections, series 56f8119f..., public domain), registers them to the atlas frame, finds her hand pieces and writes the
bone evidence (cream voxels) as data/derived/Q192_left_hand_evidence.npz.  Real data only: no template is used here.

Frame (measured, data/derived/Q192_frame_calibration.json): a photograph pixel (row, col) of slice z_c (cryo series z, mm) is atlas
    x = AX[side] - 0.33 (col)     y = z_c + 1850     zap = -166.4 + 0.33 (row)
AX = 352.2 (left arm) / 353.5 (right arm): fitted per level by maximising the overlap between the photograph silhouette (colour class tissue) and the
cross-section of her skin mesh (build/vh/ct_vhf_skin, whose arm part IS this silhouette, scripts/cryo/vhf_skin_union.py); the in-plane shift is constant to
+-1 mm over the whole hand, y offset 1850 +-3 mm (overlap peak, both hands), so the hand bones land in the same frame as her skin and her left forearm.

Evidence rule (documented numbers, see the Q192 entry of PROJECT_STATE.md):  cream pixel = value>165, saturation<0.46, r-g<36, b>80, g>0.8 r;  inside the
hand piece (tissue component not touching the crop border, the yellow ID note removed) deeper than 4.5 mm; opened / closed / filled; blobs >= 12 mm2.
On the RIGHT hand this evidence covers her CT hand bones to 88 % (carpals) / 74-86 % (phalanges) / 62-90 % (metacarpals) (recall within 1.5 mm after a rigid
13 mm photograph-vs-CT shift of the arm); its precision is ~46 % (subcutaneous fat, fascia) which the fit tolerates by trimming.

    python3 scripts/cryo/q192_hand_evidence.py [--work DIR] [--no-stream]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
PX, AZ, YOFF = 0.33, -166.4, 1850.0
AX = {"l": 352.2, "r": 353.5}
UUID = "56f8119f-5940-48c1-96ee-8d445dc0b5fd"
B = "https://storage.googleapis.com/idc-open-data/"
# (name, cryo z top, bottom, rows r0:r1, cols c0:c1 of the 1216 x 2048 photograph)
BOXES = {"left_hand": (-1640, -1840, 300, 1215, 850, 2046, "l"), "left_forearm": (-1380, -1640, 0, 800, 1500, 2046, "l"),
         "right_hand": (-1640, -1900, 300, 1215, 100, 1100, "r")}
OUT = REPO / "data" / "derived" / "Q192_left_hand_evidence.npz"


def cream(im):
    f = im.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    v = f.max(-1)
    sat = (v - f.min(-1)) / np.maximum(v, 1)
    return (v > 165) & (sat < 0.46) & ((r - g) < 36) & (b > 80) & (g > 0.80 * r)


def hand_roi(im, min_area_mm2=150, sticker_row_frac=0.80):
    """ds2 images (S,H,W,3) -> bool (S,H,W): tissue components (2 mm opening) not touching the crop border, the yellow ID note removed, holes filled"""
    S, H, W, _ = im.shape
    out = np.zeros((S, H, W), bool)
    i16 = im.astype(np.int16)
    T = (i16[..., 0] > i16[..., 2] + 20) & (i16.max(-1) > 45)
    for j in range(S):
        t = ndi.binary_opening(T[j], iterations=1)
        lab, n = ndi.label(t)
        if n == 0:
            continue
        sz = ndi.sum(t, lab, range(1, n + 1))
        com = ndi.center_of_mass(t, lab, range(1, n + 1))
        sl = ndi.find_objects(lab)
        for i in range(1, n + 1):
            if sz[i - 1] * 0.4356 < min_area_mm2:
                continue
            s = sl[i - 1]
            if s[0].start <= 2 or s[1].start <= 2 or s[0].stop >= H - 2 or s[1].stop >= W - 2:
                continue
            if com[i - 1][0] > sticker_row_frac * H and (s[1].stop - s[1].start) < 0.22 * W:
                continue
            out[j] |= lab == i
        out[j] = ndi.binary_fill_holes(out[j])
    return out


def proposals(im, roi, depth_mm=4.5, open_it=2, min_mm2=12):
    out = np.zeros(roi.shape, bool)
    for j in range(len(im)):
        if not roi[j].any():
            continue
        dep = ndi.distance_transform_edt(roi[j]) * 0.66
        m = cream(im[j]) & (dep > depth_mm)
        m = ndi.binary_opening(m, iterations=open_it)
        m = ndi.binary_fill_holes(ndi.binary_closing(m, iterations=2))
        lab, n = ndi.label(m)
        if n:
            sz = ndi.sum(m, lab, range(1, n + 1))
            m = np.isin(lab, [i + 1 for i, s in enumerate(sz) if s * 0.4356 >= min_mm2])
        out[j] = m
    return out


def discs(im, roi, j, depth_mm=9.0, contrast_min=95):
    """radius / ulna cross-sections of one forearm level: deep cream discs whose surrounding is dark muscle (subcutaneous fat has no dark ring)"""
    dep = ndi.distance_transform_edt(roi[j]) * 0.66
    m = cream(im[j]) & (dep > depth_mm)
    m = ndi.binary_opening(m, iterations=3)
    m = ndi.binary_fill_holes(ndi.binary_closing(m, iterations=2))
    lab, n = ndi.label(m)
    v = im[j].max(-1).astype(float)
    keep = np.zeros(m.shape, bool)
    for i in range(1, n + 1):
        mm = lab == i
        a = mm.sum() * 0.4356
        if a < 60 or a > 900:
            continue
        ring = ndi.binary_dilation(mm, iterations=9) & ~ndi.binary_dilation(mm, iterations=3) & roi[j]
        if ring.sum() < 10:
            continue
        rv = np.sort(v[ring])
        if v[mm].mean() - rv[:int(0.5 * len(rv))].mean() > contrast_min:
            keep |= mm
    return keep


def to_atlas(mask, zc, box, side, d=2):
    ss, rr, cc = np.where(mask)
    return np.stack([AX[side] - PX * (box[2] + (cc + 0.5) * d), zc[ss] + YOFF, AZ + PX * (box[0] + (rr + 0.5) * d)], 1).astype(np.float32)


def stream(name, work: Path, index):
    z0, z1, r0, r1, c0, c1, _ = BOXES[name]
    zs = np.array([r[2] for r in index])
    sel = [i for i in range(0, len(index), 3) if z1 <= zs[i] <= z0]
    path = work / (name + "_ds2.npy")
    if path.exists():
        return np.load(path), zs[sel]
    out = np.zeros((len(sel), (r1 - r0) // 2, (c1 - c0) // 2, 3), np.uint8)

    def get(j):
        for _ in range(5):
            try:
                import pydicom
                d = urllib.request.urlopen(B + index[sel[j]][0]).read()
                px = pydicom.dcmread(io.BytesIO(d)).pixel_array[r0:r1, c0:c1]
                H, W = px.shape[0] // 2 * 2, px.shape[1] // 2 * 2
                return j, px[:H, :W].reshape(H // 2, 2, W // 2, 2, 3).mean((1, 3)).astype(np.uint8)
            except Exception:
                time.sleep(2)
        raise RuntimeError("download failed")

    with cf.ThreadPoolExecutor(8) as ex:
        for j, a in ex.map(get, range(len(sel))):
            out[j] = a
    np.save(path, out)
    return out, zs[sel]


def load_index(work: Path):
    p = work / "cryo_index.json"
    if p.exists():
        return json.loads(p.read_text())
    import pydicom
    names, tok = [], None
    while True:
        q = f"https://storage.googleapis.com/storage/v1/b/idc-open-data/o?prefix={UUID}/&maxResults=1000&fields=items(name),nextPageToken" + (f"&pageToken={tok}" if tok else "")
        j = json.load(urllib.request.urlopen(q))
        names += [i["name"] for i in j.get("items", [])]
        tok = j.get("nextPageToken")
        if not tok:
            break

    def head(n):
        for _ in range(4):
            try:
                req = urllib.request.Request(B + n, headers={"Range": "bytes=0-8191"})
                ds = pydicom.dcmread(io.BytesIO(urllib.request.urlopen(req).read()), stop_before_pixels=True, force=True)
                return n, int(ds.InstanceNumber), float(ds.ImagePositionPatient[2]), int(ds.Rows), int(ds.Columns)
            except Exception:
                time.sleep(1)
        raise RuntimeError(n)

    with cf.ThreadPoolExecutor(16) as ex:
        allidx = list(ex.map(head, names))
    allidx.sort(key=lambda t: -t[2])
    p.write_text(json.dumps(allidx))
    return allidx


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default="/tmp/q192_work")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    index = load_index(work)
    res = {}
    for name in BOXES:
        im, zc = stream(name, work, index)
        roi = hand_roi(im)
        box = BOXES[name]
        bx = (box[2], box[3], box[4], box[5])
        side = box[6]
        if name == "left_forearm":
            m = np.zeros(roi.shape, bool)
            for j in range(len(im)):
                if roi[j].any():
                    m[j] = discs(im, roi, j)
        else:
            m = proposals(im, roi)
        res[name] = to_atlas(m, zc, bx, side)
        if name == "left_hand":
            res["_roi"], res["_zc"], res["_box"] = roi, zc.astype(np.float32), np.array([bx[0], bx[2]], np.int32)
        if name == "left_hand":                              # her radius / ulna discs at the wrist levels (y 150-210) from the same slices
            m2 = np.zeros(roi.shape, bool)
            for j in range(len(im)):
                if zc[j] + YOFF >= 150 and roi[j].any():
                    m2[j] = discs(im, roi, j)
            res["left_wrist_discs"] = to_atlas(m2, zc, bx, side)
        print(name, res[name].shape)
    q = lambda p: np.round(p * 4).astype(np.int16)
    np.savez_compressed(a.out, hand=q(res["left_hand"]), forearm=q(np.vstack([res["left_forearm"][res["left_forearm"][:, 1] >= 210], res["left_wrist_discs"][res["left_wrist_discs"][:, 1] < 210]])),
                        right_hand=q(res["right_hand"]), unit_mm=np.float32(0.25),
                        hand_roi=np.packbits(res["_roi"], axis=None), hand_roi_shape=np.array(res["_roi"].shape), hand_roi_zc=res["_zc"], hand_roi_box=res["_box"],
                        note=np.array("Q192 bone evidence (cream voxel centres, atlas mm x 4); scripts/cryo/q192_hand_evidence.py"))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
