"""Q237 core: current six pages -> structure groups (L/R by name), midsagittal plane per model, mirror helpers.
Frame of every model: mm, +X = the subject's right, +Y superior, +Z anterior (scripts/zanatomy/q198_load.py)."""
from __future__ import annotations
import os, re, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy")); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))

# current page dirs (Q233 / Q234 / Q235 outputs); override a page with Q237_SRC_<key>
PAGES = {  # key: (dir, html stem, kind, label, page dir name in build/q237)
    "own_m": ("build/q233/viewer_m_hr", "atlas_viewer_male.html", "own", "Imaging-based · Male", "viewer_m_hr"),
    "own_f": ("build/q235/viewer_f_hr", "atlas_viewer_female.html", "own", "Imaging-based · Female", "viewer_f_hr"),
    "base_m": ("build/q233/viewer_zan_atlas", "atlas_viewer_zan_atlas.html", "zan", "Base · Male", "viewer_zan_atlas"),
    "base_f": ("build/q234/viewer_base_female", "atlas_viewer_base_female.html", "zan", "Base · Female", "viewer_base_female"),
    "comb_m": ("build/q233/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Combined · Male", "viewer_zan_vhm"),
    "comb_f": ("build/q235/viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Combined · Female", "viewer_zan_female"),
}
KEYS = list(PAGES)


def load(key):
    import q198_load as L
    d, html, kind, label, _ = PAGES[key]
    d = os.environ.get("Q237_SRC_" + key, d)
    p = Path(d) if os.path.isabs(d) else REPO / d
    L.Q = p.parent
    L.MODELS["_q237"] = (p.name, html, kind, label)
    S = L.load("_q237")
    for i, x in enumerate(S):
        x["idx"] = i
    return S


# ---------------------------------------------------------------- names -> side / canonical key
SIDE_TOK = {"l": "l", "r": "r", "left": "l", "right": "r"}
DROP_TOK = re.compile(r"^(zan|q\d+|zfill\w*|distal|proximal)$")


def side_and_canon(x):
    """-> (side 'l'|'r'|'m', canonical key, how) : side from the id tokens (_l/_r/left/right) or the page's side field."""
    ident = x["id"].lower()
    ident = re.sub(r"#\d+$", "", ident)
    toks = ident.split("_")
    side, how = None, None
    for t in toks:
        if t in SIDE_TOK:
            side = SIDE_TOK[t]; how = "token" if t in ("l", "r") else "word"; break
    if side is None and x["side"] in ("l", "r"):
        side, how = x["side"], "field"
    keep = [t for t in toks if t not in SIDE_TOK and not DROP_TOK.match(t)]
    return (side or "m"), "_".join(keep), how


def groups_of(S):
    """merge pieces: {(sys, canon, side): [structure idx...]} (zfill / re-segmented pieces and #n duplicates join their structure)."""
    G = {}
    for x in S:
        side, canon, how = side_and_canon(x)
        x["_side"], x["_canon"], x["_how"] = side, canon, how
        G.setdefault((x["sys"], canon, side), []).append(x["idx"])
    return G


# ---------------------------------------------------------------- geometry helpers
def area_samples(v, f, n=1500, rng=None):
    """area-weighted surface samples (n,3)"""
    rng = rng or np.random.default_rng(0)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    ar = np.linalg.norm(np.cross(b - a, c - a), axis=1)
    tot = ar.sum()
    if tot <= 0 or len(f) == 0:
        return v[: min(len(v), n)].copy()
    t = rng.choice(len(f), size=n, p=ar / tot)
    r1 = np.sqrt(rng.random(n)); r2 = rng.random(n)
    return (1 - r1)[:, None] * a[t] + (r1 * (1 - r2))[:, None] * b[t] + (r1 * r2)[:, None] * c[t]


def merge(S, idxs):
    vs, fs, off = [], [], 0
    for i in idxs:
        vs.append(S[i]["v"]); fs.append(S[i]["f"] + off); off += len(S[i]["v"])
    return np.vstack(vs), np.vstack(fs)


