"""Q237: the Symmetric-view fragment in both templates (single source, markers, engine hooks), the mirror Source class (own template, python mirror), the sidecars and the recorded browser check."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
D = REPO / "data/derived"
OWN = (REPO / "viewer/atlas_viewer.template.html").read_text()
ZAN = (REPO / "viewer/zan_atlas.template.html").read_text()
sys.path.insert(0, str(REPO / "scripts"))


def between(text, b, e):
    i = text.index(b) + len(b)
    return text[i:text.index(e, i)].strip("\n")


def test_templates_carry_the_fragment_verbatim_and_sync_is_a_no_op():
    r = subprocess.run([sys.executable, "scripts/sync_symview_q237.py", "--check"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    for kind, f, (b, e) in (("css", "symview.css", ("/* SYMVIEW css begin */", "/* SYMVIEW css end */")), ("html", "symview.html", ("<!-- SYMVIEW html begin -->", "<!-- SYMVIEW html end -->")),
                            ("js", "symview.js", ("/* SYMVIEW js begin */", "/* SYMVIEW js end */"))):
        frag = (REPO / "viewer/symview" / f).read_text().rstrip("\n")
        for t in (OWN, ZAN):
            assert t.count(b) == 1 and t.count(e) == 1 and between(t, b, e) == frag, (kind,)
    for t, g in ((OWN, "glue_own.js"), (ZAN, "glue_zan.js")):
        assert between(t, "/* SYMVIEW glue begin */", "/* SYMVIEW glue end */") == (REPO / "viewer/symview" / g).read_text().rstrip("\n")


def test_control_and_banner_wording():
    js = (REPO / "viewer/symview/symview.js").read_text(); html = (REPO / "viewer/symview/symview.html").read_text()
    for w in ("Symmetric view: off", "Mirror right onto left", "Mirror left onto right"):
        assert w in js
    assert "Symmetric view: not measured data" in html and 'id="sym-off"' in html
    assert "symmetry_q237.json" in (REPO / "viewer/symview/glue_own.js").read_text() and "symmetry_q237.json" in (REPO / "viewer/symview/glue_zan.js").read_text()
    assert "fetch(E.url)" in js and ".catch(function(){})" in js            # graceful fallback: no sidecar = no control, no error


def test_own_engine_hooks_cut_planes_and_caps():
    g = (REPO / "viewer/symview/glue_own.js").read_text()
    assert "a.clippingPlanes = cut.on ? cutPlanes : null" in g and "changeHooks.push(symSync)" in g          # the mirrored copy takes the same clipping planes as the originals
    assert "symCap(out);" in OWN and "matrixAutoUpdate = false" in g and "root.add(c)" in g and "symSpec.hideSet[m.userData.id]" in g and "m.visible = false" in g


def test_z_engine_hooks_shader_clip_and_winding():
    assert "uniform float uSymOn;uniform vec4 uSym;" in ZAN and "p=p-2.0*s*uSym.xyz;q=q-2.0*dot(q,uSym.xyz)*uSym.xyz;" in ZAN and "vP=p;" in ZAN
    assert '"uSymOn","uSym"' in ZAN and "gl.frontFace(gl.CW)" in ZAN and "gl.frontFace(gl.CCW)" in ZAN and "symPass ? !symIsSrc(o) : symHide(o)" in ZAN
    assert "var sb = symBox(o)" in ZAN and ZAN.count("symBox(o)") >= 3 and "symCap(out);" in ZAN and "function scenePass()" in ZAN
    # the clip test stays in the fragment shader on vP (the mirrored position): uClip / uClip2 apply to the copy
    assert "dot(vP,uClip.xyz)+uClip.w>0.0 || dot(vP,uClip2.xyz)+uClip2.w>0.0" in ZAN


def test_mirror_source_class_in_the_own_template_and_python_mirror():
    assert 'if (b.indexOf("mirror_") === 0) return "mirrored_opposite";' in OWN and '{k:"mirrored_opposite", name:"Mirrored from the opposite side"' in OWN
    assert re.search(r"mirror_q237: \"MIRROR IMAGE of the opposite side, fitted to this side's bones; not measured on this side", OWN)
    import audit_q189_model_separation as A
    assert A.classify("mirror_q237", None)[0] == "mirrored_opposite" and A.classify("ct_vhm", None)[0] == "measured"
    # the Z template lists no source classes (its cards carry the procedural badge): nothing to add there
    assert "classifySource" not in ZAN


def test_private_template_override_is_wired():
    for f in ("scripts/rebuild_own_html_from_built.py", "scripts/zanatomy/rebuild_html_from_built.py", "scripts/verify_regen_q218.py"):
        assert "NMSK_TEMPLATE_DIR" in (REPO / f).read_text(), f


PAGES = {"own_m": "build/q237/viewer_m_hr", "own_f": "build/q237/viewer_f_hr", "comb_m": "build/q237/viewer_zan_vhm", "comb_f": "build/q237/viewer_zan_female", "base_m": "build/q237/viewer_zan_atlas", "base_f": "build/q237/viewer_base_female"}


@pytest.mark.parametrize("k", list(PAGES))
def test_sidecar_of_each_page(k):
    p = REPO / PAGES[k] / "symmetry_q237.json"
    if not p.exists():
        pytest.skip("page not built")
    d = json.loads(p.read_text())
    assert d["version"] == 1 and d["page"] == k and abs(sum(x * x for x in d["plane"]["n"]) - 1) < 1e-6 and d["n_pairs"] == len(d["pairs"]) > 100
    ids = set(); 
    for r, l in d["pairs"]:
        assert r and l and not (set(r) & set(l)) and not (set(r) & ids) and not (set(l) & ids)
        ids |= set(r) | set(l)
    lat = ("liver", "spleen", "stomach", "heart", "pancreas", "gallbladder", "_lung", "colon", "left_ventricle", "right_ventricle", "atrium", "aorta", "vena_cava")
    bad = [i for i in ids if any(w in i for w in lat)]
    assert not bad, bad[:5]       # lateralised organs are never in the mirror list
    if k.startswith("base"):
        assert abs(d["plane"]["d"]) < 1.0 and d["plane"]["tilt_deg"] < 0.1


def test_recorded_browser_check():
    p = D / "Q237_pagecheck.json"
    if not p.exists():
        pytest.skip("not run")
    r = json.loads(p.read_text())
    assert len(r) == 6
    for d, res in r.items():
        for dev, info in res.items():
            assert info["errors"] == [], (d, dev, info["errors"])
            assert info["scrollW"] <= info["innerW"], (d, dev)
            assert info["sym_select"] and info["options"] == ["Symmetric view: off", "Mirror right onto left", "Mirror left onto right"], (d, dev)
            for m in ("r", "l"):
                md = info["modes"][m]
                assert md["state"]["mode"] == m and md["state"]["src"] > 100 and md["banner"] and "not measured data" in md["banner_text"]
            assert info["modes"]["off"]["banner"] is False and info["modes"]["off"]["state"]["mode"] == "off"
            if dev == "desktop":
                c = info["cut"]
                # default sagittal cut removes the right half: 'mirror left onto right' puts the mirrored left on the removed side, so the clipped picture must stay the cut model ...
                assert c["left_onto_right_vs_off_diff_frac"] < 0.03, (d, c)
                if "viewer_m_hr" in d or "viewer_f_hr" in d or "vhm" in d or "viewer_zan_female" in d:
                    # ... while 'mirror right onto left' (the mirrored right lands on the kept half) really changes it
                    assert c["right_onto_left_vs_off_diff_frac"] > 2 * c["left_onto_right_vs_off_diff_frac"], (d, c)
                if "viewer_m_hr" in d or "viewer_f_hr" in d:
                    assert c["debug_l"]["clipped"] == c["debug_l"]["copies"] > 100 and c["debug_l"]["cutOn"], c        # three.js: every mirrored copy carries the cut planes
                else:
                    assert c["debug_l"]["clipOn"] and c["debug_l"]["srcObjects"] > 1000, c
