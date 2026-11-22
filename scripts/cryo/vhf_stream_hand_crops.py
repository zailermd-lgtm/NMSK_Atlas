"""Female cryosections, third pass: FULL-RESOLUTION (0.33 mm) crops of the right HAND, wrist to fingertips (v1 frame
z -680 .. -810), from the same IDC slices as vhf_stream_arm_crops.py. The arm crops (frame rows 110-370) cut the
palmar side of the hand off (the hand hangs by the thigh with the palm and thumb anterior: at the metacarpal levels
10-30 mm of the hand -- the thenar eminence and the thumb -- lie above frame row 110), so the hand is re-cut with a
box that starts at frame row 40. Same mapping as the arm crops (vhf_resample_cryo.py's piecewise shifts, x3), same
file layout (arm_full_bbox.json / arm_full_right.npy) in scratchpad/vh_cryo_f_hand/ so ArmCrops reads it unchanged.

    python3 scripts/cryo/vhf_stream_hand_crops.py [--z-top -680 --z-bot -810]
"""
import argparse, io, json, os, time, urllib.request, concurrent.futures as cf
import numpy as np, pydicom
from scipy import ndimage as ndi

S = "/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"; D = S + "vh_cryo_f/"; O = S + "vh_cryo_f_hand/"
H = 405; sc = 0.99; BOX = {"right": (40, 250, 0, 275)}


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument("--z-top", type=int, default=-680); ap.add_argument("--z-bot", type=int, default=-810)
    ap.add_argument("--threads", type=int, default=2); a = ap.parse_args()
    os.makedirs(O, exist_ok=True)
    for f in ("frame.json", "anchors.json"):
        if not os.path.exists(O + f):
            os.symlink(D + f, O + f)
    fr = json.load(open(D + "frame.json")); idx = json.load(open(D + "cryo_index.json")); a0, b = fr["z_offset_line"]
    A = [x for x in json.load(open(D + "anchors.json")) if x["flip"] == "fy" and x["iou"] >= 0.7]
    zs_a = np.array([x["ct_z"] for x in A]); rs = ndi.median_filter(np.array([x["shift"][0] for x in A], float), 5, mode="nearest")
    cs = ndi.median_filter(np.array([x["shift"][1] for x in A], float), 5, mode="nearest"); o = np.argsort(zs_a); zs_a, rs, cs = zs_a[o], rs[o], cs[o]
    win = {}; zlist = []
    for z in range(a.z_top, a.z_bot - 1, -1):
        zi = int(round(-(a0 + b * z) - z))
        if zi < 0 or zi >= len(idx):
            continue
        RS = float(np.interp(z, zs_a, rs)); CS = float(np.interp(z, zs_a, cs)); w = {}
        for side, (r0, r1, c0, c1) in BOX.items():
            src_r = [(H - 1) - (r - RS) / sc for r in (r0, r1)]; src_c = [(c - 110 - CS) / sc for c in (c0, c1)]
            w[side] = [int(max(0, min(src_r))) * 3, int(min(H, max(src_r))) * 3, int(max(0, min(src_c))) * 3, int(min(682, max(src_c))) * 3]
        win[zi] = w; zlist.append((z, zi))
    zis = [zi for _, zi in zlist]; hmax = max(v["right"][1] - v["right"][0] for v in win.values()); wmax = max(v["right"][3] - v["right"][2] for v in win.values())
    print("slices", len(zis), "crop max h,w", hmax, wmax, flush=True)
    mm = np.lib.format.open_memmap(O + "arm_full_right.npy", mode="w+", dtype=np.uint8, shape=(len(zis), hmax, wmax, 3))

    def fetch(j):
        n_ = idx[zis[j]][0]; err = None
        for _ in range(4):
            try:
                d = urllib.request.urlopen(f"https://storage.googleapis.com/idc-open-data/{n_}", timeout=120).read()
                return j, pydicom.dcmread(io.BytesIO(d)).pixel_array
            except Exception as e:
                err = e; time.sleep(2)
        raise err
    t0 = time.time()
    with cf.ThreadPoolExecutor(a.threads) as ex:
        for j, px in ex.map(fetch, range(len(zis))):
            w = win[zis[j]]["right"]; crop = px[w[0]:w[1], w[2]:w[3]]; mm[j, :crop.shape[0], :crop.shape[1]] = crop
            if j % 20 == 0:
                print(j, f"{time.time() - t0:.0f}s", flush=True)
    mm.flush()
    json.dump({"z_ras": [z for z, _ in zlist], "cryo_idx": zis, "windows": {str(k): v for k, v in win.items()}, "box_frame": BOX,
               "note": "full-res px = 3 x (1 mm cryo px); frame mapping as vhf_resample_cryo.py; hand box (rows 40-250) of vhf_stream_hand_crops.py"},
              open(O + "arm_full_bbox.json", "w"))
    print("HAND_FULL_DONE", flush=True)


if __name__ == "__main__":
    main()
