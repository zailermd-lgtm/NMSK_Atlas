"""Q295: the Imaging page of a body (its own CT / cryo segmentations, same atlas frame as the Combined page) as a 2 mm label volume:
which segmented structure occupies a point of that body. Used to NAME the soft-tissue voids of the Combined / Base pages
(e.g. 'the Z-Anatomy model leaves empty what her CT calls small intestine')."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sl295 as S  # noqa: E402

OWN = {"vhf": "own_f", "vhm": "own_m"}
RES = 2.0


def build(body):
    p = Path(f"/dev/shm/q295/ownlab_{body}.npz")
    if p.exists():
        z = np.load(p, allow_pickle=True); return z["lab"], z["origin"], list(z["ids"]), list(z["cats"]), list(z["names"])
    pg = S.Page(OWN[body])
    skin = pg.sid_where(lambda k, c, n: c == 'skin'); cnt = pg.sid_where(lambda k, c, n: c != 'skin'); cnt = cnt[~pg.hidden[cnt]]
    lo, hi = pg.bbox(skin)
    u0, v0 = lo[0] - 4, lo[2] - 4; W = int((hi[0] - lo[0] + 8) / RES); H = int((hi[2] - lo[2] + 8) / RES)
    ys = np.arange(lo[1] + 1, hi[1], RES)
    lab = np.full((len(ys), H, W), -1, np.int16)
    for i, y in enumerate(ys):
        _, _, l, _ = S.slice_page(pg, y, (u0, v0, RES, W, H), skin, cnt)
        lab[i] = l
    org = np.array([u0, ys[0], v0])
    np.savez_compressed(p, lab=lab, origin=org, ids=np.array(pg.ids), cats=np.array(pg.cats), names=np.array(pg.names, object))
    return lab, org, pg.ids, list(pg.cats), pg.names


class Lookup:
    def __init__(self, body):
        self.lab, self.org, self.ids, self.cats, self.names = build(body)

    def __call__(self, P):
        P = np.asarray(P)
        i = np.rint((P[:, 1] - self.org[1]) / RES).astype(int); j = np.floor((P[:, 2] - self.org[2]) / RES).astype(int)
        k = np.floor((P[:, 0] - self.org[0]) / RES).astype(int)
        ok = (i >= 0) & (i < self.lab.shape[0]) & (j >= 0) & (j < self.lab.shape[1]) & (k >= 0) & (k < self.lab.shape[2])
        out = np.full(len(P), -1, np.int32); out[ok] = self.lab[i[ok], j[ok], k[ok]]
        return out
