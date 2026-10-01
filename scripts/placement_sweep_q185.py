"""Q185: placement sweep -- every structure of both own-model bundles against that body's own CT labels (AUDIT ONLY).

    python3 scripts/placement_sweep_q185.py sweep [--body vhm|vhf] [--report PATH]
    python3 scripts/placement_sweep_q185.py montage [--report PATH] [--out DIR] [--n 8]

Per structure (shipped bundle record; geometry = the full-res build/vh/<subject> record when its bbox matches the
shipped one within BBOX_TOL_MM, else the decoded bundle mesh; at most MAX_PTS vertices, fixed-seed subsample):
  outside_skin_frac     vertices outside the body's own skin mesh (ct_v?_skin, embree ray parity). Q185a: HIS skin is cut
                        flat at his torso-CT field of view (FOV_CUT_MM, the skin's own x extent -/+ 1 mm); vertices beyond
                        those planes are "skin unknown" (skin_unknown_frac, status 5), NOT outside skin -- there is no skin
                        surface there to be outside of. outside_skin_frac_incl_fov keeps the pre-Q185a number.
  in_bone_gt1mm_frac    vertices > 1 mm inside bone: TS `total` bone labels (BONE, inside the CT field of view) OR the
                        body's own bone meshes for bones TS does not label / that leave the FOV (MESH_BONES)
  in_lung_gt1mm_frac    > 1 mm inside the TS lung lobes (10-14)
  in_organ_gt1mm_frac   > 1 mm inside a TS organ label (ORGANS), minus the pairs in ORGAN_OK
  own_label             mesh -> label-surface median / p90 and label -> mesh median, where the same atlas id has a label
                        of that body in a TotalSegmentator task volume (curated mapping entries; his nulled
                        no-contrast vessel labels are kept as kind "fragment": label -> mesh is the meaningful direction)
Flags (FLAG): outside skin > 1 %, bone > 5 %, lung > 5 %, organ > 5 %, curated own label mesh->label median > 5 mm.
Depth = EDT inside the mask (voxel centres) minus half a voxel, trilinear -- the Q183b depth_inside convention.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.ribs_from_ct_labels import LABELS as RIB_LABELS, LUNG, ORIGIN, TASK, load_skin, to_vox  # noqa: E402
from scripts.costal_cartilage_from_ct_labels import BONE, OWN_LABEL as VESSEL_LABEL  # noqa: E402

REPORT = REPO / "data" / "derived" / "Q185_placement_sweep.json"
SCRATCH = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/q185")
BUNDLE = {"vhm": REPO / "build" / "viewer_m_hr", "vhf": REPO / "build" / "viewer_f_hr"}
FLAG = {"outside_skin_frac": 0.01, "in_bone_gt1mm_frac": 0.05, "in_lung_gt1mm_frac": 0.05,
        "in_organ_gt1mm_frac": 0.05, "own_label_median_mm": 5.0}
MAX_PTS = 60000
TS_NAMES = json.loads((REPO / "mappings" / "totalsegmentator_labels.json").read_text())["labels"]
BBOX_TOL_MM = 3.0
ORGANS = {1: "spleen", 2: "kidney_right", 3: "kidney_left", 4: "gallbladder", 5: "liver", 6: "stomach", 7: "pancreas",
          15: "esophagus", 16: "trachea", 17: "thyroid_gland", 18: "small_bowel", 19: "duodenum", 20: "colon",
          21: "urinary_bladder", 22: "prostate", 51: "heart", 79: "spinal_cord", 90: "brain"}
# TS bones: what BONE labels cover; every other own bone mesh is the in-bone reference (and femur/hip leave his FOV)
TS_BONE_IDS = {"humerus_l", "humerus_r", "scapula_l", "scapula_r", "clavicle_l", "clavicle_r", "hip_bone_l", "hip_bone_r",
               "sacrum", "ribs_l", "ribs_r", "sternum", "cervical_vertebrae", "thoracic_vertebrae", "lumbar_vertebrae",
               "cranium", "mandible", "zygomatic_l", "zygomatic_r", "temporal_l", "temporal_r"}
MESH_BONE_EXTRA = {"femur_l", "femur_r", "hip_bone_l", "hip_bone_r"}
# exclusions (stated in the report)
# + every cat == "bone" record (the bones themselves); optic canal, carotid canal, jugular foramen pass through skull
BONE_EXCLUDE_IDS = {"optic_n", "internal_carotid_a_l", "internal_carotid_a_r", "internal_jugular_v_l", "internal_jugular_v_r"}
LUNG_EXCLUDE_RE = re.compile(r"lung|bronch|pleura|trachea|pulmonary")
VESSEL_HEART = {"aortic_arch_and_great_vessels", "descending_thoracic_aorta", "superior_vena_cava", "inferior_vena_cava"}
ORGAN_OK = {"urinary_bladder": {21}, "rectum": {20}, "sigmoid_colon": {20}, "prostate": {22, 21},
            "inferior_vena_cava": {5, 51}, "optic_n": {90}, "skin": set(ORGANS)}
for _v in VESSEL_HEART:
    ORGAN_OK.setdefault(_v, set()).add(51)
# TotalSegmentator task volumes whose curated mapping entries define "the same id has a label on that body"
TS_TASK_FILES = {"total.nii.gz": "total", "vhf_total.nii.gz": "total", "headneck_muscles_merged.nii.gz": "headneck_muscles_merged",
                 "abdominal_muscles.nii.gz": "abdominal_muscles", "craniofacial_structures.nii.gz": "craniofacial_structures",
                 "head_muscles.nii.gz": "head_muscles", "oculomotor_muscles.nii.gz": "oculomotor_muscles",
                 "headneck_bones_vessels.nii.gz": "headneck_bones_vessels"}


# ---------------------------------------------------------------- core lookup (tested)
def edt_inside(m: np.ndarray, sp) -> np.ndarray:
    """float32 mm a voxel centre lies inside `m`, minus half a voxel (surface at the voxel face); 0 outside"""
    from scipy import ndimage as ndi
    d = ndi.distance_transform_edt(m, sampling=sp).astype(np.float32)
    d -= np.float32(0.5 * float(np.min(sp))); np.clip(d, 0, None, out=d); d[~m] = 0
    return d


def depth_map(mask: np.ndarray, sp) -> tuple[np.ndarray, np.ndarray]:
    """(depth inside `mask` on its bbox crop, crop origin index)"""
    idx = np.argwhere(mask)
    if not len(idx):
        return np.zeros((1, 1, 1), np.float32), np.zeros(3, int)
    lo = np.maximum(idx.min(0) - 2, 0); hi = np.minimum(idx.max(0) + 3, mask.shape); del idx
    return edt_inside(mask[tuple(slice(a, b) for a, b in zip(lo, hi))], sp), lo


def sample_depth(dm: tuple, A: np.ndarray, O: np.ndarray, pts: np.ndarray, shape) -> np.ndarray:
    """depth (mm) at atlas points; NaN where the point is outside the volume's field of view"""
    from scipy import ndimage as ndi
    d, lo = dm
    iv = to_vox(pts, A, O)
    fov = np.all((iv >= -0.5) & (iv <= np.asarray(shape) - 0.5), 1)
    out = np.full(len(pts), np.nan)
    if fov.any():
        out[fov] = ndi.map_coordinates(d, (iv[fov] - lo).T, order=1, mode="constant", cval=0.0)
    return out


