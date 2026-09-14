"""Track a peripheral nerve through the female's FULL-RESOLUTION cryosection crops (vhf_stream_crops.py).

    python3 scripts/cryo/vhf_nerve_track.py --crops SCRATCH/vh_cryo_f/thigh --side right --nerve sciatic \
        --bundle build/viewer_f --y-start -60 --y-end -440 --out SCRATCH/vh_cryo_f/sciatic_right.json [--montage PNG]

A nerve in a cryosection is a compact bundle of pale fascicles (whitish-pink dots, 0.5-2 mm) in a pinkish
epineurium, lying in the loose connective tissue BETWEEN muscles -- never inside a belly. Per 1 mm level:
  corridor  = photograph pixels that are not muscle-red and not gel, inside the deep compartment (the
              muscle-red mask closed by 12 mm and filled, i.e. under the deep fascia), within 15 mm of the
              nerve's "roof" muscles and within 15 mm of its "floor" muscles (sections of her meshes at
              this level: the sciatic nerve runs deep to gluteus maximus / the hamstrings and on quadratus
              femoris / adductor magnus);
  detector  = fascicle TEXTURE (nerve_blobs): mid brightness with dense fine edges, away from the muscle/fat
              boundaries that mimic it; blobs of 6-200 mm2 at least half inside the corridor;
  tracking  = Viterbi over the levels from the seed down: the chain of blobs with the smallest total
              centroid jump (mm), a level without a usable blob costs 6 mm and keeps the position, jumps
              > 8 mm (+2 mm per preceding gap) are forbidden; the chain ends at the last level it reaches.
The seed is a LANDMARK RULE (sciatic: midway between the ischial tuberosity and the greater trochanter at
the level 20 mm below the tuberosity, under gluteus maximus), not a hand click. Output: per-level centroid,
area and mask bbox (atlas mm), a 0.5 mm label volume for `ingest_volume_geometry.py convert`, and montages
for the human check that the tracked cord IS the nerve. Rule-based; badged; volumes recorded.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage.morphology import convex_hull_image

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id  # noqa: E402

PX = 1 / 3.0                      # mm per full-resolution pixel
NERVES = {
    "sciatic": {"roof": ["gluteus_maximus", "biceps_femoris", "semitendinosus", "semimembranosus"],
                "floor": ["quadratus_femoris", "adductor_magnus", "gluteus_minimus", "gluteus_medius", "piriformis", "obturator_internus",
                          "gemellus_superior", "gemellus_inferior", "obturator_externus", "popliteus", "gastrocnemius", "vastus_lateralis"],
                "bone": ["femur", "patella", "tibia", "fibula"],
                "corridor_mm": 15.0, "area_mm2": (6.0, 200.0)},
}
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections at full "
          "resolution (0.33 mm) via the NCI Imaging Data Commons. Derived data (scripts/cryo/vhf_nerve_track.py).")


class Crops:
    def __init__(self, prefix, side):
        self.b = json.load(open(f"{prefix}_bbox.json")); self.side = side
        self.a = np.load(f"{prefix}_{side}.npy", mmap_mode="r"); self.ys = self.b["y_atlas"]
        self.ox, self.oy, self.oz = self.b["origin"]; self.H = self.b["H"]; self.sc = self.b["sc"]
        self.j_of = {y: j for j, y in enumerate(self.ys)}

    def level(self, y):
        L = self.b["levels"][str(int(y))]; w = L["windows"][self.side]
        return L, w

    def image(self, y):
        L, w = self.level(y); j = self.j_of[int(y)]
        return np.asarray(self.a[j, :w[1] - w[0], :w[3] - w[2]])

    def atlas_to_px(self, y, x, z):
        """atlas (x, z) at level y -> full-res (row, col) in this level's crop."""
        L, w = self.level(y)
        c = 350.0 - (np.asarray(x) + self.ox); r = 240.0 - (np.asarray(z) + self.oz)
        pr = ((self.H - 1) - (r - L["RS"]) / self.sc) * 3 - w[0]; pc = ((c - 110 - L["CS"]) / self.sc) * 3 - w[2]
        return pr, pc

    def px_to_atlas(self, y, pr, pc):
        L, w = self.level(y)
        r = (self.H - 1 - (np.asarray(pr) + w[0]) / 3) * self.sc + L["RS"]; c = (np.asarray(pc) + w[2]) / 3 * self.sc + 110 + L["CS"]
        return 350.0 - c - self.ox, 240.0 - r - self.oz


