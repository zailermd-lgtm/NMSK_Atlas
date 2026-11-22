#!/usr/bin/env python3
"""Q338: rebuild the skinning weights of the HANDS and FEET of a Base page with the fixed rig builder and splice them into
data/anatomy/pose_rig_<key>.json; every other structure keeps its stored entry byte for byte.

Why a splice and not a full rebuild: the stored rigs were last fully built before the Q319 in-bone conforms and have since been
spliced (2026-11-12), so a full `make_pose_rig.py base_m` today also re-weights ~480 trunk / limb structures that this round
neither touched nor verified. The hand / foot structures are re-weighted from the current geometry with the Q338 rules
(scripts/anatomy/q241/skin.py: same-limb patches, digit chains, digit falloff; make_pose_rig.py: refined control vertices).

A structure belongs to the splice when >= 25% of its vertices lie within 30 mm of a bone of the hand (carpals, metacarpals,
phalanges) or of the foot (tarsals distal to the talus, metatarsals, phalanges), nearest-bone wise.  Idempotent.

    python3 scripts/anatomy/q338/splice_rig_q338.py base_m base_f [--dry-run]
then put the rig into a page:   python3 scripts/anatomy/q241/make_pose_rig.py --inject <page_dir>
"""
from __future__ import annotations
import argparse, base64, json, re, sys, zlib
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q241"))
import model as MD  # noqa: E402
import make_pose_rig as MR  # noqa: E402

DATA = MD.REPO / "data/anatomy"
DISTAL = re.compile(r"^(hand|foot|th_\w+|f\d_\w|t\d_\w)_[lr]$")


def splice_set(M, RB, frac=0.25, mm=30.0):
    """structure indices of the hands and feet (nearest bone sample in a hand / foot / digit segment, within mm, for >= frac of the vertices)"""
    import skin as SK
    P, lab = SK.bone_samples(M, RB)
    tr = cKDTree(P)
    distal = np.array([bool(DISTAL.match(s["id"])) for s in RB.segs])
    out = set()
    for x in M.S:
        v = x["v"][:: max(1, len(x["v"]) // 400)]
        d, i = tr.query(v)
        if ((d < mm) & distal[lab[i]]).mean() >= frac:
            out.add(x["idx"])
    return out


def entries(payload, blob):
    """-> {structure idx: ('rigid', seg) | ('skin', [i, nv, K, pal], chunk bytes)}"""
    out = {}
    for seg, ids in payload["rigid"]:
        for i in ids:
            out[i] = ("rigid", seg)
    for e in payload["skin"]:
        n = (e[1] + 7) // 8 + e[5] * (2 * e[2] - 1)      # packbits(controls) + K index planes + (K-1) weight planes
        out[e[0]] = ("skin", e[:4] + [None, e[5]], blob[e[4]:e[4] + n])
    return out


def splice(key, dry=False):
    f = DATA / ("pose_rig_%s.json" % key)
    src = json.loads(f.read_text(encoding="utf-8"))
    old = src["rig"]
    old_blob = zlib.decompress(base64.b64decode(src["weights_zlib_b64"]))
    new, new_blob, report, (M, RB, rig, out, decoded) = MR.build(key, verbose=False)
    for k in ("count", "nv", "segs", "joints", "regions"):
        if old[k] != new[k]:
            raise SystemExit("%s: the stored rig's %s differs from a rebuild -- not a weights-only splice" % (key, k))
    S = splice_set(M, RB)
    eo, en = entries(old, old_blob), entries(new, new_blob)
    rigid, skin, chunks, off = {}, [], [], 0
    changed = 0
    for i in range(old["count"]):
        e = en[i] if i in S else eo[i]
        if i in S and (e[0] != eo[i][0] or e[1] != eo[i][1] or (e[0] == "skin" and e[2] != eo[i][2])):
            changed += 1
        if e[0] == "rigid":
            rigid.setdefault(e[1], []).append(i)
        else:
            i_, nv, K, pal, _, nc = e[1]
            skin.append([i_, nv, K, pal, off, nc]); chunks.append(e[2]); off += len(e[2])
    payload = dict(old)
    payload["rigid"] = [[s, v] for s, v in sorted(rigid.items())]
    payload["skin"] = skin
    payload["notes"] = re.sub(r"\d+ skinned structures", "%d skinned structures" % len(skin), old["notes"])
    blob = b"".join(chunks)
    p, nj, nw = MR.pack(payload, blob)
    print("%s: hand / foot structures %d, re-weighted %d; skinned %d -> %d, rigid %d -> %d; weights %.1f KB zlib" % (
        key, len(S), changed, len(old["skin"]), len(skin), sum(len(g[1]) for g in old["rigid"]), sum(len(g[1]) for g in payload["rigid"]), nw / 1024))
    if not dry:
        f.write_text(json.dumps(dict(schema=src["schema"], key=key, label=src["label"], rig=payload, weights_zlib_b64=p["w"]), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print("wrote", f)
    return sorted(S)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("keys", nargs="+", choices=["base_m", "base_f"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    for k in a.keys:
        splice(k, a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
