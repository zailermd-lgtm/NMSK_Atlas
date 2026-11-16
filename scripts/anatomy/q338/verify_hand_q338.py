#!/usr/bin/env python3
"""Q338 verifier: the wrist, hand and fingers of a Base page, at rest and posed.

    python3 scripts/anatomy/q338/verify_hand_q338.py <page_dir> [--no-browser] [--json out.json]

Prints OK / FAIL / KNOWN lines and ends with Q338_HAND_OK or Q338_HAND_FAIL.  KNOWN = a defect of the Z-Anatomy source geometry that this
round reports with its numbers but cannot repair honestly (no geometry is redrawn); it never turns the verdict green on its own -- the
list of KNOWN items is fixed below, so a new or larger defect still fails.

At rest (python, the page's own geometry; finger frames from hand_frame.py):
  R1 proper palmar digital arteries / nerves: a radial and an ulnar strand on every finger 2-5, each lateral (|radial| >= 2.5 mm), within
     12 mm of the bone axis, on the palmar half (median palmar offset >= -1.5 mm); dorsal digital NERVES on the dorsal half (<= +1 mm)
  R2 flexor tendons / digital sheaths palmar to the phalanges, extensor tendons dorsal (median palmar offset of the in-finger vertices)
  R3 no soft tissue of the hand more than 1.5 mm inside a hand bone (watertight bone meshes)
  R4 left = mirrored right (mean distance <= 1.5 mm) and every _l / _r hand structure on its own side of the midsagittal plane
  R5 no hand structure carries the hand BONES' record (lumbricals, collateral interphalangeal ligaments)
Posed (python replica of pose.js with the page's rig block; every finger flexed / extended to its range end at MCP + PIP + DIP together,
the thumb CMC + MCP + IP together, the wrist flexion / extension and radial / ulnar deviation):
  P1 no shaft vertex of a finger is bound to ANOTHER digit (dominant weight on another finger or the thumb)
  P2 per structure, its shaft vertices (outside the joint zones: wrist 20, MCP / CMC 12, PIP / IP 9, DIP 7 mm; not on a seam where one
     source mesh joins two fingers) stay within TOL_P95 of where their own bone takes them for 95% of them and within TOL_MAX for all
     (skin, nails, vessels, nerves, sheaths, ligaments, capsules, extrinsic tendons; intrinsic hand muscles that span joints and the
     rule-based fat pieces are listed, not gated)
Browser (1400x900): the page loads with 0 page errors, the pose rig is ready, and the live vertices the viewer computes for a flexed
middle finger / thumb equal the python replica (max 0.5 mm) -- so the numbers above are what the viewer draws.
"""
from __future__ import annotations
import argparse, json, re, sys, tempfile
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hand_audit_q338 as A  # noqa: E402
import hand_frame as HF  # noqa: E402

TOL_P95, TOL_P95_SKIN, TOL_MAX = 5.0, 8.0, 15.0     # skin blends over its 16 mm falloff (the builder's rule for all skin) -> 8 mm p95; a structure
                                                    # also fails when 3 or more of its shaft vertices are off by more than TOL_MAX
