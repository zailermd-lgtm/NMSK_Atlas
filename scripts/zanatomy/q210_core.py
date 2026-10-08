"""Q210 core: the male Z-fitted page (Q208 = before, Q210 = after), the genital structure sets, and the measures shared by the two fixes
(1) male genital structures vs the refit urogenital skin, (2) forearm vs trunk / thigh skin contact."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C7  # noqa: E402
from scripts.zanatomy import q207_eval as E7  # noqa: E402

PAGE = dict(src=REPO / "build/q208/viewer_zan_vhm", stem="atlas_viewer_zan_male_fitted", out=REPO / "build/q210/viewer_zan_vhm",
            raw_src=REPO / "build/q197/viewer_zan_atlas", raw_stem="atlas_viewer_zan_atlas")
BUILD = REPO / "build" / "q210"
UROS = ("zan_skin_urogenital_region_l", "zan_skin_urogenital_region_r")

# the 12 structures of the Q209 regression list
GEN_MAIN = ("zan_corpus_cavernosum_of_penis", "zan_corpus_spongiosum_of_penis", "zan_deep_artery_of_penis_l", "zan_deep_artery_of_penis_r", "zan_deep_dorsal_vein_of_penis",
            "zan_dorsal_artery_of_penis_l", "zan_dorsal_artery_of_penis_r", "zan_glans_penis", "zan_superficial_dorsal_veins_of_penis", "zan_testis_l", "zan_testis_r", "zan_urethra")
# further structures of the same region that were slightly outside (4-11 mm) in the Q208 page
GEN_EXTRA = ("zan_external_pudendal_veins_l", "zan_external_pudendal_veins_r", "zan_superficial_external_pudendal_artery_l", "zan_superficial_external_pudendal_artery_r")
# spermatic cord and scrotal contents: measured (continuity / still inside), not moved
GEN_CORD = ("zan_ductus_deferens_l", "zan_ductus_deferens_r", "zan_epididymis_l", "zan_epididymis_r", "zan_left_testicular_vein", "zan_right_testicular_vein", "genitofemoral_n_l", "genitofemoral_n_r",
            "gonadal_a_l", "gonadal_a_r", "zan_prostate", "zan_ejaculatory_duct_l", "zan_ejaculatory_duct_r", "zan_seminal_gland_l", "zan_seminal_gland_r")
GEN_ALL = GEN_MAIN + GEN_EXTRA + GEN_CORD


def load(src=None):
    pg = C7.Page("male", src=src or PAGE["src"], stem=PAGE["stem"])
    raw = C7.Page("male", src=PAGE["raw_src"], stem=PAGE["raw_stem"])
    return pg, raw


def state_path(stage):
    BUILD.mkdir(parents=True, exist_ok=True)
    return BUILD / f"male_{stage}.pkl"


def coarse(pg, V):
    """Q198 skin field (3 mm, closing 2) of the skin state V"""
    return E7.coarse_field("male", pg, V)


def outside_rows(pg, sf, ids=GEN_ALL, fine=None):
    """per structure: vertices > 3 mm / > 0 mm outside the Q198 envelope (audit measure), max; fine (1 mm envelope) > 0.5 mm"""
    rows = {}
    for i in ids:
        if i not in pg.S:
            continue
        v = pg.v(i)
        s = sf.signed(v)
        r = {"n": len(v), "audit_gt3_pct": round(float((s > 3).mean() * 100), 2), "audit_gt0_pct": round(float((s > 0).mean() * 100), 2), "audit_max_mm": round(float(max(s.max(), 0)), 1)}
        if fine is not None:
            f = fine.value(v)
            r["fine_gt0.5_pct"] = round(float((f > 0.5).mean() * 100), 2)
            r["fine_gt3_pct"] = round(float((f > 3).mean() * 100), 2)
            r["fine_max_mm"] = round(float(max(f.max(), 0)), 1)
        rows[i] = r
    return rows


def fine_box(pg, V, sf, ids=GEN_ALL, pad=22.0):
    pts = np.vstack([pg.v(i) for i in ids if i in pg.S])
    return C7.Fine(pg, V, E7.CoarseAdapter(sf), pts.min(0) - pad, pts.max(0) + pad, h=1.0)
