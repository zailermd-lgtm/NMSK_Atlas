#!/usr/bin/env python3
"""Q293: a fresh make_pose_rig run on a NEW page dir, written to OUT (the committed rig is not touched; pages_q293.py rig splices from it).

    python3 scripts/anatomy/q293/fresh_rig.py KEY PAGE_DIR OUT.json"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q241"))
key, d, out = sys.argv[1], sys.argv[2], sys.argv[3]
os.environ["Q241_SRC_" + key] = str(Path(d).resolve())
import make_pose_rig as MPR  # noqa: E402
payload, blob, report, _ = MPR.build(key)
p, nj, nw = MPR.pack(payload, blob)
Path(out).write_text(json.dumps(dict(schema="nmsk.pose_rig/1", key=key, label=MPR.MD.LABEL[key], rig=payload, weights_zlib_b64=p["w"]), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
print(key, "fresh rig", payload["count"], "structures,", len(payload["skin"]), "skinned,", report["seconds"], "s")