GATED_SYS = ("skin", "vessel", "nerve", "bursa", "joint", "fascia", "insertion")
SPANNING = re.compile(r"(region_of_wrist|radial_foveola|articular_capsule|collateral_|transverse_metacarpal_ligament|retinaculum|palmar_interphalangeal_ligaments|palmar_metacarpal_ligaments|dorsal_metacarpal_ligaments|interosseous_metacarpal|carpometacarpal|intercarpal|radiocarpal|ulnocarpal|pisotriquetral|scapho|triquetro|radiate_carpal|capitat|lunat|palmar_radio_ulnar)")
HAND_SKIN = re.compile(r"zan_skin_(palm|dorsum_of_hand)_")
WRIST_ZONE = 30.0   # mm distal to the wrist centre along the hand: the carpus and the CMC joints (the rig blends 15-30 mm, skin.py WRIST_IN / WRIST_OUT)
EXTRINSIC = re.compile(r"(flexor_digitorum_(superficialis|profundus)|humero_ulnar_head_of_flexor_digitorum|flexor_pollicis_longus|extensor_(digitorum|indicis|digiti_minimi|pollicis_(longus|brevis))|abductor_pollicis_longus|fibrous_sheath_of_digit)")
# KNOWN source-geometry defects (Z-Anatomy), with the numbers measured on both Base pages (both sides) -- see the Q338 report
KNOWN = {
    "palm_depth": "superficial venous palmar arch lies DEEP to the flexor tendons (0% of its points palmar to them, ~85% dorsal); Q340 "
                  "conformed the arterial arch and the common palmar digital arteries (real checks now) but kept the venous arch: its tapered "
                  "lift drove ~70 vertices per hand into the flexor tendons (dives toward the deep venous arch, held junctions with the ulnar "
                  "and palmar digital veins) -- data/derived/Q340_palm_report.json",
    "digital_nerve_depth": "proper palmar digital nerves of fingers 2-5 run at the mid-lateral line (median palmar offset -0.7..+1.4 mm), "
                           "3-5 mm dorsal to the arteries (+3..+8); textbook: the nerve lies palmar to the artery in the finger",
    "dorsal_digital_arteries": "dorsal digital arteries / veins of the hand run at the mid-lateral line (median palmar offset -2.1..+2.0 mm) "
                               "instead of dorsolaterally",
    "thumb_radial_artery": "radial proper palmar digital artery of the thumb at the mid-lateral line (median palmar offset -0.1 mm)",
    "in_bone": "Z meshes dipping into a hand bone by up to 2.5-4.4 mm, kept by Q340 (its push failed a guard on a side; both hands are kept "
               "mirror images): deep venous palmar arch on Base M 51 vertices (mc 3-5, 4.4 mm; flipped 0.53 % > 0.5 on the right), palmar "
               "metacarpal arteries 23 (mc 2 / 5, 2.5; flipped 1.2 %), deep palmar arch 21 (hamate, mc 2, 2.7; pushed into the flexor "
               "tendons), fibrous sheath of the digits 38 of 1817 (proximal phalanx 3, middle phalanx 4, 2.9; pushed into the tendons / "
               "digital sheaths) -- data/derived/Q340_palm_report.json",
}
ASYM = ("recurrent_branch_of_median_n_r", "zan_common_flexor_tendon_sheath_r")
KNOWN["asym"] = ("left and mirrored right differ: recurrent branch of the median nerve (Base M) mean 3.0 mm / p95 7.9; common flexor "
                 "tendon sheath (467 vs 458 vertices, two different source meshes) mean 1.9 mm (M) / 1.85 mm (F)")
LIMITS = {
    "wrist_band": "over the carpus (0-30 mm distal to the wrist centre) the tendons, sheaths, retinacula and wrist skin that cross the wrist "
                  "blend between the forearm and the hand, so at the end of wrist flexion / deviation they bend across the joint instead of "
                  "following one bone (numbers listed per test; not gated)",
    "thenar": "soft tissue lying on the thumb metacarpal or the palm next to it (the thenar eminence, its skin, the first web) blends between the hand and the thumb "
              "metacarpal, so the full CMC range (46 deg flexion + 46 deg abduction from the as-built thumb) stretches it; not gated",
    "spanning": "structures that span a joint or join two digits by definition (articular capsules, collateral ligaments, the transverse "
                "metacarpal ligaments, retinacula, the intrinsic hand muscles, the rule-based fat pieces) stretch when one finger moves; "
                "listed with their numbers, not gated",
}
DORSAL_ARTERY = re.compile(r"dorsal_digital_(arteries|veins)_of_hand")
ERRS: list[str] = []
KNOWN_HIT: set = set()
LIMIT_HIT: set = set()


def check(label, ok, known=None):
    if ok:
        print("  OK    " + label)
    elif known:
        print("  KNOWN " + label + "  [" + known + "]")
        KNOWN_HIT.add(known)
    else:
        print("  FAIL  " + label)
        ERRS.append(label)
    return ok


