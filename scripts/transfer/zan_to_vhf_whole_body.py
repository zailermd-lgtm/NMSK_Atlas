"""Q168: the whole Z-Anatomy model (CC BY-SA 4.0; one male body from BodyParts3D) fitted onto the
Visible Human FEMALE's OWN skeleton, one bone at a time, with every structure's measured error.

METHOD.
  1. BONES. Every Z-Anatomy bone is paired with her own CT bone by atlas id (`UNITS`: composites --
     cranium, each vertebral block, each rib cage side, carpus, hand/foot phalanges, metatarsus -- use
     the same composite on both sides). Each pair gets a similarity: the best (median surface residual)
     of Q147's own per-bone fit (`limb_per_bone_transfer.build_bone_maps`) and a centroid start, each
     refined by trimmed symmetric ICP (Umeyama). Her body scale = median of her reference bones; long
     bones are scaled by her own length ratio (`LENGTH_SCALED`); a bone MEASURED shorter than CUT_RATIO
     of its expected length (FOV-cut) is fitted rigidly at body scale with her->Z-Anatomy pairs only;
     a free scale outside +-SCALE_TOL of body scale is clamped. Spine/rib/digit pieces are refined
     one piece at a time, then digits, carpus and ribs by a joint-anchored chain (`CHAINS`). Her left
     radius/ulna/hand have no CT: a proxy fit to her own left forearm extensors carries them
     (`PROXY_UNITS`). Z-Anatomy bones she has no CT for (coccyx, ossicles, teeth, xiphoid, sinuses)
     follow a named unit (`FOLLOWERS`).
  2. EVERYTHING ELSE is carried by a smooth blend of the nearby bones' similarities: inverse-square
     distance to each bone's Z-Anatomy surface (Q147's SOFTEN_MM), tapered to exactly zero at
     `BLEND_CUTOFF_MM` beyond the nearest bone, so the field is continuous in space (no top-k
     switching). One gate: an upper-limb structure never takes a lower-limb bone's transform and vice
     versa, and a trunk structure never takes a forearm/hand bone's (Z-Anatomy's hands hang beside
     its thighs and hips; her hands do not sit there). Stretch and cross-structure tearing are measured.
  3. Male reproductive organs are dropped (`MALE_ONLY_IDS`); her own pelvic organs: see
     `FEMALE_PELVIC_ORGANS` (no uterus/ovary/vagina label exists for her).

VALIDATION: every transferred structure whose id is also one of HER OWN meshes (ct_vhf_* subjects,
never xfer_*) is scored (centroid distance; symmetric median surface distance), by region, with and
without the transfer (raw Z-Anatomy, only origin-aligned: both frames have origin = hip-joint-centre
midpoint).

    python3 scripts/transfer/zan_to_vhf_whole_body.py            # fits, validates, writes the JSON + PNG
    from scripts.transfer.zan_to_vhf_whole_body import load_zan_to_vhf, MALE_ONLY_IDS
    xf = load_zan_to_vhf(); v_her = xf(mesh_id, cat, v_zan_build_frame)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DEFAULT_REPORT = REPO / "data" / "derived" / "Q168_zan_to_vhf.json"
FEMALE_BUNDLE_JSON = REPO / "build" / "viewer_f_hr" / "bundle.json"
VH_DIR = REPO / "build" / "vh"

SOFTEN_MM = 8.0            # Q147 / cross_subject_transfer
BLEND_POWER = 2.0
BLEND_CUTOFF_MM = 40.0     # a bone's weight tapers to 0 this far beyond the nearest bone
UNIT_CLOUD = 4000          # source points per bone unit for the distance field
PIECE_MAX_MOVE_MM = 12.0   # piece refinement guard (vertebra/rib/finger spacing is ~15-25 mm)
PIECE_MAX_ROT_DEG = 20.0
SCALE_TOL = 0.25           # free per-bone scale allowed within +-25 % of her body scale
CUT_RATIO = 0.85           # her bone shorter than this x (Z-Anatomy x body scale): FOV-cut, fitted as a part
# a FOV-cut bone keeps its joint where the neighbouring fitted bone puts it
# (measured Q168: anchoring her FOV-cut radius/ulna to the humerus fit made her own forearm muscles WORSE,
# her->Z-Anatomy median 8.4 vs 6.2 mm -- so it is off by default; --joint-anchors turns it on)
JOINT_PARENT_OPTION = {"radius_r": "humerus_r", "ulna_r": "humerus_r", "radius_l": "humerus_l", "ulna_l": "humerus_l"}
JOINT_PARENT: dict = {}
# long bones: scale = her long-axis length / Z-Anatomy's (symmetric ICP with a free scale can trade
# length for thickness: her humerus_r came out 7 % too long that way), then rigid ICP at that scale
LENGTH_SCALED = {f"{b}_{s}" for b in ("humerus", "femur", "tibia", "fibula", "clavicle") for s in "rl"}

# ---------------------------------------------------------------- pairing (her id -> Z-Anatomy ids)
_ORD = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
        "eleventh", "twelfth")
SKULL = ["frontal", "occipital", "sphenoid", "ethmoid", "vomer"] + [
    f"{b}_{s}" for b in ("parietal", "temporal", "zygomatic", "maxilla", "nasal", "lacrimal", "palatine",
                         "inferior_nasal_concha") for s in "rl"]
CARPALS = ("scaphoid", "lunate", "triquetrum", "pisiform", "trapezium", "trapezoid", "capitate", "hamate")


def _phalanges(where: str, s: str) -> list[str]:
    out = []
    for o in _ORD[:5]:
        for p in ("proximal", "middle", "distal"):
            if p == "middle" and o == "first":
                continue
            out.append(f"zan_{p}_phalanx_of_{o}_finger_of_{where}_{s}")
    return out


def build_units() -> dict:
    """{her atlas id: [Z-Anatomy mesh ids fitted to it]} -- the per-bone pairing."""
    u = {"cranium": SKULL, "mandible": ["mandible"], "hyoid": ["hyoid"], "sacrum": ["sacrum"],
         "sternum": ["sternum"],
         "cervical_vertebrae": ["zan_atlas_c1", "zan_axis_c2"] + [f"zan_vertebra_c{i}" for i in range(3, 8)],
         "thoracic_vertebrae": [f"zan_vertebra_t{i}" for i in range(1, 13)],
         "lumbar_vertebrae": [f"zan_vertebra_l{i}" for i in range(1, 6)]}
    for s in "rl":
        u[f"ribs_{s}"] = [f"zan_{o}_rib_{s}" for o in _ORD]
        for b in ("clavicle", "scapula", "humerus", "radius", "ulna", "hip_bone", "femur", "patella", "tibia",
                  "fibula", "talus", "calcaneus", "navicular", "cuboid", "cuneiform_medial",
                  "cuneiform_intermediate", "cuneiform_lateral"):
            u[f"{b}_{s}"] = [f"{b}_{s}"]
        u[f"carpals_{s}"] = [f"zan_{c}_bone_{s}" for c in CARPALS]
        for k, o in enumerate(_ORD[:5], 1):
            u[f"metacarpal_{k}_{s}"] = [f"zan_{o}_metacarpal_bone_{s}"]
        u[f"phalanges_hand_{s}"] = _phalanges("hand", s)
        u[f"metatarsals_{s}"] = [f"zan_{o}_metatarsal_bone_{s}" for o in _ORD[:5]]
        u[f"phalanges_foot_{s}"] = _phalanges("foot", s)
    return u


UNITS = build_units()
# composites whose pieces are refined one at a time after the composite fit
REFINE_PIECES = {"cervical_vertebrae", "thoracic_vertebrae", "lumbar_vertebrae", "ribs_r", "ribs_l",
                 "carpals_r", "carpals_l", "phalanges_hand_r", "phalanges_hand_l", "metatarsals_r",
                 "metatarsals_l", "phalanges_foot_r", "phalanges_foot_l"}
# Z-Anatomy bones she has no CT label for: carried rigidly by a named unit (not fitted)
FOLLOWERS = {"coccyx": "sacrum", "zan_xiphoid_process": "sternum", "zan_sinus_of_frontal_bone": "cranium",
             "zan_sinus_of_sphenoid_bone": "cranium",
             **{f"{b}_{s}": "cranium" for b in ("malleus", "incus", "stapes") for s in "rl"},
             **{f"zan_upper_{t}_{s}": "cranium" for s in "rl" for t in (
                 "canine", "first_molar_tooth", "second_molar_tooth", "first_premolar", "second_premolar",
                 "lateral_incisor", "medial_incisor")},
             **{f"zan_lower_{t}_{s}": "mandible" for s in "rl" for t in (
                 "canine", "first_molar_tooth", "second_molar_tooth", "first_premolar", "second_premolar",
                 "lateral_incisor", "medial_incisor")}}
BODY_SCALE_UNITS = {"femur_r", "femur_l", "tibia_r", "tibia_l", "fibula_r", "fibula_l", "hip_bone_r", "hip_bone_l",
                    "cranium", "sacrum", "lumbar_vertebrae", "thoracic_vertebrae", "cervical_vertebrae",
                    "scapula_r", "scapula_l", "clavicle_r", "clavicle_l", "sternum", "mandible"}
_LEFT_FOREARM_MUSCLES = ["extensor_digitorum_l", "extensor_digiti_minimi_l", "abductor_pollicis_longus_l",
                         "extensor_pollicis_brevis_l", "extensor_pollicis_longus_l"]
# her left radius/ulna/hand are outside every CT field of view (cross_subject_transfer NOT_TRANSFERABLE), but
# her left forearm extensors ARE segmented (ct_vhf_left_forearm, cryosections): the Z-Anatomy left radius +
# ulna + hand are carried by one rigid (body-scale) fit of the same five Z-Anatomy muscles onto hers.
# Those five are then NOT independent validation (reported apart).
PROXY_UNITS = {"forearm_l_proxy": {
    "zan": _LEFT_FOREARM_MUSCLES, "her": _LEFT_FOREARM_MUSCLES,
    "drives": ["radius_l", "ulna_l"], "anchor_bone": "humerus_l", "anchor_band_mm": 30.0,
    "why": "her left radius/ulna/hand have no CT; fitted to her own left forearm extensor muscles"}}
PROXY_FOLLOWERS = {**{z: "forearm_l_proxy" for z in (
    [f"zan_{c}_bone_l" for c in CARPALS] + [f"zan_{o}_metacarpal_bone_l" for o in _ORD[:5]]
    + _phalanges("hand", "l"))}}
# her own meshes that are CT label fragments, not bones (cross_subject_transfer MIN_VERTICES note):
# never a unit, never scored
HER_FRAGMENTS = {"temporal_r", "temporal_l", "zygomatic_r", "zygomatic_l"}


PROXY_GROUP = {"forearm_l_proxy": "upper_l"}


def unit_group(unit: str) -> str:
    """axial / upper_<s> / lower_<s> -- the limb gate of the blend."""
    if unit in PROXY_GROUP:
        return PROXY_GROUP[unit]
    base, s = (unit[:-2], unit[-1]) if unit[-2:] in ("_r", "_l") else (unit, "")
    if base in ("humerus", "radius", "ulna", "carpals", "phalanges_hand") or base.startswith("metacarpal"):
        return f"upper_{s}"
    if base in ("femur", "patella", "tibia", "fibula", "talus", "calcaneus", "navicular", "cuboid",
                "metatarsals", "phalanges_foot") or base.startswith("cuneiform"):
        return f"lower_{s}"
    return "axial"


def is_distal_upper(unit: str) -> bool:
    return unit_group(unit).startswith("upper") and not unit.startswith("humerus")


def allowed_units(cls: str, units: list[str]) -> list[str]:
    """Units a structure of limb class `cls` may be carried by."""
    out = []
    for u in units:
        g = unit_group(u)
        if cls.startswith("upper") and g.startswith("lower"):
            continue
        if cls.startswith("lower") and g.startswith("upper"):
            continue
        if cls == "axial" and is_distal_upper(u):
            continue
        out.append(u)
    return out


REGION_OF_UNIT_BASE = {
    "head_neck": {"cranium", "mandible", "hyoid", "cervical_vertebrae"},
    "trunk": {"thoracic_vertebrae", "lumbar_vertebrae", "sacrum", "ribs", "sternum", "clavicle", "scapula",
              "hip_bone"},
    "upper_limb": {"humerus"},
    "forearm_hand": {"forearm_l_proxy", "radius", "ulna", "carpals", "phalanges_hand", "metacarpal_1", "metacarpal_2",
                     "metacarpal_3", "metacarpal_4", "metacarpal_5"},
    "lower_limb": {"femur", "patella", "tibia", "fibula"},
    "foot": {"talus", "calcaneus", "navicular", "cuboid", "cuneiform_medial", "cuneiform_intermediate",
             "cuneiform_lateral", "metatarsals", "phalanges_foot"},
}
REGIONS = list(REGION_OF_UNIT_BASE)


def region_of_unit(unit: str) -> str:
    base = unit[:-2] if unit[-2:] in ("_r", "_l") else unit
    for r, bases in REGION_OF_UNIT_BASE.items():
        if base in bases:
            return r
    raise KeyError(unit)


# ---------------------------------------------------------------- male-only structures (dropped)
MALE_ONLY = {
    "gonadal_a_l": "Left testicular artery", "gonadal_a_r": "Right testicular artery",
    "zan_left_testicular_vein": "Left testicular vein", "zan_right_testicular_vein": "Right testicular vein",
    "zan_testis_l": "Testis", "zan_testis_r": "Testis",
    "zan_epididymis_l": "Epididymis", "zan_epididymis_r": "Epididymis",
    "zan_ductus_deferens_l": "Ductus deferens", "zan_ductus_deferens_r": "Ductus deferens",
    "zan_ejaculatory_duct_l": "Ejaculatory duct", "zan_ejaculatory_duct_r": "Ejaculatory duct",
    "zan_seminal_gland_l": "Seminal gland", "zan_seminal_gland_r": "Seminal gland",
    "zan_prostate": "Prostate", "zan_urethra": "Urethra (male: prostatic/membranous/spongy)",
    "zan_corpus_cavernosum_of_penis": "Corpus cavernosum of penis",
    "zan_corpus_spongiosum_of_penis": "Corpus spongiosum of penis", "zan_glans_penis": "Glans penis",
    "zan_deep_artery_of_penis_l": "Deep artery of penis", "zan_deep_artery_of_penis_r": "Deep artery of penis",
    "zan_dorsal_artery_of_penis_l": "Dorsal artery of penis",
    "zan_dorsal_artery_of_penis_r": "Dorsal artery of penis",
    "zan_deep_dorsal_vein_of_penis": "Deep dorsal vein of penis",
    "zan_superficial_dorsal_veins_of_penis": "Superficial dorsal veins of penis",
}
MALE_ONLY_IDS = frozenset(MALE_ONLY)

FEMALE_PELVIC_ORGANS = {
    "uterus_ovary_tube_vagina": "none found -- no label for the uterus, ovaries, uterine tubes or vagina "
                                "exists in any of her volumes (vhf_total.nii.gz is TotalSegmentator 'total', "
                                "which has no such class; vhf_pelvic_floor_cryo.nii.gz puts the vaginal and "
                                "urethral walls in an unshipped 'perineal_other' sink). Nothing invented.",
    "labels_present_not_meshed": {
        "source": "data/ct_sources/task_outputs/vhf_total.nii.gz (TotalSegmentator v2 'total' on her CT)",
        "urinary_bladder": 21, "colon_incl_rectum": 20, "prostate_label_22": "absent (she is female)"},
    "meshed_subjects": "none (no build/vh/ct_vhf_* subject carries a pelvic organ)",
}


# ---------------------------------------------------------------- pure geometry helpers
def umeyama(P: np.ndarray, Q: np.ndarray, with_scale: bool = True):
    """Least-squares similarity Q ~ s R P + t (Umeyama 1991). Returns (s, R, t)."""
    P = np.asarray(P, np.float64); Q = np.asarray(Q, np.float64)
    mp, mq = P.mean(0), Q.mean(0)
    X, Y = P - mp, Q - mq
    U, S, Vt = np.linalg.svd(Y.T @ X / len(P))
    D = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        D[2, 2] = -1
    R = U @ D @ Vt
    s = float(np.trace(np.diag(S) @ D) / max((X ** 2).sum() / len(P), 1e-12)) if with_scale else 1.0
    return s, R, mq - s * R @ mp


def smooth_idw_weights(D: np.ndarray, soften: float = SOFTEN_MM, power: float = BLEND_POWER,
                       cutoff: float = BLEND_CUTOFF_MM) -> np.ndarray:
    """(n, m) distances (np.inf = not a candidate) -> (n, m) weights summing to 1. Inverse-power
    distance, tapered by (1 - (d - dmin)/cutoff)^2 to exactly 0: continuous wherever D is."""
    D = np.asarray(D, np.float64)
    dmin = D.min(axis=1, keepdims=True)
    with np.errstate(invalid="ignore"):
        taper = np.clip(1.0 - (D - dmin) / cutoff, 0.0, 1.0) ** 2
    taper[~np.isfinite(D)] = 0.0
    w = taper / (np.where(np.isfinite(D), D, 0.0) + soften) ** power
    return w / w.sum(axis=1, keepdims=True)


def sample_surface(v: np.ndarray, f: np.ndarray, n: int, seed: int = 0) -> np.ndarray:
    """Area-weighted random surface points (plus the vertices when there are fewer than n)."""
    v = np.asarray(v, np.float64)
    if len(f) == 0 or n <= len(v):
        rng = np.random.default_rng(seed)
        return v if n >= len(v) else v[rng.choice(len(v), n, replace=False)]
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    if area.sum() <= 0:
        return v
    rng = np.random.default_rng(seed)
    k = rng.choice(len(f), n - len(v), p=area / area.sum())
    r1, r2 = rng.random(len(k)), rng.random(len(k))
    flip = r1 + r2 > 1
    r1[flip], r2[flip] = 1 - r1[flip], 1 - r2[flip]
    pts = a[k] + r1[:, None] * (b[k] - a[k]) + r2[:, None] * (c[k] - a[k])
    return np.vstack([v, pts])


def surface_distance(A: np.ndarray, B: np.ndarray, tree_b: cKDTree | None = None,
                     tree_a: cKDTree | None = None) -> dict:
    """Median one-sided (A->B, B->A) and symmetric nearest-point distances between two dense samples."""
    dab = (tree_b or cKDTree(B)).query(A)[0]
    dba = (tree_a or cKDTree(A)).query(B)[0]
    return {"a_to_b": float(np.median(dab)), "b_to_a": float(np.median(dba)),
            "sym": float(np.median(np.concatenate([dab, dba])))}


def edge_stretch(v0: np.ndarray, v1: np.ndarray, f: np.ndarray, min_len: float = 0.1) -> np.ndarray:
    """Per-edge length ratio after/before, normalised by the mesh's own median ratio (so a uniform
    scale is not stretch). Edges shorter than `min_len` mm are ignored."""
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    l0 = np.linalg.norm(v0[e[:, 0]] - v0[e[:, 1]], axis=1)
    keep = l0 > min_len
    if not keep.any():
        return np.ones(1)
    r = np.linalg.norm(v1[e[keep, 0]] - v1[e[keep, 1]], axis=1) / l0[keep]
    return r / np.median(r)


def rot_angle_deg(R: np.ndarray) -> float:
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def apply_sim(A: np.ndarray, t: np.ndarray, v: np.ndarray) -> np.ndarray:
    return np.asarray(v, np.float64) @ A.T + t


def _sub(v: np.ndarray, n: int, seed: int = 0) -> np.ndarray:
    if len(v) <= n:
        return np.asarray(v, np.float64)
    return np.asarray(v, np.float64)[np.random.default_rng(seed).choice(len(v), n, replace=False)]


def trimmed_icp(src: np.ndarray, dst: np.ndarray, A0: np.ndarray, t0: np.ndarray, *, scale: bool = True,
                corr: str = "sym", iters: int = 40, trim: float = 0.8, anchors=None):
    """Similarity ICP from (A0, t0). corr: "sym" (src->dst and dst->src pairs), "src" (src->dst) or
    "dst" (each dst point to its nearest transformed src point -- the right one when dst is a PART of
    src, e.g. her FOV-cut bone). The worst (1 - trim) pairs are dropped each round; `anchors`
    (P, Q) pairs are always kept. scale=False keeps A0's scale. Returns (A, t) with A = s R."""
    src = np.asarray(src, np.float64); dst = np.asarray(dst, np.float64)
    tree_d = cKDTree(dst)
    A, t = A0.copy(), t0.copy()
    s_fixed = sim_scale(A0)
    for _ in range(iters):
        cur = apply_sim(A, t, src)
        P, Q, d = [], [], []
        if corr in ("sym", "src"):
            d1, j1 = tree_d.query(cur)
            P.append(src); Q.append(dst[j1]); d.append(d1)
        if corr in ("sym", "dst"):
            d2, j2 = cKDTree(cur).query(dst)
            P.append(src[j2]); Q.append(dst); d.append(d2)
        P, Q, d = np.vstack(P), np.vstack(Q), np.concatenate(d)
        keep = d <= np.quantile(d, trim)
        P, Q = P[keep], Q[keep]
        if anchors is not None:
            P, Q = np.vstack([P, anchors[0]]), np.vstack([Q, anchors[1]])
        if scale:
            s, R, tt = umeyama(P, Q, with_scale=True)
        else:
            _, R, tt = umeyama(s_fixed * P, Q, with_scale=False)
            s = s_fixed
        A_new, t_new = s * R, tt
        done = np.allclose(A_new, A, atol=1e-6) and np.allclose(t_new, t, atol=1e-4)
        A, t = A_new, t_new
        if done:
            break
    return A, t


