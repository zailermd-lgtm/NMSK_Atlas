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
    python3 scripts/anatomy/q303/assert_blocks_q303.py --old build/q307 --new /dev/shm/q306/final --round q306
    python3 scripts/anatomy/q303/assert_blocks_q303.py --old build/q306 --new /dev/shm/q308/final --round q308

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
a block that should not be there. Q307 first built from a private template copy (`NMSK_TEMPLATE_DIR`, the mechanism
Q237 added for exactly this) and this assertion is what proved it worked; Q305 then LANDED, so the final Q307
build stands on `build/q305` and asserts Q305's own block byte-identical alongside the five older ones, while
still refusing any block from a round that has not landed. `nmsk-q298` is allowed to change there
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

Q306 extends it, and it is the first round since Q303 that has to be allowed to change an earlier round's
block -- so the allowance is bounded precisely rather than loosened. In `--round q306`:
  * Q298's HTML block IS allowed to change, because this round edits three of Q298's own modules and
    nothing else can carry them: `search.js` says when a result set is only an approximate match
    (`approx` / `note_first` -- the defect that answered "psoas minor" with Psoas major at rank 1),
    `q298.js` overlays the Q306 data block onto Q298's, and `bar.js` renders the new lines through one
    guarded `if (window.NMSKQ306)`. The rule is the one Q304 used for Q303's block: with every /* ... */
    comment stripped, the only code lines that may differ are the ones named in WANT306_ADD / WANT306_REM
    here. No other earlier block may differ at all.
  * `nmsk-q298` (the DATA block) must change ON THE TWO IMAGING PAGES and must be byte-identical on the
    four Z pages. This is the gap Q307 found and recorded: Q298's adjacency and relation tables are
    committed data that `--inject` only copies, so the 135 and 124 nerves Q304 and Q307 added to the
    Imaging pages had no adjacency row and no Related / Functional-group entry. Q306 re-runs both builders
    over those two pages -- and only those two, because the Z pages' geometry never changed -- so the
    block MUST grow there and MUST NOT move anywhere else.
