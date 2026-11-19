"""Q382: the zoom chip fades after its delay (prefs in localStorage) and the layout / settings module is synced into both templates."""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_layout_module_is_synced_into_both_templates():
    for s in ("sync_layout_q382.py", "sync_q305.py", "sync_pinch_q290.py"):
        r = subprocess.run(["python3", "scripts/" + s, "--check"], cwd=REPO, capture_output=True, text=True)
        assert r.returncode == 0, s + "\n" + r.stdout + r.stderr


def test_private_words_stay_out_of_the_new_module():
    low = (REPO / "viewer/layout/layout.js").read_text(encoding="utf-8").lower()
    for w in ("ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode"):
        assert w not in low