def signed_volume(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def area(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum())


def is_closed(f):
    e = np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    _, cnt = np.unique(e[:, 0] * (e.max() + 1) + e[:, 1], return_counts=True)
    return bool((cnt == 2).all())


class Plane:
    """midsagittal plane {x : n.x = d}; reflect() maps the left half onto the right half."""
    def __init__(self, n, d):
        n = np.asarray(n, float); self.n = n / np.linalg.norm(n); self.d = float(d)

    def signed(self, p):
        return np.asarray(p) @ self.n - self.d

    def reflect(self, p):
        p = np.asarray(p, float)
        return p - 2.0 * np.outer(p @ self.n - self.d, self.n) if p.ndim == 2 else p - 2.0 * (p @ self.n - self.d) * self.n

    def reflect_mesh(self, v, f):
        return self.reflect(v), f[:, ::-1].copy()          # reflection flips handedness: reverse the winding

    def matrix(self):
        """4x4 row-major affine of the reflection (for display)"""
        n = self.n; M = np.eye(4)
        M[:3, :3] = np.eye(3) - 2.0 * np.outer(n, n); M[:3, 3] = 2.0 * self.d * n
        return M

    def tilt_deg(self):
        """tilt of the normal from +X: yaw about Y (towards +Z), roll about Z (towards +Y), total"""
        n = self.n
        return dict(yaw_deg=float(np.degrees(np.arctan2(n[2], n[0]))), roll_deg=float(np.degrees(np.arctan2(n[1], n[0]))), total_deg=float(np.degrees(np.arccos(np.clip(n[0], -1, 1)))))


def robust_plane(pairs, w=None, iters=6):
    """pairs: (k,2,3) corresponding landmarks (right, left). Plane: normal = principal axis of the (R - L) vectors, offset = median of the pair mid-points along it;
    iterated with a MAD trim on the offset residual and on the angle of each pair vector to the normal."""
    P = np.asarray(pairs, float); k = len(P)
    keep = np.ones(k, bool)
    for _ in range(iters):
        D = P[keep, 0] - P[keep, 1]
        M = D.T @ D
        ev, evec = np.linalg.eigh(M)
        n = evec[:, -1]
        if n[0] < 0: n = -n
        mid = (P[:, 0] + P[:, 1]) / 2
        e = mid @ n
        d = float(np.median(e[keep]))
        res = e - d
        ang = np.degrees(np.arccos(np.clip(np.abs((P[:, 0] - P[:, 1]) @ n) / np.maximum(np.linalg.norm(P[:, 0] - P[:, 1], axis=1), 1e-9), 0, 1)))
        s1 = 1.4826 * np.median(np.abs(res[keep] - np.median(res[keep]))) + 1e-6
        s2 = 1.4826 * np.median(np.abs(ang[keep])) + 1e-3
        new = (np.abs(res) <= max(3.0 * s1, 3.0)) & (ang <= max(3.0 * s2, 6.0))
        if (new == keep).all(): break
        keep = new
    return Plane(n, d), keep, res, ang


# ---------------------------------------------------------------- midsagittal plane from the axial skeleton
AXIAL = re.compile(r"sacrum|coccyx|vertebra|sternum|(^|_)ribs?(_|$)|rib_|clavicle|scapula|hip_bone|ilium|ischium|pubis|cranium|skull|mandible|hyoid|occipital|frontal|temporal|parietal|maxilla|zygomatic|sphenoid|ethmoid|vomer|nasal|atlas|axis_c2|xiphoid|manubrium")
MIDLINE_BONE = re.compile(r"sacrum|coccyx|vertebra|sternum|hyoid|xiphoid|manubrium|atlas|axis_c2|occipital$|frontal$|sphenoid$|ethmoid|vomer|mandible|cranium")


def axial_points(S, n_per=600):
    pts, mid = [], []
    rng = np.random.default_rng(0)
    for x in S:
        if x["sys"] != "bone":
            continue
        key = (x["id"] + " " + x["_canon"]).lower()
        if not AXIAL.search(key) or re.search(r"sinus|zfill|distal", key) and False:
            continue
        v, f = x["v"], x["f"]
        if len(f) == 0:
            continue
        n = int(min(n_per + 0.0004 * len(f), 3000))
        p = area_samples(v, f, n, rng)
        pts.append(p)
        if MIDLINE_BONE.search(key):
            mid.append(x["idx"])
    return np.vstack(pts), mid


def fit_midsagittal(S):
    """Plane that makes the axial skeleton (ribs, sternum, vertebrae, sacrum, pelvis, shoulder girdle, skull) most self-symmetric:
    minimise the 75th percentile (with the median) of the nearest-surface distance of the plane-reflected sample cloud to the cloud itself.
    Start: x = median of the cloud, normal +X; coarse offset search, then Nelder-Mead over (offset, yaw, roll)."""
    from scipy.spatial import cKDTree
    from scipy.optimize import minimize
    P, mid = axial_points(S)
    tree = cKDTree(P)

    def mk(par):
        d, yaw, roll = par
        n = np.array([np.cos(yaw) * np.cos(roll), np.sin(roll) * np.cos(yaw) if False else np.sin(roll), np.sin(yaw) * np.cos(roll)])
        return Plane(n, d)

    def cost(par):
        pl = mk(par)
        dd = tree.query(pl.reflect(P), distance_upper_bound=60.0)[0]
        dd = np.minimum(dd, 60.0)
        return float(0.5 * np.median(dd) + 0.5 * np.percentile(dd, 75))

    x0 = float(np.median(P[:, 0]))
    best = min(((cost([d, 0.0, 0.0]), d) for d in np.arange(x0 - 40, x0 + 40.1, 2.0)))
    r = minimize(cost, [best[1], 0.0, 0.0], method="Nelder-Mead", options=dict(xatol=0.02, fatol=1e-4, initial_simplex=np.array([[best[1], 0, 0], [best[1] + 3, 0, 0], [best[1], 0.03, 0], [best[1], 0, 0.03]]), maxiter=400))
    pl = mk(r.x)
    dd = tree.query(pl.reflect(P))[0]
    q = dict(n_points=int(len(P)), refl_median_mm=float(np.median(dd)), refl_p75_mm=float(np.percentile(dd, 75)), refl_p95_mm=float(np.percentile(dd, 95)))
    # midline bone centroids (vertebrae, sacrum, sternum, hyoid, skull base ...) against the plane
    off = []
    for i in mid:
        c = area_samples(S[i]["v"], S[i]["f"], 400).mean(0)
        off.append((S[i]["id"], float(pl.signed(c))))
    q["midline_bones"] = dict(n=len(off), median_offset_mm=float(np.median([o for _, o in off])) if off else None,
                              p95_abs_offset_mm=float(np.percentile(np.abs([o for _, o in off]), 95)) if off else None,
                              worst=sorted(off, key=lambda t: -abs(t[1]))[:3])
    return pl, q


# ---------------------------------------------------------------- lateralised by nature
# organs / vessels whose two sides differ BY DESIGN (never mirrored, never filled from the other side): (regex on id + name, reason)
LATERAL = [
    (r"(^|_)liver|hepatic|(^|_)caudate|segment_of_liver|(^|_)porta|portal|gallbladder|cystic|bile|biliary", "liver / biliary tree: right-sided"),
    (r"spleen|splenic|(^|_)lien", "spleen: left-sided"),
    (r"stomach|(^|_)gastric|gastro_(omental|epiploic|colic|duoden|splenic|phrenic)|pylor|(^|_)fundus|omentum|omental", "stomach: left-sided"),
    (r"pancrea|duoden|jejun|ileum|ileal|small_bowel|small_intestine|(^|_)colon|colic|cecum|caecum|appendix|(^|_)sigmoid(_colon|_arter|_vein|_mesocolon|_nodes|_a$)|mesenter|mesocolon|ileocolic|celiac|coeliac|(^|_)bowel", "abdominal viscera: asymmetric arrangement"),
    (r"(^|_)heart|atrium|atrial|ventric|coronary|cusp|leaflet|valve|papillary|pericard|aortic|(^|_)aorta|thoracic_duct|cisterna|azygos|hemiazygos|vena_cava|(^|_)ivc|(^|_)svc|brachiocephalic_(trunk|a)|arch_and_great", "heart / great vessels: lateralised"),
    (r"lung|lobar|bronch|pulmon|lingul|(superior|middle|inferior)_lobe|(^|_)pleura|trachea|carina", "lungs / bronchial tree: 3 lobes right, 2 left"),
    (r"common_carotid|subclavian|vagus|vagal|recurrent_laryn|(^|_)phrenic|internal_thoracic_a|gonadal|ovarian_v|testicular_v|renal_v|suprarenal|adrenal|(^|_)brachiocephalic_v|thyroid_ima|superior_intercostal", "paired vessel / nerve with a lateralised course (left and right differ by design)"),
    (r"(^|_)esophag|oesophag", "oesophagus: deviates left below the diaphragm"),
    (r"(^|_)thymus", "thymus lobes"),
]
LATERAL_RX = [(re.compile(rx, re.I), why) for rx, why in LATERAL]
# midline single organs / structures that are not lateralised
MIDLINE_NAME = re.compile(r"(^|_)(skin|brain|spinal_cord|cord|trachea|esophagus|oesophagus|rectum|anal_canal|bladder|urinary_bladder|prostate|uterus|vagina|cervix|penis|urethra|sacrum|coccyx|sternum|hyoid|thyroid|larynx|pharynx|tongue|diaphragm|perineal_body|linea_alba)", re.I)


def lateral_reason(x):
    if x["sys"] == "cns":
        return None                       # brain / cord structures: hemispheric, treated by geometry
    s = (x["id"] + " " + str(x["name"])).lower().replace(" ", "_")
    for rx, why in LATERAL_RX:
        if rx.search(s):
            return why
    return None