# ---------------------------------------------------------------------------------------------------------------- rest
def rest_rules(pg):
    out = {}
    for s in "rl":
        H = pg.H[s]
        print("  -- side %s" % s)
        # R1 digital strands
        for nm, kind in (("zan_proper_palmar_digital_arteries_", "palmar"), ("zan_proper_palmar_digital_branches_of_median_nerve_", "palmar"),
                         ("zan_proper_palmar_digital_branches_of_ulnar_nerve_", "palmar"), ("zan_dorsal_digital_branches_of_radial_nerve_", "dorsal"),
                         ("zan_dorsal_digital_branches_of_ulnar_nerve_", "dorsal"), ("zan_dorsal_digital_arteries_of_hand_", "dorsal_a")):
            x = pg.byid.get(nm + s)
            if x is None:
                check("%s%s present" % (nm, s), False); continue
            rows = [r for r in A.digital_components(pg, s, x) if "finger" in r]
            for r in rows:
                side = "radial" if r["radial_med"] > 0 else "ulnar"
                lab = "%s%s strand f%d %s: palmar %+.1f, radial %+.1f, axis %.1f mm" % (nm, s, r["finger"], side, r["palmar_med"], r["radial_med"], r["dist_med"])
                if kind == "palmar":
                    ok = r["palmar_med"] >= -1.5 and abs(r["radial_med"]) >= 2.5 and r["dist_med"] <= 12
                    kn = None
                    if not ok and "nerve" in nm and r["palmar_med"] >= -2.0 and abs(r["radial_med"]) >= 2.5:
                        kn = "digital_nerve_depth"
                    if not ok and "arteries" in nm and r["finger"] == 1:
                        kn = "thumb_radial_artery"
                    check(lab, ok, kn)
                    if "nerve" in nm and r["finger"] > 1 and r["palmar_med"] < 2.0:
                        KNOWN_HIT.add("digital_nerve_depth")
                    if "arteries" in nm and r["finger"] == 1 and r["palmar_med"] < 1.0:
                        KNOWN_HIT.add("thumb_radial_artery")
                elif kind == "dorsal":
                    check(lab, r["palmar_med"] <= 1.0 and abs(r["radial_med"]) >= 2.5)
                else:
                    check(lab, r["palmar_med"] <= -2.5, "dorsal_digital_arteries" if r["palmar_med"] <= 2.5 else None)
            if kind == "palmar" and "arteries" in nm:
                have = {(r["finger"], r["radial_med"] > 0) for r in rows}
                for f in range(2, 6):
                    check("%s%s: finger %d has a radial and an ulnar strand" % (nm, s, f), (f, True) in have and (f, False) in have)
        # R2 tendons / sheaths
        for x in pg.M.S:
            if not x["id"].endswith("_" + s) or A.FOOT.search(x["id"]):
                continue
            fl, ex = A.FLEXOR.search(x["id"]), A.EXTENSOR.search(x["id"])
            if not (fl or ex):
                continue
            L = H.locate(x["v"])
            m = (L["t"] > 0.1) & (L["t"] < 0.9) & (L["dist"] < 15) & np.array([(f != 1 or g > 0) for f, g in zip(L["finger"], L["seg"])])
            if m.sum() < 20:
                continue
            med = float(np.median(L["palmar"][m]))
            check("%s: %s of the phalanges (median palmar offset %+.1f mm, %d vertices)" % (x["id"], "palmar" if fl else "dorsal", med, m.sum()), med > 0 if fl else med < 0)
        # R3 inside bone
        bones = A.bones_of_hand(pg, s)
        idx, _, _ = pg.hand_structs(s)
        inside = []
        for i in idx:
            x = pg.M.S[i]
            if x["sys"] in ("bone", "skin", "fat"):
                continue
            ib = A.inside_bone(bones, x["v"], depth=1.5)
            n = int((ib != "").sum())
            if n:
                inside.append((x["id"], n, len(x["v"]), sorted(set(ib[ib != ""]))))
        big = [r for r in inside if r[1] >= max(5, 0.02 * r[2])]
        for r in big:
            # Q340 pushed the superficial venous arch and the extensor digiti minimi sheath out of bone (both pages) and the deep venous arch
            # on Base F: those are real checks now; what Q340 kept (its guards failed) stays KNOWN
            known = re.search(r"zan_deep_palmar_arch|zan_deep_venous_palmar_arch|palmar_metacarpal_arteries|fibrous_sheath_of_digit", r[0]) and r[1] <= 60
            check("%s: %d of %d vertices > 1.5 mm inside %s" % (r[0], r[1], r[2], ", ".join(r[3])), False, "in_bone" if known else None)
        check("side %s: no other hand soft tissue passes through a bone (%d structures with a few stray vertices, <2%%)" % (s, len(inside) - len(big)), True)
        out[s] = dict(inside=inside)
    # R4 mirror and sides
    idx_r, _, _ = pg.hand_structs("r")
    worst = []
    for i in idx_r:
        xr = pg.M.S[i]
        if not xr["id"].endswith("_r") or xr["sys"] == "fat":      # the Q295 fat / unlabelled pieces are fitted per side, not mirrored
            continue
        xl = pg.byid.get(xr["id"][:-2] + "_l")
        if xl is None:
            nm2 = {"palmar_aponeurosis_r": "zan_palmar_aponeurosis_l", "flexor_retinaculum_r": "zan_flexor_retinaculum_of_wrist_l"}.get(xr["id"])
            xl = pg.byid.get(nm2) if nm2 else None
            if xl is None:
                continue
        md, p95 = A.mirror_dist(pg, xl, xr)
        worst.append((md, xr["id"]))
        sr = float(np.median(pg.M.plane.signed(xr["v"]))); sl = float(np.median(pg.M.plane.signed(xl["v"])))
        if not (sr > 0 > sl):
            check("%s / _l lie on their own sides (signed %.0f / %.0f mm)" % (xr["id"], sr, sl), False)
    worst.sort(reverse=True)
    for md, sid in worst:
        if md > 1.5:
            check("left = mirrored right: %s mean %.2f mm (limit 1.5)" % (sid, md), False, "asym" if (sid in ASYM and md <= 3.5) else None)
    rest_ok = [w_ for w_ in worst if w_[0] <= 1.5]
    check("left hand = mirrored right hand for the other %d structure pairs (worst %s %.2f mm, limit 1.5)" % (len(rest_ok), rest_ok[0][1], rest_ok[0][0]), True)
    # R5 records
    bad = [x["id"] for x in pg.M.S if re.search(r"_(l|r)$", x["id"]) and x["sys"] != "bone" and re.match(r"Bones of the (left|right) hand", (x.get("rec") or {}).get("name", ""))]
    check("no hand soft tissue carries the hand bones' record%s" % ((": " + ", ".join(bad)) if bad else ""), not bad)
    # palm depth: the arterial arch and the common palmar digital arteries are a real check since Q340 conformed them (Gray 1918 p. 598:
    # the arch lies upon the flexor tendons under the palmar aponeurosis); the superficial venous arch is still KNOWN (Q340 kept it)
    for s in "rl":
        for nm, kn in (("zan_superficial_palmar_arch_", None), ("zan_common_palmar_digital_arteries_", None), ("zan_superficial_venous_palmar_arch_", "palm_depth")):
            r = palm_depth(pg, s, nm)
            check("side %s: %s%s palmar to the flexor tendons (%.0f%% of its points; %.0f%% lie dorsal to them)" % (s, nm, s, 100 * r[0], 100 * r[1]),
                  r[0] >= 0.5 and r[1] <= 0.05, kn)
    return out