def sim_scale(A: np.ndarray) -> float:
    return float(np.cbrt(abs(np.linalg.det(A))))


# ---------------------------------------------------------------- data loading
def her_subject_order(bundle_json: Path = FEMALE_BUNDLE_JSON) -> list[str]:
    b = json.loads(Path(bundle_json).read_text())
    return [s for s in b["subject"].split("+") if not s.startswith(("xfer_", "zanatomy", "zan_"))]


def load_her_meshes(order: list[str] | None = None, vh_dir: Path = VH_DIR, bundle_json: Path = FEMALE_BUNDLE_JSON):
    """{atlas_id: {'v','f','subject','cat'}} from her OWN subjects, first subject in the viewer's
    priority order to carry an id wins (exactly what the female viewer ships)."""
    order = order or her_subject_order(bundle_json)
    cats = {e["id"]: e["cat"] for e in json.loads(Path(bundle_json).read_text())["structures"]}
    out: dict = {}
    for sub in order:
        mf = Path(vh_dir) / sub / "manifest.json"
        if not mf.exists():
            continue
        man = json.loads(mf.read_text())
        V = np.fromfile(Path(vh_dir) / sub / "vertices.f32", dtype="<f4").reshape(-1, 3)
        F = np.fromfile(Path(vh_dir) / sub / "faces.u32", dtype="<u4").reshape(-1, 3)
        this: dict = {}
        srcf: dict = {}
        for s in man["structures"]:
            aid = s["atlas_id"]
            if aid in out:
                continue
            v0, nv, f0, nf = s["vertex_offset"], s["vertex_count"], s["face_offset"], s["triangle_count"]
            this.setdefault(aid, []).append((V[v0:v0 + nv].astype(np.float64), F[f0:f0 + nf].astype(np.int64) - v0))
            srcf.setdefault(aid, str(s.get("source_file", "")))
        for aid, chunks in this.items():
            vs, fs, off = [], [], 0
            for v, f in chunks:
                vs.append(v); fs.append(f + off); off += len(v)
            out[aid] = {"v": np.vstack(vs), "f": np.vstack(fs), "subject": sub, "cat": cats.get(aid),
                        "source_file": srcf[aid]}
    return out


