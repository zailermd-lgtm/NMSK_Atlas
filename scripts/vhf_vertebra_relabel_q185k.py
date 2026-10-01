"""Q185k: her (VHF) TotalSegmentator vertebra labels at the thoracolumbar junction -- documented relabel + audit.

    python3 scripts/vhf_vertebra_relabel_q185k.py relabel     # -> data/ct_sources/task_outputs/vhf_total_q185k.nii.gz (not in git)
    python3 scripts/vhf_vertebra_relabel_q185k.py audit       # CT profile + body heights (both bodies) + figures (scratch q185k/)
    python3 scripts/vhf_vertebra_relabel_q185k.py reconvert   # build/vh/ct_vhf: its label records from the corrected volume

FINDING (her CT, 2026-10-01). Her TS `total` label 31 (vertebrae_L1) covers TWO vertebral bodies separated by a disc
space (6-connected pieces of 52.6 k and 60.0 k voxels, z -610..-572 and -657..-608 mm): TS's 5-lumbar model met her
6 rib-free presacral vertebrae (7 C + 12 T + 6 L; ribs 1-12 bilateral, rib 12 on TS T12, no rib below) and named both
"L1". Every other level holds one body. Numerical variant: Tins & Balain 2016 (whole-spine MRI, 418 patients) found
+1 mobile vertebra in 4.3 % (doi:10.1007/s13244-016-0468-7).

RELABEL (only what the CT shows; deterministic, from the TS output, which stays untouched):
 1. label 31 -> its two largest 6-connected pieces (each >= MIN_PIECE voxels, centroids >= MIN_SEP_MM apart in z):
    the UPPER keeps 31 = L1 (the first rib-free vertebra below the rib-12-bearing T12 -- T12/L1 is anchored to the last
    rib); the LOWER becomes L1B (118, "vertebrae_L1b", her supernumerary lumbar vertebra). L2..L5 / S1 keep TS's
    sacrum-anchored numbering, so every lumbar disc id below stays what it was.
 2. small pieces of labels 30 / 31 / 32 (not their label's main body) within JUNCTION_PAD_MM of the two pieces and
    <= AXIS_MM from the column axis go to whichever of L1 / L1B they touch most (26-neighbour contact); no contact ->
    the nearer piece if <= NEAR_MM, else left as is. (Her T12 piece 2 = L1's inferior articular processes; her L2
    pieces 1-5 = L1B's spinous / superior articular processes.)
 3. pieces of 30 / 31 / 32 whose centroid is > AXIS_MM from the column axis are not vertebra -> 0.
The atlas carries the lumbar spine as ONE entity (lumbar_vertebrae), so L1B ships as one more part of it (ct_vhf
mapping entry label 118); costal_cartilage_from_ct_labels.BONE includes 118 so bone gates see it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
TASK = REPO / "data" / "ct_sources" / "task_outputs"
SRC = TASK / "vhf_total.nii.gz"
OUT = TASK / "vhf_total_q185k.nii.gz"
REPORT = REPO / "data" / "derived" / "Q185k_vertebrae_vhf.json"
SCRATCH = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/q185k")
CT = SCRATCH.parent / "vh_idc" / "nii" / "vhf_torso_0937.nii.gz"
L1, L1B, L2, T12 = 31, 118, 30, 32
# ct_vhf records whose label voxels the relabel changes (the aorta: its split levels use the T12 / L1 centroids)
RESURFACED = {"vertebrae_T12", "vertebrae_L1", "vertebrae_L1b", "vertebrae_L2", "aorta"}
MIN_PIECE, MIN_SEP_MM, JUNCTION_PAD_MM, AXIS_MM, NEAR_MM = 20000, 20.0, 15.0, 60.0, 10.0


def total_volume(body: str) -> Path:
    """the `total` label volume a consumer should read: hers is the Q185k-corrected one (made on demand)"""
    if body != "vhf":
        return TASK / f"{body}_total.nii.gz"
    if not OUT.exists():
        relabel()
    return OUT


def split_merged(v: np.ndarray, A: np.ndarray) -> dict:
    """apply rules 1-3 to label volume v in place; returns the per-piece log"""
    from scipy import ndimage as ndi
    s6 = ndi.generate_binary_structure(3, 1); s26 = np.ones((3, 3, 3), bool)
    sl = ndi.find_objects((np.isin(v, [T12, L1, L2])).astype(np.uint8))[0]
    sl = tuple(slice(max(s.start - 2, 0), s.stop + 2) for s in sl); sub = v[sl]
    cc, n = ndi.label(sub == L1, s6); sz = ndi.sum(sub == L1, cc, range(1, n + 1)); o = np.argsort(-sz)
    if n < 2 or sz[o[1]] < MIN_PIECE:
        raise SystemExit(f"label {L1}: no second piece >= {MIN_PIECE} voxels -- nothing to split")
    zc = [float((A @ [0, 0, np.argwhere(cc == q + 1)[:, 2].mean() + sl[2].start, 1])[2]) for q in o[:2]]
    if abs(zc[0] - zc[1]) < MIN_SEP_MM:
        raise SystemExit(f"label {L1}: pieces only {abs(zc[0] - zc[1]):.1f} mm apart -- not two vertebrae")
    up, lo = (o[0] + 1, o[1] + 1) if zc[0] > zc[1] else (o[1] + 1, o[0] + 1)
    U, Lo = cc == up, cc == lo
    log = {"L1_upper_voxels": int(U.sum()), "L1B_lower_voxels": int(Lo.sum()), "pieces": []}
    sub[Lo] = L1B
    both = U | Lo; ijk = np.argwhere(both); sp = np.sqrt((A[:3, :3] ** 2).sum(0))
    axis = ijk[:, :2].mean(0); kz = (ijk[:, 2].min(), ijk[:, 2].max()); pad = JUNCTION_PAD_MM / sp[2]
    from scipy.spatial import cKDTree
    tU, tL = cKDTree(np.argwhere(U) * sp), cKDTree(np.argwhere(Lo) * sp)
    for lab in (T12, L1, L2):
        c2, m = ndi.label(sub == lab, s6)
        if not m:
            continue
        s2 = ndi.sum(sub == lab, c2, range(1, m + 1)); main = int(np.argmax(s2)) + 1
        for q in range(1, m + 1):
            if q == main:
                continue
            f = c2 == q; pts = np.argwhere(f); cen = pts.mean(0)
            off = float(np.linalg.norm((cen[:2] - axis) * sp[:2]))
            rec = {"label": lab, "voxels": int(f.sum()),
                   "z_mm": [round(float((A @ [0, 0, pts[:, 2].min() + sl[2].start, 1])[2]), 1),
                            round(float((A @ [0, 0, pts[:, 2].max() + sl[2].start, 1])[2]), 1)],
                   "axis_offset_mm": round(off, 1)}
            if off > AXIS_MM:
                sub[f] = 0; rec["to"] = "0 (not vertebra: off the column axis)"
            elif kz[0] - pad <= cen[2] <= kz[1] + pad:
                d = ndi.binary_dilation(f, s26) & ~f; cu, cl = int((d & U).sum()), int((d & Lo).sum())
                rec["contact_L1"], rec["contact_L1B"] = cu, cl
                if cu or cl:
                    tgt = L1 if cu >= cl else L1B
                else:
                    du, dl = tU.query(pts * sp)[0].min(), tL.query(pts * sp)[0].min()
                    tgt = (L1 if du <= dl else L1B) if min(du, dl) <= NEAR_MM else None
                if tgt is not None and tgt != lab:
                    sub[f] = tgt
                rec["to"] = {L1: "L1 (31)", L1B: "L1B (118)", None: "unchanged"}[tgt]
            else:
                rec["to"] = "unchanged (outside the junction)"
            log["pieces"].append(rec)
    v[sl] = sub
    return log


def relabel() -> dict:
    import nibabel as nib
    img = nib.load(SRC); v = np.asarray(img.dataobj).astype(np.uint8)
    before = {k: int((v == k).sum()) for k in (T12, L1, L2)}
    log = split_merged(v, img.affine)
    log["voxels_before"] = before; log["voxels_after"] = {k: int((v == k).sum()) for k in (T12, L1, L1B, L2)}
    hdr = img.header.copy(); hdr.set_data_dtype(np.uint8)
    nib.save(nib.Nifti1Image(v, img.affine, hdr), OUT)
    print(f"wrote {OUT.relative_to(REPO)}: {json.dumps(log['voxels_after'])}")
    return log


def reconvert() -> int:
    """re-surface build/vh/ct_vhf from the corrected volume (same convert call as vhf_rebuild_bundle.sh), keeping the
    records later scripts appended to it (Q104 disc cylinders, Q118 tendon / Q122 ligament connectors) and every label
    record the relabel does not touch (e.g. its Q109 remeshed ribs) unchanged: only RESURFACED records are replaced"""
    import shutil
    import subprocess
    from scripts.ribs_from_ct_labels import ORIGIN
    from scripts.bone_carve_q185 import BACKUP, restore
    vh = REPO / "build" / "vh"; old = vh / "ct_vhf"; tmp = SCRATCH / "ct_vhf_q185k"
    restore("ct_vhf"); (old / BACKUP).unlink(missing_ok=True)   # splice the UNCARVED records; the rebuild's Q185 carve re-runs
    shutil.copy(REPO / "mappings" / "subjects" / "ct_vhf_volume_mapping.json", vh / "ct_vhf_volume_mapping.json")
    if not (tmp / "manifest.json").exists() or (tmp / "manifest.json").stat().st_mtime < OUT.stat().st_mtime:
        subprocess.run([sys.executable, str(REPO / "scripts" / "ingest_volume_geometry.py"), "convert", str(total_volume("vhf")),
                        "--labels", "totalsegmentator", "--subject", "ct_vhf", f"--origin={ORIGIN['vhf']}", "--smooth", "1.0",
                        "--out", str(tmp)], check=True, stdout=subprocess.DEVNULL)

    def load(d):
        m = json.loads((d / "manifest.json").read_text())
        return m, np.fromfile(d / "vertices.f32", np.float32).reshape(-1, 3), np.fromfile(d / "faces.u32", np.uint32).reshape(-1, 3)
    mo, Vo, Fo = load(old); mn, Vn, Fn = load(tmp)
    fresh = {(s["source_structure"], s["atlas_id"]): s for s in mn["structures"]}
    recs, V, F, nv, nf, changed = [], [], [], 0, 0, []
    def take(s, Vs, Fs):
        nonlocal nv, nf
        v = Vs[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]]
        f = Fs[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
        recs.append({**s, "vertex_offset": nv, "face_offset": nf}); V.append(v); F.append(f + nv); nv += len(v); nf += len(f)
        return v, f
    seen = set()
    for s in mo["structures"]:
        k = (s["source_structure"], s["atlas_id"])
        if s["source_file"].split("#")[0] in (SRC.name, OUT.name) and k in fresh and k[0] in RESURFACED:
            n = fresh[k]; seen.add(k); v0 = Vo[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]]
            v, _ = take({**n, "source_file": n["source_file"]}, Vn, Fn)
            if v.shape != v0.shape or not np.array_equal(v, v0):
                changed.append("/".join(k))
        else:
            take(s, Vo, Fo)
    for k, n in fresh.items():
        if k not in seen and k[0] in RESURFACED:
            take(n, Vn, Fn); changed.append("/".join(k) + " (new)")
    Va = np.concatenate(V).astype(np.float32); Fa = np.concatenate(F).astype(np.uint32)
    Va.tofile(old / "vertices.f32"); Fa.tofile(old / "faces.u32")
    mo.update({"structures": recs, "source_volume": mn["source_volume"], "vertex_count": int(len(Va)),
               "triangle_count": int(len(Fa)), "bbox_min_mm": [round(float(x), 4) for x in Va.min(0)],
               "bbox_max_mm": [round(float(x), 4) for x in Va.max(0)]})
    (old / "manifest.json").write_text(json.dumps(mo, indent=2))
    print(f"ct_vhf: {len(recs)} records, geometry changed: {changed}")
    return 0


# ---------------------------------------------------------------- audit
NAMES = {35: "T9", 34: "T10", 33: "T11", 32: "T12", 31: "L1", 118: "L1B", 30: "L2", 29: "L3", 28: "L4", 27: "L5", 26: "S1"}


def body_heights(body: str) -> dict:
    """central (r <= 6 mm) height of each T10..L3 vertebral BODY along its local axis (Q185c body cut), mm"""
    from scripts import discs_from_vertebrae_q185c as D
    V = D.Vol(body)
    order = ["T9", "T10", "T11", "T12", "L1"] + (["L1B"] if body == "vhf" else []) + ["L2", "L3", "L4"]
    lab = {**D.VERT, "L1B": L1B}
    cen = {k: V.points(lab[k])[1].mean(0) for k in order}
    out = {}
    for i in range(1, len(order) - 1):
        k = order[i]; F = D.frame(cen[order[i - 1]], cen[order[i + 1]]); c0 = cen[k]
        B, how = D.body_points(V, lab[k], F, c0)
        loc = (B - B.mean(0)) @ F.T; r = np.hypot(loc[:, 0], loc[:, 1])
        c = loc[r <= 6.0, 2]
        out[k] = {"central_height_mm": round(float(c.max() - c.min() + 1.0), 1), "body_cut": how,
                  "body_voxels": int(len(B))}
    return out


def ct_profile(lab: np.ndarray, ct: np.ndarray, A: np.ndarray) -> dict:
    """anterior-column 90th-percentile HU per z (endplates + cortex bright, discs dark); disc minima"""
    from scipy import ndimage as ndi
    from scipy.signal import find_peaks
    xs = A[0, 3] + A[0, 0] * np.arange(ct.shape[0]); ys = A[1, 3] + A[1, 1] * np.arange(ct.shape[1])
    zs = A[2, 3] + A[2, 2] * np.arange(ct.shape[2])
    vert = np.isin(lab, list(NAMES)); ij = np.argwhere(vert.any(2)); xc = float(np.median(xs[ij[:, 0]]))
    ix = np.flatnonzero(np.abs(xs - xc) <= 12); ok = (ys >= -60) & (ys <= 30); rows = []
    for k in range(ct.shape[2]):
        if not (-800 <= zs[k] <= -470):
            continue
        sl = ct[ix, :, max(k - 3, 0):k + 4].max(2); bone = (sl[:, ok] > 180).sum(0) >= 3
        if not bone.any():
            continue
        front = ys[ok][np.flatnonzero(bone)].max(); jb = np.flatnonzero((ys <= front - 3) & (ys >= front - 28))
        rows.append((zs[k], float(np.percentile(ct[ix][:, jb, k], 90))))
    P = np.array(rows); h = ndi.gaussian_filter1d(P[:, 1], 1.5)
    pk, _ = find_peaks(-h, prominence=60, distance=14)
    return {"x_mm": round(xc, 1), "disc_minima_z_mm": [float(P[p, 0]) for p in pk][::-1], "z": P[:, 0].tolist(), "p90": h.tolist()}


def figure(raw: np.ndarray, fix: np.ndarray, ct: np.ndarray, A: np.ndarray, prof: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy import ndimage as ndi
    xs = A[0, 3] + A[0, 0] * np.arange(ct.shape[0]); ys = A[1, 3] + A[1, 1] * np.arange(ct.shape[1])
    zs = A[2, 3] + A[2, 2] * np.arange(ct.shape[2]); i = int(np.argmin(np.abs(xs - prof["x_mm"])))
    img = ct[i - 1:i + 2].mean(0)
    cols = dict(zip(NAMES, plt.cm.tab20(np.linspace(0, 1, len(NAMES)))))
    fig, axs = plt.subplots(1, 3, figsize=(17, 11), gridspec_kw={"width_ratios": [1, 1, 0.45]})
    for ax, L, ttl in ((axs[0], raw, "TS labels as shipped (vhf_total)"), (axs[1], fix, "Q185k relabel (vhf_total_q185k)")):
        ax.imshow(np.clip(img.T, -200, 1000), cmap="gray", origin="lower", extent=[ys[0], ys[-1], zs[0], zs[-1]])
        for lab, n in NAMES.items():
            m = L[i] == lab
            if not m.any():
                continue
            ax.contour(ys, zs, m.T.astype(float), levels=[0.5], colors=[cols[lab]], linewidths=1.3)
            cc, nc = ndi.label(m)
            for q in range(1, nc + 1):
                jj, kk = np.nonzero(cc == q)
                if len(jj) > 40 and ys[int(jj.mean())] > -45:
                    ax.text(ys[int(jj.mean())] + 22, zs[int(kk.mean())], n, color=cols[lab], fontsize=9, weight="bold")
        ax.set_xlim(45, -105); ax.set_ylim(-810, -455); ax.set_title(ttl, fontsize=10)
        ax.set_xlabel("RAS y (mm), anterior to the left"); ax.set_ylabel("RAS z (mm)")
    axs[2].plot(prof["p90"], prof["z"], "k-", lw=0.8)
    for z in prof["disc_minima_z_mm"]:
        axs[2].axhline(z, color="orange", lw=0.6)
    axs[2].set_ylim(-810, -455); axs[2].set_xlabel("anterior column p90 HU"); axs[2].set_title("CT profile, orange = minima", fontsize=10)
    fig.suptitle(f"Q185k her CT mid-sagittal x = {prof['x_mm']} mm (3-voxel mean) with vertebra label outlines; "
                 "right: anterior-column p90 HU (noisy in the osteopenic thoracic bodies)", fontsize=11)
    fig.tight_layout(); fig.savefig(path, dpi=100); plt.close(fig)


def audit() -> int:
    import nibabel as nib
    log = relabel()
    if not CT.exists():
        raise SystemExit(f"audit needs her restacked torso CT at {CT} (scripts/cryo/vhf_skin_and_depth.sh)")
    C = nib.load(CT); A = C.affine
    k0, k1 = int(round((-830 - A[2, 3]) / A[2, 2])), int(round((-440 - A[2, 3]) / A[2, 2]))
    i0, i1 = int((A[0, 3] - 70) / -A[0, 0]), int((A[0, 3] + 65) / -A[0, 0])
    j0, j1 = int((A[1, 3] - 60) / -A[1, 1]), int((A[1, 3] + 120) / -A[1, 1])
    box = (slice(i0, i1), slice(j0, j1), slice(k0, k1))
    ct = np.asarray(C.dataobj[box]).astype(np.int16)
    raw = np.asarray(nib.load(SRC).dataobj[box]).astype(np.uint8); fix = np.asarray(nib.load(OUT).dataobj[box]).astype(np.uint8)
    Ab = A.copy(); Ab[:3, 3] = A[:3, :3] @ [i0, j0, k0] + A[:3, 3]
    prof = ct_profile(fix, ct, Ab)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    figure(raw, fix, ct, Ab, prof, SCRATCH / "q185k_her_midsagittal_labels.png")
    zr = {}
    for lab, n in NAMES.items():
        kk = np.argwhere(fix == lab)[:, 2]
        if len(kk):
            zr[n] = [float(Ab[2, 3] + kk.min()), float(Ab[2, 3] + kk.max())]
    rep = {"_README": (__doc__ or "").strip().splitlines(), "relabel": log, "label_z_range_mm_after": zr,
           "ct_profile": {k: v for k, v in prof.items() if k not in ("z", "p90")},
           "body_heights": {"vhf": body_heights("vhf"), "vhm": body_heights("vhm")},
           "references": ["Tins BJ, Balain B. Incidence of numerical variants and transitional lumbosacral vertebrae on "
                          "whole-spine MRI. Insights Imaging 2016;7(2):199-203. doi:10.1007/s13244-016-0468-7",
                          "Panjabi MM et al. Thoracic human vertebrae. Spine 1991;16(8):888-901. doi:10.1097/00007632-199108000-00006",
                          "Panjabi MM et al. Human lumbar vertebrae. Spine 1992;17(3):299-306. doi:10.1097/00007632-199203000-00010"]}
    REPORT.write_text(json.dumps(rep, indent=1))
    print(json.dumps({"disc_minima": prof["disc_minima_z_mm"], "heights": rep["body_heights"]}, indent=0))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["relabel", "audit", "reconvert"])
    a = ap.parse_args(argv)
    if a.cmd == "relabel":
        relabel(); return 0
    if a.cmd == "reconvert":
        return reconvert()
    return audit()


if __name__ == "__main__":
    sys.exit(main())