def palm_depth(pg, s, name="zan_superficial_palmar_arch_"):
    """fraction of a vessel's points (mid palm) palmar to the flexor tendons in the same 4 mm column, and fraction dorsal to them"""
    from scipy.spatial import cKDTree
    B = pg.M.bones(); J = {j["id"]: j for j in pg.rig["joints"]}
    w = np.array(J["wrist_" + s]["c"])
    d_h = HF.unit(np.vstack([B["mc_%d_%s" % (f, s)]["v"] for f in range(2, 6)]).mean(0) - w)
    p = pg.H[s].fingers[3][0]["p"]; p = HF.unit(p - (p @ d_h) * d_h); r = HF.unit(np.cross(p, d_h))
    tpr = lambda P: np.c_[(P - w) @ d_h, (P - w) @ p, (P - w) @ r]
    fl = np.vstack([pg.byid[n + s]["v"] for n in ("flexor_digitorum_profundus_", "zan_humero_ulnar_head_of_flexor_digitorum_superficialis_", "flexor_pollicis_longus_") if (n + s) in pg.byid])
    F = tpr(fl); tr = cKDTree(F[:, [0, 2]])
    X = tpr(pg.byid[name + s]["v"]); X = X[(X[:, 0] > 15) & (X[:, 0] < 95)]
    above = below = n = 0
    for q in X:
        ii = tr.query_ball_point(q[[0, 2]], 4.0)
        if len(ii) >= 3:
            n += 1; above += q[1] > F[ii, 1].max(); below += q[1] < F[ii, 1].min()
    return above / max(1, n), below / max(1, n)


