"""Q305: the boxes on the screen can be moved where the user wants them, and they are still there next time.

Owner (translated from Hebrew): "let the various boxes on the screen be moved around."

These are the static checks; the browser ones are scripts/anatomy/q305/verify_q305.py.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
VIEWER = REPO / "viewer"
Q305 = VIEWER / "q305"
TEMPLATES = {"own": VIEWER / "atlas_viewer.template.html", "zan": VIEWER / "zan_atlas.template.html"}
MODULES = ["guard.js", "move.js", "q305.js"]
NODE = "node"


@pytest.fixture(scope="module")
def tpl():
    return {k: v.read_text(encoding="utf-8") for k, v in TEMPLATES.items()}


@pytest.fixture(scope="module")
def src():
    return {n: (Q305 / n).read_text(encoding="utf-8") for n in MODULES + ["q305.css"]}


def node(script: str):
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def load(*names):
    return "\n".join("const %s = require(%s);" % (n.split(".")[0].upper(), json.dumps(str(Q305 / n)))
                     for n in names)


# ---------------------------------------------------------------- the modules, and the splice -------------------
def test_every_module_is_present(src):
    for n in MODULES + ["q305.css"]:
        p = Q305 / n
        assert p.is_file() and p.stat().st_size > 400, n


def test_both_templates_carry_every_module(tpl):
    for eng, t in tpl.items():
        assert t.count("<!-- Q305 html begin -->") == 1 and t.count("<!-- Q305 html end -->") == 1, eng
        for sym in ("NMSKGuard", "NMSKMove", "NMSKQ305"):
            assert t.count("var %s = (function()" % sym) == 1, (eng, sym)


def test_the_block_comes_after_q303_so_everything_it_builds_on_exists(tpl):
    for eng, t in tpl.items():
        for m in ("<!-- Q294 html begin -->", "<!-- Q300 html begin -->", "<!-- Q301 html begin -->",
                  "<!-- Q303 html begin -->"):
            assert t.index(m) < t.index("<!-- Q305 html begin -->"), (eng, m)


def test_the_two_templates_carry_the_same_bytes(tpl):
    a = tpl["own"]
    b = tpl["zan"]
    ga = a[a.index("<!-- Q305 html begin -->"):a.index("<!-- Q305 html end -->")]
    gb = b[b.index("<!-- Q305 html begin -->"):b.index("<!-- Q305 html end -->")]
    assert ga == gb, "the Q305 block must be byte-identical in both engines"


def test_the_sync_script_is_up_to_date():
    r = subprocess.run(["python3", str(REPO / "scripts" / "sync_q305.py"), "--check"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


def test_this_round_needs_no_engine_patch(tpl):
    """The whole point of moving a box by its own `translate` is that no engine code changes. If a later round adds a
    Q305 glue splice, this test is the place to decide that deliberately rather than by accident."""
    for eng, t in tpl.items():
        assert "/* Q305 glue begin */" not in t, eng
    assert not (REPO / "scripts" / "anatomy" / "q305" / "patch_engines_q305.py").exists()


# ---------------------------------------------------------------- the offset rides on top, it never replaces ----
def test_the_offset_is_the_translate_property_and_never_left_or_top(src):
    """Q301 H2(iv): "a CSS `top` of ours would lose" -- six rounds rewrite these boxes' left / top, so the offset must
    compose with them instead of fighting them."""
    m = src["move.js"]
    assert "e.style.translate" in m
    # the BOX's position is never written. (`st.top` / `st.left` below it place the handle inside its own box, which
    # is the handle's own corner and not the box's position -- `st` is the grip's style, never the box's.)
    assert not re.search(r"\be\.style\.(left|top|right|bottom)\s*=", m), "Q305 must not set a box's position"
    assert "setOff" in m and m.count("e.style.translate") == 1
    assert 'CSS.supports("translate"' in m, "and it must feature-detect, with a transform fallback"
    assert "_nmBase" in m, "the fallback composes with the AUTHOR transform, read once"


def test_an_untouched_box_is_not_clamped_and_an_off_screen_one_is_left_alone(src):
    """The defect the harness found: clamping every box, moved or not, dragged a CLOSED bottom sheet 538 px back on
    screen over the model, where it swallowed the orbit."""
    m = src["move.js"]
    assert "if (!dx && !dy) return [0, 0];" in m
    assert "r.right > 0 && r.bottom > 0 && r.left < vw() && r.top < vh()" in m


def test_the_stored_offset_is_not_clamped_only_the_applied_one(src):
    assert "The applied offset is CLAMPED; the stored one is not" in src["move.js"]


def test_the_self_healing_pass_asks_about_the_base_and_not_about_our_own_offset(src):
    """The defect the first real-page run found, at 390x844 on the Base page. A slot is a position relative to the
    box's BASE rectangle, and Q301's `place()` moves that base after our first pass (at boot it runs after us). The
    offset resolved against the stale base put the control bar at top 936 of an 844 px viewport -- and `shown()`,
    which measures the box WITH our offset, then read false, so the 600 ms pass that would have re-resolved it
    skipped the box for ever and the bar (with Undo and Redo on it) never came back. The pass must therefore ask
    whether the PAGE puts the box on the screen, which is what `clamped()` already asks of the base."""
    m = src["move.js"]
    assert "function shownBase(b)" in m, "the base-rectangle question needs its own helper"
    assert "if (shownBase(b)) apply(b, false)" in m, "applyAll must ask about the base"
    assert "if (!shownBase(b)){" in m, "refresh must ask about the base"
    assert "if (!shown(e)){ if (b._grip && !e) b._grip = null; return; }" not in m, \
        "refresh must no longer skip a box because OUR OWN offset took it off the screen"
    assert "936" in m, "the measurement that found it is written down"
    # and a box with nothing of ours applied must still take the cheap path
    assert "if (!(b._ax || b._ay)) return shown(e);" in m


# ---------------------------------------------------------------- the gestures that already exist ---------------
def test_a_drag_is_one_pointer_counted_over_the_whole_document(src):
    """A pinch whose FIRST finger lands on the handle puts its second finger beside the handle, where the handle never
    gets a pointerdown of its own -- so a count kept on the handle stays at one and the pinch dragged the box."""
    m = src["move.js"]
    assert 'document.addEventListener("pointerdown", down, true)' in m
    assert "if (drag && Object.keys(LIVE).length > 1) cancel();" in m
    assert "if (!drag && e.isPrimary !== false) LIVE = {};" in m, "the count must self-heal"


def test_a_tap_on_the_handle_is_not_a_move(src):
    m = src["move.js"]
    assert "THRESH = 4" in m
    assert "if (Math.abs(mx) < THRESH && Math.abs(my) < THRESH) return;" in m
    assert "if (!d.moved) return;" in m


def test_the_handle_releases_its_pointer_capture_by_hand(src):
    """A capturing handle keeps every later pointer event, which looks exactly like "the model stopped orbiting"."""
    m = src["move.js"]
    assert "releasePointerCapture" in m
    assert 'window.addEventListener("blur", function(){ cancel(); });' in m


def test_the_handles_hit_area_grows_inward_only(src):
    """Measured, not a preference: 9 px of padding in every direction stuck out of the box onto the canvas and
    Chromium's touch adjustment snapped a finger 7 px clear of the panel to the handle."""
    c = src["q305.css"]
    assert ".nm-grip::before{content:\"\";position:absolute;inset:0}" in c
    for at in ("tl", "tr", "bl", "br"):
        assert '.nm-grip[data-nm-at="%s"]::before' % at in c
    assert "inset:-9px" not in c and "inset:-6px" not in c
    # and every inset that is negative is paired with a 0 on the opposite side, i.e. it only grows into the box
    for line in c.splitlines():
        if ".nm-grip[data-nm-at=" in line and "::before" in line:
            ins = line[line.index("inset:") + 6:line.rindex("}")]
            parts = re.findall(r"0|calc\([^)]*\)", ins)
            assert len(parts) == 4, line
            assert parts.count("0") == 2, line


