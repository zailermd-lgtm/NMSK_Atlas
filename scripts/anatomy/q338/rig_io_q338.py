"""Q338: read the pose rig a built page carries (the NMSK-POSE-RIG block) -> payload dict + weights blob."""
from __future__ import annotations
import base64, json, re, zlib
from pathlib import Path

BEGIN, END = "<!-- NMSK-POSE-RIG begin -->", "<!-- NMSK-POSE-RIG end -->"


def page_block(page_dir):
    h = sorted(Path(page_dir).glob("atlas_viewer*.html"))[0]
    s = h.read_text(encoding="utf-8")
    i, k = s.index(BEGIN), s.index(END)
    blk = s[i:k]
    js = blk[blk.index(">", blk.index("<script")) + 1: blk.rindex("</script>")]
    return json.loads(js)


def page_rig(page_dir):
    b = page_block(page_dir)
    return json.loads(zlib.decompress(base64.b64decode(b["j"])).decode("utf-8"))


def page_weights(page_dir):
    return zlib.decompress(base64.b64decode(page_block(page_dir)["w"]))
