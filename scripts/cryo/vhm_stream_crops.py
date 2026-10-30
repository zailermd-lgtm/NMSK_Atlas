"""Male cryosections: FULL-RESOLUTION (0.33 mm) crops of a fixed photograph box over a range of levels.

    python3 scripts/cryo/vhm_stream_crops.py index --out SCRATCH/vh_cryo_m_fa
    python3 scripts/cryo/vhm_stream_crops.py preview --levels 1600,1650,1700,1750,1800 --out SCRATCH/vh_cryo_m_fa
    python3 scripts/cryo/vhm_stream_crops.py crop --levels 1598:1800 --box 400,1216,1100,2048 --out SCRATCH/vh_cryo_m_fa

The male variant of vhf_stream_crops.py. His photographs (IDC series 4aaf9181-..., 2048 x 1216 px at 0.33 mm,
1 mm apart, spine at the top, patient's left on the image right) have no registered frame in the repository, so
levels are DICOM INSTANCE NUMBERS (1001 = vertex; atlas y = 1880.476 - instance, torso RAS z = 985 - instance,
as scripts/cryo/vhm_arm_muscles_v2.py) and the box is given directly in full-resolution photograph pixels
(r0,r1,c0,c1). `index` lists the series objects on the public bucket and reads each header (8 KB range request)
for its instance number (cached in <out>/cryo_index_full.json, also seeded from any existing cryo_index.json of
the 1 mm streams); `preview` writes 3x-downsampled whole frames of a few levels (to choose the box); `crop`
streams the full frames (never written to disk) into <out>/crops.npy memmap (Z, h, w, 3) uint8 with
<out>/crops_bbox.json (levels, box), plus <out>/frames_1mm.npy, the whole frames 3x-downsampled (for the
body-centroid registration to his CT, as vhm_arm_muscles_v2.py). Network: 6 threads.
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
import pydicom

SERIES = "4aaf9181-fb6a-4a4c-bf49-d1eb9ed4a385"
BUCKET = "idc-open-data"
H, W = 1216, 2048


def list_objects():
    names, tok = [], None
    while True:
        q = (f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o?prefix={SERIES}/&maxResults=1000&fields=items(name),nextPageToken"
             + (f"&pageToken={tok}" if tok else ""))
        d = json.loads(urllib.request.urlopen(q, timeout=60).read())
        names += [it["name"] for it in d.get("items", [])]; tok = d.get("nextPageToken")
        if not tok:
            return names


def head(name):
    err = None
    for _ in range(4):
        try:
            req = urllib.request.Request(f"https://storage.googleapis.com/{BUCKET}/{name}", headers={"Range": "bytes=0-8191"})
            ds = pydicom.dcmread(io.BytesIO(urllib.request.urlopen(req, timeout=60).read()), stop_before_pixels=True, force=True)
            return name, int(ds.InstanceNumber)
        except Exception as e:  # noqa: BLE001
            err = e; time.sleep(1)
    raise err


def fetch(name):
    err = None
    for _ in range(4):
        try:
            d = urllib.request.urlopen(f"https://storage.googleapis.com/{BUCKET}/{name}", timeout=120).read()
            return pydicom.dcmread(io.BytesIO(d)).pixel_array
        except Exception as e:  # noqa: BLE001
            err = e; time.sleep(2)
    raise err


def build_index(out: Path, seeds=(), threads=6):
    """{instance: object name} for the whole series, cached."""
    p = out / "cryo_index_full.json"
    if p.exists():
        return {int(k): v for k, v in json.load(open(p)).items()}
    known = {}
    for s in seeds:
        if Path(s).exists():
            for row in json.load(open(s)):
                known[row[0]] = int(row[1])
    names = list_objects(); todo = [n for n in names if n not in known]
    print(f"{len(names)} objects, {len(todo)} headers to read", flush=True)
    with cf.ThreadPoolExecutor(threads) as ex:
        for n, inst in ex.map(head, todo):
            known[n] = inst
    idx = {inst: n for n, inst in known.items()}
    out.mkdir(parents=True, exist_ok=True); json.dump({str(k): v for k, v in sorted(idx.items())}, open(p, "w"))
    return idx


def parse_levels(s):
    if ":" in s:
        a, b = s.split(":"); return list(range(int(a), int(b) + 1))
    return [int(t) for t in s.split(",")]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("index", "preview", "crop")); ap.add_argument("--out", required=True)
    ap.add_argument("--levels", default=""); ap.add_argument("--box", default="", help="r0,r1,c0,c1 full-res photograph px")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--seed-index", action="append", default=[], help="existing cryo_index.json ([name, instance, z, ...] rows)")
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    idx = build_index(out, a.seed_index, a.threads)
    if a.cmd == "index":
        print(f"index: {len(idx)} instances {min(idx)}..{max(idx)}"); return
    levels = [l for l in parse_levels(a.levels) if l in idx]
    if a.cmd == "preview":
        from PIL import Image
        with cf.ThreadPoolExecutor(a.threads) as ex:
            for l, px in zip(levels, ex.map(lambda l: fetch(idx[l]), levels)):
                small = px[:H // 3 * 3, :W // 3 * 3].reshape(H // 3, 3, W // 3, 3, 3).mean(axis=(1, 3)).astype(np.uint8)
                Image.fromarray(small).save(out / f"preview_{l}.png"); print("preview", l, flush=True)
        return
    r0, r1, c0, c1 = [int(t) for t in a.box.split(",")]; r1 = min(r1, H); c1 = min(c1, W)
    mm = np.lib.format.open_memmap(out / "crops.npy", mode="w+", dtype=np.uint8, shape=(len(levels), r1 - r0, c1 - c0, 3))
    sm = np.lib.format.open_memmap(out / "frames_1mm.npy", mode="w+", dtype=np.uint8, shape=(len(levels), H // 3, W // 3, 3))
    t0 = time.time()
    with cf.ThreadPoolExecutor(a.threads) as ex:
        for j, px in enumerate(ex.map(lambda l: fetch(idx[l]), levels)):
            mm[j] = px[r0:r1, c0:c1]                     # the crop at full resolution
            sm[j] = px[:H // 3 * 3, :W // 3 * 3].reshape(H // 3, 3, W // 3, 3, 3).mean(axis=(1, 3)).astype(np.uint8)   # whole frame at ~1 mm (registration)
            if j % 50 == 0:
                mm.flush(); sm.flush(); print(j, f"{time.time() - t0:.0f}s", flush=True)
    mm.flush(); sm.flush()
    json.dump({"levels": levels, "box": [r0, r1, c0, c1], "px_mm": 1 / 3.0,
               "note": "levels = DICOM instance numbers; atlas y = 1880.476 - instance; torso RAS z = 985 - instance; "
                       "full frame 1216 x 2048 px at 0.33 mm, spine at the top, patient's left on the image right"},
              open(out / "crops_bbox.json", "w"))
    print("done", len(levels), "levels", f"{time.time() - t0:.0f}s", (r1 - r0) * (c1 - c0) * 3 * len(levels) / 1e6, "MB")


if __name__ == "__main__":
    main()
