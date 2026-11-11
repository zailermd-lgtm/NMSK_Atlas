#!/usr/bin/env python3
"""Q319: measure the owner's three words -- "slack, inconsistent, not matching" -- on every MUSCLE mesh of the
two Combined pages, so the decision to keep / repair / delete each one rests on numbers and not on an impression.

    python3 scripts/anatomy/q319/audit_reconstructed_muscles_q319.py                      # the current baseline
    python3 scripts/anatomy/q319/audit_reconstructed_muscles_q319.py --src build/q309
    python3 scripts/anatomy/q319/audit_reconstructed_muscles_q319.py \
        --page-dir comb_m=/some/dir --page-dir comb_f=/some/dir            # a directory holding index.html + its geo blobs

READ-ONLY. It decodes the SHIPPED geometry of a page (manifest + uint16 blob, `scripts/zanatomy/q202_pages.py`
format) and writes `data/derived/Q319_reconstructed_muscle_audit.json` plus a summary table on stdout. It changes
no mesh, no page and no other data file.

WHAT IS REUSED, NOT RE-DERIVED
  * provenance class per structure: `scripts/anatomy/q297/audit297.classify` (the Q297 provenance audit's own rule)
  * enclosed volume: `scripts/anatomy/q297/volumes297.enclosed_cm3`, copied verbatim (one line of numpy)
  * voxel solid / muscle-muscle overlap: `scripts/anatomy/q237/fill._vox` / `lattice_solid` / `_paste` /
    `overlap_pct`, copied verbatim in method (2 mm lattice, "as the Q204 audit") so the numbers here are
    comparable with the gates Q237 already records for the same pages
  * thresholds: the project's own, never invented here -- see THRESHOLDS below for where each one comes from

THE METRICS, AND WHICH OF THE OWNER'S THREE WORDS EACH ONE MEASURES
  "slack" (רופפים)      -- a belly that is too thin / too small for the muscle it claims to be:
      vol_ratio_lit   = shipped volume / the volume its own cited architecture record implies
                        (V = sum over compartments of PCSA * optimal fascicle length / cos(pennation);
                         the standard PCSA definition, Lieber & Friden 2000 -- DERIVED from
                         `data/muscles/**/*.json`, never a measured literature volume, and labelled so)
      acsa_ratio_lit  = (shipped volume / shipped belly length) / (sum of PCSA * cos(pennation))
                        -- catches a muscle drawn as a long thin strap whose total volume still looks plausible
  "inconsistent" (לא עקביים) -- the two sides of one body disagree, or the surface is not of one piece:
      lr_vol_ratio    = R/L volume of the pair; the project's own normal band is 0.80-1.25
      n_components / largest_component_frac, open_edge_frac, degenerate_tri_frac, mean_dihedral_deg
                        -- a mesh in several lumps, with boundary holes, or far off the dihedral band of a real
                        scan, is not one continuous belly
  "not matching / not fitting" (לא מתאימים, לא תואמים) -- it does not sit on this body:
      origin_gap_mm / insertion_gap_mm -- surface-to-surface distance from the muscle to the ORIGIN and the
                        INSERTION bone its own entity record names, measured on THIS page's own bones
      in_bone_pct / bone_deepest_mm    -- how much of it is buried inside bone
      overlap_muscle_pct               -- how much of its volume lies inside OTHER muscles

THRESHOLDS (every one is the project's own; none is invented here)
  lr_vol_ratio 0.80-1.25            docs: data/derived/Q241_pose_asymmetry.md section 2 ("the Q237 flags")
  origin/insertion gap 6 / 10 / 20  data/derived/Q198_anatomy_audit.json meta.thresholds.attachment_distance_mm
  in_bone_pct 8 / 20 / 40 (>3 mm)   Q198 meta.thresholds.inside_bone_pct_with_>3mm_depth; Q237 fill.BELLY_IN_BONE_MAX = 8
  bone_deepest_mm 5                 scripts/anatomy/q237/fill.BONE_DEPTH_MAX_MM ("Q204 counts > 5 mm as a defect")
  overlap_muscle_pct 40 / 60        Q198 meta.thresholds.muscle_overlap_pct; Q237 fill.OVERLAP_MAX = 60
  pieces vs the record             a mesh may be in as many pieces as its record names functional compartments
                                    (heads / fibre groups), plus one for a midline muscle Z-Anatomy ships as two
                                    mirror halves; more than that is unexplained. A piece whose centroid is more
                                    than 2x the largest piece's own diagonal away is in the wrong part of the body.
                                    (The 0.94 figure of docs/MUSCLE_GAPS.md -- the ECRL ship, "94.6 % in one
                                    component" -- is reported as largest_component_frac but no longer flagged on
                                    its own, because a two-headed muscle legitimately sits near 0.5.)
  mean_dihedral_deg 27.6-31.7       the CVH reference band quoted in docs/GEOMETRY_SOURCES.md
  vol_ratio_lit / acsa_ratio_lit    NO project threshold exists. Reported as a number only; the doc states the
                                    band it reads them against and says it is this round's assumption.

THE THREE BUCKETS are computed here, not transcribed (see BUCKET_RULE, severities(), classify()), and written
into every muscle record as `bucket` + `bucket_because` and into every page object as `bucket_counts`:
  defensible      no geometric check above severity 1
  repairable      one or more severity-2/3 geometric checks, but not two severity-3 ones
  not defensible  two or more independent severity-3 geometric checks; OR the mesh was generated here
                  (rule_based / mirror_fill) and fails even one severity-3 check, because then there is no real
                  source behind it to fall back on
Only the GEOMETRIC checks decide a bucket, because only they have a threshold the project already set. The
architecture ratios are carried in bucket_because.architecture_evidence and decide nothing. Every level is read
out of TH, so moving a threshold moves the buckets, and `bucket_because.checks` names each check that fired so a
reader never has to re-derive the verdict. There is deliberately only ONE copy of this rule in the file.
"""
from __future__ import annotations

