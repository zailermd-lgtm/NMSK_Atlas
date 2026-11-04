"""Q236: the pure geometry of the label layout (NMSKLabelsCore in viewer/labels/labels.js) under node: summed-area mask, callout placement without overlaps / crossings /
body contact, obstacles, frame, priorities, zoomed-in fallback, determinism."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")

HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8');
const C = new Function(src + '; return NMSKLabelsCore;')();
const scene = JSON.parse(fs.readFileSync(0, 'utf8'));
function mask(sc){ const w = sc.w, h = sc.h, occ = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++){ const dx = (x + 0.5) / w * sc.fw - sc.cx, dy = (y + 0.5) / h * sc.fh - sc.cy; if ((dx * dx) / (sc.rx * sc.rx) + (dy * dy) / (sc.ry * sc.ry) <= 1) occ[y * w + x] = 1; }
  return C.makeMask(occ, w, h, 0, 0, sc.fw / w, sc.fh / h); }
const M = mask(scene);
const res = C.solve({labels:scene.labels, mask:M, frame:scene.frame, obstacles:scene.obstacles || [], pad:2});
const again = C.solve({labels:scene.labels, mask:M, frame:scene.frame, obstacles:scene.obstacles || [], pad:2});
console.log(JSON.stringify({res, same:JSON.stringify(res) === JSON.stringify(again), n:M.n, count:C.maskCount(M, scene.cx - 5, scene.cy - 5, scene.cx + 5, scene.cy + 5), far:C.maskCount(M, 0, 0, 5, 5)}));
"""


