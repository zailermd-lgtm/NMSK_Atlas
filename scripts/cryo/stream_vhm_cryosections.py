"""Stream the VH male cryosection series from IDC into one 3x-downsampled RGB volume (~1 mm),
never writing the 7.5 MB DICOMs to disk. Output: OUT_DIR/cryo_1mm.npy (Z,H,W,3) u8 memmap +
OUT_DIR/cryo_index.json.

    python3 scripts/cryo/stream_vhm_cryosections.py SCRATCH/vh_cryo_m

Self-contained: lists its own objects from the public bucket (the JSON API, same approach as
scripts/cryo/vhm_stream_crops.py), so it needs nothing but network access -- earlier versions of
this script required a pre-built objects.json that was never committed, so a container reset that
wiped the scratchpad also silently made the male's whole-body cryosection frame unrecoverable
(the root blocker behind PROJECT_STATE's Q57/Q68/Q71/Q72/Q78). Verified 2026-09-18 (Q79): re-runs
cleanly from a clean container, ~3 minutes for all 1878 slices over 6 threads.
"""
import concurrent.futures as cf
import io
import json
import sys
import time
import urllib.request

import numpy as np
import pydicom

SERIES = "4aaf9181-fb6a-4a4c-bf49-d1eb9ed4a385"  # docs/GEOMETRY_SOURCES.md: his colour cryosections, 1878 slices, 0.33 mm
BUCKET = "idc-open-data"
F = 3
H, W = 1216 // F, 2048 // F  # 405 x 682


def list_objects():
    names, tok = [], None
    while True:
        q = (f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o?prefix={SERIES}/&maxResults=1000&fields=items(name),nextPageToken"
             + (f"&pageToken={tok}" if tok else ""))
        d = json.loads(urllib.request.urlopen(q, timeout=60).read())
        names += [it["name"] for it in d.get("items", [])]
        tok = d.get("nextPageToken")
        if not tok:
            return names


def head(name):
    err = None
    for _ in range(4):
        try:
            req = urllib.request.Request(f"https://storage.googleapis.com/{BUCKET}/{name}", headers={"Range": "bytes=0-8191"})
            d = urllib.request.urlopen(req, timeout=60).read()
            ds = pydicom.dcmread(io.BytesIO(d), stop_before_pixels=True, force=True)
            return name, int(ds.InstanceNumber), float(ds.ImagePositionPatient[2])
        except Exception as e:  # noqa: BLE001
            err = e; time.sleep(1)
    raise err


def fetch(idx, k):
    name = idx[k][0]
    err = None
    for _ in range(4):
        try:
            d = urllib.request.urlopen(f"https://storage.googleapis.com/{BUCKET}/{name}", timeout=60).read()
            ds = pydicom.dcmread(io.BytesIO(d))
            px = ds.pixel_array
            small = px[:H * F, :W * F].reshape(H, F, W, F, 3).mean(axis=(1, 3)).astype(np.uint8)
            return k, small
        except Exception as e:  # noqa: BLE001
            err = e; time.sleep(2)
    raise err


def main():
    out_dir = sys.argv[1]
    import os
    os.makedirs(out_dir, exist_ok=True)

    names = list_objects()
    print("listed", len(names), flush=True)

    with cf.ThreadPoolExecutor(16) as ex:
        idx = list(ex.map(head, names))
    idx.sort(key=lambda t: -t[2])  # superior (largest z) first
    json.dump(idx, open(f"{out_dir}/cryo_index.json", "w"))
    print("indexed", len(idx), "z", idx[0][2], idx[-1][2], flush=True)

    Z = len(idx)
    vol = np.lib.format.open_memmap(f"{out_dir}/cryo_1mm.npy", mode="w+", dtype=np.uint8, shape=(Z, H, W, 3))
    done = 0; t0 = time.time()
    with cf.ThreadPoolExecutor(6) as ex:
        for k, small in ex.map(lambda k: fetch(idx, k), range(Z)):
            vol[k] = small; done += 1
            if done % 200 == 0:
                vol.flush(); print(f"{done}/{Z} {time.time()-t0:.0f}s", flush=True)
    vol.flush()
    print("CRYO_DONE", flush=True)


if __name__ == "__main__":
    main()
