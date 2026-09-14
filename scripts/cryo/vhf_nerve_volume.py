"""Turn tracked nerve chains (vhf_nerve_track.py) into a label volume for `ingest_volume_geometry.py convert`.

    python3 scripts/cryo/vhf_nerve_volume.py --crops SCRATCH/vh_cryo_f/thigh \
        --track sciatic_n=SCRATCH/sciatic_right.json:-70:-250 --track sciatic_n=SCRATCH/sciatic_left.json:-70:-293 \
        --out data/ct_sources/task_outputs/vhf_nerves_cryo.nii.gz --labels-out mappings/vhf_nerves_labels.json \
        --mapping-out mappings/subjects/ct_vhf_nerve_volume_mapping.json

A --track is atlas_id=track.json[:y_top:y_bottom] (the range a human verified on the montage); several tracks of one
nerve and side (upward, main, distal runs) are merged level by level, a later one overriding an earlier one.
Each track carries, per level, the blob label in the stored label image (<track>_labels.npy). The blob pixels are
sent to RAS mm through the crop mapping and binned into a 0.5 x 0.5 x 1 mm RAS grid; a level the track crossed
without a usable blob (gap) repeats the nearest tracked mask, shifted to the chain's interpolated position, for
gaps of at most --max-gap levels. Nerve ids are side-agnostic in this atlas, so both sides of one nerve share one
label. Rule-based; badged; volumes recorded in the report next to the volume.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo.vhf_nerve_track import Crops, SOURCE  # noqa: E402

VOX = 0.5


def load_rows(spec):
    """'atlas_id=track.json[:y_top:y_bottom]' -> (atlas_id, side, rows restricted to the range, label array)."""
    aid, rest = spec.split("=", 1); parts = rest.split(":"); path = parts[0]
    y_top = float(parts[1]) if len(parts) > 1 and parts[1] else None; y_bot = float(parts[2]) if len(parts) > 2 and parts[2] else None
    d = json.load(open(path)); labs = np.load(path.replace(".json", "_labels.npy"), mmap_mode="r")
    rows = [dict(r, labs=labs) for r in d["rows"] if (y_top is None or r["y"] <= y_top) and (y_bot is None or r["y"] >= y_bot)]
    side = "right" if "right" in Path(path).name else "left"
    return aid, side, rows, d


def chain_masks(rows, crops, max_gap):
    """[(y, mask)] for every level of a chain (rows of one nerve and side, merged over track files, sorted top-down);
    levels without a blob take the nearest tracked mask shifted to the interpolated position, for gaps <= max_gap."""
    by_y = {}
    for r in rows:                                    # a later-listed track overrides an earlier one at the same level
        by_y[r["y"]] = r
    rows = [by_y[y] for y in sorted(by_y, reverse=True)]
    found = [r for r in rows if not r["gap"]]
    if not found:
        return []
    out = []
    ys = list(range(int(found[0]["y"]), int(found[-1]["y"]) - 1, -1))
    for y in ys:
        r = by_y.get(y)
        if r is not None and not r["gap"]:
            out.append((y, np.asarray(r["labs"][r["level_index"]]) == r["lab"])); continue
        prev = next((f for f in found[::-1] if f["y"] > y), None); nxt = next((f for f in found if f["y"] < y), None)
        if prev is None or nxt is None or (prev["y"] - nxt["y"]) > max_gap + 1:
            continue
        src = prev if (prev["y"] - y) <= (y - nxt["y"]) else nxt
        m = np.asarray(src["labs"][src["level_index"]]) == src["lab"]
        t = (prev["y"] - y) / max(prev["y"] - nxt["y"], 1)
        x = prev["x"] + t * (nxt["x"] - prev["x"]); z = prev["z"] + t * (nxt["z"] - prev["z"])
        pr0, pc0 = crops.atlas_to_px(src["y"], src["x"], src["z"]); pr1, pc1 = crops.atlas_to_px(y, x, z)
        out.append((y, ndi.shift(m.astype(np.uint8), (pr1 - pr0, pc1 - pc0), order=0) > 0))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crops", required=True); ap.add_argument("--track", action="append", required=True, help="atlas_id=track.json")
    ap.add_argument("--out", required=True); ap.add_argument("--labels-out", required=True); ap.add_argument("--mapping-out", required=True)
    ap.add_argument("--subject", default="ct_vhf_nerve"); ap.add_argument("--max-gap", type=int, default=12)
    a = ap.parse_args()
    groups = {}; seeds = {}
    for t in a.track:
        aid, side, rows, d = load_rows(t); groups.setdefault((aid, side), []).extend(rows); seeds.setdefault((aid, side), d["seed"])
    ids = sorted({aid for aid, _ in groups}); lab_of = {aid: i + 1 for i, aid in enumerate(ids)}
    pts = []; info = {}
    for (aid, side), rows in groups.items():
        crops = Crops(a.crops, side); masks = chain_masks(rows, crops, a.max_gap)
        areas = []
        for y, m in masks:
            rr, cc = np.nonzero(m); ax, az = crops.px_to_atlas(y, rr, cc); areas.append(len(rr) / 9.0)
            pts.append(np.column_stack([ax + crops.ox, az + crops.oz, np.full(len(rr), y + crops.oy), np.full(len(rr), lab_of[aid])]))
        info[f"{aid}:{side}"] = {"levels": len(masks), "y_top": masks[0][0] if masks else None, "y_bottom": masks[-1][0] if masks else None,
                                 "tracked_levels": sum(1 for r in rows if not r["gap"]), "seed": seeds[(aid, side)],
                                 "section_mm2_median": round(float(np.median(areas)), 1) if areas else None}
    P = np.concatenate(pts); lo = P[:, :3].min(0) - 2; hi = P[:, :3].max(0) + 2
    sp = np.array([VOX, VOX, 1.0]); shape = np.ceil((hi - lo) / sp).astype(int) + 1
    vol = np.zeros(shape, np.uint8); ijk = np.rint((P[:, :3] - lo) / sp).astype(int)
    vol[ijk[:, 0], ijk[:, 1], ijk[:, 2]] = P[:, 3].astype(np.uint8)
    for l in lab_of.values():                     # close the 0.5 mm binning holes within each level
        m = vol == l
        for k in range(shape[2]):
            if m[:, :, k].any():
                vol[:, :, k][ndi.binary_closing(m[:, :, k], iterations=1) & (vol[:, :, k] == 0)] = l
    aff = np.diag([VOX, VOX, 1.0, 1.0]); aff[:3, 3] = lo
    nib.save(nib.Nifti1Image(vol, aff), a.out)
    vols = {aid: round(float((vol == l).sum() * VOX * VOX * 1.0) / 1000, 2) for aid, l in lab_of.items()}
    Path(a.labels_out).write_text(json.dumps({"_README": ["Label id -> nerve tracked in the female's full-resolution cryosections "
                                                           "(scripts/cryo/vhf_nerve_track.py + vhf_nerve_volume.py). A KEY, not data."],
                                              "source": SOURCE, "labels": {str(l): aid for aid, l in lab_of.items()}}, indent=1))
    entries = [{"label": l, "source_structure": aid, "side": None, "status": "curated", "atlas_id": aid, "relationship": "part_of",
                "note": "Tracked through her full-resolution cryosections from a landmark-rule seed (both sides in one label; nerve ids are side-agnostic).",
                "candidates": []} for aid, l in lab_of.items()]
    Path(a.mapping_out).write_text(json.dumps({"_README": ["Review every entry before running convert.",
                                                            "Set 'atlas_id' to the correct entity, or null to skip the label.",
                                                            "'status' is advisory; convert reads 'atlas_id' only."],
                                               "subject": a.subject, "source_volume": str(Path(a.out).resolve()),
                                               "label_map": Path(a.labels_out).stem.replace("_labels", ""), "entries": entries}, indent=1))
    rep = {"source": SOURCE, "voxel_mm": [VOX, VOX, 1.0], "volume_cm3": vols, "tracks": info}
    Path(a.out.replace(".nii.gz", "_report.json")).write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
