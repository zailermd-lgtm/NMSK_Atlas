"""Apply the measured height correction to the female cryosection frame.

    python3 scripts/cryo/vhf_correct_frame_z.py [--frame DIR] [--survey data/derived/vhf_cryo_frame_z_survey.json]

vhf_check_frame_z.py measured, level by level, how many millimetres BELOW the expected slice the
photograph that matches each CT slice lies (offset > 0: the frame was placed too high). This fits a
smooth offset(y) through the reliable levels (score >= 0.45, sharpness >= 0.03; running median of 5,
then linear interpolation, constant beyond the ends) and rewrites cryo_frame_cls.npy / cryo_frame_rgb.npy
so that slice k now holds the photograph that shows the anatomy at RAS z = z0 + k. The uncorrected
arrays are kept as *_v1.npy; frame.json records the correction. Every script that reads the frame
(deltoid, rotator cuff, arm muscles, pectoralis minor, skin union, lean envelopes) then sees the
photographs at the right height without change. Nothing here is anatomy."""
import argparse, json, os
import numpy as np
from scipy.ndimage import median_filter

ap = argparse.ArgumentParser()
ap.add_argument("--frame", default="/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/vh_cryo_f")
ap.add_argument("--survey", default="data/derived/vhf_cryo_frame_z_survey.json")
ap.add_argument("--origin-y", type=float, default=-885.229, help="atlas origin's RAS z (survey heights are atlas y)")
ap.add_argument("--min-score", type=float, default=0.45); ap.add_argument("--min-sharp", type=float, default=0.03)
ap.add_argument("--dry", action="store_true")
a = ap.parse_args(); D = a.frame
rows = json.load(open(a.survey)); rows = rows["rows"] if isinstance(rows, dict) else rows
ok = [r for r in rows if r["score"] >= a.min_score and r["sharpness"] >= a.min_sharp]
ok.sort(key=lambda r: r["y"])
ys = np.array([r["y"] for r in ok]); off = np.array([r["offset_mm"] for r in ok])
off_s = median_filter(off, size=5, mode="nearest")
fr = json.load(open(f"{D}/frame.json")); z0 = fr["z0"]
cls = np.load(f"{D}/cryo_frame_cls.npy", mmap_mode="r"); n = cls.shape[0]
k = np.arange(n); y_of_k = z0 + k - a.origin_y
d = np.interp(y_of_k, ys, off_s)                  # offset per frame slice (mm = slices)
src = np.clip(np.rint(k + d).astype(int), 0, n - 1)
print(f"{len(ok)} reliable levels of {len(rows)}; offset median {np.median(off_s):.1f} mm, range {off_s.min():.1f}..{off_s.max():.1f}")
for y in (700, 500, 300, 100, 0, -200, -400, -600, -800):
    kk = int(round(y + a.origin_y - z0))
    if 0 <= kk < n:
        print(f"  y {y:5d}: slice {kk} <- old slice {src[kk]} (offset {d[kk]:+.1f})")
if a.dry:
    raise SystemExit(0)
for name in ("cryo_frame_cls.npy", "cryo_frame_rgb.npy"):
    old = f"{D}/{name}"; v1 = f"{D}/{name[:-4]}_v1.npy"
    if not os.path.exists(v1):
        os.rename(old, v1)
    arr = np.load(v1, mmap_mode="r")
    out = np.lib.format.open_memmap(old, mode="w+", dtype=arr.dtype, shape=arr.shape)
    for kk in range(n):
        out[kk] = arr[src[kk]]
    out.flush(); del out
    print("wrote", old)
fr["z_correction"] = {"applied": "2026-09-13", "survey": a.survey, "source_slice_of_slice": "k + offset(y)",
                      "offset_mm_at_y": {str(int(y)): round(float(np.interp(y, ys, off_s)), 1) for y in range(800, -900, -100)},
                      "note": "frame v1 (kept as *_v1.npy) was this many mm too high: slice k of v1 showed the anatomy of k - offset"}
json.dump(fr, open(f"{D}/frame.json", "w"), indent=1)
print("frame.json updated")
