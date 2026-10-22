"""Q248 (b): the rule-based ligament set and how each is placed.  build(ctx) -> list of dict(id, name, latin, side, V, F, rec, report, status, held)."""
from __future__ import annotations
import numpy as np
import rulelig as RL, guards as GD, landmarks as LM

CIT_ATLA = ("Gray's Anatomy 1918 (20th ed., public domain), 'The Fascia and Muscles of the Pelvis' (levator ani: posterior surface of the superior ramus of the pubis, pelvic surface of the ischial spine and, between them, a "
            "thickened band of the obturator fascia); Terminologia Anatomica 'arcus tendineus musculi levatoris ani'; Kearney R, Sawhney R, DeLancey JOL. Obstet Gynecol 2004;104:168-73, doi 10.1097/01.AOG.0000128906.61529.6b, PMID 15229017")
CIT_ATFP = ("Terminologia Anatomica 'arcus tendineus fasciae pelvis'; DeLancey JOL. Am J Obstet Gynecol 1992;166:1717-28, PMID 1615980 (pubic bone to ischial spine); Stein TA, DeLancey JOL. Obstet Gynecol 2008;111:686-93, "
            "doi 10.1097/AOG.0b013e318163a9a5, PMID 18310372 (continuous with the perineal membrane at the pubis); length ~10 cm in the fixed female pelvis (Occelli et al. 2001, abstract only: plausibility range)")
CIT_TPL = "Terminologia Anatomica 'ligamentum transversum perinei'; Gray's Anatomy 1918 (public domain): the transverse ligament of the pelvis, a thickened band of the deep perineal fascia between the inferior pubic rami below the arcuate pubic ligament"
CIT_AC = "Terminologia Anatomica 'ligamentum anococcygeum'; Gray's Anatomy 1918 (public domain): from the tip of the coccyx to the anal canal (external anal sphincter)"
CIT_PP = "Terminologia Anatomica 'ligamentum puboprostaticum' / 'ligamenta pubovesicalia'; Gray's Anatomy 1918 (public domain): posterior surface of the pubic body to the prostate (male) / bladder neck (female)"
CIT_PAT = ("Terminologia Anatomica 'ligamentum patellae'; Gray's Anatomy 1918 (public domain); Aithal Padur A et al. Surg Radiol Anat 2021;43:2039-46, doi 10.1007/s00276-021-02837-z, PMID 34570285 (length 4.8 / 4.6 cm mean right / left, range 3-6 cm, 50 limbs); "
           "Basso O, Johnson DP, Amis AA. Knee Surg Sports Traumatol Arthrosc 2001;9:2-5, doi 10.1007/s001670000133, PMID 11269580 (fibres converge toward the tibial attachment; patellar apex 39 +- 6 % of the tendon width from its medial edge)")
CIT_SS = ("Terminologia Anatomica 'ligamentum sacrospinale'; Gray's Anatomy 1918 (public domain), 'The Ligaments of the Pelvis': a thin triangular band attached by its apex to the spine of the ischium and by its base to the "
          "lateral margins of the sacrum and coccyx; Vleeming A et al. J Anat 2012;221:537-67 (cited in the repository ligament record data/ligaments/pelvis_ligaments.json)")
CIT_ST = ("Terminologia Anatomica 'ligamentum sacrotuberale'; Gray's Anatomy 1918 (public domain): from the posterior iliac spines, the lower sacrum and the coccyx to the medial margin of the ischial tuberosity")
CIT_IL = ("Terminologia Anatomica 'ligamentum iliolumbale'; Gray's Anatomy 1918 (public domain): from the apex of the transverse process of the fifth lumbar vertebra to the posterior part of the iliac crest")
BASIS_MODEL = "MODELLING CHOICE (no published caliper found by a PubMed / web search in Q248)"

# (width mm, thickness mm)
DIMS = {"ss": (10.0, 2.5), "st": (14.0, 3.5), "il": (12.0, 3.0), "atla": (5.0, 1.5), "atfp": (5.0, 1.5), "tpl": (8.0, 2.0), "ac": (10.0, 3.0), "pp": (8.0, 3.0), "pat_thickness": 5.0}


