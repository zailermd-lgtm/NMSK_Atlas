#!/usr/bin/env python3
"""Q246 -- small before / after side-by-side PNGs (data/derived/q246/) from the harness dumps.

    python3 scripts/clinical/q246_screens.py RUNS_DIR(pgm_full parent) OUT_DIR --before-tool imaging_tool_before.js --geo-own DIR --geo-zan DIR

RUNS/pgm_full/{before,after}_{own_f,zan_f}/<site>_<dir>_<kind>.pgm are written by q246_run.js --pgm, RUNS/pgm_full/us_{before,after}_<page>/*.pgm by q246_us.js --pgm.  The noise strips are
rendered here with q246_dump.js (old tool = --before-tool, new tool = clinical/imaging_tool.js)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]


def pgm(p: Path) -> Image.Image:
    return Image.open(p).convert("L")


def strip(ims, labels, scale, crop=None, gap=6, title=None):
    ims = [i.crop(crop) if crop else i for i in ims]
    ims = [i.resize((i.width * scale, i.height * scale), Image.NEAREST) for i in ims]
    h = max(i.height for i in ims); w = sum(i.width for i in ims) + gap * (len(ims) - 1)
    top = 16
    out = Image.new("L", (w, h + top), 24)
    d = ImageDraw.Draw(out); x = 0
    for im, lb in zip(ims, labels):
        out.paste(im, (x, top)); d.text((x + 3, 2), lb, fill=235); x += im.width + gap
    return out


def save(im: Image.Image, path: Path, max_w=900, colors=40):
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    im.convert("P", palette=Image.ADAPTIVE, colors=colors).save(path, optimize=True)
    print(path.name, im.size, path.stat().st_size // 1024, "KB")


def dump(tool, geo, out, *args):
    subprocess.run(["node", str(REPO / "scripts/clinical/q246_dump.js"), "--tool", str(tool), "--geo", str(geo), "--out", str(out), *args], check=True, capture_output=True)


def main():
    a = sys.argv[1:]
    runs, out = Path(a[0]), Path(a[1]); out.mkdir(parents=True, exist_ok=True)
    opt = lambda k: a[a.index(k) + 1]                                         # noqa: E731
    before_tool, geo_own, geo_zan = Path(opt("--before-tool")), Path(opt("--geo-own")), Path(opt("--geo-zan"))
    P = runs / "pgm_full"
    # 1 CT axial thigh (own), 4x crop around the femur
    save(strip([pgm(P / "before_own_f/thigh_ax_ct.pgm"), pgm(P / "after_own_f/thigh_ax_ct.pgm")], ["before: one label per pixel", "after: 3x3 coverage + hole fill"], 3, (60, 60, 220, 220)), out / "ct_thigh_axial_own_before_after.png")
    # 2 MRI T1 coronal knee (own)
    save(strip([pgm(P / "before_own_f/knee_co_t1_se.pgm"), pgm(P / "after_own_f/knee_co_t1_se.pgm")], ["before", "after"], 2, (60, 40, 260, 280)), out / "mri_t1_knee_coronal_own_before_after.png")
    # 3 Z pelvis axial CT (open meshes) + Z thigh MRI T2 sagittal
    save(strip([pgm(P / "before_zan_f/pelvis_ax_ct.pgm"), pgm(P / "after_zan_f/pelvis_ax_ct.pgm")], ["before", "after (Combined F)"], 2, (0, 40, 320, 280)), out / "ct_pelvis_zan_before_after.png")
    # 4 CT noise 25 HU on three planes 0, 0.5, 1 mm apart + a pan of 10 px: before / after
    tmp = out / "_tmp"; tmp.mkdir(exist_ok=True)
    rows = []
    for label, tool in (("before", before_tool), ("after", REPO / "clinical/imaging_tool.js")):
        ims = []
        for k, pos in enumerate((0, 0.5, 1.0)):
            f = tmp / f"n_{label}_{k}.pgm"
            dump(tool, geo_own, f, "--site", "thigh", "--dir", "ax", "--pos", str(pos), "--kind", "ct", "--noise", "25", "--ss", "3" if label == "after" else "1")
            ims.append(pgm(f))
        rows.append(strip(ims, [f"{label}: plane +{p} mm" for p in (0, 0.5, 1.0)], 2, (80, 100, 240, 220)))
    w = max(r.width for r in rows); h = sum(r.height for r in rows)
    im = Image.new("L", (w, h + 4), 24); y = 0
    for r in rows:
        im.paste(r, (0, y)); y += r.height + 4
    save(im, out / "ct_noise_adjacent_planes_before_after.png", max_w=720, colors=24)
    # 5 US speckle: homogeneous block, 1 degree of fan tilt: before / after
    ims = [pgm(P / f"us_{v}_own_f/us_thigh_spk_t{t}.pgm") for v in ("before", "after") for t in (0, 1)]
    save(strip(ims, ["before 0 deg", "before 1 deg", "after 0 deg", "after 1 deg"], 1, None), out / "us_speckle_1deg_tilt_before_after.png")
    # 6 US Combined Female abdomen: signal before / after
    ims = [pgm(P / f"us_{v}_zan_f/us_abdomen_star90_t{t}.pgm") for v in ("before", "after") for t in (0, 1)]
    save(strip(ims, ["before t0", "before t1", "after t0", "after t1"], 1, None), out / "us_zan_abdomen_before_after.png")
    for f in tmp.glob("*"):
        f.unlink()
    tmp.rmdir()


if __name__ == "__main__":
    main()
