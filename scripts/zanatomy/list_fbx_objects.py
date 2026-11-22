"""Q186: list EVERY object (meshes, pin markers, empties/group nodes) in every FBX of the pinned
Z-Anatomy release, so the viewer inventory audit (scripts/zanatomy/zan_inventory_audit.py) can account
for each source object, not only the ones extract_fbx.py kept. Metadata only (no geometry).

Run with the bpy venv (see extract_fbx.py):
    build/.venv-bpy/bin/python3 scripts/zanatomy/list_fbx_objects.py [--out build/zanatomy/source_objects.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy  # noqa: F401  (bpy venv only)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_fbx import EXPECTED_COMMIT, SYSTEMS, check_commit  # noqa: E402

REFERENCE_FILE = "References100.fbx"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zanatomy-root", default="/home/user/lluisv/z-anatomy")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "build/zanatomy/source_objects.json"))
    a = ap.parse_args(argv)
    root = Path(a.zanatomy_root)
    files = {**{fn: sysname for sysname, fn in SYSTEMS.items()}, REFERENCE_FILE: "References"}
    rows = []
    for fn, sysname in sorted(files.items()):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(root / "Resources/Models/FBX" / fn))
        for ob in bpy.data.objects:
            r = {"name": ob.name, "file": fn, "system": sysname, "type": ob.type,
                 "parent": ob.parent.name if ob.parent else None}
            if ob.type == "MESH":
                r["vertex_count"] = len(ob.data.vertices)
                r["face_count"] = len(ob.data.polygons)
            rows.append(r)
        print(fn, sum(1 for r in rows if r["file"] == fn))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"commit": check_commit(root, EXPECTED_COMMIT), "objects": rows}))
    print("wrote", a.out, len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
