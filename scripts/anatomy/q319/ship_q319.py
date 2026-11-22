#!/usr/bin/env python3
"""Q319 SHIP: write the approved Base-page repairs into the two Base build directories, in place.

    python3 scripts/anatomy/q319/ship_q319.py --page base_m --page base_f            # dry run: select + measure
    python3 scripts/anatomy/q319/ship_q319.py --page base_m --page base_f --write    # and write the files

The owner approved ("go ahead") shipping, under this rule set by the coordinator:

  1. The Q213 opponens split ships as is (no vertex moves; volumes sum exactly; two structures appended).
  2. An in-bone conform ships IF AND ONLY IF, after the move, NO check in that muscle's own `bucket_because`
     reaches a worse severity than it had before -- AND no OTHER muscle's check does either (the literal rule
     alone shipped 14 + 14 conforms but left 3 + 3 untouched neighbours with overlap 0 -> 2, because a muscle
     pushed out of bone was pushed into them; that is not a Pareto improvement, so every kept conform whose
     moved mesh touches such a neighbour is held too). Severities and thresholds are the audit's own
     (scripts/anatomy/q319/audit_reconstructed_muscles_q319.severities); no threshold is invented here.
     "Before" is the page with the split applied and no conform; "after" is the page with every conform still
     in the shipping set. Because one muscle's move changes its neighbours' overlap, the selection is iterated:
     drop every candidate that worsened, re-measure, repeat until nothing worsens.
  3. Nothing else. No give-up item (`not_defensible` bucket) is touched, even where the conform nominally
     "accepted" it (Base F's rectus_femoris_reflected_head_l, a 0.01 mm no-op).

Writing goes through the project's own pieces: geometry is packed by build_zan_atlas_viewer.pack_mesh and cut
by build_zan_atlas_viewer.split_blob exactly as scripts/zanatomy/q202_pages.save_page does, and every untouched
mesh keeps its own bytes (save_page's contract). Instead of re-rendering the page from the template (which is
what save_page does, and which would drop every injected module of the published build), only the two data
literals the regeneration reads -- `window.__ANATOMY_BIN_FILES__` and `window.__ANATOMY_MANIFEST__`, extracted
by scripts/zanatomy/rebuild_html_from_built.LIT_RE -- are replaced, in both the engine page and index.html,
serialised exactly as build_zan_atlas_viewer.render_html serialises them (checked byte-identical on the
unmodified page before anything is written). Every file replaced is first copied beside itself as `<name>.q318`.

The pose rig: the hand piece of each opponens keeps its index and becomes a RIGID entry of its hand segment
(all six of its skin-weight control vertices already point to that one segment, K = 1, so this is the same
motion), and the two foot pieces are appended as rigid entries of their foot segments -- how Combined . Female
carries them. count / nv follow. The weights blob is untouched (absolute offsets; the two dropped skin entries
leave an unreferenced slab). The rig file is data/anatomy/pose_rig_<key>.json, because that is what
scripts/anatomy/q241/make_pose_rig.py --inject (run by the regeneration) reads and checks against the page.
"""
from __future__ import annotations

import argparse
import base64
import collections
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))

import audit_reconstructed_muscles_q319 as A      # noqa: E402  metrics + severities, one copy
import repair_q319 as RP                          # noqa: E402  do_split / do_inbone, as already reported
import build_zan_atlas_viewer as B                # noqa: E402  pack_mesh / split_blob
from scripts.zanatomy import q213_zfit as Z13     # noqa: E402

PAGES = {"base_m": ("build/q309/viewer_zan_atlas", "atlas_viewer_zan_atlas"),
         "base_f": ("build/q309/viewer_base_female", "atlas_viewer_base_female")}
OUT = REPO / "data/derived/Q319_ship_report.json"
LIT = {"files": re.compile(r"^window\.__ANATOMY_BIN_FILES__=(.*);$", re.M),
       "manifest": re.compile(r"^window\.__ANATOMY_MANIFEST__=(.*);$", re.M)}


def ser_manifest(man):
    """build_zan_atlas_viewer.render_html's serialisation of the manifest literal"""
    return json.dumps(man, separators=(",", ":")).replace("</", "<\\/")


def ser_files(files):
    """render_html's serialisation of the BIN_FILES literal"""
    return json.dumps(files or [])


