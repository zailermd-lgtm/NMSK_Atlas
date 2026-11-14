#!/usr/bin/env python3
"""Q304 page step: the two Imaging pages + the transferred lower-limb nerves, and the Q304 Part B calibre note on
every page's sciatic nerve card.

    python3 scripts/anatomy/q304/pages_q304.py build [KEY...] [--src build/q303] [--out /dev/shm/q304/pre]
    python3 scripts/anatomy/q304/pages_q304.py calibre [--src ...]     # extend data/anatomy/calibre.json
    python3 scripts/anatomy/q304/pages_q304.py rig own_m --fresh FRESH.json

Every structure this round does not touch is copied byte for byte: the Imaging pages through the bundle recovered
from the shipped page (scripts/anatomy/q304/bundle304.py, round-trip proved byte-identical), the four Z pages
through q205_pages.save_page with `meta` only, which never re-packs a mesh.
"""
from __future__ import annotations

import argparse, json, shutil, subprocess, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE, REPO, REPO / "scripts/anatomy/q249", REPO / "scripts/zanatomy", REPO / "scripts/anatomy/q237"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import bundle304 as BR          # noqa: E402
import cards304 as CD           # noqa: E402

OWN = ["own_m", "own_f"]
ZKEYS = ["base_m", "base_f", "comb_m", "comb_f"]
DIR = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas",
       "base_f": "viewer_base_female", "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
HTML = {"own_m": "atlas_viewer_male.html", "own_f": "atlas_viewer_female.html"}
PAIR_LABEL = {"own_m": "Combined - Male (the same Visible Human male body)",
              "own_f": "Combined - Female (the same Visible Human female body)"}
NERVES = Path("/dev/shm/q304/nerves")
REPORT = REPO / "data/derived/Q304_page_report.json"
SIDE = {"l": "left", "r": "right", "m": "midline"}

ATTR = {
    "own_m": ("Lower-limb nerves (Q304): the common fibular (peroneal) nerve and its branches, the femoral, "
              "obturator, saphenous, sural, plantar and sided sciatic nerves on this page are NOT segmented from "
              "this body's own imaging. They are Z-Anatomy meshes already fitted to this man's own skeleton on the "
              "Combined - Male page (Q195), plus 18 Q259 rule-built tubes, carried onto this page by one bone-point "
              "registration (identity + a thin-plate-spline correction field on the bones the two pages share; "
              "bone-surface residual median 0.8 mm, p95 3.0 mm). Each card states its own error band. "
              + CD.ZAN),
    "own_f": ("Lower-limb nerves (Q304): the common fibular (peroneal) nerve and its branches, the obturator, "
              "saphenous, sural, plantar and sided sciatic nerves on this page are NOT segmented from this body's "
              "own imaging. They are Z-Anatomy meshes already fitted to this woman's own skeleton on the "
              "Combined - Female page (Q195), plus 12 Q259 rule-built tubes, carried onto this page by one "
              "bone-point registration (identity + a thin-plate-spline correction field on the bones the two pages "
              "share; bone-surface residual median 0.9 mm, p95 3.5 mm). Each card states its own error band. "
              + CD.ZAN),
}
SCIATIC_ATTR = ("Sciatic nerve calibre (Q304): validated against " + CD.SPARC.split("Required citation")[0].strip() +
                " Calibre only, never shape: the samples were excised and laid straight, so the dataset carries no "
                "in-body trajectory. No geometry was changed; the comparison is stated on the sciatic nerve's card.")


def load_items(key):
    d = json.loads((NERVES / f"{key}_nerves.json").read_text())
    z = np.load(NERVES / f"{key}_nerves.npz")
    return d, z


def sciatic_rows(key):
    cmp_ = json.loads((REPO / "data/derived/Q304_sparc692_comparison.json").read_text())
    out = {}
    for r in cmp_["rows"]:
        if r["page"] == key:
            out.setdefault(r["id"], []).append(r)
    lev = json.loads((REPO / "data/derived/Q304_sparc692_calibre.json").read_text())["levels"]
    return out, lev