def label_at(vol: np.ndarray, A, O, pts) -> np.ndarray:
    """nearest-voxel label at atlas points (0 outside the FOV)"""
    iv = np.rint(to_vox(pts, A, O)).astype(int)
    ok = np.all((iv >= 0) & (iv < np.asarray(vol.shape)), 1)
    out = np.zeros(len(pts), vol.dtype)
    out[ok] = vol[tuple(iv[ok].T)]
    return out


FOV_CUT_BODIES = {"vhm"}   # Q185a: his skin ends at the torso-CT FOV (x = -233 / +247 mm); hers is not cut there


def fov_cut(skin_v: np.ndarray, margin: float = 1.0) -> tuple[float, float]:
    """(lo, hi) atlas-x planes of a skin cut flat at the CT field of view: its own x extent, `margin` mm inside"""
    return float(skin_v[:, 0].min()) + margin, float(skin_v[:, 0].max()) - margin


def flags_of(r: dict) -> list[str]:
    f = []
    for k in ("outside_skin_frac", "in_bone_gt1mm_frac", "in_lung_gt1mm_frac", "in_organ_gt1mm_frac"):
        if r.get(k) is not None and r[k] > FLAG[k]:
            f.append(k)
    ol = r.get("own_label")
    if ol and ol.get("kind") == "curated" and ol["mesh_to_label_median_mm"] > FLAG["own_label_median_mm"]:
        f.append("own_label_median_mm")
    return f


# ---------------------------------------------------------------- data
def _nii(path: Path):
    import nibabel as nib
    img = nib.load(path); A = img.affine
    return np.asarray(img.dataobj).astype(np.uint8), A, np.sqrt((A[:3, :3] ** 2).sum(0))


