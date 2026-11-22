"""Q248 (b): RULE-BASED ligaments from the page's own bone (and organ) geometry.

Every ligament is a band (elliptical cross-section) between two attachment footprints, run along the straight line pushed out of the bones (clearance = half the thickness + 0.3 mm) and smoothed.
Attachment points are found by GEOMETRIC RULES on the page's own meshes (measured on the hip bones / patella / tibia / coccyx, no atlas landmark is interpolated); they are listed with the published description they follow.
The cross-section is a MODELLING CHOICE unless the entry says otherwise (no published caliper was found for the pelvic arches / transverse perineal ligament / anococcygeal ligament by a PubMed / web search, Q248);
the lengths are checked against published ranges where one exists.  Output per ligament: vertices / faces (closed, with end caps), length, cross-section, volume, attachment-to-surface distances.

Published descriptions used (all attachments; none of the numbers below is taken from this atlas' geometry):
  tendinous arch of levator ani: Gray's Anatomy 1918 (public domain) 'The Fascia and Muscles of the Pelvis': the levator ani arises from the posterior surface of the superior ramus of the pubis, from the pelvic surface of the
      spine of the ischium and, between the two, from a thickened band of the obturator fascia (the tendinous arch); Kearney, Sawhney, DeLancey, Obstet Gynecol 2004;104:168-73 (doi 10.1097/01.AOG.0000128906.61529.6b).
  arcus tendineus fasciae pelvis: Stein TA, DeLancey JO, Obstet Gynecol 2008;111:686-93 (doi 10.1097/AOG.0b013e318163a9a5): continuous with the perineal membrane at the pubis; DeLancey JO, Am J Obstet Gynecol 1992;166:1717-28
      (pubic bone to ischial spine); length ~10 cm reported for the fixed female pelvis (Occelli et al., Eur J Obstet Gynecol Reprod Biol 2001, abstract only: plausibility range, not used as input).
  transverse perineal ligament (ligamentum transversum perinei): Terminologia Anatomica; Gray 1918: a thickened band between the inferior pubic rami below the arcuate pubic ligament.
  anococcygeal ligament: Gray 1918 / TA: from the tip of the coccyx to the anal canal (external sphincter).
  puboprostatic / pubovesical ligaments: Gray 1918 / TA: pubic body (posterior surface) to the prostate (male) / bladder neck (female).
  patellar ligament: patellar apex and adjoining margins to the tibial tuberosity (Aithal Padur et al., Surg Radiol Anat 2021;43:2039-46, doi 10.1007/s00276-021-02837-z: mean length 4.8 cm right / 4.6 cm left, range 3-6 cm);
      Basso, Johnson, Amis, Knee Surg Sports Traumatol Arthrosc 2001;9:2-5 (doi 10.1007/s001670000133): fibres converge distally toward the tibial attachment, apex at 39 +- 6 % of the tendon width from its medial edge."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lig_pages as PG, landmarks as LM  # noqa: E402

CLEAR_EXTRA = 0.3


# ----------------------------------------------------------------------------- geometry
def tube(path, w, t, ref, nseg=12):
    """closed band along path (n,3): elliptical section with width w (along W) and thickness t (along N); W = ref made orthogonal to the tangent. w, t: scalars or (n,)"""
    P = np.asarray(path, float); n = len(P)
    w = np.broadcast_to(np.asarray(w, float), (n,)); t = np.broadcast_to(np.asarray(t, float), (n,))
    T = np.gradient(P, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    ref = np.broadcast_to(np.asarray(ref, float), (n, 3))
    W = ref - (ref * T).sum(1, keepdims=True) * T
    bad = np.linalg.norm(W, axis=1) < 1e-6
    if bad.any():
        W[bad] = np.cross(T[bad], [0, 0, 1.0])
    W /= np.linalg.norm(W, axis=1, keepdims=True)
    N = np.cross(T, W)
    th = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    V = (P[:, None, :] + 0.5 * w[:, None, None] * np.cos(th)[None, :, None] * W[:, None, :] + 0.5 * t[:, None, None] * np.sin(th)[None, :, None] * N[:, None, :]).reshape(-1, 3)
    F = []
    for i in range(n - 1):
        for k in range(nseg):
            a, b = i * nseg + k, i * nseg + (k + 1) % nseg
            c, d = (i + 1) * nseg + k, (i + 1) * nseg + (k + 1) % nseg
            F += [[a, b, d], [a, d, c]]
    c0, c1 = len(V), len(V) + 1
    V = np.vstack([V, P[0], P[-1]])
    for k in range(nseg):
        F.append([c0, (k + 1) % nseg, k]); F.append([c1, (n - 1) * nseg + k, (n - 1) * nseg + (k + 1) % nseg])
    F = np.array(F)
    m = trimesh.Trimesh(V, F, process=False)
    if m.volume < 0:
        F = F[:, ::-1]
    return V, F, c0, c1


def smooth_path(P, it=6):
    P = P.copy()
    for _ in range(it):
        P[1:-1] = 0.5 * P[1:-1] + 0.25 * (P[:-2] + P[2:])
    return P


def route(ctx, A, B, n=40, clear=1.2, bone_ids=None, loops=4):
    """straight A->B sampled at n points, interior points pushed out of the bones to a signed distance >= clear, then smoothed (ends fixed)"""
    P = A[None] + (B - A)[None] * np.linspace(0, 1, n)[:, None]
    ids = bone_ids or ctx.near_bones(P, 20.0)
    for _ in range(loops):
        sd, a, nr, pt = ctx.bf.signed(P, ids)
        bad = sd < clear
        bad[0] = bad[-1] = False
        if not bad.any():
            break
        P[bad] += nr[bad] * (clear - sd[bad])[:, None]
        P = smooth_path(P, 3)
    return P


# ----------------------------------------------------------------------------- page context
class Ctx:
    def __init__(self, key, root=None):
        self.key = key
        self.E = PG.load(key, root)
        self.bf = PG.BoneField(self.E)
        self.female = key in PG.FEMALE
        self.F = LM.pubis_frame(self.E)

    def near_bones(self, P, margin):
        ids = [i for i, e in self.E.items() if e["sys"] == "bone" and "zfill" not in i and len(e["f"]) > 20]
        return self.bf.near(P, ids, margin)

    def find(self, *cands):
        for c in cands:
            if c in self.E:
                return self.E[c]
        return None

    def ischial_spine(self, s):
        v = self.E[f"hip_bone_{s}"]["v"]; F = self.F
        m = (v[:, 2] < F["z_front"] - 70) & (v[:, 1] > F["y_top"]) & (v[:, 1] < F["y_top"] + 35)
        c = v[m]
        score = np.abs(c[:, 0] - F["x_mid"]) + 0.5 * np.abs(c[:, 1] - (F["y_top"] + 15))
        return c[np.argmin(score)]

    def pubic_posterior(self, s, lateral, y_rel, win=(5.0, 5.0)):
        """posterior-most hip-bone vertex of the pubic body in a window `lateral` mm from the symphysial face (side s), at height y_bot + y_rel"""
        F = self.F; v = self.E[f"hip_bone_{s}"]["v"]
        sg = -1.0 if s == "l" else 1.0
        xt = F["x_mid"] + sg * (F["half_gap"] + lateral); yt = F["y_bot"] + y_rel
        m = (np.abs(v[:, 0] - xt) <= win[0]) & (np.abs(v[:, 1] - yt) <= win[1]) & (v[:, 2] > F["z_front"] - 40)
        c = v[m]
        if not len(c):
            return None
        return c[np.argmin(c[:, 2])]


def attach_report(ctx, V, c0, c1, bone_of_end, cap_center_idx=None):
    """distance of the two end-cap centres to the named structures' surfaces (signed: negative = inside)"""
    out = {}
    for nm, idx, bid in (("end_a", c0, bone_of_end[0]), ("end_b", c1, bone_of_end[1])):
        if bid is None:
            continue
        if bid in ctx.E and ctx.E[bid]["sys"] == "bone":
            d = ctx.bf.signed(V[idx:idx + 1], [bid])[0][0]
        else:
            d = None
        out[nm] = dict(target=bid, signed_distance_mm=None if d is None else round(float(d), 2))
    return out


