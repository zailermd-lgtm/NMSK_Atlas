"""Q235: the Chinese Visible Human female pelvic meshes (third_party/cvh_wu2015, Wu et al. 2015 PLOS ONE S3 Fig, CC BY 4.0) in the atlas axis convention (before registration).
CVH file frame: mm, x lateral (side unknown), y POSTERIOR, z INFERIOR, bilateral midline plane x = 184. Atlas frame: +X right, +Y superior, +Z anterior (mm).
Axis map for a side convention sx = +1 (file +x is the patient's RIGHT) or -1 (file +x is the patient's LEFT):   X = sx (x - 184),  Y = -z,  Z = -y."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, trimesh

REPO = Path(__file__).resolve().parents[3]
TP = REPO / "third_party" / "cvh_wu2015"
MID = 184.0
_J = None


def index():
    global _J
    if _J is None:
        _J = json.loads((TP / "structures.json").read_text())["structures"]
    return {s["index"]: s for s in _J}


def load_raw(i):
    s = index()[i]
    m = trimesh.load(TP / s["file"], process=False)
    return np.asarray(m.vertices, float), np.asarray(m.faces, np.int64)


def to_atlas(V, sx=1, F=None):
    """file frame -> atlas axes. sx=+1 is a reflection of the numbers (the atlas frame is left-handed) but not of the anatomy; sx=-1 is a proper rotation. Winding is flipped when det < 0 so normals stay outward
    in the 'physical' sense used by the viewer (the viewer frame is the atlas frame)."""
    W = np.stack([sx * (V[:, 0] - MID), -V[:, 2], -V[:, 1]], 1)
    if F is None:
        return W
    det = np.linalg.det(np.array([[sx, 0, 0], [0, 0, -1], [0, -1, 0]], float))
    return W, (F[:, ::-1] if det < 0 else F)