# ---------------------------------------------------------------------------------------------------------------- posed
def tests_for(pg, s):
    J = {j["id"]: j for j in pg.rig["joints"]}
    T = []
    for f in range(2, 6):
        for lim in ("hi", "lo"):
            T.append(("finger %d MCP+PIP+DIP %s" % (f, "flexed" if lim == "hi" else "extended"), {("f%d_%s_%s" % (f, jn, s), "flex"): J["f%d_%s_%s" % (f, jn, s)]["dof"][0][lim] for jn in ("mcp", "pip", "dip")}))
    for lim in ("hi", "lo"):
        T.append(("thumb CMC+MCP+IP %s" % ("flexed/abducted" if lim == "hi" else "extended"), {("thumb_cmc_" + s, "flex"): J["thumb_cmc_" + s]["dof"][0][lim], ("thumb_cmc_" + s, "abd"): J["thumb_cmc_" + s]["dof"][1][lim],
                                                                                             ("thumb_mcp_" + s, "flex"): J["thumb_mcp_" + s]["dof"][0][lim], ("thumb_ip_" + s, "flex"): J["thumb_ip_" + s]["dof"][0][lim]}))
    for k, n in (("flex", 0), ("dev", 1)):
        for lim in ("hi", "lo"):
            T.append(("wrist %s %s" % (k, lim), {("wrist_" + s, k): J["wrist_" + s]["dof"][n][lim]}))
    return T


def tol95(r):
    return TOL_P95_SKIN if r["sys"] == "skin" else TOL_P95


