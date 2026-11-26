"""Q399: per-structure census (the Q394 test + Q399 single-sheet completion + per-digit test) in every state, against a fixed
posed skin, for candidate rest geometry / rig entries (development and acceptance helper for fix_q399.py)."""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[3]
for p in ("q394", "q353", "q340", "q384", "q241", "q392", "q398", "q366"):
    sys.path.insert(0, str(REPO / "scripts/anatomy" / p))
sys.path.insert(0, str(REPO))
import under_skin_q394 as U  # noqa
import pose_replica_q384 as PR  # noqa
import make_pose_rig as MK  # noqa


def entry_of(rig, blob, n, v):
    for g in rig["rigid"]:
        if n in g[1]:
            return ("rigid", g[0])
    for e in rig["skin"]:
        if e[0] == n:
            si, nv, K, pal, off, nc = e
            b = np.frombuffer(blob, np.uint8, offset=off); mb = (nv + 7) >> 3
            ctrl = np.unpackbits(b[:mb])[:nv].astype(bool); p = mb
            ci = np.stack([b[p + k * nc: p + (k + 1) * nc] for k in range(K)], 1).astype(np.int64); p += K * nc
            cw = np.zeros((nc, K))
            for k in range(1, K):
                cw[:, k] = b[p + (k - 1) * nc: p + k * nc]
            cw[:, 0] = 255 - cw[:, 1:].sum(1)
            sg, w = MK.decode_weights(np.asarray(v, float), ctrl, pal, ci, cw)
            return ("skin", sg.astype(np.int16), w.astype(np.float32))
    raise KeyError(n)


class Eval:
    def __init__(self, page_dir, rig_path=None, states=None, cache=None, skin_V=None):
        self.pg = pg = U.Page(page_dir, rig_path, cache)
        if skin_V:
            for k, v in skin_V.items():
                pg.V[k] = v
        self.states = list(states or U.STATES)
        rig, W, blend = pg.rig()
        self.rig, self.W, self.blend = rig, W, blend
        self.M = {s: (U.fk(rig, U.STATES[s]) if U.STATES[s] else None) for s in self.states}
        self.sk = {}; self.dg = {}
        cls = pg.cls()
        extra = [k for k in pg.ids if U.PHAL_RE.match(k) or (U.SKIN_SKIP.search(k) and pg.sys.get(k) == "skin")]
        for s in self.states:
            pos = pg.posed(s, ids=pg.skin_ids + extra)
            self.sk[s] = U.Skin(pg.skin_ids, pos, pg.F, cls)
            self.dg[s] = U.Digits(pg, pos, cls) if U.DIGITS else None
        self._alt = {}

    def alt_rig(self, path):
        if path not in self._alt:
            self._alt[path] = PR.load_rig(path)
        return self._alt[path]

    def pose(self, s, v, o):
        M = self.M[s]
        if M is None:
            return v
        return v @ M[o[1]][:3, :3].T + M[o[1]][:3, 3] if o[0] == "rigid" else self.blend(v, o[1], o[2], M)

    def entry(self, k, v=None, rig_path=None):
        n = self.pg.idx[k]
        v = self.pg.V[k] if v is None else v
        if rig_path is None:
            if v is self.pg.V[k]:
                return self.W[n]
            rig, blob = self.alt_rig(str(self.pg.rig_path))
        else:
            rig, blob = self.alt_rig(str(rig_path))
        return entry_of(rig, blob, n, v)

    def test(self, s, P):
        sk = self.sk[s]
        out, so, si, sown, tang, q = sk.test(P)
        c = np.where(out)[0]
        if len(c):
            conf = sk.confirm(P[c]); out[c[~conf]] = False
        din = np.zeros(len(P), bool)
        if self.dg[s] is not None:
            din, dout, dd = self.dg[s].test(P)
            out[din] = dout[din]; so = so.copy(); so[din] = dd[din]
        h = np.where((so > 0) & (si >= 0) & (tang < U.TANG_MAX) & ~din)[0]
        hid = np.zeros(len(P), bool)
        if len(h):
            hid[h[sk.confirm(P[h])]] = True
        return out, so, si, hid, sown

    def struct(self, k, v=None, o=None, states=None, detail=False):
        """-> {state: (n, max_mm, hidden_n, hidden_max)}"""
        v = self.pg.V[k] if v is None else v
        if o is None:
            o = self.entry(k, v)
        r = {}
        for s in (states or self.states):
            P = self.pose(s, v, o)
            out, so, si, hid, sown = self.test(s, P)
            r[s] = (int(out.sum()), round(float(so[out].max()), 3) if out.any() else 0.0,
                    int(hid.sum()), round(float(so[hid].max()), 3) if hid.any() else 0.0)
            if detail:
                r[s] = r[s] + (np.where(out)[0], so, si, hid)
        return r


def load_list(path):
    return {(e["state"], e["id"]): e for e in json.load(open(path))["open"]}