def collect_zan(ids: set | None = None, contralateral: bool = True) -> list[dict]:
    """Every final Z-Anatomy mesh as build_zan_atlas_viewer.build() collects it (matched, orphans,
    rescued; corrections applied; origin-shifted; welded; outward-oriented; Q162 contralateral
    repairs) -- before its gap closure/decimation. `ids` restricts to those mesh ids."""
    from scripts.zanatomy import build_zan_atlas_viewer as Z
    inv = json.loads(Path(Z.DEFAULT_INVENTORY).read_text())
    nm = json.loads(Path(Z.DEFAULT_NAMEMAP).read_text())
    zd = Path(Z.DEFAULT_ZAN_DIR)
    matched = Z.load_source(inventory_path=Z.DEFAULT_INVENTORY, namemap_path=Z.DEFAULT_NAMEMAP, zan_dir=zd)
    orph, _, _ = Z.build_orphan_pool(inv, nm)
    resc = Z.rescue_unshipped(inv, nm, matched, orph)
    origin, _ = Z.compute_origin(zd)
    corr = Z.load_corrections(Z.DEFAULT_CORRECTIONS_DIR)
    items: list[dict] = []
    seen: set = set()

    def emit(mid, cat, v, f, name):
        if mid in seen or (ids is not None and mid not in ids):
            return
        seen.add(mid)
        w, _ = Z.apply_correction(mid, v, zd, corr)
        vv, ff = Z.orient_outward(*Z.weld(w - origin, f))
        items.append({"mesh_id": mid, "cat": cat, "v": vv, "f": ff, "name": name, "notes": []})

    for aid, r in sorted(matched.items()):
        emit(aid, r["cat"], r["v"].astype(np.float64), r["f"].astype(np.int64),
             (r.get("zanatomy_parts") or [aid])[0])
    for pool in (orph, resc):
        for s, m in sorted(pool.items()):
            if s in seen or (ids is not None and s not in ids):
                continue
            v, f = Z._load_raw_mesh(zd, m["system"], m["mesh_name"])
            emit(s, m["category"], v, f, m["name"])
    if contralateral and ids is None:
        Z.repair_contralateral(items)
    return items


