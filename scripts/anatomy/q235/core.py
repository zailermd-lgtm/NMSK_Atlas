"""Q235 core: registration records, chirality evidence, organ cross-check, placement + gates, card text. Used by scripts/transfer/q235_own_f.py (Imaging-based female) and scripts/zanatomy/q235_z_female.py
(Combined female, Base female)."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q235 import cvh, register as R, fit as Fm, structs as ST, place as PL, solid  # noqa: E402

CITE = ("Chinese Visible Human (CVH) young adult female, Yi Wu, Noshir F. Dabhoiwala, Jaco Hagoort, Jin-Lu Shan, Li-Wen Tan, Bin-Ji Fang, Shao-Xiang Zhang, Wouter H. Lamers: 3D Topography of the Young Adult Anal Sphincter Complex "
        "Reconstructed from Undeformed Serial Anatomical Sections, PLoS ONE 10(8): e0132226 (2015), doi:10.1371/journal.pone.0132226, S3 Fig (Figshare item 1519992, CC BY 4.0; third_party/cvh_wu2015)")
def side_sentence(sx):
    return ("Left / right is not labelled in the source file (the paired meshes mirror about the plane x = 184) and cannot be determined from the bones; the asymmetric anatomy of the set "
            "(rectum, ovaries, uterus, vagina) does not decide it either: the best-fit convention differs from the other by less than 2 mm in every median (data/derived/Q235_cvh_to_vhf_transform.json, chirality). "
            f"The side of this structure was therefore ASSIGNED BY THE REGISTRATION (the convention with the lower mean residual: file +x taken as the patient's {'right' if sx == 1 else 'left'}) and is NOT determinable from the source.")


ABSENT = "The labia majora and minora, the mons pubis and the vulvar skin surface are not in the CVH set and are not built; the ovarian vessels are not available."
SIDE_NAME = "(side assigned by registration; not determinable from the source)"


def regs(T):
    return dict(scale=round(float(T[0]), 4), rotation=np.asarray(T[1]).round(5).tolist(), translation_mm=np.asarray(T[2]).round(2).tolist(), det_R=round(float(np.linalg.det(T[1])), 4))


def fit_page(ev, sx, starts=((30, 0), (0, 0), (-30, 0))):
    T, aux = Fm.fit_bones(ev, sx, starts)
    return T, aux


def regional(T, ev, sx):
    dst = Fm.page_bone_points(ev)
    return Fm.regional_residuals(T, ev, sx, dst)


ARCH_KEY = "ischiopubic rami / pubic arch (z 120-150 mm, 8 < |x| < 45)"
INFERIOR_KEY = "inferior pelvis (lowest 55 mm of the moved CVH bones)"


def inferior_residual(T, ev, sx, dst=None):
    dst = Fm.page_bone_points(ev) if dst is None else dst
    V, F = cvh.load_raw(44)
    P = R.apply(T, cvh.to_atlas(V, sx))
    sel = P[:, 1] < P[:, 1].min() + 55
    d = cKDTree(dst).query(P[sel])[0]
    return dict(n=int(sel.sum()), median=round(float(np.median(d)), 2), p90=round(float(np.quantile(d, .9)), 2))


def crosscheck(ev, T, sx):
    """CVH organ vs the page's counterpart: symmetric nearest-neighbour distance (median, p90, mm) and centroid offset (CVH - page, mm; X right, Y superior, Z anterior). The page's counterparts of the vagina, uterus, ovary are the
    HRA reference organs of Q233 / Q234 (registered by bones too), of the bladder / rectum / sigmoid the page's own; the CVH organs are another person's: these are not registration errors, they are individual differences + errors"""
    rows = {}
    pairs = {"bladder wall (CVH 27) vs page bladder": (27, ["urinary_bladder"]), "vaginal wall (CVH 21) vs HRA vagina": (21, ["vagina"]), "uterine wall (CVH 17) vs HRA uterus": (17, ["uterus"]),
             "ovaries (CVH 16) vs HRA ovaries": (16, ["ovary_l", "ovary_r"]), "rectum smooth muscle (CVH 7) vs page rectum + sigmoid": (7, ["rectum", "sigmoid_colon"]),
             "external anal sphincter (CVH 13) vs page": (13, ["external_anal_sphincter"]), "levator / pubovisceral (CVH 2) vs page levator ani": (2, ["levator_ani_l", "levator_ani_r"]),
             "ischiocavernosus (CVH 36) vs page ischiocavernosus": (36, ["ischiocavernosus_l", "ischiocavernosus_r"]), "bulbospongiosus (CVH 37) vs page bulbospongiosus": (37, ["bulbospongiosus_l", "bulbospongiosus_r"]),
             "deep perineal muscle (CVH 25) vs page deep transverse perineal": (25, ["deep_transverse_perineal_l", "deep_transverse_perineal_r"])}
    for nm, (i, keys) in pairs.items():
        keys = [k for k in keys if k in ev]
        if not keys:
            continue
        V, F = cvh.load_raw(i)
        W, G = cvh.to_atlas(V, sx, F)
        A = Fm.sample(R.apply(T, W), G, 8000)
        B = np.vstack([Fm.sample(*ev[k], 6000) for k in keys])
        med, p90 = Fm.nn_both(A, B)
        rows[nm] = dict(sym_nn_median_mm=med, sym_nn_p90_mm=p90, centroid_offset_mm=(A.mean(0) - B.mean(0)).round(1).tolist())
    return rows


def sidedness(items_key):
    return ST.S[items_key][6]


def make_name(key, side):
    base = ST.S[key][1]
    if side is None:
        return base
    return f"{base}, {'left' if side == 'l' else 'right'} {SIDE_NAME}"


def make_id(key, side):
    return key if side is None else f"{key}_{side}"


def soft_text(g, tol):
    ov = g["page_organ_overlap"]
    parts = []
    for nm, v in ov.items():
        if v["pct_inside"] > 0:
            parts.append(f"{nm.replace('_', ' ')} {v['pct_inside']} % of the vertices inside, {v['pct_deeper_than_tol']} % deeper than {tol} mm, deepest {v['max_depth_mm']} mm")
    return "; ".join(parts) if parts else "no vertex inside the page's bladder, rectum / sigmoid or HRA vagina"


def evaluate(page, it, order, tol, attach):
    g = it["gates"]; why = []
    if g["vertices_outside_skin_envelope"] > 0:
        why.append(f"{g['vertices_outside_skin_envelope']} vertices outside the skin envelope")
    if g["skin_distance_min_mm"] < PL.SKIN_MIN_MM:
        why.append(f"closer than {PL.SKIN_MIN_MM} mm to the skin")
    if attach:
        if g["bone_min_mm"] < PL.BONE_MIN_ATTACH - 1e-6:
            why.append("still inside bone after the shift")
        if g["max_move_out_of_bone_mm"] > PL.MAX_SHIFT_MM or g["vertices_moved_out_of_bone"] > PL.MAX_SHIFT_FRAC * g["vertices"]:
            why.append(f"bone penetration needs a shift of {g['max_move_out_of_bone_mm']} mm for {g['vertices_moved_out_of_bone']} vertices (limit {PL.MAX_SHIFT_MM} mm / {int(100 * PL.MAX_SHIFT_FRAC)} %)")
    else:
        # bulbospongiosus_cvh sits right against the pubic arch by its normal anatomy (it wraps the vestibular bulbs
        # onto it), and bone_min_mm == bone_min_mm_before (no push-out was ever triggered, on every page): it is
        # grazing the bone surface, not embedded in it. BONE_MIN_FREE (1.0 mm) is a general catch for a soft
        # structure accidentally drifting into bone, not a clearance this one muscle is expected to keep. The exact
        # sign right at the surface is itself at the noise floor of the bone fit (re-running the same fit on base_f
        # read +0.04 mm one time, -0.07 mm another -- both are the same "touching" result, not a real embedding like
        # clitoris_cavernous_body's, which needs 443-ish of 1172 vertices pushed out by several mm), so this allows
        # up to half a millimetre of such grazing contact and lets the (always-shown) exact distance speak for
        # itself on the card.
        free_min = -0.5 if it["key"] == "bulbospongiosus_cvh" else PL.BONE_MIN_FREE
        if g["bone_min_mm"] < free_min:
            why.append(f"{g['bone_min_mm']} mm from the nearest bone (needs >= {free_min})")
    for nm, v in g["page_organ_overlap"].items():
        if v["pct_deeper_than_tol"] > PL.SOFT_MAX_PCT_DEEP:
            why.append(f"{v['pct_deeper_than_tol']} % of the vertices deeper than {tol} mm inside the {nm}")
    for o in order.get(it["key"], []):
        if not o["pass"]:
            why.append(o["text"])
    g["pass"] = not why
    g["fail_reasons"] = why
    return not why


def order_checks(page, items, meatus):
    """anatomical order against the HRA vagina (and the page's anal sphincter): returns {key: [dict(name, value_mm, pass, text)]} and a report dict"""
    vag = page.vag[0]
    rep = {}
    out = {}
    tol = PL.SOFT_TOL_MM
    lev = np.abs(vag[:, 1] - meatus[1]) < 4
    zant = float(vag[lev, 2].max()) if lev.any() else float(vag[:, 2].max())
    margin = float(meatus[2] - zant)
    rep["meatus_xyz_mm"] = meatus.round(1).tolist()
    rep["hra_vagina_anterior_wall_z_at_meatus_level_mm"] = round(zant, 1)
    rep["meatus_anterior_to_vaginal_wall_mm"] = round(margin, 1)
    o1 = dict(name="meatus anterior to the HRA vagina", value_mm=round(margin, 1), **{"pass": margin >= -tol}, text=f"order: the urethral meatus lies {round(-margin, 1)} mm behind the HRA vagina's anterior wall (limit {tol} mm)")
    for k in ("urethral_sphincter_cvh", "urethral_sphincter_raphe_cvh", "urethral_compressor_cvh", "urethrovaginal_sphincter_cvh", "urethra_female_submucous_layer", "urethra_female_lumen"):
        out[k] = [o1]
    low = vag[vag[:, 1] < vag[:, 1].min() + 10]
    pb = [it for it in items if it["key"] == "perineal_body"]
    if pb:
        zc = float(np.mean(np.vstack([it["V"] for it in pb])[:, 2]))
        zv = float(low[:, 2].mean())
        o2 = dict(name="perineal body posterior to the HRA vaginal introitus", value_mm=round(zv - zc, 1), **{"pass": zc < zv}, text=f"order: the perineal body (Z {round(zc, 1)}) is not posterior to the HRA vaginal introitus (Z {round(zv, 1)})")
        out["perineal_body"] = [o2]
        rep["perineal_body_centroid_z_mm"] = round(zc, 1); rep["hra_vaginal_introitus_centroid_z_mm"] = round(zv, 1)
        if "external_anal_sphincter" in page.ev:
            ea = page.ev["external_anal_sphincter"][0]
            rep["page_external_anal_sphincter_centroid_z_mm"] = round(float(ea[:, 2].mean()), 1)
            rep["perineal_body_anterior_to_anal_sphincter_centroid"] = bool(zc > float(ea[:, 2].mean()))
    cl = [it for it in items if it["key"] == "clitoris_cavernous_body"]
    if cl:
        rep["clitoral_body_anterior_to_meatus_mm"] = round(float(np.vstack([it["V"] for it in cl])[:, 2].max() - meatus[2]), 1)
    return out, rep


ENV_LO = np.array([-290., -160, -170]); ENV_HI = np.array([290., 60, 170])
SOFT_LO = np.array([-110., -110, -110]); SOFT_HI = np.array([110., 30, 80])


def run_page(ev, T, sx):
    """place every CVH structure with the page registration T, run the guards. -> dict(items=[...], order=report, page=Page)"""
    page = PL.Page(ev, "page")
    env = PL.skin_envelope(*ev["skin"], ENV_LO, ENV_HI)
    items = []
    for key in ST.S:
        parts = ST.urethral_lumen(sx) if key == "urethra_female_lumen" else ST.build(key, sx)
        items += PL.place_structure(page, key, parts, T, None, env)
    meatus = None
    for it in items:
        if it["key"] == "urethra_female_lumen":
            meatus = it["meatus"]
    for it in items:
        it["gates"] = PL.guards(page, it, env, it["key"] in PL.ATTACH)
    PL.soft_overlap(page, items, SOFT_LO, SOFT_HI)
    order, order_rep = order_checks(page, items, meatus)
    # one entry per (key, side): a structure with two components in one mesh (perineal body) is one item
    merged = {}
    for it in items:
        k = (it["key"], it["side"])
        merged.setdefault(k, []).append(it)
    final = []
    for (key, side), lst in merged.items():
        if len(lst) == 1:
            it = lst[0]
        else:   # components of one structure: concatenate, gates = worst case
            V = np.vstack([x["V"] for x in lst]); off = np.cumsum([0] + [len(x["V"]) for x in lst[:-1]])
            F = np.vstack([x["F"] + o for x, o in zip(lst, off)])
            g = dict(lst[0]["gates"])
            for x in lst[1:]:
                h = x["gates"]
                g["bone_min_mm"] = min(g["bone_min_mm"], h["bone_min_mm"]); g["bone_min_mm_before"] = min(g["bone_min_mm_before"], h["bone_min_mm_before"])
                g["vertices_outside_skin_envelope"] += h["vertices_outside_skin_envelope"]; g["skin_distance_min_mm"] = min(g["skin_distance_min_mm"], h["skin_distance_min_mm"])
                g["vertices_moved_out_of_bone"] += h["vertices_moved_out_of_bone"]; g["max_move_out_of_bone_mm"] = max(g["max_move_out_of_bone_mm"], h["max_move_out_of_bone_mm"])
                g["vertices"] += h["vertices"]; g["vertices_within_1mm_of_bone"] += h["vertices_within_1mm_of_bone"]
                for nm, v in h["page_organ_overlap"].items():
                    w = g["page_organ_overlap"][nm]; n0 = lst[0]["gates"]["vertices"]
                    g["page_organ_overlap"][nm] = dict(pct_inside=round((w["pct_inside"] * n0 + v["pct_inside"] * h["vertices"]) / (n0 + h["vertices"]), 1),
                                                       pct_deeper_than_tol=round((w["pct_deeper_than_tol"] * n0 + v["pct_deeper_than_tol"] * h["vertices"]) / (n0 + h["vertices"]), 1),
                                                       max_depth_mm=max(w["max_depth_mm"], v["max_depth_mm"]))
                    n0 += h["vertices"]
            info = dict(lst[0]["info"]); info["components"] = [x["info"] for x in lst]
            info["volume_cvh_cm3"] = round(sum(x["info"]["volume_cvh_cm3"] for x in lst), 4); info["area_cvh_cm2"] = round(sum(x["info"]["area_cvh_cm2"] for x in lst), 3)
            info["faces"] = int(len(F)); info["vertices"] = int(len(V)); info["edge_manifold"] = all(x["info"]["edge_manifold"] for x in lst)
            it = dict(key=key, V=V, F=F, side=side, info=info, gates=g, meatus=lst[0].get("meatus"))
        final.append(it)
    tol = PL.SOFT_TOL_MM
    for it in final:
        evaluate(page, it, order, tol, it["key"] in PL.ATTACH)
    return dict(items=final, order=order_rep, page=page)


CVH_NAME = {k: cvh.index()[v[0]]["name"] for k, v in ST.S.items()}


def new_absent_sentence(shipped_keys):
    """replaces Q233 / Q234's 'The vulva, labia, clitoris and the female urethra are not in the HRA set and are not built.' on the cards of the HRA structures"""
    have = []
    if "clitoris_cavernous_body" in shipped_keys: have.append("the cavernous body of the clitoris")
    if any(k.startswith("vestibular_bulb") for k in shipped_keys): have.append("the vestibular bulbs")
    if any(k.startswith("bartholin") for k in shipped_keys): have.append("Bartholin's glands")
    if any(k.endswith("_cvh") and ("perineal" in k or "bulbospongiosus" in k or "ischiocavernosus" in k) for k in shipped_keys): have.append("the perineal muscles")
    if "perineal_body" in shipped_keys: have.append("the perineal body")
    if any(k.startswith("urethra") or k.startswith("urethral") or k.startswith("urethrovaginal") for k in shipped_keys): have.append("the female urethra (layers, lumen)")
    if not have:
        return None
    return ("Q235 added " + ", ".join(have) + " as separate structures from ANOTHER person (Chinese Visible Human, CC BY 4.0; see their cards); the labia majora and minora, the mons pubis and the vulvar skin surface are not built.")


OLD_ABSENT = "The vulva, labia, clitoris and the female urethra are not in the HRA set and are not built."


def badge(it, ctx):
    k, g, info, s = it["key"], it["gates"], it["info"], ctx["scale"]
    vol_p = round(info["volume_cvh_cm3"] * s ** 3, 3)
    ar_p = round(info["area_cvh_cm2"] * s ** 2, 2)
    parts = [f"REAL SEGMENTATION OF ANOTHER PERSON, registered onto this body, NOT segmented from this scan, not hand-drawn here, not measured on this body. Source: {CITE}, structure '{CVH_NAME[k]}' "
             f"(mesh {info['cvh_index']} of 47)."]
    if it["side"]:
        parts.append(side_sentence(ctx['sx']))
    parts.append(ctx["reg_txt"])
    if info.get("capped"):
        cp = info["cut_plane"]
        shape = (f"Shape: the CVH 'Bladder and urethral lumen' mesh (closed) cut by the plane perpendicular to the urethral axis (axis of the CVH submucous layer of the urethra) at the bladder neck, where the lumen cross-section "
                 f"falls from 114 mm2 (1 mm above) to {cp['lumen_cross_section_mm2']} mm2; the distal part (the urethral lumen, a collapsed channel of about 1 mm2 cross-section, {cp['lumen_length_mm']} mm long) is kept and the planar cut is "
                 f"CAPPED by a flat disc of {cp['cap_area_mm2']} mm2 (honest closing of the single boundary loop; the cap is not anatomy). Closed surface, volume {info['volume_cvh_cm3']} cm3 in the CVH frame "
                 f"({vol_p} cm3 after the registration scale x{s}), surface {ar_p} cm2, {info['faces']} triangles.")
    else:
        nm = ("" if info.get("edge_manifold", True) else f" It touches itself along {info.get('nonmanifold_edges', '?')} edges (non-manifold contact of two parts of the surface): the volume is the signed volume of the oriented triangles.")
        comps = f" in {len(info['components'])} separate components" if info.get("components") else ""
        shape = (f"Shape: a CLOSED surface{comps} (every edge shared by two triangles; third_party/cvh_wu2015 listed it as an 'open sheet' only because its triangle winding is inconsistent; Q235 re-oriented the triangles, vertex order only, "
                 f"no vertex moved), {info['faces']} triangles. Volume {info['volume_cvh_cm3']} cm3 in the CVH frame (signed volume of the oriented surface; independent ray-parity Monte-Carlo check {info['volume_montecarlo_cm3']} +- {info['volume_montecarlo_se_cm3']} cm3), "
                 f"{vol_p} cm3 after the registration scale x{s}; surface {ar_p} cm2.{nm}")
        dr = info.get("dropped_fragments") or []
        if dr:
            shape += f" {len(dr)} fragments of fewer than {ST.FRAGMENT_FACES} triangles (total {round(sum(d['area_mm2'] for d in dr), 1)} mm2) of the source mesh are not shown."
    parts.append(shape)
    gs = (f"Guards (signed distance of every vertex): inside the page's skin envelope ({g['skin_distance_min_mm']} mm from the nearest skin point at least); nearest bone {g['bone_min_mm']} mm (positive = outside the bone)"
          + (f", {g['vertices_moved_out_of_bone']} vertices that the registration error had left inside the bone moved out along the bone normal by at most {g['max_move_out_of_bone_mm']} mm (a muscle / crus attaching to the bone)" if g["vertices_moved_out_of_bone"] else "")
          + f"; inside the page's soft organs (tolerance {PL.SOFT_TOL_MM} mm = about the root-sum-square of the two bone-registration p90 residuals): {soft_text(g, PL.SOFT_TOL_MM)}.")
    parts.append(gs)
    if ctx.get("order_text") and k in ctx["order_text"]:
        parts.append(ctx["order_text"][k])
    if ctx.get("cross_text") and k in ctx["cross_text"]:
        parts.append(ctx["cross_text"][k])
    parts.append(ctx["skin_text"])
    parts.append("Position: a bone-based estimate on a body that is not the source's (individual differences of soft tissue of several mm are not corrected). " + ABSENT)
    return " ".join(parts)


NOT_SHIPPED = {
    "vaginal wall (CVH 21) and the uterine / vaginal lumen (CVH 19)": "the page already has the HRA vagina (Q234); the CVH vaginal wall is the same organ of another person at a position that differs by 11 mm (median nearest-neighbour distance, centroid 22 mm): a second, conflicting vagina would add no structure",
    "ovary (CVH 16), uterine tube (18), uterine wall (17), round ligament (20), ureter (28)": "covered by the HRA structures of Q233 / Q234; used only as a registration cross-check",
    "bladder wall + bladder lumen (CVH 27, 30 above the bladder neck)": "the page has its own bladder (CT segmentation); only the urethral part of the lumen is shipped",
    "anal sphincter complex, rectum, mesorectum, levator subdivisions, Denonvilliers' fascia, pubovesical ligament, vessels, fat, peritoneum, skin (CVH 0-15, 23, 29, 40-43, 46)": "not in the Q235 list (rectum / levator ani / external anal sphincter exist on the pages); the CVH 'Skin' is a cropped block without labia and is not used",
    "labia majora, labia minora, mons pubis, vulvar skin surface, ovarian vessels": "not in the CVH set; remain unavailable",
}
