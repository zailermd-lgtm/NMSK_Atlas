#!/usr/bin/env python3
"""Q210 build of the male Z-fitted page (in-process patch of the published Q208 page, no Z build):
   stage genital : urogenital skin refit to the structures' scale + rim weld                (q210_genital)
   stage contact : forearm | trunk / thigh skin contact relaxation (on the genital state)    (q210_contact)
   stage struct  : left palmaris longus distal end pulled inside his own skin                (q210_struct)
   stage report  : before -> after numbers                                                   (q210_report)
   stage pack    : changed skin patches + the muscle re-packed with before -> after badges   (q210_pack)
    python3 scripts/zanatomy/q210_build.py genital|contact|struct|report|pack|all"""
from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q210_core as K  # noqa: E402


def stage_genital(log=print):
    from scripts.zanatomy import q210_genital as GN
    pg, raw = K.load()
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    best, trials = GN.search(pg, raw, V0, log=log)
    T, V, rep = best
    pickle.dump((V, dict(T=T, rep=rep, trials=trials)), open(K.state_path("genital"), "wb"))
    log(f"genital: target {T} mm3, volumes {rep['volumes']}")


def stage_contact(log=print):
    from scripts.zanatomy import q210_contact as CT
    pg, raw = K.load()
    Vg = pickle.load(open(K.state_path("genital"), "rb"))[0]
    Fs, Ts, cand = CT.find_sets(pg, Vg)
    log("forearm slabs with a crossing:", [i[9:] for i in Fs], "| trunk / thigh patches:", [i[9:] for i in Ts])
    tis = CT.tissue_points(pg)
    t = time.time()
    Vf, rep = CT.relax(pg, raw, Vg, CT.forearm_ids(pg), Ts, tis, delta=CT.DELTA, max_it=CT.MAX_IT, absorb_it=CT.ABSORB_IT, count_every=4, log=log)
    V = dict(Vg)
    V.update(Vf)
    for k in ("V_partition", "taper", "geodesic", "off", "anchors"):
        rep.pop(k, None)
    pickle.dump((V, rep), open(K.state_path("contact"), "wb"))
    log(f"contact: done [{time.time() - t:.0f}s]")


def stage_struct(log=print):
    from scripts.zanatomy import q210_struct as ST
    from scripts.zanatomy.q207_inflate import OwnSkin
    pg, raw = K.load()
    own = OwnSkin("male")
    w, info = ST.pull_inside(pg.v(ST.ID), pg.f(ST.ID), own)
    pickle.dump(({ST.ID: w}, info), open(K.state_path("struct"), "wb"))
    log(f"struct {ST.ID}: {info}")


def stage_report(log=print):
    from scripts.zanatomy import q210_report as RP
    RP.run(log=log)


def stage_pack(log=print):
    from scripts.zanatomy import q210_pack as PK
    PK.run(log=log)


if __name__ == "__main__":
    stage = sys.argv[1]
    for s in (["genital", "contact", "struct", "report", "pack"] if stage == "all" else [stage]):
        globals()["stage_" + s]()