def section_masks(meshes, names, side, y, crops, shape):
    """Rasterised sections of the named meshes (side-suffixed) at atlas height y into the crop grid."""
    sfx = "_r" if side == "right" else "_l"; out = {}
    for nm in names:
        m = meshes.get(nm + sfx) or meshes.get(nm)
        if m is None:
            continue
        tm = trimesh.Trimesh(m["v"], m["f"], process=False)
        sec = tm.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
        if sec is None:
            continue
        img = Image.new("L", (shape[1], shape[0]), 0); dr = ImageDraw.Draw(img)
        for ent in sec.entities:
            pts = sec.vertices[ent.points]
            pr, pc = crops.atlas_to_px(y, pts[:, 0], pts[:, 2])
            if len(pr) >= 3:
                dr.polygon(list(zip(pc.tolist(), pr.tolist())), fill=1)
        out[nm] = np.asarray(img, bool)
    return out


def photo_classes(im):
    """Coarse tissue classes of a full-resolution photograph (this cadaver: fat orange-cream R>178, muscle R<90)."""
    R = im[..., 0].astype(np.float32); gel = im[..., 2] > im[..., 0]
    m5 = ndi.uniform_filter(R, 5)
    return {"gel": gel, "muscle": (m5 < 90) & ~gel, "fat": (m5 > 178) & ~gel, "R": R, "m5": m5}


def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]; return (x * x + y * y) <= r * r


def nerve_blobs(im, cl=None):
    """Fascicle texture: mid brightness (3 mm mean R 95-190; the popliteal nerve is nearly as pale as fat, only its texture differs) with dense fine edges (mean |sobel R| > 55 over 3 mm),
    not bimodal (3 mm sd < 35) and at least 1 mm from muscle, bright fat and gel (their boundaries mimic the
    texture), opened by 0.7 mm, cores
    >= 4 mm2, grown back 1 mm into mid-brightness non-muscle tissue. Returns a label image."""
    cl = cl or photo_classes(im); R = cl["R"]
    m = ndi.uniform_filter(R, 9); g = ndi.uniform_filter(np.hypot(ndi.sobel(R, 0), ndi.sobel(R, 1)), 9)
    sd = np.sqrt(np.maximum(ndi.uniform_filter(R * R, 9) - m * m, 0))          # a muscle/fat edge is bimodal (sd > 35); fascicles are not
    near = ndi.binary_dilation(cl["muscle"] | cl["fat"] | cl["gel"], structure=disk(3), iterations=1)
    core = ndi.binary_opening((m > 95) & (m < 190) & (g > 55) & (sd < 35) & ~near, structure=disk(2))
    lab, n = ndi.label(core)
    if n == 0:
        return lab, 0
    area = ndi.sum(core, lab, range(1, n + 1)); keep = np.zeros(n + 1, bool); keep[1:] = area * PX * PX >= 4.0
    grown = ndi.binary_dilation(keep[lab], structure=disk(3), iterations=1) & (m > 90) & (m < 186) & ~cl["muscle"] & ~cl["gel"]
    return ndi.label(grown)


def honeycomb_score(R, mask):
    """Density of fascicle CELLS in a blob: local maxima of the 1 px-smoothed red channel that stand >= 12 above
    the darkest pixel within 1 mm (a cell bounded by walls), at >= 1 mm spacing, per mm2; 0.4 / mm2 = 1.0."""
    sm = ndi.gaussian_filter(R, 1.0)
    peaks = (sm == ndi.maximum_filter(sm, size=7)) & ((sm - ndi.minimum_filter(sm, size=7)) >= 12) & mask
    return float(min(peaks.sum() / max(mask.sum() * PX * PX, 1e-6) / 0.4, 1.0))


def candidates(im, corridor, area_mm2, min_inside=0.5, max_aspect=3.0):
    cl = photo_classes(im); lab, n = nerve_blobs(im, cl); out = []
    for i in range(1, n + 1):
        mm = lab == i; ar = mm.sum() * PX * PX; inside = corridor[mm].mean()
        if area_mm2[0] <= ar <= area_mm2[1] and inside >= min_inside:
            yy, xx = np.nonzero(mm); cy, cx = yy.mean(), xx.mean()
            cov = np.cov(np.stack([yy - cy, xx - cx])); ev = np.sort(np.linalg.eigvalsh(cov))
            aspect = float(np.sqrt(max(ev[1], 1e-6) / max(ev[0], 1e-6)))
            if aspect > max_aspect:                       # a strip hugging a muscle edge is not a nerve section
                continue
            out.append({"lab": i, "area_mm2": float(ar), "rc": (float(cy), float(cx)), "mask": mm, "inside": float(inside), "aspect": round(aspect, 2),
                        "score": round(honeycomb_score(cl["R"], mm), 2)})
    return out, lab


