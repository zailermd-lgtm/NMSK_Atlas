#!/usr/bin/env python3
"""Q384: the viewer's pose maths in python -- forward kinematics of the compact rig a page carries, the weights as
viewer/pose/pose.js decodeSkin reconstructs them (make_pose_rig.decode_weights), and the two blends: linear (skin) and dual
quaternion (skinDQ, used when the rig says blend:"dq"). verify_pose_q384.py checks on the page that the two agree; the
offline measures (pose_metrics_q384.py, attach_q384.py) and the Q338 hand verifier's replica use it."""
from __future__ import annotations

import base64
import json
import sys
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q241"))
D2R = np.pi / 180


def rot(a, deg):
    a = np.asarray(a, float); a = a / (np.linalg.norm(a) or 1); t = deg * D2R; c, s = np.cos(t), np.sin(t); x, y, z = a; u = 1 - c
    return np.array([[c + x*x*u, x*y*u - z*s, x*z*u + y*s], [y*x*u + z*s, c + y*y*u, y*z*u - x*s], [z*x*u - y*s, z*y*u + x*s, c + z*z*u]])

def jointR(j, q):
    R = np.eye(3)
    for d, v in zip(j['dof'], q): R = R @ rot(d['a'], v)
    return R

def elevation(j, q):
    v = jointR(j, q) @ np.array(j['down']); return np.degrees(np.arccos(np.clip(v @ np.array(j['down']), -1, 1)))

def fk(rig, pose):
    """pose = {joint id: {dof key: value}} (others at q0); regions at 0 -> list of 4x4"""
    segs = rig['segs']; byseg = {j['seg']: j for j in rig['joints']}; jid = {j['id']: j for j in rig['joints']}
    lev = {L['seg']: (r, k) for r in rig['regions'] for k, L in enumerate(r['levels'])}
    def qof(j): return [pose.get(j['id'], {}).get(d['k'], d['q0']) for d in j['dof']]
    M = [np.eye(4) for _ in segs]
    for i in range(len(segs)):
        par = segs[i][1]
        if par < 0: continue
        if i in lev:
            r, k = lev[i]; c = np.array(r['levels'][k]['c']); dR = np.eye(3)
        elif i in byseg:
            j = byseg[i]; c = np.array(j['c'])
            if j.get('driven'):
                d0 = j['dof'][0]; src = jid[d0['drv']['src']]; sq = qof(src)
                ang = d0['drv']['k'] * ((elevation(src, sq) - elevation(src, [x['q0'] for x in src['dof']])) if src.get('down') else (sq[0] - src['dof'][0]['q0']))
                dR = rot(d0['a'], ang)
            else:
                dR = jointR(j, qof(j)) @ jointR(j, [x['q0'] for x in j['dof']]).T
            if j['ref'] >= 0:
                R = M[j['ref']][:3, :3] @ dR; pos = M[par][:3, :3] @ c + M[par][:3, 3]
                m = np.eye(4); m[:3, :3] = R; m[:3, 3] = pos - R @ c; M[i] = m; continue
        else:
            M[i] = M[par].copy(); continue
        A = np.eye(4); A[:3, :3] = dR; A[:3, 3] = c - dR @ c
        M[i] = M[par] @ A
    return M

def load_rig(f):
    src = json.loads(Path(f).read_text(encoding='utf-8'))
    return src['rig'], zlib.decompress(base64.b64decode(src['weights_zlib_b64']))

def decode_all(rig, blob, S, cache=None):
    import pickle
    if cache and Path(cache).exists(): return pickle.load(open(cache, 'rb'))
    import make_pose_rig as MK
    W = {}
    for g in rig['rigid']:
        for si in g[1]: W[si] = ('rigid', g[0])
    for si, nv, K, pal, off, nc in rig['skin']:
        b = np.frombuffer(blob, np.uint8, offset=off); mb = (nv + 7) >> 3
        ctrl = np.unpackbits(b[:mb])[:nv].astype(bool); p = mb
        ci = np.stack([b[p + k * nc: p + (k + 1) * nc] for k in range(K)], 1).astype(np.int64); p += K * nc
        cw = np.zeros((nc, K)); 
        for k in range(1, K): cw[:, k] = b[p + (k - 1) * nc: p + k * nc]
        cw[:, 0] = 255 - cw[:, 1:].sum(1)
        sg, w = MK.decode_weights(np.asarray(S[si]['v'], float), ctrl, pal, ci, cw)
        W[si] = ('skin', sg.astype(np.int16), w.astype(np.float32))
    if cache: pickle.dump(W, open(cache, 'wb'), protocol=4)
    return W

def lbs(v, sg, w, M):
    out = np.zeros_like(v, dtype=float)
    Ms = np.stack(M)
    for k in range(sg.shape[1]):
        A = Ms[sg[:, k]]
        out += w[:, k, None] * (np.einsum('nij,nj->ni', A[:, :3, :3], v) + A[:, :3, 3])
    return out

def m2q(R):
    """rotation matrix -> unit quaternion (w, x, y, z); the same branches as pose.js m2dq"""
    tr = R[0, 0] + R[1, 1] + R[2, 2]
    if tr > 0:
        s = np.sqrt(tr + 1.0) * 2; q = [0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s]
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2; q = [(R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s]
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2; q = [(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s]
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2; q = [(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s]
    return np.array(q)

def dqs(v, sg, w, M):
    Q = np.zeros((len(M), 8))
    for i, m in enumerate(M):
        q = m2q(m[:3, :3]); t = m[:3, 3]; w_, x, y, z = q
        Q[i, :4] = q
        Q[i, 4:] = 0.5 * np.array([-t[0]*x - t[1]*y - t[2]*z, t[0]*w_ + t[1]*z - t[2]*y, -t[0]*z + t[1]*w_ + t[2]*x, t[0]*y - t[1]*x + t[2]*w_])
    b = np.zeros((len(v), 8)); q0 = Q[sg[:, 0], :4]
    for k in range(sg.shape[1]):
        qk = Q[sg[:, k]]; sgn = np.where((qk[:, :4] * q0).sum(1) < 0, -1.0, 1.0)
        b += (w[:, k] * sgn)[:, None] * qk
    n = np.linalg.norm(b[:, :4], axis=1, keepdims=True); b /= n
    w_, x, y, z = b[:, 0], b[:, 1], b[:, 2], b[:, 3]; dw, dx, dy, dz = b[:, 4], b[:, 5], b[:, 6], b[:, 7]
    t = 2 * np.stack([-dw*x + dx*w_ - dy*z + dz*y, -dw*y + dx*z + dy*w_ - dz*x, -dw*z - dx*y + dy*x + dz*w_], 1)
    R = np.stack([1 - 2*(y*y + z*z), 2*(x*y - w_*z), 2*(x*z + w_*y), 2*(x*y + w_*z), 1 - 2*(x*x + z*z), 2*(y*z - w_*x), 2*(x*z - w_*y), 2*(y*z + w_*x), 1 - 2*(x*x + y*y)], 1).reshape(-1, 3, 3)
    return np.einsum('nij,nj->ni', R, v) + t

def posed(S, W, M, ids=None, blend=lbs):
    res = {}
    for x in S:
        i = x['idx']
        if ids is not None and i not in ids: continue
        o = W[i]; v = np.asarray(x['v'], float)
        res[i] = v @ M[o[1]][:3, :3].T + M[o[1]][:3, 3] if o[0] == 'rigid' else blend(v, o[1], o[2], M)
    return res


def blend_of(rig):
    return dqs if rig.get("blend") == "dq" else lbs
