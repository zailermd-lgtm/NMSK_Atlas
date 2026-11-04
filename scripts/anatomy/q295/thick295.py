"""Q295: how thick are the voids that stay empty after the fat / soft-tissue meshes? (3-D, on the 1 mm voxel classes of fat295.py)
The meshes leave out fat thinner than the r = 1 opening and soft tissue thinner than the r = 2 ball opening; this measures the local
thickness (2 x the 3-D distance to the nearest non-void voxel) of what was left out, plus the gas / outside-imaging voids from the stats."""
import json, sys
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fat295 as F

key = sys.argv[1]
z = np.load(F.OUT / f"{key}_vox.npz"); lab = z["lab"]
st = json.loads((F.OUT / f"{key}_vox.json").read_text())
out = {"thin_left_out_cm3": {}, "thickness_hist_cm3": {}}
hist = np.zeros(5)
edges = [0, 2, 4, 6, 10, 1e9]
n = lab.shape[0]; S_ = 260; ov = 12
for a in range(0, n, S_):
    lo, hi = max(a - ov, 0), min(a + S_ + ov, n)
    L = lab[lo:hi]
    fat = (L > 0) & (L < 128); soft = L >= 128
    keep = ndi.binary_opening(fat, structure=ndi.generate_binary_structure(3, 1)) | ndi.binary_opening(soft, structure=F.BALL2.astype(bool))
    drop = (fat | soft) & ~keep
    t = 2 * ndi.distance_transform_edt(drop)
    core = slice(a - lo, a - lo + min(S_, n - a))
    tc = t[core][drop[core]]
    hist += np.histogram(tc, bins=edges)[0]
    for k, m in (("fat", fat), ("soft", soft)):
        out["thin_left_out_cm3"][k] = out["thin_left_out_cm3"].get(k, 0) + int((m & drop)[core].sum()) / 1000
out["thickness_hist_cm3"] = {f"{edges[i]}-{edges[i+1] if edges[i+1] < 1e8 else 'more'} mm": round(hist[i] / 1000, 1) for i in range(5)}
out["thin_left_out_cm3"] = {k: round(v, 1) for k, v in out["thin_left_out_cm3"].items()}
out["gas_cm3"] = round(st["gas"] / 1000, 1); out["outside_imaging_cm3"] = round(st["unknown"] / 1000, 1)
out["void_cm3"] = round(st["void"] / 1000, 1); out["body_cm3"] = round(st["body"] / 1000, 1)
(F.OUT / f"{key}_thick.json").write_text(json.dumps(out, indent=1))
print(key, json.dumps(out))