# ---------------------------------------------------------------- fitting
def _residual(src_pts, dst_pts, dst_tree, A, t, truncated: bool) -> dict:
    cur = apply_sim(A, t, src_pts)
    sd = surface_distance(cur, dst_pts, tree_b=dst_tree)
    sd["fit"] = sd["b_to_a"] if truncated else sd["sym"]   # her FOV-cut bone: only her->Z-Anatomy is fair
    return sd


def _concat(zan: dict, ids: list[str]):
    vs = [np.asarray(zan[z]["v"], np.float64) for z in ids]
    offs = np.cumsum([0] + [len(v) for v in vs[:-1]])
    return np.vstack(vs), np.vstack([np.asarray(zan[z]["f"], np.int64) + o for z, o in zip(ids, offs)])


def fit_pair(src_v, src_f, dst_v, unit: str, fixed_scale: float | None = None, partial: bool = False,
             anchors=None, log=print) -> dict:
    """Best similarity src -> dst over {Q147 per-bone fit, centroid start} x {as is, + trimmed ICP}.
    fixed_scale: rigid ICP at that scale. partial: her mesh is only PART of the Z-Anatomy one (a
    FOV-cut bone, or a proxy's muscles) -- then ICP pairs run her -> Z-Anatomy only and the residual
    is her -> Z-Anatomy (a src -> dst pairing would let the cut end slide along the shaft)."""
    from scripts.transfer import limb_per_bone_transfer as q147
    src_pts = sample_surface(src_v, src_f, max(len(src_v), 20000))
    src_icp, dst_icp = _sub(src_pts, 5000, 1), _sub(dst_v, 6000, 2)
    dst_eval = _sub(dst_v, 40000, 3)
    tree_eval = cKDTree(dst_eval)
    cands = {}
    try:  # (a) Q147's own per-bone fit (bone_frame box + twist candidates + rigid ICP, TRUNCATED clip)
        mp = q147.build_bone_maps({unit: {"v": src_v, "cat": "bone", "side": None}},
                                  {unit: {"v": dst_v, "cat": "bone", "side": None}})[unit]
        cands["q147"] = (mp["A"], mp["t"])
    except Exception as e:  # noqa: BLE001 -- recorded, the other start still runs
        log(f"  {unit}: q147 fit failed ({e})")
    s0 = fixed_scale if fixed_scale is not None else float(np.sqrt(
        ((dst_icp - dst_icp.mean(0)) ** 2).sum(1).mean() / ((src_icp - src_icp.mean(0)) ** 2).sum(1).mean()))
    if fixed_scale is not None:
        c = src_icp.mean(0)
        cands = {k: (fixed_scale * A / sim_scale(A), t + (A - fixed_scale * A / sim_scale(A)) @ c)
                 for k, (A, t) in cands.items()}
    if not partial or anchors is not None:
        A0 = np.eye(3) * s0
        cands["centroid"] = (A0, dst_icp.mean(0) - A0 @ src_icp.mean(0))
    for name in list(cands):
        A, t = cands[name]
        cands[name + "+icp"] = trimmed_icp(src_icp, dst_icp, A, t, scale=fixed_scale is None and not partial,
                                           corr="dst" if partial else "sym", anchors=anchors)
    scored = {k: _residual(src_pts, dst_eval, tree_eval, A, t, partial) for k, (A, t) in cands.items()}
    if anchors is not None:  # a proxy must also keep its joint where the neighbouring bone fit put it
        for k, (A, t) in cands.items():
            gap = float(np.median(np.linalg.norm(apply_sim(A, t, anchors[0]) - anchors[1], axis=1)))
            scored[k]["anchor_gap_mm"] = gap
            scored[k]["fit"] = scored[k]["fit"] + 0.5 * gap
    best = min(scored, key=lambda k: scored[k]["fit"])
    A, t = cands[best]
    out = {"status": "fitted", "A": A, "t": t, "method": best, "truncated": partial, "scale": sim_scale(A),
           "residual_mm": scored[best]["b_to_a"] if partial else scored[best]["sym"],
           "residual_detail": {k: round(v["fit"], 2) for k, v in scored.items()},
           "zan_to_her_mm": scored[best]["a_to_b"], "her_to_zan_mm": scored[best]["b_to_a"], "piece_fits": {}}
    if anchors is not None:
        out["anchor_gap_mm"] = scored[best]["anchor_gap_mm"]
    return out


def long_extent(v: np.ndarray) -> float:
    """1st-99th percentile extent along the principal (long) axis."""
    v = _sub(v, 20000, 23)
    c = v - v.mean(0)
    ax = np.linalg.eigh(c.T @ c)[1][:, -1]
    p = c @ ax
    return float(np.percentile(p, 99) - np.percentile(p, 1))


def joint_anchors(zan: dict, child: str, parent: str, fits: dict, reps: int = 4):
    """(P, Q): the child's Z-Anatomy points within JOINT_MM of its parent bone, and where the
    parent's own fit puts them (the joint stays a joint)."""
    pts = _sub(np.asarray(zan[child]["v"], np.float64), 5000, 24)
    d = cKDTree(np.asarray(zan[parent]["v"], np.float64)).query(pts)[0]
    sel = d <= JOINT_MM
    if sel.sum() < 20:
        sel = np.zeros(len(pts), bool); sel[np.argsort(d)[:20]] = True
    A, t = piece_transform(fits, parent)
    return np.repeat(pts[sel], reps, axis=0), np.repeat(apply_sim(A, t, pts[sel]), reps, axis=0)


def body_scale(fits: dict) -> float:
    """Median similarity scale of her well-fitted, uncut reference bones (her size vs Z-Anatomy's)."""
    sc = [fr["scale"] for u, fr in fits.items() if u in BODY_SCALE_UNITS and fr.get("status") == "fitted"
          and not fr["truncated"] and fr["residual_mm"] < 3.0]
    return float(np.median(sc)) if sc else 1.0


