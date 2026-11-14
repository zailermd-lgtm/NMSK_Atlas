"""Q205: full-resolution (0.33 mm) crops of HIS two hands from his colour cryosection photographs (public NCI IDC mirror, series 4aaf9181...), levels atlas y -30 .. 110
(instance k = 1880.4 - y; photograph px -> atlas  x = X0 + 6.0 - 0.33 col,  z = Y0 - 4.8 + 0.33 row  with (X0, Y0) from data/derived/Q185a2_arm_skin_registration_vhm.json).
    python3 scripts/cryo/q205_hand_crops.py CRYO_1MM_DIR OUT.npz     (CRYO_1MM_DIR holds cryo_index.json from scripts/cryo/stream_vhm_cryosections.py)
"""
import concurrent.futures as cf
import io
import json
import sys
import time
import urllib.request

import numpy as np
import pydicom

BUCKET = "idc-open-data"
YS = range(-30, 111)
# per side: atlas x range, z range
BOX = {"r": ((-15.0, 175.0), (85.0, 205.0)), "l": ((-175.0, 15.0), (85.0, 205.0))}
REG = {"r": (333.68, -167.63), "l": (337.36, -163.61)}


def px_box(side):
    (xa, xb), (za, zb) = BOX[side]
    X0, Y0 = REG[side]
    c0, c1 = int((X0 + 6.0 - xb) / 0.33), int((X0 + 6.0 - xa) / 0.33)
    r0, r1 = int((za - Y0 + 4.8) / 0.33), int((zb - Y0 + 4.8) / 0.33)
    return r0, r1, c0, c1


def fetch(name):
    err = None
    for _ in range(4):
        try:
            d = urllib.request.urlopen(f"https://storage.googleapis.com/{BUCKET}/{name}", timeout=90).read()
            return pydicom.dcmread(io.BytesIO(d)).pixel_array
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(2)
    raise err


def main(cryo_dir, out):
    idx = json.load(open(f"{cryo_dir}/cryo_index.json"))
    inst = {r[1]: r[0] for r in idx}
    boxes = {s: px_box(s) for s in "rl"}
    res = {s: [] for s in "rl"}
    ks = [int(round(1880.4 - y)) for y in YS]

    def job(k):
        px = fetch(inst[k])
        return k, {s: px[b[0]:b[1], b[2]:b[3]].copy() for s, b in boxes.items()}

    t0 = time.time()
    got = {}
    with cf.ThreadPoolExecutor(6) as ex:
        for n, (k, d) in enumerate(ex.map(job, ks)):
            got[k] = d
            if n % 20 == 0:
                print(n, len(ks), round(time.time() - t0), flush=True)
    arrs = {}
    for s in "rl":
        arrs[f"crop_{s}"] = np.stack([got[k][s] for k in ks])
        arrs[f"box_px_{s}"] = np.array(boxes[s])
    arrs["ys"] = np.array(list(YS))
    arrs["reg"] = np.array([REG["r"], REG["l"]])
    np.savez_compressed(out, **arrs)
    print("DONE", {k: v.shape for k, v in arrs.items()})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
