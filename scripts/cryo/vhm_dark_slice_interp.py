"""Q178: his tracked outlines on the levels where his cryosection photographs are unusable (black / colour-cast), replaced
by shape interpolation between the nearest good, traced + clipped levels above and below. RULE-BASED; badged.

    # crops of the two Q176 boxes around the dark levels (delete after use; vh_cryo/ + vhm_ts/ kept):
    python3 scripts/cryo/vhm_stream_leg_crops.py --index SCRATCH/vh_cryo/cryo_index.json --y-top -120 --y-bot -160 \
        --box right=80,145,-85,-25 --box left=-135,-60,-85,-30 --ap-row -1 --out SCRATCH/q178/sci
    python3 scripts/cryo/vhm_stream_leg_crops.py ... --box right=30,100,-10,80 --box left=-110,-35,-25,75 --out SCRATCH/q178/fem
    python3 scripts/cryo/vhm_femoral_popliteal_track.py register --crops SCRATCH/q178/fem --out SCRATCH/q178/femR
    python3 scripts/cryo/vhm_dark_slice_interp.py photos --crops SCRATCH/q178
    python3 scripts/cryo/vhm_dark_slice_interp.py interp --crops SCRATCH/q178 --montage SCRATCH/q178
    # after vhm_rebuild_bundle.sh reconverted ct_vhm_sciatic / ct_vhm_femoral from the *_interp volumes:
    python3 scripts/cryo/vhm_dark_slice_interp.py verify --bundle build/viewer_m_hr --old-bundle SCRATCH/q178/old_bundle --old-subjects SCRATCH/q178/old_subjects
    python3 scripts/cryo/vhm_dark_slice_interp.py badge

UNUSABLE LEVELS (per photograph, all four thigh crops pooled: both sciatic boxes + both femoral boxes of Q176):
  * per level: mean brightness V (max channel), chromaticity G/R, and the Q175 photographed-muscle fraction (the class the
    Q176 clip reads), each against the median of 14 reference levels on the same side of the darkest level
    (y -120..-133 above, -147..-160 below);
  * a level is unusable when |V / ref - 1| > 0.10, or |G/R - ref| > 0.04, or muscle fraction < 0.85 x ref;
  * the span = the contiguous run of unusable levels that contains the darkest level. Per-crop flags are reported too.
INTERPOLATION (per tracked label and side, on the label volume in which it was clipped -- the sciatic in its ORIGINAL
Q57 grid, then moved by the identical Q173 step, vhm_thigh_fat_plane_snap.write_nerve; the femoral veins in their own):
  * bounds = the level just above and just below the span; both must carry the structure on that side, else the side is
    left as traced (reported);
  * centroid-aligned signed-distance interpolation: each bound's signed distance map (mm, negative inside) is shifted so
    its centroid sits on the linearly interpolated centroid, the two maps are blended with weight t = level fraction
    between the bounds, and the section is where the blend < 0; the largest 4-connected piece is kept;
  * only voxels of that label/side at the span levels change (other labels are never overwritten); every other level is
    byte-identical to the Q176 *_clip volume (asserted). New volumes *_interp.nii.gz; originals kept.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo.vhf_nerve_track import Crops  # noqa: E402
from scripts.cryo import vhm_thigh_fat_plane_snap as SNAP  # noqa: E402
from scripts.cryo import vhm_tracked_clip as CLIP  # noqa: E402

T = REPO / "data/ct_sources/task_outputs"
REPORT = REPO / "data/derived/Q178_vhm_sciatic_interp.json"
ORIGIN = CLIP.ORIGIN
VOX = CLIP.VOX
REF_ABOVE = range(-120, -134, -1)
REF_BELOW = range(-147, -161, -1)
DV, DGR, MUS_RATIO = 0.10, 0.04, 0.85
CROPS = {"sci": ("right", "left"), "fem": ("right", "left")}
# volume -> clipped source (Q176), interpolated output, labels {label: (atlas_id, side or None = both by atlas x sign)}
VOLS = {
    "sciatic": {"src": T / "vhm_nerves_cryo_clip.nii.gz", "out": T / "vhm_nerves_cryo_clip_interp.nii.gz",
                "reg_src": T / "vhm_nerves_cryo_reg_clip.nii.gz", "reg_out": T / "vhm_nerves_cryo_reg_clip_interp.nii.gz",
                "crops": "sci", "labels": {1: ("sciatic_n", None)}, "subject": "ct_vhm_sciatic"},
    "femoral": {"src": T / "vhm_femoral_cryo_clip.nii.gz", "out": T / "vhm_femoral_cryo_clip_interp.nii.gz",
                "crops": "femR", "labels": {3: ("femoral_v_l", "left"), 4: ("femoral_v_r", "right")}, "subject": "ct_vhm_femoral",
                "not_in_span": {1: "femoral_a_l", 2: "femoral_a_r"}},
}
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain): his colour cryosections at full resolution "
          "(0.33 mm, NCI Imaging Data Commons) re-streamed by scripts/cryo/vhm_stream_leg_crops.py for the per-level photograph "
          "statistics and the montage; his tracked outlines from Q57 (vhm_nerves_cryo.nii.gz) and Q174 (vhm_femoral_cryo.nii.gz) as "
          "clipped by Q176 (data/ct_sources/task_outputs/*_clip.nii.gz, scripts/cryo/vhm_tracked_clip.py); photograph-to-atlas "
          "registration from Q173 (data/derived/Q173_vhm_adductor_magnus.json); muscle/bone meshes for the overlap check from his "
          "hi-res viewer bundle (DU lower-extremity release, Andreassen TE et al., Sci Data 10:34 (2023), CC BY 4.0, with the "
          "Q173/Q175/Q177 snaps). Interpolated levels are a rule between real traced levels, not traced.")


# ------------------------------------------------------------------------------------------------ photographs
def photo_stats(crops_dir):
    per = {}; pooled = {}
    for pre, sides in CROPS.items():
        bb = json.load(open(f"{crops_dir}/{pre}_bbox.json")); ys = bb["y_atlas"]
        for sd in sides:
            a = np.load(f"{crops_dir}/{pre}_{sd}.npy", mmap_mode="r"); rows = []
            for j, y in enumerate(ys):
                im = np.asarray(a[j]); ok = im.astype(np.int32).sum(-1) > 0; px = im[ok].astype(np.float64)
                cls = SNAP.classes(im, CLIP.MIN_RED)[ok]
                s = {"n": int(ok.sum()), "sumR": px[:, 0].sum(), "sumG": px[:, 1].sum(), "sumB": px[:, 2].sum(), "sumV": px.max(-1).sum(),
                     "mus": int((cls == 3).sum())}
                rows.append((y, s)); p = pooled.setdefault(y, dict.fromkeys(s, 0)); [p.__setitem__(k, p[k] + v) for k, v in s.items()]
            per[f"{pre}_{sd}"] = dict(rows)
    per["pooled"] = pooled
    out = {}
    for c, d in per.items():
        st = {y: {"V": s["sumV"] / s["n"], "R": s["sumR"] / s["n"], "G": s["sumG"] / s["n"], "B": s["sumB"] / s["n"],
                  "G_R": s["sumG"] / s["sumR"], "B_R": s["sumB"] / s["sumR"], "muscle_frac": s["mus"] / s["n"]} for y, s in d.items()}
        dark = min(st, key=lambda y: st[y]["V"])
        ref = {side: {k: float(np.median([st[y][k] for y in blk])) for k in ("V", "G_R", "muscle_frac")}
               for side, blk in (("above", REF_ABOVE), ("below", REF_BELOW))}
        lv = {}
        for y in sorted(st, reverse=True):
            r = ref["above" if y > dark else "below"]; s = st[y]
            dv = s["V"] / r["V"] - 1; dg = s["G_R"] - r["G_R"]; mr = s["muscle_frac"] / r["muscle_frac"]
            lv[y] = {**{k: round(float(v), 4) for k, v in s.items()}, "V_rel": round(dv, 4), "G_R_diff": round(dg, 4),
                     "muscle_ratio": round(mr, 4), "unusable": bool(abs(dv) > DV or abs(dg) > DGR or mr < MUS_RATIO)}
        span = [dark]
        while lv.get(span[0] + 1, {}).get("unusable"):
            span.insert(0, span[0] + 1)
        while lv.get(span[-1] - 1, {}).get("unusable"):
            span.append(span[-1] - 1)
        out[c] = {"darkest": dark, "reference": {k: {x: round(v, 4) for x, v in r.items()} for k, r in ref.items()},
                  "unusable_span": [span[0], span[-1]], "levels": {str(y): v for y, v in lv.items()}}
    return out


def do_photos(a):
    st = photo_stats(a.crops)
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    rep.update({"source": SOURCE, "task": "Q178 his tracked outlines on his unusable photographs replaced by shape interpolation",
                "method": __doc__.split("UNUSABLE LEVELS")[1].strip(),
                "rule": {"reference_levels_above": [REF_ABOVE[0], REF_ABOVE[-1]], "reference_levels_below": [REF_BELOW[0], REF_BELOW[-1]],
                         "max_V_rel": DV, "max_G_R_diff": DGR, "min_muscle_ratio": MUS_RATIO, "decided_on": "pooled"},
                "photographs": st, "unusable_span": st["pooled"]["unusable_span"]})
    for c, s in st.items():
        bad = [int(y) for y, v in s["levels"].items() if v["unusable"]]
        print(f"{c}: darkest {s['darkest']}, span {s['unusable_span']}, all flagged {sorted(bad, reverse=True)}")
    print("pooled per level (V_rel, G/R diff, muscle ratio):")
    for y in range(-133, -147, -1):
        v = st["pooled"]["levels"][str(y)]
        print(f"  {y}: V {v['V']:.1f} ({v['V_rel']:+.2f}) G/R {v['G_R']:.3f} ({v['G_R_diff']:+.3f}) muscle {v['muscle_frac']:.3f} "
              f"(x{v['muscle_ratio']:.2f}) {'UNUSABLE' if v['unusable'] else ''}")
    REPORT.write_text(json.dumps(rep, indent=1))


# ------------------------------------------------------------------------------------------------ interpolation
def sdf(M):
    P = np.pad(M, 2)
    d = (ndi.distance_transform_edt(~P) - ndi.distance_transform_edt(P)) * VOX
    return d[2:-2, 2:-2]


def interp_section(Ma, Mb, t):
    """centroid-aligned signed-distance blend of two bool sections; t = 0 -> Ma, 1 -> Mb."""
    ca = np.array(ndi.center_of_mass(Ma)); cb = np.array(ndi.center_of_mass(Mb)); c = (1 - t) * ca + t * cb
    Sa = ndi.shift(sdf(Ma), c - ca, order=1, mode="nearest"); Sb = ndi.shift(sdf(Mb), c - cb, order=1, mode="nearest")
    M = ((1 - t) * Sa + t * Sb) < 0
    lab, n = ndi.label(M)
    if n > 1:
        M = lab == (int(np.argmax(np.bincount(lab.ravel())[1:])) + 1)
    return M, n


def level_k(A, y):
    return int(round(y + ORIGIN[1] - A[2, 3]))


def interp_volume(key, span, log=print):
    cfg = VOLS[key]; img = nib.load(str(cfg["src"])); L0 = np.asarray(img.dataobj).copy(); A = img.affine; L1 = L0.copy()
    y_top, y_bot = span; ya, yb = y_top + 1, y_bot - 1; per = {}
    for lab, (aid, side) in cfg["labels"].items():
        for sd in ([side] if side else ["right", "left"]):
            xm = CLIP.side_mask(A, L0.shape, sd)[:, None]
            sec = lambda L, y: (L[:, :, level_k(A, y)] == lab) & xm
            series0 = {y: float(sec(L0, y).sum() * VOX * VOX) for y in range(ya + 3, yb - 4, -1)}
            span_lv = [y for y in range(y_top, y_bot - 1, -1) if sec(L0, y).any()]
            if not span_lv:
                continue
            row = {"atlas_id": aid, "side": sd, "label": lab, "bounds": [ya, yb], "traced_levels_in_span": span_lv}
            Ma, Mb = sec(L0, ya), sec(L0, yb)
            if not (Ma.any() and Mb.any()):
                row.update(status="kept_as_traced", why=f"no traced section on this side at the bound y {ya if not Ma.any() else yb} "
                           "(the traced piece starts/ends inside the span); nothing to interpolate from")
                log(f"{aid} {sd}: KEPT ({row['why']})"); per[f"{aid}:{sd}"] = row; continue
            pieces = {}
            for y in range(y_top, y_bot - 1, -1):
                t = (ya - y) / (ya - yb); M, n = interp_section(Ma, Mb, t); k = level_k(A, y); sl = L1[:, :, k]
                old = (sl == lab) & xm; sl[old] = 0
                free = (sl == 0) | (sl == lab); sl[M & free & xm] = lab; pieces[y] = n
            series1 = {y: float(sec(L1, y).sum() * VOX * VOX) for y in series0}
            row.update(status="interpolated", interpolated_levels=[y_top, y_bot], blend_pieces_before_keep_largest=pieces,
                       area_mm2_before={str(y): v for y, v in series0.items()}, area_mm2_after={str(y): v for y, v in series1.items()},
                       centroid_shift_mm=round(float(np.linalg.norm((np.array(ndi.center_of_mass(Ma)) - np.array(ndi.center_of_mass(Mb))) * VOX)), 2))
            log(f"{aid} {sd}: " + " ".join(f"{y}:{series0[y]:.0f}->{series1[y]:.0f}" for y in series0))
            per[f"{aid}:{sd}"] = row
    # nothing outside the span changed
    ks = [level_k(A, y) for y in range(y_top, y_bot - 1, -1)]; other = np.ones(L0.shape[2], bool); other[ks] = False
    assert (L0[:, :, other] == L1[:, :, other]).all()
    return L0, L1, A, per


def components(L, lab, side, A):
    m = (L == lab) & CLIP.side_mask(A, L.shape, side)[:, None, None]
    return [int(ndi.label(m, np.ones((3, 3, 3)))[1]), int(ndi.label(m)[1])]


def montage(key, crops_dir, L0, L1, A, per, span, out_png):
    cfg = VOLS[key]; tiles = []
    for name, row in per.items():
        if row["status"] != "interpolated":
            continue
        lab, sd = row["label"], row["side"]; ph = Crops(f"{crops_dir}/{cfg['crops']}", sd); xm = CLIP.side_mask(A, L0.shape, sd)[:, None]
        ys = list(range(span[0] + 1, span[1] - 2, -1)); cs = []
        for y in ys:
            m = (L1[:, :, level_k(A, y)] == lab) & xm
            ii, jj = np.nonzero(m); ax, az, _ = CLIP.vox_atlas(A, ii, jj, level_k(A, y)); pr, pc = ph.atlas_to_px(y, ax, az); cs.append((pr.mean(), pc.mean()))
        r0, c0 = np.median(cs, 0).astype(int); h = 66; row_t = []
        for y in ys:
            k = level_k(A, y); m0 = (L0[:, :, k] == lab) & xm; m1 = (L1[:, :, k] == lab) & xm
            im = ph.image(y); oy, ox = max(r0 - h, 0), max(c0 - h, 0); win = np.asarray(im[oy:r0 + h, ox:c0 + h]).copy()
            rr, cc = np.mgrid[0:win.shape[0], 0:win.shape[1]]; x_, z_ = ph.px_to_atlas(y, rr + oy, cc + ox)
            vi = np.rint((x_ + ORIGIN[0] - A[0, 3]) / A[0, 0]).astype(int); vj = np.rint((z_ + ORIGIN[2] - A[1, 3]) / A[1, 1]).astype(int)
            ok = (vi >= 0) & (vj >= 0) & (vi < m0.shape[0]) & (vj < m0.shape[1])
            p0 = np.zeros(win.shape[:2], bool); p1 = p0.copy(); p0[ok] = m0[vi[ok], vj[ok]]; p1[ok] = m1[vi[ok], vj[ok]]
            interp = span[1] <= y <= span[0]
            if interp:
                win[p0 & ~ndi.binary_erosion(p0)] = (255, 255, 0)
            win[p1 & ~ndi.binary_erosion(p1)] = (0, 255, 255) if interp else (0, 255, 0)
            t = Image.fromarray(win).resize((200, 200), Image.NEAREST); d = ImageDraw.Draw(t)
            d.text((3, 2), f"y {y} {'INTERP' if interp else 'traced'}", fill=(255, 255, 255))
            d.text((3, 186), f"{m0.sum() * 0.25:.0f}->{m1.sum() * 0.25:.0f} mm2" if interp else f"{m1.sum() * 0.25:.0f} mm2", fill=(255, 255, 255))
            row_t.append(t)
        W = Image.new("RGB", (200 * len(row_t), 216)); ImageDraw.Draw(W).text((3, 2), f"{name}: yellow = traced (before), cyan = interpolated, green = traced bound/neighbour", fill=(255, 255, 255))
        [W.paste(t, (200 * i, 16)) for i, t in enumerate(row_t)]; tiles.append(W)
    if tiles:
        M = Image.new("RGB", (max(t.width for t in tiles), 216 * len(tiles))); [M.paste(t, (0, 216 * i)) for i, t in enumerate(tiles)]; M.save(out_png)


def do_interp(a):
    rep = json.loads(REPORT.read_text()); span = rep["unusable_span"]; rep["volumes"] = {}; rep["structures"] = {}
    print("span", span)
    for key, cfg in VOLS.items():
        L0, L1, A, per = interp_volume(key, span)
        nib.save(nib.Nifti1Image(L1, A), str(cfg["out"]))
        v = {"in": str(cfg["src"].relative_to(REPO)), "out": str(cfg["out"].relative_to(REPO)), "voxels_changed": int((L0 != L1).sum())}
        if key == "sciatic":
            info = SNAP.write_nerve(CLIP.tuple_reg(), src=cfg["out"], dst=cfg["reg_out"])
            R0 = nib.load(str(cfg["reg_src"])); R1 = nib.load(str(cfg["reg_out"])); r0 = np.asarray(R0.dataobj); r1 = np.asarray(R1.dataobj)
            assert np.allclose(R0.affine, R1.affine) and r0.shape == r1.shape
            ks = [level_k(R1.affine, y) for y in range(span[0], span[1] - 1, -1)]; other = np.ones(r0.shape[2], bool); other[ks] = False
            assert (r0[:, :, other] == r1[:, :, other]).all()
            # the registration step is a translation: the interpolated registered volume equals the registered clipped one off-span
            v.update(registered_in=str(cfg["reg_src"].relative_to(REPO)), registered_out=str(cfg["reg_out"].relative_to(REPO)),
                     registration_step=info, registered_off_span_identical=True)
        for name, row in per.items():
            aid, sd = name.split(":"); lab = row["label"]
            row["components_3d_26_6conn"] = {"before": components(L0, lab, sd, A), "after": components(L1, lab, sd, A)}
            rep["structures"][name] = row
        for lab, aid in cfg.get("not_in_span", {}).items():
            ks = [level_k(A, y) for y in range(span[0], span[1] - 1, -1)]
            rep["structures"][aid] = {"atlas_id": aid, "status": "not_in_span", "voxels_in_span": int((L0[:, :, ks] == lab).sum())}
        rep["volumes"][key] = v
        if a.montage:
            montage(key, a.crops, L0, L1, A, per, span, f"{a.montage}/montage_{key}.png")
    for n, r in rep["structures"].items():
        print(n, r.get("status"), r.get("components_3d_26_6conn"), r.get("why", ""))
    REPORT.write_text(json.dumps(rep, indent=1))


# ------------------------------------------------------------------------------------------------ verify / badge
def dark_count(v, M, span):
    """vertices > 1 mm inside any muscle mesh, and how many of them lie at the span levels (atlas y within +-0.5 mm)."""
    import trimesh
    beyond = np.zeros(len(v), bool); lo, hi = v.min(0) - 5, v.max(0) + 5
    for aid, m in M.items():
        if not any(w in aid for w in CLIP.MUSCLE_WORDS) or (m["v"].max(0) < lo).any() or (m["v"].min(0) > hi).any():
            continue
        tm = trimesh.Trimesh(m["v"], m["f"], process=False); c = tm.contains(v)
        if c.any():
            d = np.zeros(len(v)); d[c] = trimesh.proximity.closest_point(tm, v[c])[1]; beyond |= d > 1
    ins = (v[:, 1] <= span[0] + 0.5) & (v[:, 1] >= span[1] - 0.5)
    return int(beyond.sum()), int((beyond & ins).sum())


def do_verify(a):
    rep = json.loads(REPORT.read_text()); span = rep["unusable_span"]
    h1, M1 = CLIP.geo_hashes(a.bundle); h0, M0 = CLIP.geo_hashes(a.old_bundle)
    changed = sorted(k for k in h1 if h0.get(k) != h1[k])
    rep["bundle"] = {"structures_before_after": [len(h0), len(h1)], "ids_added": sorted(set(h1) - set(h0)),
                     "ids_removed": sorted(set(h0) - set(h1)), "geometry_changed": changed}
    ver = {}
    for key, cfg in VOLS.items():
        sn = CLIP.subject_meshes(REPO / "build/vh" / cfg["subject"]); so = CLIP.subject_meshes(Path(a.old_subjects) / cfg["subject"])
        for aid in dict.fromkeys(x[0] for x in cfg["labels"].values()):
            r = {}
            for tag, v0, v1 in (("bundle", M0[aid]["v"], M1[aid]["v"]), ("fullres_subject", so[aid][0], sn[aid][0])):
                b0, d0 = dark_count(v0, M1, span); b1, d1 = dark_count(v1, M1, span)
                r[f"muscle_beyond_1mm_{tag}"] = {"before": b0, "after": b1, "before_at_span": d0, "after_at_span": d1, "vertices_after": int(len(v1))}
            r["bone_inside"] = {"bundle": CLIP.overlap(M1[aid]["v"], M1, CLIP.BONES, True)["inside_any"],
                                "fullres_subject": CLIP.overlap(sn[aid][0], M1, CLIP.BONES, True)["inside_any"]}
            r["mesh_components"] = {"subject_before": CLIP.mesh_components(*so[aid]), "subject_after": CLIP.mesh_components(*sn[aid]),
                                    "bundle_before": CLIP.mesh_components(M0[aid]["v"], M0[aid]["f"]),
                                    "bundle_after": CLIP.mesh_components(M1[aid]["v"], M1[aid]["f"])}
            ver[aid] = r; print(aid, json.dumps(r))
    rep["verify"] = ver; print("changed ids:", changed, "structures", len(h0), "->", len(h1))
    REPORT.write_text(json.dumps(rep, indent=1))


BADGE = (" Q178 RULE-BASED: his photographs at y {y0}..{y1} are unusable (black or colour-cast; brightness/colour/muscle-class "
         "rule, all thigh crops), so there the outline is INTERPOLATED, not traced: centroid-aligned signed-distance shape "
         "interpolation between the traced, clipped sections at y {ya} and {yb}{which}. Section {sa} mm2 at those levels (was {sb}). "
         "Surface vertices more than 1 mm inside a muscle mesh: {b0} -> {b1} of {nv}.")


def do_badge(a):
    rep = json.loads(REPORT.read_text()); span = rep["unusable_span"]; ver = rep.get("verify")
    if not ver:
        print("Q178 badge: no verify numbers yet"); return
    for key, cfg in VOLS.items():
        d = REPO / "build/vh" / cfg["subject"]; m = json.loads((d / "manifest.json").read_text())
        for st in m["structures"]:
            aid = st["atlas_id"]; rows = [r for n, r in rep["structures"].items() if n.startswith(aid + ":") and r.get("status") == "interpolated"]
            if not rows or aid not in ver:
                continue
            kept = [r for n, r in rep["structures"].items() if n.startswith(aid + ":") and r.get("status") == "kept_as_traced"]
            which = ""
            if len(rows) == 1 and kept:
                which = (f" ({rows[0]['side']} side; the {kept[0]['side']} trace starts inside the span, at y {kept[0]['traced_levels_in_span'][0]}, "
                         f"with no traced level above it, and is kept as traced)")
            r = rows[0]; ys = [str(y) for y in range(span[0], span[1] - 1, -1)]
            sa = "/".join(f"{r['area_mm2_after'][y]:.0f}" for y in ys); sb = "/".join(f"{r['area_mm2_before'][y]:.0f}" for y in ys)
            b = ver[aid]["muscle_beyond_1mm_bundle"]
            st["procedural_badge"] = st["procedural_badge"].split(" Q178 RULE-BASED:")[0] + BADGE.format(
                y0=span[0], y1=span[1], ya=r["bounds"][0], yb=r["bounds"][1], which=which, sa=sa, sb=sb, b0=b["before"], b1=b["after"],
                nv=b["vertices_after"])
            rep.setdefault("badges", {})[aid] = st["procedural_badge"]
        (d / "manifest.json").write_text(json.dumps(m, indent=1))
    REPORT.write_text(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("photos"); p.add_argument("--crops", required=True, help="dir with sci_* and fem_* crops")
    i = sub.add_parser("interp"); i.add_argument("--crops", help="dir with sci_* and femR_* crops (montage)"); i.add_argument("--montage")
    v = sub.add_parser("verify"); v.add_argument("--bundle", default="build/viewer_m_hr"); v.add_argument("--old-bundle", required=True)
    v.add_argument("--old-subjects", required=True)
    sub.add_parser("badge")
    a = ap.parse_args()
    {"photos": do_photos, "interp": do_interp, "verify": do_verify, "badge": do_badge}[a.mode](a)


if __name__ == "__main__":
    main()
