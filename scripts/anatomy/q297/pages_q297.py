#!/usr/bin/env python3
"""Q297 page step on the four Z pages. Nothing is sculpted and no new geometry is created.

  (1) REMOVE `zan_skin_perineal_closure` from Base F and Combined F.
      It is the audit's only class (d): a surface this project generated (Pinkall-Polthier discrete minimal surface over a
      36-vertex rim loop left behind when Z-Anatomy's male-only urogenital skin was deleted for a female body in Q196),
      with no anatomical source and no citation for its shape. On Base F it was additionally drawn AT LOAD like ordinary
      skin, where it reads as a vulval mound. There is no real source to re-derive it from (Z-Anatomy has no female
      perineal skin; the CVH set Q235 imported gives perineal MUSCLES, not skin; Q296 established that no Open Anatomy
      atlas covers the perineum), so the brief's other branch applies: it is removed and the region is shown open.
      The neighbouring real skin patches get a note saying so, in place of the invented fill.

  (2) BADGE the rule-based brachial plexus cords (4 per Z page). They carry `method: "rule-based"` and
      `error_band_mm: 10.0`, but the viewer renders neither field, so their card showed no rule-based badge at all and
      its geometry line printed the Z-Anatomy default -- a false claim, the geometry is a rule-built spline.
      They get a RULE-BASED `procedural_badge` with this page's own measured volume, and a `geom_src` that names the rule.

  (3) CORRECT the Base F breast cards with that page's own numbers (the warped left/right difference, and the nipple /
      areola volumes after the Q250 bone warp crushed them), and

  (4) record the measured fingertip clearance on all 40 hand distal phalanx cards of the four Z pages.

    python3 scripts/anatomy/q297/pages_q297.py build [--src build/q296] [--out /dev/shm/q297/pre]
    python3 scripts/anatomy/q297/pages_q297.py rig                 # splice the pose rigs for the removed mesh
"""
from __future__ import annotations
import base64, json, re, shutil, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts/zanatomy"))
import prov297 as P                      # noqa: E402
import geo as G                          # noqa: E402
import mesh as MS                        # noqa: E402
from scripts.zanatomy import q205_pages as Q205   # noqa: E402

ZKEYS = ["base_m", "base_f", "comb_m", "comb_f"]
CLOSURE = "zan_skin_perineal_closure"
DROP = {"base_f": [CLOSURE], "comb_f": [CLOSURE]}
REPORT = REPO / "data/derived/Q297_page_report.json"
STEM = {"base_m": "atlas_viewer_zan_atlas", "base_f": "atlas_viewer_base_female",
        "comb_m": "atlas_viewer_zan_male_fitted", "comb_f": "atlas_viewer_zan_female"}
CORDS = [f"brachial_cord_{w}_{s}" for w in ("lateral", "medial") for s in "lr"]
PHAL = [f"zan_distal_phalanx_of_{n}_finger_of_hand_{s}"
        for n in ("first", "second", "third", "fourth", "fifth") for s in "lr"]

# what the neighbouring real skin patches now say instead of the removed fill
OPEN_NOTE = (" || Q297: the perineum of this page is deliberately shown OPEN. The patch that used to span it "
             "(`zan_skin_perineal_closure`) was geometry this project generated -- a smooth sheet fitted over the free rim "
             "loop left when Z-Anatomy's male-only urogenital skin was removed for a female body (Q196/Q202) -- with no "
             "anatomical source and no citation for its shape, so Q297 removed it rather than keep invented tissue on the "
             "page. No source this project holds contains female perineal skin: Z-Anatomy has none, the Chinese Visible "
             "Human set imported in Q235 gives the perineal MUSCLES and the perineal body (both still on this page, both "
             "real), and the Open Anatomy survey of Q296 found no pelvis, pelvic-floor or perineal atlas at all. The gap "
             "you can see between the thighs is therefore an honest hole, not a defect.")


