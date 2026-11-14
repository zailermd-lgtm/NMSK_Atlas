#!/usr/bin/env python3
"""Q307 page step.

    python3 scripts/anatomy/q307/pages_q307.py build [KEY...] [--src build/q304] [--out /dev/shm/q307/pre]
    python3 scripts/anatomy/q307/pages_q307.py calibre [--src build/q304]

The two Imaging pages gain this round's transferred upper-limb nerves and the three repaired lower-limb ones;
all six pages gain the measured Q307 statements on the lateral antebrachial cutaneous nerve's card and on the
card of every cutaneous nerve this round measured inside a muscle belly. Every structure this round does not
touch is copied byte for byte -- the Imaging pages through the bundle recovered from the shipped page
(Q304's bundle304, whose round trip is proved byte-identical), the four Z pages through q205_pages.save_page
with `meta` only, which never re-packs a mesh.
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE, REPO, REPO / "scripts/anatomy/q304", REPO / "scripts/anatomy/q249", REPO / "scripts/zanatomy",
          REPO / "scripts/anatomy/q237", REPO / "scripts/anatomy/q241"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import bundle304 as BR    # noqa: E402
import cards307 as CD     # noqa: E402

OWN = ["own_m", "own_f"]
DIR = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas",
       "base_f": "viewer_base_female", "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
HTML = {"own_m": "atlas_viewer_male.html", "own_f": "atlas_viewer_female.html"}
PAIR_LABEL = {"own_m": "Combined - Male (the same Visible Human male body)",
              "own_f": "Combined - Female (the same Visible Human female body)"}
NERVES = Path("/dev/shm/q307/nerves")
REPORT = REPO / "data/derived/Q307_page_report.json"
SIDE = {"l": "left", "r": "right", "m": "midline"}
LACN = "zan_lateral_antebrachial_cutaneous_nerve"

ATTR = {
 "own_m": ("Upper-limb nerves (Q307): the lateral and medial antebrachial cutaneous nerves, the brachial "
           "cutaneous nerves, the axillary, suprascapular, long thoracic, pectoral, subscapular and "
           "thoracodorsal nerves, the deep branch of the ulnar nerve, the posterior interosseous nerve and the "
           "palmar and dorsal digital nerves on this page are NOT segmented from this body's own imaging. They "
           "are Z-Anatomy meshes already fitted to this man's own skeleton on the Combined - Male page (Q195), "
           "carried onto this page by one bone-point registration, plus one lower-limb nerve (the right tibial) "
           "whose left-right stub this round replaced. Each card states its own error band and the gate it had "
           "to pass. " + CD.ZAN),
 "own_f": ("Upper-limb nerves (Q307): the lateral and medial antebrachial cutaneous nerves, the brachial "
           "cutaneous nerves, the axillary, suprascapular, long thoracic, pectoral, subscapular and "
           "thoracodorsal nerves, the deep branch of the ulnar nerve, the posterior interosseous nerve and the "
           "palmar and dorsal digital nerves on this page are NOT segmented from this body's own imaging. They "
           "are Z-Anatomy meshes already fitted to this woman's own skeleton on the Combined - Female page "
           "(Q195), carried onto this page by one bone-point registration, plus two lower-limb nerves (the left "
           "femoral and the left tibial) whose mirrored stubs this round replaced. Each card states its own "
           "error band and the gate it had to pass. " + CD.ZAN),
}
LACN_ATTR = ("Nerve placement audit (Q307): every nerve on this page was checked for continuity with its parent "
             "trunk, for the compartment and depth its own anatomy requires, for its side, and for bone and body "
             "containment. The lateral antebrachial cutaneous nerve -- reported by the owner as out of place -- "
             "is in the right compartment, on the right side and at the right depth, but covers only the "
             "proximal two thirds of the forearm and has no anterior or posterior branch; that is stated on its "
             "own card with both cadaveric sources, not sculpted away. Cutaneous nerves measured inside a muscle "
             "belly carry their measured depth on their own cards. docs/research/Q307_nerve_placement_audit.md")


def load_items(key):
    return json.loads((NERVES / f"{key}_nerves.json").read_text()), np.load(NERVES / f"{key}_nerves.npz")


def notes_for(key, lacn, inmus):
    """{structure id: the text Q307 appends to its badge} for one page."""
    out = {}
    n = CD.lacn_note(key, (lacn.get("pages") or {}).get(key) or {})
    if n:
        for s in ("l", "r"):
            out[f"{LACN}_{s}"] = n
    for sid, rows in (inmus.get(key) or {}).items():
        out[sid] = out.get(sid, "") + CD.in_muscle_note(key, sid, rows, CD.NOT_MOVED)
    return out


def build(keys, src, out_root):
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    reg_all = json.loads((REPO / "data/derived/Q307_nerve_transfer.json").read_text())
    val_all = json.loads((REPO / "data/derived/Q307_nerve_validation.json").read_text())
    lacn = json.loads((REPO / "data/derived/Q307_lacn_measurements.json").read_text())
    inmus = json.loads(Path("/dev/shm/q307/in_muscle_cards.json").read_text())
    out_root = Path(out_root)
    for key in keys:
        srcd = REPO / src / DIR[key]
        dst = out_root / DIR[key]
        notes = notes_for(key, lacn, inmus)
        if key in OWN:
            from scripts.transfer.q200_bundle import Bundle
            bdir = out_root / f"bundle_{key}"
            BR.recover(srcd, HTML[key], bdir)
            B = Bundle(bdir)
            items, z = load_items(key)
            R = reg_all[key]
            gates = dict(R["gate"], n_refused=R["n_refused"], n_candidates=R["n_candidates"])
            val = val_all[key]
            added, replaced, subs = [], [], {}
            for sid, d in sorted(items.items()):
                reg = dict(R["registration"][d["region"]])
                rec = CD.transferred_rec(key, d, reg, val, PAIR_LABEL[key], gates)
                if notes.get(sid):
                    rec["procedural_badge"] = rec["procedural_badge"] + notes.pop(sid)
                sub = CD.subject_of(key, d)
                v = z[sid + "__v"].astype(float); f = z[sid + "__f"].astype(np.int64)
                if B.get(sid) is not None:
                    B.replace(sid, v, f, rec_updates=rec, subject=sub)
                    replaced.append(sid)
                else:
                    B.add(sid, "nerve", SIDE.get(d["side"]), sub, rec, v, f)
                    added.append(sid)
                subs[sub] = None
            touched = []
            for sid, note in sorted(notes.items()):
                e = B.get(sid)
                if e is None:
                    continue
                rec = dict(e["e"].get("rec") or {})
                if "Q307 MEASURED" not in (rec.get("procedural_badge") or ""):
                    rec["procedural_badge"] = (rec.get("procedural_badge") or "") + note
                    B.items[B.find(sid)[0]]["e"]["rec"] = rec
                    touched.append(sid)
            attr = {s: ATTR[key] for s in subs}
            dst.mkdir(parents=True, exist_ok=True)
            B.write(bdir, new_subject_attribution=attr, copy_clinical=False)
            j = json.loads((bdir / "bundle.json").read_text())
            if not any(isinstance(x, str) and "Nerve placement audit (Q307)" in x for x in j["attribution"]):
                j["attribution"] = list(j["attribution"]) + [LACN_ATTR]
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
            rep[key] = dict(added=added, new_indices=[order.index(s) for s in added], replaced=replaced,
                            replaced_indices=[order.index(s) for s in replaced], cards=touched,
                            subjects=sorted(subs),
                            triangles_added=int(sum(items[s]["tris"] for s in added)),
                            cm3=round(sum(items[s]["cm3"] for s in items), 3))
        else:
            from scripts.zanatomy import q205_pages as P5
            import build_pages as BP
            stem = BP.STEM[key]
            man, blob = P5.load_page(srcd, stem)
            meta = {}
            for m in man["meshes"]:
                note = notes.get(m["id"])
                if not note:
                    continue
                rec = dict(m.get("rec") or {})
                if "Q307 MEASURED" in (rec.get("procedural_badge") or ""):
                    continue
                rec["procedural_badge"] = (rec.get("procedural_badge") or "") + note
                meta[m["id"]] = (m["name"], rec)
            man2 = json.loads(json.dumps(man))
            if "Nerve placement audit (Q307)" not in man2.get("attribution", ""):
                man2["attribution"] = man2["attribution"] + " " + LACN_ATTR
            P5.save_page(dst, stem, man2, blob, meta=meta)
            rep[key] = dict(added=[], new_indices=[], replaced=[], replaced_indices=[],
                            cards=sorted(meta), subjects=[], triangles_added=0, cm3=0.0)
        for f in list(srcd.glob("clinical_*")) + [srcd / "parts_data.json", srcd / "symmetry_q237.json",
                                                  srcd / "plexus_groups.json"]:
            if f.exists() and not (dst / f.name).exists():
                shutil.copy2(f, dst / f.name)
        h = sorted(dst.glob("atlas_viewer*.html"))[0]
        shutil.copy2(h, dst / "index.html")
        print(key, "->", dst, "| added", len(rep[key]["added"]), "| replaced", rep[key]["replaced"],
              "| cards", len(rep[key]["cards"]), flush=True)
    rep["_README"] = ["Q307 page step (scripts/anatomy/q307/pages_q307.py): the transferred upper-limb nerves and "
                      "the three repaired lower-limb nerves on the two Imaging pages, and the measured Q307 "
                      "placement statements on the lateral antebrachial cutaneous nerve and on every cutaneous "
                      "nerve this round found inside a muscle belly."]
    REPORT.write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")


def calibre(src):
    """Q240's table is keyed by structure id and `--inject` only copies it into the page, so a nerve added here
    needs its own row or the Labels panel, the nerve-level filter and Q303's nerve emphasis would all skip it --
    which is how the two Imaging pages came to report 0 fibular nerves. The diameter is MEASURED on the
    transferred mesh with Q240's own estimator and the level comes from Q240's own ladder: no new rule."""
    sys.path.insert(0, str(REPO / "scripts/anatomy/q240"))
    import make_calibre as MC
    from calibre import tube_diameter
    p = REPO / "data/anatomy/calibre.json"
    J = json.loads(p.read_text())
    added = {}
    for key in OWN:
        items, z = load_items(key)
        page = DIR[key]
        c = J["pages"][page]["c"]
        n = 0
        for sid, d in sorted(items.items()):
            v = z[sid + "__v"].astype(float); f = z[sid + "__f"].astype(np.int64)
            dia = tube_diameter(v, f)["diameter_mm"]
            lev, pr = MC.level_of("n", dia, sid)
            c[sid] = ["n", dia, lev, pr]
            n += 1
        J["pages"][page]["c"] = {k: v for k, v in sorted(c.items())}
        J["pages"][page]["count"] = len(c)
        J["pages"][page]["q307_added"] = sorted(items)
        added[key] = n
    J["_q307"] = ("Rows for the upper-limb nerves Q307 carried onto the two Imaging pages (and the three repaired "
                  "lower-limb ones), diameter measured on the transferred mesh with Q240's own tube estimator.")
    p.write_text(json.dumps(J, indent=1), encoding="utf-8")
    print("calibre rows added:", added)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "calibre"])
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--src", default="build/q304")
    ap.add_argument("--out", default="/dev/shm/q307/pre")
    a = ap.parse_args()
    if a.cmd == "calibre":
        calibre(a.src)
    else:
        build(a.keys or list(DIR), a.src, a.out)


if __name__ == "__main__":
    main()
