"""Q300: assertions for the interface round -- the "show everything" guard, the model reset, the bone-through pass in
X-ray and Fade, and the method / error_band_mm fields that Q297 found the templates never rendered.

These are source- and build-level assertions; the behaviour itself is checked in a real browser by
scripts/anatomy/q300/verify_q300.py, whose result is read here from data/derived/Q300_browser_check.json when it exists."""
from __future__ import annotations
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
VIEWER = REPO / "viewer"
Q300 = VIEWER / "q300"
TEMPLATES = [VIEWER / "atlas_viewer.template.html", VIEWER / "zan_atlas.template.html"]
BUILD = REPO / "build/q300" if (REPO / "build/q300").is_dir() else REPO / "build/q297"
PAGES = sorted(p for p in BUILD.glob("*/index.html")) if BUILD.is_dir() else []
OWN = ("viewer_m_hr", "viewer_f_hr")


@pytest.fixture(scope="module")
def tpl():
    return {t.name: t.read_text(encoding="utf-8") for t in TEMPLATES}


@pytest.fixture(scope="module")
def mods():
    return {p.name: p.read_text(encoding="utf-8") for p in Q300.glob("*.js")}


# ---------------------------------------------------------------- the shared module exists and is spliced into both
def test_the_three_modules_exist():
    for n in ("showall.js", "modelreset.js", "bonexray.js", "q300.css"):
        assert (Q300 / n).is_file(), f"viewer/q300/{n} is missing"


def test_both_templates_carry_the_q300_block(tpl):
    for name, t in tpl.items():
        assert t.count("<!-- Q300 html begin -->") == 1, name
        assert t.count("<!-- Q300 html end -->") == 1, name
        for sym in ("NMSKShowAll", "NMSKModelReset", "NMSKBoneRead"):
            assert sym in t, f"{name} does not carry {sym}"


def test_sync_q300_is_up_to_date():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, str(REPO / "scripts/sync_q300.py"), "--check"],
                       capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------- 1. every hiding path is registered, on both engines
MUST_COVER = {
    "atlas_viewer.template.html": ["iso", "hidegrp", "hideone", "layers", "facet", "sysalpha", "fadeone", "cut", "slices"],
    "zan_atlas.template.html": ["solo", "hidegrp", "hideone", "layers", "side", "preset", "box", "cut", "slices"],
}


def test_every_known_hiding_path_is_registered_with_showall(tpl):
    """the nine paths the Q300 benchmark counted in the two engines; a tenth one added later must be added here too"""
    for name, t in tpl.items():
        blk = t[t.index("NMSKShowAll.start("):]
        blk = blk[:blk.index("});") + 3]
        missing = [k for k in MUST_COVER[name] if f'key:"{k}"' not in blk.replace(" ", "")]
        assert not missing, f"{name}: hiding paths with no way out registered: {missing}"


def test_each_source_can_be_driven_and_cleared(tpl):
    """a descriptor with no clear() would be a dead end, and one with no drive() cannot be verified in the browser"""
    for name, t in tpl.items():
        blk = t[t.index("NMSKShowAll.start("):]
        blk = blk[:blk.index("});") + 3]
        keys = re.findall(r'key\s*:\s*"([a-z]+)"', blk)
        assert len(keys) >= 9, f"{name}: only {len(keys)} hiding paths registered"
        assert blk.count("clear:") == len(keys), f"{name}: {len(keys)} keys but {blk.count('clear:')} clear()"
        assert blk.count("drive:") == len(keys), f"{name}: {len(keys)} keys but {blk.count('drive:')} drive()"


def test_escape_clears_only_when_something_is_hidden(mods):
    """Escape must stay available to the engines' own deselect when nothing is hidden"""
    s = mods["showall.js"]
    assert "if (!anyActive()) return;" in s
    assert "stopImmediatePropagation" in s


def test_an_exit_is_one_undo_step(mods):
    s = mods["showall.js"]
    assert s.count("hist.commit()") >= 2, "an exit must commit before and after, so it is a single undo step"


# ---------------------------------------------------------------- 2. the model reset
def test_model_reset_restores_the_load_snapshot(mods):
    s = mods["modelreset.js"]
    assert "hist.snapshot()" in s, "the load state must come from the history's own snapshot"
    assert "hist.restore(LOAD)" in s
    assert "resetView" in s, "the camera is outside the history and must be restored separately"


def test_model_reset_states_what_it_does_and_does_not_touch(mods):
    s = mods["modelreset.js"]
    for w in ("pose", "camera", "isolation", "measurements"):
        assert w in s, f"the model reset does not say it touches {w}"
    for w in ("the module you are in", "work mode", "saved"):
        assert w in s, f"the model reset does not say it leaves {w} alone"


