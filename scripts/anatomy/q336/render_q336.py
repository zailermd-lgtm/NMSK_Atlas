#!/usr/bin/env python3
"""Q336: screenshots of the pubic / inguinal / perineal / genital region of a Base page (test copy + read-only hook).

    python3 scripts/anatomy/q336/render_q336.py --page-dir DIR --out OUTDIR [--tag before] [--modes default,skin,noskin,muscle,...]

Per mode one 2x3 montage (front, inferior/perineal, left lateral, right lateral, anterior oblique, posterior-inferior),
deviceScaleFactor 1, viewport 900x760, camera aimed at the pubic symphysis of the page (manifest bbox). Prints page errors.
Modes: default (page defaults), skin (skin only, opaque), noskin (all layers, skin off), and any layer key solo
(muscle, viscera, nerve, vessel, fascia, fat, bone)."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pagehook_q336 as P  # noqa: E402
import pagegeo_q336 as G   # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

VIEWS = [("front", 0.0, 0.0), ("inferior", 0.0, -math.pi / 2 + 0.06), ("left", -math.pi / 2, -0.05),
         ("right", math.pi / 2, -0.05), ("oblique", 0.55, -0.45), ("post-inf", math.pi, -0.75)]


def set_mode(pg, mode):
    pg.evaluate("() => __q336.defaults()")
    if mode == "default":
        pass
    elif mode == "skin":
        pg.evaluate("() => __q336.layer('skin', 1, 'skin')")
    elif mode == "noskin":
        pg.evaluate("() => __q336.layer('skin', 0, null)")
    else:
        pg.evaluate("(k) => __q336.layer(k, 1, k)", mode)
    pg.wait_for_timeout(200)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="shot")
    ap.add_argument("--modes", default="default,skin,noskin,muscle,viscera,nerve,vessel")
    ap.add_argument("--dist", type=float, default=620.0)
    ap.add_argument("--only", default="", help="comma list of ids to show alone (overrides hidden set)")
    a = ap.parse_args(argv)
    src = Path(a.page_dir); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    man = G.manifest(src)
    tgt = G.region_target(man)
    d = P.test_copy(src, Path("/dev/shm/q336t") / (src.name + "_" + a.tag))
    errs = []
    with sync_playwright() as pl:
        srv, b, pg = P.open_page(pl, d, 900, 760, errs=errs)
        for mode in a.modes.split(","):
            set_mode(pg, mode)
            if a.only:
                pg.evaluate("(ids) => __q336.only(ids)", a.only.split(","))
            tiles = []
            for name, az, el in VIEWS:
                pg.evaluate("(c) => __q336.cam(c)", {"az": az, "el": el, "dist": a.dist, "tgt": tgt})
                pg.wait_for_timeout(350)
                f = out / f"_{a.tag}_{mode}_{name}.png"
                pg.screenshot(path=str(f), clip={"x": 150, "y": 110, "width": 600, "height": 600})
                im = Image.open(f).convert("RGB"); ImageDraw.Draw(im).text((8, 8), f"{a.tag} {mode} {name}", fill=(0, 0, 0))
                tiles.append(im); f.unlink()
            W = Image.new("RGB", (1800, 1200), "white")
            for i, im in enumerate(tiles):
                W.paste(im, ((i % 3) * 600, (i // 3) * 600))
            W.save(out / f"{a.tag}_{mode}.png")
        b.close(); srv.terminate()
    print(json.dumps({"page": str(src), "tgt": tgt, "page_errors": errs}))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