def fit_units(zan: dict, her: dict, units: dict = UNITS, log=print) -> dict:
    """One similarity per paired bone unit. zan: {mesh_id: {'v','f'}}; her: {atlas_id: {'v','f'}}.
    Reference bones first (-> her body scale); FOV-cut bones and proxies are fitted rigidly at that
    scale; a unit whose free scale leaves [1-SCALE_TOL, 1+SCALE_TOL] x the body scale (a curled
    hand, a label that is not the whole bone) is refitted rigidly at the body scale and flagged."""
    fits: dict = {}
    order = sorted(units, key=lambda u: (u not in BODY_SCALE_UNITS, u))
    bs = None
    for unit in order:
        if bs is None and unit not in BODY_SCALE_UNITS:
            bs = body_scale(fits)
            log(f"  body scale (median of reference bones) {bs:.3f}")
        pieces = [z for z in units[unit] if z in zan]
        if unit not in her or unit in HER_FRAGMENTS or not pieces:
            fits[unit] = {"status": "unpaired", "her": unit in her, "zan_pieces": len(pieces)}
            continue
        src_v, src_f = _concat(zan, pieces)
        ratio = long_extent(her[unit]["v"]) / (long_extent(src_v) * (bs or 1.0))
        cut = bs is not None and ratio < CUT_RATIO and len(pieces) == 1
        anchors = None
        if cut and unit in JOINT_PARENT and fits.get(JOINT_PARENT[unit], {}).get("status") == "fitted":
            anchors = joint_anchors(zan, pieces[0], JOINT_PARENT[unit], fits)
        fixed = bs if cut else None
        if unit in LENGTH_SCALED and not cut and len(pieces) == 1:
            fixed = long_extent(her[unit]["v"]) / long_extent(src_v)
        fr = fit_pair(src_v, src_f, her[unit]["v"], unit, fixed_scale=fixed, partial=cut, anchors=anchors, log=log)
        fr["her_length_ratio"] = round(float(ratio), 3)
        if fixed is not None and not cut:
            fr["length_scaled"] = True
        if anchors is not None:
            fr["joint_anchor"] = JOINT_PARENT[unit]
        if bs is not None and not cut and fixed is None and abs(fr["scale"] / bs - 1) > SCALE_TOL:
            free = {"scale": round(fr["scale"], 3), "residual_mm": round(fr["residual_mm"], 2)}
            fr = {**fit_pair(src_v, src_f, her[unit]["v"], unit, fixed_scale=bs, log=log),
                  "scale_clamped": True, "free_fit": free}
        fr["pieces"] = pieces
        fits[unit] = fr
        log(f"  {unit:24s} {fr['method']:14s} res {fr['residual_mm']:6.2f} mm  scale {fr['scale']:.3f}"
            + ("  (clamped)" if fr.get("scale_clamped") else "") + ("  (FOV-cut)" if cut else ""))
        if unit in REFINE_PIECES and len(pieces) > 1:
            fr["piece_fits"] = refine_pieces(zan, pieces, fr["A"], fr["t"], her[unit]["v"], log=log)
    chain_rep = refine_chains(zan, fits, her, log=log)
    moved = [c for c, r in chain_rep.items() if r["start"] != "unchanged"]
    log(f"  chain refinement: {len(moved)}/{len(chain_rep)} pieces re-fitted; median anchor gap "
        f"{np.median([r['anchor_gap_before_mm'] for r in chain_rep.values()]):.1f} -> "
        f"{np.median([r['anchor_gap_after_mm'] for r in chain_rep.values()]):.1f} mm, median residual "
        f"{np.median([r['residual_before_mm'] for r in chain_rep.values()]):.1f} -> "
        f"{np.median([r['residual_after_mm'] for r in chain_rep.values()]):.1f} mm")
    # proxies: bones she has no CT for, fitted through her own soft tissue around them, with the
    # joint to the neighbouring fitted bone as anchor pairs
    for proxy, spec in PROXY_UNITS.items():
        zids = [z for z in spec["zan"] if z in zan]
        hids = [h for h in spec["her"] if h in her]
        anc_fit = fits.get(spec["anchor_bone"], {})
        if not zids or not hids or anc_fit.get("status") != "fitted":
            fits[proxy] = {"status": "unpaired", "her": bool(hids), "zan_pieces": len(zids)}
            continue
        src_v, src_f = _concat(zan, zids)
        dst_v = np.vstack([her[h]["v"] for h in hids])
        hv = np.asarray(zan[spec["anchor_bone"]]["v"], np.float64)
        P = _sub(hv[hv[:, 1] <= hv[:, 1].min() + spec["anchor_band_mm"]], 400, 18)
        anchors = (np.repeat(P, 4, axis=0), np.repeat(apply_sim(anc_fit["A"], anc_fit["t"], P), 4, axis=0))
        fr = fit_pair(src_v, src_f, dst_v, proxy, fixed_scale=bs, partial=True, anchors=anchors, log=log)
        fits[proxy] = {**fr, "pieces": [p for p in spec["drives"] if p in zan], "proxy_of": spec["why"],
                       "fitted_to_her": hids, "fitted_from_zan": zids, "anchor_bone": spec["anchor_bone"]}
        log(f"  {proxy:24s} {fr['method']:14s} res {fr['residual_mm']:6.2f} mm  scale {fr['scale']:.3f} "
            f"(proxy; elbow anchor gap {fr['anchor_gap_mm']:.1f} mm)")
    return fits


def refine_pieces(zan: dict, pieces: list[str], A: np.ndarray, t: np.ndarray, dst_v: np.ndarray, log=print) -> dict:
    """Rigid ICP of each piece against the part of her composite within 10 mm of where the
    composite fit already put it; kept only if it improves that piece's own residual and moves
    less than PIECE_MAX_MOVE_MM / PIECE_MAX_ROT_DEG."""
    tree_all = cKDTree(dst_v)
    out = {}
    for p in pieces:
        pts = sample_surface(zan[p]["v"], zan[p]["f"], max(len(zan[p]["v"]), 3000))
        cur = apply_sim(A, t, pts)
        idx = sorted(set(i for lst in tree_all.query_ball_point(_sub(cur, 1500, 4), 10.0) for i in lst))
        rec = {"A": A, "t": t, "refined": False}
        if len(idx) < 50:
            out[p] = rec
            continue
        local = dst_v[idx]
        base = float(np.median(cKDTree(local).query(cur)[0]))
        A2, t2 = trimmed_icp(_sub(pts, 2000, 5), _sub(local, 4000, 6), A, t, scale=False, corr="src",
                             iters=30, trim=0.7)
        new = apply_sim(A2, t2, pts)
        res2 = float(np.median(tree_all.query(new)[0]))
        res1 = float(np.median(tree_all.query(cur)[0]))
        move = float(np.linalg.norm(new.mean(0) - cur.mean(0)))
        rot = rot_angle_deg((A2 / sim_scale(A2)) @ (A / sim_scale(A)).T)
        ok = res2 < res1 and move <= PIECE_MAX_MOVE_MM and rot <= PIECE_MAX_ROT_DEG
        if ok:
            rec = {"A": A2, "t": t2, "refined": True}
        rec.update({"residual_before_mm": round(res1, 2), "residual_after_mm": round(res2 if ok else res1, 2),
                    "move_mm": round(move, 2), "rot_deg": round(rot, 1), "local_base_mm": round(base, 2)})
        out[p] = rec
    return out


def build_chains() -> list[tuple[str, list[str], str]]:
    """(child piece, parent pieces, her composite unit of the child), proximal -> distal: each
    finger/toe from its own metacarpal/metatarsal, each rib from the vertebrae it articulates with."""
    out = []
    for s in "rl":
        mc = {k: f"zan_{o}_metacarpal_bone_{s}" for k, o in enumerate(_ORD[:5], 1)}
        cb = {c: f"zan_{c}_bone_{s}" for c in CARPALS}
        # carpus: distal row from its own (well-fitted, individually labelled) metacarpals, then the
        # proximal row from the distal row (her FOV-cut radius is not a reliable wrist anchor)
        for c, par in (("trapezium", [mc[1], mc[2]]), ("trapezoid", [mc[2]]), ("capitate", [mc[3]]),
                       ("hamate", [mc[4], mc[5]]), ("scaphoid", [cb["trapezium"], cb["capitate"]]),
                       ("lunate", [cb["capitate"]]), ("triquetrum", [cb["hamate"], cb["lunate"]]),
                       ("pisiform", [cb["triquetrum"]])):
            out.append((cb[c], par, f"carpals_{s}"))
        for k, o in enumerate(_ORD[:5], 1):
            for where, base, unit in (("hand", f"zan_{o}_metacarpal_bone_{s}", f"phalanges_hand_{s}"),
                                      ("foot", f"zan_{o}_metatarsal_bone_{s}", f"phalanges_foot_{s}")):
                prev = base
                for p in ("proximal", "middle", "distal"):
                    if p == "middle" and o == "first":
                        continue
                    child = f"zan_{p}_phalanx_of_{o}_finger_of_{where}_{s}"
                    out.append((child, [prev], unit))
                    prev = child
        for k, o in enumerate(_ORD, 1):
            par = [f"zan_vertebra_t{k}"] + ([f"zan_vertebra_t{k - 1}"] if k > 1 else [])
            out.append((f"zan_{o}_rib_{s}", par, f"ribs_{s}"))
    return out


CHAINS = build_chains()
JOINT_MM = 6.0             # child points this close to a parent (Z-Anatomy frame) form the joint anchor
CHAIN_ANGLES = (-60.0, -30.0, 30.0, 60.0)


def piece_transform(fits: dict, piece: str):
    for fr in fits.values():
        if fr.get("status") == "fitted" and piece in fr.get("pieces", []):
            pf = fr.get("piece_fits", {}).get(piece)
            return (pf["A"], pf["t"]) if pf else (fr["A"], fr["t"])
    return None


def _rot(axis, deg):
    from scripts.transfer.limb_per_bone_transfer import _rotate_about_axis
    return _rotate_about_axis(np.asarray(axis, float), np.radians(deg))