In `--round q308` the build stands on `build/q306`, which stands on `build/q307`, so EVERY earlier round's
html block (Q294, Q298, Q300, Q301, Q303, Q305 and now Q306) must be byte-identical on ALL SIX pages and must
still be present exactly as often as before -- Q308 adds data and cards, not a block of its own, and no marker
pair from a later round may appear. What MUST change, on every one of the six pages, is every per-structure
data table, because Q308 adds 4-10 structures to each: `nmsk-abbrev`, `nmsk-calibre`, `nmsk-pose-rig`,
`nmsk-q298` (its adjacency and relation builders re-run on all six, not only the Imaging pair) and
`nmsk-q306` (the search table, which also carries this round's correction to three absence explanations).
A table that does NOT change is a failure there, not a pass: it would mean the inject step was skipped.

  * Q306's own html block and its `nmsk-q306` data block must each appear exactly once, and must not have
    been in the baseline.
  * Q305's and Q303's blocks must be byte-identical, like every other round's.
"""
import argparse, re, sys
from pathlib import Path
R = Path(__file__).resolve().parents[3]
PAGES = ["viewer_m_hr", "viewer_f_hr", "viewer_zan_atlas", "viewer_base_female", "viewer_zan_vhm", "viewer_zan_female"]
DATA = ["nmsk-q298", "nmsk-abbrev", "nmsk-calibre", "nmsk-pose-rig", "nmsk-learn", "nmsk-moments"]
AP = argparse.ArgumentParser()
AP.add_argument("--old", default="build/q301")
AP.add_argument("--new", default="build/q303")
AP.add_argument("--round", dest="rnd", default="q303",
                choices=["q303", "q304", "q305", "q306", "q307", "q308"])
ARG = AP.parse_args()
OLD = Path(ARG.old) if Path(ARG.old).is_absolute() else R / ARG.old
NEW = Path(ARG.new) if Path(ARG.new).is_absolute() else R / ARG.new
Q304 = ARG.rnd == "q304"
Q305 = ARG.rnd == "q305"
Q307 = ARG.rnd == "q307"
Q306 = ARG.rnd == "q306"
Q308 = ARG.rnd == "q308"
# the pages where Q304 / Q307 added structures, so their per-structure tables must change and nothing else may
# Q308 adds geometry to ALL SIX pages, so every page's per-structure table must grow there.
GREW = (set(PAGES) if Q308 else
        ({"viewer_m_hr", "viewer_f_hr"} if (Q304 or Q307 or Q306) else set()))
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
        if Q306:
            # this round touches no geometry and no card, so the three per-structure tables must NOT move.
            # `nmsk-q298` MUST change on the two Imaging pages, because the adjacency and relation builders
            # were re-run there for the nerves Q304 and Q307 added -- and must not change anywhere else.
            must_grow = p in GREW and d == "nmsk-q298"
        if Q308:
            # Q308 adds 4-10 structures to every page, so EVERY per-structure table must change on EVERY page:
            # the abbreviation, calibre and pose-rig tables, Q298's own (its adjacency and relation builders
            # were re-run on all six, which the coordinator required rather than the Imaging pair alone) and
            # Q306's search table. Nothing else may move.
            must_grow = d in ("nmsk-abbrev", "nmsk-calibre", "nmsk-pose-rig", "nmsk-q298", "nmsk-q306")
        allowed = must_grow or (Q307 and p in GREW and d == "nmsk-q298")
        row.append("%s %d%s" % (d, len(mb.group(0)), "" if same else (" grew (allowed)" if allowed else " CHANGED")))
        if not same and not allowed: bad.append((p, d, "changed"))
        if same and must_grow: bad.append((p, d, "did NOT change although structures were added"))
    if Q306:
        # Q306 stands on Q307, which has landed, so every earlier round's block is in the baseline and the
        # only new marker pair allowed anywhere is Q306's own.
        for tag in ("Q308", "Q309"):
            na2, nb2 = a.count("<!-- %s html begin -->" % tag), b.count("<!-- %s html begin -->" % tag)
            if nb2 != na2:
                bad.append((p, tag + " block", "appeared in this build although Q306 does not build on it "
                                               "(%d -> %d)" % (na2, nb2)))
    if Q308:
        # Q308 stands on Q306, which stands on Q307: so every earlier round's block is already in the baseline
        # and NO new marker pair may appear. Q308 adds data and cards, not an html block of its own.
        for tag in ("Q309", "Q310"):
            na2, nb2 = a.count("<!-- %s html begin -->" % tag), b.count("<!-- %s html begin -->" % tag)
            if nb2 != na2:
                bad.append((p, tag + " block", "appeared in this build although Q308 does not build on it "
                                               "(%d -> %d)" % (na2, nb2)))
        for tag in ("Q294", "Q298", "Q300", "Q301", "Q303", "Q305", "Q306"):
            na2, nb2 = a.count("<!-- %s html begin -->" % tag), b.count("<!-- %s html begin -->" % tag)
            row.append("%s %d->%d" % (tag, na2, nb2))
            if nb2 != na2 or nb2 < 1:
                bad.append((p, tag + " block", "must survive this build unchanged in count (%d -> %d)"
                                               % (na2, nb2)))
    if Q307:
        # no block from a round this build does not stand on (see the module docstring)
        for tag in ("Q306",):   # Q305 landed before Q307 published, so Q307 builds on it: see the note below
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
    for tag in ("Q294", "Q298", "Q300", "Q301") + (("Q303",) if (Q304 or Q305 or Q306 or Q307 or Q308) else ()) \
               + (("Q305",) if (Q306 or Q307 or Q308) else ()) + (("Q306",) if Q308 else ()):
        m = re.compile(r"<!-- %s html begin -->(.*?)<!-- %s html end -->" % (tag, tag), re.S)
        xa, xb = m.search(a), m.search(b)
        if not xa or not xb:
            bad.append((p, tag + " block", "missing")); continue
        A, B = xa.group(1), xb.group(1)
        if A != B:
            if Q308 and tag == "Q298":
                # Q308 changes exactly ONE thing inside Q298's own block, and it is a COMMENT: the stale claim
                # that 3.46 mm is the surface-to-surface bound. The number the page PRINTS lives in the DATA
                # (`threshold_mm` in Q298_adjacency_<key>.json, now the strict sqrt(3) * 2 * cell = 6.93 mm),
                # not in this code, so no code line may move. The precise rule, Q304's: with every /* ... */
                # comment removed the two blocks must be BYTE-IDENTICAL.
                nc = lambda t: re.sub(r"/\*.*?\*/", "", t, flags=re.S)
                if nc(A) == nc(B):
                    row.append("Q298 block: comment-only change (allowed)")
                    continue
                bad.append((p, tag + " block", "changed in CODE, not only in a comment"))
                continue
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
            if Q306 and tag == "Q298":
                # The ONE allowance of this round, bounded exactly as Q304 bounded Q303's: with every
                # comment stripped, only these code lines may differ. Three of Q298's own modules change --
                # search.js (approx / note_first / per-id score), q298.js (overlay the Q306 data block),
                # bar.js (the host element, the offer count on an explanation, and the guarded call).
                import difflib
                nc6 = lambda t: re.sub(r"/\*.*?\*/", "", t, flags=re.S)
                d6 = [x for x in difflib.unified_diff(nc6(A).splitlines(), nc6(B).splitlines(),
                                                      lineterm="", n=0)
                      if x[:1] in "+-" and x[:3] not in ("+++", "---")]
                a6 = [x[1:].strip() for x in d6 if x.startswith("+") and x[1:].strip()]
                r6 = [x[1:].strip() for x in d6 if x.startswith("-") and x[1:].strip()]
                MUST = ["out.approx", "out.note_first", "out.score[pick[j].id]", "nmsk-q306",
                        "window.NMSKQ306", 'id="q8-q306"',
                        # the FOURTH change, found by Q306's own browser run rather than by review: on a
                        # phone both engines close the panel that holds the search box, so a concept card
                        # left in the bar's own container sat inside a hidden panel exactly when it was
                        # wanted and its button could never be pressed. Q298 had already recorded this trap
                        # for its expansion row; `reparent()` now carries Q306's host with it.
                        'var q6 = $("q8-q306")',
                        # and the fifth: the reserved band is measured AFTER reparent() has moved the host,
                        # because the strip's height is only knowable once it holds what it will hold.
                        "NMSKQ306.band()"]
                # every added line must belong to one of the three named changes, and NOTHING may be removed
                # that is not one of the four lines they replace
                ALLOW_REM = ['var out = {q:q0, ids:[], why:{}, groups:[], notes:[], stats:{exact:0, alias:0, wordstart:0, substr:0, fuzzy:0}};',
                             'try { D = el ? JSON.parse(el.textContent || "{}") : {}; } catch (err){ D = {}; }',
                             'out.notes.push(ns[j]); break;',
                             'return "<b>" + esc(x.name) + "</b> — no mesh on this page. " + esc(x.why) +',
                             '" This project\'s name for it: <i>" + esc(x.canon) + "</i>.";',
                             "'<p class=\"q8-note\" id=\"q8-notes\" hidden></p>' +",
                             "floatBox.hidden = to !== floatBox || !eb || eb.hidden;",
                             "floatBox.hidden = to !== floatBox || ((!eb || eb.hidden) && (!q6 || q6.hidden));"]
                stray_rem = [x for x in r6 if x not in ALLOW_REM]
                have_all = all(any(k in x for x in a6) for k in MUST)
                ok6 = have_all and not stray_rem
                row.append("%s %d -> %d (the three Q298 modules this round edits%s)"
                           % (tag, len(A), len(B), "" if ok6 else " PLUS SOMETHING ELSE"))
                if not ok6:
                    bad.append((p, tag + " block",
                                "changed beyond the named lines: %d stray removals %r; missing %r"
                                % (len(stray_rem), stray_rem[:3],
                                   [k for k in MUST if not any(k in x for x in a6)])))
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
            if Q304 or Q305 or Q306:
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
    if Q306:
        m6 = re.compile(r"<!-- Q306 html begin -->(.*?)<!-- Q306 html end -->", re.S).search(b)
        if not m6:
            bad.append((p, "Q306 block", "missing"))
        else:
            row.append("Q306 %d" % len(m6.group(1)))
            if m6.group(1).count("var NMSKQ306 = (function()") != 1:
                bad.append((p, "NMSKQ306", "not once inside the Q306 block"))
            if "<!-- Q306 html begin -->" in a:
                bad.append((p, "Q306 block", "was already in the baseline"))
        # the data block the build step fills, exactly once, and filled
        n6 = b.count('id="nmsk-q306"')
        row.append("nmsk-q306 x%d" % n6)
        if n6 != 1:
            bad.append((p, "nmsk-q306", "appears %d times" % n6))
        else:
            mb6 = re.search(r'<script[^>]*id="nmsk-q306"[^>]*>(.*?)</script>', b, re.S)
            if not mb6 or len(mb6.group(1)) < 10000:
                bad.append((p, "nmsk-q306", "block is empty or tiny: the build step did not --inject"))
            else:
                row.append("nmsk-q306 %d" % len(mb6.group(1)))
        if "<!-- Q306 glue begin -->" in b:
            bad.append((p, "Q306 glue", "this round must not patch either engine"))
    # Q303's own modules present exactly once
    for sym in ("NMSKPCA", "NMSKStep", "NMSKPx", "NMSKNervePass", "NMSKTarget", "NMSKAutoFocus", "NMSKFourUp",
                "NMSKViews", "NMSKNerves", "NMSKQ303"):
        if b.count("var %s = (function()" % sym) != 1:
            bad.append((p, sym, "not once"))
    print("  " + " | ".join(row))
print("ASSERT the earlier rounds' blocks survive:", "OK" if not bad else bad)
sys.exit(1 if bad else 0)