def repack_bytes(man, blob, replace, add):
    """q202_pages.save_page's contract without the HTML render: untouched meshes keep their own bytes."""
    meshes, chunks, off = [], [], 0
    for m in man["meshes"]:
        if m["id"] in replace:
            v, f, rec = replace[m["id"]]
            fields, packed = B.pack_mesh(np.asarray(v, float), np.asarray(f), off)
            n = dict(m)
            n.update(fields)
            if rec is not None:
                n["rec"] = rec
            meshes.append(n)
            chunks.append(packed)
            off += len(packed)
        else:
            pos = blob[m["vo"]: m["vo"] + m["vc"] * 6]
            idx = blob[m["io"]: m["io"] + m["ic"] * 6]
            n = {k: m[k] for k in m}
            n["vo"], n["io"] = off, off + len(pos)
            meshes.append(n)
            chunks += [pos, idx]
            off += len(pos) + len(idx)
    for entry, v, f in add:
        fields, packed = B.pack_mesh(np.asarray(v, float), np.asarray(f), off)
        n = dict(entry)
        n.update(fields)
        meshes.append(n)
        chunks.append(packed)
        off += len(packed)
    man2 = dict(man)
    man2["meshes"] = meshes
    t = json.loads(json.dumps(man.get("totals") or {}))
    if t:                                          # save_page's totals_fix
        t["meshes"] = len(meshes)
        for entry, _, _ in add:
            t.setdefault("by_layer", {})
            t["by_layer"][entry["sys"]] = t["by_layer"].get(entry["sys"], 0) + 1
        man2["totals"] = t
    return man2, b"".join(chunks)


def levels(r):
    """{check: worst level} of one muscle, from the audit's own severities()"""
    out = collections.defaultdict(int)
    for lvl, check, _ in A.severities(r):
        out[check] = max(out[check], lvl)
    return dict(out)


def worsened(before, after):
    """[(check, before level, after level)] where the after level is worse"""
    lb, la = levels(before), levels(after)
    return [(c, lb.get(c, 0), la[c]) for c in sorted(la) if la[c] > lb.get(c, 0)]


def audit(key, man, blob, cap, note):
    return A.audit_page(key, None, None, note, cap, verbose=False, man_blob=(man, blob))["muscles"]


