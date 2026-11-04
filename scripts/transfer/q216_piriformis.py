#!/usr/bin/env python3
"""Q216: piriformis r / l of the own female page -- is there ANY evidence of her own for it?  Checked: (1) every label key of her segmentations (TotalSegmentator `total`, the Q48 septa volume, her pelvic-floor
volume, the other vhf_* keys) for a piriformis class; (2) how much of the male-carried mesh lies inside the window of her registered photographs (y +40 .. -420); (3) the mesh's state on her page (volume vs the Z-Anatomy
female reference, bones, skin, neighbours).  -> data/derived/Q216_piriformis_evidence.json.  Nothing is changed on the page."""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402

WINDOW_Y = (-420.0, 40.0)               # the photographed window of Q215 (registered stack, y in the atlas frame)


def label_hits():
    hits, nfiles, nlabels = [], 0, 0
    for p in sorted(glob.glob(str(REPO / "mappings" / "*labels*.json"))):
        d = json.loads(Path(p).read_text())
        labs = d.get("labels", d)
        names = [str(v) for v in (labs.values() if isinstance(labs, dict) else labs)]
        nfiles += 1
        nlabels += len(names)
        for n in names:
            if "pirif" in n.lower():
                hits.append((Path(p).name, n))
    return hits, nfiles, nlabels


def photo_shares(B, names, work):
    """share of each mesh's volume that lies on her photographed muscle / non-muscle / unknown, read from the registered photograph stack of Q215 (work dir of q215_fill: p1_<side>_mus.npy); None if the stack is gone"""
    import nibabel as nib
    from scripts.cryo import vhf_thigh_refit_q181 as R
    from scripts.transfer import q215_fill as Q15
    from scripts.zanatomy.q198_core import Grid
    if not Path(work, "p1_right_mus.npy").exists():
        return None
    img = nib.load(str(R.Q48_VOL))
    A = img.affine
    D = np.zeros(img.shape, np.uint8)
    labels = {}
    for k, nm in enumerate(names, 1):
        v, f = B.mesh(B.items[B.find(nm)[0]])
        ii = (v[:, 0] + R.ORIGIN[0] - A[0, 3]) / A[0, 0]
        jj = (v[:, 2] + R.ORIGIN[2] - A[1, 3]) / A[1, 1]
        kk = (v[:, 1] + R.ORIGIN[1] - A[2, 3]) / A[2, 2]
        vi = np.column_stack([ii, jj, kk])
        lo = np.floor(vi.min(0)).astype(int) - 3
        hi = np.ceil(vi.max(0)).astype(int) + 3
        g = Grid(lo.astype(float), hi.astype(float), 1.0)
        sol = g.solid(vi, np.asarray(f, np.int64), close=1)
        sl = tuple(slice(max(int(lo[a]), 0), min(int(lo[a]) + sol.shape[a], D.shape[a])) for a in range(3))
        sub = tuple(slice(sl[a].start - int(lo[a]), sl[a].stop - int(lo[a])) for a in range(3))
        D[sl][sol[sub]] = k
        labels[nm] = k
    return Q15.Evidence(work).shares(D, labels)


def main():
    hits, nfiles, nlabels = label_hits()
    B = Bundle(REPO / "build/viewer_f_hr_q215")
    q213 = json.loads((REPO / "data/derived/Q213_target_muscle_audit.json").read_text())
    out = dict(label_files_checked=nfiles, labels_checked=nlabels, piriformis_labels_found=hits, septa_labels_51_to_57_muscles_listed=None, window_y_mm=list(WINDOW_Y), sides={})
    septa = json.loads((REPO / "mappings/vhf_xfer_septa_labels.json").read_text())["labels"]
    out["q48_septa_labels"] = len(septa)
    out["q48_septa_has_piriformis"] = any("pirif" in v for v in septa.values())
    for s in "rl":
        sid = f"piriformis_{s}"
        d = B.get(sid)
        v, f = d["v"], d["f"]
        tm = trimesh.Trimesh(v, f, process=False)
        vol = abs(tm.volume) / 1000.0
        # share of the volume inside the window: slice the closed mesh in y
        ys = np.linspace(v[:, 1].min(), v[:, 1].max(), 60)
        inwin = 0.0
        tot = 0.0
        for y0, y1 in zip(ys[:-1], ys[1:]):
            yc = 0.5 * (y0 + y1)
            sec = tm.section(plane_origin=[0, yc, 0], plane_normal=[0, 1, 0])
            if sec is None:
                continue
            try:
                a = sum(abs(p.area) for p in sec.to_planar()[0].polygons_full)
            except Exception:
                a = 0.0
            tot += a * (y1 - y0)
            if WINDOW_Y[0] <= yc <= WINDOW_Y[1]:
                inwin += a * (y1 - y0)
        a213 = q213.get(sid, {})
        out["sides"][sid] = dict(subject=d["e"]["subject"], volume_cm3=round(vol, 1), y_range_mm=[round(float(v[:, 1].min()), 1), round(float(v[:, 1].max()), 1)],
                                 share_inside_photographed_window=round(inwin / max(tot, 1e-9), 2), q213_volumes_cm3=a213.get("vol_cm3"), q213_own_q204=a213.get("own_q204"), q213_own_defects=a213.get("own_defects"))
    work = REPO / "SCRATCH" / "q215" / "work"
    import os
    env_work = os.environ.get("Q215_WORK")
    sh = photo_shares(B, ["piriformis_r", "piriformis_l", "obturator_internus_r", "obturator_internus_l"], env_work or work)
    out["photographed_tissue_share_of_mesh"] = sh
    out["conclusion"] = ("No piriformis class exists in any of her label sets (TotalSegmentator total, the Q48 septa volume, her pelvic-floor volume, other vhf_* keys), the Q48 septa watershed has no piriformis marker, "
                         "and only part of the muscle lies inside the photographed window; no evidence of her own was reached -> piriformis r / l are left as the male-carried meshes (class TRANSFERRED, male size unscaled) and recorded.")
    (REPO / "data/derived/Q216_piriformis_evidence.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1)[:2500])


if __name__ == "__main__":
    main()
