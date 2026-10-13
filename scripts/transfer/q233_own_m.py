#!/usr/bin/env python3
"""Q233 (own male): his Q224 bundle -> build/viewer_m_hr_q233. His own CT / cryosection give only the prostate (Q170) of the male-only organs; the page lacked testes, epididymides, deferent ducts, seminal
vesicles, penis (corpora, glans), male urethra and ejaculatory ducts. They are FILLED from the Z-Anatomy male fitted to him (page build/q225/viewer_zan_vhm, his frame, Q195 fit + Q186c skin clamp), as badged
Z-Anatomy fills (Source class 'Filled from Z-Anatomy'), each inside guards: inside his own CT skin, out of his bones, out of his bladder / rectum / sigmoid / prostate. Everything else byte-identical (ship diff).
    python3 scripts/transfer/q233_own_m.py [--out build/viewer_m_hr_q233]"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer.q233_own_f import mask_of, keyed  # noqa: E402
import q233_load as Q  # noqa: E402

SUBJECT = "xfer_zan2vhm_genital_q233"
ATTR = ("Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D, CC BY-SA 2.1 Japan): the male genital organs his own scans do not give (testes, epididymides, deferent ducts, seminal vesicles, penis, male urethra, "
        "ejaculatory ducts), taken from the Z-Anatomy male fitted to his body (Q195 fit, Q186c skin clamp) and checked against his own skin, bones and pelvic organs (Q233). Z-Anatomy: models by the Z-Anatomy project, "
        "app by Lluis Vinent Juanico -- see third_party/z-anatomy/NOTICE and third_party/z-anatomy/README.md. Licensed CC BY-SA 4.0; this derivative remains CC BY-SA 4.0 (ShareAlike).")
ITEMS = [  # new id, Z id, side, name, latin
    ("testis_l", "zan_testis_l", "left", "Testis (left)", "Testis sinister"), ("testis_r", "zan_testis_r", "right", "Testis (right)", "Testis dexter"),
    ("epididymis_l", "zan_epididymis_l", "left", "Epididymis (left)", "Epididymis sinister"), ("epididymis_r", "zan_epididymis_r", "right", "Epididymis (right)", "Epididymis dexter"),
    ("ductus_deferens_l", "zan_ductus_deferens_l", "left", "Ductus deferens (left)", "Ductus deferens sinister"), ("ductus_deferens_r", "zan_ductus_deferens_r", "right", "Ductus deferens (right)", "Ductus deferens dexter"),
    ("seminal_vesicle_l", "zan_seminal_gland_l", "left", "Seminal vesicle (left)", "Glandula vesiculosa sinistra"), ("seminal_vesicle_r", "zan_seminal_gland_r", "right", "Seminal vesicle (right)", "Glandula vesiculosa dextra"),
    ("corpus_cavernosum_penis", "zan_corpus_cavernosum_of_penis", None, "Corpora cavernosa of the penis", "Corpora cavernosa penis"),
    ("corpus_spongiosum_penis", "zan_corpus_spongiosum_of_penis", None, "Corpus spongiosum of the penis", "Corpus spongiosum penis"),
    ("glans_penis", "zan_glans_penis", None, "Glans penis", "Glans penis"), ("urethra_male", "zan_urethra", None, "Urethra (male, penile and prostatic part)", "Urethra masculina"),
    ("ejaculatory_duct_l", "zan_ejaculatory_duct_l", "left", "Ejaculatory duct (left)", "Ductus ejaculatorius sinister"), ("ejaculatory_duct_r", "zan_ejaculatory_duct_r", "right", "Ejaculatory duct (right)", "Ductus ejaculatorius dexter"),
]


def main(out_dir):
    np.random.seed(0)
    src = REPO / "build/viewer_m_hr_q224"
    B, A0 = Bundle(src), Bundle(src)
    C = {x["id"]: x for x in Q.load("comb_m")}
    skin_it = [it for it in B.items if it["e"]["id"] == "skin"][0]
    skin = trimesh.Trimesh(*B.mesh(skin_it), process=False)
    bone_pts = []
    for it in B.items:
        if it["e"]["cat"] == "bone":
            v, f = B.mesh(it); bone_pts.append(trimesh.Trimesh(v, f, process=False).sample(8000))
    bone_tree = cKDTree(np.vstack(bone_pts))
    lo = np.array([-100, -170, -120.]); pitch = 1.0; shape = (200, 240, 260)
    ev = {}
    for it in B.items:
        if it["e"]["id"] in ("urinary_bladder", "rectum", "sigmoid_colon", "prostate"):
            ev[it["e"]["id"]] = mask_of(*B.mesh(it), lo, shape, pitch)
    report, new = {}, []
    for sid, zid, side, name, latin in ITEMS:
        z = C[zid]; V, F = z["v"].astype(float), z["f"]
        m = trimesh.Trimesh(V, F, process=True)
        trimesh.repair.fix_normals(m)
        V, F = np.asarray(m.vertices), np.asarray(m.faces)
        inside = skin.contains(V)
        dmin, dmed = B._depth(V)
        db = bone_tree.query(V)[0]
        mk = mask_of(V, F, lo, shape, pitch)
        vol = float(abs(m.volume)) / 1000
        ov = {i: round(float((mk & g).sum()) * pitch ** 3 / 1000, 3) for i, g in ev.items() if (mk & g).sum()}
        inherent = ("prostate",) if sid in ("urethra_male", "ejaculatory_duct_l", "ejaculatory_duct_r") else ()      # these ducts run THROUGH the prostate by definition
        ov_gate = {i: x for i, x in ov.items() if i not in inherent}
        g = dict(inside_skin_pct=round(100 * float(inside.mean()), 1), skin_depth_min_mm=dmin, bone_min_mm=round(float(db.min()), 2), vertices_within_1mm_of_bone=int((db < 1).sum()),
                 overlap_cm3=ov, overlap_total_pct=round(100 * sum(ov_gate.values()) / max(vol, 1e-9), 2), overlap_inherent_prostate_cm3=round(sum(x for i, x in ov.items() if i in inherent), 3), volume_cm3=round(vol, 2), watertight=bool(m.is_watertight), vertices=int(len(V)))
        small = vol < 0.2          # a 2 mm duct (0.06 cm3) is below what a 1 mm voxel mask can resolve: absolute limit 0.05 cm3 instead of the 10 % gate
        g["pass"] = bool(g["inside_skin_pct"] >= 99.0 and g["bone_min_mm"] >= 0.5 and (g["overlap_total_pct"] <= 10.0 or (small and sum(ov_gate.values()) <= 0.05)))
        report[sid] = dict(z_id=zid, gates=g)
        print(sid, g, flush=True)
        if not g["pass"]:
            report[sid]["held"] = True; continue
        zb = (z["rec"] or {}).get("procedural_badge", "")
        badge = (f"FILLED from Z-Anatomy (CC BY-SA 4.0 reference model, `{zid}`), NOT measured on him: his own CT / cryosections give only the prostate of the male-only organs, so this male organ is the Z-Anatomy male "
                 f"structure as fitted to his body on the Combined (Z fitted to him) page: {zb} Checked here (Q233): inside his own CT skin ({g['inside_skin_pct']} % of the vertices, {dmin} mm from it), "
                 f"{g['bone_min_mm']} mm from his bones, overlap with his bladder / rectum / sigmoid / prostate {g['overlap_total_pct']} % of its volume; volume {g['volume_cm3']} cm3 (Z-Anatomy shape, "
                 f"scaled by the fit; no norm checked). Position and shape are Z-Anatomy's arrangement in his frame, an estimate.")
        rec = dict(name=name, latin=latin, folder="viscera", region="pelvis", source="Z-Anatomy male (CC BY-SA 4.0), fitted to the Visible Human male; checked against his own skin, bones and organs (Q233)", procedural_badge=badge)
        new.append((sid, "organ", side, rec, V, F))
    for sid, cat, side, rec, V, F in new:
        B.add(sid, cat, side, SUBJECT, rec, V, F)
    B.write(out_dir, new_subject_attribution={SUBJECT: ATTR}, copy_clinical=True)
    N = Bundle(out_dir)
    Ak, Ao = keyed(A0); Nk, No = keyed(N)
    ident, unlisted = 0, []
    for k in Ao:
        if k in Nk and Ak[k]["raw"] == Nk[k]["raw"] and Ak[k]["e"] == Nk[k]["e"]:
            ident += 1
        else:
            unlisted.append(k[0])
    added = [k[0] for k in Nk if k not in Ak]
    diff = dict(source="build/viewer_m_hr_q224", new=str(Path(out_dir)), entries_old=len(A0.items), entries_new=len(N.items), identical=ident, added=added, removed=[], card_only=[], unlisted_changes=unlisted, problems=[],
                triangles_old=A0.j["triangles"], triangles_new=N.j["triangles"])
    (REPO / "data/derived/Q233_vertex_diff_m.json").write_text(json.dumps(diff, indent=1) + "\n")
    (REPO / "data/derived/Q233_report_own_m.json").write_text(json.dumps(dict(subject=SUBJECT, organs=report, attribution=ATTR), indent=1, default=float) + "\n")
    print("ship diff:", {k: (v if not isinstance(v, list) else len(v)) for k, v in diff.items() if k in ("entries_old", "entries_new", "identical", "added", "unlisted_changes")})
    sys.exit(1 if unlisted else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(REPO / "build/viewer_m_hr_q233")); main(ap.parse_args().out)