def bundle_pieces(body: str):
    from scripts.transfer.bundle_io import decode, read_bundle_dir
    b, blob = read_bundle_dir(BUNDLE[body])
    out = {}
    for e, v, f in decode(b, blob):
        m = out.setdefault(e["id"], {"entries": [], "v": [], "f": []})
        m["f"].append(f + sum(len(x) for x in m["v"])); m["v"].append(v); m["entries"].append(e)
    return out


class FullRes:
    """build/vh/<subject> records by atlas id, memory-mapped"""
    def __init__(self):
        self.c = {}

    def get(self, sub: str, aid: str):
        if sub not in self.c:
            d = REPO / "build" / "vh" / sub
            if not (d / "manifest.json").exists():
                self.c[sub] = None
            else:
                m = json.loads((d / "manifest.json").read_text())
                self.c[sub] = (m, np.memmap(d / "vertices.f32", np.float32, "r").reshape(-1, 3),
                               np.memmap(d / "faces.u32", np.uint32, "r").reshape(-1, 3))
        if self.c[sub] is None:
            return None
        m, V, F = self.c[sub]; vs, fs = [], []; n = 0
        for s in m["structures"]:
            if s["atlas_id"] != aid:
                continue
            v = np.array(V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]])
            f = np.array(F[s["face_offset"]:s["face_offset"] + s["triangle_count"]]).astype(np.int64) - s["vertex_offset"]
            vs.append(v); fs.append(f + n); n += len(v)
        return (np.concatenate(vs), np.concatenate(fs)) if vs else None


def geometry(aid: str, piece: dict, fr: FullRes):
    vb = np.concatenate(piece["v"]).astype(np.float64); fb = np.concatenate(piece["f"]).astype(np.int64)
    subs = sorted({e["subject"] for e in piece["entries"]})
    got = [fr.get(s, aid) for s in subs]
    if all(g is not None for g in got):
        v = np.concatenate([g[0] for g in got]).astype(np.float64)
        off = np.cumsum([0] + [len(g[0]) for g in got])
        f = np.concatenate([g[1] + o for g, o in zip(got, off)])
        dev = float(max(np.abs(v.min(0) - vb.min(0)).max(), np.abs(v.max(0) - vb.max(0)).max()))
        if dev <= BBOX_TOL_MM:
            return v, f, f"full-res build/vh ({'+'.join(subs)})", round(dev, 2)
        return vb, fb, f"bundle (full-res bbox off {dev:.1f} mm)", round(dev, 2)
    return vb, fb, "bundle (no full-res record)", None


def own_label_index(body: str) -> dict:
    """atlas id -> list of (volume file, [labels], kind) for that body's TotalSegmentator task volumes"""
    idx: dict = {}
    for p in sorted((REPO / "mappings" / "subjects").glob(f"ct_{body}*_volume_mapping.json")):
        m = json.loads(p.read_text()); src = Path(str(m.get("source_volume"))).name
        if src not in TS_TASK_FILES:
            continue
        task = TS_TASK_FILES[src]
        if body == "vhm" and task == "abdominal_muscles":
            task = "hybrid_abdominal_muscles"     # README: his ct_vhm_abd muscles ship from the hybrid-CT run
        vol = f"{body}_{task}.nii.gz"
        for e in m["entries"]:
            ids = [e["atlas_id"]] if e.get("atlas_id") else list((e.get("split_parts") or {}).values())
            for a in ids:
                if isinstance(a, str):
                    lst = idx.setdefault(a, {}).setdefault(vol, [])
                    if e["label"] not in lst:
                        lst.append(e["label"])
    out = {a: [(v, labs, "curated") for v, labs in d.items()] for a, d in idx.items()}
    for a, labs in RIB_LABELS.items():
        out.setdefault(a, [(f"{body}_total.nii.gz", labs, "curated")])
    if body == "vhm":
        out.setdefault("costal_cartilage_r", [("vhm_total.nii.gz", [117], "curated")])
        out.setdefault("costal_cartilage_l", [("vhm_total.nii.gz", [117], "curated")])
        for a, lab in VESSEL_LABEL.items():   # nulled in his mapping: no-contrast fragments (Q183/Q183b)
            out.setdefault(a, [("vhm_total.nii.gz", [lab], "fragment")])
    return out


