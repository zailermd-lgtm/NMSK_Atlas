"""Q344: the readability / screen-area round -- static checks (the browser ones are scripts/anatomy/q344/verify_ui_q344.py)."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FORBIDDEN = ["ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode"]


def run(*a):
    return subprocess.run([sys.executable, *a], cwd=REPO, capture_output=True, text=True)


def test_blocks_are_in_sync_and_patch_is_applied():
    assert run("scripts/sync_q344.py", "--check").returncode == 0
    assert run("scripts/anatomy/q344/patch_ui_q344.py", "--check").returncode == 0


def test_module_has_no_private_wording():
    t = "\n".join((REPO / "viewer/q344" / n).read_text(encoding="utf-8").lower() for n in ("q344.css", "q344.js"))
    assert not [w for w in FORBIDDEN if w in t]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_human_wording():
    src = (REPO / "viewer/parts_ui/parts_ui.js").read_text(encoding="utf-8")
    i = src.index("var NMSKHuman = (function(){")
    j = src.index("try { window.NMSKHuman")
    code = ("global.window={__ANATOMY_MANIFEST__:{meshes:[{id:'humerus_l',name:'Humerus'}]}};" + src[i:j] +
            ";const H=NMSKHuman;console.log(JSON.stringify([H.line('humerus_l: medial epicondyle'),H.nerve('median n'),"
            "H.text('generated in Q323; see data/ligaments/*.json and shoulder_muscles_reference_v1.html'),"
            "H.list(['biceps_femoris_r_long_head']),H.badge('Q162 gap closure: x').main]))")
    out = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)
    assert out[0] == "Humerus (left): medial epicondyle"
    assert out[1] == "median nerve"
    assert not re.search(r"Q\d{3}|\.json|\.html|data/", out[2])
    assert out[3] == ["Biceps femoris long head (right)"]
    assert out[4].startswith("Surface adjusted")