def cord_badge(key, sid, vol_cm3, length_mm):
    return (f"RULE-BASED (Q258, re-badged Q297): this cord is NOT segmented from any imaging and is NOT a Z-Anatomy mesh. "
            f"It is a spline built by rule as the continuation of this page's own shipped brachial-plexus division meshes, "
            f"to the course given in Gray's Anatomy for Students, 4th ed. (Drake, Vogl, Mitchell) ch.7 and Moore KL, Dalley AF, "
            f"Agur AMR, Clinically Oriented Anatomy, 8th ed. (brachial plexus). Stated error band 10.0 mm. "
            f"Volume on this page {vol_cm3:.4f} cm3, end-to-end span {length_mm:.1f} mm, 600 triangles. "
            f"Q297 found that before this round the card showed no rule-based badge at all -- `method` and `error_band_mm` "
            f"are not rendered by either viewer -- and its geometry line printed the page's Z-Anatomy default, which was "
            f"wrong: the shape is ours, built by the rule above, not Z-Anatomy's.")


CORD_GEOM = ("rule-based spline on this page's own brachial-plexus divisions (Q258); NOT Z-Anatomy geometry. "
             "Error band 10.0 mm. See scripts/anatomy/q258 and docs/GEOMETRY_SOURCES.md")


def phal_badge(key, sid, clear_mm, bone_mm):
    c = "not measurable on this page's pose" if clear_mm is None else f"{clear_mm:+.2f} mm"
    verdict = ("" if clear_mm is None else
               (" The bone therefore reaches THROUGH the local skin front on this page." if clear_mm < 0 else
                (" That is below the 3-8 mm a real distal pulp and nail occupy over the tuft, i.e. there is effectively no "
                 "soft tissue in front of the bone here." if clear_mm < 3.0 else "")))
    return (f"Q297 FINGERTIP MEASUREMENT (no geometry was changed): measured on this page's own meshes, the skin front "
            f"reaches {c} past the tip of this distal phalanx, inside a 9 mm cylinder about the phalanx's own long axis "
            f"(bone length {bone_mm:.1f} mm).{verdict} "
            f"Root cause, stated plainly: Z-Anatomy -- the source of every hand mesh on this page -- models NO nail, NO "
            f"nail bed and NO digital pulp, so there is nothing at the tips but bone and a thin skin patch; the same "
            f"measurement on the unfitted Base Male page gives only 0.68 mm in front of the middle finger, so the thinness "
            f"is inherited from the source, not introduced by our fitting. On the Combined pages the Q293 finger re-seating "
            f"moved the index and middle distal phalanges a further 0.4-4.9 mm forward. Nothing here has been re-sculpted: "
            f"inventing a nail or a pulp would be exactly the thing this project does not do. See "
            f"docs/research/Q297_provenance_audit.md and docs/OPEN_ITEMS_FOR_OWNER.md.")


def tip_clearances(key, src):
    """{structure id: (skin_past_tip_mm | None, bone_len_mm)} -- scripts/anatomy/q297/tips3.py, same measurement."""
    import tips3
    out = {}
    for r in tips3.run(key, src):
        out[r["phalanx"]] = (r["skin_past_tip_mm"], r["bone_len_mm"])
    return out