class Body:
    def __init__(self, body: str):
        from scipy.spatial import cKDTree
        self.body = body; self.O = np.array([float(x) for x in ORIGIN[body].split(",")])
        tot, self.A, self.sp = _nii(TASK / f"{body}_total.nii.gz"); self.shape = tot.shape
        self.bone = depth_map(np.isin(tot, BONE), self.sp)
        self.lung = depth_map(np.isin(tot, LUNG), self.sp)
        from scipy import ndimage as ndi
        self.objs = ndi.find_objects(tot)
        org = np.zeros(tot.shape, np.float32)
        for lab in ORGANS:
            if lab > len(self.objs) or self.objs[lab - 1] is None:
                continue
            sl = tuple(slice(max(x.start - 2, 0), x.stop + 2) for x in self.objs[lab - 1])
            d = edt_inside(tot[sl] == lab, self.sp)
            org[sl] = np.where(d > 0, d, org[sl])
        self.organ = (org, np.zeros(3, int)); self.tot = tot
        self.skin = load_skin(body); self.skin_tree = cKDTree(self.skin.vertices)
        self.fov_cut = fov_cut(self.skin.vertices) if body in FOV_CUT_BODIES else None
        self.labels = own_label_index(body); self.vol_cache = {}
        self.mesh_bones = []

    def set_mesh_bones(self, pieces: dict, fr: FullRes):
        import trimesh
        from scipy.spatial import cKDTree
        for aid, p in pieces.items():
            e = p["entries"][0]
            if e["cat"] != "bone" or str(e["subject"]).startswith(("xfer_", "ct_s1159")):
                continue
            if aid in TS_BONE_IDS and aid not in MESH_BONE_EXTRA:
                continue
            v, f, _, _ = geometry(aid, p, fr)
            t = trimesh.Trimesh(v, f, process=False)
            n = np.asarray(t.vertex_normals, np.float64)
            if float(np.einsum("ij,ij->i", v[f[:, 0]], np.cross(v[f[:, 1]], v[f[:, 2]])).sum()) < 0:
                n = -n                       # inward-wound mesh: flip so normals point out
            self.mesh_bones.append({"id": aid, "v": v, "n": n, "tree": cKDTree(v), "lo": v.min(0) - 2, "hi": v.max(0) + 2,
                                    "watertight": bool(t.is_watertight)})

    def mesh_bone_depth(self, pts, self_id):
        """(depth inside any own bone mesh, mm; NaN-free) -- 0 where outside all; ids hit"""
        d = np.zeros(len(pts)); hit = {}
        for b in self.mesh_bones:
            if b["id"] == self_id:
                continue
            sel = np.flatnonzero(np.all((pts >= b["lo"]) & (pts <= b["hi"]), 1))
            if not len(sel):
                continue
            dd, j = b["tree"].query(pts[sel])
            ins = np.einsum("ij,ij->i", pts[sel] - b["v"][j], b["n"][j]) < 0   # nearest-vertex pseudo-normal side test
            ii, dd = sel[ins], dd[ins]
            if not len(ii):
                continue
            d[ii] = np.maximum(d[ii], dd)
            if (dd > 1.0).any():
                hit[b["id"]] = int((dd > 1.0).sum())
        return d, hit

    def label_surface(self, vol: str, labs: list[int]):
        from scipy import ndimage as ndi
        from engine.volume_ingest import voxels_to_atlas
        if vol == f"{self.body}_total.nii.gz":
            V, A, objs = self.tot, self.A, self.objs
        else:
            if vol not in self.vol_cache:
                if not (TASK / vol).exists():
                    return None
                self.vol_cache.clear(); V, A, _ = _nii(TASK / vol); self.vol_cache[vol] = (V, A, ndi.find_objects(V))
            V, A, objs = self.vol_cache[vol]
        sls = [objs[x - 1] for x in labs if x - 1 < len(objs) and objs[x - 1] is not None]
        if not sls:
            return np.zeros((0, 3))
        lo = np.maximum(np.min([[x.start for x in s] for s in sls], 0) - 1, 0)
        hi = np.minimum(np.max([[x.stop for x in s] for s in sls], 0) + 1, V.shape)
        self.last_vol = (A, V.shape)
        c = np.isin(V[tuple(slice(a, b) for a, b in zip(lo, hi))], labs)
        surf = c & ~ndi.binary_erosion(c)
        sidx = np.argwhere(surf) + lo
        return voxels_to_atlas(sidx.astype(float), A) - self.O


