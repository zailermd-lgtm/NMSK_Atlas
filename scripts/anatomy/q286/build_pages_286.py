#!/usr/bin/env python3
"""Q286: structures from TotalSegmentator's open `head_glands_cavities` / `vertebrae_body` tasks onto the Imaging-based pages.

    python3 scripts/anatomy/q286/build_pages_286.py baseline own_m   # rebuild the CURRENT own_m page data, prove geo files == build/q265/viewer_m_hr
    python3 scripts/anatomy/q286/build_pages_286.py baseline own_f   # same for own_f against build/q285/viewer_f_hr (Q285's bundle)
    python3 scripts/anatomy/q286/build_pages_286.py build own_m|own_f  # baseline + the shipped items of build/vh/<subject>/items.json
    python3 scripts/anatomy/q286/build_pages_286.py rig own_m|own_f --fresh FRESH.json   # splice the new structures' rig entries

Own pages only: Base / Combined pages carry Z-Anatomy shapes (Combined = Z-Anatomy moved onto the VH body), not these bodies' CT labels.
Items come from scripts/anatomy/q286/ct_tasks_q286.py (gated there; held items never reach this script).
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, hashlib, base64, zlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE, REPO, REPO / "scripts" / "anatomy", REPO / "scripts/anatomy/q249", REPO / "scripts/anatomy/q265", REPO / "scripts/anatomy/q285"):
    sys.path.insert(0, str(p))
import build_pages as Q249BP            # noqa: E402
import build_pages_265 as Q265          # noqa: E402
import rule_q265 as RQ265               # noqa: E402

DIR = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr"}
LIVE = {"own_m": "build/q265/viewer_m_hr", "own_f": "build/q285/viewer_f_hr"}
SUBJECTS = {"own_m": ["ct_vhm_hgc", "ct_vhm_disc_ts"], "own_f": ["ct_vhf_hgc", "ct_vhf_disc_ts"]}
ATTR = {
    "hgc": ("Head glands and cavities (Q286): TotalSegmentator v2.18.0 `head_glands_cavities` task (Apache-2.0; Wasserthal J et al., "
            "Radiology: Artificial Intelligence 2023, doi:10.1148/ryai.230024) run on this body's own head CT (NLM Visible Human Project, "
            "public domain); automatic segmentation, meshed with the Q193 volume-preserving recipe; not hand-drawn."),
    "disc_ts": ("Intervertebral discs at levels the Q185c endplate rebuild held (Q286): TotalSegmentator v2.18.0 `vertebrae_body` task "
                "(Apache-2.0, class `intervertebral_discs`) on this body's own CT, split by level between its own vertebral labels; "
                "automatic segmentation, not hand-drawn."),
}


def bundle_baseline(key):
    from scripts.transfer.q200_bundle import Bundle
    if key == "own_f":
        return Bundle(REPO / "build/q285_pre/bundle_own_f"), {}
    B = Bundle(REPO / "build/q263_pre/bundle_own_m")
    q265, _ = RQ265.build(key, root=Q265.CUR)
    for it in [it for it in q265 if it.get("status") == "ship"]:
        B.add(it["id"], it["cat"], Q249BP.sidemap(it["side"]), Q265.SUBJ265[key], it["rec"], it["V"], it["F"])
    return B, {Q265.SUBJ265[key]: Q265.ATTR265_OWN}


def write_page(key, B, attr, out_root):
    stem = Q249BP.STEM[key]
    bdir = REPO / out_root / f"bundle_{key}"
    B.write(bdir, new_subject_attribution=attr, copy_clinical=True)
    d = REPO / out_root / DIR[key]; d.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, str(REPO / "scripts/build_viewer_html.py"), "--bundle", str(bdir), "-o", str(d / f"{stem}.html"),
                        "--external-bin"], capture_output=True, text=True, cwd=REPO)
    if r.returncode:
        raise SystemExit(r.stderr[-800:])
    t = (d / f"{stem}.html").read_text(encoding="utf-8").replace("<title>NMSK Atlas Viewer</title>", f"<title>{Q249BP.TITLE[key]}</title>")
    (d / f"{stem}.html").write_text(t, encoding="utf-8")
    src = REPO / LIVE[key]
    for f in list(src.glob("clinical_*")) + [src / "parts_data.json", src / "symmetry_q237.json", src / "plexus_groups.json"]:
        if f.exists():
            shutil.copy2(f, d / f.name)
    return d


def geo_digest(key, d):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in sorted(Path(d).glob(f"{Q249BP.STEM[key]}_geo_*.txt"))}


def replaced_indices(key):
    """page indices of items REPLACED in place this round (their geometry changed, so their rig entries must come from the fresh run too)"""
    ids = []
    for subj in SUBJECTS[key]:
        f = REPO / "build/vh" / subj / "items.json"
        if f.exists():
            ids += [it["id"] for it in json.loads(f.read_text()) if it.get("replace")]
    order = [e["id"] for e in json.loads((REPO / "build/q286_pre" / f"bundle_{key}" / "bundle.json").read_text())["structures"]]
    base = json.loads((REPO / f"data/anatomy/pose_rig_{key}.json").read_text())["rig"]["count"]
    return [order.index(i) for i in ids if order.index(i) < base]


def splice_rig(key, fresh, out):
    """Committed rig byte for byte + only the new structures' entries from a fresh make_pose_rig.py run (Q285: the builder is not
    bit-reproducible, so a wholesale rebuild would change structures this round did not touch)."""
    committed = REPO / f"data/anatomy/pose_rig_{key}.json"
    A = json.loads(committed.read_text()); F = json.loads(Path(fresh).read_text())
    n0, n1 = A["rig"]["count"], F["rig"]["count"]
    new_idx = list(range(n0, n1))
    wa = zlib.decompress(base64.b64decode(A["weights_zlib_b64"])); wf = zlib.decompress(base64.b64decode(F["weights_zlib_b64"]))
    offs = sorted(e[4] for e in F["rig"]["skin"]) + [len(wf)]
    span = {e[0]: (e[4], offs[offs.index(e[4]) + 1]) for e in F["rig"]["skin"]}
    rig = json.loads(json.dumps(A["rig"]))
    rig["count"] = n1; rig["nv"] = rig["nv"] + [F["rig"]["nv"][i] for i in new_idx]
    blob = bytearray(wa); fe = {e[0]: e for e in F["rig"]["skin"]}
    for i in replaced_indices(key):                   # same index, new geometry: take the fresh entry (nv + weights or rigid segment)
        rig["nv"][i] = F["rig"]["nv"][i]
        rig["skin"] = [e for e in rig["skin"] if e[0] != i]
        for seg in rig["rigid"]:
            if i in seg[1]:
                seg[1].remove(i)
        if i in fe:
            e = list(fe[i]); s, t2 = span[i]; e[4] = len(blob); blob += wf[s:t2]; rig["skin"].append(e)
        else:
            for seg, (si, lst) in enumerate(F["rig"]["rigid"]):
                if i in lst:
                    rig["rigid"][seg][1].append(i)
    for i in new_idx:
        if i in fe:
            e = list(fe[i]); s, t = span[i]; e[4] = len(blob); blob += wf[s:t]; rig["skin"].append(e)
        else:
            for seg, (si, lst) in enumerate(F["rig"]["rigid"]):
                if i in lst:
                    rig["rigid"][seg][1].append(i)
    # repack the weight blob contiguously in skin-list order (a replaced skinned entry would otherwise leave its old bytes as a gap)
    def seglen(e):
        return (e[1] + 7) // 8 + e[5] * (2 * e[2] - 1)
    packed = bytearray()
    for e in rig["skin"]:
        s = e[4]; chunk = bytes(blob[s:s + seglen(e)])
        e[4] = len(packed); packed += chunk
    blob = packed
    rig["notes"] = A["rig"]["notes"] + f"; Q286: +{len(new_idx)} structures (CT head glands/cavities, TS discs) spliced in, every other entry as committed"
    out_j = dict(A); out_j["rig"] = rig; out_j["weights_zlib_b64"] = base64.b64encode(zlib.compress(bytes(blob), 9)).decode("ascii")
    Path(out).write_text(json.dumps(out_j, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return n0, n1


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["baseline", "build", "rig"]); ap.add_argument("key", choices=["own_m", "own_f"])
    ap.add_argument("--out", default="build/q286_pre"); ap.add_argument("--fresh")
    a = ap.parse_args()
    if a.cmd == "rig":
        print(splice_rig(a.key, a.fresh, REPO / f"data/anatomy/pose_rig_{a.key}.json")); return
    B, attr = bundle_baseline(a.key)
    if a.cmd == "baseline":
        d = write_page(a.key, B, attr, "build/q286_base")
        live, mine = geo_digest(a.key, REPO / LIVE[a.key]), geo_digest(a.key, d)
        print("geo files identical to the live page:", live == mine, len(live), "files")
        if live != mine:
            print(" live", live); print(" mine", mine)
        return
    import trimesh
    added = []
    for subj in SUBJECTS[a.key]:
        f = REPO / "build/vh" / subj / "items.json"
        if not f.exists():
            continue
        items = json.loads(f.read_text())
        for it in items:
            m = trimesh.load(REPO / "build/vh" / subj / it["obj"], process=False)
            if it.get("replace") and B.find(it["id"]):
                old = B.get(it["id"])["e"]
                rec = {**(old.get("rec") or {}), **it["rec"]}
                B.replace(it["id"], m.vertices, m.faces, rec_updates=rec, subject=subj)
                added.append(it["id"] + " (replaced in place)")
            else:
                B.add(it["id"], it["cat"], it["side"], subj, it["rec"], m.vertices, m.faces)
                added.append(it["id"])
        if items:
            attr[subj] = ATTR[subj.split("_", 2)[2]]
    d = write_page(a.key, B, attr, a.out)
    print("wrote", d, "added", len(added), added)


if __name__ == "__main__":
    main()