def refine_chains(zan: dict, fits: dict, her: dict, chains=CHAINS, log=print) -> dict:
    """Joint-anchored refinement of each chain piece (finger/toe phalanx, rib): its joint surface
    (points within JOINT_MM of its parent in Z-Anatomy) is anchored where the parent's own fit puts
    it, and the piece is rigidly ICP'd (its unit's scale) onto the nearby part of her composite from
    several starts (its current fit, the parent's fit, the parent's fit flexed +-30/60 deg about the
    joint). Kept only if residual + 0.5 x anchor gap improves. Returns a per-piece report."""
    trees: dict = {}
    report = {}
    for child, parents, unit in chains:
        fr = fits.get(unit, {})
        if fr.get("status") != "fitted" or child not in fr.get("pieces", []) or child not in zan:
            continue
        cur = piece_transform(fits, child)
        par_tf = [(p, piece_transform(fits, p)) for p in parents if p in zan]
        par_tf = [(p, tf) for p, tf in par_tf if tf is not None]
        if not par_tf:
            continue
        if unit not in trees:
            trees[unit] = (her[unit]["v"], cKDTree(her[unit]["v"]))
        hv, htree = trees[unit]
        pts = sample_surface(zan[child]["v"], zan[child]["f"], max(len(zan[child]["v"]), 2000))
        pts = _sub(pts, 2500, 20)
        a_src, a_dst = [], []
        for p, (Ap, tp) in par_tf:
            d = cKDTree(np.asarray(zan[p]["v"], np.float64)).query(pts)[0]
            sel = d <= JOINT_MM
            if sel.sum() < 20:
                sel = np.zeros(len(pts), bool); sel[np.argsort(d)[:20]] = True
            a_src.append(pts[sel]); a_dst.append(apply_sim(Ap, tp, pts[sel]))
        a_src, a_dst = np.vstack(a_src), np.vstack(a_dst)
        reps = max(1, int(0.25 * len(pts) / len(a_src)))
        anchors = (np.repeat(a_src, reps, axis=0), np.repeat(a_dst, reps, axis=0))
        sc = sim_scale(fr["A"])

        def score(A, t):
            res = float(np.median(htree.query(apply_sim(A, t, pts))[0]))
            gap = float(np.median(np.linalg.norm(apply_sim(A, t, a_src) - a_dst, axis=1)))
            return res + 0.5 * gap, res, gap

        Ap, tp = par_tf[0][1]
        Ap = sc * Ap / sim_scale(Ap)
        tp = a_dst.mean(0) - Ap @ a_src.mean(0)        # parent rotation, joint on the anchor
        c0 = a_dst.mean(0)
        inits = {"current": cur, "parent": (Ap, tp)}
        for ax_name, ax in (("x", (1, 0, 0)), ("y", (0, 1, 0)), ("z", (0, 0, 1))):
            for ang in CHAIN_ANGLES:
                Rk = _rot(ax, ang)
                inits[f"parent_{ax_name}{ang:+.0f}"] = (Rk @ Ap, Rk @ (tp - c0) + c0)
        best_k, best = "unchanged", (cur, score(*cur))
        for k, (A0, t0) in inits.items():
            placed = apply_sim(A0, t0, pts)
            idx = np.unique(np.concatenate([np.asarray(i, int) for i in htree.query_ball_point(
                _sub(placed, 600, 21), 20.0)] + [np.zeros(0, int)]))
            if len(idx) < 50:
                continue
            A1, t1 = trimmed_icp(pts, _sub(hv[idx], 4000, 22), A0, t0, scale=False, corr="src", iters=25,
                                 trim=0.7, anchors=anchors)
            sc1 = score(A1, t1)
            if sc1[0] < best[1][0]:
                best_k, best = k, ((A1, t1), sc1)
        s_cur = score(*cur)
        rec = {"parents": [p for p, _ in par_tf], "start": best_k,
               "residual_before_mm": round(s_cur[1], 2), "anchor_gap_before_mm": round(s_cur[2], 2),
               "residual_after_mm": round(best[1][1], 2), "anchor_gap_after_mm": round(best[1][2], 2)}
        if best_k != "unchanged":
            (A1, t1) = best[0]
            fr.setdefault("piece_fits", {})[child] = {**fr.get("piece_fits", {}).get(child, {}),
                                                     "A": A1, "t": t1, "refined": True, "chain": rec}
        report[child] = rec
    return report