def measure(B: Body, aid: str, entry: dict, v: np.ndarray) -> dict:
    from scipy.spatial import cKDTree
    rng = np.random.default_rng(185)
    p = v if len(v) <= MAX_PTS else v[rng.choice(len(v), MAX_PTS, replace=False)]
    cat = entry["cat"]; r = {"n_points": int(len(p))}; st = np.zeros(len(p), np.uint8)
    # skin
    if aid == "skin":
        r["outside_skin_frac"] = None
    else:
        out = ~B.skin.contains(p)
        unk = ((p[:, 0] <= B.fov_cut[0]) | (p[:, 0] >= B.fov_cut[1])) if B.fov_cut else np.zeros(len(p), bool)
        if unk.any():
            r["skin_unknown_frac"] = round(float(unk.mean()), 4)
            r["outside_skin_frac_incl_fov"] = round(float(out.mean()), 4)
        out &= ~unk; st[out] = 1
        r["outside_skin_frac"] = round(float(out.mean()), 4)
        r["outside_skin_max_mm"] = round(float(B.skin_tree.query(p[out])[0].max()), 1) if out.any() else 0.0
    # bone
    tsb = sample_depth(B.bone, B.A, B.O, p, B.shape)
    fov = ~np.isnan(tsb); r["in_ct_fov_frac"] = round(float(fov.mean()), 3)
    if cat == "bone":
        r["in_bone_gt1mm_frac"] = None; r["bone_excluded"] = True
    else:
        mb, hit = B.mesh_bone_depth(p, aid)
        ts_in = np.nan_to_num(tsb) > 1.0; m_in = mb > 1.0; st[(st == 0) & (ts_in | m_in)] = 2
        r["in_bone_gt1mm_frac"] = round(float((ts_in | m_in).mean()), 4)
        r["in_bone_ts_label_frac"] = round(float(ts_in.mean()), 4)
        r["in_bone_mesh_frac"] = round(float(m_in.mean()), 4)
        if ts_in.any():
            labs = label_at(B.tot, B.A, B.O, p[ts_in]); u, c = np.unique(labs[np.isin(labs, BONE)], return_counts=True)
            r["in_bone_ts_top"] = {TS_NAMES[str(int(a))]: int(b) for a, b in sorted(zip(u, c), key=lambda x: -x[1])[:3]}
        if hit:
            r["in_bone_mesh_top"] = dict(sorted(hit.items(), key=lambda x: -x[1])[:3])
    # lung
    if LUNG_EXCLUDE_RE.search(aid):
        r["in_lung_gt1mm_frac"] = None
    else:
        lg = np.nan_to_num(sample_depth(B.lung, B.A, B.O, p, B.shape)) > 1.0; st[(st == 0) & lg] = 3
        r["in_lung_gt1mm_frac"] = round(float(lg.mean()), 4)
    # organs
    od = np.nan_to_num(sample_depth(B.organ, B.A, B.O, p, B.shape)) > 1.0
    ok = ORGAN_OK.get(aid, set())
    if od.any():
        labs = label_at(B.tot, B.A, B.O, p[od]); keep = ~np.isin(labs, list(ok)) & np.isin(labs, list(ORGANS))
        u, c = np.unique(labs[keep], return_counts=True)
        r["in_organ_gt1mm_frac"] = round(float(keep.sum() / len(p)), 4)
        oi = np.flatnonzero(od)[keep]; st[oi[st[oi] == 0]] = 4
        r["in_organ_top"] = {ORGANS[int(a)]: int(b) for a, b in sorted(zip(u, c), key=lambda x: -x[1])[:3]}
    else:
        r["in_organ_gt1mm_frac"] = 0.0
    # own label
    for vol, labs, kind in B.labels.get(aid, []):
        s = B.label_surface(vol, labs)
        if s is None or len(s) < 50:
            continue
        A2, sh2 = B.last_vol; iv = to_vox(p, A2, B.O)
        fov2 = np.all((iv >= 0) & (iv <= np.asarray(sh2) - 1), 1)   # only vertices that volume could label
        if fov2.sum() < 20:
            continue
        d = cKDTree(s).query(p[fov2])[0]; d2 = cKDTree(p).query(s)[0]
        r["own_label"] = {"volume": vol, "labels": labs, "kind": kind, "surface_voxels": int(len(s)),
                          "mesh_in_label_fov_frac": round(float(fov2.mean()), 3),
                          "mesh_to_label_median_mm": round(float(np.median(d)), 2),
                          "mesh_to_label_p90_mm": round(float(np.percentile(d, 90)), 2),
                          "label_to_mesh_median_mm": round(float(np.median(d2)), 2)}
        r["_label_pts"] = s
        break
    if aid != "skin" and unk.any():
        st[unk & (st == 0)] = 5
    r["_pts"], r["_status"] = p, st
    return r


def badge_kind(rec: dict | None) -> str:
    b = (rec or {}).get("procedural_badge")
    if not b:
        return "none"
    m = re.match(r"\s*([A-Z][A-Z -]{3,}[A-Z])\b", b)
    return m.group(1) if m else b[:60]