def test_history_can_restore_an_arbitrary_snapshot_without_rewriting_the_entry():
    """NMSKModelReset leans on NMSKHistory.restore(); if that overwrote H[idx] the pre-reset state would be lost"""
    h = (VIEWER / "q294" / "history.js").read_text(encoding="utf-8")
    assert "restore:" in h, "Q300 added NMSKHistory.restore(); it is gone"
    i = h.index("function applyObj")
    assert "H[idx]" not in h[i:h.index("}", h.index("finally", i))], "restore() must not rewrite the current entry"


def test_pose_is_a_history_provider_so_the_reset_covers_it(tpl):
    for name, t in tpl.items():
        assert 'NMSKHistory.register("pose"' in t, f"{name}: pose is not in the history, so no reset can undo it"


# ---------------------------------------------------------------- 3. the skeleton must read in x-ray and fade
def test_bone_pass_strength_is_taps_not_a_slider(mods):
    s = mods["bonexray.js"]
    assert "<input" not in s and "type=\"range\"" not in s, "the mobile rule: taps or drag, not a slider"
    assert re.search(r"A\s*=\s*\[0,\s*0?\.\d+,\s*0?\.\d+\]", s), "three steps expected"


def test_bone_pass_is_in_the_history(mods):
    assert 'register("boneread"' in mods["bonexray.js"]


def test_both_engines_draw_the_extra_bone_pass(tpl):
    """the fix that does not depend on how many layers lie in front of the bone"""
    own = tpl["atlas_viewer.template.html"]
    zan = tpl["zan_atlas.template.html"]
    assert "boneRead" in own and "depthTest" in own, "own engine: no bone overlay material"
    assert "boneRead" in zan, "Z engine: no bone pass"
    assert "DEPTH_TEST" in zan


def test_the_fade_alpha_has_a_floor_per_tissue_class():
    """the fade view used one flat 0.15 for every class, which is why bone faded exactly as hard as skin"""
    s = (VIEWER / "selection" / "selection.js").read_text(encoding="utf-8")
    assert "FADE_FLOOR" in s, "no per-class floor in the fade state"
    assert re.search(r"FADE_FLOOR\s*=\s*\{[^}]*bone\s*:", s), "the floor does not name bone"


@pytest.mark.skipif(not (REPO / "data/derived/Q300_browser_check.json").is_file(),
                    reason="browser check has not been run")
def test_measured_bone_contrast_passes_on_both_engines():
    d = json.loads((REPO / "data/derived/Q300_browser_check.json").read_text(encoding="utf-8"))
    rows = []
    for page, vps in d.items():
        if page.startswith("BEFORE_"):
            continue
        for vp, got in (vps or {}).items():
            for mode, row in ((got or {}).get("modes") or {}).items():
                if row.get("off") is not None and row.get("clear") is not None:
                    rows.append((vp, mode, row["off"], row["clear"]))
    assert rows, "the browser check recorded no contrast figures"
    bad = [r for r in rows if not (r[3] >= 0.12 and r[3] > r[2] + 0.02)]
    assert not bad, f"bone does not read clearly in: {bad}"


# ---------------------------------------------------------------- 4. provenance can no longer be hidden (Q297 E)
def test_both_templates_render_method_and_error_band(tpl):
    for name, t in tpl.items():
        assert "r.method" in t, f"{name} still never renders rec.method"
        assert "r.error_band_mm" in t, f"{name} still never renders rec.error_band_mm"


@pytest.mark.skipif(not PAGES, reason="no build directory on disk")
def test_every_record_with_a_method_is_on_a_page_that_renders_it():
    """the 68 brachial-plexus meshes (34 per Imaging page) carry method + error_band_mm; nothing else does yet"""
    seen = {}
    for p in PAGES:
        t = p.read_text(encoding="utf-8")
        seen[p.parent.name] = (len(re.findall(r'"method":\s*"', t)), len(re.findall(r'"error_band_mm":\s*[0-9]', t)))
    for own in OWN:
        if own in seen:
            assert seen[own] == (34, 34), f"{own}: expected 34 method / 34 error_band records, got {seen[own]}"
    total = sum(a for a, _ in seen.values())
    assert total >= 68, f"only {total} records carry a method across the build"


@pytest.mark.skipif(not PAGES, reason="no build directory on disk")
def test_no_page_claims_measured_for_a_rule_based_record():
    """Q297's finding, held: a record whose method is rule-based must not be classed as measured"""
    for p in PAGES:
        t = p.read_text(encoding="utf-8")
        for m in re.finditer(r'"subject":\s*"([^"]+)",\s*"rec":\s*\{"method":\s*"rule-based"', t):
            assert "rule" in m.group(1) or "q258" in m.group(1), \
                f"{p.parent.name}: rule-based record on subject {m.group(1)!r} that does not say so"