def _badge(kind, cit, att, rep, dims, basis, page, extra="", area=0.0):
    ln = rep["length_mm"]
    return (f"RULE-BASED (Q248): this {kind} is NOT segmented from imaging and NOT a Z-Anatomy / atlas object: a band built from the bones of THIS page. Attachments: {att}. "
            f"Path: straight line between the attachments pushed out of the bones (clearance half the thickness + 0.3 mm) and smoothed. Cross-section {dims[0]} x {dims[1]} mm elliptical = {basis}. "
            f"Length {ln} mm, cross-sectional area {area} mm2, volume {rep['volume_cm3']} cm3 (closed mesh). End-cap centres lie on the attachment surfaces (signed distance "
            f"{rep['attachments'].get('end_a', {}).get('signed_distance_mm')} / {rep['attachments'].get('end_b', {}).get('signed_distance_mm')} mm; no vertex deeper than 1 mm inside a bone after the push-out: {rep['vertices_deeper_1mm']}). "
            f"Attachment description: {cit}. {extra}An estimate of position: the exact fibre course and thickness of this structure are not resolved by CT or the cryosections.")


def _path_len(P):
    return float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())


def band(ctx, gd, sid, name, latin, side, kind, A, B, endsA, endsB, dims, cit, att_text, basis, ref, region="pelvis", taper=None, n=40, extra="", clear=None, bone_ids=None, min_skin=3.0, skin_pull=None):
    w, t = dims
    clear = clear if clear is not None else t / 2 + RL.CLEAR_EXTRA
    P = RL.route(ctx, A, B, n=n, clear=clear, bone_ids=bone_ids)
    if skin_pull is not None and ctx.key.startswith('own'):
        P = RL.smooth_path(gd.skin_pull(P, skin_pull + t / 2), 3)
    ww = np.full(n, w) if taper is None else np.linspace(taper[0], taper[1], n)
    V, F, c0, c1 = RL.tube(P, ww, t, ref)
    V, rep = RL.finish(ctx, V, F, c0, c1, (endsA, endsB), None, name)
    rep["length_mm"] = round(_path_len(P), 1); rep["straight_distance_mm"] = round(float(np.linalg.norm(B - A)), 1)
    ov, sk, why = gd.gate(V, min_skin, gate_soft=ctx.key.startswith('own'))
    rep["soft_overlap"] = ov; rep["skin_min_depth_mm"] = sk
    if rep["vertices_deeper_1mm"]: why.append("vertices still > 1 mm in bone")
    for k, v in rep["attachments"].items():
        if v["signed_distance_mm"] is not None and abs(v["signed_distance_mm"]) > 1.0:
            why.append(f"{k} not within 1 mm of {v['target']} ({v['signed_distance_mm']} mm)")
    rep["cross_section_mm"] = [float(ww.min()) if taper else w, float(ww.max()) if taper else w, t]
    rec = dict(name=name, latin=latin, folder="ligaments", region=region, source=cit)
    rec["procedural_badge"] = _badge(kind, cit, att_text, rep, (f"{w}" if taper is None else f"{taper[0]}-{taper[1]}", t), basis, ctx.key, extra, round(float(np.pi / 4 * np.mean(ww) * t), 1))
    return dict(id=sid, name=name, latin=latin, side=side, V=V, F=F, rec=rec, report=rep, status="ship" if not why else "held", held=why, endpoints=dict(a=A.tolist(), b=B.tolist()), cat="ligament")