def sweep(body: str, only: str | None = None) -> dict:
    import gc
    pieces = bundle_pieces(body); fr = FullRes(); B = Body(body); B.set_mesh_bones(pieces, fr)
    if only:   # Q185c: re-sweep a subset (bone meshes above are still built from the whole bundle)
        pieces = {k: v for k, v in pieces.items() if re.search(only, k)}
    rows, hidden = {}, []
    for i, (aid, pc) in enumerate(pieces.items()):
        e = pc["entries"][0]
        if any(x.get("hidden_default") for x in pc["entries"]):
            hidden.append(aid); continue
        v, f, src, dev = geometry(aid, pc, fr)
        r = {"subject": "+".join(sorted({x["subject"] for x in pc["entries"]})), "cat": e["cat"],
             "badge_kind": badge_kind(e.get("rec")), "badge": ((e.get("rec") or {}).get("procedural_badge") or "")[:240],
             "geometry": src, "full_res_bbox_dev_mm": dev, "nv": int(len(v))}
        r.update(measure(B, aid, e, v)); r["flags"] = flags_of(r)
        pts, stt, lab = r.pop("_pts"), r.pop("_status"), r.pop("_label_pts", None)
        if r["flags"]:
            SCRATCH.mkdir(parents=True, exist_ok=True)
            lab = lab[np.random.default_rng(0).choice(len(lab), min(len(lab), 20000), replace=False)] if lab is not None else np.zeros((0, 3))
            np.savez_compressed(SCRATCH / f"pts_{body}_{aid}.npz", pts=pts.astype(np.float32), status=stt, label=lab.astype(np.float32))
        rows[aid] = r
        del v, f; gc.collect()
        if i % 50 == 0:
            print(f"{body} {i}/{len(pieces)} {aid}", flush=True)
    return {"structures": rows, "hidden_default_skipped": hidden}


def score(r: dict) -> float:
    s = 0.0
    for k in ("outside_skin_frac", "in_bone_gt1mm_frac", "in_lung_gt1mm_frac", "in_organ_gt1mm_frac"):
        if r.get(k) is not None:
            s += r[k] / FLAG[k]
    ol = r.get("own_label")
    if ol and ol["kind"] == "curated":
        s += ol["mesh_to_label_median_mm"] / FLAG["own_label_median_mm"]
    return s


STATUS = [("ok", "#2ca02c"), ("outside skin", "#d62728"), ("in bone > 1 mm", "#ff7f0e"), ("in lung > 1 mm", "#1f77b4"),
          ("in organ > 1 mm", "#9467bd"), ("skin unknown (beyond his CT FOV)", "#bdbdbd")]