def finish(ctx, V, F, c0, c1, ends, protect_bones, name, extra=None):
    """push every vertex that is deeper than 1 mm inside a bone out of it (end-cap centres stay: they are the attachment points), measure"""
    ids = ctx.near_bones(V, 4.0)
    sd, a, nr, pt = ctx.bf.signed(V, ids)
    deep = sd < -1.0
    deep[[c0, c1]] = False
    moved = int(deep.sum())
    if moved:
        V = V.copy(); V[deep] += nr[deep] * (-sd[deep] + 0.2)[:, None]
    sd2 = ctx.bf.signed(V, ids)[0]
    m = trimesh.Trimesh(V, F, process=False)
    rep = dict(vertices=int(len(V)), pushed_out_of_bone=moved, min_signed_distance_mm=round(float(sd2.min()), 2), vertices_deeper_1mm=int((sd2 < -1.0).sum()),
               volume_mm3=round(float(abs(m.volume)), 1), volume_cm3=round(float(abs(m.volume)) / 1000, 4), watertight=bool(m.is_watertight))
    rep["attachments"] = attach_report(ctx, V, c0, c1, ends)
    if extra:
        rep.update(extra)
    return V, rep


def snap_end(ctx, P, bone_id):
    p, d = LM.snap(ctx.bf, P, bone_id)
    return p, d
