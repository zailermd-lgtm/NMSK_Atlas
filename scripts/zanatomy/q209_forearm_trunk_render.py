#!/usr/bin/env python3
"""Q209 render (git-ignored build/q209_renders/male_forearm_trunk_skin.png): the male Z-fitted page's skin where the forearms rest on the body: forearm / elbow slabs orange, trunk / thigh patches blue-grey, other limb skin
grey, faces in a deep (> 2 mm) forearm | trunk crossing magenta; both sides, front / oblique / top."""
import sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q209_paths  # noqa: F401,E402
from scripts.zanatomy.q198_load import load  # noqa: E402
from scripts.zanatomy import q190_render as R  # noqa: E402
from scripts.zanatomy import q207_geom as G  # noqa: E402
from scripts.zanatomy.q209_forearm_trunk import TUBE, ELBOW, NB  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

S = load("z_male_fit")
skin = {s["id"]: s for s in S if s["sys"] == "skin"}
base = lambda i: i[len("zan_skin_"):-2]
fore = {i for i in skin if base(i) in TUBE + ELBOW}
out = REPO / "build/q209_renders"; out.mkdir(exist_ok=True)
fv = np.concatenate([skin[i]["v"] for i in fore]); lo, hi = fv.min(0) - 20, fv.max(0) + 20
ids = sorted(i for i, s in skin.items() if "nail_plate" not in i and "perionyx" not in i and (s["v"].max(0) >= lo).all() and (s["v"].min(0) <= hi).all())
Vc, F, ow, nm = G.concat({i: (skin[i]["v"], skin[i]["f"]) for i in ids})
pr = G.intersecting_pairs(Vc, F, ow); dd = G.pair_depth(Vc, F, pr)
bad = set()
for (x, y), d in zip(pr, dd):
    a, b = nm[ow[x]], nm[ow[y]]
    if d > 2 and ((a in fore) != (b in fore)) and base(b if a in fore else a) not in NB:
        bad.add(int(x)); bad.add(int(y))
bad = np.array(sorted(bad))
offs = np.r_[0, np.cumsum([len(skin[i]["f"]) for i in ids])]
sc = []
for k, i in enumerate(ids):
    f = skin[i]["f"]; isbad = np.isin(np.arange(offs[k], offs[k + 1]), bad)
    col = (0.95, 0.55, 0.15) if i in fore else (0.62, 0.70, 0.84) if base(i) not in NB else (0.75, 0.75, 0.75)
    if (~isbad).any(): sc.append({"v": skin[i]["v"], "f": f[~isbad], "color": col})
    if isbad.any(): sc.append({"v": skin[i]["v"], "f": f[isbad], "color": (0.95, 0.05, 0.75)})
c = Vc[F[bad]].reshape(-1, 3).mean(0)
half = 230.0
for nm_, az, el in (("front", 0, 0), ("oblique", 35, 25), ("top", 0, 80), ("side_r", 90, 0)):
    R.render(sc, [dict(name=nm_, az=az, el=el, target=c, half=half)], out / "male_forearm_trunk", size=(560, 560))
ims = [Image.open(out / "male_forearm_trunk" / f"{n}.png").convert("RGB") for n in ("front", "oblique", "top", "side_r")]
W = Image.new("RGB", (560 * 4, 560 + 40), (255, 255, 255))
for k, im in enumerate(ims): W.paste(im, (560 * k, 40))
ImageDraw.Draw(W).text((8, 6), "Z fitted to his reconstruction (build/q208/viewer_zan_vhm): skin only. orange = forearm / elbow slabs, blue-grey = trunk / thigh patches, magenta = faces in a deep (> 2 mm) forearm | trunk crossing. front / oblique / top / right side", fill=(0, 0, 0))
W.save(out / "male_forearm_trunk_skin.png"); print("ok", len(bad))
