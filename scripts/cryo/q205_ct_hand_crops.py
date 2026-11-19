"""Q205: HU crops of HIS two hands from the frozen-CT series 5d409385 (head to proximal femur, arms included; public NCI IDC mirror) -> data not committed (scratch .npz).
The label volume vhm_arm_bones_cryo_completed.nii.gz kept only HU >= 600 seed components that connect to the hand mass; the thumb / low-density bones of the cadaver hand are missing there.
    python3 scripts/cryo/q205_ct_hand_crops.py OUT.npz
Output: per slice (DICOM position z mm, instance, HU crop of the two hand boxes in DICOM pixel grid) + the DICOM geometry (ImagePositionPatient x, y, pixel spacing)."""
import concurrent.futures as cf
import io
import json
import sys
import time
import urllib.request

import numpy as np
import pydicom

B = "idc-open-data"
U = "5d409385-d3e7-48a9-ae50-150b39e834da"


def lst():
    names, tok = [], None
    while True:
        q = f"https://storage.googleapis.com/storage/v1/b/{B}/o?prefix={U}/&maxResults=1000&fields=items(name),nextPageToken" + (f"&pageToken={tok}" if tok else "")
        j = json.load(urllib.request.urlopen(q, timeout=60))
        names += [i["name"] for i in j.get("items", [])]
        tok = j.get("nextPageToken")
        if not tok:
            return names


def head(n):
    for _ in range(4):
        try:
            req = urllib.request.Request(f"https://storage.googleapis.com/{B}/{n}", headers={"Range": "bytes=0-6000"})
            d = urllib.request.urlopen(req, timeout=60).read()
            ds = pydicom.dcmread(io.BytesIO(d), stop_before_pixels=True, force=True)
            return n, float(ds.ImagePositionPatient[2]), [float(x) for x in ds.ImagePositionPatient], [float(x) for x in ds.PixelSpacing]
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(1)
    raise err


def get(n):
    for _ in range(4):
        try:
            d = urllib.request.urlopen(f"https://storage.googleapis.com/{B}/{n}", timeout=90).read()
            ds = pydicom.dcmread(io.BytesIO(d))
            px = ds.pixel_array.astype(np.int16) * float(getattr(ds, "RescaleSlope", 1)) + float(getattr(ds, "RescaleIntercept", 0))
            return px.astype(np.int16)
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(2)
    raise err


if __name__ == "__main__":
    out = sys.argv[1]
    names = lst()
    print("files", len(names), flush=True)
    with cf.ThreadPoolExecutor(16) as ex:
        hs = list(ex.map(head, names))
    hs.sort(key=lambda t: t[1])
    zs = np.array([h[1] for h in hs])
    print("z range", zs.min(), zs.max(), "n", len(zs), "ipp0", hs[0][2], "pix", hs[0][3], flush=True)
    json.dump([[h[0], h[1]] for h in hs], open(out + ".index.json", "w"))
    lo, hi = float(sys.argv[2]), float(sys.argv[3])
    sel = [h for h in hs if lo <= h[1] <= hi]
    print("selected", len(sel), flush=True)
    with cf.ThreadPoolExecutor(8) as ex:
        vol = list(ex.map(lambda h: get(h[0]), sel))
    np.savez_compressed(out, vol=np.stack(vol), z=np.array([h[1] for h in sel]), ipp=np.array([h[2] for h in sel]), pix=np.array(hs[0][3]))
    print("DONE", flush=True)