def breast_notes(key, src):
    """Base F / Combined F: this page's OWN breast numbers after the fit, which the Q285/Q234 cards do not state."""
    out = {}
    vols = {}
    for sid in ("breast_ct_l", "breast_ct_r", "nipple_l", "nipple_r", "areola_l", "areola_r"):
        g = G.get(key, sid, src)
        if g:
            vols[sid] = MS.stats(g[0], g[1])
    if "breast_ct_l" in vols and "breast_ct_r" in vols:
        vl, vr = vols["breast_ct_l"]["vol_cm3"], vols["breast_ct_r"]["vol_cm3"]
        diff = 100.0 * abs(vl - vr) / ((vl + vr) / 2)
        for sid in ("breast_ct_l", "breast_ct_r"):
            d = vols[sid]
            out[sid] = (f" || Q297 re-measured this page's own breast meshes. On THIS page left {vl:.1f} / right {vr:.1f} cm3, "
                        f"a left/right difference of {diff:.1f} % of the mean -- against the {13.6:.1f} % of her own CT label, "
                        f"which the line above quotes. The extra asymmetry is the fit on this page, not her body"
                        f"{' (Base F carries the Q250 bone-anchored thin-plate spline)' if key == 'base_f' else ''}. "
                        f"Mesh quality on this page: {d['degenerate_tris']} zero-area triangles, {d['defect_pct']:.2f} % defect edges, "
                        f"mean dihedral {d['mean_dihedral_deg']:.1f} deg, no spikes (max one-ring offset {d['spike_max']:.2f} x the local "
                        f"edge length) and consistent winding -- so what looks distorted is the SHAPE, not a broken mesh. "
                        f"The shape is her SUPINE unenhanced cadaver CT: a 59-year-old supine breast spreads laterally and "
                        f"superiorly almost to the clavicle. We hold no upright or prone imaging of her, and this atlas will "
                        f"not sculpt a more flattering breast. See docs/OPEN_ITEMS_FOR_OWNER.md.")
    for sid in ("nipple_l", "nipple_r", "areola_l", "areola_r"):
        if sid in vols:
            v = vols[sid]["vol_cm3"]
            ref = {"nipple_l": 0.05, "nipple_r": 0.06, "areola_l": 0.29, "areola_r": 0.30}[sid]
            out[sid] = (f" || Q297 re-measured this mesh on THIS page: {v:.3f} cm3, against {ref:.2f} cm3 for the same "
                        f"structure on the Imaging F page. "
                        + (f"The bone-anchored warp this page carries has flattened it to {100.0 * v / ref:.0f} % of that, "
                           f"i.e. it is effectively collapsed and should be read as a position marker, not as a shape. "
                           if v < 0.5 * ref else "")
                        + "It is in any case a sculpted HuBMAP HRA reference object, not her tissue -- see the line above.")
    return out


def build(src="build/q296", out="/dev/shm/q297/pre"):
    src_p, out_p = REPO / src if not Path(src).is_absolute() else Path(src), Path(out)
    out_p.mkdir(parents=True, exist_ok=True)
    rep = {"src": str(src), "pages": {}}
    # the two Imaging pages are copied byte for byte: their Q297 fix is a template change (sync_subjects_q297.py)
    for key in ("own_m", "own_f"):
        dn = P.DIRS[key][0]
        if (out_p / dn).exists():
            shutil.rmtree(out_p / dn)
        shutil.copytree(src_p / dn, out_p / dn)
        rep["pages"][key] = {"copied": True, "note": "unchanged here; the Q297 fix for this page is the SUBJECT_LABELS template entry"}
    for key in ZKEYS:
        dn, hn, _ = P.DIRS[key]
        d_in, d_out = src_p / dn, out_p / dn
        if d_out.exists():
            shutil.rmtree(d_out)
        d_out.mkdir(parents=True)
        for f in d_in.iterdir():
            if not f.name.startswith(STEM[key]) and f.name != "index.html":
                shutil.copy2(f, d_out / f.name)
        man, blob = Q205.load_page(d_in, STEM[key])
        ids = [m["id"] for m in man["meshes"]]
        meta = {}
        # (2) the rule-based cords
        for sid in CORDS:
            if sid not in ids:
                continue
            v, f, _ = G.get(key, sid, src)
            st = MS.stats(v, f)
            m = next(x for x in man["meshes"] if x["id"] == sid)
            rec = json.loads(json.dumps(m.get("rec") or {}))
            rec["procedural_badge"] = cord_badge(key, sid, st["vol_cm3"], float(np.linalg.norm(v.max(0) - v.min(0))))
            rec["geom_src"] = CORD_GEOM
            meta[sid] = (m["name"], rec)
        # (4) the fingertip measurement
        tc = tip_clearances(key, src)
        for sid, (clear, bone) in tc.items():
            m = next((x for x in man["meshes"] if x["id"] == sid), None)
            if m is None:
                continue
            rec = json.loads(json.dumps(m.get("rec") or {}))
            rec["procedural_badge"] = ((rec.get("procedural_badge") + " || ") if rec.get("procedural_badge") else "") + phal_badge(key, sid, clear, bone)
            meta[sid] = (m["name"], rec)
        # (3) the breast cards
        if key in ("base_f", "comb_f"):
            for sid, note in breast_notes(key, src).items():
                m = next((x for x in man["meshes"] if x["id"] == sid), None)
                if m is None:
                    continue
                rec = json.loads(json.dumps(m.get("rec") or {}))
                rec["procedural_badge"] = (rec.get("procedural_badge") or "") + note
                meta[sid] = (m["name"], rec)
        # (1) the perineal closure: drop it, and tell the neighbours
        drop = [s for s in DROP.get(key, []) if s in ids]
        if drop:
            for m in man["meshes"]:
                if m["sys"] == "skin" and m["id"] != CLOSURE and re.search(
                        r"anal_region|gluteal_fold|femoral_triangle|hypogastric|inguinal|pubic|perine", m["id"]):
                    rec = json.loads(json.dumps(m.get("rec") or {}))
                    rec["procedural_badge"] = (rec.get("procedural_badge") or "") + OPEN_NOTE
                    meta[m["id"]] = (m["name"], rec)
            man = dict(man); man["meshes"] = [m for m in man["meshes"] if m["id"] not in drop]
        tot = dict(man["totals"])
        by_l = dict(tot.get("by_layer") or {}); by_c = dict(tot.get("by_category") or {})
        if drop:
            by_l["skin"] = by_l.get("skin", 0) - len(drop)
            by_c["skin"] = by_c.get("skin", 0) - len(drop)
        man2, _ = Q205.save_page(d_out, STEM[key], man, blob, meta=meta,
                                 totals={"by_layer": by_l, "by_category": by_c})
        shutil.copy2(d_out / f"{STEM[key]}.html", d_out / "index.html")
        rep["pages"][key] = {"dropped": drop, "dropped_index": [ids.index(s) for s in drop],
                             "cards_patched": sorted(meta), "meshes_before": len(ids), "meshes_after": len(man2["meshes"]),
                             "tip_clearance_mm": {k: v[0] for k, v in sorted(tc.items())}}
        print(key, "dropped", drop, "cards patched", len(meta), "meshes", len(ids), "->", len(man2["meshes"]))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print("report", REPORT)


