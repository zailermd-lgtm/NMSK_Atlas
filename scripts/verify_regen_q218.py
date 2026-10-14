#!/usr/bin/env python3
"""Q218: prove a regenerated page differs from its source page only by the viewer template.

    python3 scripts/verify_regen_q218.py own|zan SOURCE_DIR OUT_DIR

* every geo file the page names is byte-identical in OUT_DIR (sha256);
* every other sibling file is byte-identical, except clinical_needle_tool.js which may be the current clinical/needle_tool.js;
* the data literals of the new page equal those of the source page;
* the git revision of the template that reproduces the SOURCE page byte for byte (after removing the artifact service's skeleton,
  if the source dir was restored from a published artifact) is found; the new page equals the CURRENT template filled with the same data.
So (source) = (old template + data) and (new) = (current template + data): nothing else differs. Prints one JSON line."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from platform_wrap import unwrap  # noqa: E402
import rebuild_own_html_from_built as ro  # noqa: E402
import rebuild_html_from_built as rz  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 22), b""):
            h.update(ch)
    return h.hexdigest()


def main():
    kind, src, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    tpl_rel = "viewer/atlas_viewer.template.html" if kind == "own" else "viewer/zan_atlas.template.html"
    mod = ro if kind == "own" else rz
    html_name = next(p.name for p in src.glob("atlas_viewer*.html"))
    s_html = unwrap((src / html_name).read_text(encoding="utf-8"))
    o_html = (out / html_name).read_text(encoding="utf-8")
    ext = ro.extract if kind == "own" else rz.extract_data
    ds, do = ext(s_html), ext(o_html)
    res = {"page": str(out), "literals_identical": all(ds[k] == do[k] for k in ds if k != "title") and ds.get("title") == do.get("title")}
    files = json.loads(ds["files"])
    res["geo_files"] = len(files)
    res["geo_identical"] = all(sha(src / f["path"]) == sha(out / f["path"]) for f in files)
    needle = (REPO / "clinical" / "needle_tool.js").read_bytes()
    sib, bad = [], []
    for p in sorted(src.iterdir()):
        if p.name in (html_name, "index.html") or p.name in {f["path"] for f in files}:
            continue
        q = out / p.name
        ok = q.exists() and (q.read_bytes() == p.read_bytes() or (p.name == "clinical_needle_tool.js" and q.read_bytes() == needle))
        sib.append(p.name + (" (needle tool refreshed from clinical/needle_tool.js)" if ok and p.name == "clinical_needle_tool.js" and q.read_bytes() != p.read_bytes() else ""))
        if not ok:
            bad.append(p.name)
    res["siblings"] = sib
    res["siblings_ok"] = not bad
    if (out / "index.html").exists():
        res["index_html_equals_page"] = (out / "index.html").read_bytes() == (out / html_name).read_bytes()
    revs = subprocess.run(["git", "log", "--format=%h", "--", tpl_rel], capture_output=True, text=True, cwd=REPO).stdout.split()
    found = None
    for r in revs:
        t = subprocess.run(["git", "show", f"{r}:{tpl_rel}"], capture_output=True, text=True, cwd=REPO).stdout
        try:
            if mod.render(t, ds) == s_html:
                found = r
                break
        except SystemExit:
            pass
    res["source_built_from_template_rev"] = found
    # Q237: NMSK_TEMPLATE_DIR names a directory with private copies of the two templates (a build that must not pick up an uncommitted edit of another change); default = viewer/
    cur = (Path(os.environ["NMSK_TEMPLATE_DIR"]) / Path(tpl_rel).name if os.environ.get("NMSK_TEMPLATE_DIR") else REPO / tpl_rel).read_text(encoding="utf-8")
    res["new_equals_current_template_plus_same_data"] = mod.render(cur, ds) == o_html
    if found:
        old = subprocess.run(["git", "show", f"{found}:{tpl_rel}"], capture_output=True, text=True, cwd=REPO).stdout
        st = subprocess.run(["git", "diff", "--numstat", found, "--", tpl_rel], capture_output=True, text=True, cwd=REPO).stdout.split()
        res["template_diff_added_removed"] = st[:2]
    res["OK"] = all([res["literals_identical"], res["geo_identical"], res["siblings_ok"], found, res["new_equals_current_template_plus_same_data"]])
    print(json.dumps(res))
    return 0 if res["OK"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