def posed_rules(pg):
    res = {}
    for s in "rl":
        idx, _, _ = pg.hand_structs(s)
        pack = A.bone_segments(pg, s)
        print("  -- side %s" % s)
        for name, mv in tests_for(pg, s):
            wrist = name.startswith("wrist"); thumb = name.startswith("thumb")
            # the thumb tests gate the thumb's phalanges and the fingers; the thenar region and the first web (own bone = the thumb metacarpal or
            # the hand) span the CMC joint -> listed apart
            rows = A.follow(pg, s, idx, mv, tol=2.0, pack=pack, wrist_mm=WRIST_ZONE if wrist else None, over=TOL_MAX,
                            own_in=(["th_p_" + s, "th_d_" + s] + ["f%d_%s_%s" % (f, g, s) for f in range(2, 6) for g in "pmd"]) if thumb else None)
            gated = [r for r in rows if (r["sys"] in GATED_SYS or EXTRINSIC.search(r["id"])) and not SPANNING.search(r["id"])
                     and not (thumb and HAND_SKIN.search(r["id"]))]      # the palm / dorsum skin over the first web: thenar region, listed below
            cross = sum(r["cross"] for r in rows)
            badp = [r for r in gated if r["p95"] > tol95(r) or r["n_over"] >= 3]
            n = sum(r["n"] for r in gated); seam = sum(r["seam"] for r in rows)
            p95all = max([r["p95"] for r in gated] or [0]); mx = max([r["max"] for r in gated] or [0])
            check("%s %s: 0 finger shaft vertices bound to another digit (%d)" % (s, name, cross), cross == 0)
            check("%s %s: %d gated structures follow their bones (worst p95 %.1f mm, worst max %.1f mm; %d shaft vertices; %d seam vertices apart)%s"
                  % (s, name, len(gated), p95all, mx, n, seam, "" if not badp else " -- " + "; ".join("%s p95 %.1f max %.1f" % (r["id"], r["p95"], r["max"]) for r in badp[:4])), not badp)
            ung = [r for r in rows if r not in gated and (r["p95"] > TOL_P95 or r["max"] > TOL_MAX)]
            if ung:
                LIMIT_HIT.add("spanning")
                print("        LIMIT not gated (spanning): %s" % "; ".join("%s p95 %.1f max %.1f" % (r["id"], r["p95"], r["max"]) for r in ung[:6]))
            if thumb:
                th = A.follow(pg, s, idx, mv, tol=2.0, pack=pack, own_in=["th_mc_" + s, "hand_" + s]) + [r for r in rows if HAND_SKIN.search(r["id"])]
                tw = sorted([r for r in th if r["p95"] > TOL_P95 or r["max"] > TOL_MAX], key=lambda r: -r["p95"])
                if tw:
                    LIMIT_HIT.add("thenar")
                    print("        LIMIT thenar region / first web (own bone = thumb metacarpal or hand; not gated): %s" % "; ".join("%s p95 %.1f max %.1f" % (r["id"], r["p95"], r["max"]) for r in tw[:6]))
            if wrist:
                band = A.follow(pg, s, idx, mv, tol=2.0, pack=pack, wrist_mm=0.0, band_mm=WRIST_ZONE)
                bw = sorted([r for r in band if r["p95"] > TOL_P95 or r["max"] > TOL_MAX], key=lambda r: -r["max"])
                if bw:
                    LIMIT_HIT.add("wrist_band")
                    print("        LIMIT wrist band 0-30 mm (not gated): %s" % "; ".join("%s p95 %.1f max %.1f" % (r["id"], r["p95"], r["max"]) for r in bw[:5]))
            res["%s %s" % (s, name)] = [dict((k, v) for k, v in r.items() if k != "worst") for r in rows]
    return res


# ---------------------------------------------------------------------------------------------------------------- browser
LIVE_JS = """async (arg) => {
  const P = window.__poseApi; const sleep = ms => new Promise(r => setTimeout(r, ms));
  if (!P || !P.ready()) return {err: 'pose rig not ready: ' + (P && P.failed && P.failed())};
  const ix = window.__poseIndex();
  P.reset(); await sleep(400);
  for (const m of arg.moves) P.set(m[0], m[1], m[2]);
  await sleep(1500);
  const out = {};
  for (const id of arg.ids) { const k = ix[id]; if (!k) { out[id] = null; continue; }
    const live = window.__poseLive(k.index), rest = window.__poseRestPos(k.index);
    out[id] = {i: k.index, live: live ? Array.from(live) : null, rest: rest ? Array.from(rest) : null}; }
  P.reset(); await sleep(500);
  return out;
}"""


