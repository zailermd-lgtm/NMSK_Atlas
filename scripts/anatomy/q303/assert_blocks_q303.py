#!/usr/bin/env python3
"""Q303: assert that the earlier rounds' blocks survive this round's regen, byte for byte.

Q298's search block, Q299's cut-face minimum drawn width, Q300's show-everything / model reset / bone pass and Q301's
whole control-bar block are compared between build/q301 (the baseline this round builds on, and what is live) and
build/q303. Everything must be byte-identical EXCEPT Q301's block, which is allowed to differ by exactly the two
four-line hooks this round adds to its own modules -- NMSKGroups.addTo and NMSKCombos.addPair -- and by nothing else;
that is checked as a line diff, not as a length.

    python3 scripts/anatomy/q303/assert_blocks_q303.py                                   # Q301 -> Q303 (as written)
    python3 scripts/anatomy/q303/assert_blocks_q303.py --old build/q303 --new /dev/shm/q304/final --round q304
    python3 scripts/anatomy/q303/assert_blocks_q303.py --old build/q304 --new /dev/shm/q305/final --round q305
    python3 scripts/anatomy/q303/assert_blocks_q303.py --old build/q304 --new /dev/shm/q307/final --round q307

Q305 extends it again, and it is the strictest round so far: it adds a block of its own and changes NOTHING else --
a box is moved by its own `translate`, which composes with the five earlier rounds' placement code instead of
replacing it, so there is no hook, no engine patch and no allowed difference. In `--round q305` every earlier
round's block (Q294, Q298, Q300, Q301, Q303) and every per-structure data table must be byte-identical on ALL SIX
pages, and the Q305 block itself must appear exactly once with its three modules in it.

Q307 extends it too, and like Q305 it changes no engine code at all: this round adds geometry and card text, so
in `--round q307` every earlier round's block (Q294, Q298, Q300, Q301, Q303) must be byte-identical on ALL SIX
pages, and the per-structure data tables -- `nmsk-abbrev`, `nmsk-calibre`, `nmsk-pose-rig`, `nmsk-q298` -- are
allowed to change ON THE TWO IMAGING PAGES ONLY, where 57 and 60 nerves were added and 1 and 2 replaced; on the
four Z pages they must still be byte-identical. It also asserts that the new build carries NO BLOCK FROM A ROUND
THIS ONE DID NOT BUILD ON: the first Q307 build was made in a working tree that another round was editing at the
same time, the regen chain re-applied `viewer/*.template.html` as it stood on disk, and the six pages came out
carrying that round's unlanded UI block -- which every earlier check here passed, because none of them looked for
a block that should not be there. Q307 builds from a private template copy (`NMSK_TEMPLATE_DIR`, the mechanism
Q237 added for exactly this) and this assertion is what proves it worked. `nmsk-q298` is allowed to change there
but is NOT required to:
running this check is how Q307 learned that it does not -- Q298's adjacency, relation and alias tables are
committed data that `--inject` only copies, so a nerve added to a page gets no adjacency row and no Related /
Functional-group entry until that builder is re-run. Q304 added 71 and 64 nerves under the same gap, so it is
inherited rather than new, and it is in the open items for the owner with its cost.

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
AP.add_argument("--round", dest="rnd", default="q303", choices=["q303", "q304", "q305", "q307"])
ARG = AP.parse_args()
OLD = Path(ARG.old) if Path(ARG.old).is_absolute() else R / ARG.old
NEW = Path(ARG.new) if Path(ARG.new).is_absolute() else R / ARG.new
Q304 = ARG.rnd == "q304"
Q305 = ARG.rnd == "q305"
Q307 = ARG.rnd == "q307"
# the pages where Q304 / Q307 added structures, so their per-structure tables must change and nothing else may
GREW = {"viewer_m_hr", "viewer_f_hr"} if (Q304 or Q307) else set()
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
        must_grow = (Q304 or Q307) and p in GREW and d in ("nmsk-abbrev", "nmsk-calibre", "nmsk-pose-rig")
        allowed = must_grow or (Q307 and p in GREW and d == "nmsk-q298")
        row.append("%s %d%s" % (d, len(mb.group(0)), "" if same else (" grew (allowed)" if allowed else " CHANGED")))
        if not same and not allowed: bad.append((p, d, "changed"))
        if same and must_grow: bad.append((p, d, "did NOT change although structures were added"))
    if Q307:
        # no block from a round this build does not stand on (see the module docstring)
        for tag in ("Q305", "Q306"):
            na2, nb2 = a.count("<!-- %s html begin -->" % tag), b.count("<!-- %s html begin -->" % tag)
            row.append("%s %d->%d" % (tag, na2, nb2))
            if nb2 != na2:
                bad.append((p, tag + " block", "appeared in this build although Q307 does not build on it "
                                               "(%d -> %d)" % (na2, nb2)))
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
    for tag in ("Q294", "Q298", "Q300", "Q301") + (("Q303",) if (Q304 or Q305 or Q307) else ()):
        m = re.compile(r"<!-- %s html begin -->(.*?)<!-- %s html end -->" % (tag, tag), re.S)
        xa, xb = m.search(a), m.search(b)
        if not xa or not xb:
            bad.append((p, tag + " block", "missing")); continue
        A, B = xa.group(1), xb.group(1)
        if A != B:
            if Q304 and tag == "Q303":   # Q305 allows nothing here: see the q305 branch below
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
                # Q304 changes TWO things inside Q303's own block, both of them stated: the stale comment above
                # `var MAJOR` (comment only), and three lines of `absent()` -- the id is now matched with its
                # underscores turned into spaces as well as raw, because the engine's list does not always carry a
                # display name and `/\btibial\b/` can never match `tibial_n`. With the comments stripped, the only
                # difference allowed is exactly those three lines, named here.
                da = [x for x in difflib.unified_diff(nc(A).splitlines(), nc(B).splitlines(), lineterm="", n=0)
                      if x[:1] in "+-" and x[:3] not in ("+++", "---")]
                code_add = [x[1:].strip() for x in da if x.startswith("+")]
                code_rem = [x[1:].strip() for x in da if x.startswith("-")]
                WANT_ADD = ['rows.forEach(function(r){',
                            'var idn = String(r.id || "").replace(/_/g, " ");',
                            'if (p[1].test(r.id) || p[1].test(idn) || p[1].test(r.name)) hit++;',
                            '});']
                WANT_REM = ['rows.forEach(function(r){ if (p[1].test(r.id) || p[1].test(r.name)) hit++; });']
                okc = (code_add == WANT_ADD and code_rem == WANT_REM
                       and len(rem2) == 5 and len(add2) == 18)
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
            if Q304 or Q305:
                bad.append((p, tag + " block", "changed; in %s Q301's block must be byte-identical" % ARG.rnd))
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
    if Q305:
        m = re.compile(r"<!-- Q305 html begin -->(.*?)<!-- Q305 html end -->", re.S).search(b)
        if not m:
            bad.append((p, "Q305 block", "missing"))
        else:
            row.append("Q305 %d" % len(m.group(1)))
            for sym in ("NMSKGuard", "NMSKMove", "NMSKQ305"):
                if m.group(1).count("var %s = (function()" % sym) != 1:
                    bad.append((p, sym, "not once inside the Q305 block"))
            if "<!-- Q305 html begin -->" in a:
                bad.append((p, "Q305 block", "was already in the baseline"))
        # and nothing of this round may reach the engines: no glue splice, no new marker pair of ours anywhere else
        if b.count("/* Q305 glue begin */"):
            bad.append((p, "Q305 glue", "this round must not patch either engine"))
    # Q303's own modules present exactly once
    for sym in ("NMSKPCA", "NMSKStep", "NMSKPx", "NMSKNervePass", "NMSKTarget", "NMSKAutoFocus", "NMSKFourUp",
                "NMSKViews", "NMSKNerves", "NMSKQ303"):
        if b.count("var %s = (function()" % sym) != 1:
            bad.append((p, sym, "not once"))
    print("  " + " | ".join(row))
print("ASSERT the earlier rounds' blocks survive:", "OK" if not bad else bad)
sys.exit(1 if bad else 0)
