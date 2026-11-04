"""Q299: a FRESH pose rig for one page, written outside the repository.

    python3 scripts/anatomy/q299/fresh_rig299.py KEY PAGE_DIR OUT.json

`scripts/anatomy/q241/make_pose_rig.py KEY` writes straight into `data/anatomy/`, which would overwrite the committed
rig before the Q299 splice has decided what to take from it (and this working tree is shared with another round). This
calls the same `build()` / `pack()` of that module and writes the result where it is asked to, so the committed file is
touched exactly once, by `fix_contain299.py rig`.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))

key, page_dir, out = sys.argv[1], sys.argv[2], sys.argv[3]
os.environ["Q241_SRC_" + key] = str(Path(page_dir).resolve())
import make_pose_rig as MP  # noqa: E402

payload, blob, report, _ = MP.build(key)
p, nj, nw = MP.pack(payload, blob)
Path(out).parent.mkdir(parents=True, exist_ok=True)
Path(out).write_text(json.dumps(dict(schema="nmsk.pose_rig/1", key=key, label=MP.MD.LABEL[key], rig=payload,
                                     weights_zlib_b64=p["w"]), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
print(key, "fresh rig ->", out, "segments", report["counts"]["segments"],
      "skinned", report["counts"]["skinned"], "of", report["counts"]["structures"], "seconds", report["seconds"], flush=True)