def build(keys, src, out_root):
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    reg_all = json.loads((REPO / "data/derived/Q304_nerve_transfer.json").read_text())
    val_all = json.loads((REPO / "data/derived/Q304_nerve_validation.json").read_text())
    out_root = Path(out_root)
    for key in keys:
        srcd = REPO / src / DIR[key]
        dst = out_root / DIR[key]
        rows, lev = sciatic_rows(key)
        if key in OWN:
            from scripts.transfer.q200_bundle import Bundle
            bdir = out_root / f"bundle_{key}"
            BR.recover(srcd, HTML[key], bdir)
            B = Bundle(bdir)
            items, z = load_items(key)
            reg = dict(reg_all[key]["registration"]); reg["bone_groups"] = reg_all[key]["bone_groups"]
            val = val_all[key]
            added, subs = [], {}
            for sid, d in sorted(items.items()):
                rec = CD.transferred_rec(key, d, reg, val, PAIR_LABEL[key])
                sub = CD.subject_of(key, d)
                B.add(sid, "nerve", SIDE.get(d["side"], None), sub, rec,
                      z[sid + "__v"].astype(float), z[sid + "__f"].astype(np.int64))
                added.append(sid); subs[sub] = None
            # Part B: the sciatic card
            touched = []
            for sidc, rws in rows.items():
                e = B.get(sidc)
                if e is None:
                    continue
                rec = dict(e["e"].get("rec") or {})
                note = CD.sciatic_note(key, rws, lev)
                if note and "Q304 CALIBRE VALIDATED" not in (rec.get("procedural_badge") or ""):
                    rec["procedural_badge"] = (rec.get("procedural_badge") or "") + note
                i = B.find(sidc)[0]
                B.items[i]["e"]["rec"] = rec
                touched.append(sidc)
            attr = {s: ATTR[key] for s in subs}
            dst.mkdir(parents=True, exist_ok=True)
            B.write(bdir, new_subject_attribution=attr, copy_clinical=False)
            j = json.loads((bdir / "bundle.json").read_text())
            # the bundle's attribution list carries one plain string per source (the pattern since Q286/Q295)
            if not any(isinstance(x, str) and "Sciatic nerve calibre (Q304)" in x for x in j["attribution"]):
                j["attribution"] = list(j["attribution"]) + [SCIATIC_ATTR]
            (bdir / "bundle.json").write_text(json.dumps(j), encoding="utf-8")
            r = subprocess.run([sys.executable, str(REPO / "scripts/build_viewer_html.py"), "--bundle", str(bdir),
                                "-o", str(dst / HTML[key]), "--external-bin"], capture_output=True, text=True, cwd=REPO)
            if r.returncode:
                raise SystemExit(r.stderr[-900:])
            import build_pages as BP
            t = (dst / HTML[key]).read_text(encoding="utf-8").replace(
                "<title>NMSK Atlas Viewer</title>", f"<title>{BP.TITLE[key]}</title>")
            (dst / HTML[key]).write_text(t, encoding="utf-8")
            order = [e["id"] for e in json.loads((bdir / "bundle.json").read_text())["structures"]]
            rep[key] = dict(added=added, new_indices=[order.index(s) for s in added], replaced=[],
                            replaced_indices=[], sciatic_cards=touched, subjects=sorted(subs),
                            triangles_added=int(sum(items[s]["tris"] for s in added)),
                            cm3=round(sum(abs(items[s]["cm3"]) for s in added), 3))
        else:
            from scripts.zanatomy import q205_pages as P5
            import build_pages as BP
            stem = BP.STEM[key]
            man, blob = P5.load_page(srcd, stem)
            meta = {}
            for m in man["meshes"]:
                if m["id"] not in rows:
                    continue
                rec = dict(m.get("rec") or {})
                note = CD.sciatic_note(key, rows[m["id"]], lev)
                if note and "Q304 CALIBRE VALIDATED" not in (rec.get("procedural_badge") or ""):
                    rec["procedural_badge"] = (rec.get("procedural_badge") or "") + note
                meta[m["id"]] = (m["name"], rec)
            man2 = json.loads(json.dumps(man))
            if "Q304 sciatic calibre" not in man2.get("attribution", ""):
                man2["attribution"] = man2["attribution"] + " " + SCIATIC_ATTR
            P5.save_page(dst, stem, man2, blob, meta=meta)
            for f in list(srcd.glob("clinical_*")) + [srcd / "parts_data.json", srcd / "symmetry_q237.json",
                                                      srcd / "plexus_groups.json"]:
                if f.exists():
                    shutil.copy2(f, dst / f.name)
            rep[key] = dict(added=[], new_indices=[], replaced=[], replaced_indices=[],
                            sciatic_cards=sorted(meta), subjects=[], triangles_added=0, cm3=0.0)
        for f in list(srcd.glob("clinical_*")) + [srcd / "parts_data.json", srcd / "symmetry_q237.json",
                                                  srcd / "plexus_groups.json"]:
            if f.exists() and not (dst / f.name).exists():
                shutil.copy2(f, dst / f.name)
        h = sorted(dst.glob("atlas_viewer*.html"))[0]
        shutil.copy2(h, dst / "index.html")
        print(key, "->", dst, "| added", len(rep[key]["added"]), "| sciatic cards", rep[key]["sciatic_cards"], flush=True)
    rep["_README"] = ["Q304 page step (scripts/anatomy/q304/pages_q304.py): the transferred lower-limb nerves on the "
                      "two Imaging pages, and the SPARC 692 calibre note on every page's sciatic nerve card."]
    REPORT.write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")