def select(key, d, stem, cap, log=print):
    man, blob = A.read_page(REPO / d, stem)
    S = {m["id"]: A.decode_one(m, blob) for m in man["meshes"]}
    before_json = json.loads((REPO / "data/derived/Q319_reconstructed_muscle_audit.json").read_text())["pages"][key]
    rep = json.loads((REPO / "data/derived/Q319_repair_report.json").read_text())["pages"][key]

    log(f"\n=== {A.LABEL[key]}: {len(man['meshes'])} meshes from {d}/{stem}.html")
    split_replace, split_add, split_done = RP.do_split(man, S, log)

    accepted = sorted(rep["in_bone"]["repaired"])
    giveup = sorted(m for m, r in before_json["muscles"].items() if r["bucket"] == "not_defensible")
    excluded = [m for m in accepted if m in giveup]
    cands = [m for m in accepted if m not in giveup]
    log(f"  conform candidates: {len(accepted)} accepted in the repair report; {len(excluded)} excluded as give-up "
        f"items ({', '.join(excluded) or 'none'}); {len(cands)} to judge")

    # the conformed geometry, recomputed by the same tool on the same inputs as the reported run
    conf_replace = dict(split_replace)
    res = RP.do_inbone(man, S, cands, conf_replace, lambda *a: None)
    recomputed = sorted(res["repaired"])
    drift = sorted(set(cands) ^ set(recomputed))
    for m in recomputed:
        a, b = res["repaired"][m]["inside_after_pct"], rep["in_bone"]["repaired"][m]["inside_after_pct"]
        if abs(a - b) > 0.05:
            drift.append(f"{m}: in-bone after {a} here vs {b} in the report")
    log(f"  recomputed {len(recomputed)} conforms; differences from the repair report: {drift or 'none'}")
    conform = {m: conf_replace[m] for m in recomputed}

    # BEFORE = split only, measured
    man0, blob0 = repack_bytes(man, blob, split_replace, split_add)
    t0 = time.time()
    base = audit(key, man0, blob0, cap, "split only (in memory)")
    log(f"  baseline (split only) measured in {time.time() - t0:.0f} s")

    # bounding boxes, to attribute a NEIGHBOUR's worsening to the conforms that moved next to it
    def bbox(v):
        v = np.asarray(v, float)
        return v.min(0) - 4.0, v.max(0) + 4.0          # 4 mm, the margin the audit's overlap pass uses
    box_base = {m["id"]: bbox(S[m["id"]][0]) for m in man["meshes"] if m["sys"] == "muscle"}
    box_conf = {m: bbox(conform[m][0]) for m in conform}

    def touches(a, b):
        return bool(np.all(a[0] <= b[1]) and np.all(b[0] <= a[1]))

    keep, rounds = set(recomputed), []
    while True:
        rp_ = dict(split_replace)
        rp_.update({m: conform[m] for m in keep})
        man1, blob1 = repack_bytes(man, blob, rp_, split_add)
        after = audit(key, man1, blob1, cap, "split + conforms (in memory)")
        self_w = {m: worsened(base[m], after[m]) for m in sorted(keep)}
        self_w = {m: w for m, w in self_w.items() if w}
        # PAGE-WIDE: a muscle that was NOT moved but got worse because a neighbour was pushed into it. The
        # conforms responsible are every kept conform whose moved mesh touches it; all of them are dropped.
        coll = {m: worsened(base[m], after[m]) for m in after if m not in keep}
        coll = {m: w for m, w in coll.items() if w}
        blame = {}
        for m in coll:
            for c in sorted(keep):
                if m in box_base and touches(box_conf[c], box_base[m]):
                    blame.setdefault(c, []).append(m)
        unexplained = [m for m in coll if not any(m in v for v in blame.values())]
        rounds.append({"kept_in": sorted(keep),
                       "worsened_itself": {m: [list(x) for x in w] for m, w in self_w.items()},
                       "neighbours_worsened": {m: [list(x) for x in w] for m, w in coll.items()},
                       "blamed_for_a_neighbour": blame, "unexplained": unexplained})
        log(f"  round {len(rounds)}: {len(keep)} in | worsen themselves: "
            + ("; ".join(f"{m} ({', '.join(f'{c} {b}->{a}' for c, b, a in w)})" for m, w in self_w.items()) or "none")
            + " | neighbours worsened: "
            + ("; ".join(f"{m} ({', '.join(f'{c} {b}->{a}' for c, b, a in w)})" for m, w in coll.items()) or "none")
            + (" | blamed: " + "; ".join(f"{c} -> {', '.join(v)}" for c, v in blame.items()) if blame else "")
            + (f" | UNEXPLAINED {unexplained}" if unexplained else ""))
        drop = set(self_w) | set(blame)
        if not drop:
            break
        keep -= drop

    held = {}
    for rd in rounds:
        for m, w in rd["worsened_itself"].items():
            held.setdefault(m, {"why": "worsened its own check", "checks": w})
        for c, nb in rd["blamed_for_a_neighbour"].items():
            held.setdefault(c, {"why": "pushed into a neighbour whose check worsened",
                                "neighbours": {n: rd["neighbours_worsened"][n] for n in nb}})
    collateral = {m: worsened(base[m], after[m]) for m in after if m not in keep}
    collateral = {m: [list(x) for x in w] for m, w in collateral.items() if w}
    shipped = {m: {"before": levels(base[m]), "after": levels(after[m]),
                   "in_bone_vertex_pct": [base[m].get("in_bone_vertex_pct"), after[m].get("in_bone_vertex_pct")],
                   "overlap_muscle_pct": [base[m]["overlap_muscle_pct"], after[m]["overlap_muscle_pct"]],
                   "bucket": [base[m]["bucket"], after[m]["bucket"]]} for m in sorted(keep)}
    final_replace = dict(split_replace)
    final_replace.update({m: conform[m] for m in keep})
    return dict(man=man, blob=blob, replace=final_replace, add=split_add, split=split_done, base=base, after=after,
                report=dict(page=key, label=A.LABEL[key], source=f"{d}/{stem}.html",
                            conform_candidates_in_report=accepted, excluded_giveup=excluded,
                            recompute_drift=drift, rounds=rounds, shipped=shipped,
                            held=held,
                            collateral_worsened=collateral, split=split_done,
                            bucket_counts_before=dict(collections.Counter(r["bucket"] for r in base.values())),
                            bucket_counts_after=dict(collections.Counter(r["bucket"] for r in after.values()))))


