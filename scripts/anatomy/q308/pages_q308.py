#!/usr/bin/env python3
"""Q308 page step: the four rule-based structure families onto all six pages, plus the three cards that denied
tissue which is on the screen.

    python3 scripts/anatomy/q308/pages_q308.py build [KEY...] [--src <model.build_root()>] [--out /dev/shm/q308/pre]

Every structure this round does not touch is copied byte for byte -- the Imaging pages through the bundle
recovered from the shipped page (Q304's bundle304, whose round trip is proved byte-identical), the four Z pages
through q205_pages.save_page, which re-packs only the meshes it is given.

PSOAS MINOR SHIPS ON THE FOUR Z PAGES ONLY. It must not default to visible, because it is absent in roughly
half of people and a visible mesh on a named body is a claim about that body. The Z engine has a per-mesh
hidden-by-default flag (`rec.hd` -> `hideDefaults()`, measured: Combined F already hides 261 meshes with it);
the own engine has NO such mechanism -- checked, not assumed: `hideDefault`, `defaultHidden`, `startHidden`
and `e.hd` all occur zero times in its page. Adding one is an engine patch and a separate decision, so on the
two Imaging pages the muscle is NOT shipped and the reason is recorded rather than the flag being dropped.
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE, REPO, REPO / "scripts/anatomy/q304", REPO / "scripts/anatomy/q249", REPO / "scripts/zanatomy",
          REPO / "scripts/anatomy/q298", REPO / "scripts/anatomy/q241"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import bundle304 as BR    # noqa: E402
import cards308 as CD     # noqa: E402
import model as M         # noqa: E402

KEYS = ["own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"]
OWN = ["own_m", "own_f"]
DIR = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas",
       "base_f": "viewer_base_female", "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
HTML = {"own_m": "atlas_viewer_male.html", "own_f": "atlas_viewer_female.html"}
WORK = Path("/dev/shm/q308/work")
BUILT = REPO / "data/derived/Q308_built_structures.json"
REPORT = REPO / "data/derived/Q308_page_report.json"
# the own engine cannot hide a mesh by default, so this family is not shipped there
OWN_EXCLUDE = ("psoas_minor",)
HIDE_BY_DEFAULT = ("psoas_minor",)


def shipped_for(key, built):
    out = {}
    for sid, st in built[key].items():
        if sid.startswith("_") or sid == "frame" or not isinstance(st, dict):
            continue
        if st.get("refused") or "volume_cm3" not in st:
            continue
        if key in OWN and sid.rsplit("_", 1)[0] in OWN_EXCLUDE:
            continue
        out[sid] = st
    return out


def build(keys, src, out_root):
    built = json.loads(BUILT.read_text(encoding="utf-8"))
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    out_root = Path(out_root)
    for key in keys:
        srcd = REPO / src / DIR[key]
        dst = out_root / DIR[key]
        ship = shipped_for(key, built)
        z = np.load(WORK / f"q308_{key}.npz")
        added, cards, skipped = [], [], []
        for sid in built[key].get("_refused", {}):
            skipped.append(sid)
        if key in OWN:
            from scripts.transfer.q200_bundle import Bundle
            bdir = out_root / f"bundle_{key}"
            BR.recover(srcd, HTML[key], bdir)
            B = Bundle(bdir)
            notes = CD.tier_a_notes([e["e"]["id"] for e in B.items])
            for sid, st in sorted(ship.items()):
                rec, (cat, _), side = CD.rec_for(sid, st, key)
                v = z[sid + "__v"].astype(float)
                f = z[sid + "__f"].astype(np.int64)
                assert B.get(sid) is None, sid
                B.add(sid, cat, {"l": "left", "r": "right"}[side], CD.SUBJ, rec, v, f)
                added.append(sid)
            for sid, note in sorted(notes.items()):
                i, it = B.find(sid)[0], B.items[B.find(sid)[0]]
                rec = dict(it["e"].get("rec") or {})
                if "Q308" in (rec.get("procedural_badge") or ""):
                    continue
                rec["procedural_badge"] = (rec.get("procedural_badge") or "") + note
                B.items[i]["e"]["rec"] = rec
                cards.append(sid)
            dst.mkdir(parents=True, exist_ok=True)
            B.write(bdir, new_subject_attribution={CD.SUBJ: CD.ATTRIBUTION}, copy_clinical=False)
            r = subprocess.run([sys.executable, str(REPO / "scripts/build_viewer_html.py"), "--bundle", str(bdir),
                                "-o", str(dst / HTML[key]), "--external-bin"], capture_output=True, text=True, cwd=REPO)
            if r.returncode:
                raise SystemExit(r.stderr[-900:])
            import build_pages as BP
            t = (dst / HTML[key]).read_text(encoding="utf-8").replace(
                "<title>NMSK Atlas Viewer</title>", f"<title>{BP.TITLE[key]}</title>")
            (dst / HTML[key]).write_text(t, encoding="utf-8")
        else:
            from scripts.zanatomy import q205_pages as P5
            import build_pages as BP
            stem = BP.STEM[key]
            man, blob = P5.load_page(srcd, stem)
            have = {m["id"] for m in man["meshes"]}
            notes = CD.tier_a_notes(sorted(have))
            meta = {}
            for m in man["meshes"]:
                note = notes.get(m["id"])
                if not note:
                    continue
                rec = dict(m.get("rec") or {})
                if "Q308" in (rec.get("procedural_badge") or ""):
                    continue
                rec["procedural_badge"] = (rec.get("procedural_badge") or "") + note
                meta[m["id"]] = (m["name"], rec)
                cards.append(m["id"])
            add = []
            for sid, st in sorted(ship.items()):
                assert sid not in have, sid
                rec, (_, sysname), side = CD.rec_for(sid, st, key)
                if sid.rsplit("_", 1)[0] in HIDE_BY_DEFAULT:
                    rec["hd"] = 1
                entry = {"name": rec["name"], "id": sid, "side": side, "sys": sysname, "rec": rec}
                if sid.rsplit("_", 1)[0] in HIDE_BY_DEFAULT:
                    entry["hd"] = 1
                add.append((entry, z[sid + "__v"].astype(float), z[sid + "__f"].astype(np.int64)))
                added.append(sid)
            man2 = json.loads(json.dumps(man))
            if "Rule-based structures (Q308)" not in (man2.get("attribution") or ""):
                man2["attribution"] = (man2.get("attribution") or "") + " " + CD.ATTRIBUTION
            dst.mkdir(parents=True, exist_ok=True)
            P5.save_page(dst, stem, man2, blob, meta=meta, add=add)
        for f in list(srcd.glob("clinical_*")) + [srcd / "parts_data.json", srcd / "symmetry_q237.json",
                                                  srcd / "plexus_groups.json"]:
            if f.exists() and not (dst / f.name).exists():
                shutil.copy2(f, dst / f.name)
        h = sorted(dst.glob("atlas_viewer*.html"))[0]
        shutil.copy2(h, dst / "index.html")
        if key in OWN:
            order = [e["e"]["id"] for e in B.items]
        else:
            import re as _re
            _h = (dst / "index.html").read_text(encoding="utf-8")
            _man = json.loads(_re.search(r"^window\.__ANATOMY_MANIFEST__=(.*);$", _h, _re.M).group(1))
            order = [m["id"] for m in _man["meshes"]]
        rep[key] = {"added": added, "n_added": len(added), "cards_amended": sorted(set(cards)),
                    # rig307.py's splice needs these: Q308 only APPENDS, never replaces
                    "new_indices": [order.index(s) for s in added],
                    "replaced_indices": [],
                    "n_structures_after": len(order),
                    "refused_not_shipped": sorted(skipped),
                    "psoas_withheld_because_engine_cannot_hide": key in OWN,
                    "cm3_added": round(sum(ship[s]["volume_cm3"] for s in added), 4)}
        print(f"{key} -> {dst} | added {len(added)} ({rep[key]['cm3_added']} cm3) | "
              f"cards amended {len(set(cards))}", flush=True)
    rep["_README"] = [
      "Q308 page step (scripts/anatomy/q308/pages_q308.py): the four rule-based families, and the notes that "
      "stop three cards denying tissue which is on the screen.",
      "psoas minor ships on the four Z pages only, with rec.hd = 1. The own engine has no hidden-by-default "
      "flag (checked: hideDefault / defaultHidden / startHidden / e.hd all occur zero times in its page), and "
      "a muscle absent in roughly half of people must not default to visible on a named body.",
    ]
    REPORT.write_text(json.dumps(rep, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("keys", nargs="*", default=KEYS)
    # the baseline comes from model.SRC via build_root(); --src still overrides it
    ap.add_argument("--src", default=M.build_root())
    ap.add_argument("--out", default="/dev/shm/q308/pre")
    a = ap.parse_args()
    build(a.keys or KEYS, a.src, a.out)


if __name__ == "__main__":
    main()