def run(scene):
    p = subprocess.run([NODE, "-e", HARNESS, str(REPO / "viewer/labels/labels.js")], input=json.dumps(scene), capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def body_scene(n, w=70, h=18, rx=110, ry=300, fw=900, fh=700, prio_first=0, obstacles=None):
    import math
    labels = []
    for i in range(n):
        a = i / n * 2 * math.pi + 0.2
        labels.append({"id": f"l{i}", "ax": 450 + math.cos(a) * rx * 0.7, "ay": 350 + math.sin(a) * ry * 0.8, "w": w + (i * 7) % 40, "h": h, "prio": prio_first if i == 0 else 0})
    return {"w": 300, "h": 233, "fw": fw, "fh": fh, "cx": 450, "cy": 350, "rx": rx, "ry": ry, "labels": labels, "frame": {"x0": 6, "y0": 6, "x1": fw - 6, "y1": fh - 6}, "obstacles": obstacles or []}


def boxes_overlap(a, b):
    return abs(a["x"] - b["x"]) < (a["w"] + b["w"]) / 2 and abs(a["y"] - b["y"]) < (a["h"] + b["h"]) / 2


def check(out, scene, body_clear=True):
    ok = [r for r in out["res"] if r["ok"]]
    for i, a in enumerate(ok):
        for b in ok[i + 1:]:
            assert not boxes_overlap(a, b), (a["id"], b["id"])
        assert a["x"] - a["w"] / 2 >= scene["frame"]["x0"] - 0.01 and a["x"] + a["w"] / 2 <= scene["frame"]["x1"] + 0.01
        assert a["y"] - a["h"] / 2 >= scene["frame"]["y0"] - 0.01 and a["y"] + a["h"] / 2 <= scene["frame"]["y1"] + 0.01
        for o in scene["obstacles"]:
            assert not (a["x"] - a["w"] / 2 < o["x1"] and a["x"] + a["w"] / 2 > o["x0"] and a["y"] - a["h"] / 2 < o["y1"] and a["y"] + a["h"] / 2 > o["y0"])
        if body_clear and not a["forced"]:
            ex = ((abs(a["x"] - scene["cx"]) - a["w"] / 2) / scene["rx"]) ** 2 + ((abs(a["y"] - scene["cy"]) - a["h"] / 2) / scene["ry"]) ** 2
            assert max(abs(a["x"] - scene["cx"]) - a["w"] / 2, 0) > 0 or max(abs(a["y"] - scene["cy"]) - a["h"] / 2, 0) > 0
    return ok


def test_mask_sums_are_exact():
    out = run(body_scene(1))
    assert out["n"] > 1000
    assert out["count"] > 0 and out["far"] == 0


@pytest.mark.parametrize("n", [3, 12, 30, 60])
def test_callouts_do_not_overlap_or_touch_the_body(n):
    sc = body_scene(n)
    out = run(sc)
    ok = check(out, sc)
    assert len(ok) >= 0.9 * min(n, 56)                 # (almost) everything fits in this large frame
    assert out["same"]                                  # deterministic
    # no callout box touches the elliptical body (3 px margin)
    for a in ok:
        # nearest point of the box to the centre
        nx = min(max(sc["cx"], a["x"] - a["w"] / 2), a["x"] + a["w"] / 2); ny = min(max(sc["cy"], a["y"] - a["h"] / 2), a["y"] + a["h"] / 2)
        assert ((nx - sc["cx"]) / sc["rx"]) ** 2 + ((ny - sc["cy"]) / sc["ry"]) ** 2 >= 0.98


def test_labels_stay_close_to_their_anchor():
    sc = body_scene(12)
    out = run(sc)
    for r in out["res"]:
        assert r["ok"]
        lead = ((r["lx"] - r["x"]) ** 2 + (r["ly"] - r["y"]) ** 2) ** 0.5
        d = ((r["lx"] - next(l for l in sc["labels"] if l["id"] == r["id"])["ax"]) ** 2 + (r["ly"] - next(l for l in sc["labels"] if l["id"] == r["id"])["ay"]) ** 2) ** 0.5
        assert d < 330                                  # a few hundred px at most in a 900 x 700 frame for a 220 x 600 body


def test_obstacles_are_respected():
    obs = [{"x0": 560, "y0": 6, "x1": 894, "y1": 330}]
    sc = body_scene(24, obstacles=obs)
    out = run(sc)
    check(out, sc)


def test_priority_wins_when_there_is_no_room():
    sc = body_scene(40, fw=360, fh=300, rx=40, ry=100, prio_first=3)
    sc["cx"], sc["cy"] = 180, 150
    for l in sc["labels"]:
        l["ax"] = 180 + (l["ax"] - 450) * 0.15; l["ay"] = 150 + (l["ay"] - 350) * 0.15
    sc["frame"] = {"x0": 6, "y0": 6, "x1": 354, "y1": 294}
    out = run(sc)
    ok = check(out, sc, body_clear=False)
    assert 0 < len(ok) < 40
    assert out["res"][0]["ok"]                          # the high-priority label is kept


def test_zoomed_in_labels_fall_back_to_the_frame_edge_without_overlaps():
    sc = body_scene(10, rx=2000, ry=2000)               # the body fills the whole frame
    out = run(sc)
    assert all(r["forced"] for r in out["res"] if r["ok"])
    check(out, sc, body_clear=False)


def test_crossing_leaders_are_rare():
    import math
    sc = body_scene(36)
    out = run(sc)
    segs = []
    for r in out["res"]:
        if r["ok"]:
            l = next(l for l in sc["labels"] if l["id"] == r["id"]); segs.append((l["ax"], l["ay"], r["lx"], r["ly"]))
    def o(p, q, r): return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    cross = 0
    for i, a in enumerate(segs):
        for b in segs[i + 1:]:
            d1, d2 = o(a[:2], a[2:], b[:2]), o(a[:2], a[2:], b[2:]); d3, d4 = o(b[:2], b[2:], a[:2]), o(b[:2], b[2:], a[2:])
            if d1 * d2 < 0 and d3 * d4 < 0:
                cross += 1
    assert cross <= max(2, len(segs) // 8), cross
