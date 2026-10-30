"""Stream HER full-resolution (0.33 mm) colour cryosections of the pelvis from the IDC mirror into a memmap (Q288).

    python3 scripts/cryo/vhf_stream_pelvis_q288.py --index /dev/shm/q288/idx/full_index.json \
        --z-top -1700 --z-bot -1960 --out /dev/shm/q288/photos/pelvis

Series 56f8119f-5940-48c1-96ee-8d445dc0b5fd (VHP-F 'Fullcolor - direct digital', 5186 photographs 0.33 mm apart,
1216 x 2048 RGB, public domain NLM). --index is the header index [(object, instance, z_mm, rows, cols)] sorted
superior first (one ranged 8 kB GET per object). One photograph per --step mm of the series' own z (cryo z), kept
at FULL in-plane resolution inside the fixed photograph window --rows/--cols (the gelatin block does not move
between photographs). Output <out>.npy (n, h, w, 3) uint8 and <out>.json (per level: object, instance, cryo z).
Nothing is written to disk but the crops; the 7.5 MB DICOMs are decoded in memory."""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.cryo.vhf_stream_crops import fetch  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", required=True); ap.add_argument("--z-top", type=float, required=True)
    ap.add_argument("--z-bot", type=float, required=True); ap.add_argument("--step", type=float, default=1.0)
    ap.add_argument("--rows", default="60,1060"); ap.add_argument("--cols", default="280,1820")
    ap.add_argument("--out", required=True); ap.add_argument("--threads", type=int, default=8)
    a = ap.parse_args()
    idx = json.load(open(a.index)); zs = np.array([t[2] for t in idx])
    r0, r1 = map(int, a.rows.split(",")); c0, c1 = map(int, a.cols.split(","))
    want = np.arange(a.z_top, a.z_bot - 1e-6, -a.step)
    sel = []
    for z in want:
        i = int(np.argmin(abs(zs - z)))
        if abs(zs[i] - z) < 0.2 and (not sel or sel[-1] != i):
            sel.append(i)
    print(f"{len(sel)} photographs, cryo z {zs[sel[0]]:.2f}..{zs[sel[-1]]:.2f}, window rows {r0}:{r1} cols {c0}:{c1}", flush=True)
    mm = np.lib.format.open_memmap(a.out + ".npy", mode="w+", dtype=np.uint8, shape=(len(sel), r1 - r0, c1 - c0, 3))
    t0 = time.time()
    with cf.ThreadPoolExecutor(a.threads) as ex:
        for j, px in enumerate(ex.map(lambda i: fetch(idx[i][0]), sel)):
            mm[j] = px[r0:r1, c0:c1]
            if j % 25 == 0:
                print(j, f"{time.time() - t0:.0f}s", flush=True)
    mm.flush()
    json.dump({"series": "56f8119f-5940-48c1-96ee-8d445dc0b5fd", "window_rows": [r0, r1], "window_cols": [c0, c1], "px_mm": 1 / 3,
               "levels": [{"object": idx[i][0], "instance": idx[i][1], "cryo_z": idx[i][2]} for i in sel]}, open(a.out + ".json", "w"))
    print("STREAM_DONE", len(sel), f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
