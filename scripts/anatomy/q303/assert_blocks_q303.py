#!/usr/bin/env python3
"""Q303: assert that the earlier rounds' blocks survive this round's regen, byte for byte.

Q298's search block, Q299's cut-face minimum drawn width, Q300's show-everything / model reset / bone pass and Q301's
whole control-bar block are compared between build/q301 (the baseline this round builds on, and what is live) and
build/q303. Everything must be byte-identical EXCEPT Q301's block, which is allowed to differ by exactly the two
four-line hooks this round adds to its own modules -- NMSKGroups.addTo and NMSKCombos.addPair -- and by nothing else;
that is checked as a line diff, not as a length.

    python3 scripts/anatomy/q303/assert_blocks_q303.py                                   # Q301 -> Q303 (as written)
    python3 scripts/anatomy/q303/assert_blocks_q303.py --old build/q303 --new /dev/shm/q304/final --round q304

Q304 extends it rather than adding a second script of its own (the round brief's instruction). In `--round q304`
the earlier rounds' blocks must still be byte-identical, Q301's block is no longer allowed the two Q303 hooks
(they are in the baseline now), Q303's own html block is allowed to differ by exactly the one comment Q304
rewrites in `viewer/q303/nerves.js` (the stale "the Imaging pages carry no fibular nerve" claim), and the three
per-structure data tables -- `nmsk-abbrev`, `nmsk-calibre`, `nmsk-pose-rig` -- are allowed to change ON THE TWO
IMAGING PAGES ONLY, because that is where 71 and 64 structures were added; on the four Z pages they must still be
byte-identical.
"""
import argparse, re, sys
from pathlib import Path
R = Path(__file__).resolve().parents[3]
PAGES = ["viewer_m_hr", "viewer_f_hr", "viewer_zan_atlas", "viewer_base_female", "viewer_zan_vhm", "viewer_zan_female"]
DATA = ["nmsk-q298", "nmsk-abbrev", "nmsk-calibre", "nmsk-pose-rig", "nmsk-learn", "nmsk-moments"]
AP = argparse.ArgumentParser()
AP.add_argument("--old", default="build/q301")
AP.add_argument("--new", default="build/q303")
AP.add_argument("--round", dest="rnd", default="q303", choices=["q303", "q304"])
ARG = AP.parse_args()
OLD = Path(ARG.old) if Path(ARG.old).is_absolute() else R / ARG.old
NEW = Path(ARG.new) if Path(ARG.new).is_absolute() else R / ARG.new
Q304 = ARG.rnd == "q304"
# the pages where Q304 added structures, so their per-structure tables must change and nothing else may
GREW = {"viewer_m_hr", "viewer_f_hr"} if Q304 else set()
bad = []
print("comparing", OLD, "->", NEW, "as", ARG.rnd)
for p in PAGES:
    a = (OLD/p/"index.html").read_text(encoding="utf-8", errors="surrogateescape")
    b = (NEW/p/"index.html").read_text(encoding="utf-8", errors="surrogateescape")
    row = [p]
    for d in DATA:
        pat = re.compile(r'<script[^>]*id="%s"[^>]*>.*?</script>' % d, re.S)
        ma, mb = pat.search(a), pat.search(b)
        if not ma or not mb:
            row.append("%s MISSING" % d); bad.append((p, d, "missing")); continue
        same = ma.group(0) == mb.group(0)
        allowed = Q304 and p in GREW and d in ("nmsk-abbrev", "nmsk-calibre", "nmsk-pose-rig")
        row.append("%s %d%s" % (d, len(mb.group(0)), "" if same else (" grew (allowed)" if allowed else " CHANGED")))
        if not same and not allowed: bad.append((p, d, "changed"))
        if same and allowed: bad.append((p, d, "did NOT change although %d structures were added" % 1))
    # Q299's cut-face minimum drawn width
    na, nb = a.count("bandFrac"), b.count("bandFrac")
    row.append("bandFrac %d->%d%s" % (na, nb, "" if na == nb else " CHANGED"))
    if na != nb: bad.append((p, "bandFrac", "%d->%d" % (na, nb)))
    # Q301's control bar and its modules, Q300's, Q298's, Q227's cut-face kernel
    for sym in ("NMSKGroups", "NMSKCombos", "NMSKRenderStyle", "NMSKPeel", "NMSKFat", "NMSKInfo", "NMSKTissue",
                "NMSKShowAll", "NMSKModelReset", "NMSKBoneRead", "NMSKQ298", "NMSKCapCore", "NMSKHistory"):
        ca, cb = a.count("var %s = (function()" % sym), b.count("var %s = (function()" % sym)
        if not (ca == cb == 1):
            if a.count("function %s(" % sym) == b.count("function %s(" % sym) >= 1:
                continue
            bad.append((p, sym, "%d->%d" % (ca, cb)))
    # Q301's own block, byte identical between the markers
    for tag in ("Q294", "Q298", "Q300", "Q301") + (("Q303",) if Q304 else ()):
        m = re.compile(r"<!-- %s html begin -->(.*?)<!-- %s html end -->" % (tag, tag), re.S)
        xa, xb = m.search(a), m.search(b)
        if not xa or not xb:
            bad.append((p, tag + " block", "missing")); continue
        A, B = xa.group(1), xb.group(1)
        if A != B:
            if Q304 and tag == "Q303":
                # exactly the one comment Q304 rewrites in viewer/q303/nerves.js: the stale claim that the
                # Imaging pages carry no fibular nerve. No code line may move.
                import difflib
                dd = [x for x in difflib.unified_diff(A.splitlines(), B.splitlines(), lineterm="", n=0)
                      if x[:1] in "+-" and x[:3] not in ("+++", "---")]
                add2 = [x[1:] for x in dd if x.startswith("+")]
                rem2 = [x[1:] for x in dd if x.startswith("-")]
                # The precise rule: with every /* ... */ comment removed, the two blocks must be BYTE-IDENTICAL.
                # That proves no code line moved, which a line-by-line heuristic cannot (a comment line in this
                # module legitimately contains a semicolon, and the first version of this check tripped on it).
                nc = lambda t: re.sub(r"/\*.*?\*/", "", t, flags=re.S)
                okc = nc(A) == nc(B) and len(rem2) == 3 and len(add2) == 7
                row.append("%s %d -> %d (the Q304 comment rewrite%s)" % (tag, len(A), len(B), "" if okc else " PLUS CODE"))
                if not okc:
                    bad.append((p, tag + " block", "changed outside the comment: -%d +%d" % (len(rem2), len(add2))))
                continue
            if tag != "Q301":
                bad.append((p, tag + " block", "changed")); continue
            # Q301's block is allowed to differ by EXACTLY the two four-line hooks this round adds to its own
            # modules (NMSKGroups.addTo, NMSKCombos.addPair), carried in by sync_q301.py. Nothing else.
            import difflib
            d = [x for x in difflib.unified_diff(A.splitlines(), B.splitlines(), lineterm="", n=0)
                 if x[:1] in "+-" and x[:3] not in ("+++", "---")]
            added = [x[1:] for x in d if x.startswith("+")]
            removed = [x[1:] for x in d if x.startswith("-")]
            if Q304:
                bad.append((p, tag + " block", "changed; in Q304 Q301's block must be byte-identical"))
                continue
            okdiff = (not removed and len(added) == 18
                      and any("addTo:function(key, m)" in x for x in added)
                      and any("addPair:function(r)" in x for x in added))
            row.append("%s %d -> %d (+%d, the two Q303 hooks%s)" % (tag, len(A), len(B), len(B) - len(A),
                                                                    "" if okdiff else " PLUS SOMETHING ELSE"))
            if not okdiff:
                bad.append((p, tag + " block", "changed by more than the two hooks: -%d +%d" % (len(removed), len(added))))
            continue
        row.append("%s %d" % (tag, len(B)))
    # Q303's own modules present exactly once
    for sym in ("NMSKPCA", "NMSKStep", "NMSKPx", "NMSKNervePass", "NMSKTarget", "NMSKAutoFocus", "NMSKFourUp",
                "NMSKViews", "NMSKNerves", "NMSKQ303"):
        if b.count("var %s = (function()" % sym) != 1:
            bad.append((p, sym, "not once"))
    print("  " + " | ".join(row))
print("ASSERT the earlier rounds' blocks survive:", "OK" if not bad else bad)
sys.exit(1 if bad else 0)
