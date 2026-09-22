#!/usr/bin/env python3
"""Q115: decimation-vs-source triage sweep for the ~140 fragmented muscle/nerve/
vessel structures Q112 found and Q113/Q114 did not already root-cause.

Exactly Q113/Q114's own diagnostic, applied mechanically to every remaining
candidate instead of by hand: for each (id, side, body) group below main_frac
0.99, resolve the structure back to the RAW source label volume it was
surfaced from (following a cross-subject transfer's own 'transfer.from' back
to the real originating subject when the shipped piece is a transfer, and a
split label's own splitter function when the shipped piece is one part of a
label another script cut into several), and count real connected components
in that raw voxel mask with scipy.ndimage.label (26-connectivity, matching
Q113/Q114's own convention). A source_main_frac close to the shipped
main_frac means the fragmentation is already in the segmentation
(LIKELY_GENUINE); a source_main_frac much higher than shipped means
smoothing/decimation is the destroyer (LIKELY_PIPELINE_ARTIFACT), exactly
Q113's sciatic_n and Q114's external_intercostals/internal_carotid finding.
Anything this script cannot resolve to a real source volume (no manifest
entry, a 'recovered from the published viewer' provenance with no voxel mask
behind it, a missing file) is UNCLEAR, with the reason recorded.

Read-only: never writes into build/ or mappings/, only the output JSON.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine import volume_ingest as vol  # noqa: E402

BUILD = REPO_ROOT / "build" / "vh"
AUDIT_JSON = REPO_ROOT / "data" / "derived" / "Q112_full_continuity_audit.json"

# The 8 structures (12 (id,side) entries) Q113/Q114 already root-caused --
# excluded here per this item's own brief, regardless of outcome (fixed or
# declined), so this sweep only covers genuinely untouched ground.
ALREADY_HANDLED = {
    "sciatic_n", "external_intercostals_l", "external_intercostals_r",
    "internal_carotid_a_l", "internal_carotid_a_r", "longus_capitis_r",
    "longus_colli_l", "longus_colli_r", "pectoralis_minor_l",
    "pectoralis_minor_r", "internal_oblique_r", "transversus_abdominis_r",
}
# Also already fully investigated by Q114 (a third, distinct failure mode --
# marching-cubes surface topology at a sub-voxel-thin bridge -- confirmed not
# fixable by the smoothing parameter) even though the brief's own exclude
# list omits them by name. Re-running this sweep on them would find nothing
# new (their raw-mask main_frac is already known: 0.933/0.519) and would
# waste triage time re-discovering Q114's own conclusion, so they are skipped
# with an explicit note rather than silently re-measured.
ALSO_SKIPPED_ALREADY_INVESTIGATED = {"geniohyoid_l", "hyoglossus_r"}

TARGET_CATS = {"muscle", "vessel", "nerve"}

_volume_cache: "OrderedDict[str, tuple]" = None  # set below
_manifest_cache: dict[str, dict | None] = {}
_volmap_cache: dict[str, dict | None] = {}

from collections import OrderedDict  # noqa: E402

_volume_cache = OrderedDict()
_VOLUME_CACHE_MAX = 2  # full-body CT volumes are large (multi-GB); keep at most this many
                        # resident at once. Targets are processed sorted by source path so
                        # consecutive items normally reuse the same volume anyway -- this cap
                        # is what stops memory from growing unbounded across ~150 items after
                        # an early run OOM-killed at item 74 with 5+ volumes cached at once.


def load_manifest(subject: str) -> dict | None:
    if subject not in _manifest_cache:
        p = BUILD / subject / "manifest.json"
        _manifest_cache[subject] = json.loads(p.read_text()) if p.exists() else None
    return _manifest_cache[subject]


def load_volmap(subject: str) -> dict | None:
    if subject not in _volmap_cache:
        p = BUILD / f"{subject}_volume_mapping.json"
        _volmap_cache[subject] = json.loads(p.read_text()) if p.exists() else None
    return _volmap_cache[subject]


def load_volume_cached(path_str: str):
    if path_str in _volume_cache:
        _volume_cache.move_to_end(path_str)
        return _volume_cache[path_str]
    while len(_volume_cache) >= _VOLUME_CACHE_MAX:
        _volume_cache.popitem(last=False)  # evict least-recently-used
    result = vol.load_labels(Path(path_str))
    _volume_cache[path_str] = result
    return result


def find_manifest_entries(subject: str, atlas_id: str, side_norm: str | None):
    m = load_manifest(subject)
    if m is None:
        return m, []
    matches = [s for s in m["structures"]
               if s["atlas_id"] == atlas_id and s.get("side") == side_norm]
    return m, matches


def resolve_source(subject: str, atlas_id: str, side_norm: str | None, depth: int = 0) -> dict:
    """Follow (possibly through a transfer) to a raw {kind: volume|unclear} source."""
    if depth > 4:
        return {"kind": "unclear", "reason": "transfer chain too deep (>4 hops)"}
    m, matches = find_manifest_entries(subject, atlas_id, side_norm)
    if m is None:
        return {"kind": "unclear", "reason": f"no manifest at build/vh/{subject}/manifest.json"}
    if not matches:
        return {"kind": "unclear",
                "reason": f"atlas_id={atlas_id!r} side={side_norm!r} not found in "
                          f"{subject}'s manifest ({len(m['structures'])} entries)"}
    rec = matches[0]
    if "transfer" in rec:
        origin = (rec.get("transfer") or {}).get("from")
        if not origin:
            return {"kind": "unclear",
                    "reason": f"{subject}: transfer record with no 'from' field"}
        chased = resolve_source(origin, atlas_id, side_norm, depth + 1)
        chased["chased_via"] = chased.get("chased_via", []) + [subject]
        return chased

    source_file = rec.get("source_file", "")
    if "#" not in source_file:
        return {"kind": "unclear",
                "reason": f"{subject}: unrecognized source_file {source_file!r}"}
    fname, label_str = source_file.rsplit("#", 1)
    if not re.fullmatch(r"-?\d+", label_str):
        return {"kind": "unclear",
                "reason": f"{subject}: non-numeric label suffix "
                          f"({source_file!r}) -- likely geometry recovered "
                          f"from a published viewer bundle, not a voxel mask; "
                          f"no raw source available to measure"}
    label = int(label_str)
    src_vol = m.get("source_volume")
    if not src_vol:
        return {"kind": "unclear", "reason": f"{subject}: manifest has no source_volume"}
    src_path = Path(src_vol)
    if not src_path.exists():
        return {"kind": "unclear",
                "reason": f"{subject}: source_volume {src_vol} does not exist on disk"}

    out = {"kind": "volume", "path": str(src_path), "label": label,
           "resolved_subject": subject, "label_map": m.get("label_map"),
           "smoothing_sigma": m.get("surface_smoothing_sigma_voxels")}
    if rec.get("split_from"):
        out["split_from"] = rec["split_from"]
        out["splitter"] = rec.get("splitter")
        out["split_atlas_id"] = atlas_id
    return out


def components_of_mask(mask: np.ndarray) -> tuple[int, float, list[int]]:
    """26-connected components of a binary mask.

    Cropped to the mask's own bounding box first: a structure's label
    occupies a small corner of a full-body CT volume (hundreds of millions
    of voxels), and scipy.ndimage.label's cost scales with the volume it is
    given, not the number of set voxels -- cropping first is a 10-50x speedup
    for a typical single-organ label and changes no result (padding by 1
    voxel on every side keeps components that touch the crop face from being
    clipped)."""
    from scipy import ndimage
    if not mask.any():
        return 0, 0.0, []
    coords = np.argwhere(mask)
    lo = np.maximum(coords.min(axis=0) - 1, 0)
    hi = np.minimum(coords.max(axis=0) + 2, mask.shape)
    cropped = mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    comp, n = ndimage.label(cropped, structure=np.ones((3, 3, 3), dtype=int))
    sizes = ndimage.sum(cropped, comp, index=range(1, n + 1))
    sizes = sorted((int(s) for s in sizes), reverse=True)
    main_frac = sizes[0] / sum(sizes) if sizes else 0.0
    return n, main_frac, sizes[:8]


def resolve_split_mask(src: dict) -> np.ndarray | None:
    """For a shipped piece that is one PART of a label another script split,
    reproduce the exact submask the ingestion used -- not the whole label,
    which would overstate connectivity by including sibling parts."""
    subject = src["resolved_subject"]
    volmap = load_volmap(subject)
    if volmap is None:
        return None
    entry = next((e for e in volmap["entries"]
                  if e.get("splitter") == src["splitter"]
                  and src["split_atlas_id"] in (e.get("split_parts") or {}).values()), None)
    if entry is None:
        return None
    part_name = next(p for p, tgt in entry["split_parts"].items()
                      if tgt == src["split_atlas_id"])
    splitter_fn = vol.LABEL_SPLITTERS.get(src["splitter"])
    if splitter_fn is None:
        return None
    volume, affine, _codes = load_volume_cached(src["path"])
    names = vol.load_label_names(src["label_map"])
    label_ids = {n: i for i, n in names.items()}
    try:
        produced, _notes = splitter_fn(volume, src["label"], affine, label_ids)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"    splitter {src['splitter']} failed: {exc}", file=sys.stderr)
        return None
    return produced.get(part_name)


def measure_one(group_key: str, rec: dict) -> dict:
    atlas_id, side = rec["id"], rec["side"]
    side_norm = None if side in (None, "none") else side
    subjects = rec.get("subjects") or []
    uniq_subjects = list(dict.fromkeys(s for s in subjects if s))
    if not uniq_subjects:
        return {"classification": "UNCLEAR", "reason": "no subject recorded in audit"}

    per_subject = []
    for subject in uniq_subjects:
        src = resolve_source(subject, atlas_id, side_norm)
        per_subject.append((subject, src))

    volume_sources = [(s, r) for s, r in per_subject if r["kind"] == "volume"]
    if not volume_sources:
        reasons = "; ".join(f"{s}: {r['reason']}" for s, r in per_subject)
        return {"classification": "UNCLEAR", "reason": reasons,
                "per_subject": [{"subject": s, **r} for s, r in per_subject]}

    total_n_comp = 0
    total_main_frac_num = 0
    total_main_frac_den = 0
    detail = []
    ok = True
    for subject, src in volume_sources:
        try:
            volume, affine, _codes = load_volume_cached(src["path"])
        except Exception as exc:
            detail.append({"subject": subject, "error": str(exc)})
            ok = False
            continue
        if src.get("split_from"):
            mask = resolve_split_mask(src)
            if mask is None:
                detail.append({"subject": subject,
                                "error": "could not reproduce split submask"})
                ok = False
                continue
        else:
            mask = volume == src["label"]
        n, mf, top_sizes = components_of_mask(mask)
        detail.append({
            "subject": subject, "resolved_subject": src["resolved_subject"],
            "path": src["path"], "label": src["label"],
            "smoothing_sigma": src.get("smoothing_sigma"),
            "split_from": src.get("split_from"), "splitter": src.get("splitter"),
            "n_components": n, "main_frac": round(mf, 4),
            "top_component_voxel_counts": top_sizes,
            "chased_via": src.get("chased_via", []),
        })
        total_n_comp += n
        if top_sizes:
            total_main_frac_num += top_sizes[0]
            total_main_frac_den += sum(top_sizes)

    if not ok and not detail:
        return {"classification": "UNCLEAR", "reason": "all volume sources failed to load"}

    source_main_frac = (total_main_frac_num / total_main_frac_den) if total_main_frac_den else None
    shipped_main_frac = rec["main_frac"]

    unresolved = [f"{s}: {r['reason']}" for s, r in per_subject if r["kind"] != "volume"]

    result = {
        "shipped_main_frac": shipped_main_frac,
        "shipped_n_components": rec["n_components"],
        "shipped_status": rec["status"],
        "source_main_frac": round(source_main_frac, 4) if source_main_frac is not None else None,
        "source_n_components_total": total_n_comp,
        "per_source": detail,
    }
    if unresolved:
        result["partially_unresolved"] = unresolved

    if source_main_frac is None:
        result["classification"] = "UNCLEAR"
        result["reason"] = "no usable voxel mask measured"
        return result

    gap = source_main_frac - shipped_main_frac
    result["gap_ratio"] = round(gap, 4)

    # Classification thresholds, chosen to mirror Q113/Q114's own language:
    #   - source is already close to shipped (gap small) or itself badly
    #     fragmented -> LIKELY_GENUINE (a pipeline fix cannot invent
    #     continuity the segmentation never had).
    #   - source is well connected (>=0.90) while shipped is well below it
    #     (gap >= 0.15) -> LIKELY_PIPELINE_ARTIFACT, Q113/Q114's own bug
    #     class (smoothing/decimation fragmenting an intact source).
    #   - everything else (some improvement plausible but source itself
    #     already meaningfully broken, or gap too small to be worth a fix
    #     attempt) -> UNCLEAR/marginal, left for judgement rather than
    #     forced into a bucket a single number can't responsibly decide.
    if source_main_frac >= 0.90 and gap >= 0.15:
        result["classification"] = "LIKELY_PIPELINE_ARTIFACT"
    elif source_main_frac < 0.70 or gap < 0.05:
        result["classification"] = "LIKELY_GENUINE"
    else:
        result["classification"] = "MARGINAL"
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO_ROOT / "data" / "derived" /
                                         "Q115_triage.json"))
    ap.add_argument("--only", nargs="*", help="restrict to these atlas_ids (debug)")
    args = ap.parse_args()

    audit = json.loads(AUDIT_JSON.read_text())

    targets = []
    for body in ("male", "female"):
        for key, rec in audit["bodies"][body]["structures"].items():
            if rec["cat"] not in TARGET_CATS:
                continue
            if rec["main_frac"] >= 0.99:
                continue
            if rec["id"] in ALREADY_HANDLED:
                continue
            if rec["id"] in ALSO_SKIPPED_ALREADY_INVESTIGATED:
                continue
            if args.only and rec["id"] not in args.only:
                continue
            targets.append((body, key, rec))

    def sort_key(t):
        _body, _key, rec = t
        subjects = rec.get("subjects") or []
        subject = subjects[0] if subjects else ""
        side_norm = None if rec["side"] in (None, "none") else rec["side"]
        try:
            src = resolve_source(subject, rec["id"], side_norm)
            return src.get("path", "") if src["kind"] == "volume" else "zzz_unclear"
        except Exception:
            return "zzz_unclear"

    targets.sort(key=sort_key)

    print(f"{len(targets)} candidate (id,side,body) groups to triage "
          f"(muscle/vessel/nerve, main_frac<0.99, minus Q113/Q114's already-handled set), "
          f"sorted by source volume path to minimize how often the volume cache reloads")

    out = {"source": "Q115: decimation-vs-source triage sweep for the muscle/vessel/nerve "
                      "structures Q112 found fragmented and Q113/Q114 did not already root-cause "
                      "(scripts/triage_continuity_q115.py, method: scipy.ndimage.label on each "
                      "structure's raw source label volume, 26-connectivity, compared to the "
                      "shipped bundle's own main_frac from data/derived/Q112_full_continuity_audit.json)",
           "generated_from": str(AUDIT_JSON.relative_to(REPO_ROOT)),
           "already_handled_excluded": sorted(ALREADY_HANDLED),
           "already_investigated_skipped": sorted(ALSO_SKIPPED_ALREADY_INVESTIGATED),
           "n_targets": len(targets), "results": {}}

    counts = {"LIKELY_PIPELINE_ARTIFACT": 0, "LIKELY_GENUINE": 0, "MARGINAL": 0, "UNCLEAR": 0}
    for i, (body, key, rec) in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {body} {key} (shipped main_frac {rec['main_frac']:.3f}) ...",
              flush=True)
        r = measure_one(key, rec)
        r["body"] = body
        r["id"] = rec["id"]
        r["side"] = rec["side"]
        r["cat"] = rec["cat"]
        r["name"] = rec.get("name")
        counts[r["classification"]] += 1
        out["results"][f"{body}|{key}"] = r
        print(f"    -> {r['classification']}"
              + (f" (source_main_frac={r.get('source_main_frac')}, gap={r.get('gap_ratio')})"
                 if r.get("source_main_frac") is not None else f" ({r.get('reason')})"))

        # Write incrementally: a crash (e.g. OOM on a later, larger volume)
        # should not lose already-computed results, exactly the failure this
        # loop hit once already (killed at item 74/149 with nothing saved).
        out["summary"] = dict(counts)
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, indent=2))

    out["summary"] = counts
    print("\nSUMMARY:", counts)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
