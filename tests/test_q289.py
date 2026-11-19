"""Q289: ultrasound CINE motion types + clean split full screen, and muscle fibre direction / documented septa in the simulation.

Static + node checks only (the browser behaviour is scripts/anatomy/q289/verify_q289.py)."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = (REPO / "clinical" / "ultrasound_tool.js").read_text(encoding="utf-8")
US = json.loads((REPO / "clinical" / "data" / "ultrasound_tissues.json").read_text(encoding="utf-8"))
CUR = json.loads((REPO / "data" / "anatomy" / "us_architecture_q289.json").read_text(encoding="utf-8"))
NODE = shutil.which("node")


def node(code):
    r = subprocess.run([NODE, "-e", code], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_architecture_table_is_up_to_date():
    r = subprocess.run(["python3", "scripts/clinical/q289_architecture.py", "--check"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_septum_is_cited_with_a_rule_and_only_curated_muscles_have_septa():
    A = US["architecture"]
    with_septa = {k for k, m in A["muscles"].items() if m.get("septa")}
    assert with_septa == {k for k, m in CUR["muscles"].items() if m.get("septa")}
    assert {"tibialis_anterior", "rectus_femoris", "soleus", "deltoid", "masseter"} <= with_septa
    for k in with_septa:
        for s in A["muscles"][k]["septa"]:
            assert s["refs"] and s["rule"] and s["name"], (k, s)
            for r in s["refs"]:
                ref = A["references"][r]
                assert re.fullmatch(r"\d{6,9}", ref["pmid"]) and ref["doi"].startswith("10."), (k, r)
    # gastrocnemius: aponeuroses documented but on the mesh surfaces -> no internal sheet invented
    assert not A["muscles"]["gastrocnemius"].get("septa") and A["muscles"]["gastrocnemius"]["apo"]["refs"]
    # masseter: laminae documented without a count -> only the head boundary is drawn
    assert len(A["muscles"]["masseter"]["septa"]) == 1 and "NOT drawn" in A["muscles"]["masseter"]["septa"][0]["rule"]


def test_pennation_values_come_from_the_muscle_records_with_their_source_lines():
    A = US["architecture"]
    ta = A["muscles"]["tibialis_anterior"]
    assert ta["p0"] == 15 and ta["p1"] == 6 and ta["pr"] == ["hiblar2003"]       # Hiblar 2003 abstract: ~15 deg near the belly -> ~6 deg near the ankle
    rf = json.loads((REPO / "data" / "muscles" / "lower_limb" / "rectus_femoris_r.json").read_text(encoding="utf-8"))
    pens = [(c["fiber_architecture"]["pennation_deg"], c["fiber_architecture"]["physiological_cross_section_area_mm2"]) for c in rf["functional_compartments"]]
    want = sum(p * a for p, a in pens) / sum(a for p, a in pens)
    assert abs(A["muscles"]["rectus_femoris"]["p"] - round(want, 1)) < 1e-9
    assert all(A["sources"][i] for m in A["muscles"].values() for i in m.get("s", []))
    assert any("Ward SR" in s for s in A["sources"])
    assert len(A["muscles"]) > 150


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_fibre_field_follows_the_rules_on_a_synthetic_muscle():
    out = node(r"""
      require('./clinical/ultrasound_tool.js'); const L = globalThis.NMSKUltrasoundLib;
      let s = 7; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
      const pos = []; for (let i = 0; i < 6000; i++) pos.push((rnd() - .5) * 30, (rnd() - .5) * 200, (rnd() - .5) * 12);   // width x, long y, thickness z
      const P = new Float32Array(pos), res = {};
      const ang = (f, a) => Math.acos(Math.min(1, Math.abs(f[0]*a[0] + f[1]*a[1] + f[2]*a[2]))) * 180 / Math.PI;
      for (const sp of [{t: 'unipennate', p: 20}, {t: 'bipennate', p: 20, septa: [{normal: 'w', at: 0.5, span: [0, 1]}]},
                        {t: 'multipennate', p: 20, septa: [{normal: 'w', count: 3, span_alternate: [[0, .7], [.3, 1]]}]}, {t: 'fusiform', p: 20},
                        {t: 'bipennate', p: 11, p0: 15, p1: 6, septa: [{normal: 'w', at: 0.5, span: [0, 1]}]}]) {
        const ar = L.archFrame(P, 0, 6000, sp, {prox: [0, 1000, 0]});
        const sh = ar.sheets.length ? ar.sheets[0].off : 0, pt = d => [ar.c[0] + ar.w[0]*d, ar.c[1] + ar.w[1]*d, ar.c[2] + ar.w[2]*d];
        const f1 = L.fibreAt(ar, ...pt(sh + 4)).slice(), f2 = L.fibreAt(ar, ...pt(sh - 4)).slice();
        L.fibreAt(ar, ...pt(sh)); const on = ar._sep; L.fibreAt(ar, ...pt(sh + 3)); const off = ar._sep;
        const prox = L.fibreAt(ar, ar.c[0] + ar.a[0]*(ar.la[0] + 2), ar.c[1] + ar.a[1]*(ar.la[0] + 2), ar.c[2] + ar.a[2]*(ar.la[0] + 2) + 0).slice();
        const dist = L.fibreAt(ar, ar.c[0] + ar.a[0]*(ar.la[1] - 2), ar.c[1] + ar.a[1]*(ar.la[1] - 2), ar.c[2] + ar.a[2]*(ar.la[1] - 2)).slice();
        res[sp.t + (sp.p0 ? '_graded' : '')] = {a1: ang(f1, ar.a), a2: ang(f2, ar.a), wdot: (f1[0]*ar.w[0] + f1[1]*ar.w[1] + f1[2]*ar.w[2]) * (f2[0]*ar.w[0] + f2[1]*ar.w[1] + f2[2]*ar.w[2]),
          tdot: Math.abs(f1[0]*ar.t[0] + f1[1]*ar.t[1] + f1[2]*ar.t[2]), on, off, sheets: ar.sheets.length, aY: ar.a[1], prox: ang(prox, ar.a), dist: ang(dist, ar.a)};
      }
      console.log(JSON.stringify(res));""")
    u, b, m, f, g = out["unipennate"], out["bipennate"], out["multipennate"], out["fusiform"], out["bipennate_graded"]
    assert u["aY"] < -0.99                                         # long axis oriented proximal (+Y here) -> distal
    assert abs(u["a1"] - 20) < 0.5 and u["tdot"] > 0.3              # unipennate: tilted toward the thickness axis
    assert abs(b["a1"] - 20) < 0.5 and abs(b["a2"] - 20) < 0.5 and b["wdot"] < 0   # bipennate: opposite sides lean opposite ways
    assert b["on"] > 0.99 and b["off"] < 0.01                      # the sheet is a ~1 mm hyperechoic band
    assert m["sheets"] == 3 and f["a1"] < 1e-3 and f["sheets"] == 0
    assert abs(g["prox"] - 15) < 0.6 and abs(g["dist"] - 6) < 0.6  # graded pennation along the muscle (Hiblar 2003)


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_playback_one_way_back_and_forth_and_loop():
    body = re.search(r"(function motionStep\(dist\) \{.*?\n    \})", SRC, re.S).group(1)
    out = node("""
      const S = {mRev: false, mBack: false, mLoop: false}; const mPath = {total: 100}; const contState = {pos: 0, dir: 1};
      """ + body + """
      function run(back, loop, steps) { S.mBack = back; S.mLoop = loop; contState.pos = 0; contState.dir = 1; const tr = [];
        for (let i = 0; i < steps; i++) { const more = motionStep(7); tr.push([contState.pos, contState.dir, more]); if (!more) break; } return tr; }
      const once = run(false, false, 100), back = run(true, false, 100), loop = run(false, true, 60), pp = run(true, true, 100);
      console.log(JSON.stringify({once: once.slice(-1)[0], onceN: once.length, back: back.slice(-1)[0], backTurn: back.some(x => x[1] < 0),
        loopEnded: loop.some(x => !x[2]), loopWrapped: loop.some((x, i) => i && x[0] < loop[i - 1][0] && x[1] > 0), ppEnded: pp.some(x => !x[2]), ppTurns: pp.filter((x, i) => i && x[1] !== pp[i - 1][1]).length}));""")
    assert out["once"] == [100, 1, False] and out["onceN"] == 15
    assert out["back"][0] == 0 and out["back"][2] is False and out["backTurn"]
    assert not out["loopEnded"] and out["loopWrapped"]
    assert not out["ppEnded"] and out["ppTurns"] >= 3


def test_cine_motion_types_extend_the_q257_continuous_cine_not_a_second_loop():
    assert len(re.findall(r"function contTick\(", SRC)) == 1
    assert 'if (S.motion) {' in SRC and "more = motionStep(motionSpeed() * dt); spec = motionSpec(contState.pos);" in SRC
    assert "if (S.motion) ensureMotion();" in SRC
    for k in ("long", "circ", "rot", "tilt", "track"):
        assert f'["{k}", ' in SRC
    # 90 deg to the skin: every path sample's frame is built from its own smoothed skin normal, never a tilt
    assert "return {id: S.sel, P: q.P, N: q.N, tilt: 0, dir: 0, off: 0, rotOverride: rotFor(q.N, q.u)" in SRC
    # the structure path is the mesh's own centreline
    assert "function centreline(sid)" in SRC and "binned along the PCA axis" in SRC


def test_full_screen_view_keeps_the_watermark_and_exits_by_tap_or_esc():
    assert 'var FS_MARK = "סימולציה מהמשים – לא סריקה";' in SRC
    assert "if (fs.on) { ctx.font" in SRC and "txt(FS_MARK," in SRC
    assert 'e.key === "Escape"' in SRC and '"aria-label": "יציאה ממסך מלא (Esc)"' in SRC
    assert "function fsLayout() { return window.innerWidth >= window.innerHeight ? \"row\" : \"col\"; }" in SRC
    assert 'body.us-fs #us-root>*:not(.us-views){display:none!important}' in SRC


def test_templates_untouched_and_js_syntax_clean():
    for t in ("viewer/atlas_viewer.template.html", "viewer/zan_atlas.template.html"):
        assert "Q289" not in (REPO / t).read_text(encoding="utf-8")
    if NODE:
        r = subprocess.run([NODE, "--check", "clinical/ultrasound_tool.js"], cwd=REPO, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
