#!/usr/bin/env python3
"""Q354: the name-card rules (scripts/zanatomy/card_rules_q354.py) applied to already-built Base pages' embedded manifest.

regen_template_only.py does not re-run the builder, so a card rule reaches a page only through a patch (precedent:
patch_manifest_records_q327.py, patch_manifest_nerves_q350.py). Per mesh:
  * a "part of" link that is not a piece of its parent (wrong class, or a name that only shares a word) is dropped exactly as the
    builder emits a never-linked structure (no `rec`, or `rec` = {procedural_badge}); a bursa / tendon sheath that lost its
    muscle's record gets `rel` = that muscle's mesh id (the card shows "Related: <muscle>" as a link, not its attachments);
  * a mesh drawn as `nerve` that is a brain part / eye part (-> cns) or middle-ear part (-> viscera) gets its class fixed;
  * raw Z-Anatomy labels get readable names (card_rules_q354.NAMES, sourced or marked mechanical; a trailing '*' dropped);
  * an eye-muscle insertion on the sclera names no bone (export_viewer_bundle.summarise, Q354);
  * nerve / target / supply lists: ids -> display names, a sided structure lists its own side only;
  * build-provenance text leaves the card: notes' build sentences and the Q250 per-structure deformation numbers move to
    rec.build_note (kept in the page data, never rendered).
Idempotent; only the manifest literal is rewritten (same compact JSON, byte-identical elsewhere).

    python3 scripts/zanatomy/patch_manifest_cards_q354.py <page_dir>... [--check] [--report out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "scripts"), str(REPO / "scripts/zanatomy")]
import card_rules_q354 as R  # noqa: E402
from export_viewer_bundle import summarise  # noqa: E402

KEY = "window.__ANATOMY_MANIFEST__="
SIDES = ("l", "r")
# Q354 data correction (Mannan 2017 p. 408): serratus posterior inferior = ventral rami T9-T12; its target moved off the T1-T8
# muscular branches onto the subcostal nerve. These records are recomputed from data/ like patch_manifest_nerves_q350.py does.
RECOMPUTE_MUSCLES = ("serratus_posterior_inferior",)
RECOMPUTE_NERVES = (*(f"intercostal_n_t{i}_muscular" for i in range(1, 7)), "thoracoabdominal_n_t7_intercostal_muscular",
                    "thoracoabdominal_n_t8_intercostal_muscular", "subcostal_n")


def _muscle_recs() -> dict:
    out = {}
    for p in (REPO / "data/muscles").rglob("*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(r, dict) and r.get("id"):
            out[r["id"]] = r
    return out


def _recompute_sources(muscles: dict) -> dict:
    out = {f"{m}_{s}": muscles[f"{m}_{s}"] for m in RECOMPUTE_MUSCLES for s in SIDES}
    tree = {}
    for p in sorted((REPO / "data/nerves").glob("*.json")):
        for e in json.loads(p.read_text(encoding="utf-8")):
            if isinstance(e, dict) and e.get("id") in RECOMPUTE_NERVES:
                tree[e["id"]] = e
    for n in RECOMPUTE_NERVES:
        for mid in (n, *(f"{n}_{s}" for s in SIDES)):
            out[mid] = tree[n]
    return out


def patch_manifest(man: dict, cats: dict, muscles: dict) -> dict:
    """Mutates `man`; returns {kind: [ids]} of what changed."""
    ch = {k: [] for k in ("link", "rel", "layer", "name", "insertion", "lists", "notes", "badge")}
    meshes = man["meshes"]
    names = {m["id"]: m.get("name") for m in meshes}
    recomp = _recompute_sources(muscles)
    for m in meshes:
        mid, raw = m["id"], m.get("name") or ""
        new = R.layer_fix(raw, m.get("sys"))
        if new:
            m["sys"] = new
            ch["layer"].append(mid)
        nm = R.display_name(mid, raw)
        if nm != raw:
            m["name"] = nm
            names[mid] = nm
            ch["name"].append(mid)
        rec = m.get("rec")
        if not rec:
            continue
        pid = rec.get("part_of_id")
        if pid and not R.part_link_ok(m["name"], m.get("sys"), pid, rec.get("part_of") or "", cats.get(pid),
                                      [c.get("id") for c in rec.get("compartments") or []]):
            if rec.get("procedural_badge"):
                m["rec"] = rec = {"procedural_badge": rec["procedural_badge"]}
            else:
                del m["rec"]
                rec = None
            ch["link"].append(mid)
            if m.get("sys") == "bursa" and pid in names and m.get("rel") != pid:
                m["rel"] = pid
                ch["rel"].append(mid)
            if rec is None:
                continue
        b0 = json.dumps(rec, sort_keys=True)
        rsrc = recomp.get(mid)
        if rsrc is not None:
            fresh = summarise(rec.get("folder"), rsrc, {})
            for k in ("nerve", "source", "targets"):
                if k in fresh and k in rec:
                    rec[k] = fresh[k]
        before = json.dumps(rec, sort_keys=True)
        src = muscles.get(mid)
        if src and "sclera" in ((src.get("attachments") or {}).get("insertion_landmark") or "").lower() and rec.get("insertion"):
            rec["insertion"] = summarise(rec.get("folder"), src, {})["insertion"]
        if json.dumps(rec, sort_keys=True) != before:
            ch["insertion"].append(mid)
        side = m.get("side")
        for k in ("nerve", "targets", "supplies"):
            if rec.get(k):
                rec[k] = R.clean_list(rec[k], side, names)
        if json.dumps(rec, sort_keys=True) != b0:
            ch["lists"].append(mid)
        moved = []
        if rec.get("notes"):
            t, mv = R.split_build_text(rec["notes"])
            if mv:
                moved.append(mv)
            if t != rec["notes"]:
                ch["notes"].append(mid)
                if t:
                    rec["notes"] = t
                else:
                    del rec["notes"]
        for k in ("latin", "source"):
            if rec.get(k) and R.tidy_text(rec[k]) != rec[k]:
                rec[k] = R.tidy_text(rec[k])
                ch["notes"].append(mid)
        if rec.get("procedural_badge"):
            t, mv = R.split_badge(rec["procedural_badge"])
            if mv:
                moved.append(mv)
                ch["badge"].append(mid)
                if t:
                    rec["procedural_badge"] = t
                else:
                    del rec["procedural_badge"]
        if moved:
            rec["build_note"] = " ".join(x for x in (rec.get("build_note"), *moved) if x)
        if not rec:
            del m["rec"]
    return ch


def patch_text(html: str, cats: dict, muscles: dict) -> tuple[str, dict]:
    if html.count(KEY) != 1:
        return html, {}
    i = html.index(KEY) + len(KEY)
    man, n = json.JSONDecoder().raw_decode(html[i:])
    before = json.dumps(man, separators=(",", ":"), ensure_ascii=True)
    ch = patch_manifest(man, cats, muscles)
    after = json.dumps(man, separators=(",", ":"), ensure_ascii=True)
    if after == before:
        return html, {}
    return html[:i] + after + html[i + n:], ch


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 if a patch is needed")
    ap.add_argument("--report", help="write the changed ids per kind (JSON)")
    a = ap.parse_args(argv)
    cats, muscles = R.atlas_categories(), _muscle_recs()
    need, rep = False, {}
    for d in map(Path, a.dirs):
        pages = sorted(d.glob("atlas_viewer*.html")) + ([d / "index.html"] if (d / "index.html").exists() else [])
        if not pages:
            sys.exit(f"{d}: no page html")
        for f in pages:
            new, ch = patch_text(f.read_text(encoding="utf-8"), cats, muscles)
            if ch:
                need = True
                if not a.check:
                    f.write_text(new, encoding="utf-8")
                rep[str(f)] = ch
            summ = " ".join(f"{k}={len(v)}" for k, v in ch.items() if v) or "0"
            print(f"{f}: {'would patch' if a.check and ch else 'patched' if ch else 'ok'} {summ}")
    if a.report:
        Path(a.report).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    return 1 if (need and a.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