import argparse
import base64
import collections
import glob
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q297"))

OUT = REPO / "data/derived/Q319_reconstructed_muscle_audit.json"

# page key -> (build subdirectory, html stem) -- the project's own convention (scripts/anatomy/q297/prov297.DIRS)
DIRS = {"comb_m": ("viewer_zan_vhm", "atlas_viewer_zan_male_fitted"),
        "comb_f": ("viewer_zan_female", "atlas_viewer_zan_female"),
        "base_m": ("viewer_zan_atlas", "atlas_viewer_zan_atlas"),
        "base_f": ("viewer_base_female", "atlas_viewer_base_female")}
LABEL = {"comb_m": "Combined M", "comb_f": "Combined F", "base_m": "Base M", "base_f": "Base F"}

# ---------------------------------------------------------------- thresholds, all of them the project's own
TH = {
    "lr_vol_ratio_ok": [0.80, 1.25],          # Q241_pose_asymmetry.md s2 (the Q237 flags)
    "attachment_mm": [6.0, 10.0, 20.0],       # Q198_anatomy_audit meta.thresholds.attachment_distance_mm
    "in_bone_pct": [8.0, 20.0, 40.0],         # Q198 inside_bone_pct_with_>3mm_depth / Q237 BELLY_IN_BONE_MAX
    "bone_deepest_mm": 5.0,                   # Q237 fill.BONE_DEPTH_MAX_MM
    "overlap_muscle_pct": [40.0, 60.0],       # Q198 muscle_overlap_pct / Q237 fill.OVERLAP_MAX
    "largest_component_frac": 0.94,           # docs/MUSCLE_GAPS.md, the ECRL ship
    "mean_dihedral_deg_ref": [27.6, 31.7],    # docs/GEOMETRY_SOURCES.md, the CVH references
    # How far OUTSIDE the lr_vol_ratio band counts as severity 2 / 3. Expressed as a factor on the band itself
    # (f = max(ratio / hi, lo / ratio); f <= 1 is inside the band), so moving the band moves these with it.
    "lr_outside_factor_sev2": 1.2,            # = 1.5 / 1.25, the ratio at which Q237 would not mirror-fill either way
    "lr_outside_factor_sev3": 4.0 / 3.0,      # = 1.667 / 1.25, a side half again the size of the other
    "spread_over_diag_sev3": 2.0,             # a piece further than 2x the largest piece's own diagonal
    "coarse_solid_voxels": 200,               # below this the 2 mm voxel share is too coarse to flag
}

# the three buckets, and the rule, in one place. Named here so the document and the JSON cannot drift.
BUCKET_RULE = {
    "defensible": "no geometric check above severity 1",
    "repairable": "one or more severity-2/3 geometric checks, but not two severity-3 ones",
    "not_defensible": ("two or more independent severity-3 geometric checks; OR the mesh was generated here "
                       "(rule_based / mirror_fill) and fails even one severity-3 check, because then there is no "
                       "real source behind it to fall back on"),
    "note": ("Only GEOMETRIC checks -- the ones with a threshold the project already set -- decide a bucket. The "
             "architecture ratios (vol_ratio_lit / acsa_ratio_lit) have no project threshold and are recorded as "
             "supporting evidence only, in bucket_because.architecture_evidence."),
}
GENERATED_HERE = ("rule_based", "mirror_fill")
PITCH = 2.0                                    # mm, the Q204 / Q237 lattice


