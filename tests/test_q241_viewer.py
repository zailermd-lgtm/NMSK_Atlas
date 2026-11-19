"""Q241: the Pose fragment in both templates (single source, markers, engine hooks, rig placeholder), its wording, storage guards and syntax."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
OWN = (REPO / "viewer/atlas_viewer.template.html").read_text()
ZAN = (REPO / "viewer/zan_atlas.template.html").read_text()
FR = REPO / "viewer/pose"


def between(text, b, e):
    i = text.index(b) + len(b)
    return text[i:text.index(e, i)].strip("\n")


def test_templates_carry_the_fragment_verbatim_and_sync_is_a_no_op():
    r = subprocess.run([sys.executable, "scripts/sync_pose_q241.py", "--check"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    for kind, f, (b, e) in (("css", "pose.css", ("/* POSE css begin */", "/* POSE css end */")), ("html", "pose.html", ("<!-- POSE html begin -->", "<!-- POSE html end -->")),
                            ("js", "pose.js", ("/* POSE js begin */", "/* POSE js end */"))):
        frag = (FR / f).read_text().rstrip("\n")
        for t in (OWN, ZAN):
            assert t.count(b) == 1 and t.count(e) == 1 and between(t, b, e) == frag, kind
    for t, g in ((OWN, "glue_own.js"), (ZAN, "glue_zan.js")):
        assert between(t, "/* POSE glue begin */", "/* POSE glue end */") == (FR / g).read_text().rstrip("\n")
    for t in (OWN, ZAN):
        assert t.count("<!-- NMSK-POSE-RIG begin -->") == 1 and 'id="nmsk-pose-rig"' in t


def test_zan_engine_hooks():
    assert "o.vOff = base;" in ZAN and "window.__poseLive && window.__poseLive(i)" in ZAN
    g = (FR / "glue_zan.js").read_text()
    assert "gl.bufferSubData" in g and "capGeomCache = {}" in g and "o.bmin = lo" in g and "labelsCtl.dirty()" in g
    o = (FR / "glue_own.js").read_text()
    assert "computeBoundingBox" in o and "needsUpdate = true" in o and "labelsCtl.dirty()" in o


def test_wording_and_safety():
    js = (FR / "pose.js").read_text(); html = (FR / "pose.html").read_text()
    assert "kinematic approximation, soft tissue not simulated (no collision / volume preservation)" in html
    for w in ("Reset to model pose", "Anatomical position", "Symmetric pose R", "Link left and right", "Save pose", "Load pose", "population averages", "R\u2192L", "L\u2192R"):
        assert w in js, w
    # localStorage only inside try / catch
    for m in re.finditer(r"localStorage\.(getItem|setItem)", js):
        before = js[max(0, m.start() - 160):m.start()]
        assert "try {" in before, before
    # no network: the rig is embedded. The SVG namespace of Q318's rings is an identifier passed to
    # createElementNS, not an address anything is fetched from, so it is the one allowed occurrence.
    bare = js.replace('createElementNS("http://www.w3.org/2000/svg"', "createElementNS(SVGNS")
    assert "http://" not in bare and "https://" not in bare and "fetch(" not in bare
    assert "DecompressionStream" in js


def test_pose_js_parses_and_exports_the_core():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    p = subprocess.run([node, "-e", "const s=require('fs').readFileSync(process.argv[1],'utf8');const r=new Function(s+';return {c:NMSKPoseCore,p:NMSKPose};')();console.log(Object.keys(r.c).sort().join(','), typeof r.p)",
                        str(FR / "pose.js")], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert "fk" in p.stdout and "decodeSkin" in p.stdout and "function" in p.stdout


# ---------------------------------------------------------------- Q318: the rings on the model ------------------
def test_the_rings_read_the_joint_from_the_same_kinematics_that_moved_the_geometry():
    """Q318, owner: "if I have marked POSE then moving over a joint should mark the 3 axis rings on that
       joint, and if I click on them, allow changing it graphically on the model itself, with or without
       the detailed window."

       The ring must not be able to point somewhere the bone is not, so its centre and axes come from the
       SAME segment matrices (st.M) that carried the vertices, and a drag must go through setJoint(), the
       door the slider already uses, so the clamp to the joint's own range and the left/right link apply
       identically. Verified in a browser by scripts/anatomy/q318/verify_rings_q318.py."""
    js = (FR / "pose.js").read_text()
    assert "function jointFrame(" in js
    assert re.search(r"return \{c:m12p\(st\.M\[par\], j\.c\), ax:ax\};", js), \
        "the centre must come from the forward kinematics, not from a separate guess"
    assert "C.mul3(R, C.rotM(j.dof[k].a, q[k]))" in js, \
        "dof k turns about its own axis carried by the dofs before it, as fk composes them"
    assert re.search(r"setJoint\(D\.id, D\.key, D\.q0 \+ dd\)", js), "a drag must go through setJoint"
    # the allowed range is what you can grab, so a turn cannot be started from outside it
    assert 'class:"pz-grab"' in js and "arc.length > 1 ? arc : pts" in js
    # and the panel is not required
    assert "function ringsOn(" in js and "if (st.open && st.ready) ringsOn(true);" in js
    html = (FR / "pose.html").read_text()
    assert 'id="pz-rings-btn"' in html, "there must be a way to switch the rings off again"


def test_reaching_for_a_ring_does_not_hand_the_rings_to_a_neighbouring_joint():
    """Measured before this guard existed: the shoulder's outer ring is 84 px out, and moving the pointer
       onto it passed within reach of the elbow, so the rings jumped to the elbow on the way and the drag
       then started on a joint that was no longer the one drawn. Two things stop it: the pointer over the
       rings never re-picks, and the joint already showing its rings keeps them while the pointer is inside
       them. The drag also takes the joint from the path it started on, not from the hover state."""
    js = (FR / "pose.js").read_text()
    assert 'closest("#pz-rings")' in js, "a pointer over the rings must not re-pick the joint"
    assert re.search(r"if \(ca && Math\.hypot\(ca\[0\] - x, ca\[1\] - y\) <= REACH\) return cur;", js), \
        "the joint showing its rings must keep them while the pointer is within them"
    assert "grab.dataset.j = j.id;" in js and 'e.currentTarget.dataset.j || rg.jid' in js, \
        "the drag must use the joint the ring was drawn for"


def test_both_engines_can_say_where_a_point_of_the_model_is_on_the_screen():
    """The rings are an SVG over the canvas -- nothing enters either 3D scene -- so each engine has to
       answer one question: where does this model-frame point land. The Z engine answers with the same
       model->clip matrix the labels are placed with; the three.js engine projects through its camera."""
    for glue, needle in (("glue_zan.js", "lastMVP"), ("glue_own.js", "project(camera)")):
        src = (FR / glue).read_text()
        assert "toScreen:function(p)" in src, glue
        assert needle in src, (glue, needle)
        assert "canvasRect:function()" in src, glue
    assert "toScreen:function(p)" in OWN and "toScreen:function(p)" in ZAN


def test_the_z_engine_uploads_every_structure_whatever_its_system():
    """Q318: WHY POSE WAS BROKEN ON THE Z PAGES. A structure whose system is not one of the engine's
       fourteen layers was put in perLayer under its own key, which the batching loop -- which walks LK --
       never visits. It was never uploaded and never drawn, and the first pose that touched it threw on its
       missing batch, taking the whole pose update with it. Four structures were in that state on every Z
       page: the knee's anterolateral and the coracoacromial ligament, both sides, system "ligament".
       The page's own systems table already groups ligament WITH joint, which is the layer they are now
       drawn as, and anything still unknown is drawn as bone and counted rather than vanishing."""
    assert 'var SYS_LAYER = {ligament:"joint"}, UNKNOWN_SYS = {};' in ZAN
    assert "if (perLayer[layer] === undefined){ UNKNOWN_SYS[sys] = (UNKNOWN_SYS[sys] || 0) + 1; layer = \"bone\"; }" in ZAN
    assert "window.__layerAudit = function()" in ZAN, "the hole must be visible if it ever reopens"
    assert "var NOBATCH = OBJ.filter(function (o) { return !o.batch; })" in ZAN