def build(ctx):
    out = []
    gd = GD.Guards(ctx.E)
    F = ctx.F
    male = not ctx.female
    hips = {s: f"hip_bone_{s}" for s in "lr"}
    sgn = {"l": -1.0, "r": 1.0}
    for s in "lr":
        side_word = "left" if s == "l" else "right"
        spine = ctx.ischial_spine(s)
        # tendinous arch of levator ani: upper pubic origin (posterior surface of the pubic body, ~22 mm from the face, upper fifth of the symphysial height) -> ischial spine
        h = F["y_top"] - F["y_bot"]
        for kind, lat, yrel, key, nm, lat_nm, cit in (("atla", 22.0, 0.8 * h, "atla", "Tendinous arch of levator ani", "Arcus tendineus musculi levatoris ani", CIT_ATLA),
                                                         ("atfp", 12.0, 0.45 * h, "atfp", "Arcus tendineus fasciae pelvis", "Arcus tendineus fasciae pelvis", CIT_ATFP)):
            Ap = ctx.pubic_posterior(s, lat, yrel, win=(6.0, 5.0))
            if Ap is None:
                out.append(dict(id=f"{key}_{s}", status="held", held=["no pubic bone vertex in the attachment window"], side=s)); continue
            A, _ = RL.snap_end(ctx, Ap, hips[s]); B, _ = RL.snap_end(ctx, spine, hips[s])
            medial = np.array([-sgn[s], 0, 0])                 # toward the midline
            ref = np.cross(medial, (B - A) / np.linalg.norm(B - A))     # width axis lies in the side-wall plane, thickness points medially
            w, t = DIMS[key]
            att = (f"A = posterior surface of the pubic body of the {side_word} hip bone, {lat:.0f} mm lateral to the symphysial face at {yrel:.0f} mm above the subpubic angle (window +-6 x +-5 mm, posterior-most vertex); "
                   f"B = ischial spine of the {side_word} hip bone (most medial vertex of the posterior ischium {F['y_top']:.0f}-{F['y_top'] + 35:.0f} mm level, weighted toward y_top + 15 mm)")
            e = band(ctx, gd, f"{'tendinous_arch_levator_ani' if key == 'atla' else 'arcus_tendineus_fasciae_pelvis'}_{s}", f"{nm} ({side_word})", f"{lat_nm} {'sinister' if s == 'l' else 'dexter'}", s,
                     nm.lower(), A, B, hips[s], hips[s], (w, t), cit, att, BASIS_MODEL, ref)
            out.append(e)
    # transverse perineal ligament: between the two inferior pubic rami just below the symphysis
    pts = []
    for s in "lr":
        T = np.array([F["x_mid"] + sgn[s] * (F["half_gap"] + 6.0), F["y_bot"] - 4.0, F["z_front"] - 10.0])
        d, a, n, p = ctx.bf.signed(T[None], [hips[s]])
        pts.append(p[0])
    A, B = pts
    w, t = DIMS["tpl"]
    att = ("A, B = surface of the left / right inferior pubic ramus nearest to a point 6 mm lateral to the symphysial face, 4 mm below the subpubic angle and 10 mm behind the anterior face")
    e = band(ctx, gd, "transverse_perineal_ligament", "Transverse perineal ligament (of the pelvis)", "Ligamentum transversum perinei", "m", "transverse perineal ligament", A, B, hips["l"], hips["r"], (w, t),
             CIT_TPL, att, BASIS_MODEL, np.array([0, 1.0, 0]), n=16, bone_ids=[hips["l"], hips["r"]])
    out.append(e)
    # anococcygeal ligament: coccyx tip -> posterior wall of the external anal sphincter (male pages, Base female; the female Imaging-based / Combined pages get the CVH ligament)
    if True:                                              # female Imaging-based / Combined pages: shipped only if the CVH ligament is not (see collect.py)
        cx = ctx.find("coccyx") or ctx.find("sacrum#2")
        eas = ctx.find("external_anal_sphincter", "zan_external_anal_sphincter", "zan_anal_sphincter_external")
        if cx is not None and eas is not None:
            tip = cx["v"][np.argmin(cx["v"][:, 1])]
            bid = "coccyx" if "coccyx" in ctx.E else "sacrum#2"
            A, _ = RL.snap_end(ctx, tip, bid)
            ev = eas["v"]
            cand = ev[np.abs(ev[:, 0] - F["x_mid"]) < 6]
            if len(cand):
                Bp = cand[np.argmin(cand[:, 2])]
                w, t = DIMS["ac"]
                # B on the sphincter surface: the posterior-most midline vertex
                att = f"A = tip (lowest point) of the coccyx; B = posterior-most midline vertex of the external anal sphincter ({eas['id']})"
                e = band(ctx, gd, "anococcygeal_ligament", "Anococcygeal ligament", "Ligamentum anococcygeum", "m", "anococcygeal ligament", A, Bp, bid, None, (w, t), CIT_AC, att, BASIS_MODEL,
                         np.array([1.0, 0, 0]), n=24)
                out.append(e)
    # puboprostatic (male) / pubovesical (Base female) ligaments
    organ = ctx.find("prostate", "zan_prostate") if male else ctx.find("urinary_bladder", "zan_urinary_bladder")
    if organ is not None:
        from scipy.spatial import cKDTree
        kd = cKDTree(organ["v"])
        for s in "lr":
            Ap = ctx.pubic_posterior(s, 8.0, 0.35 * (F["y_top"] - F["y_bot"]), win=(5.0, 5.0))
            if Ap is None: continue
            A, _ = RL.snap_end(ctx, Ap, hips[s])
            j = kd.query(A)[1]; B = organ["v"][j]
            w, t = DIMS["pp"]
            word = "left" if s == "l" else "right"
            att = (f"A = posterior surface of the pubic body of the {word} hip bone, 8 mm lateral to the symphysial face, 35 % of the symphysial height above the subpubic angle; "
                   f"B = nearest vertex of the {'prostate' if male else 'bladder'} ({organ['id']}) to A")
            e = band(ctx, gd, f"{'puboprostatic' if male else 'pubovesical'}_ligament_{s}", f"{'Puboprostatic' if male else 'Pubovesical'} ligament ({word})",
                     f"Ligamentum {'puboprostaticum' if male else 'pubovesicale'} {'sinister' if s == 'l' else 'dexter'}", s, "puboprostatic ligament" if male else "pubovesical ligament", A, B, hips[s], None, (w, t), CIT_PP, att,
                     BASIS_MODEL, np.array([0, 1.0, 0]), n=16, extra=("The organ end lies on the organ mesh of this page (not a bone). " if True else ""))
            if np.linalg.norm(B - A) > 45: e["status"] = "held"; e["held"].append("organ more than 45 mm from the pubis")
            out.append(e)
    # patellar ligament
    for s in "lr":
        pat, tib = ctx.find(f"patella_{s}"), ctx.find(f"tibia_{s}")
        if pat is None or tib is None: continue
        pv, tv = pat["v"], tib["v"]
        apex = pv[np.argmin(pv[:, 1])]
        ytop = tv[:, 1].max()
        c = tv[(tv[:, 1] < ytop - 20) & (tv[:, 1] > ytop - 65)]
        tub = c[np.argmax(c[:, 2])]
        A, _ = RL.snap_end(ctx, apex, f"patella_{s}"); B, _ = RL.snap_end(ctx, tub, f"tibia_{s}")
        # patellar width in the distal third (x extent of the patella vertices within 15 mm above the apex)
        band_v = pv[pv[:, 1] < apex[1] + 15]
        wp = float(np.ptp(band_v[:, 0]))
        wp = min(0.85 * wp, 30.0)                              # the flat band must stay inside the curved skin: <= 85 % of the patellar width and <= 30 mm (textbook width of the patellar ligament, ~3 cm)
        t = DIMS["pat_thickness"]
        word = "left" if s == "l" else "right"
        att = (f"A = patellar apex (lowest vertex of the {word} patella); B = tibial tuberosity (anterior-most vertex of the {word} tibia between 20 and 65 mm below the plateau); width at the patella = 85 % of the patellar width 15 mm above the apex, at most 30 mm "
               f"({wp:.0f} mm), narrowing to 80 % at the tuberosity (fibres converge distally)")
        e = band(ctx, gd, f"patellar_ligament_{s}", f"Patellar ligament ({word})", f"Ligamentum patellae {'sinister' if s == 'l' else 'dexter'}", s, "patellar ligament", A, B, f"patella_{s}", f"tibia_{s}", (wp, t), CIT_PAT, att,
                 "width = 85 % of the measured patellar width (max 30 mm), tapering to 80 % (Basso 2001: fibres converge distally); thickness 5 mm = MODELLING CHOICE (no value obtained from the cited papers)", np.array([1.0, 0, 0]), region="knee", taper=(wp, 0.8 * wp), n=24, min_skin=0.5, skin_pull=3.0)
        L = e["report"]["length_mm"]
        if not (30.0 <= L <= 60.0): e["status"] = "held"; e["held"].append(f"length {L} mm outside the published range 30-60 mm (Aithal Padur 2021)")
        out.append(e)
    # pelvic girdle ligaments for the OWN pages that the Z-Anatomy transfer could not place (collect.py drops a rule ligament whose id was shipped by the transfer): sacrospinous, sacrotuberous, iliolumbar
    if ctx.key.startswith("own"):
        sac_ids = [i for i, e in ctx.E.items() if e["sys"] == "bone" and (i == "coccyx" or i.startswith("sacrum")) and "zfill" not in i]
        sv = np.vstack([ctx.E[i]["v"] for i in sac_ids]); owner = np.concatenate([[i] * len(ctx.E[i]["v"]) for i in sac_ids])
        ylow = float(sv[:, 1].min())
        lum = sorted([i for i in ctx.E if i.startswith("lumbar_vertebrae#")], key=lambda x: float(ctx.E[x]["v"][:, 1].mean()), reverse=True)    # top -> bottom (the page numbers them bottom-up)
        for s in "lr":
            word = "left" if s == "l" else "right"
            sg = sgn[s]
            spine = ctx.ischial_spine(s)
            A, _ = RL.snap_end(ctx, spine, hips[s])
            m = (sv[:, 1] < ylow + 50) & (sg * (sv[:, 0] - F["x_mid"]) > -3)
            j = np.argmin(np.where(m, np.linalg.norm(sv - A, axis=1), 1e9)); B0 = sv[j]; bidb = str(owner[j])
            B, _ = RL.snap_end(ctx, B0, bidb)
            w, t = DIMS["ss"]
            e = band(ctx, gd, f"sacrospinous_ligament_{s}", f"Sacrospinous ligament ({word})", f"Ligamentum sacrospinale {'sinister' if s == 'l' else 'dexter'}", s, "sacrospinous ligament", A, B, hips[s], bidb, (w, t), CIT_SS,
                     f"A = ischial spine of the {word} hip bone (geometric rule, see the pelvic arches); B = the point of the sacrum / coccyx ({bidb}) nearest to A within the lowest 50 mm of the sacrococcygeal column (shortest path); fan 12 mm at the sacrum narrowing to 7 mm at the spine",
                     BASIS_MODEL, np.cross(np.array([0, 1.0, 0]), (B - A) / np.linalg.norm(B - A)), taper=(12.0, 7.0), n=24, region="pelvis")
            e["report"]["length_published_mm"] = "43 +- 6.6 mm (nine embalmed hemipelves; web abstract, plausibility only)"
            out.append(e)
            # sacrotuberous: ischial tuberosity (lowest vertex of the posterior ischium) -> lateral margin of the lower sacrum / coccyx
            hv = ctx.E[hips[s]]["v"]
            mt = (hv[:, 2] < F["z_front"] - 60) & (sg * (hv[:, 0] - F["x_mid"]) > 20)
            tub = hv[np.argmin(np.where(mt, hv[:, 1], 1e9))]
            At, _ = RL.snap_end(ctx, tub, hips[s])
            m2 = (sv[:, 1] < ylow + 90) & (sv[:, 1] > ylow + 15) & (sg * (sv[:, 0] - F["x_mid"]) > -3)
            j2 = np.argmin(np.where(m2, np.linalg.norm(sv - At, axis=1), 1e9)); B2 = sv[j2]; bid2 = str(owner[j2])
            Bt, _ = RL.snap_end(ctx, B2, bid2)
            w, t = DIMS["st"]
            e = band(ctx, gd, f"sacrotuberous_ligament_{s}", f"Sacrotuberous ligament ({word})", f"Ligamentum sacrotuberale {'sinister' if s == 'l' else 'dexter'}", s, "sacrotuberous ligament", At, Bt, hips[s], bid2, (w, t), CIT_ST,
                     f"A = ischial tuberosity of the {word} hip bone (lowest vertex of the posterior ischium); B = the point of the sacrum / coccyx ({bid2}) nearest to A between 15 and 90 mm above the lowest sacrococcygeal point (shortest path); a single band stands for the fan of origins",
                     BASIS_MODEL, np.cross(np.array([0, 1.0, 0]), (Bt - At) / np.linalg.norm(Bt - At)), taper=(10.0, 14.0), n=30, region="pelvis")
            out.append(e)
            # iliolumbar: lowest lumbar vertebra transverse process -> iliac crest
            if lum:
                lv = ctx.E[lum[-1]]["v"]
                mm = lv[:, 1] > lv[:, 1].min() + 0.35 * np.ptp(lv[:, 1])
                tp = lv[mm][np.argmax(sg * (lv[mm][:, 0] - F["x_mid"]))]
                Al, _ = RL.snap_end(ctx, tp, lum[-1])
                m3 = hv[:, 1] >= Al[1] - 10
                jj = np.argmin(np.where(m3, np.linalg.norm(hv - Al, axis=1), 1e9)); Bl, _ = RL.snap_end(ctx, hv[jj], hips[s])
                w, t = DIMS["il"]
                e = band(ctx, gd, f"iliolumbar_ligament_{s}", f"Iliolumbar ligament ({word})", f"Ligamentum iliolumbale {'sinister' if s == 'l' else 'dexter'}", s, "iliolumbar ligament", Al, Bl, lum[-1], hips[s], (w, t), CIT_IL,
                         f"A = tip of the transverse process of the lowest lumbar vertebra ({lum[-1]}, lateral-most vertex of its upper 65 %); B = nearest vertex of the {word} hip bone at or above that height (iliac crest region)",
                         BASIS_MODEL, np.array([0, 0, 1.0]), n=16, region="pelvis")
                if not (10.0 <= e["report"]["length_mm"] <= 80.0): e["status"] = "held"; e["held"].append("length outside the 10-80 mm sanity window (no published length used)")
                out.append(e)
    return out