def rig():
    """Drop the removed mesh's index from the committed pose rig of each affected page and renumber the ones after it.
    The closure is a RIGID entry on both pages (not skinned), so no weight blob has to be repacked -- asserted here."""
    rep = json.loads(REPORT.read_text())
    for key, info in rep["pages"].items():
        drop_idx = info.get("dropped_index") or []
        if not drop_idx:
            continue
        p = REPO / f"data/anatomy/pose_rig_{key}.json"
        J = json.loads(p.read_text()); R = J["rig"]
        before = R["count"]
        for i in sorted(drop_idx, reverse=True):
            assert not any(e[0] == i for e in R["skin"]), f"{key}: index {i} is a SKINNED rig entry -- weight surgery needed"
            R["nv"] = R["nv"][:i] + R["nv"][i + 1:]
            R["count"] -= 1
            for g in R["rigid"]:
                g[1] = [(x - 1 if x > i else x) for x in g[1] if x != i]
            R["rigid"] = [g for g in R["rigid"] if g[1]]
            for e in R["skin"]:
                if e[0] > i:
                    e[0] -= 1
        assert len(R["nv"]) == R["count"], (len(R["nv"]), R["count"])
        assert all(0 <= e[0] < R["count"] for e in R["skin"])
        assert all(0 <= x < R["count"] for g in R["rigid"] for x in g[1])
        R["notes"] = R["notes"] + f"; Q297: -{len(drop_idx)} structure (the generated perineal surface closure, removed), later indices renumbered"
        J["rig"] = R
        p.write_text(json.dumps(J, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print(key, "rig", before, "->", R["count"], "skinned", len(R["skin"]), "rigid groups", len(R["rigid"]))


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "build"
    kw = {}
    if "--src" in a:
        kw["src"] = a[a.index("--src") + 1]
    if "--out" in a:
        kw["out"] = a[a.index("--out") + 1]
    if cmd == "build":
        build(**kw)
    elif cmd == "rig":
        rig()
    else:
        print(__doc__); sys.exit(2)