def corridor_mask(im, masks, spec):
    cl = photo_classes(im)
    deep = ndi.binary_fill_holes(ndi.binary_closing(cl["muscle"], structure=disk(12), iterations=3))   # closing ~ 12 mm
    roof = np.zeros(im.shape[:2], bool); floor = np.zeros(im.shape[:2], bool); bone = np.zeros(im.shape[:2], bool)
    for nm, m in masks.items():
        (roof if nm in spec["roof"] else bone if nm in spec.get("bone", ()) else floor)[m] = True
    if (roof | floor).any():                      # the space enclosed by the nerve's muscles (e.g. the popliteal fossa) is deep too
        deep = deep | convex_hull_image(roof | floor)
    d = int(round(spec["corridor_mm"] / PX))
    near_roof = ndi.binary_dilation(roof, structure=disk(6), iterations=d // 6) if roof.any() else np.zeros_like(roof)
    near_floor = ndi.binary_dilation(floor, structure=disk(6), iterations=d // 6) if floor.any() else np.ones_like(floor)   # no floor muscle at this level (popliteal fossa): the roof alone bounds the corridor
    near_bone = ndi.binary_dilation(bone, structure=disk(6), iterations=2) if bone.any() else np.zeros_like(bone)   # 4 mm: periosteum/cortex texture mimics fascicles
    # the space between the roof muscles themselves (the popliteal fossa between biceps femoris and semimembranosus)
    # counts as floor: a nerve there lies on fat, not on a muscle
    fossa = convex_hull_image(roof) if roof.any() else np.zeros_like(roof)
    # never inside a belly: the interior of the muscles' own sections (eroded 3 mm for registration slack) is out --
    # gluteus maximus' fatty striations otherwise pass every photograph test
    inside = ndi.binary_erosion(roof | floor, structure=disk(3), iterations=3)
    return deep & ~cl["gel"] & near_roof & (near_floor | fossa) & ~near_bone & ~inside, deep


def seed_rule(nerve, meshes, side):
    sg = 1 if side == "right" else -1
    if nerve == "sciatic":
        p = meshes["hip_bone_" + side[0]]["v"]; it = p[np.argmin(p[:, 1])]
        f = meshes["femur_" + side[0]]["v"]; prox = f[f[:, 1] > f[:, 1].max() - 70]; gt = prox[np.argmax(sg * prox[:, 0])]
        mid = (it + gt) / 2
        return {"y": float(it[1] - 20), "x": float(mid[0]), "z": float(mid[2]) - 10.0,
                "rule": "midway between the ischial tuberosity and the greater trochanter, 20 mm below the tuberosity, 10 mm posterior"}
    raise SystemExit("no seed rule for " + nerve)


def learned_candidates(scorer, im, cor, cands, lab, lab_store_slot=None):
    """Score the hand-crafted candidates with the learned patch scorer and add blobs of its dense corridor scan
    (probability > 0.5, 6-200 mm2) that no hand-crafted candidate covers. Label ids for the new blobs continue
    after the detector's; the label image is updated in place so the volume builder can find them."""
    from scripts.cryo import vhf_nerve_scorer as sc
    P = sc.P; pads = []
    for c in cands:
        r, cc = int(round(c["rc"][0])), int(round(c["rc"][1]))
        ok = P <= r < im.shape[0] - P and P <= cc < im.shape[1] - P
        pads.append(im[r - P:r + P, cc - P:cc + P] if ok else np.zeros((2 * P, 2 * P, 3), np.uint8))
    probs = sc.score_patches(scorer, pads)
    for c, p in zip(cands, probs):
        c["score"] = round(float(p), 3)
    prob = sc.dense_scan(scorer, im, cor)
    blob = (prob > 0.5) & cor
    if not blob.any():
        return cands, lab
    bl, nb = ndi.label(blob); nxt = int(lab.max()) + 1; lab = lab.copy()
    for i in range(1, nb + 1):
        mm = bl == i; ar = mm.sum() * PX * PX
        if not (6.0 <= ar <= 200.0) or any((lab == c["lab"])[mm].mean() > 0.3 for c in cands):
            continue
        lab[mm & (lab == 0)] = nxt; mm = lab == nxt
        cy, cx = ndi.center_of_mass(mm)
        cands.append({"lab": nxt, "area_mm2": float(mm.sum() * PX * PX), "rc": (float(cy), float(cx)), "inside": float(cor[mm].mean()),
                      "aspect": None, "score": round(float(prob[mm].mean()), 3), "learned": True}); nxt += 1
    return cands, lab


def collect(crops, meshes, side, spec, y_top, y_end, lab_store=None, log=print, scorer=None):
    """Per level: candidate blobs (atlas centroid, area, label id) and the blob label image (stored if lab_store given)."""
    if y_end > y_top:                                     # tracking UPWARD from the seed
        ys = sorted(y for y in crops.ys if y_top <= y <= y_end)
    else:
        ys = [y for y in crops.ys if y_top >= y >= y_end]
    per = {}
    for i, y in enumerate(ys):
        im = crops.image(y); masks = section_masks(meshes, spec["roof"] + spec["floor"] + spec.get("bone", []), side, y, crops, im.shape[:2])
        cor, _ = corridor_mask(im, masks, spec)
        cands, lab = candidates(im, cor, spec["area_mm2"])
        if scorer is not None:
            cands, lab = learned_candidates(scorer, im, cor, cands, lab)
        if lab_store is not None:
            lab_store[i, :lab.shape[0], :lab.shape[1]] = np.clip(lab, 0, 255)
        for c in cands:
            ax, az = crops.px_to_atlas(y, c["rc"][0], c["rc"][1]); c["x"], c["z"] = float(ax), float(az); c.pop("mask", None)
        per[y] = cands
        if i % 50 == 0:
            log(f"  level {y}: {len(cands)} candidates")
    return ys, per


def viterbi(ys, per, seed, jump_mm=8.0, gap_cost=6.0, seed_radius=25.0, lam=8.0):
    """Best chain of candidates from the seed level down: cost = sum of centroid jumps (mm) + lam x (1 - honeycomb
    score) per blob, a level without a candidate costs gap_cost and keeps the position; a jump > jump_mm (+2 mm per
    preceding gap) is forbidden."""
    INF = 1e18; states = []          # per level: list of (x, z, cand_index or None)
    for y in ys:
        st = [(c["x"], c["z"], k) for k, c in enumerate(per[y])]
        states.append(st)
    texture = [[lam * (1.0 - c.get("score", 1.0)) for c in per[y]] for y in ys]      # a blob without fascicle cells costs lam mm
    cost = []; back = []
    # level 0: candidates near the seed, or a gap at the seed
    c0 = [np.hypot(x - seed["x"], z - seed["z"]) + texture[0][k] for k, (x, z, _) in enumerate(states[0])]
    c0 = [c if c <= seed_radius else INF for c in c0] + [gap_cost]; states[0] = states[0] + [(seed["x"], seed["z"], None)]
    cost.append(c0); back.append([None] * len(c0)); gaps_at = [[0] * len(c0)]
    for i in range(1, len(ys)):
        prev = states[i - 1]; cur = states[i]
        # gap state carries every previous position forward: keep only the best previous position as the gap node
        pcost = cost[i - 1]; jbest = int(np.argmin(pcost)); gap_node = (prev[jbest][0], prev[jbest][1], None)
        cur = cur + [gap_node]; states[i] = cur
        ci = []; bi = []; gi = []
        for k, (x, z, idx) in enumerate(cur):
            best, bj, bg = INF, None, 0
            for j, (px_, pz_, _) in enumerate(prev):
                if pcost[j] >= INF:
                    continue
                if idx is None:
                    if j != jbest:
                        continue
                    c = pcost[j] + gap_cost; g = gaps_at[i - 1][j] + 1
                else:
                    d = np.hypot(x - px_, z - pz_); lim = jump_mm + 2.0 * gaps_at[i - 1][j]
                    if d > lim:
                        continue
                    c = pcost[j] + d + texture[i][k]; g = 0
                if c < best:
                    best, bj, bg = c, j, g
            ci.append(best); bi.append(bj); gi.append(bg)
        cost.append(ci); back.append(bi); gaps_at.append(gi)
    # end: the last level whose best state is a real candidate, with finite cost
    end = None
    for i in range(len(ys) - 1, -1, -1):
        real = [c for c, (x, z, idx) in zip(cost[i], states[i]) if idx is not None]
        if real and min(real) < INF:
            end = i; break
    if end is None:
        return []
    k = int(np.argmin([c if states[end][j][2] is not None else INF for j, c in enumerate(cost[end])]))
    chain = []
    for i in range(end, -1, -1):
        x, z, idx = states[i][k]; chain.append((ys[i], x, z, idx)); k = back[i][k]
        if k is None:
            break
    return chain[::-1]


def track(crops, meshes, side, spec, seed, y_end, lab_store=None, log=print, scorer=None):
    ys, per = collect(crops, meshes, side, spec, seed["y"], y_end, lab_store, log, scorer=scorer)
    chain = viterbi(ys, per, seed, lam=15.0 if scorer is not None else 8.0)
    rows = []
    for y, x, z, idx in chain:
        c = per[y][idx] if idx is not None else None
        rows.append({"y": y, "gap": c is None, "x": round(x, 1), "z": round(z, 1), "n_cands": len(per[y]),
                     **({"area_mm2": round(c["area_mm2"], 1), "inside": round(c["inside"], 2), "lab": int(c["lab"]), "score": c.get("score"),
                         "learned": bool(c.get("learned", False)), "level_index": ys.index(y)} if c else {})})
    lost = chain[-1][0] if chain else None
    return rows, lost


def montage(crops, rows, path, every=20, half_mm=25):
    tiles = []; h = int(half_mm / PX)
    for r in rows[::every]:
        im = crops.image(r["y"]); pr, pc = crops.atlas_to_px(r["y"], r["x"], r["z"]); pr, pc = int(pr), int(pc)
        t = np.zeros((2 * h, 2 * h, 3), np.uint8)
        r0, r1, c0, c1 = max(0, pr - h), min(im.shape[0], pr + h), max(0, pc - h), min(im.shape[1], pc + h)
        t[r0 - (pr - h):r1 - (pr - h), c0 - (pc - h):c1 - (pc - h)] = im[r0:r1, c0:c1]
        col = (255, 0, 0) if r["gap"] else (0, 255, 0)
        t[h - 1:h + 1, :] = col; t[:, h - 1:h + 1] = col
        pil = Image.fromarray(t); ImageDraw.Draw(pil).text((3, 3), f"y{int(r['y'])}", fill=(255, 255, 0)); tiles.append(np.asarray(pil))
    n = len(tiles); cols = min(8, n); rws = (n + cols - 1) // cols
    canvas = np.zeros((rws * 2 * h, cols * 2 * h, 3), np.uint8)
    for i, t in enumerate(tiles):
        canvas[(i // cols) * 2 * h:(i // cols + 1) * 2 * h, (i % cols) * 2 * h:(i % cols + 1) * 2 * h] = t
    Image.fromarray(canvas).save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crops", required=True); ap.add_argument("--side", required=True, choices=["right", "left"])
    ap.add_argument("--nerve", default="sciatic"); ap.add_argument("--bundle", default="build/viewer_f")
    ap.add_argument("--y-end", type=float, default=-440, help="last level; above the seed = track upward")
    ap.add_argument("--seed", default=None, help="x,y,z atlas mm (overrides the rule)")
    ap.add_argument("--out", required=True); ap.add_argument("--montage", default=None); ap.add_argument("--every", type=int, default=20)
    ap.add_argument("--scorer", default=None, help="learned patch scorer (vhf_nerve_scorer.py train) -> candidates scored, corridor scanned")
    a = ap.parse_args()
    crops = Crops(a.crops, a.side); bf, blob = read_bundle_dir(a.bundle); meshes = meshes_by_id(bf, blob)
    lab_store = np.lib.format.open_memmap(a.out.replace(".json", "_labels.npy"), mode="w+", dtype=np.uint8,
                                          shape=(len(crops.ys), crops.a.shape[1], crops.a.shape[2]))
    spec = NERVES[a.nerve]
    seed = seed_rule(a.nerve, meshes, a.side) if a.seed is None else dict(zip("xyz", map(float, a.seed.split(","))), rule="given")
    seed["y"] = float(int(round(seed["y"])))
    print("seed", {k: (round(v, 1) if isinstance(v, float) else v) for k, v in seed.items()})
    scorer = None
    if a.scorer:
        from scripts.cryo import vhf_nerve_scorer as sc
        scorer = sc.load(a.scorer)
    rows, lost = track(crops, meshes, a.side, spec, seed, a.y_end, lab_store, scorer=scorer); lab_store.flush()
    found = [r for r in rows if not r["gap"]]
    span = (found[0]["y"] - found[-1]["y"]) if found else 0
    print(f"{len(found)} levels with a blob of {len(rows)} ({span:.0f} mm span), lost at {lost}")
    json.dump({"source": SOURCE, "nerve": a.nerve, "side": a.side, "seed": seed, "lost_at": lost, "span_mm": span, "rows": rows}, open(a.out, "w"), indent=1)
    if a.montage and rows:
        montage(crops, rows, a.montage, every=a.every); print("montage", a.montage)


if __name__ == "__main__":
    main()