# ------------------------------------------------------------------ data/anatomy/calibre.json
def calibre(src):
    """Q240's table is keyed by structure id, and `--inject` only copies it into the page, so the new nerves need
    their own rows or the Labels panel, the nerve-level filter and Q303's nerve emphasis would all skip them.
    The diameter is MEASURED on the transferred mesh with Q240's own estimator (q240/calibre.tube_diameter), and
    the level comes from Q240's own ladder, so nothing here is a new rule."""
    sys.path.insert(0, str(REPO / "scripts/anatomy/q240"))
    import make_calibre as MC
    from calibre import tube_diameter
    p = REPO / "data/anatomy/calibre.json"
    J = json.loads(p.read_text())
    changed = {}
    for key in OWN:
        items, z = load_items(key)
        pk = DIR[key]            # calibre.json is keyed by page DIRECTORY name (q240/pages.PAGES)
        tab = J["pages"][pk]["c"]
        n0 = len(tab)
        for sid in sorted(items):
            V = z[sid + "__v"].astype(float); F = z[sid + "__f"].astype(np.int64)
            r = tube_diameter(V, F)
            d = r["diameter_mm"]
            lv, pr = MC.level_of("n", d, sid)
            tab[sid] = ["n", d, lv, pr]
        J["pages"][pk]["c"] = {k: v for k, v in sorted(tab.items())}
        J["pages"][pk]["count"] = len(tab)
        J["pages"][pk]["q304_added"] = sorted(items)
        changed[key] = (n0, len(tab))
    J["_q304"] = ("the 71 / 64 lower-limb nerves transferred onto the Imaging pages in Q304 carry a diameter "
                  "measured on the transferred mesh with this module's own estimator")
    p.write_text(json.dumps(J, indent=1), encoding="utf-8")
    for k, (a, b) in changed.items():
        print(k, "calibre rows", a, "->", b)
    print("->", p)


# ------------------------------------------------------------------ pose rig splice (Q295's, verbatim)
def splice(key, fresh):
    import base64, zlib
    rep = json.loads(REPORT.read_text())[key]
    committed = REPO / f"data/anatomy/pose_rig_{key}.json"
    A = json.loads(committed.read_text()); F = json.loads(Path(fresh).read_text())
    assert [s_[0] for s_ in A["rig"]["segs"]] == [s_[0] for s_ in F["rig"]["segs"]], "segment lists differ"
    n0, n1 = A["rig"]["count"], F["rig"]["count"]
    assert list(range(n0, n1)) == rep["new_indices"], (n0, n1, rep["new_indices"][:3])
    wa = zlib.decompress(base64.b64decode(A["weights_zlib_b64"])); wf = zlib.decompress(base64.b64decode(F["weights_zlib_b64"]))
    offs = sorted(e[4] for e in F["rig"]["skin"]) + [len(wf)]
    span = {e[0]: (e[4], offs[offs.index(e[4]) + 1]) for e in F["rig"]["skin"]}
    rig = json.loads(json.dumps(A["rig"])); rig["count"] = n1
    rig["nv"] = rig["nv"] + [F["rig"]["nv"][i] for i in range(n0, n1)]
    blob = bytearray(wa); fe = {e[0]: e for e in F["rig"]["skin"]}
    nsk = nrg = 0
    for i in range(n0, n1):
        if i in fe:
            e = list(fe[i]); s0, t0 = span[i]; e[4] = len(blob); blob.extend(wf[s0:t0]); rig["skin"].append(e); nsk += 1
        else:
            hit = [seg for seg, lst in F["rig"]["rigid"] if i in lst]
            assert len(hit) == 1, (i, hit)
            for g in rig["rigid"]:
                if g[0] == hit[0]:
                    g[1].append(i); g[1].sort(); break
            else:
                rig["rigid"].append([hit[0], [i]]); rig["rigid"].sort()
            nrg += 1

    def seglen(e):
        return (e[1] + 7) // 8 + e[5] * (2 * e[2] - 1)
    packed = bytearray()
    for e in rig["skin"]:
        s0 = e[4]; chunk = bytes(blob[s0:s0 + seglen(e)]); e[4] = len(packed); packed.extend(chunk)
    rig["notes"] = A["rig"]["notes"] + (f"; Q304: +{n1 - n0} structures (lower-limb nerves carried from the Combined "
                                        f"page of the same body) from a fresh run, every other entry as committed")
    o = dict(A); o["rig"] = rig
    o["weights_zlib_b64"] = base64.b64encode(zlib.compress(bytes(packed), 9)).decode("ascii")
    committed.write_text(json.dumps(o, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(key, "rig", rig["count"], "skinned", len(rig["skin"]), "new skinned", nsk, "new rigid", nrg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "calibre", "rig"])
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--src", default="build/q303")
    ap.add_argument("--out", default="/dev/shm/q304/pre")
    ap.add_argument("--fresh")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.keys or (OWN + ZKEYS), a.src, a.out)
    elif a.cmd == "calibre":
        calibre(a.src)
    else:
        splice(a.keys[0], a.fresh)


if __name__ == "__main__":
    main()
