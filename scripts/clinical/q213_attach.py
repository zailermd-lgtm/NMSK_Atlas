#!/usr/bin/env python3
"""Q213: attachment check of the TARGET MUSCLES on the two female pages: for every muscle the distance of its mesh to the bone(s) its card names as origin / insertion
(rec.origin / rec.insertion, e.g. "scapula_r: ...") and whether a named bone is on the other side of the body (L/R swap).  Read-only.  -> data/derived/Q213_attachment_check.json

    python3 scripts/clinical/q213_attach.py [--after]
Note: her own meshes are muscle bellies (tendons are not modelled), so insertion distances of 50-190 mm are the tendon length, not an error; the Z page includes the tendons."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import q213_audit as Q  # noqa: E402

REPO = Q.REPO


def recs(key):
    p = Q.PAGES.get(key) or Q.PAGES_AFTER[key]
    h = Path(p["html"]).read_text(encoding="utf-8")
    if "bin" in p:
        b = json.loads(re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', h, re.S).group(1))
        return {e["id"]: e["rec"] for e in b["structures"]}
    i = h.find("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    return {m["id"]: m.get("rec") or {} for m in json.JSONDecoder().raw_decode(h[i:])[0]["meshes"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", action="store_true")
    a = ap.parse_args()
    aud = json.loads((REPO / ("data/derived/Q213_target_muscle_audit_after.json" if a.after else "data/derived/Q213_target_muscle_audit.json")).read_text())
    keys = {"vhf": "vhf_q213" if a.after else "vhf", "zan_f": "zan_f_q213" if a.after else "zan_f"}
    out = {}
    for vk, pk in keys.items():
        me = Q.load(pk)[0]
        R = recs(pk)
        for k, e in aud.items():
            ids = e["ids"][vk]
            if not ids:
                continue
            V = np.vstack([me[i]["v"] for i in ids])
            rec = R.get(ids[0], {})
            res = {}
            for role in ("origin", "insertion"):
                bs = [b for b in re.findall(r"\b([a-z_0-9]+_(?:r|l)):", rec.get(role) or "") if b in me]
                if not bs:
                    continue
                d = cKDTree(np.vstack([me[b]["v"] for b in bs])).query(V)[0]
                res[role] = {"bones": bs, "min_mm": round(float(d.min()), 1), "p5_mm": round(float(np.percentile(d, 5)), 1),
                             "side_mismatch": any(not b.endswith("_" + k[-1]) for b in bs)}
            out[f"{vk}|{k}"] = res
    flagged = {k: v for k, v in out.items() if any(r["side_mismatch"] or r["min_mm"] > 12 for r in v.values())}
    res = {"n_checked": len(out), "side_mismatch": [k for k, v in out.items() if any(r["side_mismatch"] for r in v.values())], "n_gt_12mm": len(flagged), "rows": out}
    (REPO / "data/derived" / ("Q213_attachment_check_after.json" if a.after else "Q213_attachment_check.json")).write_text(json.dumps(res, indent=1) + "\n")
    print(res["n_checked"], "checked;", "side mismatches:", res["side_mismatch"], "; ends > 12 mm from a named bone:", res["n_gt_12mm"])


if __name__ == "__main__":
    main()