def splice_rig(key, man_old, man_new, write, log=print):
    f = REPO / f"data/anatomy/pose_rig_{key}.json"
    src = json.loads(f.read_text(encoding="utf-8"))
    R = src["rig"]
    ids_old = [m["id"] for m in man_old["meshes"]]
    ids_new = [m["id"] for m in man_new["meshes"]]
    assert ids_new[:len(ids_old)] == ids_old, "existing indices must not move"
    assert R["count"] == len(ids_old), "committed rig does not match the page it is spliced onto"
    segname = {i: s[0] for i, s in enumerate(R["segs"])}
    segidx = {s[0]: i for i, s in enumerate(R["segs"])}
    skin = {e[0]: e for e in R["skin"]}
    rigid = {g[0]: list(g[1]) for g in R["rigid"]}
    W = __import__("zlib").decompress(base64.b64decode(src["weights_zlib_b64"]))
    changes = []
    for side in ("r", "l"):
        hid = f"opponens_digiti_minimi_{side}"
        fid = f"opponens_digiti_minimi_foot_{side}"
        hi = ids_old.index(hid)
        e = skin.pop(hi, None)
        if e is not None:
            si, nv, K, pal, off, nc = e
            mb = (nv + 7) >> 3
            ctrl = np.unpackbits(np.frombuffer(W, np.uint8, mb, off))[:nv].astype(bool)
            pi = np.frombuffer(W, np.uint8, nc, off + mb)
            cseg = [pal[p] for p in pi]
            # which control vertices belong to the hand piece: the split keeps the hand component's vertices in
            # their original order, so recompute the components on the ORIGINAL mesh
            m_old = man_old["meshes"][hi]
            v, fcs = A.decode_one(m_old, SHIP_BLOB[key])
            k, lab = Z13.components(v, fcs)
            ys = [v[lab == c][:, 1].mean() for c in range(k)]
            hand_c = int(np.argmax(ys))
            cv = np.flatnonzero(ctrl)
            hand_segs = sorted({s for c, s in zip(cv, cseg) if lab[c] == hand_c})
            foot_segs = sorted({s for c, s in zip(cv, cseg) if lab[c] != hand_c})
            assert len(hand_segs) == 1 and len(foot_segs) == 1 and K == 1, (hand_segs, foot_segs, K)
            hseg, fseg = hand_segs[0], foot_segs[0]
        else:                                      # already rigid: keep its segment for the hand, foot by name
            hseg = next(s for s, lst in rigid.items() if hi in lst)
            fseg = segidx[f"foot_{side}"]
        rigid.setdefault(hseg, []).append(hi)
        fi = ids_new.index(fid)
        rigid.setdefault(fseg, []).append(fi)
        changes.append(dict(hand=hid, hand_index=hi, hand_rig_before=("skinned" if e else "rigid"),
                            hand_rig_after=f"rigid, segment {hseg} ({segname[hseg]})",
                            foot=fid, foot_index=fi, foot_rig=f"rigid, segment {fseg} ({segname[fseg]})"))
    nv_new = [int(m["vc"]) for m in man_new["meshes"]]
    for i in range(len(ids_old)):                  # only the two hand pieces may change vertex count
        if nv_new[i] != R["nv"][i]:
            assert ids_new[i].startswith("opponens_digiti_minimi_"), ids_new[i]
    R2 = dict(R)
    R2["count"] = len(ids_new)
    R2["nv"] = nv_new
    R2["skin"] = [skin[i] for i in sorted(skin)]
    R2["rigid"] = [[s, sorted(v)] for s, v in sorted(rigid.items())]
    R2["notes"] = R["notes"] + ("; Q319: +2 structures (opponens_digiti_minimi_foot_l/r, the foot pieces split out "
                                "of the merged Z-Anatomy opponens mesh, rigid in their foot segments, appended so no "
                                "index moved); opponens_digiti_minimi_l/r now the hand piece only, rigid in its hand "
                                "segment (its K=1 skin weights already sent every hand control vertex there); weights "
                                "blob unchanged")
    out = dict(src)
    out["rig"] = R2
    if write:
        f.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    log(f"  rig {f.relative_to(REPO)}: count {R['count']} -> {R2['count']}, skin {len(R['skin'])} -> "
        f"{len(R2['skin'])}" + ("" if write else "  (dry run: not written)"))
    return dict(rig_file=str(f.relative_to(REPO)), count_before=R["count"], count_after=R2["count"],
                skin_entries_before=len(R["skin"]), skin_entries_after=len(R2["skin"]), changes=changes)


