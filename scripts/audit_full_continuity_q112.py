#!/usr/bin/env python3
"""Q112: Full-bundle mesh continuity audit (every shipped structure, both bodies).

This is Q103's audit redone with the measurement method Q111 fixed: face-adjacency
connected components, main_frac = largest_component_vertices / total_vertices
(vertex-based, matching Q103/Q104/verify_vertebral_continuity.py's convention).

Unlike Q103 (44 structures, bones/vessels/cartilage only) and unlike
verify_vertebral_continuity.py (vertebrae/discs only, and pre-Q111 had the
atlas_id-dict-collision bug), this script:
  - covers EVERY structure in the LIVE, currently-published viewer bundles
    (build/viewer_m/atlas_viewer_male.html, build/viewer_f/atlas_viewer_female.html),
    read directly from their embedded <script id="bundle-json"> / <script
    id="bundle-b64"> payloads -- not the pending/unpublished rebuilds in build/vh/.
  - groups multi-piece structures (structures sharing one "id", e.g.
    lumbar_vertebrae x5, cervical_vertebrae x7, thoracic_vertebrae x12) by
    (id, side) using a list-accumulating dict, so it evaluates ALL pieces
    together -- the exact bug class Q111 found and fixed in
    verify_vertebral_continuity.py. Grouping additionally includes `side` so
    that genuinely-separate bilateral structures which happen to share one
    "id" in this bundle format (e.g. optic_n left/right, each a single
    correct piece) are never wrongly combined into one "structure" and
    scored against each other.

DATA FORMAT (build_viewer_html.py's bundle layout, reverse-engineered from the
live HTML's own decode script, not guessed):
  - `structures` is an ordered list; each entry has nv/nf (vertex/face counts
    of that ONE piece's own independently-decimated mesh) plus id/cat/side/rec.
  - `bundle-b64` decodes to a flat byte buffer holding, per structure IN THE
    SAME ORDER as `structures`, back-to-back: an Int16Array of nv*3 quantized
    positions (nv*6 bytes) then a Uint16Array of nf*3 LOCAL (0-based, that
    piece's own indexing) face vertex indices (nf*6 bytes). No gaps/padding.
  - We only need the face index arrays (topology) for continuity; positions
    are decoded byte-length only (to keep the running offset correct) and
    otherwise ignored.

For each (id, side) group with N pieces, faces are combined into one graph by
offsetting piece i's face indices by the running sum of nv over pieces
0..i-1 (mirrors a correct vertex_offset, the exact thing Q107/Q108 found
missing in the ingestion scripts). Face-adjacency (faces sharing a full edge,
i.e. 2 vertices) connected components are found with a union-find over faces;
main_frac is then computed vertex-wise like the reference script: each
component's vertex set is the union of its faces' vertices, and
main_frac = size of the largest component's vertex set / sum of all
components' vertex set sizes (matches verify_vertebral_continuity.py exactly,
including its edge-case behavior at non-manifold single-vertex pinch points,
for direct comparability).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from base64 import b64decode
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent

BUNDLES = {
    "male": REPO_ROOT / "build" / "viewer_m" / "atlas_viewer_male.html",
    "female": REPO_ROOT / "build" / "viewer_f" / "atlas_viewer_female.html",
}

CONTINUOUS_THRESHOLD = 0.99  # matches verify_vertebral_continuity.py / Q103/Q104
FRAGMENTED_THRESHOLD = 0.50  # below this -> SEVERE_BREAK


def extract_bundle(html_path: Path) -> tuple[dict, bytes]:
    """Pull the embedded bundle JSON + raw binary payload straight out of the
    live viewer HTML (no dependency on any sibling bundle.json/bundle.bin --
    those are build byproducts; this reads what's actually published)."""
    html = html_path.read_text(encoding="utf-8")

    m_json = re.search(r'<script id="bundle-json"[^>]*>(.*?)</script>', html, re.S)
    if not m_json:
        raise ValueError(f"{html_path}: could not find <script id=\"bundle-json\">")
    bundle = json.loads(m_json.group(1))

    m_b64 = re.search(r'<script id="bundle-b64"[^>]*>(.*?)</script>', html, re.S)
    if not m_b64:
        raise ValueError(f"{html_path}: could not find <script id=\"bundle-b64\">")
    raw = b64decode(m_b64.group(1).strip())

    return bundle, raw


def iter_piece_faces(bundle: dict, raw: bytes):
    """Yield (structure_dict, local_faces[nf,3] uint32, nv) for each structure,
    in bundle order, replicating the HTML decoder's own offset arithmetic
    exactly (Int16 positions then Uint16 faces, no padding)."""
    offset = 0
    for s in bundle["structures"]:
        nv, nf = s["nv"], s["nf"]
        pos_bytes = nv * 3 * 2
        idx_bytes = nf * 3 * 2
        faces_local = np.frombuffer(
            raw, dtype="<u2", count=nf * 3, offset=offset + pos_bytes
        ).reshape(-1, 3).astype(np.uint32)
        offset += pos_bytes + idx_bytes
        yield s, faces_local, nv
    if offset != len(raw):
        raise ValueError(
            f"byte accounting mismatch: consumed {offset}, buffer is {len(raw)}"
        )


def union_find_components(n: int, edges_a: np.ndarray, edges_b: np.ndarray) -> np.ndarray:
    """Plain union-find over `n` face indices, unioning pairs (edges_a[i], edges_b[i])."""
    parent = np.arange(n)

    def find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    for a, b in zip(edges_a.tolist(), edges_b.tolist()):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    return np.array([find(i) for i in range(n)])


def analyze_group(pieces: list[tuple[dict, np.ndarray, int]]) -> dict:
    """Face-adjacency continuity for one (id, side) group of one or more pieces."""
    all_faces = []
    vertex_offset = 0
    for _s, faces_local, nv in pieces:
        all_faces.append(faces_local + vertex_offset)
        vertex_offset += nv
    faces = np.concatenate(all_faces, axis=0) if len(all_faces) > 1 else all_faces[0]
    n_faces = faces.shape[0]

    if n_faces == 0:
        return {
            "status": "ERROR",
            "error": "zero faces",
            "n_pieces": len(pieces),
        }

    # Build the 3 edges per face as (min_vertex, max_vertex) pairs, then find
    # all faces sharing a full edge (both vertices) and union them.
    e0 = np.sort(faces[:, [0, 1]], axis=1)
    e1 = np.sort(faces[:, [1, 2]], axis=1)
    e2 = np.sort(faces[:, [2, 0]], axis=1)
    edges = np.concatenate([e0, e1, e2], axis=0)
    face_of_edge = np.tile(np.arange(n_faces), 3)

    # Encode each edge as one integer key to sort/group cheaply.
    max_v = int(faces.max()) + 1
    keys = edges[:, 0].astype(np.int64) * max_v + edges[:, 1].astype(np.int64)
    order = np.argsort(keys, kind="stable")
    keys_sorted = keys[order]
    faces_sorted = face_of_edge[order]

    # For each run of equal keys (an edge shared by >=2 faces), union the
    # first face in the run with every other face in the run.
    boundaries = np.flatnonzero(np.diff(keys_sorted)) + 1
    run_starts = np.concatenate([[0], boundaries])
    run_ends = np.concatenate([boundaries, [len(keys_sorted)]])

    union_a = []
    union_b = []
    for start, end in zip(run_starts, run_ends):
        if end - start >= 2:
            first = faces_sorted[start]
            for k in range(start + 1, end):
                union_a.append(first)
                union_b.append(faces_sorted[k])

    labels = union_find_components(
        n_faces,
        np.array(union_a, dtype=np.int64),
        np.array(union_b, dtype=np.int64),
    )

    # Vertex-based main_frac, matching verify_vertebral_continuity.py exactly:
    # collect each face's 3 (global) vertices into its component's vertex set,
    # then main_frac = largest set size / sum of all set sizes.
    comp_ids, comp_inverse = np.unique(labels, return_inverse=True)
    n_components = len(comp_ids)

    comp_vertex_sets: dict[int, set] = defaultdict(set)
    flat_verts = faces.reshape(-1)
    flat_comp = np.repeat(comp_inverse, 3)
    for v, c in zip(flat_verts.tolist(), flat_comp.tolist()):
        comp_vertex_sets[c].add(v)

    sizes = {c: len(vs) for c, vs in comp_vertex_sets.items()}
    largest = max(sizes.values())
    total = sum(sizes.values())
    main_frac = largest / total if total else 0.0

    if main_frac >= CONTINUOUS_THRESHOLD:
        status = "CONTINUOUS"
    elif main_frac >= FRAGMENTED_THRESHOLD:
        status = "FRAGMENTED"
    else:
        status = "SEVERE_BREAK"

    return {
        "status": status,
        "main_frac": float(main_frac),
        "n_components": int(n_components),
        "total_vertices": int(total),
        "largest_component_vertices": int(largest),
        "n_pieces": len(pieces),
        "n_faces": int(n_faces),
    }


def audit_body(name: str, html_path: Path) -> dict:
    bundle, raw = extract_bundle(html_path)

    groups: dict[tuple[str, str], list] = defaultdict(list)
    meta: dict[tuple[str, str], dict] = {}
    for s, faces_local, nv in iter_piece_faces(bundle, raw):
        side = s.get("side") or "none"
        key = (s["id"], side)
        groups[key].append((s, faces_local, nv))
        if key not in meta:
            meta[key] = {
                "id": s["id"],
                "side": side,
                "cat": s["cat"],
                "name": s.get("rec", {}).get("name"),
                "subjects": [],
            }
        meta[key]["subjects"].append(s.get("subject"))

    results = {}
    cat_mismatch = []
    for key, pieces in groups.items():
        cats = {p[0]["cat"] for p in pieces}
        if len(cats) > 1:
            cat_mismatch.append({"key": list(key), "cats": sorted(cats)})
        r = analyze_group(pieces)
        r.update(meta[key])
        results[f"{key[0]}|{key[1]}"] = r

    return {
        "subject": bundle.get("subject"),
        "frame": bundle.get("frame"),
        "html_path": str(html_path.relative_to(REPO_ROOT)),
        "html_mtime": html_path.stat().st_mtime,
        "n_structures_raw": len(bundle["structures"]),
        "n_groups": len(results),
        "cat_mismatches": cat_mismatch,
        "structures": results,
    }


def summarize(body_results: dict) -> dict:
    by_status = defaultdict(int)
    by_cat_status = defaultdict(lambda: defaultdict(int))
    for r in body_results["structures"].values():
        by_status[r["status"]] += 1
        by_cat_status[r["cat"]][r["status"]] += 1
    return {
        "by_status": dict(by_status),
        "by_category_status": {k: dict(v) for k, v in by_cat_status.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "data" / "derived" / "Q112_full_continuity_audit.json"),
    )
    args = parser.parse_args()

    report = {
        "audit_timestamp": "2026-09-22",
        "source": "Q112: Full mesh continuity audit of every shipped structure, both bodies",
        "methodology": (
            "Face-adjacency connected components with vertex-based main_frac metric "
            "(largest_component_vertices / total_vertices), matching Q103/"
            "verify_vertebral_continuity.py post-Q111-fix. Multi-piece structures "
            "(sharing one bundle 'id') are grouped by (id, side) and ALL pieces are "
            "combined into one face graph with correct per-piece vertex offsetting "
            "before computing components -- avoiding the atlas_id-dict-collision bug "
            "Q111 found and fixed."
        ),
        "bundles_audited": "LIVE published bundles as embedded in build/viewer_m/"
        "atlas_viewer_male.html and build/viewer_f/atlas_viewer_female.html "
        "(NOT the pending Q108/Q109/Q111 rebuilds; see PROJECT_STATE.md Q112 entry "
        "for what that distinction does and does not mean here).",
        "thresholds": {
            "continuous_min_main_frac": CONTINUOUS_THRESHOLD,
            "fragmented_min_main_frac": FRAGMENTED_THRESHOLD,
        },
        "bodies": {},
    }

    for name, path in BUNDLES.items():
        print(f"Auditing {name} ({path})...")
        body = audit_body(name, path)
        body["summary"] = summarize(body)
        report["bodies"][name] = body
        print(
            f"  {body['n_structures_raw']} raw structure entries -> "
            f"{body['n_groups']} groups; status counts: {body['summary']['by_status']}"
        )
        if body["cat_mismatches"]:
            print(f"  WARNING: category mismatch within group: {body['cat_mismatches']}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nWrote {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