# ================================================================= page reading (manifest + uint16 blob)
def read_page(page_dir: Path, stem: str | None):
    """-> manifest dict, blob bytes.  `stem` None means the artifact layout (index.html)."""
    html_name = "index.html" if stem is None else f"{stem}.html"
    html = (page_dir / html_name).read_text(encoding="utf-8", errors="replace")
    i = html.index("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    man, _ = json.JSONDecoder().raw_decode(html[i:])
    files = json.loads(re.search(r"window\.__ANATOMY_BIN_FILES__=(\[.*?\]);\s*window\.__ANATOMY_MANIFEST__=",
                                 html, re.S).group(1))
    blob = b"".join(base64.b64decode((page_dir / f["path"]).read_bytes()) for f in files)
    return man, blob


def decode_one(m, blob):
    """scripts/zanatomy/q202_pages.decode_one, verbatim."""
    q = np.frombuffer(blob, np.uint16, m["vc"] * 3, m["vo"]).reshape(-1, 3).astype(np.float64)
    f = np.frombuffer(blob, np.uint16, m["ic"] * 3, m["io"]).reshape(-1, 3).astype(np.int64)
    v = np.asarray(m["min"]) + q / 65535.0 * np.asarray(m["span"])
    return v, f


# ================================================================= mesh measures
def enclosed_cm3(v, f):
    """scripts/anatomy/q297/volumes297.enclosed_cm3, verbatim."""
    vv = v[f]
    return float(np.einsum("ij,ij->i", vv[:, 0], np.cross(vv[:, 1], vv[:, 2])).sum() / 6.0 / 1000.0)


def tri_area(v, f):
    vv = v[f]
    return 0.5 * np.linalg.norm(np.cross(vv[:, 1] - vv[:, 0], vv[:, 2] - vv[:, 0]), axis=1)


def area(v, f):
    return float(tri_area(v, f).sum())


def area_samples(v, f, n, rng):
    """uniform points on the surface, area-weighted (the method of scripts/anatomy/q237/core.area_samples)."""
    a = tri_area(v, f)
    s = a.sum()
    if s <= 0 or len(a) == 0:
        return v[:0]
    idx = rng.choice(len(a), size=int(n), p=a / s)
    u = rng.random((int(n), 1))
    w = rng.random((int(n), 1))
    bad = (u + w) > 1
    u[bad] = 1 - u[bad]
    w[bad] = 1 - w[bad]
    tv = v[f[idx]]
    return tv[:, 0] + u * (tv[:, 1] - tv[:, 0]) + w * (tv[:, 2] - tv[:, 0])


def _vox(v, f, lo, shape, pitch, cap):
    """scripts/anatomy/q237/fill._vox: shell from dense samples, sealed, exterior flood-filled, eroded back."""
    A = area(v, f)
    n = int(min(max(4.0 * A / pitch ** 2, 3000), cap))
    p = area_samples(v, f, n, np.random.default_rng(11))
    if len(p) == 0:
        z = np.zeros(shape, bool)
        return z, False, z
    ix = np.clip(np.floor((p - lo) / pitch).astype(int), 0, np.array(shape) - 1)
    sh = np.zeros(shape, bool)
    sh[ix[:, 0], ix[:, 1], ix[:, 2]] = True
    sd = ndi.binary_dilation(sh, iterations=1)
    lab, _ = ndi.label(~sd)
    sol = ndi.binary_erosion(lab != lab[0, 0, 0], iterations=1)
    return sol, bool(sol.sum() >= 8 and sol.sum() >= 0.35 * sh.sum()), sh


def lattice_solid(v, f, pitch=PITCH, cap=250000):
    """scripts/anatomy/q237/fill.lattice_solid: a lattice aligned to multiples of `pitch`, so grids line up."""
    lo = np.floor((v.min(0) - 4) / pitch).astype(int)
    hi = np.ceil((v.max(0) + 4) / pitch).astype(int)
    shape = tuple((hi - lo + 1).tolist())
    sol, ok, sh = _vox(v, f, lo * pitch, shape, pitch, cap)
    return lo, sol, ok, sh


def paste(canvas, lo_c, arr, lo_a):
    """scripts/anatomy/q237/fill._paste, verbatim."""
    a0 = np.maximum(lo_c, lo_a)
    a1 = np.minimum(lo_c + np.array(canvas.shape), lo_a + np.array(arr.shape))
    if (a1 <= a0).any():
        return
    c = tuple(slice(int(a0[i] - lo_c[i]), int(a1[i] - lo_c[i])) for i in range(3))
    r = tuple(slice(int(a0[i] - lo_a[i]), int(a1[i] - lo_a[i])) for i in range(3))
    canvas[c] |= arr[r]


def topology(v, f):
    """components over the triangle graph, boundary (once-used) edges, degenerate triangles, mean dihedral."""
    n = len(v)
    e = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    key = np.sort(e, axis=1)
    uk, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    open_edge_frac = float((cnt == 1).sum() / max(len(uk), 1))
    # vertex components, by welding on position (the blob is quantised, so equal positions share a lattice cell)
    q = np.round(v, 3)
    _, wid = np.unique(q, axis=0, return_inverse=True)
    parent = np.arange(len(_))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in wid[key]:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    roots = np.array([find(i) for i in range(len(_))])
    a = tri_area(v, f)
    lab = roots[wid[f[:, 0]]]
    tot = a.sum()
    sizes = collections.Counter()
    for l, ar in zip(lab, a):
        sizes[int(l)] += float(ar)
    largest = max(sizes.values()) / tot if tot > 0 else 0.0
    degen = float((a <= 1e-9).sum() / max(len(a), 1))
    # mean dihedral over manifold edges
    pair = np.where(cnt == 2)[0]
    mean_dih = None
    if len(pair):
        order = np.argsort(inv, kind="stable")
        tri_of = order % len(f)   # e was stacked as [f[:,01]; f[:,12]; f[:,20]], so row i belongs to triangle i % len(f)
        starts = np.searchsorted(inv[order], pair)
        t0 = tri_of[starts]
        t1 = tri_of[starts + 1]
        vv = v[f]
        nrm = np.cross(vv[:, 1] - vv[:, 0], vv[:, 2] - vv[:, 0])
        ln = np.linalg.norm(nrm, axis=1)
        good = (ln[t0] > 0) & (ln[t1] > 0)
        if good.any():
            n0 = nrm[t0[good]] / ln[t0[good]][:, None]
            n1 = nrm[t1[good]] / ln[t1[good]][:, None]
            ang = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", n0, n1), -1, 1)))
            mean_dih = float(ang.mean())
    # where the pieces are: a muscle with several HEADS has its pieces touching; a mesh that carries a lump from
    # somewhere else in the body has one far away. Measured as the spread of the component centroids against the
    # diagonal of the largest component, so the test does not depend on the muscle's absolute size.
    cents, diags = [], {}
    for l in sizes:
        k = lab == l
        cv = v[f[k]].reshape(-1, 3)
        cents.append(cv.mean(0))
        diags[int(l)] = float(np.linalg.norm(cv.max(0) - cv.min(0)))
    big = max(sizes, key=lambda x: sizes[x])
    spread = 0.0
    for i in range(len(cents)):
        for j in range(i + 1, len(cents)):
            spread = max(spread, float(np.linalg.norm(cents[i] - cents[j])))
    # two near-equal mirror halves of a MIDLINE muscle: same y/z centroid, opposite x
    mirror_halves = False
    if len(cents) == 2 and abs(sizes[list(sizes)[0]] - sizes[list(sizes)[1]]) / max(tot, 1e-9) < 0.05:
        d = cents[0] - cents[1]
        mirror_halves = bool(abs(d[0]) > 2 * max(abs(d[1]), abs(d[2])))
    return dict(n_components=len(sizes), largest_component_frac=round(float(largest), 4),
                component_centroid_spread_mm=round(spread, 1),
                largest_component_diag_mm=round(diags[int(big)], 1),
                spread_over_diag=(round(spread / diags[int(big)], 2) if diags[int(big)] > 0 else None),
                two_mirror_halves=mirror_halves,
                open_edge_frac=round(open_edge_frac, 5), degenerate_tri_frac=round(degen, 6),
                mean_dihedral_deg=(None if mean_dih is None else round(mean_dih, 2)))


def belly_length_mm(v):
    """extent along the mesh's own first principal axis -- the length a belly is 'long' along."""
    c = v - v.mean(0)
    try:
        w, V = np.linalg.eigh(c.T @ c)
    except np.linalg.LinAlgError:
        return float(np.ptp(v, axis=0).max())
    ax = V[:, int(np.argmax(w))]
    p = c @ ax
    return float(p.max() - p.min())


# ================================================================= the atlas records
def muscle_entities():
    out = {}
    for p in glob.glob(str(REPO / "data/muscles/**/*.json"), recursive=True):
        if p.endswith("muscle_index.json"):
            continue
        try:
            e = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(e, dict) and "id" in e:
            out[e["id"]] = e
    return out


def lit_architecture(e):
    """DERIVED, not measured: V = sum PCSA * Lf / cos(pennation) and ACSA = sum PCSA * cos(pennation),
    the standard PCSA definition applied to the muscle's OWN cited architecture record. Returns None when the
    record carries no PCSA / fascicle length (29 of 433 entities)."""
    vol = acsa = 0.0
    srcs, got = [], False
    for c in e.get("functional_compartments") or []:
        fa = c.get("fiber_architecture") or {}
        pcsa = fa.get("physiological_cross_section_area_mm2")
        lf = fa.get("optimal_fascicle_length_mm")
        pen = fa.get("pennation_deg")
        if not pcsa or not lf:
            continue
        cosp = math.cos(math.radians(float(pen or 0.0)))
        cosp = max(cosp, 0.3)
        vol += float(pcsa) * float(lf) / cosp
        acsa += float(pcsa) * cosp
        got = True
        if c.get("source"):
            srcs.append(c["source"])
    if not got:
        return None
    return dict(volume_cm3=round(vol / 1000.0, 3), acsa_mm2=round(acsa, 1),
                source=srcs[0][:300] if srcs else (e.get("source") or "")[:300])


# bone-group ids used by the entity records that are not single meshes on a Z page
GROUP_PAT = {
    "cervical_vertebrae": r"^(zan_vertebra_c\d|atlas|axis)$",
    "thoracic_vertebrae": r"^zan_vertebra_t\d+$",
    "lumbar_vertebrae": r"^zan_vertebra_l\d$",
    "ribs_l": r"^zan_\w+_rib_l$", "ribs_r": r"^zan_\w+_rib_r$",
    "carpals_l": r"^zan_(scaphoid|lunate|triquetrum|pisiform|trapezium|trapezoid|capitate|hamate)\w*_l$",
    "carpals_r": r"^zan_(scaphoid|lunate|triquetrum|pisiform|trapezium|trapezoid|capitate|hamate)\w*_r$",
    "metacarpals_l": r"^zan_\w+_metacarpal_bone_l$", "metacarpals_r": r"^zan_\w+_metacarpal_bone_r$",
    "metatarsals_l": r"^zan_\w+_metatarsal_bone_l$", "metatarsals_r": r"^zan_\w+_metatarsal_bone_r$",
    "phalanges_hand_l": r"^zan_\w+_phalanx_of_\w+_finger_of_hand_l$",
    "phalanges_hand_r": r"^zan_\w+_phalanx_of_\w+_finger_of_hand_r$",
    "phalanges_foot_l": r"^zan_\w+_phalanx_of_\w+_finger_of_foot_l$",
    "phalanges_foot_r": r"^zan_\w+_phalanx_of_\w+_finger_of_foot_r$",
    "tarsals_l": r"^(calcaneus|talus|navicular|cuboid|cuneiform_\w+)_l$",
    "tarsals_r": r"^(calcaneus|talus|navicular|cuboid|cuneiform_\w+)_r$",
    "metacarpal_1_l": r"^zan_first_metacarpal_bone_l$", "metacarpal_1_r": r"^zan_first_metacarpal_bone_r$",
}


def resolve_bone(bid, bone_ids):
    if not bid:
        return []
    if bid in bone_ids:
        return [bid]
    pat = GROUP_PAT.get(bid)
    if pat:
        return [b for b in bone_ids if re.match(pat, b)]
    return []



# ---------------------------------------------------------------- when a number is NOT applicable, and why
# A belly does not have to touch the bone its record names when the record itself says the attachment is made by
# a tendon / aponeurosis, or that the skeletal element is not modelled on this page. Flagging those would invent
# defects, so the gap is still MEASURED and reported, but marked not-applicable with the reason.
NO_DIRECT = re.compile(
    r"tendon|aponeuro|retinacul|via the|raphe|linea alba|septum|sheath|capsule|"            # soft-tissue attachment
    r"fascia|\bskin\b|mucosa|ligament|cartilage|perineal body|\bdermis\b|sclera|"          # ditto
    r"not mode?ll?ed as skeletal|named only because|the schema takes|midline structure",     # the record's own caveat
    re.I)

# A mesh that ships ONE solid for a serially repeating muscle (one mesh, many bellies) cannot be compared with an
# architecture record measured on ONE unit, and its mesh is MEANT to be in many pieces.
# matched ANYWHERE in the id, because the Z-Anatomy names wrap the same group ("zan_dorsal_parts_of_lateral_
# intertransversarii_lumborum_muscles_l"). A serial muscle's pieces are MEANT to sit at different levels of the
# body, so neither the piece count nor the spread of the pieces is evidence against it.
SERIAL = re.compile(r"levatores_costarum|interspinal|intertransversarii|rotatores|multifidus|semispinalis|"
                    r"lumbrical|interossei|intercostal|subcostales|transversus_thoracis|iliocostalis|"
                    r"longissimus|spinalis|erector_spinae|parts_of|_of_digit|_muscles(_|$)|"
                    r"fibrous_sheath|fibrous_digital")
SERIAL_TEXT = re.compile(r"repeating unit|the rib below|directly above|each origin|per digit|each rib|"
                         r"vertebral levels above", re.I)


def serial_mesh(mid, e):
    if SERIAL.search(mid):
        return True, "id names a serially repeating muscle (one mesh, many bellies)"
    if re.search(r"(^|_)(muscles)(_|$)", mid):
        return True, "id names a GROUP of muscles shipped as one mesh"
    a = (e or {}).get("attachments") or {}
    t = " ".join(str(a.get(k) or "") for k in ("origin_landmark", "insertion_landmark"))
    if SERIAL_TEXT.search(t):
        return True, "the record's own attachment text describes a repeating unit"
    return False, None


def gap_applicable(e, which):
    a = (e or {}).get("attachments") or {}
    t = str(a.get(which + "_landmark") or "")
    if NO_DIRECT.search(t):
        return False, "the record states this end attaches by tendon / aponeurosis, or that the element is not modelled here"
    return True, None


# ================================================================= the severity ladder and the three buckets
def severities(r):
    """[(level, check, text)] -- ONLY the checks that have a project threshold (see THRESHOLDS).

    Every level comes from TH, so changing a threshold moves the buckets. A check whose number was measured but
    marked not-applicable (see the qualifiers above) contributes nothing."""
    out = []
    g1, g2, g3 = TH["attachment_mm"]
    for w in ("origin", "insertion"):
        g = r.get(w + "_gap_mm")
        if r.get(w + "_gap_applicable") and g is not None:
            lvl = 3 if g > g3 else 2 if g > g2 else 1 if g > g1 else 0
            if lvl:
                out.append((lvl, w + "_gap", f"{w} gap {g} mm"))
    o1, o2 = TH["overlap_muscle_pct"]
    ov = r["overlap_muscle_pct"]
    if ov > o2:
        out.append((3, "overlap_muscle", f"overlap {ov} %"))
    elif ov > o1:
        out.append((2, "overlap_muscle", f"overlap {ov} %"))
    b1, b2, b3 = TH["in_bone_pct"]
    if not r.get("coarse_voxel_estimate") and r["bone_deepest_mm"] > 3.0:
        ib = r["in_bone_pct"]
        lvl = 3 if ib > b3 else 2 if ib > b2 else 1 if ib > b1 else 0
        if lvl:
            out.append((lvl, "in_bone", f"in bone {ib} % / {r['bone_deepest_mm']} mm"))
    lo, hi = TH["lr_vol_ratio_ok"]
    x = r.get("lr_vol_ratio_r_over_l")
    if x:
        f = max(x / hi, lo / x)
        if f > 1.0:
            lvl = 3 if f > TH["lr_outside_factor_sev3"] else 2 if f > TH["lr_outside_factor_sev2"] else 1
            out.append((lvl, "lr_vol_ratio", f"R/L volume {x} (band {lo}-{hi})"))
    sd = r.get("spread_over_diag")
    if sd is not None and sd > TH["spread_over_diag_sev3"] and not r.get("serial_or_group_mesh"):
        out.append((3, "piece_in_the_wrong_place",
                    f"a piece {r['component_centroid_spread_mm']} mm away ({sd}x its own diagonal)"))
    elif (r["n_components"] > (r.get("expected_pieces") or 1) and not r.get("serial_or_group_mesh")
          and not r.get("two_mirror_halves")):
        out.append((2, "unexplained_pieces",
                    f"{r['n_components']} pieces, its record allows {r.get('expected_pieces')}"))
    if not r["solid_ok"]:
        out.append((3, "no_solid", "the surface does not enclose a solid"))
    return out


def arch_evidence(r):
    """Supporting evidence only: the architecture ratios have NO project threshold and decide no bucket."""
    out = []
    if r.get("lit_ratio_applicable"):
        v, a = r.get("vol_ratio_lit"), r.get("acsa_ratio_lit")
        if v is not None and (v < 0.5 or v > 2.0):
            out.append(f"volume {v}x the volume its own architecture record implies")
        if a is not None and a < 0.5:
            out.append(f"cross-section {a}x the one its own architecture record implies")
    return out


def classify(r):
    """-> (bucket, bucket_because).  The rule is BUCKET_RULE, applied to severities() only."""
    sev = severities(r)
    s3 = [t for l, _, t in sev if l == 3]
    s2 = [t for l, _, t in sev if l == 2]
    s1 = [t for l, _, t in sev if l == 1]
    gen = r["provenance"] in GENERATED_HERE
    if gen and s3:
        b, why = "not_defensible", ("generated here (%s) and fails a severity-3 geometric check, so there is no "
                                   "real source behind it to fall back on" % r["provenance"])
    elif len(s3) >= 2:
        b, why = "not_defensible", "fails %d independent severity-3 geometric checks" % len(s3)
    elif s3 or s2:
        b, why = "repairable", "%d severity-3 and %d severity-2 geometric checks" % (len(s3), len(s2))
    else:
        b, why = "defensible", "no geometric check above severity 1"
    return b, dict(verdict=why, rule=BUCKET_RULE[b], generated_here=gen,
                   severity_3=s3, severity_2=s2, severity_1=s1,
                   checks=[dict(level=l, check=c, text=t) for l, c, t in sev],
                   architecture_evidence=arch_evidence(r))


# ================================================================= one page
def audit_page(key, page_dir, stem, src_note, cap, verbose=True, man_blob=None):
    """`man_blob` lets a caller audit an IN-MEMORY page (manifest, blob) instead of one on disk -- used by
    scripts/anatomy/q319/repair_q319.py to measure a repaired page with exactly these metrics, so the
    before/after numbers come from one implementation and not two."""
    t0 = time.time()
    import audit297 as A  # the Q297 provenance rule, reused rather than re-derived

    man, blob = man_blob if man_blob is not None else read_page(page_dir, stem)
    M = man["meshes"]
    by_id = {m["id"]: m for m in M}
    bone_ids = [m["id"] for m in M if m["sys"] == "bone"]
    mus = [m for m in M if m["sys"] == "muscle"]
    ENT = muscle_entities()

    geo = {}

    def G(mid):
        if mid not in geo:
            geo[mid] = decode_one(by_id[mid], blob)
        return geo[mid]

    # bone surface samples, for the attachment gaps
    rng = np.random.default_rng(7)
    bone_pts, bone_sol = {}, {}
    for b in bone_ids:
        v, f = G(b)
        bone_pts[b] = area_samples(v, f, min(max(int(4 * area(v, f) / 4.0), 600), 6000), rng)

    # every muscle's own 2 mm solid, once (the overlap metric needs all of them)
    sol = {}
    for m in mus:
        v, f = G(m["id"])
        sol[m["id"]] = lattice_solid(v, f, PITCH, cap)

    rows = {}
    for n, m in enumerate(mus):
        mid = m["id"]
        v, f = G(mid)
        rec = m.get("rec") or {}
        st = dict(id=mid, name=m["name"], sys="muscle", side=m["side"], subject="zan", rec=rec,
                  hd=bool(m.get("hd")), fd=bool(m.get("fd")))
        cls, src_name, why = A.classify(st, "zan", {})
        badge = rec.get("procedural_badge") or ""
        # a finer provenance than Q297's three classes: what the badge says this mesh IS
        if re.search(r"^MIRROR IMAGE|contralateral repair.*replaced by the mirror", badge):
            prov = "mirror_fill"                 # GENERATED HERE: this side is a mirror of the other
        elif re.search(r"^RULE-BASED", badge):
            prov = "rule_based"                  # GENERATED HERE: built from a documented rule
        elif re.search(r"REAL SEGMENTATION OF ANOTHER PERSON", badge):
            prov = "other_person_registered"
        elif re.search(r"IMPORTED REAL MESH", badge):
            prov = "third_party_import"
        elif re.search(r"^Q213:", badge):
            prov = "z_split"
        elif re.search(r"Z-Anatomy geometry fitted onto", badge):
            prov = "z_fitted"                    # Combined pages: Z mesh fitted per bone onto this body
        elif re.search(r"^Q250 female skeleton", badge):
            prov = "z_tps_female"                # Base F: the Z mesh carried by the bone-anchored TPS
        elif re.search(r"^Q162 gap closure", badge):
            prov = "z_raw_gap_closed"            # Base pages: the Z mesh's own shape, nudged out along its normals
        elif not badge or re.search(r"^Q186:", badge):
            prov = "z_raw"                       # Base pages: a plain Z-Anatomy mesh (page-level attribution)
        else:
            prov = "other"
        fit_err = None
        mm = re.search(r"surface error median ([\d.]+) mm, max ([\d.]+) mm \(n ?= ?(\d+)\)", badge)
        if mm:
            fit_err = dict(median_mm=float(mm.group(1)), max_mm=float(mm.group(2)), n=int(mm.group(3)))

        vol = abs(enclosed_cm3(v, f))
        L = belly_length_mm(v)
        top = topology(v, f)

        lo, me, ok, shell = sol[mid]
        # ---- muscle-muscle overlap, Q237 method
        other = np.zeros(me.shape, bool)
        vmin, vmax = v.min(0) - 4, v.max(0) + 4
        for x in mus:
            if x["id"] == mid:
                continue
            xm = by_id[x["id"]]
            if (np.asarray(xm["min"]) + np.asarray(xm["span"]) < vmin).any() or (np.asarray(xm["min"]) > vmax).any():
                continue
            lo2, s2, _, _ = sol[x["id"]]
            paste(other, lo, s2, lo2)
        if ok and me.sum():
            ov = round(100 * float((me & other).sum() / me.sum()), 1)
            ov_basis = "volume"
        else:
            ov = round(100 * float((shell & other).sum() / max(shell.sum(), 1)), 1)
            ov_basis = "surface"

        # ---- inside bone: the same lattice, bones rasterised as solids near this muscle
        bone_near = [b for b in bone_ids
                     if not ((np.asarray(by_id[b]["min"]) + np.asarray(by_id[b]["span"]) < vmin).any()
                             or (np.asarray(by_id[b]["min"]) > vmax).any())]
        bsol = np.zeros(me.shape, bool)
        for b in bone_near:
            if b not in bone_sol:
                vb, fb = G(b)
                bone_sol[b] = lattice_solid(vb, fb, PITCH, cap)
            lo2, s2, ok2, _ = bone_sol[b]
            if ok2:
                paste(bsol, lo, s2, lo2)
        if ok and me.sum():
            in_bone_pct = round(100 * float((me & bsol).sum() / me.sum()), 2)
        else:
            in_bone_pct = round(100 * float((shell & bsol).sum() / max(shell.sum(), 1)), 2)
        if bsol.any() and (me & bsol).any():
            dt = ndi.distance_transform_edt(bsol) * PITCH
            deepest = round(float(dt[me & bsol].max()), 2)
        else:
            deepest = 0.0

        # ---- attachment gaps, on this page's own bones
        e = ENT.get(mid)
        att = (e or {}).get("attachments") or {}
        samp = area_samples(v, f, min(max(int(2 * area(v, f)), 1500), 20000), rng)
        gaps = {}
        for which, fld in (("origin", "origin_bone"), ("insertion", "insertion_bone")):
            ids = resolve_bone(att.get(fld), bone_ids)
            if not ids or len(samp) == 0:
                gaps[which + "_gap_mm"] = None
                gaps[which + "_bone"] = att.get(fld)
                gaps[which + "_bone_resolved"] = len(ids)
                continue
            P = np.vstack([bone_pts[b] for b in ids if len(bone_pts[b])])
            d = cKDTree(P).query(samp)[0]
            gaps[which + "_gap_mm"] = round(float(d.min()), 2)
            gaps[which + "_bone"] = att.get(fld)
            gaps[which + "_bone_resolved"] = len(ids)

        lit = lit_architecture(e) if e else None
        acsa = (vol * 1000.0 / L) if L > 0 else None
        is_serial, serial_why = serial_mesh(mid, e)
        # how many pieces this mesh is ENTITLED to: one per functional compartment the record names (heads /
        # fibre groups), and two if it is a midline muscle Z-Anatomy ships as left and right halves
        ncomp_rec = max(1, len(((e or {}).get("functional_compartments") or [])))
        expected_pieces = ncomp_rec + (1 if m["side"] == "m" else 0)
        for which in ("origin", "insertion"):
            app, whyg = gap_applicable(e, which)
            gaps[which + "_gap_applicable"] = bool(app and gaps.get(which + "_gap_mm") is not None)
            gaps[which + "_gap_not_applicable_because"] = whyg if not app else (
                None if gaps.get(which + "_gap_mm") is not None else "this page carries no mesh for the bone the record names")

        rows[mid] = dict(
            name=m["name"], side=m["side"], hidden_by_default=bool(m.get("hd")),
            q297_class=cls, provenance=prov, fit_error_badge=fit_err,
            atlas_entity=bool(e),
            volume_cm3=round(vol, 3), length_mm=round(L, 1),
            acsa_mm2=(None if acsa is None else round(acsa, 1)),
            lit=lit,
            vol_ratio_lit=(None if not lit or not lit["volume_cm3"] else round(vol / lit["volume_cm3"], 3)),
            acsa_ratio_lit=(None if not lit or not lit["acsa_mm2"] or acsa is None
                            else round(acsa / lit["acsa_mm2"], 3)),
            overlap_muscle_pct=ov, overlap_basis=ov_basis,
            in_bone_pct=in_bone_pct, bone_deepest_mm=deepest,
            solid_ok=bool(ok), solid_voxels=int(me.sum()), shell_voxels=int(shell.sum()),
            coarse_voxel_estimate=bool(me.sum() < 200),
            serial_or_group_mesh=is_serial, serial_or_group_because=serial_why,
            compartments_in_record=ncomp_rec, expected_pieces=expected_pieces,
            lit_ratio_applicable=bool(lit is not None and not is_serial),
            **gaps, **top)
        if verbose and (n + 1) % 50 == 0:
            print(f"    {LABEL[key]}: {n + 1}/{len(mus)}  {time.time() - t0:.0f}s", file=sys.stderr)

    # ---- left/right pairing, by id
    for mid, r in rows.items():
        twin = None
        if mid.endswith("_l"):
            twin = mid[:-2] + "_r"
        elif mid.endswith("_r"):
            twin = mid[:-2] + "_l"
        r["twin"] = twin if twin in rows else None
        if r["twin"]:
            a = rows[mid]["volume_cm3"]
            b = rows[r["twin"]]["volume_cm3"]
            right, left = (a, b) if mid.endswith("_r") else (b, a)
            r["lr_vol_ratio_r_over_l"] = round(right / left, 3) if left > 0 else None
            r["lr_length_ratio_r_over_l"] = (
                round((rows[mid]["length_mm"] if mid.endswith("_r") else rows[r["twin"]]["length_mm"])
                      / max(rows[r["twin"]]["length_mm"] if mid.endswith("_r") else rows[mid]["length_mm"], 1e-9), 3))
        else:
            r["lr_vol_ratio_r_over_l"] = None
            r["lr_length_ratio_r_over_l"] = None

    # ---- the three buckets, computed here (never transcribed) so re-running reproduces them and a change to a
    # threshold in TH moves them. Runs AFTER the left/right pairing, because lr_vol_ratio is one of the checks.
    counts = collections.Counter()
    for r in rows.values():
        b, because = classify(r)
        r["bucket"], r["bucket_because"] = b, because
        counts[b] += 1

    return dict(page=key, label=LABEL[key], source=src_note, n_meshes=len(M), n_muscle_meshes=len(mus),
                seconds=round(time.time() - t0, 1),
                bucket_counts={k: counts.get(k, 0) for k in ("defensible", "repairable", "not_defensible")},
                muscles=rows)


# ================================================================= the summary table
def summary(rep):
    lines = []
    for key, pg in rep["pages"].items():
        R = pg["muscles"]
        bc = pg["bucket_counts"]
        lines.append(f"\n=== {pg['label']}  ({pg['n_muscle_meshes']} muscle meshes of {pg['n_meshes']})")
        lines.append(f"    source: {pg['source']}")
        prov = collections.Counter(r["provenance"] for r in R.values())
        lines.append("  provenance: " + ", ".join(f"{k} {v}" for k, v in prov.most_common()))
        lines.append("  Q297 class: " + ", ".join(f"{k} {v}" for k, v in
                                                  collections.Counter(r["q297_class"] for r in R.values()).most_common()))
        lines.append("  BUCKETS: defensible %d | repairable %d | NOT DEFENSIBLE %d  (of %d)"
                     % (bc["defensible"], bc["repairable"], bc["not_defensible"], len(R)))

        def sev_total(r):
            return sum(l for l, _, _ in severities(r))

        for want, title in (("not_defensible", "NOT DEFENSIBLE -- the deletion candidates"),
                            ("repairable", "REPAIRABLE -- the 15 worst by total severity")):
            sel = sorted(((sev_total(r), mid, r) for mid, r in R.items() if r["bucket"] == want), reverse=True)
            if want == "repairable":
                sel = sel[:15]
            lines.append(f"\n  {title} ({len([1 for r in R.values() if r['bucket'] == want])})")
            lines.append("  %-50s %8s %6s %8s %6s %6s %6s %6s %6s  %s"
                         % ("id", "vol cm3", "/lit", "ACSA/lit", "R/L", "ovl%", "bone%", "ori", "ins", "why"))
            for _, mid, r in sel:
                lines.append("  %-50s %8.2f %6s %8s %6s %6.1f %6.2f %6s %6s  %s" % (
                    mid[:50], r["volume_cm3"], r["vol_ratio_lit"], r["acsa_ratio_lit"],
                    r["lr_vol_ratio_r_over_l"], r["overlap_muscle_pct"], r["in_bone_pct"],
                    r["origin_gap_mm"] if r["origin_gap_applicable"] else "n/a",
                    r["insertion_gap_mm"] if r["insertion_gap_applicable"] else "n/a",
                    "; ".join(r["bucket_because"]["severity_3"] + r["bucket_because"]["severity_2"])))
    lines.append("\n--- bucket counts, for comparison with docs/Q319_reconstructed_muscles.md section 4 ---")
    for key, pg in rep["pages"].items():
        bc = pg["bucket_counts"]
        lines.append("  %-20s %d muscle meshes = %d defensible / %d repairable / %d not defensible"
                     % (pg["label"], pg["n_muscle_meshes"], bc["defensible"], bc["repairable"], bc["not_defensible"]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=None, help="build root holding the six page directories (default: the project baseline)")
    ap.add_argument("--page-dir", action="append", default=[], metavar="KEY=PATH",
                    help="a directory holding index.html + its geo blobs for one page (the published artifact layout)")
    ap.add_argument("--page-note", action="append", default=[], metavar="KEY=TEXT",
                    help="free text recorded as the page's source provenance (artifact version, sha256, ...)")
    ap.add_argument("--pages", default="comb_m,comb_f")
    ap.add_argument("--cap", type=int, default=250000, help="max surface samples per voxelisation (Q237 uses 250000)")
    ap.add_argument("--json", default=str(OUT))
    ap.add_argument("--merge", action="store_true",
                    help="keep the pages already in the output file and add/replace only the ones audited now")
    a = ap.parse_args(argv)

    explicit = {}
    for s in a.page_dir:
        k, _, p = s.partition("=")
        explicit[k] = Path(p)
    notes = {}
    for s in a.page_note:
        k, _, t = s.partition("=")
        notes[k] = t

    src = a.src
    if src is None and not explicit:
        sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
        import model as _m
        src = _m.build_root()

    rep = {"schema": "nmsk.q319.reconstructed_muscle_audit.v1",
           "round": "Q319",
           "generated": time.strftime("%Y-%m-%d"),
           "what": "every muscle mesh of the named pages, measured off the SHIPPED geometry; read-only",
           "thresholds": TH,
           "bucket_rule": BUCKET_RULE,
           "threshold_provenance": {
               "lr_vol_ratio_ok": "data/derived/Q241_pose_asymmetry.md s2 (the Q237 flags)",
               "attachment_mm": "data/derived/Q198_anatomy_audit.json meta.thresholds.attachment_distance_mm",
               "in_bone_pct": "Q198 meta.thresholds.inside_bone_pct_with_>3mm_depth; scripts/anatomy/q237/fill.BELLY_IN_BONE_MAX",
               "bone_deepest_mm": "scripts/anatomy/q237/fill.BONE_DEPTH_MAX_MM",
               "overlap_muscle_pct": "Q198 meta.thresholds.muscle_overlap_pct; scripts/anatomy/q237/fill.OVERLAP_MAX",
               "largest_component_frac": "docs/MUSCLE_GAPS.md (the ECRL ship: 94.6 % in one component)",
               "mean_dihedral_deg_ref": "docs/GEOMETRY_SOURCES.md (CVH references 27.6 / 29.5 / 31.7 deg)",
               "vol_ratio_lit / acsa_ratio_lit": "NO project threshold exists; the numbers are reported raw"},
           "literature_volume_note": (
               "DERIVED, not measured: V = sum over the entity's functional_compartments of "
               "PCSA * optimal_fascicle_length / cos(pennation), and ACSA = sum PCSA * cos(pennation), from the "
               "muscle's OWN cited architecture record in data/muscles/**/*.json (Ward 2009 and the other sources "
               "each record names). It is a literature-architecture implication, never a measured cadaver volume."),
           "pages": {}}

    for key in a.pages.split(","):
        key = key.strip()
        if key in explicit:
            pd, stem = explicit[key], None
            note = notes.get(key) or f"published artifact files in {explicit[key]}"
        else:
            sub, stem = DIRS[key]
            pd = REPO / src / sub
            note = notes.get(key) or f"{src}/{sub}"
        print(f"  reading {LABEL[key]} from {note}", file=sys.stderr)
        rep["pages"][key] = audit_page(key, pd, stem, note, a.cap)

    txt = summary(rep)
    print(txt)
    out = Path(a.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    if a.merge and out.exists():
        # keep every page already on file (the rule and the thresholds are the same, so the figures stay
        # comparable); add or replace only the ones audited in this run.
        prev = json.loads(out.read_text(encoding="utf-8"))
        kept = [k for k in (prev.get("pages") or {}) if k not in rep["pages"]]
        merged = dict(prev)
        merged.update({k: v for k, v in rep.items() if k != "pages"})
        merged["pages"] = {**(prev.get("pages") or {}), **rep["pages"]}
        merged["merged_note"] = ("pages audited in separate runs of the same script, same rule and same "
                                 "thresholds; kept from the previous file: " + (", ".join(kept) or "none"))
        rep = merged
        print("merged: kept %s, wrote %s" % (", ".join(kept) or "none", ", ".join(a.pages.split(","))))
    out.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print("\nwritten " + str(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
