"""Q390: a click tints the picked structure at once (LEQUAL blend pass, colour from the Settings "From now on" choice) in the Z engine."""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
Z = (REPO / "viewer/zan_atlas.template.html").read_text(encoding="utf-8")


def test_selection_module_is_synced():
    r = subprocess.run(["python3", "scripts/sync_q227.py", "--check"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_pick_tint_pass_passes_the_depth_test_and_blends():
    i = Z.index("Q390: this pass sat on the same depth")
    seg = Z[i:i + 900]
    assert "gl.depthFunc(gl.LEQUAL)" in seg and "gl.depthFunc(gl.LESS)" in seg and "gl.BLEND" in seg and "PICK_A" in seg


def test_tint_colour_comes_from_the_existing_colour_control():
    assert "uniform vec3 uHLc" in Z and "mix(c,uHLc,uHL*0.6)" in Z
    sel = (REPO / "viewer/selection/selection.js").read_text(encoding="utf-8")
    assert "function pickHex()" in sel and "pickHex:pickHex" in sel and "ucolNext" in sel.split("function pickHex()")[1].split("\n")[0]
    assert "selCtl.pickHex" in Z