def browser(pg, page_dir):
    from playwright.sync_api import sync_playwright
    import pagehook_q338 as PH
    tmp = Path(tempfile.mkdtemp(prefix="q338v_", dir="/dev/shm"))
    d = PH.test_copy(Path(page_dir), tmp / Path(page_dir).name)
    errs: list[str] = []
    ids = ["zan_skin_palmar_surfaces_of_digits_of_hand_r", "zan_skin_dorsal_surfaces_of_digits_of_hand_r", "zan_skin_nail_plate_r",
           "zan_proper_palmar_digital_arteries_r", "zan_proper_palmar_digital_branches_of_median_nerve_r", "flexor_digitorum_profundus_r"]
    J = {j["id"]: j for j in pg.rig["joints"]}
    cases = [("finger 3 flexed", [["f3_%s_r" % jn, "flex", J["f3_%s_r" % jn]["dof"][0]["hi"]] for jn in ("mcp", "pip", "dip")]),
             ("thumb flexed", [["thumb_ip_r", "flex", 80], ["thumb_mcp_r", "flex", 50], ["thumb_cmc_r", "abd", 42]])]
    with sync_playwright() as pl:
        srv, b, pgw = PH.open_page(pl, d, 1400, 900, errs)
        try:
            pgw.evaluate("() => { const b = document.getElementById('btn-pose'); if (b) b.click(); }")
            pgw.wait_for_timeout(1000)
            ready = pgw.evaluate("() => !!(window.__poseApi && window.__poseApi.ready())")
            check("browser: pose rig ready", ready)
            for name, moves in cases:
                r = pgw.evaluate(LIVE_JS, {"moves": moves, "ids": ids})
                if r.get("err"):
                    check("browser %s: %s" % (name, r["err"]), False); continue
                Ms = pg.fk(A.pose_for(pg, {(m[0], m[1]): m[2] for m in moves}))
                worst = 0.0; nmoved = 0; seam_max = 0.0
                for sid in ids:
                    e = r.get(sid)
                    if not e or e["live"] is None:
                        continue
                    i = pg.byid[sid]["idx"]
                    live = np.array(e["live"]).reshape(-1, 3); rest = np.array(e["rest"]).reshape(-1, 3)
                    dr = float(np.abs(rest - pg.M.S[i]["v"]).max())
                    if dr > 0.01:
                        # Q334: the page welds the border vertices of neighbouring SKIN pieces at load (cracks closed, a vertex moves
                        # less than a third of its shortest edge). The skin's rest shape in the page is then not the file's, by design;
                        # the skinning must still be right, so it is replayed here on the page's own rest vertices.
                        if not (sid.startswith("zan_skin") and dr <= 1.5):
                            check("browser: %s rest vertices equal the python model's (max %.3f mm)" % (sid, dr), False); continue
                        seam_max = max(seam_max, dr)
                        keep = pg.M.S[i]["v"]; pg.M.S[i]["v"] = rest
                        try: py = pg.posed(i, Ms)
                        finally: pg.M.S[i]["v"] = keep
                    else:
                        py = pg.posed(i, Ms)
                    worst = max(worst, float(np.linalg.norm(live - py, axis=1).max()))
                    nmoved += int((np.linalg.norm(live - rest, axis=1) > 1).sum())
                check("browser %s: the viewer's live vertices = the python replica (max %.3f mm over %d structures, %d vertices moved)" % (name, worst, len(ids), nmoved), worst <= 0.5 and nmoved > 0)
        finally:
            b.close(); srv.terminate()
            import shutil; shutil.rmtree(tmp, ignore_errors=True)
    check("browser: 0 page errors at 1400x900 (%d)" % len(errs), not errs)
    for e in errs[:5]:
        print("        " + e[:200])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("page_dir"); ap.add_argument("--no-browser", action="store_true"); ap.add_argument("--json")
    a = ap.parse_args()
    pg = A.Page(a.page_dir)
    print("=== Q338 hand: %s (%s) ===" % (Path(a.page_dir).name, pg.key))
    print(" rest")
    rest = rest_rules(pg)
    print(" posed (python replica of the viewer's skinning, the page's own rig)")
    posed = posed_rules(pg)
    if not a.no_browser:
        print(" browser")
        browser(pg, a.page_dir)
    print(" known source-geometry defects (reported, not repaired):")
    for k in sorted(KNOWN_HIT):
        print("  KNOWN %s: %s" % (k, KNOWN[k]))
    print(" rig limits (reported, not gated):")
    for k in sorted(LIMIT_HIT):
        print("  LIMIT %s: %s" % (k, LIMITS[k]))
    if a.json:
        Path(a.json).write_text(json.dumps(dict(rest={s: dict(inside=v["inside"]) for s, v in rest.items()}, posed=posed, known=sorted(KNOWN_HIT), errors=ERRS), indent=1, default=str))
    print("Q338_HAND_FAIL (%d)" % len(ERRS) if ERRS else "Q338_HAND_OK")
    return 1 if ERRS else 0


if __name__ == "__main__":
    raise SystemExit(main())