def test_the_handle_is_at_least_the_projects_touch_target(src):
    c = src["q305.css"]
    assert re.search(r"@media \(pointer:coarse\)\{\.nm-grip\{width:34px;height:34px;--nm-pad:10px\}\}", c)
    assert "--nm-pad,18px" in c                                      # 26 + 18 = 44 on a fine pointer


def test_the_handle_never_drags_the_canvas_or_a_list_row(src):
    """Nothing in this round listens on a surface or on a row: every listener is on the handle, the document or the
    window -- which is the whole reason the orbit, the pinch, the probe and the long-press ranges are untouched."""
    m = src["move.js"]
    hosts = sorted(set(re.findall(r"(\w+)\.addEventListener\(", m)))
    assert hosts == ["document", "g", "window"], hosts
    for bad in ("#view", "#stage", "#list", "touchstart", "querySelectorAll"):
        assert bad not in m, bad


# ---------------------------------------------------------------- the collision check ---------------------------
def test_the_collision_check_is_element_from_point_at_the_controls_centre(src):
    """The instrument that caught Q301's info drawer over Undo and Q300's chip bar over Redo."""
    g = src["guard.js"]
    assert "document.elementFromPoint(x, y)" in g
    assert "r.left + r.width / 2" in g and "r.top + r.height / 2" in g
    assert "t === e || e.contains(t) || t.contains(e)" in g


def test_a_drop_that_covers_a_control_is_refused(src):
    m = src["move.js"]
    assert "if (bad.length > d.bad0.length){" in m
    assert "reverts++" in m
    assert "guard.hard" in m, "the refusal is decided on the hard set, not on a handle under another box"


