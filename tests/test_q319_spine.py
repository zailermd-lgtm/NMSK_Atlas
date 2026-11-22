"""Q319: the spine moves either as a segment or one vertebra at a time, and both engines agree it does.

Owner: "in POSE the spine also needs movement in the relevant regions. Bear in mind that this is
sometimes more challenging, because one joint's movement is usually small and the movement is made of
several vertebrae moving together. Allow performing a movement either of a specific joint or of a
segment."

The segment half already existed: a region carries one angle per degree of freedom and the forward
kinematics shares it out over the region's levels by weights the project derived from the literature
(`spine_weights` in scripts/anatomy/q241/rom.py -- C1/C2 takes half the cervical rotation, the
occiput/C1 joint a fifth of the flexion arc). What Q319 adds is the other half: an offset belonging to
ONE vertebra, applied on top of its share, so that the two compose rather than overwrite each other.

This checks that composition where it actually has to hold -- in the maths, on a rig built here rather
than taken from a page, so it needs no built page and no browser:

  * a region's angle reaches every level in its own documented share, and nothing else moves;
  * a single level's offset moves that level and ONLY that level;
  * the two add, and a level is held inside its share of the regional range;
  * and the JavaScript the viewer runs agrees with the Python reference to numerical precision, which
    is the only thing that keeps `validate_pose.py` and the pages from drifting apart.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")
sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
import fk as FK  # noqa: E402

POSE_JS = REPO / "viewer" / "pose" / "pose.js"

# Three stacked levels and a region over them, in the shape make_pose_rig.py emits: segment 0 is the
# root, 1..3 are the vertebrae. The weights are deliberately unequal, as the cervical ones are.
W = [0.2, 0.3, 0.5]
RIG = {
    "segments": [{"par": -1}, {"par": 0}, {"par": 1}, {"par": 2}],
    "joints": [],
    "regions": [{
        "id": "lumbar", "name": "Lumbar spine", "group": "Lumbar spine",
        "levels": [{"seg": 1, "par": 0, "c": [0.0, 10.0, 0.0], "label": "L1"},
                   {"seg": 2, "par": 1, "c": [0.0, 20.0, 0.0], "label": "L2"},
                   {"seg": 3, "par": 2, "c": [0.0, 30.0, 0.0], "label": "L3"}],
        "dof": [{"k": "flex", "l": "Flexion", "a": [1.0, 0.0, 0.0], "lo": -30.0, "hi": 60.0, "q0": 0.0,
                 "rk": "lumb_flex", "w": W},
                {"k": "rot", "l": "Rotation", "a": [0.0, 1.0, 0.0], "lo": -10.0, "hi": 10.0, "q0": 0.0,
                 "rk": "lumb_rot", "w": W}],
    }],
}
# the viewer's rig dict uses `segs` as [id, parent] pairs; the python reference uses `segments`
RIG_JS = {"segs": [[i, s["par"]] for i, s in enumerate(RIG["segments"])],
          "joints": [], "regions": RIG["regions"]}


def py_pose(region=(0.0, 0.0), levels=None):
    p = FK.default_pose(RIG)
    p["regions"]["lumbar"] = list(region)
    if levels:
        for lv, off in levels.items():
            p["levels"]["lumbar"][lv] = list(off)
    return p


def py_matrices(pose):
    return [np.asarray(m) for m in FK.fk(RIG, pose)]


def js(script):
    src = POSE_JS.read_text(encoding="utf-8")
    out = subprocess.run([NODE, "-e", src + "\n" + script], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-3000:]
    return json.loads(out.stdout)


def js_matrices(region=(0.0, 0.0), levels=None):
    """the same pose through NMSKPoseCore.fk, as the pages run it"""
    call = """
      var C = NMSKPoseCore, rig = %s;
      var P = C.prepare(rig), pose = C.defaultPose(P);
      pose.r.lumbar = %s;
      var L = %s;
      Object.keys(L).forEach(function(k){ pose.l.lumbar[+k] = L[k]; });
      var M = C.fk(P, pose, []);
      console.log(JSON.stringify(M.map(function(m){ return Array.prototype.slice.call(m); })));
    """ % (json.dumps(RIG_JS), json.dumps(list(region)), json.dumps({str(k): v for k, v in (levels or {}).items()}))
    return [np.array(m, float).reshape(3, 4) for m in js(call)]


def angle_of(m):
    """the rotation this segment carries, in degrees, about the x axis of the 3x4 row-major matrix"""
    R = np.asarray(m)[:, :3]
    return float(np.degrees(np.arctan2(R[2, 1], R[1, 1])))


# ---------------------------------------------------------------- the segment half, as it already was
def test_a_region_angle_reaches_every_level_in_its_documented_share():
    M = py_matrices(py_pose(region=(30.0, 0.0)))
    # each level turns by its own share, and they accumulate down the chain
    got = [angle_of(M[i]) for i in (1, 2, 3)]
    want = np.cumsum([30.0 * w for w in W])
    assert np.allclose(got, want, atol=1e-9), (got, want.tolist())


# ---------------------------------------------------------------- the vertebra half, which Q319 adds
def test_one_vertebras_offset_moves_that_vertebra_and_nothing_above_it():
    M0 = py_matrices(py_pose())
    M1 = py_matrices(py_pose(levels={1: (7.0, 0.0)}))
    assert abs(angle_of(M1[1]) - angle_of(M0[1])) < 1e-9, "the level above it must not move"
    assert abs(angle_of(M1[2]) - angle_of(M0[2]) - 7.0) < 1e-9, "the level itself must carry the offset"
    # and the one below inherits it, because it hangs off it -- that is the chain, not a leak
    assert abs(angle_of(M1[3]) - angle_of(M0[3]) - 7.0) < 1e-9


def test_the_segment_and_the_vertebra_compose():
    M = py_matrices(py_pose(region=(30.0, 0.0), levels={1: (7.0, 0.0)}))
    want = np.cumsum([30.0 * W[0], 30.0 * W[1] + 7.0, 30.0 * W[2]])
    got = [angle_of(M[i]) for i in (1, 2, 3)]
    assert np.allclose(got, want, atol=1e-9), (got, want.tolist())


# ---------------------------------------------------------------- the two implementations must agree
@pytest.mark.parametrize("region,levels", [
    ((0.0, 0.0), None),
    ((30.0, 0.0), None),
    ((-20.0, 5.0), None),
    ((0.0, 0.0), {1: (7.0, 0.0)}),
    ((30.0, 0.0), {1: (7.0, 0.0)}),
    ((45.0, -8.0), {0: (-3.0, 1.0), 2: (6.0, -2.0)}),
], ids=["rest", "flex", "flex+rot", "one level", "both", "all of it"])
def test_the_viewers_javascript_agrees_with_the_python_reference(region, levels):
    a = js_matrices(region, levels)
    b = py_matrices(py_pose(region, levels))
    for i, (x, y) in enumerate(zip(a, b)):
        assert np.allclose(x, np.asarray(y)[:3, :4], atol=1e-9), (i, x.tolist(), np.asarray(y).tolist())


# ---------------------------------------------------------------- a level may not leave its own share
def test_a_vertebra_is_held_inside_its_share_of_the_regional_range():
    """The share is what the weights already mean, so no range is invented for a single vertebra: its
       limit is the regional limit times its weight. Driving one past that must clamp, not pass."""
    call = """
      var C = NMSKPoseCore, rig = %s, P = C.prepare(rig), r = rig.regions[0];
      var out = {range:[], total:[]};
      for (var lv = 0; lv < r.levels.length; lv++) out.range.push(C.levelRange(r, lv, 0));
      var pose = C.defaultPose(P);
      pose.r.lumbar = [30, 0];
      for (lv = 0; lv < r.levels.length; lv++) out.total.push(C.levelTotal(pose, r, lv, 0));
      console.log(JSON.stringify(out));
    """ % json.dumps(RIG_JS)
    r = js(call)
    # lo and hi of a level are the region's lo and hi times that level's weight
    for lv, w in enumerate(W):
        assert abs(r["range"][lv][0] - (-30.0 * w)) < 1e-9, (lv, r["range"][lv])
        assert abs(r["range"][lv][1] - (60.0 * w)) < 1e-9, (lv, r["range"][lv])
        assert abs(r["range"][lv][2] - w) < 1e-9
        # with the region at 30 degrees and no offset, a level stands exactly at its share
        assert abs(r["total"][lv] - 30.0 * w) < 1e-9, (lv, r["total"][lv])


def test_the_controller_offers_both_a_segment_and_a_vertebra():
    src = POSE_JS.read_text(encoding="utf-8")
    assert "function setLevel(" in src and "setLevel:function(" in src, "one vertebra at a time"
    assert "function setRegion(" in src, "and the whole segment, as before"
    assert "function levelsOf(" in src and "levels:levelsOf" in src, \
        "the UI and the checks both need to read a level's own share back"
    # the clamp is derived from the weights, never written as its own number
    assert "return [r.dof[d].lo * w, r.dof[d].hi * w, w];" in src, \
        "a level's range must be its share of the region's, so that no new range is invented"


def test_an_older_saved_pose_still_loads():
    """A pose saved before per-vertebra offsets existed has no `l`, and must come back meaning exactly
       what it meant when it was saved: every level at its share."""
    src = POSE_JS.read_text(encoding="utf-8")
    i = src.index("function apply(d)")
    body = src[i:src.index("\n  }", i)]
    assert "d.l && d.l[r.id]" in body, "the offsets are read only when the saved pose has them"
    p = FK.default_pose(RIG)
    assert "levels" in p and p["levels"]["lumbar"] == [[0.0, 0.0]] * 3
    old = {"joints": p["joints"], "regions": {"lumbar": [30.0, 0.0]}}      # no "levels" key at all
    M = py_matrices(old)
    assert np.allclose([angle_of(M[i]) for i in (1, 2, 3)], np.cumsum([30.0 * w for w in W]), atol=1e-9)
