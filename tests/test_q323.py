"""Q323: the attachments view of the "insertions" preset (viewer/parts_ui/) -- source-level assertions. The browser run is
scripts/anatomy/q323/verify_insertions_q323.py."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
D = REPO / "viewer" / "parts_ui"
JS = (D / "parts_ui.js").read_text(encoding="utf-8")
CSS = (D / "parts_ui.css").read_text(encoding="utf-8")
HTML = (D / "parts_ui.html").read_text(encoding="utf-8")
ZAN = (REPO / "viewer" / "zan_atlas.template.html").read_text(encoding="utf-8")
OWN = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
BANNED = ["ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode"]


def test_view_draws_origins_and_insertions_by_class():
    assert 'p.ty === "origin_part" ? "o" : p.ty === "insertion_point" ? "i"' in JS        # only the two attachment part types
    for k in ('"mt"', '"lig"', '"fas"', '"cap"', '"ret"', '"oth"'):
        assert k in JS, k
    assert "cls:{mt:true, lig:false, fas:false, cap:false, ret:false, oth:false}" in JS        # muscles & tendons on by default
    assert 'A.scope === "all" || byTissue' in JS                                               # all / selected-only
    assert "attach:attach" in JS and "attSet:attSet" in JS


def test_no_attachment_drawn_without_data():
    assert "no placed attachment on this body" in JS and " disabled" in JS
    assert "!!mk.ar && A.cls[mk.ac] === true" in JS                       # a marker is drawn only for a placed part of a ticked class


def test_panel_markup_and_style():
    assert 'id="pm-att"' in HTML
    assert "#pm-att{" in CSS and "width:max-content" in CSS and "--pm-ori" in CSS and "--pm-ins" in CSS
    assert ".pm.pm-ao .pm-ring" in CSS and ".pm.pm-ai .pm-ring" in CSS


def test_engine_glue_z_template():
    assert 'partsCtl.attach(name==="insert")' in ZAN
    assert "structs:function(){ return OBJ.map(" in ZAN
    r = subprocess.run([sys.executable, str(REPO / "scripts/anatomy/q323/patch_q323.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_templates_in_sync():
    r = subprocess.run([sys.executable, str(REPO / "scripts/sync_parts_ui_q220.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_sidecar_carries_structure_class():
    t = (REPO / "scripts/anatomy/q220/build_parts_sidecar.py").read_text(encoding="utf-8")
    assert 'row["sc"] = p["structure_class"]' in t


def test_no_banned_words():
    for name, t in (("js", JS), ("css", CSS), ("html", HTML), ("zan", ZAN), ("own", OWN)):
        low = t.lower()
        for w in BANNED:
            assert w not in low, (name, w)