# ---------------------------------------------------------------- the transform
def spatial_clusters(v: np.ndarray, link_mm: float = 25.0, n_sub: int = 1500):
    """Label each vertex by the connected cluster (points linked within link_mm) it belongs to,
    computed on a subsample. Returns (labels, n_clusters)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    v = np.asarray(v, np.float64)
    if len(v) == 0 or np.linalg.norm(np.ptp(v, axis=0)) < 4 * link_mm:   # too small to span two limbs
        return np.zeros(len(v), int), 1
    sub = _sub(v, n_sub, 19)
    pairs = cKDTree(sub).query_pairs(link_mm, output_type="ndarray")
    pairs = pairs.reshape(-1, 2)
    g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(sub), len(sub)))
    n, lab = connected_components(g, directed=False)
    if n == 1:
        return np.zeros(len(v), int), 1
    return lab[cKDTree(sub).query(v)[1]], int(n)


class ZanToVhf:
    """transform(mesh_id, cat, v) -> v in her atlas frame. Built from the per-unit fits + the
    Z-Anatomy bone geometry (for the distance field)."""

    def __init__(self, fits: dict, zan_bones: dict):
        self.fits = fits
        self.piece_map: dict = {}         # zan mesh id -> (A, t)
        self.unit_names: list[str] = []
        self.unit_A, self.unit_t, self.unit_pts = [], [], []
        for unit, fr in sorted(fits.items()):
            if fr.get("status") != "fitted":
                continue
            for p in fr["pieces"]:
                pf = fr.get("piece_fits", {}).get(p)
                A, t = (pf["A"], pf["t"]) if pf else (fr["A"], fr["t"])
                self.piece_map[p] = (np.asarray(A), np.asarray(t))
                if p not in zan_bones:
                    continue
                self.unit_names.append(f"{unit}/{p}" if len(fr["pieces"]) > 1 else unit)
                self.unit_A.append(np.asarray(A)); self.unit_t.append(np.asarray(t))
                self.unit_pts.append(_sub(zan_bones[p], max(400, UNIT_CLOUD // max(1, len(fr["pieces"]) // 2)), 7))
        for f_id, unit in {**FOLLOWERS, **PROXY_FOLLOWERS}.items():
            fr = fits.get(unit, {})
            if fr.get("status") == "fitted":
                self.piece_map[f_id] = (np.asarray(fr["A"]), np.asarray(fr["t"]))
        self.unit_base = [n.split("/")[0] for n in self.unit_names]
        self.trees = [cKDTree(p) for p in self.unit_pts]
        self.lo = np.array([p.min(0) for p in self.unit_pts]); self.hi = np.array([p.max(0) for p in self.unit_pts])
        lab = np.concatenate([np.full(len(p), i) for i, p in enumerate(self.unit_pts)])
        self.all_tree, self.all_lab = cKDTree(np.vstack(self.unit_pts)), lab
        self._class_trees: dict = {}

    def limb_class(self, v: np.ndarray) -> str:
        _, j = self.all_tree.query(_sub(v, 2000, 8))
        groups = [unit_group(self.unit_base[i]) for i in self.all_lab[j]]
        vals, cnt = np.unique(groups, return_counts=True)
        return str(vals[np.argmax(cnt)])

    def _allowed(self, cls: str):
        if cls not in self._class_trees:
            idx = [i for i, b in enumerate(self.unit_base) if b in set(allowed_units(cls, [b]))]
            pts = np.vstack([self.unit_pts[i] for i in idx])
            self._class_trees[cls] = (np.array(idx), cKDTree(pts))
        return self._class_trees[cls]

    def blend(self, v: np.ndarray, cls: str) -> np.ndarray:
        v = np.asarray(v, np.float64)
        idx, ctree = self._allowed(cls)
        dmin = ctree.query(v)[0]
        reach = dmin + BLEND_CUTOFF_MM
        vlo, vhi = v.min(0), v.max(0)
        box_gap = np.linalg.norm(np.maximum(0, np.maximum(self.lo[idx] - vhi, vlo - self.hi[idx])), axis=1)
        idx = idx[box_gap <= reach.max()]
        D = np.full((len(v), len(idx)), np.inf)
        for k, i in enumerate(idx):
            gap = np.linalg.norm(np.maximum(0, np.maximum(self.lo[i] - v, v - self.hi[i])), axis=1)
            sel = gap <= reach
            if sel.any():
                D[sel, k] = self.trees[i].query(v[sel])[0]
        W = smooth_idw_weights(D)
        out = np.zeros_like(v)
        for k, i in enumerate(idx):
            sel = W[:, k] > 0
            if sel.any():
                out[sel] += W[sel, k:k + 1] * apply_sim(self.unit_A[i], self.unit_t[i], v[sel])
        return out

    def map_points(self, mesh_id: str, v: np.ndarray, pts: np.ndarray | None = None) -> np.ndarray:
        """Carry `pts` (default: v itself) the way mesh `mesh_id` with vertices v is carried. A mesh
        made of spatially separate pieces (Z-Anatomy merges e.g. the hand's AND foot's opponens digiti
        minimi into one object) gets its limb class per piece (clusters linked within CLUSTER_LINK_MM)."""
        v = np.asarray(v, np.float64)
        pts = v if pts is None else np.asarray(pts, np.float64)
        if mesh_id in self.piece_map:
            return apply_sim(*self.piece_map[mesh_id], pts)
        lab_v, n = spatial_clusters(v)
        if n == 1:
            return self.blend(pts, self.limb_class(v))
        lab_p = lab_v if pts is v else lab_v[cKDTree(v).query(pts)[1]]
        out = np.empty_like(pts)
        for c in range(n):
            sel = lab_p == c
            if sel.any():
                out[sel] = self.blend(pts[sel], self.limb_class(v[lab_v == c]))
        return out

    def __call__(self, mesh_id: str, cat: str, v: np.ndarray) -> np.ndarray:
        return self.map_points(mesh_id, v)


def fits_to_json(fits: dict) -> dict:
    def conv(x):
        if isinstance(x, np.ndarray):
            return np.round(x, 6).tolist()
        if isinstance(x, dict):
            return {k: conv(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [conv(v) for v in x]
        if isinstance(x, (np.floating, float)):
            return round(float(x), 4)
        return x
    return conv(fits)


def fits_from_json(d: dict) -> dict:
    out = {}
    for unit, fr in d.items():
        fr = dict(fr)
        if fr.get("status") == "fitted":
            fr["A"], fr["t"] = np.array(fr["A"]), np.array(fr["t"])
            fr["piece_fits"] = {p: {**pf, "A": np.array(pf["A"]), "t": np.array(pf["t"])}
                                for p, pf in fr.get("piece_fits", {}).items()}
        out[unit] = fr
    return out


def load_zan_to_vhf(zan_meshes: dict | None = None, report_path: Path = DEFAULT_REPORT) -> ZanToVhf:
    """The Q168 transform, from the committed per-bone fits in `report_path`.
    zan_meshes: optional {mesh_id: v (build frame)} holding at least the Z-Anatomy bones (e.g. the
    caller's own collected meshes); if omitted, the bones are collected from Z-Anatomy here."""
    rep = json.loads(Path(report_path).read_text())
    fits = fits_from_json(rep["bone_fits"])
    need = {p for fr in fits.values() if fr.get("status") == "fitted" for p in fr["pieces"]}
    if zan_meshes is None:
        zan_bones = {it["mesh_id"]: it["v"] for it in collect_zan(ids=need)}
    else:
        zan_bones = {k: (v["v"] if isinstance(v, dict) else v) for k, v in zan_meshes.items() if k in need}
    return ZanToVhf(fits, zan_bones)


# ---------------------------------------------------------------- validation
def region_tree(zan: dict):
    """(tree, labels) over every Z-Anatomy bone piece named in UNITS (paired with her or not):
    a structure's region is that of the Z-Anatomy bone nearest to most of its vertices."""
    pts, lab = [], []
    for unit, zids in UNITS.items():
        r = region_of_unit(unit)
        for z in zids:
            if z in zan:
                p = _sub(zan[z]["v"], 600, 16)
                pts.append(p); lab += [r] * len(p)
    return cKDTree(np.vstack(pts)), np.array(lab)


def structure_region(v: np.ndarray, rtree) -> str:
    tree, lab = rtree
    vals, cnt = np.unique(lab[tree.query(_sub(v, 1500, 17))[1]], return_counts=True)
    return str(vals[np.argmax(cnt)])


def validate(items: list[dict], her: dict, xf: "ZanToVhf", rtree) -> dict:
    """Per shared id (her OWN mesh): centroid distance, symmetric median surface distance and the
    one-sided her->Z-Anatomy median (fair when her mesh is FOV-cut), transferred vs raw."""
    fit_targets = {h for fr in xf.fits.values() for h in fr.get("fitted_to_her", [])}
    rows = {}
    for it in items:
        mid = it["mesh_id"]
        if mid not in her or mid in HER_FRAGMENTS or mid in MALE_ONLY_IDS:
            continue
        if "generated" in her[mid].get("source_file", ""):   # e.g. her cylinder discs: not segmented
            continue
        hv = her[mid]["v"]
        hs = _sub(hv, 20000, 10)
        th = cKDTree(hs)
        zs = sample_surface(it["v"], it["f"], max(len(it["v"]), 8000))
        new_v = xf(mid, it["cat"], it["v"])
        new_s = xf.map_points(mid, it["v"], zs)
        sd, sd0 = surface_distance(new_s, hs, tree_b=th), surface_distance(zs, hs, tree_b=th)
        diag_her = float(np.linalg.norm(np.ptp(hv, axis=0)))
        diag_zan = float(np.linalg.norm(np.ptp(new_v, axis=0)))
        rows[mid] = {"cat": it["cat"], "region": structure_region(np.asarray(it["v"]), rtree),
                     "her_subject": her[mid]["subject"],
                     "centroid_mm": float(np.linalg.norm(new_v.mean(0) - hv.mean(0))),
                     "surface_mm": sd["sym"], "her_to_zan_mm": sd["b_to_a"],
                     "raw_centroid_mm": float(np.linalg.norm(np.asarray(it["v"]).mean(0) - hv.mean(0))),
                     "raw_surface_mm": sd0["sym"], "raw_her_to_zan_mm": sd0["b_to_a"],
                     "her_extent_ratio": diag_her / max(diag_zan, 1e-6),
                     "fit_target": mid in fit_targets}
    return rows


def summarise_rows(rows: dict, keys=("centroid_mm", "surface_mm", "her_to_zan_mm", "raw_centroid_mm",
                                     "raw_surface_mm", "raw_her_to_zan_mm")) -> dict:
    """Region / whole-body median+max; fit targets (proxy) are excluded and reported apart."""
    fit_t = {i for i, x in rows.items() if x.get("fit_target")}
    rows_all, rows = rows, {i: x for i, x in rows.items() if i not in fit_t}
    def stats(sel):
        if not sel:
            return {"n": 0}
        out = {"n": len(sel)}
        for k in keys:
            a = np.array([rows[i][k] for i in sel])
            out[k] = {"median": round(float(np.median(a)), 1), "max": round(float(a.max()), 1)}
        return out
    res = {r: stats([i for i, x in rows.items() if x["region"] == r]) for r in REGIONS}
    res["whole_body"] = stats(list(rows))
    res["whole_body_soft_tissue"] = stats([i for i, x in rows.items() if x["cat"] != "bone"])
    res["whole_body_bones"] = stats([i for i, x in rows.items() if x["cat"] == "bone"])
    res["whole_body_her_mesh_complete"] = stats([i for i, x in rows.items() if x["her_extent_ratio"] >= 0.7])
    rows = rows_all
    res["proxy_fit_targets_not_independent"] = stats(sorted(fit_t))
    return res


def continuity(items: list[dict], out_v: dict, n_sample: int = 400_000, touch_mm: float = 1.0) -> dict:
    """Edge stretch (per mesh, normalised by its own median) and cross-structure tearing: vertices
    of DIFFERENT structures within `touch_mm` before -> their separation after."""
    worst, allr = [], []
    for it in items:
        if it["mesh_id"] not in out_v or len(it["f"]) == 0:
            continue
        r = edge_stretch(np.asarray(it["v"], np.float64), out_v[it["mesh_id"]], it["f"])
        allr.append(r)
        worst.append((float(r.max()), float(1 / max(r.min(), 1e-9)), it["mesh_id"]))
    allr = np.concatenate(allr)
    worst.sort(reverse=True)
    V0 = np.vstack([np.asarray(it["v"], np.float64) for it in items if it["mesh_id"] in out_v])
    V1 = np.vstack([out_v[it["mesh_id"]] for it in items if it["mesh_id"] in out_v])
    L = np.concatenate([np.full(len(it["v"]), k) for k, it in enumerate(items) if it["mesh_id"] in out_v])
    sel = np.random.default_rng(11).choice(len(V0), min(n_sample, len(V0)), replace=False)
    tree = cKDTree(V0)
    d, j = tree.query(V0[sel], k=8)
    other = (L[j] != L[sel][:, None]) & (d <= touch_mm)
    first = np.argmax(other, axis=1)
    has = other.any(axis=1)
    a, b = sel[has], j[has, first[has]]
    sep_before = np.linalg.norm(V0[a] - V0[b], axis=1)
    sep_after = np.linalg.norm(V1[a] - V1[b], axis=1)
    growth = sep_after - sep_before
    ids = [it["mesh_id"] for it in items if it["mesh_id"] in out_v]
    worst_pairs = {}
    for k in np.argsort(-growth)[:400]:
        key = tuple(sorted((ids[L[a[k]]], ids[L[b[k]]])))
        worst_pairs.setdefault(key, round(float(growth[k]), 1))
    return {"edge_stretch_max": round(float(allr.max()), 2), "edge_stretch_p999": round(float(np.quantile(allr, 0.999)), 3),
            "edge_compress_max": round(float(1 / allr.min()), 2),
            "edge_compress_p999": round(float(1 / np.quantile(allr, 0.001)), 3),
            "worst_meshes": [{"id": w[2], "stretch_max": round(w[0], 2), "compress_max": round(w[1], 2)} for w in worst[:8]],
            "touching_pairs_checked": int(has.sum()),
            "tear_max_mm": round(float(growth.max()), 2) if len(growth) else 0.0,
            "tear_p99_mm": round(float(np.quantile(growth, 0.99)), 2) if len(growth) else 0.0,
            "tear_median_mm": round(float(np.median(growth)), 3) if len(growth) else 0.0,
            "tear_worst_pairs": [{"a": k[0], "b": k[1], "mm": v} for k, v in list(worst_pairs.items())[:10]]}


def render_check(her: dict, out_v: dict, items: list[dict], path: Path, muscles=(
        "biceps_brachii_r", "rectus_femoris_r", "gastrocnemius_r", "sternocleidomastoid_r", "gluteus_maximus_r",
        "rectus_abdominis_r", "deltoid_r", "tibialis_anterior_l")) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cat = {it["mesh_id"]: it["cat"] for it in items}
    hb = np.vstack([_sub(m["v"], 3000, 12) for k, m in her.items() if m.get("cat") == "bone" and k not in HER_FRAGMENTS])
    zb = np.vstack([_sub(v, 800, 13) for k, v in out_v.items() if cat.get(k) == "bone"])
    fig, axs = plt.subplots(1, 2, figsize=(12, 13))
    cols = plt.cm.tab10(np.linspace(0, 1, len(muscles)))
    for ax, (ix, lab) in zip(axs, ((0, "front (x right)"), (2, "side (z anterior)"))):
        ax.scatter(hb[:, ix], hb[:, 1], s=0.3, c="0.6", label="her CT bones")
        ax.scatter(zb[:, ix], zb[:, 1], s=0.3, c="tab:red", alpha=0.35, label="Z-Anatomy bones, transferred")
        for m, c in zip(muscles, cols):
            if m in out_v:
                p = _sub(out_v[m], 600, 14)
                ax.scatter(p[:, ix], p[:, 1], s=0.6, color=c, label=f"{m} (Z-Anatomy)")
            if m in her:
                p = _sub(her[m]["v"], 600, 15)
                ax.scatter(p[:, ix], p[:, 1], s=0.6, color=c, marker="x", alpha=0.4)
        ax.set_aspect("equal"); ax.set_title(lab); ax.set_xlabel("mm"); ax.set_ylabel("y (mm, up)")
    axs[0].legend(loc="lower left", fontsize=7, markerscale=8)
    fig.suptitle("Q168 Z-Anatomy -> VH female: grey = her bones, red = transferred bones; "
                 "dots = transferred muscles, x = her own muscle")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return str(path)


SOURCE = ("Q168 (2026-09-29): derived by scripts/transfer/zan_to_vhf_whole_body.py. Geometry: Z-Anatomy "
          "(CC BY-SA 4.0, https://github.com/LluisV/Z-Anatomy, pinned commit in "
          "scripts/zanatomy/build_zan_atlas_viewer.py; one male body from BodyParts3D, DBCLS CC BY-SA 2.1 JP) "
          "and the U.S. National Library of Medicine Visible Human Project FEMALE (public domain) -- her own "
          "CT/cryosection segmentations under build/vh/ct_vhf_* (never xfer_*). Per-bone similarity (Q147 "
          "bone_frame + twist + ICP, and a centroid start, both refined by trimmed symmetric ICP / Umeyama "
          "1991 doi:10.1109/34.88573); soft tissue by a tapered inverse-square blend of nearby bones.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", default=str(DEFAULT_REPORT))
    ap.add_argument("--png", default=None, help="quick-check render (default: no render)")
    ap.add_argument("--items-cache", default=None, help="pickle of collect_zan() output (speeds reruns)")
    ap.add_argument("--joint-anchors", action="store_true",
                    help="anchor FOV-cut radius/ulna at the elbow to the humerus fit (comparison run; worse)")
    a = ap.parse_args(argv)
    t0 = time.time()
    if a.items_cache and Path(a.items_cache).exists():
        import pickle
        items = pickle.loads(Path(a.items_cache).read_bytes())
    else:
        items = collect_zan()
        if a.items_cache:
            import pickle
            Path(a.items_cache).write_bytes(pickle.dumps(items, protocol=4))
    print(f"collected {len(items)} Z-Anatomy meshes ({time.time() - t0:.0f} s)")
    her = load_her_meshes()
    print(f"her own meshes: {len(her)}")
    zan = {it["mesh_id"]: it for it in items}
    if a.joint_anchors:
        JOINT_PARENT.update(JOINT_PARENT_OPTION)
    fits = fit_units(zan, her)
    xf = ZanToVhf(fits, {k: zan[k]["v"] for k in zan})
    keep = [it for it in items if it["mesh_id"] not in MALE_ONLY_IDS]
    t1 = time.time()
    out_v = {it["mesh_id"]: xf(it["mesh_id"], it["cat"], it["v"]) for it in keep}
    t_xf = time.time() - t1
    print(f"transformed {len(out_v)} meshes ({sum(len(v) for v in out_v.values())} vertices) in {t_xf:.1f} s")
    rtree = region_tree(zan)
    rows = validate(keep, her, xf, rtree)
    region_all = {it["mesh_id"]: structure_region(np.asarray(it["v"]), rtree) for it in keep}
    summ = summarise_rows(rows)
    cont = continuity(keep, out_v)
    png = render_check(her, out_v, keep, Path(a.png)) if a.png else None
    fitted = {u: fr for u, fr in fits.items() if fr.get("status") == "fitted"}
    res = np.array([fr["residual_mm"] for fr in fitted.values()])
    report = {
        "source": SOURCE,
        "frame": "input: Z-Anatomy build frame (atlas axes, mm, origin = Z-Anatomy hip-joint-centre midpoint); "
                 "output: her atlas frame (origin = her hip-joint-centre midpoint)",
        "method": {"soften_mm": SOFTEN_MM, "blend_power": BLEND_POWER, "blend_cutoff_mm": BLEND_CUTOFF_MM,
                   "piece_guard": {"max_move_mm": PIECE_MAX_MOVE_MM, "max_rot_deg": PIECE_MAX_ROT_DEG},
                   "limb_gate": "upper-limb structures never take lower-limb bones and vice versa; trunk "
                                "structures never take radius/ulna/hand bones"},
        "her_subjects": her_subject_order(),
        "bone_fit_summary": {"units_fitted": len(fitted), "residual_median_mm": round(float(np.median(res)), 2),
                             "residual_max_mm": round(float(res.max()), 2),
                             "over_5mm": sorted(u for u, fr in fitted.items() if fr["residual_mm"] > 5)},
        "unpaired_units": {u: fr for u, fr in fits.items() if fr.get("status") != "fitted"},
        "followers": FOLLOWERS,
        "her_fragments_not_used": sorted(HER_FRAGMENTS),
        "region_errors": summ,
        "continuity": cont,
        "runtime_s": {"transform_all": round(t_xf, 1), "meshes": len(out_v),
                      "vertices": int(sum(len(v) for v in out_v.values()))},
        "male_only_excluded": MALE_ONLY,
        "female_pelvic_organs": FEMALE_PELVIC_ORGANS,
        "png": png,
        "per_structure_centroid_mm": {k: round(r["centroid_mm"], 1) for k, r in sorted(rows.items())},
        "badge_note": "per_structure_centroid_mm is measured (her own mesh exists; centroid distance is inflated "
                      "where her mesh is FOV-cut -- see per_structure.her_extent_ratio < 0.7 and her_to_zan_mm); "
                      "every other structure: use its region_of_structure's region_errors median/max "
                      "(estimate, not measured on that structure)",
        "region_of_structure": dict(sorted(region_all.items())),
        "per_structure": {k: {kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in r.items()}
                          for k, r in sorted(rows.items())},
        "bone_fits": fits_to_json(fits),
    }
    Path(a.report).write_text(json.dumps(report, indent=1))
    print(json.dumps({"bone_fit_summary": report["bone_fit_summary"], "region_errors": summ, "continuity": cont,
                      "runtime_s": report["runtime_s"], "png": png}, indent=1))
    print(f"total {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
