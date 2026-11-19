"""Q307 pose-rig splice: Q304's, extended to REPLACED indices as well as appended ones.

    python3 scripts/anatomy/q307/rig307.py KEY --fresh /dev/shm/q307/rig/KEY.json

`make_pose_rig` derives a structure's skin weights from its vertex positions, so a page that gains 57-60 nerves
and has 1-2 replaced with a different vertex count needs a new rig -- and the committed file must be touched
exactly once, from a fresh run on the NEW page, with every entry this round did not touch left byte-identical.
Q304's splice only knew how to APPEND (its `assert list(range(n0, n1)) == rep["new_indices"]`); this round also
replaces three structures whose vertex count changes from 1877 to 606-616, which keeps their index but
invalidates their weight chunk and their skinned/rigid membership.
"""
from __future__ import annotations
import argparse, base64, json, sys, zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
REPORT = REPO / "data/derived/Q307_page_report.json"


def seglen(e):
    return (e[1] + 7) // 8 + e[5] * (2 * e[2] - 1)


def splice(key, fresh):
    rep = json.loads(REPORT.read_text())[key]
    committed = REPO / f"data/anatomy/pose_rig_{key}.json"
    A = json.loads(committed.read_text()); F = json.loads(Path(fresh).read_text())
    assert [s[0] for s in A["rig"]["segs"]] == [s[0] for s in F["rig"]["segs"]], "segment lists differ"
    n0, n1 = A["rig"]["count"], F["rig"]["count"]
    assert list(range(n0, n1)) == rep["new_indices"], (n0, n1, rep["new_indices"][:3])
    repl = sorted(rep["replaced_indices"])
    assert all(i < n0 for i in repl), repl
    wa = zlib.decompress(base64.b64decode(A["weights_zlib_b64"]))
    wf = zlib.decompress(base64.b64decode(F["weights_zlib_b64"]))
    offs = sorted(e[4] for e in F["rig"]["skin"]) + [len(wf)]
    span = {e[0]: (e[4], offs[offs.index(e[4]) + 1]) for e in F["rig"]["skin"]}
    rig = json.loads(json.dumps(A["rig"])); rig["count"] = n1
    rig["nv"] = rig["nv"] + [F["rig"]["nv"][i] for i in range(n0, n1)]
    for i in repl:                                  # the replaced structures' vertex counts come from the fresh run
        rig["nv"][i] = F["rig"]["nv"][i]
    blob = bytearray(wa)
    fe = {e[0]: e for e in F["rig"]["skin"]}
    nsk = nrg = nrepl_sk = nrepl_rg = 0
    # --- the replaced indices: drop whatever the committed rig said about them and take the fresh run's word
    for i in repl:
        rig["skin"] = [e for e in rig["skin"] if e[0] != i]
        for g in rig["rigid"]:
            if i in g[1]:
                g[1].remove(i)
        rig["rigid"] = [g for g in rig["rigid"] if g[1]]
        if i in fe:
            e = list(fe[i]); s0, t0 = span[i]
            e[4] = len(blob); blob.extend(wf[s0:t0]); rig["skin"].append(e); nrepl_sk += 1
        else:
            hit = [seg for seg, lst in F["rig"]["rigid"] if i in lst]
            assert len(hit) == 1, (i, hit)
            for g in rig["rigid"]:
                if g[0] == hit[0]:
                    g[1].append(i); g[1].sort(); break
            else:
                rig["rigid"].append([hit[0], [i]])
            nrepl_rg += 1
    # --- the appended indices, exactly as Q304
    for i in range(n0, n1):
        if i in fe:
            e = list(fe[i]); s0, t0 = span[i]
            e[4] = len(blob); blob.extend(wf[s0:t0]); rig["skin"].append(e); nsk += 1
        else:
            hit = [seg for seg, lst in F["rig"]["rigid"] if i in lst]
            assert len(hit) == 1, (i, hit)
            for g in rig["rigid"]:
                if g[0] == hit[0]:
                    g[1].append(i); g[1].sort(); break
            else:
                rig["rigid"].append([hit[0], [i]])
            nrg += 1
    rig["skin"].sort(key=lambda e: e[0]); rig["rigid"].sort()
    packed = bytearray()
    for e in rig["skin"]:
        s0 = e[4]; chunk = bytes(blob[s0:s0 + seglen(e)]); e[4] = len(packed); packed.extend(chunk)
    rig["notes"] = A["rig"]["notes"] + (
        f"; Q307: +{n1 - n0} structures (the upper-limb nerves carried from the Combined page of the same body) "
        f"and {len(repl)} replaced (a nerve whose mirrored stub this round replaced with the full nerve), all from "
        f"a fresh run on the new page; every other entry as committed")
    o = dict(A); o["rig"] = rig
    o["weights_zlib_b64"] = base64.b64encode(zlib.compress(bytes(packed), 9)).decode("ascii")
    committed.write_text(json.dumps(o, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(key, "rig", rig["count"], "skinned", len(rig["skin"]), "| new skinned", nsk, "new rigid", nrg,
          "| replaced skinned", nrepl_sk, "replaced rigid", nrepl_rg)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("key"); ap.add_argument("--fresh", required=True)
    a = ap.parse_args()
    splice(a.key, a.fresh)
