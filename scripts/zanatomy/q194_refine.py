"""Q194 build hook (--q194-refine): bounded post-gap-closure refinements of the female Z-Anatomy viewer.  Everything not listed in the returned report stays bit-identical.

  1. LEFT FOREARM structures placed with her photograph-fitted left radius / ulna and her left-forearm cryosection photographs (scripts/zanatomy/q194_forearm.py)
  2. RIGHT FOREARM muscles onto her own-model forearm labels, hand / trunk leftovers (q194_forearm.py, q194_hand_trunk.py, q194_separate.py)

The work runs in a CHILD process (`--child`): the build process already holds ~10 GB when the hook starts and the first full build died here (killed, no traceback) when the
neighbour-separation meshes were added on top; the child needs only the pending meshes, which are passed through an npz and the results (changed vertices, shipped meshes,
card notes, report) come back the same way.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
LEFT_FIT = REPO / "data" / "derived" / "Q192_left_hand_fit.json"


def refine_core(by: dict, raw: dict, decimate_fn, log=print) -> dict:
    """by: {id: {"v","f","cat","fit_note"?}} (mutated), raw: {id: Z source vertices}"""
    from scripts.transfer.zan_to_vhf_whole_body import DEFAULT_REPORT
    from scripts.zanatomy import q194_forearm as F
    from scripts.zanatomy import q194_hand_trunk as HT
    regions = json.loads(DEFAULT_REPORT.read_text())["region_of_structure"]
    rep = {"rule": "scripts/zanatomy/q194_refine.py"}
    rep["left_forearm"] = F.refine_left_forearm(by, raw, json.loads(LEFT_FIT.read_text()), regions, log=log)
    rep.update(HT.refine(by, raw, regions, decimate_fn=decimate_fn, log=log))
    return rep


def refine_pending(pending: list[dict], raw: dict, budget_scale=1.0, category_scale=None, log=print, in_process=False) -> dict:
    """build hook: moves / annotates the pending meshes in place; returns the report"""
    if in_process:
        from scripts.zanatomy import build_zan_atlas_viewer as B
        by = {p["mesh_id"]: p for p in pending}
        sc = category_scale or {}
        def dec(v, f, i, c):
            dv, df = B.decimate(v, f, i, c, sc.get(c, budget_scale), prepped=True)
            return dv, B.outward_if_closed(dv, df)
        return refine_core(by, {k: np.asarray(v, float) for k, v in raw.items()}, dec, log=log)
    import ctypes
    import gc
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except OSError:
        pass
    rss = [l for l in Path("/proc/self/status").read_text().splitlines() if l.startswith(("VmRSS", "VmHWM"))]
    log(f"  Q194: build process before the child: {' / '.join(x.split(':')[0] + x.split(':')[1].strip() for x in rss)}")
    tmp = Path(tempfile.mkdtemp(prefix="q194_"))
    ids = [p["mesh_id"] for p in pending]
    arrs = {"ids": np.array(json.dumps(ids)), "cats": np.array(json.dumps([p["cat"] for p in pending]))}
    for k, p in enumerate(pending):
        arrs[f"v{k}"] = np.asarray(p["v"], np.float64)
        arrs[f"f{k}"] = np.asarray(p["f"], np.int32)
        arrs[f"r{k}"] = np.asarray(raw[p["mesh_id"]], np.float64)
    np.savez(tmp / "in.npz", **arrs)
    del arrs
    cmd = [sys.executable, str(Path(__file__).resolve()), "--child", str(tmp / "in.npz"), str(tmp / "out.npz"), "--budget-scale", str(budget_scale),
           "--category-scale", json.dumps(category_scale or {})]
    log(f"  Q194: running the refinement in a child process ({tmp})")
    env = {**__import__("os").environ, "PYTHONPATH": str(REPO)}
    r = subprocess.run(cmd, cwd=str(REPO), env=env)
    if r.returncode != 0:                    # e.g. a pyembree segfault in the child: once more with the pure-numpy ray tester (slow, cannot crash)
        log(f"  Q194: child exited with {r.returncode}; repeating with --safe")
        subprocess.run(cmd + ["--safe"], check=True, cwd=str(REPO), env=env)
    z = np.load(tmp / "out.npz", allow_pickle=False)
    rep = json.loads(str(z["report"]))
    by = {p["mesh_id"]: p for p in pending}
    for i in json.loads(str(z["changed"])):
        k = ids.index(i)
        if f"nv{k}" in z.files:
            by[i]["v"] = z[f"nv{k}"]
        if f"pv{k}" in z.files:
            by[i]["pre_decimated"] = (z[f"pv{k}"], z[f"pf{k}"].astype(np.int64))
        note = json.loads(str(z["notes"])).get(i)
        if note:
            by[i]["fit_note"] = (by[i].get("fit_note") or "") + note
    for f_ in tmp.iterdir():
        f_.unlink()
    tmp.rmdir()
    return rep


def child(a):
    import faulthandler
    faulthandler.enable()
    from scripts.zanatomy import build_zan_atlas_viewer as B
    z = np.load(a.inp, allow_pickle=False)
    ids, cats = json.loads(str(z["ids"])), json.loads(str(z["cats"]))
    by = {i: {"v": z[f"v{k}"], "f": z[f"f{k}"].astype(np.int64), "cat": c, "fit_note": ""} for k, (i, c) in enumerate(zip(ids, cats))}
    raw = {i: z[f"r{k}"] for k, i in enumerate(ids)}
    v0 = {i: d["v"].copy() for i, d in by.items()}
    sc = json.loads(a.category_scale)
    def dec(v, f, i, c):                       # exactly what finish() ships (decimation + outward winding), so the separation works on the shipped mesh
        dv, df = B.decimate(v, f, i, c, sc.get(c, a.budget_scale), prepped=True)
        return dv, B.outward_if_closed(dv, df)
    rep = refine_core(by, raw, dec)
    out = {"report": np.array(json.dumps(rep, default=float)), "changed": np.array("[]")}
    changed, notes = [], {}
    for k, i in enumerate(ids):
        d = by[i]
        moved = not np.array_equal(d["v"], v0[i])
        pre = d.get("pre_decimated")
        if moved or pre is not None or d.get("fit_note"):
            changed.append(i)
            if moved:
                out[f"nv{k}"] = np.asarray(d["v"], np.float64)
            if pre is not None:
                out[f"pv{k}"] = np.asarray(pre[0], np.float64)
                out[f"pf{k}"] = np.asarray(pre[1], np.int32)
            if d.get("fit_note"):
                notes[i] = d["fit_note"]
    out["changed"] = np.array(json.dumps(changed))
    out["notes"] = np.array(json.dumps(notes))
    np.savez(a.out, **out)
    print("q194 child: changed", len(changed))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--child", nargs=2, metavar=("IN", "OUT"), required=True)
    ap.add_argument("--budget-scale", type=float, default=1.0)
    ap.add_argument("--category-scale", default="{}")
    ap.add_argument("--safe", action="store_true")
    args = ap.parse_args()
    if args.safe:
        from scripts.zanatomy import q194_separate as _S
        _S.Skel.SAFE = True
    args.inp, args.out = args.child
    child(args)
