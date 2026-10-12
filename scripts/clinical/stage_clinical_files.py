#!/usr/bin/env python3
"""Q188 -- stage the PRIVATE needle-planning add-on next to a built viewer page.

The viewer pages (anatomy layer, CC BY-SA where Z-Anatomy-derived) carry only a generic
hook: <script src="clinical_needle_tool.js"> plus an API object. This script copies the
owner's private files in as SEPARATE files beside the page -- it never edits the page or
the anatomy geometry files:

    clinical_needle_tool.js     <- clinical/needle_tool.js
    clinical_risk.json          <- clinical/data/risk_<viewer>.json   (per viewer)
    clinical_motor_points.json  <- clinical/data/motor_points.json    (if present, or --motor-points)

Q226 (--imaging / --imaging-only): the IMAGING add-on (simulated CT / MRI of the cut plane), also private:

    clinical_imaging_tool.js       <- clinical/imaging_tool.js
    clinical_imaging_tissues.json  <- clinical/data/imaging_tissues.json   (tissue table, mapping rules, sources)

It needs no per-viewer data, so it also works on the pages that have no needle files (Z male fitted, base female).
--imaging-only stages just these two files (no needle tool, risk or motor points) -- any build dir name is accepted.

--remove deletes exactly those names again (an anatomy-only build).

Usage:
    python3 scripts/clinical/stage_clinical_files.py build/viewer_m_hr
    python3 scripts/clinical/stage_clinical_files.py --all
    python3 scripts/clinical/stage_clinical_files.py build/viewer_zan_female --remove
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLINICAL = REPO / "clinical"
# published viewer build dirs (see the hub, viewer/atlas_hub.html) -> viewer key
DIR_VIEWER = {
    "viewer_m_hr": "vhm",
    "viewer_f_hr": "vhf",
    "viewer_zan_atlas": "zan_m",
    "viewer_zan_female": "zan_f",
}
NAMES = ("clinical_needle_tool.js", "clinical_risk.json", "clinical_motor_points.json")
IMAGING_NAMES = ("clinical_imaging_tool.js", "clinical_imaging_tissues.json")
# Q228: the ULTRASOUND companion (loaded by the imaging add-on, never by a template); needs the imaging files beside it
ULTRASOUND_NAMES = ("clinical_ultrasound_tool.js", "clinical_ultrasound_tissues.json")
# all six pages (Q226): build dir name -> viewer key (only the first four have needle data)
ALL_PAGES = {"viewer_m_hr": "vhm", "viewer_f_hr": "vhf", "viewer_zan_atlas": "zan_m", "viewer_zan_female": "zan_f",
             "viewer_zan_vhm": "zan_vhm", "viewer_base_female": "base_f"}


def viewer_for(build_dir: Path) -> str:
    key = DIR_VIEWER.get(Path(build_dir).name)
    if not key:
        raise SystemExit(f"cannot tell the viewer of {build_dir}; pass --viewer (one of {sorted(set(DIR_VIEWER.values()))})")
    return key


def stage_imaging(build_dir: Path, clinical: Path = CLINICAL) -> list[Path]:
    build_dir = Path(build_dir)
    if not build_dir.is_dir():
        raise SystemExit(f"no such build dir: {build_dir}")
    out = []
    for src, name in ((clinical / "imaging_tool.js", IMAGING_NAMES[0]), (clinical / "data" / "imaging_tissues.json", IMAGING_NAMES[1])):
        if not src.is_file():
            raise SystemExit(f"missing source {src}")
        dst = build_dir / name
        shutil.copyfile(src, dst)
        out.append(dst)
    return out


def stage_ultrasound(build_dir: Path, clinical: Path = CLINICAL) -> list[Path]:
    """Q228: clinical_ultrasound_tool.js + clinical_ultrasound_tissues.json (also stages the imaging files it depends on)."""
    build_dir = Path(build_dir)
    if not build_dir.is_dir():
        raise SystemExit(f"no such build dir: {build_dir}")
    out = stage_imaging(build_dir, clinical)
    for src, name in ((clinical / "ultrasound_tool.js", ULTRASOUND_NAMES[0]), (clinical / "data" / "ultrasound_tissues.json", ULTRASOUND_NAMES[1])):
        if not src.is_file():
            raise SystemExit(f"missing source {src}")
        dst = build_dir / name
        shutil.copyfile(src, dst)
        out.append(dst)
    return out


def stage(build_dir: Path, viewer: str | None = None, motor_points: Path | None = None,
          clinical: Path = CLINICAL) -> list[Path]:
    build_dir = Path(build_dir)
    if not build_dir.is_dir():
        raise SystemExit(f"no such build dir: {build_dir}")
    viewer = viewer or viewer_for(build_dir)
    risk = clinical / "data" / f"risk_{viewer}.json"
    mp = Path(motor_points) if motor_points else clinical / "data" / "motor_points.json"
    plan = [(clinical / "needle_tool.js", build_dir / NAMES[0]), (risk, build_dir / NAMES[1])]
    if mp.is_file():
        plan.append((mp, build_dir / NAMES[2]))
    elif (build_dir / NAMES[2]).exists():
        (build_dir / NAMES[2]).unlink()          # stale copy: the add-on then says "no motor-point data loaded"
    out = []
    for src, dst in plan:
        if not src.is_file():
            raise SystemExit(f"missing source {src}")
        shutil.copyfile(src, dst)
        out.append(dst)
    return out


def remove(build_dir: Path) -> list[Path]:
    gone = []
    for n in NAMES + IMAGING_NAMES + ULTRASOUND_NAMES:
        p = Path(build_dir) / n
        if p.exists():
            p.unlink()
            gone.append(p)
    return gone


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("build_dir", nargs="*", help="viewer build dir(s), e.g. build/viewer_m_hr")
    ap.add_argument("--all", action="store_true", help="the four published viewer dirs under build/")
    ap.add_argument("--viewer", choices=sorted(set(DIR_VIEWER.values())))
    ap.add_argument("--motor-points", help="motor-point file to stage instead of clinical/data/motor_points.json")
    ap.add_argument("--imaging", action="store_true", help="Q226: also stage the imaging add-on (clinical_imaging_tool.js + clinical_imaging_tissues.json)")
    ap.add_argument("--imaging-only", action="store_true", help="Q226: stage ONLY the imaging add-on (any build dir, no needle files)")
    ap.add_argument("--ultrasound", action="store_true", help="Q228: stage the imaging add-on AND its ultrasound companion (no needle files); any build dir")
    ap.add_argument("--remove", action="store_true", help="delete the staged add-on files (anatomy-only build), needle and imaging")
    a = ap.parse_args(argv)
    dirs = [REPO / "build" / d for d in DIR_VIEWER] if a.all else [Path(d) for d in a.build_dir]
    if not dirs:
        ap.error("give a build dir or --all")
    for d in dirs:
        if a.remove:
            print(f"{d}: removed {[p.name for p in remove(d)]}")
        elif a.ultrasound:
            print(f"{d}: staged {[p.name for p in stage_ultrasound(d)]}")
        elif a.imaging_only:
            print(f"{d}: staged {[p.name for p in stage_imaging(d)]}")
        else:
            files = stage(d, a.viewer, Path(a.motor_points) if a.motor_points else None)
            if a.imaging:
                files += stage_imaging(d)
            print(f"{d}: staged {[p.name for p in files]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
