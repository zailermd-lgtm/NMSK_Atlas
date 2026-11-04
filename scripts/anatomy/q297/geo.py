"""Decode one structure's geometry straight from a page dir (no full-page load)."""
import json, re, base64
from pathlib import Path
import numpy as np
REPO = Path('/home/user/NMSK_Atlas')
DIRS = {"own_m": ("viewer_m_hr","atlas_viewer_male.html","own"),
        "own_f": ("viewer_f_hr","atlas_viewer_female.html","own"),
        "base_m": ("viewer_zan_atlas","atlas_viewer_zan_atlas.html","zan"),
        "base_f": ("viewer_base_female","atlas_viewer_base_female.html","zan"),
        "comb_m": ("viewer_zan_vhm","atlas_viewer_zan_male_fitted.html","zan"),
        "comb_f": ("viewer_zan_female","atlas_viewer_zan_female.html","zan")}
_CACHE = {}


# Q308: the baseline is ASKED FOR, never written down here. `scripts/anatomy/q241/model.SRC` is the one place
# in this repository that declares which build the six pages come from, and `model.build_root()` reads it. A
# second copy of the literal goes stale silently the moment a round lands -- which is exactly what happened to
# this module: its default stayed `build/q296`, where the provenance audit reports d_unaccounted = 2, so every
# run without an explicit --src kept auditing the PRE-Q297 state and reporting it as today's.
def _baseline():
    import sys as _s
    _p = str(REPO / "scripts/anatomy/q241")
    if _p not in _s.path:
        _s.path.insert(0, _p)
    import model as _m
    return _m.build_root()


def blob(key, root=None):
    root = root or _baseline()   # Q308: the current baseline, not a stale literal
    ck = (key, root)
    if ck in _CACHE: return _CACHE[ck]
    dn, hn, kind = DIRS[key]
    d = REPO/root/dn
    h = (d/hn).read_text(encoding='utf-8')
    files = json.loads(re.search(r"BIN_FILES(?:__)?\s*=\s*(\[.*?\])\s*;?\s*$", h, re.M).group(1))
    b = b"".join(base64.b64decode((d/f["path"]).read_text().strip()) for f in files)
    _CACHE[ck] = (b, h, kind, d)
    return _CACHE[ck]

def zan_meshes(key, root=None):
    root = root or _baseline()   # Q308: the current baseline, not a stale literal
    b, h, kind, d = blob(key, root)
    man = json.loads(re.search(r"^window\.__ANATOMY_MANIFEST__=(.*);$", h, re.M).group(1))
    return b, man['meshes']

def get_zan(key, sid, root=None):
    root = root or _baseline()   # Q308: the current baseline, not a stale literal
    b, me = zan_meshes(key, root)
    for r in me:
        if r['id'] == sid:
            q = np.frombuffer(b, np.uint16, r['vc']*3, r['vo']).reshape(-1,3).astype(np.float64)
            f = np.frombuffer(b, np.uint16, r['ic']*3, r['io']).reshape(-1,3).astype(np.int64)
            v = np.asarray(r['min']) + q/65535.0*np.asarray(r['span'])
            return v, f, r
    return None

def own_structures(key, root=None):
    root = root or _baseline()   # Q308: the current baseline, not a stale literal
    b, h, kind, d = blob(key, root)
    import sys; sys.path.insert(0, str(REPO))
    from scripts.transfer.bundle_io import decode
    bj = json.loads(re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', h, re.S).group(1))
    return bj, b, decode

def get_own(key, sid, root=None):
    root = root or _baseline()   # Q308: the current baseline, not a stale literal
    bj, b, decode = own_structures(key, root)
    for e, v, f in decode(bj, b):
        if e['id'] == sid:
            return np.asarray(v, float), np.asarray(f, np.int64), e
    return None

def get(key, sid, root=None):
    root = root or _baseline()   # Q308: the current baseline, not a stale literal
    return (get_own if DIRS[key][2]=='own' else get_zan)(key, sid, root)
