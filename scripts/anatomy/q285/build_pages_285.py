#!/usr/bin/env python3
"""Q285: her own breasts (TotalSegmentator `breasts` on her CT, scripts/anatomy/q285/breast_from_ct_q285.py) onto Imaging-based Female.

    python3 scripts/anatomy/q285/build_pages_285.py baseline   # rebuild the CURRENT own_f page data from build/q263_pre + Q265 and
                                                               # prove it byte-identical to build/q265/viewer_f_hr (geo files + manifest)
    python3 scripts/anatomy/q285/build_pages_285.py build      # baseline + breast_ct_r / breast_ct_l -> build/q285_pre/viewer_f_hr

Own female page only. Combined Female is NOT changed: its skin is the Z-Anatomy (male-derived) surface fitted to her skeleton, and her
CT breasts, which follow her own skin, would sit outside it (measured, PROJECT_STATE Q285). The HRA sculpted breast meshes already on
the page (subject xfer_hrasculpt2vhf_q234, region breast: fat pad, mammary gland, lactiferous ducts, areola, nipple, suspensory ligaments,
both sides) are kept, selectable, and set hidden_default so the sculpted set is not drawn through her real breast; geometry and cards untouched.
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE, REPO, REPO / "scripts" / "anatomy", REPO / "scripts/anatomy/q249", REPO / "scripts/anatomy/q265"):
    sys.path.insert(0, str(p))
import build_pages as Q249BP            # noqa: E402
import build_pages_265 as Q265          # noqa: E402
import rule_q265 as RQ265               # noqa: E402

KEY = "own_f"; DIR = "viewer_f_hr"; STEM = Q249BP.STEM[KEY]
BASE = "build/q263_pre/bundle_own_f"; LIVE = "build/q265/viewer_f_hr"
SUBJ = "ct_vhf_breast"
ATTR = ("Her breasts (Q285): TotalSegmentator v2.18.0 `breasts` task (Apache-2.0; Wasserthal J et al., Radiology: Artificial Intelligence "
        "2023, doi:10.1148/ryai.230024) run on her own CT (NLM Visible Human Project female CT, public domain); automatic segmentation, "
        "cut at her own midline, meshed with the Q193 volume-preserving recipe; not hand-drawn.")
HRA_SUBJ = "xfer_hrasculpt2vhf_q234"     # the HRA sculpted breast set (fat pad, gland, ducts, areola, nipple, suspensory ligaments), Q234


def bundle_baseline():
    from scripts.transfer.q200_bundle import Bundle
    B = Bundle(REPO / BASE)
    q265, _ = RQ265.build(KEY, root=Q265.CUR)
    items = [it for it in q265 if it.get("status") == "ship"]
    for it in items:
        B.add(it["id"], it["cat"], Q249BP.sidemap(it["side"]), Q265.SUBJ265[KEY], it["rec"], it["V"], it["F"])
    return B, {Q265.SUBJ265[KEY]: Q265.ATTR265_OWN}


def write_page(B, attr, out_root):
    bdir = REPO / out_root / f"bundle_{KEY}"
    B.write(bdir, new_subject_attribution=attr, copy_clinical=True)
    d = REPO / out_root / DIR; d.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, str(REPO / "scripts/build_viewer_html.py"), "--bundle", str(bdir), "-o", str(d / f"{STEM}.html"),
                        "--external-bin"], capture_output=True, text=True, cwd=REPO)
    if r.returncode:
        raise SystemExit(r.stderr[-800:])
    t = (d / f"{STEM}.html").read_text(encoding="utf-8").replace("<title>NMSK Atlas Viewer</title>", f"<title>{Q249BP.TITLE[KEY]}</title>")
    (d / f"{STEM}.html").write_text(t, encoding="utf-8")
    src = REPO / LIVE
    for f in list(src.glob("clinical_*")) + [src / "parts_data.json", src / "symmetry_q237.json", src / "plexus_groups.json"]:
        if f.exists():
            shutil.copy2(f, d / f.name)
    return d


def geo_digest(d):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in sorted(Path(d).glob(f"{STEM}_geo_*.txt"))}


def splice_rig(committed, fresh, new_idx, out):
    """Pose rig for the page with the breasts: the COMMITTED rig of the live page, byte for byte, plus only the new structures' entries
    taken from a fresh make_pose_rig.py run on the new page. Why: a fresh run on the UNCHANGED live page already differs from the committed
    rig in ~10 trunk entries (the builder is not bit-reproducible), so a wholesale rebuild would change structures this round did not touch."""
    import base64, zlib
    A = json.loads(Path(committed).read_text()); F = json.loads(Path(fresh).read_text())
    wa = zlib.decompress(base64.b64decode(A["weights_zlib_b64"])); wf = zlib.decompress(base64.b64decode(F["weights_zlib_b64"]))
    offs = sorted(e[4] for e in F["rig"]["skin"]) + [len(wf)]
    span = {e[0]: (e[4], offs[offs.index(e[4]) + 1]) for e in F["rig"]["skin"]}
    rig = json.loads(json.dumps(A["rig"]))
    assert rig["count"] == min(new_idx) and F["rig"]["count"] == max(new_idx) + 1
    rig["count"] = F["rig"]["count"]; rig["nv"] = rig["nv"] + [F["rig"]["nv"][i] for i in new_idx]
    blob = bytearray(wa)
    fe = {e[0]: e for e in F["rig"]["skin"]}
    for i in new_idx:
        if i in fe:
            e = list(fe[i]); s, t = span[i]; e[4] = len(blob); blob += wf[s:t]; rig["skin"].append(e)
        else:
            for seg, (si, lst) in enumerate(F["rig"]["rigid"]):
                if i in lst:
                    rig["rigid"][seg][1].append(i)
    rig["notes"] = A["rig"]["notes"] + f"; Q285: +{len(new_idx)} structures (her CT breasts) spliced in, every other entry as committed"
    out_j = dict(A); out_j["rig"] = rig; out_j["weights_zlib_b64"] = base64.b64encode(zlib.compress(bytes(blob), 9)).decode("ascii")
    Path(out).write_text(json.dumps(out_j, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return len(wa), len(blob)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["baseline", "build", "rig"]); ap.add_argument("--out", default="build/q285_pre")
    ap.add_argument("--committed"); ap.add_argument("--fresh")
    a = ap.parse_args()
    if a.cmd == "rig":
        print(splice_rig(a.committed, a.fresh, [1041, 1042], REPO / "data/anatomy/pose_rig_own_f.json"))
        return
    B, attr = bundle_baseline()
    if a.cmd == "baseline":
        d = write_page(B, attr, "build/q285_base")
        live, mine = geo_digest(REPO / LIVE), geo_digest(d)
        print("geo files identical to the live page:", live == mine, len(live), "files")
        if live != mine:
            print(" live", live); print(" mine", mine)
        return
    items = json.loads((REPO / "build/vh/ct_vhf_breast/items.json").read_text())
    import trimesh
    for it in items:
        m = trimesh.load(REPO / "build/vh/ct_vhf_breast" / it["obj"], process=False)
        rec = {"name": it["name"], "latin": it["latin"], "folder": "viscera", "region": "breast",
               "source": "Her own CT (NLM Visible Human Project, public domain), TotalSegmentator v2.18.0 `breasts` task (Apache-2.0)",
               "procedural_badge": it["badge"]}
        B.add(it["id"], "organ", it["side"], SUBJ, rec, m.vertices, m.faces)
    hide = [x["e"]["id"] for x in B.items if x["e"]["subject"] == HRA_SUBJ and (x["e"].get("rec") or {}).get("region") == "breast"]
    assert len(hide) == 12, hide
    for x in B.items:
        if x["e"]["id"] in hide:
            x["e"]["hidden_default"] = True
    attr[SUBJ] = ATTR
    d = write_page(B, attr, a.out)
    print("wrote", d, "added", [i["id"] for i in items], "hidden_default set on", hide)


if __name__ == "__main__":
    main()