SHIP_BLOB = {}


def write_page(key, d, stem, man_old, man_new, blob_new, log=print):
    d = REPO / d
    pages = [d / f"{stem}.html", d / "index.html"]
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    # prove the serialisation is the builder's, on the UNMODIFIED page, before writing anything
    for p, t in texts.items():
        assert LIT["manifest"].search(t).group(1) == ser_manifest(man_old), f"{p}: manifest serialisation differs"
    old_files = json.loads(LIT["files"].search(texts[pages[0]]).group(1))
    assert LIT["files"].search(texts[pages[0]]).group(1) == ser_files(old_files)
    chunks = B.split_blob(blob_new, stem)
    files = [{"path": n, "bytes": len(c), "enc": "base64"} for n, c in chunks]
    replaced = []
    targets = [d / f["path"] for f in old_files] + [d / n for n, _ in chunks] + pages
    for p in dict.fromkeys(targets):
        if p.exists():
            bk = p.with_name(p.name + ".q318")
            if not bk.exists():
                shutil.copy2(p, bk)
            replaced.append(p.name)
    for n, c in chunks:
        (d / n).write_text(base64.b64encode(c).decode("ascii"), encoding="ascii")
    stale = [f["path"] for f in old_files if f["path"] not in {n for n, _ in chunks}]
    assert not stale, f"the new blob needs fewer geo files than before ({stale}); not handled"
    for p, t in texts.items():
        t2 = LIT["manifest"].sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + ser_manifest(man_new) + ";", t, count=1)
        t2 = LIT["files"].sub(lambda _m: "window.__ANATOMY_BIN_FILES__=" + ser_files(files) + ";", t2, count=1)
        p.write_text(t2, encoding="utf-8")
    log(f"  wrote {d.relative_to(REPO)}: {len(chunks)} geo files, {stem}.html, index.html (originals kept as *.q318)")
    return dict(replaced=sorted(set(replaced)), geo_files=[f["path"] for f in files], bin_files=files)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", action="append", required=True, choices=sorted(PAGES))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--cap", type=int, default=250000)
    ap.add_argument("--json", default=str(OUT))
    a = ap.parse_args(argv)
    out = {"schema": "nmsk.q319.ship.v1", "round": "Q319", "generated": time.strftime("%Y-%m-%d"),
           "rule": ("an in-bone conform ships iff no check in that muscle's own bucket_because reaches a worse "
                    "severity than before (audit severities, no new threshold); the opponens split ships as is; "
                    "no give-up item is touched; nothing is deleted"),
           "written": bool(a.write), "pages": {}}
    for key in a.page:
        d, stem = PAGES[key]
        sel = select(key, d, stem, a.cap)
        SHIP_BLOB[key] = sel["blob"]
        man_new, blob_new = repack_bytes(sel["man"], sel["blob"], sel["replace"], sel["add"])
        rep = sel["report"]
        rep["meshes_before"], rep["meshes_after"] = len(sel["man"]["meshes"]), len(man_new["meshes"])
        rep["geometry_changed"] = sorted(sel["replace"])
        rep["structures_added"] = [e[0]["id"] for e in sel["add"]]
        rep["structures_deleted"] = []
        rep["pose_rig"] = splice_rig(key, sel["man"], man_new, a.write)
        if a.write:
            rep["files"] = write_page(key, d, stem, sel["man"], man_new, blob_new)
        out["pages"][key] = rep
        print(f"  {A.LABEL[key]}: {len(rep['shipped'])} conforms ship, {len(rep['held'])} held; "
              f"buckets {rep['bucket_counts_before']} -> {rep['bucket_counts_after']}; "
              f"collateral worsened: {len(rep['collateral_worsened'])}")
    Path(a.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("written " + a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
