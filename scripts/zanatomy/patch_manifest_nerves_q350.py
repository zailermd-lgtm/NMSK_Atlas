#!/usr/bin/env python3
"""Q350: carry the Q348 book corrections of three muscle records' nerve supply into already-built Base pages.

regen_template_only.py does not re-run the builder; it re-reads the manifest embedded in each page, so a corrected record reaches a
page only through a patch (precedent: patch_manifest_records_q327.py). For the meshes below, the builder's own inspector summary
(export_viewer_bundle.summarise, exactly as build_zan_atlas_viewer.py calls it) is recomputed from the current record and ONLY these
keys are replaced: rec.nerve, rec.source, rec.compartments[].nerves (muscles); rec.targets (nerves whose target list changed).
Records: serratus posterior superior (T2-T5, Mannan 2017 p. 407), pectoralis minor (lateral + medial pectoral, p. 106), plantar /
dorsal interossei of the foot (superficial-branch exception, pp. 291 / 295). Idempotent; only the manifest literal is rewritten.

    python3 scripts/zanatomy/patch_manifest_nerves_q350.py <page_dir>... [--check]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from export_viewer_bundle import summarise  # noqa: E402  (the builder's own record -> inspector summary)

KEY = "window.__ANATOMY_MANIFEST__="
SIDES = ("l", "r")
MUSCLES = ("serratus_posterior_superior", "pectoralis_minor", "plantar_interossei", "dorsal_interossei_foot")
NERVES = ("lateral_pectoral_n", "lateral_plantar_n_superficial_branch",
          "intercostal_n_t1_muscular", "intercostal_n_t6_muscular",
          *(f"thoracoabdominal_n_t{i}_intercostal_muscular" for i in range(7, 12)))


def _records():
    out = {}
    for m in MUSCLES:
        for s in SIDES:
            (p,) = (REPO / "data/muscles").rglob(f"{m}_{s}.json")
            out[f"{m}_{s}"] = json.loads(p.read_text(encoding="utf-8"))
    tree = {}
    for p in sorted((REPO / "data/nerves").glob("*.json")):
        for e in json.loads(p.read_text(encoding="utf-8")):
            if isinstance(e, dict) and e.get("id") in NERVES:
                tree[e["id"]] = e
    for n in NERVES:
        for mid in (n, *(f"{n}_{s}" for s in SIDES)):
            out[mid] = tree[n]
    return out


def patch_text(html: str, recs: dict) -> tuple[str, list[str]]:
    if html.count(KEY) != 1:
        return html, []
    i = html.index(KEY) + len(KEY)
    man, n = json.JSONDecoder().raw_decode(html[i:])
    changed = []
    for m in man["meshes"]:
        rec = m.get("rec")
        src = recs.get(m.get("id")) or recs.get((rec or {}).get("part_of_id"))
        if not rec or src is None:
            continue
        new = summarise(rec.get("folder"), src, {})
        before = json.dumps(rec, sort_keys=True)
        for k in ("nerve", "source", "targets"):
            if k in new and k in rec:
                rec[k] = new[k]
        by_id = {c["id"]: c for c in new.get("compartments", [])}
        for c in rec.get("compartments", []):
            if c.get("id") in by_id:
                c["nerves"] = by_id[c["id"]]["nerves"]
        if json.dumps(rec, sort_keys=True) != before:
            changed.append(m["id"])
    if not changed:
        return html, []
    return html[:i] + json.dumps(man, separators=(",", ":"), ensure_ascii=True) + html[i + n:], changed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 if a patch is needed")
    a = ap.parse_args(argv)
    recs = _records()
    need = False
    for d in map(Path, a.dirs):
        pages = sorted(d.glob("atlas_viewer*.html")) + ([d / "index.html"] if (d / "index.html").exists() else [])
        if not pages:
            sys.exit(f"{d}: no page html")
        for f in pages:
            new, ids = patch_text(f.read_text(encoding="utf-8"), recs)
            if ids:
                need = True
                if not a.check:
                    f.write_text(new, encoding="utf-8")
            print(f"{f}: {'would patch' if a.check and ids else 'patched' if ids else 'ok'} {len(ids)}: {' '.join(ids)}")
    return 1 if (need and a.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