def test_the_controls_q301_lost_to_an_overlap_are_all_watched(src):
    q = src["q305.js"]
    for i in ("q301-undo", "q301-redo", "q301-reset", "q301-mr-model", "q301-info-btn", "sa-all"):
        assert i in q, i
    assert "#q301-sheet:not([hidden]) .qg-sbody button" in q, "the open group's own controls too (Q301 H2 iv)"
    assert "soft:true" in q and ".nm-grip" in q


def test_a_handle_is_reseated_to_a_corner_that_is_really_reachable(src):
    m = src["move.js"]
    assert 'CORNERS = ["tl", "tr", "br", "bl"]' in m
    assert "function reseat(" in m and "elementFromPoint" in m


# ---------------------------------------------------------------- the store -------------------------------------
def test_every_storage_read_and_write_is_guarded(src):
    """It can throw (a private window, blocked site data) and it can come back empty, and the page must be exactly as
    usable either way."""
    m = src["move.js"]
    for call in re.finditer(r"localStorage\.(getItem|setItem)", m):
        seg = m[max(0, call.start() - 260):call.start()]
        assert "try {" in seg, m[call.start() - 120:call.start() + 80]
    assert m.count("localStorage.getItem") == 1 and m.count("localStorage.setItem") == 1


def test_the_store_is_per_page(src):
    assert '"nmsk.q305.layout." + opt.key' in src["move.js"]
    assert "function pageKey()" in src["q305.js"]


def test_the_layout_is_an_ordinary_history_provider(src):
    """So it is in Q294's Undo / Redo and in Q300's model reset for free -- the model reset restores the history's own
    load snapshot, and this key is in it."""
    m = src["move.js"]
    assert 'hist.register("q305layout"' in m
    assert "reset:function(){}" in m, "Q294's Reset is the module you are in; the boxes are the page's chrome"


def test_restore_is_one_undo_step(src):
    m = src["move.js"]
    block = m[m.index("function restore(){"):m.index("function restore(){") + 700]
    assert block.count("hist.commit()") == 1, "exactly one commit, so exactly one entry"
    assert "B.forEach(function(b){ b.dx = 0; b.dy = 0; b.slot = \"\"; });" in block


def test_restore_is_reachable_from_the_control_bars_view_group_and_not_as_a_new_top_level_button(src):
    q = src["q305.js"]
    assert 'G.addTo("view", {' in q
    assert '"Restore layout"' in q
    assert "document.body.appendChild" not in q, "no new top-level button of our own"


def test_the_round_has_an_i_section_built_from_the_real_state(src):
    q = src["q305.js"]
    assert 'I.add({key:"layout"' in q
    assert "NMSKMove.state()" in q and "NMSKGuard.watched()" in q


# ---------------------------------------------------------------- the phone decision ---------------------------
def test_the_phone_rule_is_measured_and_the_threshold_is_written_down(src):
    m = src["move.js"]
    assert "freeX < 48" in m and "freeY < 48" in m
    assert "under one thumb (48 px)" in m


def test_a_wide_box_gets_bands_and_a_small_one_corners(src):
    """A box with no room on an axis gets one centred position there; a box with room gets the two edges. So a wide
    box ends up with three bands (tc / mc / bc) and a small one with the six (tl..br)."""
    m = src["move.js"]
    assert 'var wide = freeX < 48, tall = freeY < 48;' in m
    assert 'xs = wide ? [{k:"c"' in m
    assert '[{k:"l"' in m and '{k:"r"' in m
    assert 'ys = tall ? [{k:"m"' in m
    assert '[{k:"t"' in m and '{k:"b"' in m


def test_the_module_list_is_one_table_for_both_engines(src):
    q = src["q305.js"]
    keys = re.findall(r'\{key:"([a-z]+)",\s+el:"([a-z0-9-]+)"', q)
    assert len(keys) >= 11, keys
    got = dict(keys)
    # the Z engine's three and the shared ones -- a box whose element is not on a page is simply never mounted
    for k, e in (("rail", "rail"), ("card", "info"), ("pills", "topright"), ("control", "q301-bar"),
                 ("hidden", "sa-bar"), ("info", "q301-info"), ("cut", "cut-panel"), ("measure", "ms-bar"),
                 ("slices", "xsp-panel"), ("expand", "q8-float")):
        assert got.get(k) == e, (k, got.get(k))


def test_what_is_not_movable_is_named_with_its_reason(src):
    q = src["q305.js"]
    for s in ("pz-chip", "q3-ch", "q301-sheet", "data-nmsk-move"):
        assert s in q, s
    assert "GRID COLUMNS" in q


def test_every_module_parses(src):
    for n in MODULES:
        r = subprocess.run([NODE, "--check", str(Q305 / n)], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, (n, r.stderr[-2000:])


def test_the_research_note_rests_every_claim_on_a_quote():
    p = REPO / "docs" / "research" / "Q305_movable_panels.md"
    t = p.read_text(encoding="utf-8")
    assert t.count("«") == t.count("»") and t.count("«") >= 10
    assert "לא מאומת" in t
    assert "WebFetch" in t and "WebSearch" in t
