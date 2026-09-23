"""Q141 phase 1: extract per-object triangle meshes from the Z-Anatomy FBX release.

Z-Anatomy (CC BY-SA 4.0; models by the Z-Anatomy project, BodyParts3D upstream credited
in its own LICENSE, app by Lluis Vinent Juanico) is cloned read-only at a path this
script takes as an argument (default: /home/user/lluisv/z-anatomy), pinned at commit
6c7f9016bd5899ac8edafd31b9900c151df42ed6. See third_party/z-anatomy/ for the licence
text, NOTICE and the layer-split rule, and docs/GEOMETRY_SOURCES.md for the owner
decision that lets this material enter the repo at all (2026-09-23).

Route chosen: `bpy` (Blender's own Python API), NOT a hand-rolled binary-FBX reader.
`pip install bpy==5.0.1` installed cleanly for this machine's Python 3.11 (cp311 wheel,
374 MB, no compiler needed) into an ISOLATED venv (build/.venv-bpy/), so it never
touches the project's own numpy pin (bpy requires numpy<2.0; the project runs 2.4.6).
bpy's own FBX importer already resolves everything the task called out as the
alternative hand-rolled reader's job -- node tree, Geometry Vertices / triangulated
loops, Model names, Lcl Translation/Rotation/Scaling + PreRotation, Model->Model
parenting, and GlobalSettings UnitScaleFactor/axis convention -- into each object's
`matrix_world` and `mesh.vertices`/`mesh.loop_triangles`, in Blender's internal frame
(metres, Z-up). This script only has to apply matrix_world and multiply by 1000 for mm.

This script MUST be run with the bpy venv's interpreter, not the project's main one:

    build/.venv-bpy/bin/python3 scripts/zanatomy/extract_fbx.py [options]

(create the venv first if it does not exist: `python3 -m venv build/.venv-bpy &&
build/.venv-bpy/bin/pip install bpy==5.0.1`). It does not import anything from this
project's own `engine`/`scripts` packages, precisely so it has no dependency on the
project's numpy version -- it is a standalone extraction step whose only committed
output is data/derived/zanatomy_inventory.json (small) and this file. Per-object
meshes are written to build/zanatomy/<system>/<safe_name>.npz -- gitignored, never
committed, reproducible from the pinned clone + commit by rerunning this script.

Z-Anatomy's own naming convention marks small (~8-90 vertex) helper objects with a
trailing ``.i``/``.j`` suffix -- confirmed by inspection to be annotation/leader-line
pin markers for sub-features (e.g. "(Third trochanter).i"), not tissue surface
geometry -- and marks left/right copies of a real structure or sub-part with
``.l``/``.r``/``.el``/``.er``/``.e1l``/``.e1r``/... suffixes. --min-vertices (default
12) drops the pin markers; every dropped object is still counted in the report so the
exclusion is visible, not silent.

Usage:
    build/.venv-bpy/bin/python3 scripts/zanatomy/extract_fbx.py \\
        --zanatomy-root /home/user/lluisv/z-anatomy \\
        --commit 6c7f9016bd5899ac8edafd31b9900c151df42ed6 \\
        --out-dir build/zanatomy \\
        --inventory data/derived/zanatomy_inventory.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    import bpy
except ImportError:  # pragma: no cover - guidance path, not exercised by pytest
    sys.exit(
        "error: this script needs `bpy` (Blender's Python API) and must be run with\n"
        "the isolated venv's interpreter, not the project's main Python:\n\n"
        "    python3 -m venv build/.venv-bpy\n"
        "    build/.venv-bpy/bin/pip install bpy==5.0.1\n"
        "    build/.venv-bpy/bin/python3 scripts/zanatomy/extract_fbx.py ...\n\n"
        "It is isolated deliberately: bpy pins numpy<2.0 and this project runs numpy 2.x."
    )

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]

# system label -> FBX filename under <zanatomy-root>/Resources/Models/FBX/
# "Regions of human body100.fbx" and "References100.fbx" are deliberately excluded:
# they are diagram overlays (axillary lines, movement-direction arrows, cross-section
# planes -- confirmed by inspection, e.g. "Abduction", "Cross Section X") rather than
# tissue geometry, and map to none of this project's data/ tissue directories.
SYSTEMS = {
    "Muscular": "MuscularSystem100.fbx",
    "Nervous": "NervousSystem100.fbx",
    "Skeletal": "SkeletalSystem100.fbx",
    "CardioVascular": "CardioVascular41.fbx",
    "Joints": "Joints100.fbx",
    "Visceral": "VisceralSystem100.fbx",
    "Lymphoid": "LymphoidOrgans100.fbx",
}

EXPECTED_COMMIT = "6c7f9016bd5899ac8edafd31b9900c151df42ed6"

# Objects the release's own LICENSE / credits doc (Resources/Models/License.txt)
# states are under a DIFFERENT, non-commercial licence than the rest of the CC BY-SA
# 4.0 release: "Anatomy of the Inner Ear" (CC BY-NC-SA 4.0, Univ. of Dundee) and
# "Kidney" (CC BY-NC 4.0, lissiecowley). NC is incompatible with this project's
# commercial use regardless of the owner's CC BY-SA decision, so anything matching
# these name patterns is extracted (for inventory completeness) but flagged
# license="CC-BY-NC-4.0-or-CC-BY-NC-SA-4.0 (EXCLUDED, non-commercial)" and must never
# be used past phase 1 cataloguing.
NC_NAME_PATTERNS = [
    re.compile(r"\bkidney\b", re.I),
    re.compile(r"\brenal\b", re.I),
    re.compile(r"\bcochlea", re.I),
    re.compile(r"\bvestibule\b", re.I),
    re.compile(r"\bvestibular\b", re.I),
    re.compile(r"\bsemicircular duct", re.I),
    re.compile(r"\bsemicircular canal", re.I),
    re.compile(r"\binner ear\b", re.I),
    re.compile(r"\bmembranous labyrinth", re.I),
    re.compile(r"\bbony labyrinth", re.I),
    re.compile(r"\bosseous labyrinth", re.I),
    re.compile(r"\bendolymphatic", re.I),
]

# Trailing dot-suffix -> side, per the naming convention documented above.
_LEFT_SUFFIXES = {"l", "el", "ol", "e1l", "e2l", "e3l", "o1l", "o2l", "o3l"}
_RIGHT_SUFFIXES = {"r", "er", "or", "e1r", "e2r", "e3r", "o1r", "o2r", "o3r"}
_PIN_SUFFIXES = {"i", "j"}

_SUFFIX_RE = re.compile(r"\.([A-Za-z0-9]+)$")


def split_suffix(name: str) -> tuple[str, str | None]:
    """('Vastus lateralis muscle.l', 'l') -> ('Vastus lateralis muscle', 'l')."""
    m = _SUFFIX_RE.search(name)
    if not m:
        return name, None
    return name[: m.start()], m.group(1).lower()


def infer_side(suffix: str | None) -> str | None:
    if suffix in _LEFT_SUFFIXES:
        return "left"
    if suffix in _RIGHT_SUFFIXES:
        return "right"
    return None


def is_pin_marker(suffix: str | None) -> bool:
    return suffix in _PIN_SUFFIXES


def nc_flag(base_name: str) -> str | None:
    for pat in NC_NAME_PATTERNS:
        if pat.search(base_name):
            return "CC-BY-NC-4.0-or-CC-BY-NC-SA-4.0 (EXCLUDED, non-commercial per Resources/Models/License.txt)"
    return None


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "unnamed"


def extract_object(obj) -> dict:
    """World-space vertices (mm) and triangulated faces for one mesh object."""
    mesh = obj.data
    mesh.calc_loop_triangles()

    n_verts = len(mesh.vertices)
    flat = np.empty(n_verts * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", flat)
    local = flat.reshape(n_verts, 3)

    mw = np.array(obj.matrix_world, dtype=np.float64)  # 4x4
    homogeneous = np.hstack([local, np.ones((n_verts, 1))])
    world_m = (homogeneous @ mw.T)[:, :3]
    world_mm = (world_m * 1000.0).astype(np.float32)

    n_tris = len(mesh.loop_triangles)
    tri_flat = np.empty(n_tris * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("vertices", tri_flat)
    faces = tri_flat.reshape(n_tris, 3).astype(np.int32)

    return {"vertices_mm": world_mm, "faces": faces}


def check_commit(zanatomy_root: Path, expected: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(zanatomy_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception as exc:  # pragma: no cover - environment problem, not logic
        print(f"warning: could not read git commit at {zanatomy_root}: {exc}")
        return "unknown"
    if out != expected:
        print(f"warning: {zanatomy_root} is at {out}, expected pinned commit {expected} "
              f"-- extraction may not match what was sanity-checked")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--zanatomy-root", default="/home/user/lluisv/z-anatomy")
    ap.add_argument("--commit", default=EXPECTED_COMMIT)
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "build" / "zanatomy"),
                     help="gitignored directory for per-object .npz meshes")
    ap.add_argument("--inventory", default=str(REPO_ROOT / "data" / "derived" / "zanatomy_inventory.json"))
    ap.add_argument("--min-vertices", type=int, default=12,
                     help="objects with fewer vertices than this are annotation pin "
                          "markers (see module docstring), excluded from the kept set")
    ap.add_argument("--systems", nargs="+", choices=sorted(SYSTEMS), default=sorted(SYSTEMS))
    ap.add_argument("--no-write-meshes", action="store_true",
                     help="build the inventory/sanity report only, skip writing .npz files")
    args = ap.parse_args(argv)

    zanatomy_root = Path(args.zanatomy_root)
    fbx_dir = zanatomy_root / "Resources" / "Models" / "FBX"
    out_dir = Path(args.out_dir)
    commit = check_commit(zanatomy_root, args.commit)

    objects = []
    system_stats = {}
    for system in args.systems:
        fbx_path = fbx_dir / SYSTEMS[system]
        if not fbx_path.exists():
            print(f"skipping {system}: {fbx_path} not found")
            continue
        t0 = time.time()
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(fbx_path))
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]

        kept = excluded_pins = nc_flagged = 0
        sys_dir = out_dir / system
        if not args.no_write_meshes:
            sys_dir.mkdir(parents=True, exist_ok=True)

        for obj in meshes:
            base_name, suffix = split_suffix(obj.name)
            pin = is_pin_marker(suffix)
            n_verts = len(obj.data.vertices)
            if pin or n_verts < args.min_vertices:
                excluded_pins += 1
                continue

            side = infer_side(suffix)
            data = extract_object(obj)
            verts = data["vertices_mm"]
            bbox_min = verts.min(axis=0).tolist()
            bbox_max = verts.max(axis=0).tolist()
            license_flag = nc_flag(base_name)
            if license_flag:
                nc_flagged += 1

            record = {
                # base_name is `name` with the trailing dot-suffix removed (see
                # split_suffix() above) and mesh_file is always
                # build/<out-dir-relative>/<system>/<safe_filename(name)>.npz --
                # both omitted here to keep this committed inventory small; both
                # are cheap to recompute from `name`/`system` and this script's
                # own split_suffix()/safe_filename() when needed (map_names.py does).
                "name": obj.name,
                "suffix": suffix,
                "system": system,
                "side": side,
                "vertex_count": int(len(verts)),
                "face_count": int(len(data["faces"])),
                "bbox_min_mm": [round(v, 1) for v in bbox_min],
                "bbox_max_mm": [round(v, 1) for v in bbox_max],
                "license": license_flag or "CC-BY-SA-4.0",
            }
            if not args.no_write_meshes:
                mesh_path = sys_dir / f"{safe_filename(obj.name)}.npz"
                np.savez_compressed(mesh_path, vertices_mm=verts, faces=data["faces"])
            objects.append(record)
            kept += 1

        dt = round(time.time() - t0, 1)
        system_stats[system] = {
            "source_file": str((fbx_path).relative_to(zanatomy_root)),
            "total_mesh_objects": len(meshes),
            "kept": kept,
            "excluded_pin_markers": excluded_pins,
            "nc_flagged": nc_flagged,
            "seconds": dt,
        }
        print(f"{system}: {len(meshes)} mesh objects, kept {kept}, "
              f"excluded {excluded_pins} pin markers, {nc_flagged} NC-flagged ({dt}s)")

    # --- sanity checks (Q141 item 3): catch transform bugs before anything downstream
    # trusts this frame. ---
    def obj_by_name(name):
        for o in objects:
            if o["name"] == name:
                return o
        return None

    def span_z(rec):
        return rec["bbox_max_mm"][2] - rec["bbox_min_mm"][2] if rec else None

    femur_l, femur_r = obj_by_name("Femur.l"), obj_by_name("Femur.r")
    humerus_l, humerus_r = obj_by_name("Humerus.l"), obj_by_name("Humerus.r")

    skeletal_objs = [o for o in objects if o["system"] == "Skeletal"]
    # Exclude the diagram cross-section planes (present even inside SkeletalSystem100
    # as reference geometry) from the whole-skeleton height measurement.
    real_bones = [o for o in skeletal_objs if "cross section" not in o["name"].lower()]
    if real_bones:
        z_min = min(o["bbox_min_mm"][2] for o in real_bones)
        z_max = max(o["bbox_max_mm"][2] for o in real_bones)
        skeleton_height_mm = round(z_max - z_min, 1)
    else:
        skeleton_height_mm = None

    radial_names = sorted(o["name"] for o in objects if "radial nerve" in o["name"].lower())

    mirror_ok = None
    if femur_l and femur_r:
        mirror_ok = abs(span_z(femur_l) - span_z(femur_r)) < 1.0

    sanity = {
        "femur_length_mm": {"left": round(span_z(femur_l), 1) if femur_l else None,
                             "right": round(span_z(femur_r), 1) if femur_r else None,
                             "expected_range_mm": [400, 500]},
        "humerus_length_mm": {"left": round(span_z(humerus_l), 1) if humerus_l else None,
                               "right": round(span_z(humerus_r), 1) if humerus_r else None,
                               "expected_range_mm": [300, 340]},
        "skeleton_height_mm": {"value": skeleton_height_mm, "expected_range_mm": [1600, 1800],
                                "note": "z-span of every Skeletal-system object except the "
                                        "diagram 'Cross Section X/Y/Z' reference planes"},
        "left_right_mirror_femur_within_1mm": mirror_ok,
        "muscle_sits_on_bone_check": None,  # filled below if both systems were extracted
        "radial_nerve_present": bool(radial_names),
        "radial_nerve_objects": radial_names,
    }

    vastus_l = obj_by_name("Vastus lateralis muscle.l")
    if vastus_l and femur_l:
        overlap = not (vastus_l["bbox_max_mm"][2] < femur_l["bbox_min_mm"][2] or
                        vastus_l["bbox_min_mm"][2] > femur_l["bbox_max_mm"][2])
        sanity["muscle_sits_on_bone_check"] = {
            "vastus_lateralis_l_z_mm": [round(v, 1) for v in
                                         (vastus_l["bbox_min_mm"][2], vastus_l["bbox_max_mm"][2])],
            "femur_l_z_mm": [round(v, 1) for v in
                              (femur_l["bbox_min_mm"][2], femur_l["bbox_max_mm"][2])],
            "z_ranges_overlap": overlap,
            "note": "Muscular and Skeletal systems were extracted into the same run and "
                    "share one coordinate frame iff this is true, since neither FBX carries "
                    "its own separate origin -- both come from bpy's single import each, and "
                    "Z-Anatomy authors the whole body in one Blender scene.",
        }

    for line in [
        f"femur length L/R (mm): {sanity['femur_length_mm']}",
        f"humerus length L/R (mm): {sanity['humerus_length_mm']}",
        f"skeleton height (mm): {sanity['skeleton_height_mm']}",
        f"left/right femur mirror within 1mm: {mirror_ok}",
        f"radial nerve present: {sanity['radial_nerve_present']} ({radial_names})",
    ]:
        print(line)

    inventory = {
        "source": (
            f"Q141 (2026-09-23): phase-1 extraction of Z-Anatomy (CC BY-SA 4.0) FBX geometry "
            f"via scripts/zanatomy/extract_fbx.py, run with bpy {'.'.join(map(str, bpy.app.version))} "
            f"in an isolated venv (build/.venv-bpy). Z-Anatomy clone: {zanatomy_root}, "
            f"commit {commit} (pinned: {args.commit}). See third_party/z-anatomy/ for licence "
            f"and attribution and docs/GEOMETRY_SOURCES.md for the owner decision permitting "
            f"this material into the repo. Per-object meshes are NOT committed (build/ is "
            f"gitignored); this inventory and scripts/zanatomy/extract_fbx.py are the "
            f"reproducible record."
        ),
        "generated": "2026-09-23",
        "zanatomy_root": str(zanatomy_root),
        "zanatomy_commit": commit,
        "zanatomy_commit_pinned": args.commit,
        "extraction_route": (
            "bpy (Blender's Python API), NOT a hand-rolled binary-FBX reader: "
            "`pip install bpy==5.0.1` installed cleanly for this Python 3.11 (cp311 "
            "wheel) into build/.venv-bpy/, isolated from the project's main venv because "
            "bpy pins numpy<2.0 and the project runs numpy 2.x. bpy.ops.import_scene.fbx "
            "resolves the FBX node tree, geometry, transforms (Lcl "
            "Translation/Rotation/Scaling, PreRotation), Model->Model parenting and "
            "GlobalSettings unit scale/axis convention into each object's matrix_world; "
            "vertices are read via matrix_world @ local_co, faces via "
            "mesh.loop_triangles (already triangulated), and metres are converted to "
            "millimetres by *1000."
        ),
        "min_vertices_kept": args.min_vertices,
        "excluded_non_tissue_systems": {
            "Regions of human body100.fbx": "diagram overlay geometry (axillary lines, "
                "movement-direction arrows) -- not tissue, maps to no data/ tissue directory",
            "References100.fbx": "reference planes/lines/cross-sections for the interactive "
                "app's own UI -- not tissue",
        },
        "nc_licensed_name_patterns": [p.pattern for p in NC_NAME_PATTERNS],
        "nc_licensing_note": (
            "Resources/Models/License.txt (in the pinned clone) states most of the release "
            "is CC BY-SA 4.0 (derivative of BodyParts3D, Database Center for Life Science, "
            "CC-BY-SA 2.1 Japan -- both credits required together) BUT explicitly carries "
            "non-commercial exceptions: 'Anatomy of the Inner Ear' (Univ. of Dundee, "
            "CC-BY-NC-SA 4.0) and 'Kidney' (lissiecowley, CC-BY-NC 4.0). Objects matching "
            "nc_licensed_name_patterns are extracted here for inventory completeness only "
            "and are flagged license!=\"CC-BY-SA-4.0\" -- they must never be used past this "
            "phase-1 catalogue in a commercial product."
        ),
        "systems": system_stats,
        "total_objects_kept": len(objects),
        "sanity_checks": sanity,
        "objects": objects,
    }

    inv_path = Path(args.inventory)
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    inv_path.write_text(json.dumps(inventory, indent=1))
    print(f"\nwrote {inv_path} ({len(objects)} objects)")


if __name__ == "__main__":
    main()