def montage(rep: dict, out: Path, n: int) -> int:
    """worst n flagged per body: anterior (X-Y) + right lateral (Z-Y) views, vertices coloured by STATUS, own CT label
    surface (black dots) where one exists, skin + bone vertices of the shipped bundle as context"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out.mkdir(parents=True, exist_ok=True)
    for body in ("vhm", "vhf"):
        if body not in rep:
            continue
        worst, per = [], {}           # worst first, skipping `ref`, one per defect group so the groups show
        for k in rep[body]["flagged_ranked"]:
            g = rep[body]["structures"][k]["group"]
            if g != "ref" and per.get(g, 0) < 1 and len(worst) < n:
                worst.append(k); per[g] = per.get(g, 0) + 1
        pieces = bundle_pieces(body); rng = np.random.default_rng(1)
        ctx = {"skin": np.concatenate(pieces["skin"]["v"]) if "skin" in pieces else np.zeros((0, 3)),
               "bone": np.concatenate([np.concatenate(p["v"]) for p in pieces.values() if p["entries"][0]["cat"] == "bone"])}
        ctx = {k: v[rng.choice(len(v), min(len(v), 400000), replace=False)] for k, v in ctx.items()}
        cols = 4; rows = int(np.ceil(len(worst) * 2 / cols))
        fig, axs = plt.subplots(rows, cols, figsize=(cols * 4.2, rows * 4.6)); axs = np.atleast_2d(axs)
        for k, aid in enumerate(worst):
            r = rep[body]["structures"][aid]; z = np.load(SCRATCH / f"pts_{body}_{aid}.npz")
            P, S, L = z["pts"], z["status"], z["label"]
            lo, hi = P.min(0) - 40, P.max(0) + 40
            for j, (ax_i, ax_j, nm) in enumerate(((0, 1, "anterior (X right, Y up)"), (2, 1, "lateral (Z anterior, Y up)"))):
                ax = axs[(2 * k + j) // cols, (2 * k + j) % cols]
                for key, c, sz in (("skin", "#d9d9d9", 0.3), ("bone", "#8c8c8c", 0.3)):
                    C = ctx[key]; m = np.all((C >= lo) & (C <= hi), 1)
                    ax.scatter(C[m, ax_i], C[m, ax_j], s=sz, c=c, linewidths=0)
                if len(L):
                    m = np.all((L >= lo) & (L <= hi), 1)
                    ax.scatter(L[m, ax_i], L[m, ax_j], s=0.4, c="k", linewidths=0, alpha=0.5)
                for code in range(len(STATUS)):
                    m = S == code
                    if m.any():
                        ax.scatter(P[m, ax_i], P[m, ax_j], s=1.0 if code else 0.5, c=STATUS[code][1], linewidths=0)
                ax.set_xlim(lo[ax_i], hi[ax_i]); ax.set_ylim(lo[ax_j], hi[ax_j]); ax.set_aspect("equal")
                if ax_i == 2:
                    ax.invert_xaxis()
                ax.tick_params(labelsize=6)
                fl = ", ".join(f"{f.split('_gt1mm')[0].replace('_frac', '')} "
                               + (f"{r['own_label']['mesh_to_label_median_mm']:.1f} mm" if f == "own_label_median_mm" else f"{100 * r[f]:.1f}%")
                               for f in r["flags"])
                ax.set_title(f"{r['group']}: {aid} [{r['subject'][:26]}]\n{fl}\n{nm}", fontsize=7)
        for ax in axs.ravel()[len(worst) * 2:]:
            ax.axis("off")
        h = [plt.Line2D([], [], marker="o", ls="", c=c, label=t) for t, c in STATUS] + \
            [plt.Line2D([], [], marker="o", ls="", c="k", label="own CT label surface"),
             plt.Line2D([], [], marker="o", ls="", c="#8c8c8c", label="bundle bones"),
             plt.Line2D([], [], marker="o", ls="", c="#d9d9d9", label="skin")]
        fig.legend(handles=h, loc="lower center", ncol=8, fontsize=8)
        fig.suptitle(f"Q185 placement sweep -- {'his (VHM)' if body == 'vhm' else 'her (VHF)'} worst {len(worst)} flagged", fontsize=11)
        fig.tight_layout(rect=(0, 0.03, 1, 0.97)); fig.savefig(out / f"montage_{body}.png", dpi=110); plt.close(fig)
        print("wrote", out / f"montage_{body}.png")
    return 0


# defect groups (queue lines Q185a..; see PROJECT_STATE ## Q185) -- (group, likely cause)
GROUPS = {
    "Q185a": "his skin mesh is cut flat at the torso-CT field of view (x = -233 / +247 mm): arm parts beyond it read 'outside skin'",
    "Q185b": "Z-Anatomy limb transfer (bone-driven warp) misfits his/her hand, foot and forearm: through the skin and into bone",
    "Q185c": "procedural disc cylinders (Q104) not fitted to the vertebral bodies: rim pokes into lung / organs / vertebrae",
    "Q185d": "articular cartilage / knee ligaments carried male->female (xfer_vhm2vhf) or his recovered vhm_both ones sink into bone",
    "Q185e": "male->female muscle transfer (xfer_vhm2vhf*, mostly the leg/hip septa route; ct_vhf_xfersepta_fix) not carved against her bones",
    "Q185f": "transversus / rectus abdominis inside the liver or stomach label (TVA transfer / his cryo abdominal wall)",
    "Q185g": "his orbit muscles + optic nerve are her geometry carried by xfer_vhf2vhm, 5.6-9.7 mm off his own TS oculomotor labels",
    "Q185h": "Z-Anatomy head transfer: rectus capitis anterior / lateralis 11-43 % inside the skull base",
    "Q185i": "own cryo/CT muscle segmentation not carved against the bone labels / meshes (overlaps 5-32 %)",
    "Q185j": "procedural tendon connectors (Q118) end > 1 mm inside the bone they insert on",
    "ref": "NOT a placement defect: own label agrees (<= 1 mm); TS skull label overlaps the TS head-muscle label",
}


def classify(aid: str, r: dict) -> str:
    sub, cat, fl = r["subject"], r["cat"], set(r["flags"])
    ol = r.get("own_label") or {}
    if "outside_skin_frac" in fl and r.get("outside_skin_beyond_fov_cut_frac", 0) >= 0.8 \
            and (fl == {"outside_skin_frac"} or cat == "bone"):
        return "Q185a"
    if aid.startswith("intervertebral_disc"):
        return "Q185c"
    if cat == "tendon" and r["badge_kind"].startswith("PROCEDURAL"):
        return "Q185j"
    if sub.startswith(("xfer_zan2vhm_limb", "xfer_zan2vhf_limb", "xfer_zan2vhf_foot")):
        return "Q185b"
    if sub.startswith(("xfer_zan2vhm_head", "xfer_zan2vhf_head")):
        return "Q185h"
    if cat in ("cartilage", "ligament") and sub.split("+")[0] in ("xfer_vhm2vhf", "vhm_both"):
        return "Q185d"
    if sub.startswith(("xfer_vhm2vhf", "ct_vhf_xfersepta")) and not sub.startswith("xfer_vhm2vhf_tva"):
        return "Q185e"
    if fl == {"in_organ_gt1mm_frac"} or (aid.startswith(("transversus_abdominis", "rectus_abdominis")) and "in_organ_gt1mm_frac" in fl):
        return "Q185f"
    if sub.startswith("xfer_vhf2vhm") and "own_label_median_mm" in fl:
        return "Q185g"
    if fl == {"in_bone_gt1mm_frac"} and ol.get("kind") == "curated" and ol["mesh_to_label_median_mm"] <= 1.0 \
            and set(r.get("in_bone_ts_top") or {}) <= {"skull"}:
        return "ref"
    return "Q185i"


def finalize(rep: dict) -> None:
    """exclusions, skin-cut annotation, flags, ranking, groups -- re-runnable on a stored report"""
    for body in ("vhm", "vhf"):
        if body not in rep:
            continue
        S = rep[body]["structures"]
        cut = None
        if body == "vhm":
            cut = fov_cut(load_skin(body).vertices)
        for aid, r in S.items():
            if aid in BONE_EXCLUDE_IDS and r.get("in_bone_gt1mm_frac") is not None:
                r["in_bone_gt1mm_frac_raw"] = r["in_bone_gt1mm_frac"]; r["in_bone_gt1mm_frac"] = None; r["bone_excluded"] = True
            r["flags"] = flags_of(r)
            f = SCRATCH / f"pts_{body}_{aid}.npz"
            if cut and "outside_skin_frac" in r["flags"] and f.exists():
                z = np.load(f); P, st = z["pts"], z["status"]; o = st == 1
                beyond = o & ((P[:, 0] <= cut[0]) | (P[:, 0] >= cut[1]))
                r["outside_skin_beyond_fov_cut_frac"] = round(float(beyond.sum() / max(o.sum(), 1)), 3)
                r["outside_skin_frac_excl_fov_cut"] = round(float((o & ~beyond).mean()), 4)
        fl = {k: r for k, r in S.items() if r["flags"]}
        for k, r in fl.items():
            r["group"] = classify(k, r); r["likely_cause"] = GROUPS[r["group"]]
        for k, r in S.items():
            if not r["flags"]:
                r.pop("group", None); r.pop("likely_cause", None)
        rep[body]["flagged_ranked"] = sorted(fl, key=lambda k: -score(fl[k]))
    rep["groups"] = GROUPS


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["sweep", "finalize", "montage"])
    ap.add_argument("--body", choices=["vhm", "vhf", "both"], default="both"); ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--out", default=str(SCRATCH)); ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--only", default=None, help="sweep only ids matching this regex (use with a separate --report)")
    a = ap.parse_args(argv); rep_p = Path(a.report)
    rep = json.loads(rep_p.read_text()) if rep_p.exists() else {}
    if a.cmd == "sweep":
        for body in (["vhm", "vhf"] if a.body == "both" else [a.body]):
            rep[body] = sweep(body, a.only)
        a.cmd = "finalize"
    if a.cmd == "finalize":
        finalize(rep)
        for body in ("vhm", "vhf"):
            if body in rep:
                print(body, "swept", len(rep[body]["structures"]), "flagged", len(rep[body]["flagged_ranked"]),
                      "hidden", len(rep[body]["hidden_default_skipped"]))
        rep["_README"] = __doc__.strip().splitlines() + [
            f"Flag thresholds: {FLAG}. Excluded from in-bone: every cat=='bone' record and {sorted(BONE_EXCLUDE_IDS)} (optic canal, carotid canal, jugular foramen; raw value kept as in_bone_gt1mm_frac_raw); "
            f"from in-lung: ids matching /{LUNG_EXCLUDE_RE.pattern}/ (none in either bundle); from in-organ: {json.dumps({k: sorted(v) for k, v in ORGAN_OK.items() if k != 'skin'})} "
            "(TS label ids), skin entirely. Vertices outside the TS `total` field of view count as not-in-bone for the label part "
            "(in_ct_fov_frac); the own bone meshes cover the limbs there. A flagged row has `group` + `likely_cause` (see `groups`); "
            "his outside-skin rows also give the share of outside vertices beyond his skin's flat FOV cut (outside_skin_beyond_fov_cut_frac)."]
        rep_p.write_text(json.dumps(rep, indent=1))
        return 0
    return montage(rep, Path(a.out), a.n)


if __name__ == "__main__":
    sys.exit(main())
